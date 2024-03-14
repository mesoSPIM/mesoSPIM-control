"""
mesoSPIM Module for controlling a shutter via NI-DAQmx
Authors: Nikita Vladimirov, Fabian Voigt

"""

import nidaqmx
from nidaqmx.constants import LineGrouping
import logging
logger = logging.getLogger(__name__)

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
        self.shutterline = shutterline

        # Make sure that the Shutter is closed upon initialization
        if self.shutterline:
            with nidaqmx.Task() as task:
                if self.shutterline != '':
                    task.do_channels.add_do_chan(self.shutterline, line_grouping=LineGrouping.CHAN_PER_LINE)
                    task.write([False], auto_start=True)
                    self.shutterstate = False
        else:
            logger.info("No shutter line defined, skipping shutter initialization.")
            return None

    # Open and close shutter take an optional argument to deal with the on_click method of Jupyter Widgets
    def open(self, *args):
        if self.shutterline:
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(self.shutterline, line_grouping=LineGrouping.CHAN_PER_LINE)
                task.write([True], auto_start=True)
                self.shutterstate = True
        else:
            logger.info("No shutter line defined, skipping shutter opening.")

    def close(self, *args):
        if self.shutterline:
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(self.shutterline, line_grouping=LineGrouping.CHAN_PER_LINE)
                task.write([False], auto_start=True)
                self.shutterstate = False
        else:
            logger.info("No shutter line defined, skipping shutter closing.")

    def state(self, *args):
        """ Returns "True" if the shutter is open, otherwise "False" """
        return self.shutterstate
