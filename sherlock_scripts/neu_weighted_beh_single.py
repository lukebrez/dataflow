import os
import sys
import numpy as np
import argparse
import subprocess
import json
import time
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.image import grid_to_graph
import scipy
import nibabel as nib
import bigbadbrain as bbb
import dataflow as flow

def main(args):
	logfile = args['logfile']
	z = args['z']
	printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

	fly_names = ['fly_087', 'fly_089', 'fly_094', 'fly_095', 'fly_097', 'fly_098', 'fly_099', 'fly_100', 'fly_101', 'fly_105']
	dataset_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset"
	expt_len = 1000*30*60
	resolution = 10
	high_res_timepoints = np.arange(0,expt_len,resolution) #0 to last time at subsample res

	class Fly:
		def __init__ (self, fly_name, fly_idx):
			self.dir = os.path.join(dataset_path, fly_name, 'func_0')
			self.fly_idx = fly_idx
			self.fly_name = fly_name
			self.maps = {}
		def load_timestamps (self):
			self.timestamps = bbb.load_timestamps(os.path.join(self.dir, 'imaging'))
		def load_fictrac (self):
			self.fictrac = Fictrac(self.dir, self.timestamps)
		def load_brain_slice (self):
			self.brain = brain[:,:,:,self.fly_idx]
		def load_anatomy (self):
			to_load = os.path.join(dataset_path, self.fly_name, 'warp', 'anat-to-meanbrain.nii')
			self.anatomy = np.array(nib.load(to_load).get_data(), copy=True)
		def load_z_depth_correction (self):
			to_load = os.path.join(dataset_path, self.fly_name, 'warp', '20201220_warped_z_depth.nii')
			self.z_correction = np.array(nib.load(to_load).get_data(), copy=True)
		def get_cluster_averages (self, cluster_model_labels, n_clusters):
			neural_data = self.brain.reshape(-1, 3384)
			signals = []
			self.cluster_indicies = []
			for cluster_num in range(n_clusters):
				cluster_indicies = np.where(cluster_model_labels==cluster_num)[0]
				mean_signal = np.mean(neural_data[cluster_indicies,:], axis=0)
				signals.append(mean_signal)
				self.cluster_indicies.append(cluster_indicies) # store for later
			self.cluster_signals=np.asarray(signals)
		def get_cluster_id (self, x, y):
			ax_vec = x*128 + y
			for i in range(n_clusters):
				if ax_vec in self.cluster_indicies[i]:
					cluster_id = i
					break
			return cluster_id

	class Fictrac:
		def __init__ (self, fly_dir, timestamps):
			self.fictrac_raw = bbb.load_fictrac(os.path.join(fly_dir, 'fictrac'))
			self.timestamps = timestamps
		def make_interp_object(self, behavior):
			# Create camera timepoints
			fps=50
			camera_rate = 1/fps * 1000 # camera frame rate in ms
			expt_len = 1000*30*60
			x_original = np.arange(0,expt_len,camera_rate)

			# Smooth raw fictrac data
			fictrac_smoothed = scipy.signal.savgol_filter(np.asarray(self.fictrac_raw[behavior]),25,3)

			# Create interp object with camera timepoints
			fictrac_interp_object = interp1d(x_original, fictrac_smoothed, bounds_error = False)
			return fictrac_interp_object

		def pull_from_interp_object(self, interp_object, timepoints):
			new_interp = interp_object(timepoints)
			np.nan_to_num(new_interp, copy=False);
			return new_interp

		def interp_fictrac(self, z):
			behaviors = ['dRotLabY', 'dRotLabZ']; shorts = ['Y', 'Z']
			self.fictrac = {}

			for behavior, short in zip(behaviors, shorts):
				interp_object = self.make_interp_object(behavior)
				self.fictrac[short + 'i'] = interp_object

				### Velocity ###
				low_res_behavior = self.pull_from_interp_object(interp_object, self.timestamps[:,z])
				self.fictrac[short] = low_res_behavior#/np.std(low_res_behavior)

				### Clipped Velocities ###
				self.fictrac[short + '_pos'] = np.clip(self.fictrac[short], a_min=0, a_max=None)
				self.fictrac[short + '_neg'] = np.clip(self.fictrac[short], a_min=None, a_max=0)*-1

				### Strongly Clipped Velocities ###
				# excludes points even close to 0
				#self.fictrac[short + '_pos_very'] = np.clip(self.fictrac[short], a_min=0.3, a_max=None)
				#self.fictrac[short + '_neg_very'] = np.clip(self.fictrac[short], a_min=None, a_max=-0.3)*-1

				### Acceleration ###
				high_res_behavior = self.pull_from_interp_object(interp_object, high_res_timepoints)
				self.fictrac[short + 'h'] = high_res_behavior/np.std(high_res_behavior)

				accel = scipy.signal.savgol_filter(np.diff(high_res_behavior),25,3)
				accel = np.append(accel, 0)
				interp_object = interp1d(high_res_timepoints, accel, bounds_error = False)
				acl = interp_object(self.timestamps[:,z])
				acl[-1] = 0
				self.fictrac[short + 'a'] = acl#/np.std(acl)

				### Clipped Acceleration ###
				self.fictrac[short + 'a' + '_pos'] = np.clip(self.fictrac[short + 'a'], a_min=0, a_max=None)
				self.fictrac[short + 'a' + '_neg'] = np.clip(self.fictrac[short + 'a'], a_min=None, a_max=0)*-1

			self.fictrac['YZ'] = np.sqrt(np.power(self.fictrac['Y'],2), np.power(self.fictrac['Z'],2))
			self.fictrac['YZh'] = np.sqrt(np.power(self.fictrac['Yh'],2), np.power(self.fictrac['Zh'],2))

	#######################
	### Load Superslice ###
	#######################
	brain_file = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201129_super_slices/superslice_{}.nii".format(z) #<---------- !!!
	brain = np.array(nib.load(brain_file).get_data(), copy=True)

	#####################
	### Make Clusters ###
	#####################
	n_clusters = 2000
	labels_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201129_super_slices/cluster_labels.npy'
	cluster_model_labels = np.load(labels_file)
	cluster_model_labels = cluster_model_labels[z,:]

	###################
	### Build Flies ###
	###################
	flies = {}
	for i, fly in enumerate(fly_names):
		flies[fly] = Fly(fly_name=fly, fly_idx=i)
		flies[fly].load_timestamps()
		flies[fly].load_fictrac()
		flies[fly].fictrac.interp_fictrac(z)
		flies[fly].load_brain_slice()
		flies[fly].load_z_depth_correction()
		flies[fly].get_cluster_averages(cluster_model_labels, n_clusters)

	#####################
	### Load Master X ###
	#####################
	file = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201221_neural_weighted_behavior/master_X.npy"
	X = np.load(file)

	#################
	### Main Loop ###
	#################
	for i, fly in enumerate(fly_names):
		cluster_responses = []
		for cluster_num in range(n_clusters):
		    if cluster_num%100 == 0:
		        printlog(str(cluster_num))
		    ###############################################################
		    ### Build Y vector for a single supervoxel (with all flies) ###
		    ###############################################################
		    Y = np.asarray(flies[fly].cluster_signals[cluster_num,:])

		    ###########################################
		    ### Build the X matrix for this cluster ###
		    ###########################################
		    # For each fly, this cluster could have originally come from a different z-depth
		    # Get correct original z-depth
	        cluster_indicies = flies[fly].cluster_indicies[cluster_num]
	        z_map = flies[fly].z_correction[:,:,z].ravel()
	        original_z = int(np.median(z_map[cluster_indicies]))
	        X_cluster = X[original_z,i,:,:]
	        # before, would be [z,fly,timewindow,timepoint]
	        # after loop [fly,timewindow,timepoint]
	        # after reshape [timewindow,fly,timepoint], finally [alltimewindows,timepoints]

	        #for a single fly i have [timewindows,timepoints]
		    #Xs_new = np.asarray(Xs_new)
		    #X_cluster = np.reshape(np.moveaxis(Xs_new,0,1),(-1,33840))

		    ###################
		    ### Dot Product ###
		    ###################
		    cluster_response = np.dot(X_cluster,Y)
		    cluster_responses.append(cluster_response)
		cluster_responses = np.asarray(cluster_responses)

		######################
		### Save Responses ###
		######################
		save_dir = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210210_neural_weighted_behavior_singles'
		save_dir_fly = os.path.join(save_dir, fly)
		if not os.path.exists(save_dir_fly):
			os.mkdir(save_dir_fly)

		save_file = os.path.join(save_dir_fly, F'responses_{z}')
		np.save(save_file, cluster_responses)

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))	 