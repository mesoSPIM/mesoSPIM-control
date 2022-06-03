"""
mesoSPIM Module for enabling single laser lines via NI-DAQmx

Authors: Fabian Voigt, Nikita Vladimirov
"""

import nidaqmx
from nidaqmx.constants import LineGrouping

class mesoSPIM_LaserEnabler:
    ''' Class for interacting with the laser enable DO lines via NI-DAQmx
    This uses the property of NI-DAQmx-outputs to keep their last digital state or
    analog voltage for as long the device is not powered down. This means that
    the NI tasks are closed after calls to "enable", "disable", etc which in turn
    means that this class is not intended for fast switching in complicated waveforms.
    Needs a dictionary which combines laser wavelengths and device outputs
    in the form:
    {'488 nm': 'PXI1Slot4/port0/line2',
    '515 nm': 'PXI1Slot4/port0/line3'}
    '''
    def __init__(self, laserdict):
        self.laserenablestate = 'None'
        self.laserdict = laserdict

        # get a value in the laserdict to get the general device string
        self.laserenable_device = ''
        self.laser_keys_sorted = sorted(laserdict.keys())
        for key in self.laser_keys_sorted:
            self.laserenable_device += laserdict[key] + ','
        self.disable_all()         # Make sure that all the Lasers are off upon initialization:

    def _check_if_laser_in_laserdict(self, laser):
        '''Checks if the laser designation (string) given as argument exists in the laserdict'''
        if laser in self.laserdict:
            return True
        else:
            raise ValueError('Laser not in the configuration')

    def enable(self, laser):
        '''Enables a single laser line. All other lines are switched off.'''
        if self._check_if_laser_in_laserdict(laser):
            command_list = [False]*len(self.laserdict)
            ind_line_on = list(self.laser_keys_sorted).index(laser)
            command_list[ind_line_on] = True
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(self.laserenable_device, line_grouping=LineGrouping.CHAN_PER_LINE)
                task.write(command_list, auto_start=True)
            self.laserenablestate = laser
        else:
            pass

    def disable_all(self):
        '''Disables all laser lines.'''
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.laserenable_device, line_grouping=LineGrouping.CHAN_PER_LINE)
            task.write([False]*len(self.laserdict), auto_start=True)
        self.laserenablestate = 'off'

    def state(self):
        """ Returns laserline if a laser is on, otherwise "False" """
        return self.laserenablestate
