import time
import sys
import os
import re
import json
import datetime
import pyfiglet
import textwrap
import dataflow as flow

modules = 'gcc/6.3.0 python/3.6.1 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36'

#########################
### Setup preferences ###
#########################

width = 120 # width of print log
nodes = 2 # 1 or 2
nice = True # true to lower priority of jobs. ie, other users jobs go first

flies = ['fly_095']
seed_fly = 'fly_091'
save_directory = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20200802_meanbrain"
#flies = ['fly_' + str(x).zfill(3) for x in list(range(84,112))]

#####################
### Setup logging ###
#####################

logfile = './logs/' + time.strftime("%Y%m%d-%H%M%S") + '.txt'
printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')
sys.stderr = flow.Logger_stderr_sherlock(logfile)

###################
### Setup paths ###
###################

imports_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/imports/build_queue"
scripts_path = "/home/users/brezovec/projects/dataflow/sherlock_scripts"
com_path = "/home/users/brezovec/projects/dataflow/sherlock_scripts/com"
dataset_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset"

###################
### Print Title ###
###################

title = pyfiglet.figlet_format("Loop", font="cyberlarge" ) #28 #shimrod
title_shifted = ('\n').join([' '*44+line for line in title.split('\n')][:-2])
printlog(title_shifted)
day_now = datetime.datetime.now().strftime("%B %d, %Y")
time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
printlog(F"{day_now+' | '+time_now:^{width}}")
printlog("")

###################
### LOOP SCRIPT ###
###################

printlog(f"\n{'   LOOP   ':=^{width}}")
job_ids = []
fixed_path = os.path.join(dataset_path, seed_fly, 'anat_0', 'moco', 'stitched_brain_red_mean.nii')
fixed_fly = seed_fly
type_of_transform = 'Affine'
for fly in flies:
    moving_path = os.path.join(dataset_path, fly, 'anat_0', 'moco', 'stitched_brain_red_mean.nii')
    moving_fly = fly

    args = {'logfile': logfile,
            'save_directory': save_directory,
            'fixed_path': fixed_path,
            'moving_path': moving_path,
            'fixed_fly': fixed_fly,
            'moving_fly': moving_fly,
            'type_of_transform': type_of_transform}

    script = 'align_anat.py'
    job_id = flow.sbatch(jobname='align',
                         script=os.path.join(scripts_path, script),
                         modules=modules,
                         args=args,
                         logfile=logfile, time=1, mem=4, nice=nice, nodes=nodes) # 2 to 1
    job_ids.append(job_id)

for job_id in job_ids:
    flow.wait_for_job(job_id, logfile, com_path)

############
### Done ###
############

time.sleep(30) # to allow any final printing
day_now = datetime.datetime.now().strftime("%B %d, %Y")
time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
printlog("="*width)
printlog(F"{day_now+' | '+time_now:^{width}}")