import os
import sys
import numpy as np
import argparse
import subprocess
import json
import time
from scipy.ndimage import gaussian_filter1d
import nibabel as nib
import bigbadbrain as bbb
import dataflow as flow

def main(args):

    logfile = args['logfile']
    directory = args['directory'] # full fly func path
    printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

    for color in ['red', 'green']:
        brain_file = os.path.join(directory, 'moco', 'stitched_brain_{}.nii'.format(color))
        if os.path.exists(brain_file):
            t0 = time.time()
            to_print = '/'.join(brain_file.split('/')[-4:])
            printlog(f'Z-scoring{to_print:.>{120-9}}')

            brain = np.asarray(nib.load(brain_file).get_data(), dtype='uint16')

            printlog("brain load duration: ({})".format(time.time()-t0))
            t0 = time.time()

            smoothed = gaussian_filter1d(brain,sigma=200,axis=-1,truncate=1)

            printlog("brain smoothed duration: ({})".format(time.time()-t0))
            t0 = time.time()

            brain = brain - smoothed

            printlog("brain subtracted duration: ({})".format(time.time()-t0))
            t0 = time.time()

            # Z-score brain
            brain_mean  = np.mean(brain, axis=3)

            printlog("brain mean duration: ({})".format(time.time()-t0))
            t0 = time.time()

            brain_std = np.std(brain, axis=3)

            printlog("brain std duration: ({})".format(time.time()-t0))
            t0 = time.time()

            brain = (brain - brain_mean[:,:,:,None]) / brain_std[:,:,:,None]

            printlog("brain zscored duration: ({})".format(time.time()-t0))
            t0 = time.time()

            # Save brain
            zbrain_file = os.path.join(directory, 'brain_zscored_{}.nii'.format(color))
            printlog('Saving {}'.format(zbrain_file))
            aff = np.eye(4)
            img = nib.Nifti1Image(brain, aff)
            img.to_filename(zbrain_file)

            printlog("brain save duration: ({})".format(time.time()-t0))

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))