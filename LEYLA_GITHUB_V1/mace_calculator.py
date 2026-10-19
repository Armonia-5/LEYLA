import argparse
import glob
import os
import re
import sys
import yaml
from copy import copy

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.multiprocessing as mp
from ase.io import read, write
from mace.calculators import MACECalculator
from tqdm import tqdm


def process_chunk(device_str, start_idx, end_idx, args, tag):
    """Funzione di calcolo eseguita su una porzione (chunk) della traiettoria."""
    traj_chunk = read(args.file, index=f'{start_idx}:{end_idx}:{args.stride}')
    calc = MACECalculator(model_paths=args.model, device=device_str, model_type=args.type)

    uncertainties = []
    traj_above_thresh = []

    tmp_out = f"tmp_out_rank{tag}.xyz"
    tmp_thresh = f"tmp_thresh_rank{tag}.xyz"
    tmp_unc = f"tmp_unc_rank{tag}.npy"

    show_pbar = (str(tag) == "0")
    iterator = tqdm(traj_chunk, desc=f"GPU/Rank {tag}") if show_pbar else traj_chunk

    for atoms in iterator:
        calc.calculate(atoms)
        atoms.calc = copy(calc)

        if calc.num_models > 1:
            fstd = calc.results['forces_comm'].std(axis=0)
            var = np.amax(fstd, axis=1, keepdims=True)
            atoms.set_array('force_std_comp_max', var.flatten())

            frame_max_unc = float(var.max())
            atoms.info['uncertainty'] = frame_max_unc
            uncertainties.append(frame_max_unc)

            if args.threshold <= frame_max_unc <= args.threshold_max:
                traj_above_thresh.append(atoms)

    write(tmp_out, traj_chunk)
    if len(traj_above_thresh) > 0:
        write(tmp_thresh, traj_above_thresh)

    np.save(tmp_unc, np.array(uncertainties))
    return uncertainties


def merge_and_plot(num_chunks, args):
    """Unisce i file temporanei prodotti dai worker e genera grafico e statistiche."""
    print("\nINFO      | Checking and merging temporary files...")

    unc_files = glob.glob("tmp_unc_rank*.npy")

    # Se l'output esiste già e non ci sono temp file, la fase di merge è già stata completata
    if not unc_files and os.path.exists(args.outfile):
        print(f"INFO      | Main output file '{args.outfile}' already exists and no temp files found. Skipping merge.")
        return

    # Identifica i rank effettivamente generati dai file temporanei
    ranks = []
    for f in unc_files:
        match = re.search(r"tmp_unc_rank(\d+)\.npy", f)
        if match:
            ranks.append(int(match.group(1)))

    if not ranks:
        if num_chunks is not None and num_chunks > 0:
            ranks = list(range(num_chunks))
        else:
            print("WARNING   | No temporary files found to merge.")
            return

    ranks.sort()

    tmp_out_files = [f"tmp_out_rank{i}.xyz" for i in ranks if os.path.exists(f"tmp_out_rank{i}.xyz")]
    tmp_thresh_files = [f"tmp_thresh_rank{i}.xyz" for i in ranks if os.path.exists(f"tmp_thresh_rank{i}.xyz")]
    tmp_unc_files = [f"tmp_unc_rank{i}.npy" for i in ranks if os.path.exists(f"tmp_unc_rank{i}.npy")]

    if os.path.exists(args.outfile):
        os.remove(args.outfile)
    if os.path.exists(args.out_thresh):
        os.remove(args.out_thresh)

    if tmp_out_files:
        os.system(f"cat {' '.join(tmp_out_files)} > {args.outfile}")
        print(f'INFO      | Written unified trajectory: {args.outfile}')

    if tmp_thresh_files:
        os.system(f"cat {' '.join(tmp_thresh_files)} > {args.out_thresh}")
        print(f'INFO      | Written unified threshold trajectory: {args.out_thresh}')
    else:
        print(f'INFO      | 0 frames within window [{args.threshold}, {args.threshold_max}] eV/Å. File {args.out_thresh} not created.')

    all_uncertainties = []
    for f in tmp_unc_files:
        all_uncertainties.extend(np.load(f))

    # Pulizia file temporanei
    all_temp_files = tmp_out_files + tmp_thresh_files + tmp_unc_files
    for f in set(all_temp_files):
        if os.path.exists(f):
            os.remove(f)

    if len(all_uncertainties) > 0:
        unc = np.array(all_uncertainties)
        n_total = len(unc)
        in_window = (unc >= args.threshold) & (unc <= args.threshold_max)
        n_selected = np.sum(in_window)
        pct_selected = (n_selected / n_total) * 100 if n_total > 0 else 0.0

        print('\n' + '=' * 50)
        print('      MACE UNCERTAINTY STATISTICS        ')
        print('=' * 50)
        print(f'Total configurations:       {n_total}')
        print(f'Interval (Window):          [{args.threshold:.4f}, {args.threshold_max:.4f}] eV/Å')
        print(f'Selected frames (window): {n_selected} ({pct_selected:.2f}%)')
        print(f'Max uncertainty found:     {unc.max():.4f} eV/Å')
        print(f'Mean uncertainty:          {unc.mean():.4f} eV/Å')
        print('=' * 50 + '\n')

        max_bin_val = max(unc.max() * 1.05, args.threshold_max * 1.2 if args.threshold_max != float('inf') else args.threshold * 2)
        bins = np.linspace(0, max_bin_val, 60)
        bin_width = bins[1] - bins[0]

        h1, x_edges = np.histogram(unc, bins=bins)
        h2, _ = np.histogram(unc[in_window], bins=bins)
        x_centers = (x_edges[:-1] + x_edges[1:]) / 2

        if args.out_data:
            hist_data = np.column_stack((x_centers, h1, h2, x_edges[:-1], x_edges[1:]))
            header = (
                f"MACE Uncertainty Histogram Data\n"
                f"Window: [{args.threshold:.4f}, {args.threshold_max:.4f}] eV/A | Total Frames: {n_total} | Selected: {n_selected}\n"
                f"Columns:\n"
                f"1: bin_center [eV/A]\n"
                f"2: count_all\n"
                f"3: count_selected_in_window\n"
                f"4: bin_left [eV/A]\n"
                f"5: bin_right [eV/A]"
            )
            np.savetxt(args.out_data, hist_data, fmt="%.6f %d %d %.6f %.6f", header=header)
            print(f'INFO      | Histogram data saved in: {args.out_data}')

        if args.out_raw:
            raw_data = np.column_stack((np.arange(len(unc)), unc))
            np.savetxt(args.out_raw, raw_data, fmt="%d %.6f", header="Frame_Index Uncertainty[eV/A]")
            print(f'INFO      | Raw uncertainties saved in: {args.out_raw}')

        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=150)
        ax.bar(x_centers, h1, width=bin_width, color='#1f77b4', alpha=0.4, label='All configurations')
        ax.bar(x_centers, h2, width=bin_width, color='#2ca02c', alpha=0.7, label=f'Selected Window [{args.threshold:.4f}, {args.threshold_max if args.threshold_max != float("inf") else "inf"}]')
        ax.axvline(args.threshold, color='red', linestyle='--', linewidth=1.2, alpha=0.8, label='Lower Threshold')
        if args.threshold_max != float('inf'):
            ax.axvline(args.threshold_max, color='orange', linestyle='--', linewidth=1.2, alpha=0.8, label='Upper Threshold')
        ax.set_xlabel(r'Uncertainty on forces $\sigma_{max}^{(MACE)}$ [eV/Å]')
        ax.set_ylabel('Number of configurations')
        ax.set_title('Uncertainty Distribution (Committee MACE)')
        ax.legend(frameon=True, loc='upper right')
        ax.grid(True, linestyle=':', alpha=0.5)

        plt.tight_layout()
        plt.savefig(args.plotfile)
        print(f'INFO      | Plot saved successfully in: {args.plotfile}')


if __name__ == '__main__':
    mp.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser(description='MACE Committee Uncertainty Evaluation Multi-GPU/Multi-Node')
    parser.add_argument('--config', help='Path to YAML config file')
    parser.add_argument('-m', '--model', type=str, nargs='+', help='Model paths')
    parser.add_argument('-t', '--type', type=str, default='MACE')
    parser.add_argument('-f', '--file', type=str, default='traj.xyz')
    parser.add_argument('-o', '--outfile', type=str, default='traj-std.xyz')
    parser.add_argument('--out_thresh', type=str, default='traj-above-thresh.xyz')
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--threshold', type=float, default=0.06)
    parser.add_argument('--threshold_max', type=float, default=float('inf'))
    parser.add_argument('--plotfile', type=str, default='uncertainty_hist.png')
    parser.add_argument('--out_data', type=str, default=None)
    parser.add_argument('--out_raw', type=str, default=None)
    parser.add_argument('--num_gpus', type=int, default=None)
    parser.add_argument('--merge_only', action='store_true', help='Perform only the merge step')

    args = parser.parse_args()

    if args.config:
        with open(args.config, 'r') as f:
            cfg = yaml.safe_load(f)
        m_cfg = cfg['step_02_mace']
        args.model = m_cfg['models']
        args.type = m_cfg.get('model_type', 'MACE')
        args.file = m_cfg['input_file']
        args.outfile = m_cfg['output_file']
        args.out_thresh = m_cfg['out_thresh']
        args.stride = m_cfg.get('stride', 1)
        args.threshold = float(m_cfg.get('threshold', 0.06))
        args.threshold_max = float(m_cfg.get('threshold_max', float('inf')))
        args.plotfile = m_cfg.get('plotfile', 'uncertainty_histogram.png')
        args.out_data = m_cfg.get('out_data', None)
        args.out_raw = m_cfg.get('out_raw', None)
        if 'num_gpus' in m_cfg and m_cfg['num_gpus'] is not None:
            args.num_gpus = m_cfg['num_gpus']

    slurm_tasks = int(os.environ.get("SLURM_NTASKS", "1"))
    slurm_rank = int(os.environ.get("SLURM_PROCID", "0"))

    # Esecuzione solo Merge
    if args.merge_only:
        num_chunks = slurm_tasks if slurm_tasks > 1 else (args.num_gpus or (torch.cuda.device_count() if torch.cuda.is_available() else 1))
        merge_and_plot(num_chunks, args)
        sys.exit(0)

    # 1. Lettura lunghezza traiettoria
    if slurm_rank == 0:
        print(f"INFO      | Reading total length of {args.file}...")

    full_traj_len = len(read(args.file, index=f'::{args.stride}'))

    # MODALITÀ 1: Multi-Task Slurm (srun con SLURM_NTASKS > 1)
    if slurm_tasks > 1:
        chunk_size = int(np.ceil(full_traj_len / slurm_tasks))
        start_idx = slurm_rank * chunk_size
        end_idx = min((slurm_rank + 1) * chunk_size, full_traj_len)

        if slurm_rank == 0:
            print(f'INFO      | Running in Slurm Distributed Mode across {slurm_tasks} tasks.')
            print(f'INFO      | Total frames to process: {full_traj_len}')
            print(f'INFO      | Frames per task: ~{chunk_size}')

        print(f'[Rank {slurm_rank}] Assigned frames: {start_idx} to {end_idx} (Total: {max(0, end_idx - start_idx)})')

        if start_idx < full_traj_len:
            local_rank = int(os.environ.get("SLURM_LOCALID", "0"))
            if torch.cuda.is_available():
                device_str = f"cuda:{local_rank}" if local_rank < torch.cuda.device_count() else "cuda:0"
            else:
                device_str = "cpu"
            process_chunk(device_str, start_idx, end_idx, args, tag=slurm_rank)

    # MODALITÀ 2: Singolo Task Slurm (SLURM_NTASKS == 1) -> Usa Multiprocessing Locale se N_GPU > 1
    else:
        n_gpus = args.num_gpus if args.num_gpus else (torch.cuda.device_count() if torch.cuda.is_available() else 1)

        if n_gpus > 1:
            chunk_size = int(np.ceil(full_traj_len / n_gpus))
            print(f'INFO      | Running in Local Multi-GPU Mode on 1 node with {n_gpus} GPUs.')
            print(f'INFO      | Total frames to process: {full_traj_len}')
            print(f'INFO      | Frames per GPU: ~{chunk_size}')

            with mp.Pool(processes=n_gpus) as pool:
                results = []
                for i in range(n_gpus):
                    s_idx = i * chunk_size
                    e_idx = min((i + 1) * chunk_size, full_traj_len)
                    if s_idx >= full_traj_len:
                        break
                    print(f'[GPU {i}] Assigned frames: {s_idx} to {e_idx} (Total: {max(0, e_idx - s_idx)})')
                    res = pool.apply_async(process_chunk, (f'cuda:{i}', s_idx, e_idx, args, i))
                    results.append(res)

                for res in results:
                    res.get()

            merge_and_plot(n_gpus, args)

        else:
            print(f'INFO      | Running on 1 single GPU / CPU Process.')
            print(f'INFO      | Total frames to process: {full_traj_len}')
            device_str = "cuda:0" if torch.cuda.is_available() else "cpu"
            process_chunk(device_str, 0, full_traj_len, args, tag=0)
            merge_and_plot(1, args)