#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

python -m xyz_to_ase --config leyla_config.yaml
