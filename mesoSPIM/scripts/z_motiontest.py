for i in range(10):
	print('Starting movement')
	self.serial_worker.move_relative({'z_rel':1000}, wait_until_done=True)
	print('Done with the first movement')
	time.sleep(1)
	print('Starting second movement')
	self.serial_worker.move_relative({'z_rel':-1000}, wait_until_done=True)
	time.sleep(1)
	print('Done with the second movement')