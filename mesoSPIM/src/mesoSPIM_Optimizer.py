import sys
import time
import numpy as np
from .utils.optimization import shannon_dct, fit_gaussian_1d, _gaussian_1d
import pyqtgraph as pg

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
        self.results_window = None
        self.new_state = None
        self.delay_s = 0.1  # give some delay between snaps to avoid state update hickups

        loadUi('gui/mesoSPIM_Optimizer.ui', self)
        self.setWindowTitle('mesoSPIM-Optimizer')
        self.show()

        self.runButton.clicked.connect(self.run_optimization)
        self.acceptButton.clicked.connect(self.acceptNewState)
        self.discardButton.clicked.connect(self.discardNewState)
        self.closeButton.clicked.connect(self.close_window)

    @QtCore.pyqtSlot()
    def run_optimization(self):
        shutter = self.state['shutterconfig']
        if shutter == 'Left':
            self.state_key = 'etl_l_offset'
        else:
            self.state_key = 'etl_r_offset'
        self.ini_state = self.state[self.state_key]
        self.min_value = self.ini_state - self.searchAmpDoubleSpinBox.value()
        self.max_value = self.ini_state + self.searchAmpDoubleSpinBox.value()
        self.n_points = self.nPointsSpinBox.value()
        assert self.n_points % 2 == 1, f"Number of points must be odd, got {self.n_points} instead."
        self.search_grid = np.linspace(self.min_value, self.max_value, self.n_points)
        self.img_subsampling = self.core.camera_worker.camera_display_acquisition_subsampling
        self.metric_array = np.zeros(len(self.search_grid))
        print(f"Image subsampling: {self.img_subsampling}")
        for i, v in enumerate(self.search_grid):
            self.core.sig_state_request.emit({self.state_key: v})
            time.sleep(self.delay_s)
            self.core.snap(write_flag=False)
            img = self.core.camera_worker.camera.get_image()[::self.img_subsampling, ::self.img_subsampling]
            self.metric_array[i] = shannon_dct(img)
            print(f"{i}, image metric: {self.metric_array[i]}")
        # Reset to initial state
        self.core.sig_state_request.emit({self.state_key: self.ini_state})
        #fit with Gaussian
        fit_center, fit_sigma, fit_amp, fit_offset = fit_gaussian_1d(self.metric_array, self.search_grid)
        fit_grid = np.linspace(min(self.search_grid), max(self.search_grid), 51)
        gaussian_values = _gaussian_1d(fit_grid, fit_center, fit_sigma, fit_amp, fit_offset)
        self.new_state = fit_center

        # Plot the results and prepare GUI
        self.results_window = pg.plot(title='Image metric')
        self.results_window.addLegend()
        self.results_window.plot(self.search_grid, self.metric_array,
                                 pen=None, symbolBrush=(200,200,200), name='measured')
        self.results_window.plot(x=[self.ini_state], y=[self.metric_array[(len(self.search_grid) - 1)//2]],
                                 symbolBrush=(0,0,250), name='old value')
        self.results_window.plot(fit_grid, gaussian_values,
                                 pen=(200,0,0), symbol=None, name='fitted')
        self.results_window.plot(x=[fit_center], y=[max(gaussian_values)],
                                 symbolBrush=(250, 0, 0), name='new value')
        labelStyle = {'color': '#FFF', 'font-size': '16pt'}
        self.results_window.setLabel('bottom', self.state_key, **labelStyle)
        self.results_window.setLabel('left', 'Shannon(DCT), AU', **labelStyle)

        self.acceptButton.setEnabled(True)
        self.discardButton.setEnabled(True)

    @QtCore.pyqtSlot()
    def acceptNewState(self):
        self.core.sig_state_request.emit({self.state_key: self.new_state})
        print(f"Fitted value: {self.new_state}")
        print(f"New {self.state_key}:{self.state[self.state_key]}")

        self.acceptButton.setEnabled(False)
        self.discardButton.setEnabled(False)

    @QtCore.pyqtSlot()
    def discardNewState(self):
        self.new_state = None
        self.acceptButton.setEnabled(False)
        self.discardButton.setEnabled(False)

    @QtCore.pyqtSlot()
    def close_window(self):
        if self.results_window:
            self.results_window.close()
        self.close()
