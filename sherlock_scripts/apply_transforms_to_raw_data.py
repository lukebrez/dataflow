import numpy as np
import os
import sys
import psutil
import nibabel as nib
from time import time
import json
import dataflow as flow
import matplotlib.pyplot as plt
from contextlib import contextmanager
import warnings
warnings.filterwarnings("ignore")

from shutil import copyfile

import platform
if platform.system() != 'Windows':
    sys.path.insert(0, '/home/users/brezovec/.local/lib/python3.6/site-packages/lib/python/')
    import ants

def main(args):

    logfile = args['logfile']
    save_directory = args['save_directory']
    warp_directory = args['warp_directory']

    fixed_path = args['fixed_path']
    fixed_fly = args['fixed_fly']
    fixed_resolution = args['fixed_resolution']

    moving_path = args['moving_path']
    moving_fly = args['moving_fly']
    moving_resolution = args['moving_resolution']

    ###################
    ### Load Brains ###
    ###################
    fixed = np.asarray(nib.load(fixed_path).get_data().squeeze(), dtype='float32')
    fixed = ants.from_numpy(fixed)
    fixed.set_spacing(fixed_resolution)
    fixed = ants.resample_image(fixed,(256,128,49),1,0)

    moving = np.asarray(nib.load(moving_path).get_data().squeeze(), dtype='float32')
    moving = ants.from_numpy(moving)
    moving.set_spacing(moving_resolution)

    ###########################
    ### Organize Transforms ###
    ###########################
    affine_file = os.listdir(os.path.join(warp_directory, 'func-to-anat_fwdtransforms_lowres'))[0]
    affine_path = os.path.join(warp_directory, 'func-to-anat_fwdtransforms_lowres', affine_file)

    syn_files = os.listdir(os.path.join(warp_directory, 'anat-to-meanbrain_fwdtransforms_lowres'))
    syn_linear_path = os.path.join(warp_directory, 'anat-to-meanbrain_fwdtransforms_lowres', [x for x in syn_files if '.mat' in x][0])
    syn_nonlinear_path = os.path.join(warp_directory, 'anat-to-meanbrain_fwdtransforms_lowres', [x for x in syn_files if '.nii.gz' in x][0])

    transforms = [affine_path, syn_linear_path, syn_nonlinear_path]

    ########################
    ### Apply Transforms ###
    ########################
    moco = ants.apply_transforms(fixed, moving, transforms, imagetype=3)

    ############
    ### Save ###
    ############
    save_file = os.path.join(save_directory, 'functional_channel_2_moco_zscore_highpass_warped.nii')#<---------------------------------------
    nib.Nifti1Image(moco.numpy(), np.eye(4)).to_filename(save_file)

def sec_to_hms(t):
        secs=F"{np.floor(t%60):02.0f}"
        mins=F"{np.floor((t/60)%60):02.0f}"
        hrs=F"{np.floor((t/3600)%60):02.0f}"
        return ':'.join([hrs, mins, secs])

@contextmanager
def stderr_redirected(to=os.devnull):

    fd = sys.stderr.fileno()

    def _redirect_stderr(to):
        sys.stderr.close() # + implicit flush()
        os.dup2(to.fileno(), fd) # fd writes to 'to' file
        sys.stderr = os.fdopen(fd, 'w') # Python writes to fd

    with os.fdopen(os.dup(fd), 'w') as old_stderr:
        with open(to, 'w') as file:
            _redirect_stderr(to=file)
        try:
            yield # allow code to be run with the redirected stdout
        finally:
            _redirect_stderr(to=old_stderr) # restore stdout.
                                            # buffering and flags such as
                                            # CLOEXEC may be different

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))