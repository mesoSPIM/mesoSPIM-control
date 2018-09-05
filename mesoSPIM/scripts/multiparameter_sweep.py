for filter in ['515LP','561LP','594LP']:
	self.set_filter(filter, wait_until_done=True)
	time.sleep(0.1)
	
for zoom in ['1x','2x','4x','5x']:
	self.set_zoom(zoom, wait_until_done=True)
	time.sleep(0.1)