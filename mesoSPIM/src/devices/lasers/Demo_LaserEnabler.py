class Demo_LaserEnabler:
    def __init__(self, laserdict):
        self.laserenablestate = 'None'
        self.laserdict = laserdict

    def _check_if_laser_in_laserdict(self, laser):
        if laser in self.laserdict:
            return True
        else:
            raise ValueError('Laser not in the configuration')
    
    def enable(self, laser):
        if self._check_if_laser_in_laserdict(laser) == True:
            self.laserenablestate = laser
        else:
            pass

    def enable_all(self):
        self.laserenablestate = 'all on'

    def disable_all(self):
        self.laserenablestate = 'off'

    def state(self):
        return self.laserenablestate