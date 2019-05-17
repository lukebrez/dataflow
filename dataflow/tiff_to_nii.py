import numpy as np
import nibabel as nib
import os
from matplotlib.pyplot import imread
from xml.etree import ElementTree as ET
import sys
from tqdm import tqdm
from dataflow.utils import timing
import psutil
from PIL import Image

def tiff_to_nii(xml_file):
    data_dir, _ = os.path.split(xml_file)

    tree = ET.parse(xml_file)
    root = tree.getroot()
    # Get all volumes
    sequences = root.findall('Sequence')

    # Get num channels
    num_channels = get_num_channels(sequences[0])

    # De each channel separately (for memory reasons)
    # I think this should also work for 1 channel recordings but should confirm
    print('Converting tiffs to nii in directory: \n{}'.format(data_dir))
    for channel in range(num_channels):
        last_num_z = None
        volumes_img = []
        for i, sequence in enumerate(sequences):
            print('{}/{}'.format(i+1, len(sequences)))
            # For a given volume, get all frames
            frames = sequence.findall('Frame')
            frames_img = []
            for frame in frames:
                # For a given frame, get all channels
                files = frame.findall('File')
                filename = files[channel].get('filename')
                fullfile = os.path.join(data_dir, filename)

                # Read in file
                compress = False
                if compress:
                    starting_bit_depth = 2**13
                    desired_bit_depth = 2**8
                    im = Image.open(fullfile)
                    img = np.asarray(im)
                    img = img*(desired_bit_depth/starting_bit_depth)
                    img = img.astype('uint8')
                else:
                    img = imread(fullfile)
                frames_img.append(img)
                 
            current_num_z = np.shape(frames_img)[0]
        
            if last_num_z is not None:
                if current_num_z != last_num_z:
                    print('Inconsistent number of z-slices (scan aborted).')
                    print('Tossing last volume.')
                    break
            volumes_img.append(frames_img)
            last_num_z = current_num_z

        memory_usage = psutil.Process(os.getpid()).memory_info().rss*10**-9
        print('Current memory usage: {:.2f}GB'.format(memory_usage))
        sys.stdout.flush()

        volumes_img = np.asarray(volumes_img)
        # Will start as t,z,x,y. Want y,x,z,t
        volumes_img = np.moveaxis(volumes_img,1,-1) # Now t,x,y,z
        volumes_img = np.moveaxis(volumes_img,0,-1) # Now x,y,z,t
        volumes_img = np.swapaxes(volumes_img,0,1) # Now y,x,z,t

        aff = np.eye(4)
        save_name = xml_file[:-4] + '_channel_{}'.format(channel+1) + '.nii'
        img = nib.Nifti1Image(volumes_img, aff)
        volumes_img = None # for memory
        print('Saving nii as {}'.format(save_name))
        img.to_filename(save_name)

def get_num_channels(sequence):
    frame = sequence.findall('Frame')[0]
    files = frame.findall('File')
    return len(files)

@timing
def start_convert_tiff_collections(*args):
    convert_tiff_collections(*args)

def convert_tiff_collections(directory): 
    for item in os.listdir(directory):
        new_path = directory + '/' + item

        # Check if item is a directory
        if os.path.isdir(new_path):
            convert_tiff_collections(new_path)
            
        # If the item is a file
        else:
            # If the item is an xml file
            if '.xml' in item:
                tree = ET.parse(new_path)
                root = tree.getroot()
                # If the item is an xml file with scan info
                if root.tag == 'PVScan':
                    tiff_to_nii(new_path)