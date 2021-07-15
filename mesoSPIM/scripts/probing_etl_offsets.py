laser = "488 nm"
image_counter = 0
delay_s = 1 # give plenty of delay between snaps to avoid hickups
self.set_laser(laser, wait_until_done=True, update_etl=False)
etl_midvalues_R_L = {"488 nm": (2.5, 2.2),
					"561 nm": (2.7, 2.4)}
# R-arm offset probing
self.set_shutterconfig("Right")
self.open_shutters()
self.sig_state_request.emit({'etl_r_amplitude' : 0})
min_offset = etl_midvalues_R_L[laser][0] - 0.5
max_offset = etl_midvalues_R_L[laser][0] + 0.5
for offset in np.linspace(min_offset, max_offset, 21):
	self.sig_state_request.emit({'etl_r_offset' : offset})
	time.sleep(delay_s)
	self.snap()
	image_counter += 1
	print(image_counter)

# L-arm offset
self.set_shutterconfig("Left")
self.open_shutters()
self.sig_state_request.emit({'etl_l_amplitude' : 0})
min_offset = etl_midvalues_R_L[laser][1] - 0.5
max_offset = etl_midvalues_R_L[laser][1] + 0.5
for offset in np.linspace(min_offset, max_offset, 21):
	self.sig_state_request.emit({'etl_l_offset' : offset})
	time.sleep(delay_s)
	self.snap()
	image_counter += 1
	print(image_counter)
