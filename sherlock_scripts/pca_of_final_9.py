import sys
import numpy as np
import json
import time
import dataflow as flow
import pickle

from sklearn.decomposition import PCA
from sklearn.decomposition import IncrementalPCA

def main(args):

    logfile = args['logfile']
    fly_idx = args['fly_idx']
    printlog = getattr(flow.Printlog(logfile=logfile), 'print_to_log')

    printlog('numpy: ' + str(np.__version__))

    # load_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210115_super_brain/20210115_super_brain.npy'
    # brain = np.load(load_file)
    # printlog('brain is shape {}'.format(brain.shape))
    # printlog(F'X_type is {X_type}')
    # # 2000,49,3384,9


    load_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/super_brain.pickle'
    with open(load_file, 'rb') as handle:
        temp_brain = pickle.load(handle)
    #brain is a dict of z, each containing a variable number of supervoxels
    #one dict element looks like: (n_clusters, 3384, 9)
    X = np.zeros((0,3384,9))
    #for z in range(49):
    for z in range(9,49-9):
        X = np.concatenate((X,temp_brain[z]),axis=0)

    printlog(str(X.shape))
    #printlog(F'X_type is {X_type}')
    X = np.swapaxes(X,1,2) # THIS LINE WAS MISSING
    #X = np.reshape(X,(30858, -1))
    X = np.reshape(X,(-1, 30456))
    X = X.T

    # there are 30456 timepoints


    # if X_type == 'single_slice':
    #     X = np.reshape(brain[:,20,:,:], (2000,3384*9))
    #     # 2000, 30456
    #     X = X.T
    #     # 30456, 2000
    # elif X_type == 'two_slice_near':
    #     X = np.reshape(brain[:,20:22,:,:], (2000*2,3384*9))
    #     X = X.T
    # elif X_type == 'two_slice_far':
    #     X = np.reshape(brain[:,[20,30],:,:], (2000*2,3384*9))
    #     X = X.T
    # elif X_type == 'one_fly':
    #     X = np.reshape(brain[:,:,:,0], (2000*49,3384))
    #     X = X.T
    # elif X_type == 'two_fly':
    #     X = np.reshape(brain[:,:,:,0:2], (2000*49,3384*2))
    #     X = X.T
    # elif X_type == 'all_slice':
    #     X = np.reshape(brain, (2000*49,3384*9))
    #     # 98000, 30456
    #     X = X.T
    #     # 30456, 98000
    # elif X_type == 'trimmed_zs':
    #     X = np.reshape(brain[:,7:42,:,:], (-1,3384*9))
    #     X = X.T
    # elif X_type == 'seven_fly_trimmed_zs':
    #     X = np.reshape(brain[:,7:42,:,:7], (-1,3384*7))
    #     X = X.T
    # elif X_type == 'all_fly_trimmed_zs':
    #     X = np.reshape(brain[:,7:42,:,:], (-1,3384*9))
    #     X = X.T
    # elif X_type == 'all_fly_trimmed_zs_more':
    #     X = np.reshape(brain[:,15:35,:,:], (-1,3384*9))
    #     X = X.T
    # elif X_type == 'five_fly':
    #     X = np.reshape(brain[:,:,:,0:5], (2000*49,-1))
    #     X = X.T
    # elif X_type == 'new_clusters':
    #     X = np.reshape(brain, (-1,3384*9))
    #     X = X.T
    # elif X_type == 'ones':
    #     printlog('MATRIX OF ONES')
    #     X = np.ones((30456,30858))
    # # elif X_type == 'fly_087':
    # #     X = np.reshape(brain[:,:,:,0], (2000*49,3384))
    # #     X = X.T

    # else:
    #     printlog('INVALID X_TYPE')
    #     return

    printlog('X is time by voxels {}'.format(X.shape))
    num_tp = 3384
    start = fly_idx*num_tp
    stop = (fly_idx+1)*num_tp
    X = X[start:stop,:]
    printlog(F'fly_idx: {fly_idx}, start: {start}, stop: {stop}')
    printlog('After fly_idx, X is time by voxels {}'.format(X.shape))

    
    printlog('Using np.linalg.ein')
    covariance_matrix = np.cov(X.T)
    eigen_values, eigen_vectors = np.linalg.eig(covariance_matrix)

    printlog('eigen_values is {}'.format(eigen_values.shape))
    save_file = F'/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210214_eigen_values_ztrim_fly{fly_idx}.npy'
    np.save(save_file, eigen_values)

    printlog('eigen_vectors is {}'.format(eigen_vectors.shape))
    save_file = F'/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210214_eigen_vectors_ztrim_fly{fly_idx}.npy'
    np.save(save_file, eigen_vectors)

    # printlog('PCA START...')
    # pca = IncrementalPCA().fit(X)
    # #pca = PCA().fit(X)
    # printlog('PCA COMPLETE')

    # pca_scores = pca.components_
    # printlog('Scores is PC by voxel {}'.format(pca_scores.shape))
    # save_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210213_pca_scores_inc.npy'
    # np.save(save_file, pca_scores)
    # printlog('scores saved')

    # pca_loadings = pca.transform(X)
    # printlog('Loadings is time by PC {}'.format(pca_loadings.shape))

    # printlog('deleting X for memory')
    # X = None
    # time.sleep(10)

    # save_file = '/oak/stanford/groups/trc/data/Brezovec/2P_Imaging/20210130_superv_depth_correction/20210213_pca_loadings_inc.npy'
    # np.save(save_file, pca_loadings)
    # # printlog('SAVING COMPLETE')

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))