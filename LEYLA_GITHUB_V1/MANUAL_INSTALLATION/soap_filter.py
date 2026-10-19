import numpy as np
from ase.io import read, write
from dscribe.descriptors import SOAP
import os
import argparse
import yaml

def set_box_size(structures, box_size):
    """Set the periodic box size for all structures."""
    for structure in structures:
        structure.set_cell(box_size)
        structure.set_pbc(True)

def soap_matrix(soap_obj, configurations, centers_list):
    if not isinstance(configurations, list):
        configurations = [configurations]

    soap_vec = soap_obj.create(configurations, centers_list)
    if soap_vec.ndim == 1:
        return soap_vec.reshape(1, -1)

    return soap_vec

def save_selected_structures(filename, structures):
    """Save selected structures to a file."""
    if os.path.exists(filename):
        write(filename, structures, append=True)
    else:
        write(filename, structures)

def compute_soap_kernel_for_new_structures(cfg_step):
    # Extract parameters from YAML
    training_data_file = cfg_step['training_data_file']
    new_data_file = cfg_step['new_data_file']
    output_file = cfg_step['output_file']
    progress_file = cfg_step['progress_file']
    
    training_index = cfg_step.get('training_index', '0:1')
    new_data_index = cfg_step.get('new_data_index', '::2')
    
    zeta = cfg_step['zeta']
    threshold = cfg_step['threshold']
    
    box_size = cfg_step['box_size']
    centers = cfg_step['centers']

    # Initialize SOAP descriptor from YAML
    soap = SOAP(
        species=cfg_step['species'],
        periodic=True,
        r_cut=cfg_step['r_cut'],
        n_max=cfg_step['n_max'],
        l_max=cfg_step['l_max'],
        average=cfg_step['average'],
        sparse=cfg_step['sparse']
    )

    # Load structures
    training_structures = read(training_data_file, format='extxyz', index=training_index)
    new_structures = read(new_data_file, format='extxyz', index=new_data_index)

    # Set box size
    set_box_size(training_structures, box_size)
    set_box_size(new_structures, box_size)

    # Progress management (resume)
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            last_processed = int(f.read().strip())
        print(f"Resuming from structure {last_processed + 1}")
    else:
        last_processed = -1

    # Initial SOAP cache for training set
    train_soap = soap_matrix(soap, training_structures, [centers] * len(training_structures))
    train_norms = np.linalg.norm(train_soap, axis=1).reshape(-1, 1)
    train_soap_norm = train_soap / train_norms

    # Loop over new structures
    for idx, structure in enumerate(new_structures):
        if idx <= last_processed:
            continue

        v_new = soap_matrix(soap, [structure], [centers])[0]
        v_new_norm = v_new / np.linalg.norm(v_new)

        kernel_vector = np.power(np.dot(train_soap_norm, v_new_norm), zeta)
        max_kernel_value = np.max(kernel_vector)

        print(f"Kernel values for new structure {idx + 1}:")
        for j, value in enumerate(kernel_vector):
            print(f"  Kernel with training structure {j + 1}: {value:.4f}")

        if max_kernel_value < threshold:
            print(f"Structure {idx + 1} selected (max kernel value: {max_kernel_value:.4f})\n")
            save_selected_structures(output_file, [structure])
            
            training_structures.append(structure)
            train_soap_norm = np.vstack([train_soap_norm, v_new_norm])
        else:
            print(f"Structure {idx + 1} not selected (max kernel value: {max_kernel_value:.4f})\n")

        with open(progress_file, 'w') as f:
            f.write(str(idx))

    print("All structures processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SOAP Filter for LEYLA")
    parser.add_argument("--config", type=str, default="leyla_config.yaml", help="Path to config YAML file")
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)

    compute_soap_kernel_for_new_structures(cfg['step_03_soap'])