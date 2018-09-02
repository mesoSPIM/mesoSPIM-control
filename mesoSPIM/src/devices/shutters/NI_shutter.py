"""
mesoSPIM Module for controlling a shutter via NI-DAQmx
Author: Fabian Voigt
#TODO
"""

import nidaqmx
from nidaqmx.constants import LineGrouping

class NI_Shutter:
    """
    Slow shutter, intended more as a gating device than a fast open/close because the
    NI task is recreated and deleted every time a shutter is actuated.

    Thus, the shutter has more a "gating" function to protect the sample than
    fast control of the laser, this is done via the laser intensity anyway.

    This uses the property of NI-DAQmx-outputs to keep their last digital state or
    analog voltage for as long the device is not powered down.
    """
    def __init__(self, shutterline):
        self.shutterline =  shutterline

        # Make sure that the Shutter is closed upon initialization
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.shutterline,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write([False], auto_start=True)
            self.shutterstate = False

    # Open and close shutter take an optional argument to deal with the on_click method of Jupyter Widgets
    def open(self, *args):
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.shutterline,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write([True], auto_start=True)
            self.shutterstate = True

    def close(self, *args):
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(self.shutterline,line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
            task.write([False], auto_start=True)
            self.shutterstate = False

    def state(self, *args):
        """ Returns "True" if the shutter is open, otherwise "False" """
        return self.shutterstate
