# Basic timelapse script for mesoSPIM
# Before running it, the user must:
# - define the acquisition list in the Acquisition Manager window in the usual way
# - make sure the `TIME_INTERVAL_SEC` is sufficiently long to allow the acquisition to finish before the next timepoint starts
# - set file format to TIFF in the Acquisition Manager window

TIME_INTERVAL_SEC = 2 * 60 # every 2 minutes
N_TIMEPOINTS = 3 # Number of timepoints to acquire
self.run_time_lapse(tpoints=N_TIMEPOINTS, time_interval_sec=TIME_INTERVAL_SEC)  
