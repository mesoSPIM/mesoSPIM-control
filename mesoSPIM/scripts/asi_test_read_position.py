for i in range(50):
	logger.info(f"{self.serial_worker.stage.asi_stages.read_position()}")
	time.sleep(0.02)