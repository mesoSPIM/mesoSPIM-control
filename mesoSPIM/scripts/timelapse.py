# A script to acquire the acquisition list defined in the Acqusitio Manager window
# Warning: there is no check that acquisition sequence duration is shorter tthe timelapse interval. Use with caution.
# Saving only in TIFF files currently
# self. is a reference to the Core class.
#TIME_INTERVAL_SEC = 2 * 60 # every 2 minutes
N_TIMEPOINTS = 10
for it in range(N_TIMEPOINTS):
	print('Timelapse started')
	self.parent.acquisition_manager_window.append_time_index_to_filenames(it)
	self.parent.run_acquisition_list()
	#time.sleep(TIME_INTERVAL_SEC)
	print(f'{it+1}/{N_TIMEPOINTS} done')