#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

python -m soap_filter --config leyla_config.yaml

