self.sig_polling_stage_position_stop.emit()

for i in range(100):
	response = self.serial_worker.stage.asi_stages._send_command('W VZRXY\r'.encode('ascii'))
	logger.info(f"Received: {response}")
    
self.sig_polling_stage_position_start.emit()