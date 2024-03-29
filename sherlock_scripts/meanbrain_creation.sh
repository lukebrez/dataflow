#!/bin/bash
#SBATCH --job-name=bldmnbrn
#SBATCH --partition=trc
#SBATCH --time=7-00:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=22
#SBATCH --open-mode=append

ml python/3.6.1
date
python3 -u /home/users/brezovec/projects/dataflow/sherlock_scripts/20230124_DSX_meanbrain_creation.py
##SBATCH --output=./logs/mainlog.out