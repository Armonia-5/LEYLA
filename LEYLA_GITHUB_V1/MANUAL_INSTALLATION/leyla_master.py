#!/usr/bin/env python3
import os
import sys
import re
import time
import shutil
import argparse
import subprocess
import yaml
from datetime import datetime

# ==============================================================================
# BANNER & UTILITY FUNCTIONS
# ==============================================================================

def print_banner():
    banner = r"""
                                  ██╗      ███████╗██╗    ██╗██╗       █████╗ 
                                  ██║      ██╔════╝╚██╗ ██╔╝██║      ██╔══██╗
                                  ██║      █████╗   ╚████╔╝ ██║       ███████║
                                  ██║      ██╔══╝    ╚██╔╝  ██║       ██╔═ ═██╗
                                  ███████╗███████╗  ██║   ███████╗ ██║    ██║
                                  ╚══════╝╚══════╝  ╚═╝   ╚══════╝╚═╝     ╚═╝
                  ***********************************************************************************
                  *                                     LEYLA:                                      *
                  * Learning Engine data-Labelling, energy-Yielding, and active-Learning Automation *
                  *                                                                                 *
                  *                                Alessandro Morittu                               *
                  *                                     GitHub                                      *
                  *                    https://github.com/Armonia-5/LEYLA.git                       *
                  ***********************************************************************************
"""
    print(banner)

def log(msg, level="INFO"):
    """Prints a formatted message with a timestamp."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}", flush=True)

def copy_file(src, dst):
    """Copies a file, handling errors and potential symlinks."""
    if not os.path.exists(src):
        log(f"Source file not found: {src}", "ERROR")
        sys.exit(1)
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)

def submit_slurm_job(job_file, work_dir):
    """Submits a SLURM job and extracts the Job ID."""
    log(f"Submitting job '{job_file}' in folder {work_dir}...")
    try:
        res = subprocess.run(
            ["sbatch", job_file],
            cwd=work_dir,
            capture_output=True,
            text=True,
            check=True
        )
        match = re.search(r"Submitted batch job (\d+)", res.stdout)
        if not match:
            log(f"Unable to extract Job ID from output: {res.stdout}", "ERROR")
            sys.exit(1)
        job_id = match.group(1)
        log(f"Job submitted with ID: {job_id}")
        return job_id
    except subprocess.CalledProcessError as e:
        log(f"Error submitting SLURM job:\n{e.stderr}", "ERROR")
        sys.exit(1)

def get_slurm_job_status(job_id):
    """Checks the current status of the SLURM job via sacct."""
    try:
        res = subprocess.run(
            ["sacct", "-j", str(job_id), "--format=State", "-n"],
            capture_output=True,
            text=True
        )
        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        if not lines:
            return "RUNNING"  # If sacct does not respond yet, assume it is queued/running
        
        # Takes the first status returned by sacct for the main job
        main_state = lines[0].split()[0]
        return main_state
    except Exception as e:
        log(f"Error checking status for Job {job_id}: {e}", "WARNING")
        return "RUNNING"

def wait_for_slurm_jobs(job_dict, poll_interval=30):
    """
    Monitors a list/dictionary of SLURM jobs until completion.
    job_dict = { job_id: "Run / Step Description" }
    """
    pending_jobs = dict(job_dict)
    log(f"Starting monitoring of {len(pending_jobs)} SLURM jobs...")
    
    while pending_jobs:
        time.sleep(poll_interval)
        completed_this_cycle = []
        
        for job_id, info in pending_jobs.items():
            status = get_slurm_job_status(job_id)
            
            if status == "COMPLETED":
                log(f"Job {job_id} ({info}) COMPLETED successfully!")
                completed_this_cycle.append(job_id)
            elif status in ["FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY"]:
                log(f"CRASH DETECTED: Job {job_id} ({info}) terminated with status '{status}'. Interrupting pipeline!", "ERROR")
                sys.exit(1)
            else:
                # Status still in progress (RUNNING, PENDING, COMPLETING, etc.)
                pass
                
        for job_id in completed_this_cycle:
            del pending_jobs[job_id]
            
    log("All monitored jobs completed successfully!")

def count_xyz_frames(xyz_file):
    """Counts the exact number of structures/frames in an XYZ file."""
    frames = 0
    with open(xyz_file, 'r', encoding='utf-8') as f:
        while True:
            line = f.readline()
            if not line:
                break
            line_str = line.strip()
            if line_str.isdigit():
                num_atoms = int(line_str)
                # Skip comment line + atom lines
                for _ in range(num_atoms + 1):
                    f.readline()
                frames += 1
            else:
                continue
    return frames

# ==============================================================================
# STEP EXECUTORS
# ==============================================================================

def run_step_1(cfg, root_dir):
    """STEP 1: LAMMPS TO XYZ"""
    log("=== STARTING STEP 1: LAMMPS TO XYZ ===")
    step_cfg = cfg["step_01_conversion"]
    work_dir = os.path.join(root_dir, "01_LAMMPS_TO_XYZ")
    os.makedirs(work_dir, exist_ok=True)

    # Copy necessary files
    copy_file(os.path.join(root_dir, step_cfg["input_file"]), os.path.join(work_dir, step_cfg["input_file"]))
    copy_file(os.path.join(root_dir, "lammps_to_xyz.py"), os.path.join(work_dir, "lammps_to_xyz.py"))
    copy_file(os.path.join(root_dir, "lammps_to_xyz_myjob.sh"), os.path.join(work_dir, "lammps_to_xyz_myjob.sh"))
    copy_file(os.path.join(root_dir, "leyla_config.yaml"), os.path.join(work_dir, "leyla_config.yaml"))

    job_id = submit_slurm_job("lammps_to_xyz_myjob.sh", work_dir)
    wait_for_slurm_jobs({job_id: "Step 1 - LAMMPS to XYZ"})

def run_step_2(cfg, root_dir):
    """STEP 2: MACE CALCULATOR"""
    log("=== STARTING STEP 2: MACE CALCULATOR ===")
    step_cfg = cfg["step_02_mace"]
    work_dir = os.path.join(root_dir, "02_MACE_CALCULATOR")
    os.makedirs(work_dir, exist_ok=True)

    prev_dir = os.path.join(root_dir, "01_LAMMPS_TO_XYZ")
    copy_file(os.path.join(prev_dir, step_cfg["input_file"]), os.path.join(work_dir, step_cfg["input_file"]))

    # Copy models and scripts from root
    for model_file in step_cfg["models"]:
        copy_file(os.path.join(root_dir, model_file), os.path.join(work_dir, model_file))

    copy_file(os.path.join(root_dir, "mace_calculator.py"), os.path.join(work_dir, "mace_calculator.py"))
    copy_file(os.path.join(root_dir, "mace_calculator_myjob.sh"), os.path.join(work_dir, "mace_calculator_myjob.sh"))
    copy_file(os.path.join(root_dir, "leyla_config.yaml"), os.path.join(work_dir, "leyla_config.yaml"))

    job_id = submit_slurm_job("mace_calculator_myjob.sh", work_dir)
    wait_for_slurm_jobs({job_id: "Step 2 - MACE Calculator"})

def run_step_3(cfg, root_dir):
    """STEP 3: SOAP FILTERING"""
    log("=== STARTING STEP 3: SOAP FILTERING ===")
    step_cfg = cfg["step_03_soap"]
    work_dir = os.path.join(root_dir, "03_SOAP")
    os.makedirs(work_dir, exist_ok=True)

    prev_dir = os.path.join(root_dir, "02_MACE_CALCULATOR")
    
    train_file = step_cfg["training_data_file"]
    new_file = step_cfg["new_data_file"]

    # Input file management
    if train_file == new_file:
        copy_file(os.path.join(prev_dir, new_file), os.path.join(work_dir, new_file))
    else:
        # If different, training_data_file comes from root folder
        copy_file(os.path.join(root_dir, train_file), os.path.join(work_dir, train_file))
        copy_file(os.path.join(prev_dir, new_file), os.path.join(work_dir, new_file))

    copy_file(os.path.join(root_dir, "soap_filter.py"), os.path.join(work_dir, "soap_filter.py"))
    copy_file(os.path.join(root_dir, "soap_myjob.sh"), os.path.join(work_dir, "soap_myjob.sh"))
    copy_file(os.path.join(root_dir, "leyla_config.yaml"), os.path.join(work_dir, "leyla_config.yaml"))

    job_id = submit_slurm_job("soap_myjob.sh", work_dir)
    wait_for_slurm_jobs({job_id: "Step 3 - SOAP Filtering"})

def run_step_4(cfg, root_dir):
    """STEP 4: CP2K REFTRAJ EVALUATION"""
    log("=== STARTING STEP 4: CP2K REFTRAJ ===")
    step_cfg = cfg["step_04_reftraj"]
    work_dir = os.path.join(root_dir, "04_REFTRAJ")
    os.makedirs(work_dir, exist_ok=True)

    prev_dir = os.path.join(root_dir, "03_SOAP")
    soap_output = cfg["step_03_soap"]["output_file"]
    target_traj = os.path.join(work_dir, step_cfg["traj_file"])
    
    # Copy output trajectory from Step 3
    copy_file(os.path.join(prev_dir, soap_output), target_traj)

    # Count structures generated by SOAP
    num_frames = count_xyz_frames(target_traj)
    log(f"Selected SOAP structures found in XYZ file: {num_frames}")

    if num_frames == 0:
        log("ERROR: No structures found in XYZ file for Step 4!", "ERROR")
        sys.exit(1)

    # Read cp2k.inp from root and replace {{LAST_SNAPSHOT}} or an existing numerical value
    inp_src = os.path.join(root_dir, step_cfg["inp_file"])
    inp_dst = os.path.join(work_dir, step_cfg["inp_file"])
    
    with open(inp_src, "r", encoding="utf-8") as f:
        inp_content = f.read()

    # Replace placeholder or existing LAST_SNAPSHOT line
    if "{{LAST_SNAPSHOT}}" in inp_content:
        inp_content = inp_content.replace("{{LAST_SNAPSHOT}}", str(num_frames))
    else:
        inp_content = re.sub(r"LAST_SNAPSHOT\s+\d+", f"LAST_SNAPSHOT {num_frames}", inp_content)

    with open(inp_dst, "w", encoding="utf-8") as f:
        f.write(inp_content)

    # Copy any other coord.dat / coord.xyz files
    if os.path.exists(os.path.join(root_dir, step_cfg["coord_dat"])):
        copy_file(os.path.join(root_dir, step_cfg["coord_dat"]), os.path.join(work_dir, step_cfg["coord_dat"]))
    if os.path.exists(os.path.join(root_dir, step_cfg["coord_xyz"])):
        copy_file(os.path.join(root_dir, step_cfg["coord_xyz"]), os.path.join(work_dir, step_cfg["coord_xyz"]))

    copy_file(os.path.join(root_dir, "reftraj_myjob.sh"), os.path.join(work_dir, "reftraj_myjob.sh"))
    copy_file(os.path.join(root_dir, "leyla_config.yaml"), os.path.join(work_dir, "leyla_config.yaml"))

    job_id = submit_slurm_job("reftraj_myjob.sh", work_dir)
    wait_for_slurm_jobs({job_id: "Step 4 - CP2K Reftraj"})

def run_step_5(cfg, root_dir):
    """STEP 5: DATA CONVERSION & POST-PROCESSING"""
    log("=== STARTING STEP 5: XYZ TO ASE / CONVERSION ===")
    work_dir = os.path.join(root_dir, "05_XYZ_TO_ASE")
    os.makedirs(work_dir, exist_ok=True)

    prev_dir = os.path.join(root_dir, "04_REFTRAJ")
    
    # Copy all files and folders produced by Step 4
    for item in os.listdir(prev_dir):
        src_item = os.path.join(prev_dir, item)
        dst_item = os.path.join(work_dir, item)
        copy_file(src_item, dst_item)

    step_cfg = cfg["step_05_convert"]
    copy_file(os.path.join(root_dir, "xyz_to_ase.py"), os.path.join(work_dir, "xyz_to_ase.py"))
    copy_file(os.path.join(root_dir, step_cfg["conversion_script"]), os.path.join(work_dir, step_cfg["conversion_script"]))
    copy_file(os.path.join(root_dir, "conversion_myjob.sh"), os.path.join(work_dir, "conversion_myjob.sh"))
    copy_file(os.path.join(root_dir, "leyla_config.yaml"), os.path.join(work_dir, "leyla_config.yaml"))

    job_id = submit_slurm_job("conversion_myjob.sh", work_dir)
    wait_for_slurm_jobs({job_id: "Step 5 - Conversion"})

def run_step_6(cfg, root_dir):
    """STEP 6: MACE FINE-TUNING (4 RUNS IN PARALLEL)"""
    log("=== STARTING STEP 6: MACE FINE-TUNING ===")
    step_cfg = cfg["step_06_finetune"]
    common = step_cfg["common_args"]
    work_dir = os.path.join(root_dir, "06_MACE_TRAINING")
    os.makedirs(work_dir, exist_ok=True)

    step3_cfg = cfg["step_03_soap"]
    step5_cfg = cfg["step_05_convert"]
    
    step5_output = os.path.join(root_dir, "05_XYZ_TO_ASE", step5_cfg["final_output_name"])
    final_train_file = os.path.join(work_dir, common["train_file"])

    # Handle dataset merging for Active Learning if needed
    if step3_cfg["training_data_file"] != step3_cfg["new_data_file"]:
        log("Difference detected between training_data_file and new_data_file. Merging historical dataset with new data...")
        historical_file = os.path.join(root_dir, step3_cfg["training_data_file"])
        with open(final_train_file, "w", encoding="utf-8") as outfile:
            with open(historical_file, "r", encoding="utf-8") as f1:
                outfile.write(f1.read())
            with open(step5_output, "r", encoding="utf-8") as f2:
                outfile.write(f2.read())
    else:
        copy_file(step5_output, final_train_file)

    # Copy other common MACE files
    foundation_src = os.path.join(root_dir, common["foundation_model"])
    pt_train_src = os.path.join(root_dir, common["pt_train_file"])
    copy_file(foundation_src, os.path.join(work_dir, common["foundation_model"]))
    copy_file(pt_train_src, os.path.join(work_dir, common["pt_train_file"]))

    template_path = os.path.join(root_dir, step_cfg.get("template_file", "training.template"))
    if not os.path.exists(template_path):
        log(f"Template file not found: {template_path}", "ERROR")
        sys.exit(1)
        
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    active_jobs = {}

    # Generate subfolders and launch jobs for the 4 seeds
    for run in step_cfg["runs"]:
        run_dir = os.path.join(work_dir, f"run_seed_{run['seed']}")
        os.makedirs(run_dir, exist_ok=True)

        # Symlink/copy dataset files inside each run
        for fname in [common["train_file"], common["pt_train_file"], common["foundation_model"]]:
            src = os.path.abspath(os.path.join(work_dir, fname))
            dst = os.path.join(run_dir, fname)
            if not os.path.exists(dst):
                os.symlink(src, dst)

        # Generate MACE_ARGS
        mace_args_str = f'    --name="{run["name"]}"\n'
        mace_args_str += f'    --seed={run["seed"]}\n'
        for k, v in common.items():
            if k == "max_num_epochs": continue
            if isinstance(v, bool):
                if v: mace_args_str += f'    --{k}\n'
            else:
                mace_args_str += f'    --{k}="{v}"\n'

        # Replace variables in template
        job_str = template_content.replace("{{JOB_NAME}}", f"ft_seed_{run['seed']}")
        job_str = job_str.replace("{{ENV_PATH}}", step_cfg["env_path"])
        job_str = job_str.replace("{{MACE_ARGS}}", mace_args_str.rstrip())
        job_str = job_str.replace("{{SEED}}", str(run["seed"]))
        job_str = job_str.replace("{{PYTHON_BIN}}", step_cfg["python_bin"])
        job_str = job_str.replace("{{MACE_SCRIPT}}", step_cfg["mace_script"])
        job_str = job_str.replace("{{MAX_NUM_EPOCHS}}", str(common.get("max_num_epochs", 1100)))

        job_filename = f"training_{run['id']}_myjob.sh"
        with open(os.path.join(run_dir, job_filename), "w", encoding="utf-8") as f:
            f.write(job_str)

        job_id = submit_slurm_job(job_filename, run_dir)
        active_jobs[job_id] = f"Step 6 - MACE Training Seed {run['seed']}"

    # Simultaneous monitoring of all 4 jobs
    wait_for_slurm_jobs(active_jobs)

def run_step_6_5(cfg, root_dir):
    """STEP 6.5: METRICS EVALUATION & MODEL SELECTION"""
    log("=== STARTING STEP 6.5: METRICS EVALUATION AND MODEL SELECTION ===")
    step_cfg = cfg["step_06_finetune"]
    work_dir = os.path.join(root_dir, "06_MACE_TRAINING")
    model_dir = os.path.join(root_dir, "MODEL")
    os.makedirs(model_dir, exist_ok=True)

    results = []

    for run in step_cfg["runs"]:
        run_dir = os.path.join(work_dir, f"run_seed_{run['seed']}")
        log_file = os.path.join(run_dir, "lammps.out")
        
        if not os.path.exists(log_file):
            log(f"Output file not found: {log_file}", "ERROR")
            sys.exit(1)

        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to capture valid_Default values
        pattern = r"\|\s*valid_Default\s*\|\s*([\d\.]+)\s*\|\s*([\d\.]+)\s*\|"
        matches = re.findall(pattern, content)
        
        if not matches:
            log(f"Unable to find validation table in {log_file}", "ERROR")
            sys.exit(1)

        # Take the last table printed in log (the final one)
        rmse_e = float(matches[-1][0])
        rmse_f = float(matches[-1][1])

        results.append({
            "run_id": run["id"],
            "name": run["name"],
            "seed": run["seed"],
            "dir": run_dir,
            "rmse_e": rmse_e,
            "rmse_f": rmse_f
        })

    # Calculate relative percentages and averages
    max_rmse_e = max(r["rmse_e"] for r in results)
    max_rmse_f = max(r["rmse_f"] for r in results)

    for r in results:
        r["perc_e"] = (r["rmse_e"] / max_rmse_e) * 100
        r["perc_f"] = (r["rmse_f"] / max_rmse_f) * 100
        r["mean_perc"] = (r["perc_e"] + r["perc_f"]) / 2

    # Sort to find the best (lowest average percentage)
    results.sort(key=lambda x: x["mean_perc"])
    winner = results[0]

    log(f"WINNER: Seed {winner['seed']} with Average Percentage = {winner['mean_perc']:.2f}%")

    # Copy winning model to MODEL/ folder
    model_copied = False
    for fname in os.listdir(winner["dir"]):
        if fname.endswith(".model"):
            src_model = os.path.join(winner["dir"], fname)
            dst_model = os.path.join(model_dir, fname)
            copy_file(src_model, dst_model)
            log(f"Winning model saved in: {dst_model}")
            model_copied = True

    if not model_copied:
        log("WARNING: No .model file found in winner folder!", "WARNING")

    # Writing Final Report
    summary_path = os.path.join(model_dir, "model_selection_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("=====================================================\n")
        f.write("       LEYLA STEP 6.5 - MODEL SELECTION SUMMARY       \n")
        f.write("=====================================================\n\n")
        f.write(f"Processing date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"{'RUN ID':<8}{'SEED':<8}{'RMSE E (meV)':<16}{'RMSE F (meV)':<16}{'PERC E (%)':<12}{'PERC F (%)':<12}{'SCORE (%)':<12}\n")
        f.write("-" * 84 + "\n")
        
        for r in sorted(results, key=lambda x: x["run_id"]):
            flag = " <-- BEST" if r["run_id"] == winner["run_id"] else ""
            f.write(f"{r['run_id']:<8}{r['seed']:<8}{r['rmse_e']:<16.2f}{r['rmse_f']:<16.2f}{r['perc_e']:<12.2f}{r['perc_f']:<12.2f}{r['mean_perc']:<12.2f}{flag}\n")

    log(f"Summary report saved in: {summary_path}")

# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="LEYLA Master Orchestrator Script")
    parser.add_argument("--start", type=int, default=1, choices=range(1, 7), help="Initial step (1-6)")
    parser.add_argument("--end", type=int, default=6, choices=range(1, 7), help="Final step (1-6)")
    parser.add_argument("--config", type=str, default="leyla_config.yaml", help="Path to YAML configuration file")
    args = parser.parse_args()

    print_banner()

    root_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(root_dir, args.config)

    if not os.path.exists(config_path):
        log(f"Configuration file '{config_path}' not found!", "ERROR")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    log(f"Starting LEYLA Orchestrator from Step {args.start} to Step {args.end}")

    steps = [
        (1, run_step_1),
        (2, run_step_2),
        (3, run_step_3),
        (4, run_step_4),
        (5, run_step_5),
        (6, run_step_6),
    ]

    for step_num, step_func in steps:
        if args.start <= step_num <= args.end:
            step_func(cfg, root_dir)

    # If the final step includes 6, automatically execute Step 6.5 as well
    if args.end == 6:
        run_step_6_5(cfg, root_dir)

    log("=== LEYLA PIPELINE EXECUTION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()