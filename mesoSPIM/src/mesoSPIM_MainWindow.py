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

# from .mesoSPIM_State import mesoSPIM_State
from .mesoSPIM_Core import mesoSPIM_Core
from .devices.joysticks.mesoSPIM_JoystickHandlers import mesoSPIM_JoystickHandler

class mesoSPIM_MainWindow(QtWidgets.QMainWindow):
    '''
    Main application window which instantiates worker objects and moves them
    to a thread.
    '''
    # sig_live = QtCore.pyqtSignal()
    sig_stop = QtCore.pyqtSignal()

    sig_finished = QtCore.pyqtSignal()

    sig_enable_gui = QtCore.pyqtSignal()

    sig_state_request = QtCore.pyqtSignal(dict)

    sig_execute_script = QtCore.pyqtSignal(str)

    sig_move_relative = QtCore.pyqtSignal(dict)
    sig_move_relative_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_move_absolute = QtCore.pyqtSignal(dict)
    sig_move_absolute_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()

    def __init__(self, config=None):
        super().__init__()

        '''
        Initial housekeeping
        '''

        self.cfg = config
        self.script_window_counter = 0
        self.enable_external_gui_updates = False

        ''' Instantiate the one and only mesoSPIM state and get a mutex for it '''
        self.state = copy.deepcopy(config.startup)
        self.state_mutex = QtCore.QMutex()

        '''
        Setting up the user interface windows
        '''

        loadUi('gui/mesoSPIM_MainWindow.ui', self)
        self.setWindowTitle('mesoSPIM Main Window')

        self.camera_window = mesoSPIM_CameraWindow()
        self.camera_window.show()

        self.acquisition_manager_window = mesoSPIM_AcquisitionManagerWindow(self)
        self.acquisition_manager_window.show()

        '''
        Setting up the threads
        '''

        ''' Setting the mesoSPIM_Core thread up '''
        self.core_thread = QtCore.QThread()
        self.core = mesoSPIM_Core(self.cfg, self)
        self.core.moveToThread(self.core_thread)

        ''' Connecting the menu actions '''
        self.openScriptEditorButton.clicked.connect(self.create_script_window)

        ''' Connecting the movement & zero buttons '''
        self.xPlusButton.pressed.connect(lambda: self.sig_move_relative.emit({'x_rel': self.xyzIncrementSpinbox.value()}))
        self.xMinusButton.pressed.connect(lambda: self.sig_move_relative.emit({'x_rel': -self.xyzIncrementSpinbox.value()}))
        self.yPlusButton.pressed.connect(lambda: self.sig_move_relative.emit({'y_rel': self.xyzIncrementSpinbox.value()}))
        self.yMinusButton.pressed.connect(lambda: self.sig_move_relative.emit({'y_rel': -self.xyzIncrementSpinbox.value()}))
        self.zPlusButton.pressed.connect(lambda: self.sig_move_relative.emit({'z_rel': self.xyzIncrementSpinbox.value()}))
        self.zMinusButton.pressed.connect(lambda: self.sig_move_relative.emit({'z_rel': -self.xyzIncrementSpinbox.value()}))
        self.focusPlusButton.pressed.connect(lambda: self.sig_move_relative.emit({'f_rel': self.focusIncrementSpinbox.value()}))
        self.focusMinusButton.pressed.connect(lambda: self.sig_move_relative.emit({'f_rel': -self.focusIncrementSpinbox.value()}))
        self.rotPlusButton.pressed.connect(lambda: self.sig_move_relative.emit({'theta_rel': self.rotIncrementSpinbox.value()}))
        self.rotMinusButton.pressed.connect(lambda: self.sig_move_relative.emit({'theta_rel': -self.rotIncrementSpinbox.value()}))

        self.xyzrotStopButton.pressed.connect(self.sig_stop_movement.emit)

        self.xyZeroButton.toggled.connect(lambda bool: print('XY toggled') if bool is True else print('XY detoggled'))
        self.xyZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['x','y']) if bool is True else self.sig_unzero_axes.emit(['x','y']))
        self.zZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['z']) if bool is True else self.sig_unzero_axes.emit(['z']))
        # self.xyzZeroButton.clicked.connect(lambda bool: self.sig_zero.emit(['x','y','z']) if bool is True else self.sig_unzero.emit(['x','y','z']))
        self.focusZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['f']) if bool is True else self.sig_unzero_axes.emit(['f']))
        self.rotZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['theta']) if bool is True else self.sig_unzero_axes.emit(['theta']))
        #
        self.xyzLoadButton.clicked.connect(self.sig_load_sample.emit)
        self.xyzUnloadButton.clicked.connect(self.sig_unload_sample.emit)

        self.LiveButton.clicked.connect(self.live)
        self.StopButton.clicked.connect(self.sig_stop.emit)
        self.StopButton.clicked.connect(lambda: print('Stopping'))

        ''' Connecting the microscope controls '''
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
        self.core.sig_position.connect(self.update_position_indicators)

        ''' Start the threads '''
        self.core_thread.start()

        ''' Setting up the joystick '''
        self.joystick = mesoSPIM_JoystickHandler(self)

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
            if key in self.state:
                self.state[key]=value
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
                if key in self.state:
                    self.state[key]=value
                    self.sig_state_updated.emit()
                else:
                    print('Set state parameters failed: Key ', key, 'not in state dictionary!')

    def pos2str(self, position):
        ''' Little helper method for converting positions to strings '''

        ''' Show 2 decimal places '''
        return '%.2f' % position

    @QtCore.pyqtSlot(dict)
    def update_position_indicators(self, dict):
        self.X_Position_Indicator.setText(self.pos2str(dict['x_pos'])+' µm')
        self.Y_Position_Indicator.setText(self.pos2str(dict['y_pos'])+' µm')
        self.Z_Position_Indicator.setText(self.pos2str(dict['z_pos'])+' µm')
        self.Focus_Position_Indicator.setText(self.pos2str(dict['f_pos'])+' µm')
        self.Rotation_Position_Indicator.setText(self.pos2str(dict['theta_pos'])+'°')

        ''' Update position state '''
        self.set_state_parameter('position', dict)

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
        self.block_signals_from_controls(True)
        self.sig_execute_script.emit(script)

    def block_signals_from_controls(self, bool):
        self.FilterComboBox.blockSignals(bool)
        self.ZoomComboBox.blockSignals(bool)
        self.ShutterComboBox.blockSignals(bool)
        self.LaserComboBox.blockSignals(bool)
        self.LaserIntensitySlider.blockSignals(bool)

    def update_gui_from_state(self):
        # sender = self.sender()
        # print(sender)
        # print(self.enable_external_gui_updates)
        if self.enable_external_gui_updates is True:
            # self.ControlGroupBox.blockSignals(True)
            with QtCore.QMutexLocker(self.state_mutex):
                self.FilterComboBox.setCurrentText(self.state['filter'])
                self.ZoomComboBox.setCurrentText(self.state['zoom'])
                self.ShutterComboBox.setCurrentText(self.state['shutterconfig'])
                self.LaserComboBox.setCurrentText(self.state['laser'])
                self.LaserIntensitySlider.setValue(self.state['intensity'])
            # self.ControlGroupBox.blockSignals(False)
            # also for self.tabWidget

    def live(self):
        print('Going live')
        self.sig_state_request.emit({'state':'live'})

    def disable_gui(self):
        pass

    def enable_gui(self):
        self.enable_external_gui_updates = False
        self.block_signals_from_controls(False)
