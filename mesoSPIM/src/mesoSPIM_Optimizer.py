'''
Frontend of the optimizer which allows to use auto-focus or optimization of other microscope parameters
Auto-focus is based on Autopilot paper (Royer at al, Nat Biotechnol. 2016 Dec;34(12):1267-1278. doi: 10.1038/nbt.3708.)
author: Nikita Vladimirov, @nvladimus, 2021
License: GPL-3
'''

import time
import numpy as np
from .utils.optimization import shannon_dct, fit_gaussian_1d, gaussian_1d
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
        self.results_window = self.graphics_widget = None
        self.modes_list = ['etl_offset', 'etl_amp', 'focus']
        self.mode = self.modes_list[0]
        self.n_points = 5
        self.search_amplitude = 0.5
        self.state_key = None
        self.image = self.roi = self.roi_dims = self.img_subsampling = None
        self.ini_state = self.ini_metric = self.new_state = self.min_value = self.max_value = None
        self.search_grid = self.metric_array = self.fit_grid = self.gaussian_values = None
        self.delay_s = 0.5  # time delay between snaps to avoid state update hickups, esp for heavy lens-camera assembly during AF

        loadUi('gui/mesoSPIM_Optimizer.ui', self)
        self.setWindowTitle('mesoSPIM-Optimizer')
        self.show()

        # initialize
        #self.set_parameters({'mode': 'etl_offset', 'amplitude': 0.5, 'n_points': 7})

        # signal switchboard
        self.core.camera_worker.sig_camera_frame.connect(self.set_image)
        self.runButton.clicked.connect(self.run_optimization)
        self.closeButton.clicked.connect(self.close_window)

        self.parent.camera_window.sig_update_roi.connect(self.get_roi_dims)
        self.sig_move_absolute.connect(self.core.move_absolute)
        self.comboBoxMode.currentTextChanged.connect(self.set_mode_from_gui)

    @QtCore.pyqtSlot(np.ndarray)
    def set_image(self, image):
        self.image = image
        self.roi = self.image[self.roi_dims[1]:self.roi_dims[1] + self.roi_dims[3],
                   self.roi_dims[0]:self.roi_dims[0] + self.roi_dims[2]]

    @QtCore.pyqtSlot(tuple)
    def get_roi_dims(self, roi_dims):
        self.roi_dims = np.array(roi_dims).clip(min=0).astype(int)

    def set_roi(self, orientation='h', roi_perc=0.25):
        img_w, img_h = self.parent.camera_window.get_image_shape()
        if orientation == 'h':
            self.parent.camera_window.set_roi('box', (0, img_h*(1-roi_perc)//2, img_w, int(img_h*roi_perc)))
        elif orientation == 'v':
            self.parent.camera_window.set_roi('box', (img_w*(1-roi_perc)//2, 0, int(img_w*roi_perc), img_h))
        elif orientation == 'c':
            self.parent.camera_window.set_roi('box', (img_h * (1 - roi_perc) // 2, (img_w * (1 - roi_perc)) // 2,
                                                    int(img_h * roi_perc), int(img_w * roi_perc)))
        elif orientation is None:
            self.parent.camera_window.set_roi(None, (0, 0, img_w, img_h))
        else:
            raise ValueError("Orientation must be one of ('h', 'v', None).")

    def set_parameters(self, param_dict=None, update_gui=True):
        if param_dict:
            if 'mode' in param_dict.keys():
                self.mode = param_dict['mode']
            if 'amplitude' in param_dict.keys():
                self.search_amplitude = param_dict['amplitude']
            if 'n_points' in param_dict.keys():
                self.n_points = param_dict['n_points']
        if self.mode == 'focus':
            self.state_key = 'position'
        elif self.mode == 'etl_offset':
            assert self.state['shutterconfig'] in ('Left', 'Right'),  f"Shutter config must be in ('Left', 'Right'), got {self.state['shutterconfig']}"
            self.state_key = 'etl_l_offset' if self.state['shutterconfig'] == 'Left' else 'etl_r_offset'
        elif self.mode == 'etl_amp':
            ini_etl_amp = 0.1 # so that we never start from zero
            self.state_key = 'etl_l_amplitude' if self.state['shutterconfig'] == 'Left' else 'etl_r_amplitude'
            if self.state[self.state_key] == 0:
                self.core.sig_state_request.emit({self.state_key: ini_etl_amp})
                print(f"Initial ETL amp set to {ini_etl_amp}")
        if update_gui:
            self.update_gui()

    def update_gui(self):
        if self.mode == 'focus':
            self.searchAmpDoubleSpinBox.setSuffix(" \u03BCm")
            self.searchAmpDoubleSpinBox.setDecimals(0)
            self.set_roi('c')
        else:
            self.searchAmpDoubleSpinBox.setSuffix(" V")
            self.searchAmpDoubleSpinBox.setDecimals(3)
            self.set_roi('v') if self.mode == 'etl_offset' else self.set_roi('h')

        mode_index = self.modes_list.index(self.mode)
        if mode_index != self.comboBoxMode.currentIndex():
            self.comboBoxMode.setCurrentIndex(mode_index)
        if self.search_amplitude != self.searchAmpDoubleSpinBox.value():
            self.searchAmpDoubleSpinBox.setValue(self.search_amplitude)
        if self.n_points != self.nPointsSpinBox.value():
            self.nPointsSpinBox.setValue(self.n_points)

    @QtCore.pyqtSlot(str)
    def set_mode_from_gui(self, choice):
        if choice == "ETL offset":
            self.set_parameters({'mode': 'etl_offset', 'amplitude': 0.2, 'n_points': 7})
        elif choice == "ETL amplitude":
            self.set_parameters({'mode': 'etl_amp', 'amplitude': 0.1, 'n_points': 7})
        elif choice == "Focus":
            self.set_parameters({'mode': 'focus', 'amplitude': 300, 'n_points': 7})
        else:
            raise ValueError(f"{choice} value is not allowed.")

    def get_params_from_gui(self):
        self.mode = self.modes_list[self.comboBoxMode.currentIndex()]
        self.search_amplitude = self.searchAmpDoubleSpinBox.value()
        self.n_points = self.nPointsSpinBox.value()

    def set_state(self, new_val):
        if self.mode == 'focus':
            self.sig_move_absolute.emit({'f_abs': new_val})
        else:
            self.core.sig_state_request.emit({self.state_key: new_val})

    def set_etl_amp_to_zero(self):
        if self.state_key == 'etl_l_offset':
            self.core.sig_state_request.emit({'etl_l_amplitude': 0})
            print("ETL offset optimization: ETL amplitude (L) set to 0")
        elif self.state_key == 'etl_r_offset':
            self.core.sig_state_request.emit({'etl_r_amplitude': 0})
            print("ETL offset optimization: ETL amplitude (R) set to 0")

    @QtCore.pyqtSlot()
    def run_optimization(self):
        self.parent.sig_state_request.emit({'state': 'idle'}) # stop Live if it is running
        time.sleep(0.5)
        self.get_params_from_gui()
        self.set_etl_amp_to_zero()
        self.ini_state = self.state[self.state_key]['f_pos'] if self.mode == 'focus' else self.state[self.state_key]
        self.min_value = self.ini_state - self.search_amplitude
        if self.mode in ('etl_offset', 'etl_amp'):
            self.min_value = max(self.min_value, 0) # clip negative values for ETL
        self.max_value = self.ini_state + self.search_amplitude
        assert self.n_points % 2 == 1, f"Number of points must be odd, got {self.n_points} instead."
        self.search_grid = np.linspace(self.min_value, self.max_value, self.n_points)
        self.img_subsampling = self.core.camera_worker.camera_display_acquisition_subsampling
        self.metric_array = np.zeros(len(self.search_grid))
        print(f"Image subsampling: {self.img_subsampling}")
        print(f"Initial value: {self.ini_state:.3f}, searching in ({self.min_value:.3f}, {self.max_value:.3f}), n_points {self.n_points}")
        for i, v in enumerate(self.search_grid):
            self.set_state(v)
            time.sleep(self.delay_s)
            if i == 0:
                self.core.snap(write_flag=False, laser_blanking=True) # clears the first image from buffer
            self.core.snap(write_flag=False, laser_blanking=True) # this shares downsampled image via slot self.set_image()
            self.metric_array[i] = shannon_dct(self.roi)

        self.set_state(self.ini_state) # Reset to initial state
        time.sleep(self.delay_s) # give it some time to settle
        self.core.snap(write_flag=False)  # this shares downsampled image via slot self.set_image()
        self.ini_metric = shannon_dct(self.roi)

        #fit with Gaussian
        fit_center, fit_sigma, fit_amp, fit_offset = fit_gaussian_1d(self.metric_array, self.search_grid)
        self.fit_grid = np.linspace(min(self.search_grid), max(self.search_grid), 51)
        self.gaussian_values = gaussian_1d(self.fit_grid, fit_center, fit_sigma, fit_amp, fit_offset)
        self.new_state = fit_center

        # Plot the results
        self.create_results_window()
        self.plot_results()

    def create_results_window(self):
        self.results_window = loadUi('gui/mesoSPIM_Optimizer_Results.ui')
        self.results_window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.results_window.setWindowTitle('Optimization results')
        # signal switchboard for results window
        self.results_window.acceptButton.clicked.connect(self.accept_new_state)
        self.results_window.discardButton.clicked.connect(self.discard_new_state)

    def plot_results(self):
        layout = pg.QtGui.QGridLayout()
        self.results_window.setLayout(layout)

        self.graphics_widget = pg.GraphicsLayoutWidget(show=True)
        plot0 = self.graphics_widget.addPlot(title='Image metric')
        plot0.addLegend(offset=(0, 0))
        plot0.plot(self.search_grid, self.metric_array, pen=None, symbolBrush=(150,0,150), name='measured')
        plot0.plot(x=[self.ini_state], y=[self.ini_metric],  symbolBrush=(0,0,250), name='old state')
        plot0.plot(x=[self.new_state], y=[max(self.gaussian_values)], symbolBrush=(250, 0, 0), name='new state')
        plot0.plot(self.fit_grid, self.gaussian_values, pen=(200, 0, 0), symbol=None, name='fitted')

        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        plot0.setLabel('bottom', self.state_key, **labelStyle)
        plot0.setLabel('left', 'Shannon(DCT), AU', **labelStyle)
        plot0.showGrid(x=True)
        plot0.setYRange(min(self.gaussian_values.min(), self.metric_array.min())*0.7,
                        max(self.gaussian_values.max(), self.metric_array.max())*1.2)
        self.results_window.label_results.setText(self.results_string())

        layout.addWidget(self.graphics_widget, 0, 0, 1, 2, QtCore.Qt.AlignHCenter)
        layout.addWidget(self.results_window.label_results, 1, 0, 1, 2, QtCore.Qt.AlignHCenter)
        layout.addWidget(self.results_window.acceptButton, 2, 0, 1, 1, QtCore.Qt.AlignHCenter)
        layout.addWidget(self.results_window.discardButton, 2, 1, 1, 1, QtCore.Qt.AlignHCenter)
        self.results_window.show()

    def results_string(self):
        """Pretty formatting"""
        if self.mode == 'focus':
            return f"Old: {self.ini_state:.0f}\t New: {self.new_state:.0f}\t Diff: {(self.new_state - self.ini_state):.0f}"
        else:
            return f"Old: {self.ini_state:.3f}\t New: {self.new_state:.3f}\t Diff: {(self.new_state - self.ini_state):.3f}"

    @QtCore.pyqtSlot()
    def accept_new_state(self):
        self.set_state(self.new_state)
        print(f"Fitted value: {self.new_state:.3f}")
        time.sleep(self.delay_s)
        self.core.snap(write_flag=False, laser_blanking=True)
        state_str = f"{self.state[self.state_key]}" if self.mode == 'focus' else f"{self.state[self.state_key]:.3f}"
        print(f"New {self.state_key}:{state_str}")
        self.results_window.deleteLater()
        self.results_window = None

    @QtCore.pyqtSlot()
    def discard_new_state(self):
        self.new_state = None
        self.results_window.deleteLater()
        self.results_window = None

    @QtCore.pyqtSlot()
    def close_window(self):
        self.parent.camera_window.set_roi(None)
        if self.results_window:
            self.results_window.deleteLater()
        self.close()
