'''
Core for the mesoSPIM project
=============================
'''

import numpy as np
import time
from scipy import signal
import csv
import traceback

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

'''National Instruments Imports'''
import nidaqmx
from nidaqmx.constants import AcquisitionType, TaskMode
from nidaqmx.constants import LineGrouping, DigitalWidthUnits
from nidaqmx.types import CtrTime

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_State

class mesoSPIM_Core(QtCore.QObject):
    '''This class is the pacemaker of a mesoSPIM'''

    def __init__(self, config, parent):
        super().__init__()

        self.state = mesoSPIM_State(config)

        with QMutexLocker(state_mutex):
            s.filter = filterstring

    def live(self):
        pass
