#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

path/LEYLA/bin/python soap_filter.py --config leyla_config.yaml

