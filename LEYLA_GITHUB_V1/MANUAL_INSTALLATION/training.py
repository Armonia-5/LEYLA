import os
import subprocess
import sys
import yaml

CONFIG_FILE = "leyla_config.yaml"

if not os.path.exists(CONFIG_FILE):
    print(f"Error: {CONFIG_FILE} not found!")
    sys.exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)["step_06_finetune"]

template_path = cfg.get("template_file", "training.template")
if not os.path.exists(template_path):
    print(f"Error: Template file '{template_path}' not found!")
    sys.exit(1)

with open(template_path, "r", encoding="utf-8") as f:
    template_content = f.read()

python_bin = cfg["python_bin"]
env_path = cfg["env_path"]
mace_script = cfg["mace_script"]
common = cfg["common_args"]

required_files = [common["train_file"], common["pt_train_file"], common["foundation_model"]]

for run in cfg["runs"]:
    run_dir = f"run_seed_{run['seed']}"
    os.makedirs(run_dir, exist_ok=True)
    
    # Creation of symbolic links for input files
    for fname in required_files:
        src = os.path.abspath(fname)
        dst = os.path.join(run_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            os.symlink(src, dst)

    # Building MACE arguments string
    mace_args_str = f'    --name="{run["name"]}"\n'
    mace_args_str += f'    --seed={run["seed"]}\n'
    for k, v in common.items():
        if k == "max_num_epochs": continue
        if isinstance(v, bool):
            if v: mace_args_str += f'    --{k}\n'
        else:
            mace_args_str += f'    --{k}="{v}"\n'

    # Variable substitution in template
    job_str = template_content.replace("{{JOB_NAME}}", f"ft_seed_{run['seed']}")
    job_str = job_str.replace("{{ENV_PATH}}", env_path)
    job_str = job_str.replace("{{MACE_ARGS}}", mace_args_str.rstrip())
    job_str = job_str.replace("{{SEED}}", str(run["seed"]))
    job_str = job_str.replace("{{PYTHON_BIN}}", python_bin)
    job_str = job_str.replace("{{MACE_SCRIPT}}", mace_script)
    job_str = job_str.replace("{{MAX_NUM_EPOCHS}}", str(common.get("max_num_epochs", 1100)))

    # Writing job file to subfolder
    job_filename = os.path.join(run_dir, f"training_{run['id']}_myjob.sh")
    with open(job_filename, "w", encoding="utf-8") as f:
        f.write(job_str)

    # SLURM job submission
    print(f"Submitting job for Seed {run['seed']} in {run_dir}...")
    subprocess.run(["sbatch", f"training_{run['id']}_myjob.sh"], cwd=run_dir)

print("\nAll 4 jobs have been generated and submitted successfully!")