#!/bin/bash
#SBATCH INFOS (USE CPUs)

source path/LEYLA/bin/activate

#Other ranges such as 2–6, 1–5, 2–4, and 3–3 are possible
path/LEYLA/bin/python leyla_master.py --start 1 --end 6