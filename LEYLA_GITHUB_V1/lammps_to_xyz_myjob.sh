#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

python -m lammps_to_xyz --config leyla_config.yaml

