#!/bin/bash
#SBATCH INFOS (USE GPUs)

module load cuda/12.6
module load cmake/3.27.9
module load gcc/12.2.0
module load openmpi/4.1.6--gcc--12.2.0-cuda-12.2
module load intel-oneapi-mkl/2024.0.0

source path/LEYLA/bin/activate

srun path/LEYLA/bin/python mace_calculator.py --config leyla_config.yaml

path/LEYLA/bin/python mace_calculator.py --config leyla_config.yaml --merge_only
