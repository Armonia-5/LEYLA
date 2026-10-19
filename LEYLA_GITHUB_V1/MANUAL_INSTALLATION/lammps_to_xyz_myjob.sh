#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

path/LEYLA/bin/python lammps_to_xyz.py --config leyla_config.yaml

