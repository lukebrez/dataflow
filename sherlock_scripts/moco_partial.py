import sys
import os
import json
import nibabel as nib
import numpy as np
import bigbadbrain as bbb
import dataflow as flow
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, '/home/users/brezovec/.local/lib/python3.6/site-packages/lib/python/')
import ants

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # directory will be a full path to either an anat folder or a func folder
    dirtype = args['dirtype']
    start = int(args['start'])
    stop = int(args['stop'])
    printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

    moco_dir = os.path.join(directory, 'moco')
    if dirtype == 'func':
        master_path = os.path.join(directory, 'imaging', 'functional_channel_1.nii')
        slave_path = os.path.join(directory, 'imaging', 'functional_channel_2.nii')
        master_path_mean = os.path.join(directory, 'imaging', 'functional_channel_1_mean.nii')
    elif dirtype == 'anat':
        master_path = os.path.join(directory, 'imaging', 'anatomy_channel_1.nii')
        slave_path = os.path.join(directory, 'imaging', 'anatomy_channel_2.nii')
        master_path_mean = os.path.join(directory, 'imaging', 'anatomy_channel_1_mean.nii')

    # For the sake of memory, load only the part of the brain we will need.
    # Load master (required)
    master_brain = load_partial_brain(master_path,start,stop)
    # Load slave (optional)
    if os.path.exists(slave_path):
        slave_brain = load_partial_brain(slave_path,start,stop)
    else:
        slave_brain = None
        printlog('Slave brain not found, continuing without: {}'.format(slave_path))
    # Load mean (required)
    mean_brain = ants.from_numpy(np.asarray(nib.load(master_path_mean).get_data(), dtype='float32'))

    flow.motion_correction(master_brain,
                           slave_brain,
                           moco_dir,
                           printlog,
                           mean_brain,
                           suffix='_'+str(start))

def load_partial_brain(file, start, stop):
    brain = nib.load(file).dataobj[:,:,:,start:stop]
    # for ants, supported_ntypes = {'uint8', 'uint32', 'float32', 'float64'}
    brain = ants.from_numpy(np.asarray(np.squeeze(brain), dtype='float32')) #updated dtype 20200626 from float64 to float32
    # always keep 4 axes:
    if len(np.shape(brain)) == 3:
      brain = brain[:,:,:,np.newaxis]
    return brain

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))