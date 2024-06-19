# A script to acquire the acquisition list defined in the Acqusitio Manager window
# Warning: there is no check that acquisition sequence duration is shorter tthe timelapse interval. Use with caution.
# Saving only in TIFF files currently
# self. is a reference to the Core class.
TIME_INTERVAL_SEC = 2 * 60 # every 2 minutes
N_TIMEPOINTS = 3 # Number of timepoints to acquire

self.parent.run_timepoint() # Start the first acquisition immediately

acq_list_timer = QtCore.QTimer(self)
acq_list_timer.timeout.connect(self.parent.run_timepoint)
acq_list_timer.start(TIME_INTERVAL_SEC * 1000)
