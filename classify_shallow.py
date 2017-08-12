from __future__ import print_function
from ConfigParser import SafeConfigParser
from shallow_clf.features_extractor import RootSIFT
from shallow_clf import codebook_generator as cbk
from shallow_clf import bovw
from progressbar import Percentage, ProgressBar,Bar,ETA
from preprocessor import utils
import argparse
import os, shutil
import h5py
import numpy as np
import cv2

#Create command line arguments parser
ap = argparse.ArgumentParser()
ap.add_argument('-c', '--config', required=True, help='Path to the configuration file')
ap.add_argument('-e', '--extract', action='store_true', 
				help='Extract and save local features from images')
ap.add_argument('-b', '--bovw', action='store_true', help='Describe images with bovw')
args = vars(ap.parse_args())

#Parse config file
parser = SafeConfigParser()
parser.read(args['config'])


#Execute if the script started with the -e option
if args['extract']:
	
	#Define local helper functions
	def prepare_datasets(file_path,features_ds):
		data_file = h5py.File(file_path, mode='w')
		data_file.create_dataset(features_ds, (0,128), maxshape=(None,128),
					dtype='float')
		return data_file
	
	features_data = parser.get('local_paths', 'local_features')	
	features_ds = parser.get('datasets', 'data')
	
	#Check if hdf5 file with local features exists
	if os.path.exists(features_data):
		features_file = h5py.File(features_data, mode='a')
	else:
		features_file = prepare_datasets(features_data, features_ds)
		
	
	training_data = parser.get('local_paths', 'training_data')	
	data_file = h5py.File(training_data, mode='r')
	
	#Create instance of RootSIFT descriptor
	extractor = RootSIFT()
	
	pbar = ProgressBar(widgets=[Bar(), ' ', Percentage(), ' ', ETA()])
	
	#Iterate through every image in training set and extract features
	print('[INFO] Saving local features data to {}'.format(features_data))
	for img in pbar(data_file[features_ds]):
		gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
		features = extractor.compute(gray)
		if len(features) != 0:
			utils.save_data(features, features_file[features_ds])
	
	data_file.close()
	features_file.close()

	
#Execute if the script started with the -b option (Bag of Visual Words)
if args['bovw']:

	#Define local helper functions
	def prepare_datasets(file_path,features_ds, features_dim):
		data_file = h5py.File(file_path, mode='a')
		data_file.create_dataset(features_ds, (0,features_dim), maxshape=(None,features_dim),
					dtype='float')
		return data_file
		
	def extract_features(data_array, extractor):
		bovw_features = []
		for image in data_array:
			gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
			features = extractor.compute(gray)
			
			if len(features) > 0:
				bovw_features.append(bovw.describe(features, codebook))
			else:
				bovw_features.append(np.zeros(n_clusters))
		return bovw_features
		
		
	codebook_data = parser.get('local_paths', 'codebook')	
	
	#Check if codebook exists
	if os.path.exists(codebook_data):
		codebook = cbk.load_codebook(codebook_data)
	else:
		#------------------#
		#Generate a codebook
		#------------------#
		
		#Get paths and settings
		features_data = parser.get('local_paths', 'local_features')
		features_file = h5py.File(features_data, 'r')
		features_ds = parser.get('datasets', 'data')
		sample_percent = int(parser.get('settings', 'codebook_samples'))/100.
		n_clusters = int(parser.get('settings', 'clusters'))

		#Get subset of data and close the HDF5 file
		subset = cbk.get_random_subset(features_file[features_ds], sample_percent)
		features_file.close()
		
		#Calculate clusters centers
		codebook = cbk.generate_codebook(subset, n_clusters)
		
		#Save the codebook
		cbk.save_codebook(codebook, codebook_data)
		

	#-----------------------------#	
	#Extract and save bovw features
	#-----------------------------#
	
	#Create instance of RootSIFT descriptor
	extractor = RootSIFT()
	
	features_ds = parser.get('datasets', 'data')
	shallow_ds = parser.get('datasets', 'shallow')
	n_clusters = int(parser.get('settings', 'clusters'))
	
	#--------------------#
	#Process training data
	#--------------------#
	training_data = parser.get('local_paths', 'training_data')
	
	
	trn_bovw_data = parser.get('local_paths', 'training_bovw_features')
	if os.path.exists(trn_bovw_data):
		trn_bovw_file = h5py.File(trn_bovw_data,mode='a')
	else:
		shutil.copyfile(training_data, trn_bovw_data)
		trn_bovw_file = prepare_datasets(trn_bovw_data,shallow_ds, n_clusters)
		
	#Create batch generator instance
	batches = bovw.get_batches(trn_bovw_file[features_ds],10000)
	
	
	#Iterate through batches and extract features
	for batch in batches:
		print('[INFO] Processing next training batch')
		bovw_features = extract_features(batch, extractor)
		utils.save_data(bovw_features,trn_bovw_file[shallow_ds])
	trn_bovw_file.close()
    
	
	#--------------------#
	#Process tresting data
	#--------------------#
	testing_data = parser.get('local_paths', 'testing_data')
	
	test_bovw_data = parser.get('local_paths', 'testing_bovw_features')
	if os.path.exists(test_bovw_data):
		test_bovw_file = h5py.File(test_bovw_data,mode='a')
	else:
		shutil.copyfile(testing_data, test_bovw_data)
		test_bovw_file = prepare_datasets(test_bovw_data,shallow_ds, n_clusters)
	
	data = test_bovw_file[features_ds]
	
	print('[INFO] Processing testing data')
	bovw_features = extract_features(data, extractor)
	utils.save_data(bovw_features,test_bovw_file[shallow_ds])

	test_bovw_file.close()	