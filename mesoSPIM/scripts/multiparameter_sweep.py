for filter in ['515LP','561LP','594LP']:
	self.set_filter(filter, wait_until_done=True)
	time.sleep(0.1)
	
for zoom in ['1x','2x','4x','5x']:
	self.set_zoom(zoom, wait_until_done=True)
	time.sleep(0.1)

# Deprecated?
# for offset in np.linspace(0,5,21):
# 	self.set_galvo_l_offset(offset)
# 	time.sleep(0.2)