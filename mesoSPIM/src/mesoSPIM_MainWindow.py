'''
mesoSPIM MainWindow

'''
import sys
import copy

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi

from .mesoSPIM_CameraWindow import mesoSPIM_CameraWindow
from .mesoSPIM_AcquisitionManagerWindow import mesoSPIM_AcquisitionManagerWindow
from .mesoSPIM_ScriptWindow import mesoSPIM_ScriptWindow

from .mesoSPIM_State import mesoSPIM_State
from .mesoSPIM_Core import mesoSPIM_Core

class mesoSPIM_MainWindow(QtWidgets.QMainWindow):
    '''
    Main application window which instantiates worker objects and moves them
    to a thread.
    '''
    sig_live = QtCore.pyqtSignal()
    sig_finished = QtCore.pyqtSignal()

    sig_enable_gui = QtCore.pyqtSignal()

    sig_state_request = QtCore.pyqtSignal(dict)

    sig_execute_script = QtCore.pyqtSignal(str)

    def __init__(self, config=None):
        super().__init__()

        self.cfg = config
        self.script_window_counter = 0

        self.state = copy.deepcopy(config.startup)
        self.state_mutex = QtCore.QMutex()

        loadUi('gui/mesoSPIM_MainWindow.ui', self)
        self.setWindowTitle('Thread Template')

        self.camera_window = mesoSPIM_CameraWindow()
        self.camera_window.show()

        self.acquisition_manager_window = mesoSPIM_AcquisitionManagerWindow(self)
        self.acquisition_manager_window.show()

        # self.script_window = mesoSPIM_ScriptWindow(self)

        self.core = mesoSPIM_Core(self.cfg, self)

        ''' Connecting the menu actions '''
        self.actionClose.triggered.connect(lambda: self.close())
        self.actionScriptWindow.triggered.connect(self.create_script_window)

        ''' Connecting the buttons and other GUI elements'''
        self.LiveButton.clicked.connect(lambda: self.sig_live.emit())

        self.FilterComboBox.addItems(self.cfg.filterdict.keys())
        self.FilterComboBox.currentTextChanged.connect(lambda: self.sig_state_request.emit({'filter':self.FilterComboBox.currentText()}))
        self.FilterComboBox.setCurrentText(config.startup['filter'])

        self.ZoomComboBox.addItems(self.cfg.zoomdict.keys())
        self.ZoomComboBox.currentTextChanged.connect(lambda: self.sig_state_request.emit({'zoom':self.ZoomComboBox.currentText()}))
        self.ZoomComboBox.setCurrentText(config.startup['zoom'])

        self.ShutterComboBox.addItems(self.cfg.shutteroptions)
        self.ShutterComboBox.currentTextChanged.connect(lambda: self.sig_state_request.emit({'shutterconfig':self.ShutterComboBox.currentText()}))
        self.ShutterComboBox.setCurrentText(config.startup['shutterconfig'])

        self.LaserComboBox.addItems(self.cfg.laserdict.keys())
        self.LaserComboBox.currentTextChanged.connect(lambda: self.sig_state_request.emit({'laser':self.LaserComboBox.currentText()}))
        self.LaserComboBox.setCurrentText(config.startup['laser'])

        self.LaserIntensitySlider.valueChanged.connect(lambda: self.sig_state_request.emit({'intensity':self.LaserIntensitySlider.value()}))
        self.LaserIntensitySlider.setValue(config.startup['intensity'])

        ''' The signal switchboard '''
        self.core.sig_finished.connect(lambda: self.sig_finished.emit())

    def create_script_window(self):
        windowstring = 'self.scriptwindow'+str(self.script_window_counter)
        exec(windowstring+ '= mesoSPIM_ScriptWindow(self)')
        exec(windowstring+'.show()')
        exec(windowstring+'.sig_execute_script.connect(self.core.execute_script)')
        self.script_window_counter += 1

    def request_state(self, keys, values):
        pass

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.sig_execute_script.emit(script)
