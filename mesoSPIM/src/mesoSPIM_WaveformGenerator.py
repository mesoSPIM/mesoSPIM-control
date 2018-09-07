'''
mesoSPIM Waveform Generator - Creates and 
'''


'''National Instruments Imports'''
import nidaqmx
from nidaqmx.constants import AcquisitionType, TaskMode
from nidaqmx.constants import LineGrouping, DigitalWidthUnits
from nidaqmx.types import CtrTime

'''
mesoSPIM State class
'''
from PyQt5 import QtCore

class mesoSPIM_StateModel(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by 
    the responsible class for actually causing that state change in hardware.

    '''
    sig_state_model_updated = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        self.cfg = parent.cfg
        self.state = self.cfg.startup

