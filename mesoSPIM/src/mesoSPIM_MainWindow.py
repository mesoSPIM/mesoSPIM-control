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
        self.enable_external_gui_updates = False

        ''' Instantiate the one and only mesoSPIM state and get a mutex for it '''
        self.state = copy.deepcopy(config.startup)
        self.state_mutex = QtCore.QMutex()

        loadUi('gui/mesoSPIM_MainWindow.ui', self)
        self.setWindowTitle('Thread Template')

        self.camera_window = mesoSPIM_CameraWindow()
        self.camera_window.show()

        self.acquisition_manager_window = mesoSPIM_AcquisitionManagerWindow(self)
        self.acquisition_manager_window.show()

        ''' Setting the mesoSPIM_Core thread up '''
        self.core_thread = QtCore.QThread()
        self.core = mesoSPIM_Core(self.cfg, self)
        self.core.moveToThread(self.core_thread)

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
        self.core.sig_finished.connect(self.enable_gui)
        self.core.sig_state_updated.connect(self.update_gui_from_state)

        ''' Start the threads '''
        self.core_thread.start()

    def __del__(self):
        '''Cleans the threads up after deletion, waits until the threads
        have truly finished their life.

        Make sure to keep this up to date with the number of threads
        '''
        try:
            self.core_thread.quit()
            self.core_thread.wait()
        except:
            pass

    def get_state_parameter(self, key):
        with QtCore.QMutexLocker(self.state_mutex):
            if key in self.state:
                return self.state[key]
            else:
                print('Getting state parameters failed: Key ', key, 'not in state dictionary!')

    def set_state_parameter(self, key, value):
        '''
        Sets the mesoSPIM state

        In order to do this, a QMutexLocker has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
            else:
                print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def set_state_parameters(self, dict):
        '''
        Sets a whole dict of mesoSPIM state parameters:

        Args:
            dict (dict):
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            for key, value in dict:
                if key in self.parent.state:
                    self.parent.state[key]=value
                    self.sig_state_updated.emit()
                else:
                    print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def create_script_window(self):
        '''
        Creates a script window and binds it to a self.scriptwindow0 ... n instanceself.

        This happens dynamically using exec which should be replaced at
        some point with a factory pattern.
        '''
        windowstring = 'self.scriptwindow'+str(self.script_window_counter)
        exec(windowstring+ '= mesoSPIM_ScriptWindow(self)')
        exec(windowstring+'.setWindowTitle("Script Window #'+str(self.script_window_counter)+'")')
        exec(windowstring+'.show()')
        exec(windowstring+'.sig_execute_script.connect(self.execute_script)')
        self.script_window_counter += 1

    def request_state(self, keys, values):
        pass

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.enable_external_gui_updates = True
        self.sig_execute_script.emit(script)

    def update_gui_from_state(self):
        sender = self.sender()
        print(sender)
        print(self.enable_external_gui_updates)
        if self.enable_external_gui_updates is True:
            self.ControlGroupBox.blockSignals(True)
            with QtCore.QMutexLocker(self.state_mutex):
                self.FilterComboBox.setCurrentText(self.state['filter'])
                self.ZoomComboBox.setCurrentText(self.state['zoom'])
                self.ShutterComboBox.setCurrentText(self.state['shutterconfig'])
                self.LaserComboBox.setCurrentText(self.state['laser'])
                self.LaserIntensitySlider.setValue(self.state['intensity'])
            #QtWidgets.QApplication.processEvents()
            self.ControlGroupBox.blockSignals(False)
            # also for self.tabWidget

    def disable_gui(self):
        pass

    def enable_gui(self):
        self.enable_external_gui_updates = False
