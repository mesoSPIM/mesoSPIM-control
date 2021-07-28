import sys
import time
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
        shutter = self.state['shutterconfig']
        if shutter == 'Left':
            self.state_key = 'etl_l_offset'
        else:
            self.state_key = 'etl_r_offset'
        self.ini_value = self.state[self.state_key]
        self.min_value = self.ini_value - self.searchAmpDoubleSpinBox.value()
        self.max_value = self.ini_value + self.searchAmpDoubleSpinBox.value()
        self.n_points = self.nPointsSpinBox.value()
        self.img_subsampling = self.core.camera_worker.camera_display_acquisition_subsampling
        for i, v in enumerate(np.linspace(self.min_value, self.max_value, self.n_points)):
            self.core.sig_state_request.emit({self.state_key: v})
            self.core.snap(write_flag=False)
            img = self.core.camera_worker.camera.get_image()[::self.img_subsampling, ::self.img_subsampling]
            print(f"{i}, image shape: {img.shape}")
        print("DONE")
