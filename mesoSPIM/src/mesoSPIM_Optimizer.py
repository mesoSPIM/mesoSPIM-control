import sys
import numpy as np
from .utils.optimization import shannon_dct

import logging
logger = logging.getLogger(__name__)

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi
from .mesoSPIM_State import mesoSPIM_StateSingleton


class mesoSPIM_Optimizer(QtWidgets.QWidget):
    sig_state_request = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        '''Parent must be an mesoSPIM_MainWindow() object'''
        super().__init__()
        self.parent = parent # the mesoSPIM_MainWindow() object
        self.core = parent.core
        self.cfg = parent.cfg # initial config file
        self.state = mesoSPIM_StateSingleton() # current state

        loadUi('gui/mesoSPIM_Optimizer.ui', self)
        self.setWindowTitle('mesoSPIM-Optimizer')
        self.show()

        self.runButton.clicked.connect(self.run_optimization)

    @QtCore.pyqtSlot()
    def run_optimization(self):
        print("OPTIMIZATION")
