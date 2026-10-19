import os
import yaml
import dpdata
from ase.io import write

# Dynamic resolution of the leyla_config.yaml path
config_path = "leyla_config.yaml"
if not os.path.exists(config_path) and os.path.exists("../leyla_config.yaml"):
    config_path = "../leyla_config.yaml"

cp2kmd_output_name = "output"
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f).get("step_05_convert", {})
        cp2kmd_output_name = cfg.get("cp2k_output_name", "output")

cp2kmd_dir = "."

# Parsing CP2K output with dpdata
data = dpdata.LabeledSystem(cp2kmd_dir, cp2k_output_name=cp2kmd_output_name, fmt="cp2k/aimd_output")
data.to_deepmd_npy('CP')

# Conversion from DeepMD npy to ASE structure and export to extxyz
data_cp = dpdata.LabeledSystem('CP', fmt='deepmd/npy')
listall = data_cp.to_ase_structure()
write('all_data.extxyz', listall, format='extxyz')