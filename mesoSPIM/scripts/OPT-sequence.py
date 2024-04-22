# Quick script to acquire OPT projection sequence
# choose the number of angular steps at least 256 for a full OPT projection sequence
n_angular_steps = 12
theta_step = int(360/n_angular_steps)
for i in range(n_angular_steps):
	print('OPT projection sequence started')
	self.move_relative({'theta_rel':theta_step}, wait_until_done=True)
	self.snap()
	time.sleep(1)
	print(f'{i+1}/{n_angular_steps} done')