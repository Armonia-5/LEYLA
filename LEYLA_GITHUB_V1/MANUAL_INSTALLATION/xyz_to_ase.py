import os
import shutil
import re
import subprocess
import sys
import argparse
import yaml

# ==========================================
# ARGUMENT PARSING AND YAML LOADING
# ==========================================
parser = argparse.ArgumentParser(description="Step 05 - Data Conversion & Post-Processing")
parser.add_argument("--config", type=str, default="leyla_config.yaml", help="Path to the YAML configuration file")
args = parser.parse_args()

CONFIG_FILE = args.config

if not os.path.exists(CONFIG_FILE):
    print(f"Error: Configuration file '{CONFIG_FILE}' not found!")
    sys.exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)["step_05_convert"]

FINAL_OUTPUT_NAME = config["final_output_name"]
PYTHON_SCRIPT = config["conversion_script"]
FILES_TO_KEEP = set(config["files_to_keep"])

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def natural_sort_key(s):
    """Numerically sorts strings (e.g., run_2 before run_10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def rename_extxyz_properties(filepath):
    """
    Reads the extxyz file and replaces 'forces' -> 'REF_forces' and 'energy' -> 'REF_energy'.
    """
    temp_filepath = filepath + ".tmp"
    with open(filepath, 'r', encoding='utf-8') as infile, open(temp_filepath, 'w', encoding='utf-8') as outfile:
        for line in infile:
            new_line = re.sub(r'\bforces\b', 'REF_forces', line)
            new_line = re.sub(r'\benergy\b', 'REF_energy', new_line)
            outfile.write(new_line)

    os.replace(temp_filepath, filepath)

def main():
    if not os.path.exists(PYTHON_SCRIPT):
        print(f"Error: The script {PYTHON_SCRIPT} was not found in the main directory!")
        sys.exit(1)

    # Detects run_* subdirectories and sorts them numerically
    run_dirs = sorted(
        [d for d in os.listdir('.') if os.path.isdir(d) and d.startswith('run_')],
        key=natural_sort_key
    )

    all_dirs = ['.'] + run_dirs
    print(f"Detected directories in the correct order: {all_dirs}")
    print("---------------------------------------------------")

    valid_converted_count = 0

    for dir_path in all_dirs:
        print(f">>> Processing directory: {dir_path}")

        # --- CHECK FOR CP2K OUTPUT FILES ---
        # Check that the simulation produced at least the base files for conversion
        ener_file = os.path.join(dir_path, "cha_MD-1.ener")
        pos_file = os.path.join(dir_path, "cha_MD-pos-1.xyz")

        if not (os.path.exists(ener_file) and os.path.exists(pos_file)):
            print(f"    [WARNING] Simulation failed at 1st step or incomplete in '{dir_path}'. Output files missing -> Directory skipped.")
            continue

        # If the directory is valid, copy conversion.py if we are in a subdirectory
        if dir_path != '.':
            shutil.copy(PYTHON_SCRIPT, dir_path)

        # --- INITIAL CLEANUP PHASE ---
        print("    Cleaning up unnecessary files...")
        script_filename = os.path.basename(__file__)

        for item in os.listdir(dir_path):
            full_path = os.path.join(dir_path, item)
            if os.path.isfile(full_path):
                if item not in FILES_TO_KEEP and item != PYTHON_SCRIPT and item != script_filename and item != CONFIG_FILE:
                    try:
                        os.remove(full_path)
                    except Exception as e:
                        print(f"    Warning: Unable to remove {item}: {e}")

        # --- EXECUTION PHASE ---
        print("    Executing conversion script...")
        abs_script_path = os.path.abspath(os.path.join(dir_path, PYTHON_SCRIPT))

        result = subprocess.run([sys.executable, abs_script_path], cwd=dir_path)
        if result.returncode != 0:
            print(f"    Error during conversion in {dir_path}. Directory skipped.")
            continue

        # --- RENAME PROPERTIES IN all_data.extxyz ---
        extxyz_path = os.path.join(dir_path, "all_data.extxyz")
        if os.path.exists(extxyz_path):
            print("    Updating keys to REF_forces and REF_energy...")
            rename_extxyz_properties(extxyz_path)
            valid_converted_count += 1
        else:
            print(f"    Warning: {extxyz_path} not found in {dir_path}")

        print("    Done.")

    print("---------------------------------------------------")

    # --- GLOBAL CHECK FOR VALIDATED CONVERSIONS ---
    if valid_converted_count == 0:
        print("CRITICAL ERROR: No CP2K simulation converged in any directory!")
        print("Unable to generate output file for Active Learning.")
        sys.exit(1)

    print(f"Total directories successfully converted: {valid_converted_count}/{len(all_dirs)}")

    # --- MERGING PHASE ---
    print(f"Merging all_data.extxyz files into {FINAL_OUTPUT_NAME}...")
    if os.path.exists(FINAL_OUTPUT_NAME):
        os.remove(FINAL_OUTPUT_NAME)

    with open(FINAL_OUTPUT_NAME, 'wb') as outfile:
        for dir_path in all_dirs:
            extxyz_path = os.path.join(dir_path, 'all_data.extxyz')
            if os.path.exists(extxyz_path):
                with open(extxyz_path, 'rb') as infile:
                    shutil.copyfileobj(infile, outfile)

    print(f"Merging completed. The final merged file is: {FINAL_OUTPUT_NAME}")

    # --- FINAL CLEANUP PHASE (REMOVING 'CP' DIRECTORIES) ---
    print("---------------------------------------------------")
    print("Deleting remaining 'CP' directories...")
    for dir_path in all_dirs:
        cp_path = os.path.join(dir_path, "CP")
        if os.path.exists(cp_path) and os.path.isdir(cp_path):
            try:
                shutil.rmtree(cp_path)
                print(f"    Removed CP directory from: {dir_path}")
            except Exception as e:
                print(f"    Error removing {cp_path}: {e}")

    print("---------------------------------------------------")
    print("Process completed successfully!")

if __name__ == '__main__':
    main()