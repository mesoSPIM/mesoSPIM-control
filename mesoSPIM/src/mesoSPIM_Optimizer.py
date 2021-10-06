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
    sig_move_absolute = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        '''Parent must be an mesoSPIM_MainWindow() object'''
        super().__init__()
        self.parent = parent # the mesoSPIM_MainWindow() object
        self.core = parent.core
        self.cfg = parent.cfg # initial config file
        self.state = mesoSPIM_StateSingleton() # current state
        self.results_window = None
        self.state_key = self.new_state = None
        self.delay_s = 0.1  # give some delay between snaps to avoid state update hickups
        self.roi_dims = None

        self.core.camera_worker.sig_camera_frame.connect(self.set_image)

        loadUi('gui/mesoSPIM_Optimizer.ui', self)
        self.setWindowTitle('mesoSPIM-Optimizer')
        self.show()

        # initialize
        self.set_mode(self.comboBoxMode.currentText())

        # signal switchboard
        self.runButton.clicked.connect(self.run_optimization)
        self.acceptButton.clicked.connect(self.acceptNewState)
        self.discardButton.clicked.connect(self.discardNewState)
        self.closeButton.clicked.connect(self.close_window)
        self.parent.camera_window.sig_update_roi.connect(self.get_roi_dims)
        self.sig_move_absolute.connect(self.core.move_absolute)
        self.comboBoxMode.currentTextChanged.connect(self.set_mode)

    @QtCore.pyqtSlot(np.ndarray)
    def set_image(self, image):
        self.image = image
        self.roi = self.image[self.roi_dims[0]:self.roi_dims[0] + self.roi_dims[2],
                   self.roi_dims[1]:self.roi_dims[1] + self.roi_dims[3]]

    @QtCore.pyqtSlot(tuple)
    def get_roi_dims(self, roi_dims):
        self.roi_dims = np.array(roi_dims).clip(min=0).astype(int)
        #print(f"ROI X, Y, W, H: {self.roi_dims}")

    @QtCore.pyqtSlot(str)
    def set_mode(self, choice):
        shutter = self.state['shutterconfig']
        if choice == "ETL offset":
            self.mode = 'etl_offset'
            self.searchAmpDoubleSpinBox.setValue(0.5)
            self.searchAmpDoubleSpinBox.setSuffix(" V")
            self.state_key = 'etl_l_offset' if shutter == 'Left' else 'etl_r_offset'
        elif choice == "ETL amplitude":
            self.mode = 'etl_amp'
            self.searchAmpDoubleSpinBox.setValue(0.3)
            self.searchAmpDoubleSpinBox.setSuffix(" V")
            self.state_key = 'etl_l_amplitude' if shutter == 'Left' else 'etl_r_amplitude'
        elif choice == "Focus":
            self.mode = 'focus'
            self.searchAmpDoubleSpinBox.setValue(200)
            self.searchAmpDoubleSpinBox.setSuffix(" \u03BCm")
            self.searchAmpDoubleSpinBox.setDecimals(0)
            self.state_key = 'position'
        else:
            raise ValueError(f"{choice} value is not allowed.")

    def set_state(self, new_val):
        if self.mode == 'focus':
            self.sig_move_absolute.emit({'f_abs': new_val})
        else:
            self.core.sig_state_request.emit({self.state_key: new_val})

    @QtCore.pyqtSlot()
    def run_optimization(self):
        self.ini_state = self.state[self.state_key]['f_pos'] if self.mode == 'focus' else self.state[self.state_key]
        print(f"DEBUG: ini state {self.ini_state}")
        self.min_value = self.ini_state - self.searchAmpDoubleSpinBox.value()
        self.max_value = self.ini_state + self.searchAmpDoubleSpinBox.value()
        self.n_points = self.nPointsSpinBox.value()
        assert self.n_points % 2 == 1, f"Number of points must be odd, got {self.n_points} instead."
        self.search_grid = np.linspace(self.min_value, self.max_value, self.n_points)
        self.img_subsampling = self.core.camera_worker.camera_display_acquisition_subsampling
        self.metric_array = np.zeros(len(self.search_grid))
        print(f"Image subsampling: {self.img_subsampling}")
        for i, v in enumerate(self.search_grid):
            self.set_state(v)
            time.sleep(self.delay_s)
            self.core.snap(write_flag=False) # this shares downsampled image via slot self.set_image()
            self.metric_array[i] = shannon_dct(self.roi)
            print(f"{i}, image metric: {self.metric_array[i]}")
        # Reset to initial state
        if self.mode == 'focus':
            self.sig_move_absolute.emit({'f_pos': self.ini_state})
        else:
            self.core.sig_state_request.emit({self.state_key: self.ini_state})

        #fit with Gaussian
        fit_center, fit_sigma, fit_amp, fit_offset = fit_gaussian_1d(self.metric_array, self.search_grid)
        fit_grid = np.linspace(min(self.search_grid), max(self.search_grid), 51)
        gaussian_values = _gaussian_1d(fit_grid, fit_center, fit_sigma, fit_amp, fit_offset)
        self.new_state = fit_center

        # Plot the results and prepare GUI
        self.results_window = pg.GraphicsLayoutWidget(show=True, title='Optimization results')
        self.plot0 = self.results_window.addPlot(title='Image metric')
        self.plot0.addLegend()
        self.plot0.plot(self.search_grid, self.metric_array,
                                 pen=None, symbolBrush=(200,200,200), name='measured')
        self.plot0.plot(x=[self.ini_state], y=[self.metric_array[(len(self.search_grid) - 1)//2]],
                                 symbolBrush=(0,0,250), name='old value')
        self.plot0.plot(fit_grid, gaussian_values,
                                 pen=(200,0,0), symbol=None, name='fitted')
        self.plot0.plot(x=[fit_center], y=[max(gaussian_values)],
                                 symbolBrush=(250, 0, 0), name='new value')
        labelStyle = {'color': '#FFF', 'font-size': '16pt'}
        self.plot0.setLabel('bottom', self.state_key, **labelStyle)
        self.plot0.setLabel('left', 'Shannon(DCT), AU', **labelStyle)

        self.acceptButton.setEnabled(True)
        self.discardButton.setEnabled(True)

    @QtCore.pyqtSlot()
    def acceptNewState(self):
        self.set_state(self.new_state)
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
