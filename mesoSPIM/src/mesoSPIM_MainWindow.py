'''
mesoSPIM MainWindow

'''
import copy

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi

from .mesoSPIM_CameraWindow import mesoSPIM_CameraWindow
from .mesoSPIM_AcquisitionManagerWindow import mesoSPIM_AcquisitionManagerWindow

from .mesoSPIM_State import mesoSPIM_State
from .mesoSPIM_Core import mesoSPIM_Core

class mesoSPIM_MainWindow(QtWidgets.QMainWindow):
    '''
    Main application window which instantiates worker objects and moves them
    to a thread.
    '''
    def __init__(self, config=None):
        super().__init__()

        self.cfg = config

        self.state = copy.deepcopy(config.startup)
        self.state_mutex = QtCore.QMutex()

        loadUi('gui/mesoSPIM_MainWindow.ui', self)
        self.setWindowTitle('Thread Template')

        self.camera_window = mesoSPIM_CameraWindow()
        self.camera_window.show()

        self.acquisiton_manager_window = mesoSPIM_AcquisitionManagerWindow(self)
        self.acquisiton_manager_window.show()

        self.core = mesoSPIM_Core(self.cfg, self)
