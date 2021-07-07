## Scripts usage
Scripts are files with python code that exposes `mesoSPIM_Core` class methods for direct use. 

### Examples of scripts
Relative motion of stages
```
for i in range(10):
	print('Starting Z movement')
	self.serial_worker.move_relative({'z_rel':1000}, wait_until_done=True)
	print('Done with the first movement')
	time.sleep(1)
	print('Starting X movement')
	self.serial_worker.move_relative({'x_rel':-1000}, wait_until_done=True)
	print('Done with the X movement')
```
Snapping images (and saving them into snap folder)
```
for i in range(10):
	self.snap()
	print('Image Number: '+str(i))
	time.sleep(1)
```
Changing filters
```
for filter in ['515LP','561LP','594LP']:
	self.set_filter(filter, wait_until_done=True)
	time.sleep(0.1)
```
Setting zoom
```
for zoom in ['1x','2x','4x','5x']:
	self.set_zoom(zoom, wait_until_done=True)
	time.sleep(0.1)
```
Adjusting ETL parameters
```
min_offset, max_offset = 0, 3
for offset in np.linspace(min_offset,max_offset,11):
	self.sig_state_request.emit({'etl_l_offset' : offset})
	time.sleep(1)

min_amp, max_amp = 0, 1.5	
for amp in np.linspace(min_amp,max_amp,11):
	self.sig_state_request.emit({'etl_l_amplitude' : amp})
	time.sleep(1)
```