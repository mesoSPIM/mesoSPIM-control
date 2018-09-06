"""
mesoSPIM Module for enabling single laser lines via NI-DAQmx

Author: Fabian Voigt

#TODO
"""

import nidaqmx
from nidaqmx.constants import LineGrouping

class mesoSPIM_LaserEnabler:
    ''' Class for interacting with the laser enable DO lines via NI-DAQmx

    Works only with NI-PXI 6733s with all lasers on 6 output lines.

    This uses the property of NI-DAQmx-outputs to keep their last digital state or
    analog voltage for as long the device is not powered down. This means that
    the NI tasks are closed after calls to "enable", "disable", etc which in turn
    means that this class is not intended for fast switching in complicated waveforms.

    Needs a dictionary which combines laser wavelengths and device outputs
    in the form:
    {'488 nm': 'PXI6259/line0/port0', '515 nm': 'PXI6259/line0/port1'}
    '''
    def __init__(self, laserdict):
        self.laserenablestate = 'None'
        self.laserdict = laserdict

        # get a value in the laserdict to get the general device string
        self.laserenable_device = next(iter(self.laserdict.values()))
        # strip the line number at the end (e.g. PXI6259/line0/port0)
        self.laserenable_device = self.laserenable_device[0:-1]
        # add 0:7 to the device string:
        self.laserenable_device += '0:7'

        # Make sure that all the Lasers are off upon initialization:
        self.disable_all()

    def _check_if_laser_in_laserdict(self, laser):
        '''Checks if the laser designation (string) given as argument exists in the laserdict'''
        if laser in self.laserdict:
            return True
        else:
            raise ValueError('Laser not in the configuration')

    def _build_cmd_int(self, laser):
        '''Turns the line number into a command integer via 2^n'''
        self.line = self.laserdict[laser][-1]
        return pow(2,int(self.line))

    def enable(self, laser):
        '''Enables a single laser line. If another laser was on beforehand, this one is switched off.'''
        if self._check_if_laser_in_laserdict(laser) == True:
            #print(self.laserdict[laser])
            self.cmd = self._build_cmd_int(laser)

            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(self.laserenable_device,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                task.write(self.cmd, auto_start=True)

            self.laserenablestate = laser
            #print('enabled '+ laser)
        else:
            pass

    def enable_all(self):
        '''Enables all laser lines.'''
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.laserenable_device,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write(255, auto_start=True)

        self.laserenablestate = 'all on'
        #print('enabled all')

    def disable_all(self):
        '''Disables all laser lines.'''
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.laserenable_device,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write(0, auto_start=True)

        self.laserenablestate = 'off'
        #print('disabled all')

    def state(self):
        """ Returns laserline if a laser is on, otherwise "False" """
        return self.laserenablestate
