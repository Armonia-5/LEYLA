#!/bin/bash
#SBATCH INFOS (USE GPUs)

#LOAD YOUR MODULES
module load cuda/12.6
module load cmake/3.27.9
module load gcc/12.2.0
module load openmpi/4.1.6--gcc--12.2.0-cuda-12.2
module load intel-oneapi-mkl/2024.0.0

source path/LEYLA/bin/activate

# 1. Calculation phase distributed on multi-GPU
srun python -m mace_calculator --config leyla_config.yaml

# 2. Merge phase
python -m mace_calculator --config leyla_config.yaml --merge_only
