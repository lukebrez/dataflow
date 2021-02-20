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
from sklearn.linear_model import RidgeCV

import scipy
import nibabel as nib
import bigbadbrain as bbb
import dataflow as flow
import umap
import pickle
import psutil

def main(args):

	logfile = args['logfile']
	num_pcs = args['num_pcs']
	printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

	printlog(F'num pcs: {num_pcs}')

	dataset_path = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20190101_walking_dataset"
	fly_names = ['fly_087', 'fly_089', 'fly_094', 'fly_097', 'fly_098', 'fly_099', 'fly_100', 'fly_101', 'fly_105']
	expt_len = 1000*30*60
	resolution = 10
	high_res_timepoints = np.arange(0,expt_len,resolution) #0 to last time at subsample res

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

		def interp_fictrac(self):
			behaviors = ['dRotLabY', 'dRotLabZ']; shorts = ['Y', 'Z']
			self.fictrac = {}

			### Y and Z ###
			for behavior, short in zip(behaviors, shorts):
				interp_object = self.make_interp_object(behavior)
				self.fictrac[short + 'i'] = interp_object
				
				### Interpolate to neural data
				self.fictrac[short] = []
				self.fictrac[short + '_pos'] = []
				self.fictrac[short + '_neg'] = []
				for z in range(49):
					### Velocity ###
					low_res_behavior = self.pull_from_interp_object(interp_object, self.timestamps[:,z])
					self.fictrac[short].append(low_res_behavior/np.std(low_res_behavior))

					### Clipped Velocities ###
					self.fictrac[short + '_pos'].append(np.clip(self.fictrac[short][-1], a_min=0, a_max=None))
					self.fictrac[short + '_neg'].append(np.clip(self.fictrac[short][-1], a_min=None, a_max=0)*-1)
			
			### Walking ###
			self.fictrac['walking'] = []
			for z in range(49):    
				YZ = np.sqrt(np.power(self.fictrac['Y'][z],2), np.power(self.fictrac['Z'][z],2))        
				self.fictrac['walking'].append(np.zeros(3384))
				self.fictrac['walking'][-1][np.where(YZ>.2)] = 1

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

	# # need to change a few key things to switch to reconstructed data
	# # originally, was given a brain of shape (256,128,3384,9)
	# # now I have (30456, 26840) time by voxel

	# # new super voxels
	# labels_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/labels.pickle'
	# with open(labels_file, 'rb') as handle:
	#     cluster_model_labels = pickle.load(handle)

	# # use this to get super voxels from a desired slice:
	# running_sum = 0
	# new = []
	# for z in range(9,49-9):
	#     num_clusters = len(np.unique(cluster_model_labels[z]))
	#     new.append(out[:,running_sum:num_clusters+running_sum])
	#     running_sum += num_clusters

	# # keep fly loop. restrict z loop. 

	# new super voxels
	labels_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/labels.pickle'
	with open(labels_file, 'rb') as handle:
	    cluster_model_labels = pickle.load(handle)

	# #### FOR SUPERFLY-BASED PCA RECONSTRUCTION ####
	# # reconstructed data
	# file = F'/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210216_reconstructed_{num_pcs}.npy'
	# brain = np.load(file) # (30456, 26840) time by voxel
	# ### reshape brain
	# running_sum = 0
	# brain_z = []
	# for z in range(9,49-9):
	#     num_clusters = len(np.unique(cluster_model_labels[z]))
	#     brain_z.append(brain[:,running_sum:num_clusters+running_sum])
	#     running_sum += num_clusters
	# # brain_z[z] is now time by voxels for a given z-slice

	flies = {}
	fly_names = ['fly_094']
	for i, fly in enumerate(fly_names):
		i = 2 #temp hardcode - REMOVE <--------------------------------------------------------------- !!!
		printlog(F'*** fly: {fly} ***')
		flies[fly] = Fly(fly_name=fly, fly_idx=i)
		flies[fly].load_timestamps()
		flies[fly].load_fictrac()
		flies[fly].fictrac.interp_fictrac()
		flies[fly].load_z_depth_correction()

		### FOR SINGLE-FLY PCA RECONSTRUCTION #######################
		# here i have not yet run the reconstruction in jupyter, so i'll do it here:
		file = F'/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210214_eigen_vectors_ztrim_fly{i}.npy'
		vectors = np.load(file).real
		#print(vectors.shape)# vectors is voxel by PC probably (3384, 3384)
		printlog(f'vectors are {vectors.shape} voxel by PC')

		load_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/super_brain.pickle'
		with open(load_file, 'rb') as handle:
		    temp_brain = pickle.load(handle)
		#brain is a dict of z, each containing a variable number of supervoxels
		#one dict element looks like: (n_clusters, 3384, 9)
		X = np.zeros((0,3384,9))
		for z in range(9,49-9):
		    X = np.concatenate((X,temp_brain[z]),axis=0)
		X = np.swapaxes(X,1,2) # THIS LINE WAS MISSING
		X = np.reshape(X,(26840, -1))
		X = X.T
		#X.shape # x is time by voxels (30456, 26840)
		num_tp = 3384
		start = i*num_tp
		stop = (i+1)*num_tp
		X = X[start:stop,:] # now (3384,26840)
		printlog(f'X is {X.shape} time by voxel - expecting (3384,26840)')

		temporal = X.dot(vectors)
		brain = np.matmul(temporal[:,:num_pcs], vectors[:,:num_pcs].T)
		# brain should be (3384, 26840) time by voxel
		printlog(f'brain is {brain.shape} time by voxel - expecting (3384,26840)')

		### reshape brain
		running_sum = 0
		brain_z = []
		for z in range(9,49-9):
		    num_clusters = len(np.unique(cluster_model_labels[z]))
		    brain_z.append(brain[:,running_sum:num_clusters+running_sum])
		    running_sum += num_clusters
		# brain_z[z] is now time by voxels for a given z-slice

		############################################################

		for z in range(9,49-9):
			printlog(F'Z: {z}')
			# #labels_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201129_super_slices/final_9_cluster_labels_2000.npy'
			# labels_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201129_super_slices/cluster_labels.npy'
			# cluster_model_labels = np.load(labels_file) #z,t
			# cluster_model_labels = cluster_model_labels[z,:]

			# brain_file = "/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20201129_super_slices/superslice_{}.nii".format(z) #<---------- !!!
			# brain = np.array(nib.load(brain_file).get_data(), copy=True)
			# fly_idx_delete = 3 #(fly_095)
			# brain = np.delete(brain, fly_idx_delete, axis=-1) #### DELETING FLY_095 ####

			#for i, fly in enumerate(fly_names):
			#flies[fly].load_brain_slice()
			#flies[fly].get_cluster_averages(cluster_model_labels, n_clusters)

			#for i, fly in enumerate(fly_names):

			scores_all = []

			scores_walking = []
			scores_ypos = []
			scores_zpos = []
			scores_zneg = []

			scores_walking_unique = []
			scores_ypos_unique = []
			scores_zpos_unique = []
			scores_zneg_unique = []

			for cluster_num in range(len(np.unique(cluster_model_labels[z]))):
				# if cluster_num == 100:
				# 	printlog(str(cluster_num))
				###############################################################
				### Build Y vector for a single supervoxel (with all flies) ###
				###############################################################
				# all_fly_neural = []
				#for fly in fly_names:
				# signal = flies[fly].cluster_signals[cluster_num,:]
				# all_fly_neural.extend(signal)
				# Y = np.asarray(all_fly_neural)

				# grab single fly from superfly
				# num_tp = 3384
				# start = i*num_tp
				# stop = (i+1)*num_tp
				Y = brain_z[z-9]#[start:stop,:] # -9 to correct for shift
				# now Y is (3384, voxel)
				Y = Y[:,cluster_num]

				###########################################
				### Build the X matrix for this cluster ###
				###########################################
				# For each fly, this cluster could have originally come from a different z-depth
				# Get correct original z-depth
				ypos = []
				zpos = []
				zneg = []
				walking = []
				#for i, fly in enumerate(fly_names):

				cluster_indicies = np.where(cluster_model_labels[z]==cluster_num)[0]
				#cluster_indicies = flies[fly].cluster_indicies[cluster_num]
				z_map = flies[fly].z_correction[:,:,z].ravel()
				original_z = int(np.median(z_map[cluster_indicies]))
				ypos.extend(flies[fly].fictrac.fictrac['Y_pos'][original_z])
				zpos.extend(flies[fly].fictrac.fictrac['Z_pos'][original_z])
				zneg.extend(flies[fly].fictrac.fictrac['Z_neg'][original_z])
				walking.extend(flies[fly].fictrac.fictrac['walking'][original_z])
											   
				### ALL ###
				X = np.stack((ypos, zpos, zneg, walking)).T
				model = RidgeCV().fit(X,Y)
				scores_all.append(np.sqrt(model.score(X,Y)))
				   
				### Singles ###
				X = np.reshape(walking, (-1, 1))
				model = RidgeCV().fit(X,Y)
				scores_walking.append(np.sqrt(model.score(X,Y)))
				
				X = np.reshape(ypos, (-1, 1))
				model = RidgeCV().fit(X,Y)
				scores_ypos.append(np.sqrt(model.score(X,Y)))
				
				X = np.reshape(zpos, (-1, 1))
				model = RidgeCV().fit(X,Y)
				scores_zpos.append(np.sqrt(model.score(X,Y)))
				
				X = np.reshape(zneg, (-1, 1))
				model = RidgeCV().fit(X,Y)
				scores_zneg.append(np.sqrt(model.score(X,Y)))
					
				### LOO ###
				X = np.stack((ypos, zpos, zneg)).T
				model = RidgeCV().fit(X,Y)
				scores_walking_unique.append(np.sqrt(model.score(X,Y)))
				
				X = np.stack((zpos, zneg, walking)).T
				model = RidgeCV().fit(X,Y)
				scores_ypos_unique.append(np.sqrt(model.score(X,Y)))
				
				X = np.stack((ypos, zneg, walking)).T
				model = RidgeCV().fit(X,Y)
				scores_zpos_unique.append(np.sqrt(model.score(X,Y)))
				
				X = np.stack((ypos, zpos, walking)).T
				model = RidgeCV().fit(X,Y)
				scores_zneg_unique.append(np.sqrt(model.score(X,Y)))

			### Save ###
			save_dir = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210216_inst_uniq_glm_recon'
			save_dir_fly = os.path.join(save_dir, fly)
			if not os.path.exists(save_dir_fly):
				os.mkdir(save_dir_fly)

			save_dir_fly_pc = os.path.join(save_dir_fly, str(num_pcs) + '_singlePCA')
			if not os.path.exists(save_dir_fly_pc):
				os.mkdir(save_dir_fly_pc)

			save_file = os.path.join(save_dir_fly_pc, F'Z{z}.pickle')
			scores = {'scores_all':scores_all,
					 'scores_walking':scores_walking,
					 'scores_ypos':scores_ypos,
					 'scores_zpos':scores_zpos,
					 'scores_zneg':scores_zneg,
					 'scores_walking_unique':scores_walking_unique,
					 'scores_ypos_unique':scores_ypos_unique,
					 'scores_zpos_unique':scores_zpos_unique,
					 'scores_zneg_unique':scores_zneg_unique}

			with open(save_file, 'wb') as handle:
				pickle.dump(scores, handle, protocol=pickle.HIGHEST_PROTOCOL)
			printlog('SAVED')

if __name__ == '__main__':
	main(json.loads(sys.argv[1]))