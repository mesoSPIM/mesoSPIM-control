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

from .mesoSPIM_State import mesoSPIM_StateModel
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
    sig_state_model_request = QtCore.pyqtSignal(dict)
    sig_state_changed = QtCore.pyqtSignal(dict)

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

        ''' Instantiate the one and only mesoSPIM state '''
        self.state_model = mesoSPIM_StateModel(self)
        self.state_model_mutex = QtCore.QMutex()
        self.sig_state_model_request.connect(self.state_model.set_state)
        self.state_model.sig_state_model_updated.connect(self.update_gui_from_state)

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

        ''' Get buttons & connections ready '''
        self.initialize_and_connect_widgets()

        ''' The signal switchboard '''
        self.core.sig_finished.connect(lambda: self.sig_finished.emit())
        self.core.sig_finished.connect(self.enable_gui)

        self.core.sig_state_model_request.connect(lambda dict: self.sig_state_model_request.emit(dict))
        self.core.sig_state_model_request.connect(self.update_position_indicators)
                
        self.core.sig_progress.connect(self.update_progressbars)

        ''' Start the thread '''
        self.core_thread.start()

        ''' Setting up the joystick '''
        self.joystick = mesoSPIM_JoystickHandler(self)

        ''' Connecting the camera frames (this is a deep connection and slightly
        risky) It will break immediately when there is an API change.'''
        try:
            self.core.camera_worker.sig_camera_frame.connect(self.camera_window.set_image)
            print('Camera connected successfully to the display window!')
        except:
            print('Warning: camera not connected to display!')

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

    def create_widget_list(self):
        for widget in self.centralWidget.children():
            if isinstance(widget, QtWidgets.QLineEdit):
                print(f"Linedit: {widget.objectName()} - {widget.text()}")

            if isinstance(widget, QtWidgets.QCheckBox):
                print(f"QCheckBox: {widget.objectName()} - {widget.text()}")

            if isinstance(widget, QtWidgets.QPushbutton):
                print(f"QPushbutton: {widget.objectName()} - {widget.text()}")

    @QtCore.pyqtSlot(str)
    def display_status_message(self, string, time=0):
        '''
        Displays a message in the status bar for a time in ms

        If time=0, the message will stay.
        '''

        if time == 0:
            self.statusBar().showMessage(string)
        else:
            self.statusBar().showMessage(string, time)

    def pos2str(self, position):
        ''' Little helper method for converting positions to strings '''

        ''' Show 2 decimal places '''
        return '%.2f' % position

    @QtCore.pyqtSlot(dict)
    def update_position_indicators(self, dict):
        for key, pos_dict in dict.items():
            if key == 'position':
                self.X_Position_Indicator.setText(self.pos2str(pos_dict['x_pos'])+' µm')
                self.Y_Position_Indicator.setText(self.pos2str(pos_dict['y_pos'])+' µm')
                self.Z_Position_Indicator.setText(self.pos2str(pos_dict['z_pos'])+' µm')
                self.Focus_Position_Indicator.setText(self.pos2str(pos_dict['f_pos'])+' µm')
                self.Rotation_Position_Indicator.setText(self.pos2str(pos_dict['theta_pos'])+'°')

    @QtCore.pyqtSlot(dict)
    def update_progressbars(self,dict):
        cur_acq = dict['current_acq']
        tot_acqs = dict['total_acqs']
        cur_image = dict['current_image_in_acq']
        images_in_acq = dict['images_in_acq']
        tot_images = dict['total_image_count']
        image_count = dict['image_counter']

        self.AcquisitionProgressBar.setValue(int((cur_image+1)/images_in_acq*100))
        self.TotalProgressBar.setValue(int((image_count+1)/tot_images*100))

        self.AcquisitionProgressBar.setFormat('%p% (Image '+ str(cur_image+1) +\
                                        '/' + str(images_in_acq) + ')')
        self.TotalProgressBar.setFormat('%p% (Acquisition '+ str(cur_acq+1) +\
                                        '/' + str(tot_acqs) +\
                                         ')' + ' (Image '+ str(image_count) +\
                                        '/' + str(tot_images) + ')')

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

    def initialize_and_connect_widgets(self):
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
        self.StopButton.clicked.connect(lambda: self.sig_state_request.emit({'state':'idle'}))
        self.StopButton.clicked.connect(lambda: print('Stopping'))

        ''' Connecting the microscope controls '''
        self.connect_combobox_to_state_parameter(self.FilterComboBox,self.cfg.filterdict.keys(),'filter')
        self.connect_combobox_to_state_parameter(self.ZoomComboBox,self.cfg.zoomdict.keys(),'zoom')
        self.connect_combobox_to_state_parameter(self.ShutterComboBox,self.cfg.shutteroptions,'shutterconfig')
        self.connect_combobox_to_state_parameter(self.LaserComboBox,self.cfg.laserdict.keys(),'laser')

        self.LaserIntensitySlider.valueChanged.connect(lambda currentValue: self.sig_state_request.emit({'intensity': currentValue}))
        self.LaserIntensitySlider.setValue(self.cfg.startup['intensity'])

        ''' Connecting camera parameter controls '''
        self.connect_spinbox_to_state_parameter(self.CameraExposureTimeSpinbox,'camera_exposure_time',1000)
        self.connect_spinbox_to_state_parameter(self.CameraLineIntervalSpinbox,'camera_line_interval',1000000)

        ''' Connecting laser waveform controls '''
        self.connect_spinbox_to_state_parameter(self.SweeptimeSpinBox,'sweeptime',1000)
        self.connect_spinbox_to_state_parameter(self.LeftLaserPulseDelaySpinBox,'laser_l_delay_%')
        self.connect_spinbox_to_state_parameter(self.RightLaserPulseDelaySpinBox,'laser_r_delay_%')
        self.connect_spinbox_to_state_parameter(self.LeftLaserPulseLengthSpinBox,'laser_l_pulse_%')
        self.connect_spinbox_to_state_parameter(self.RightLaserPulseLengthSpinBox,'laser_r_pulse_%')
        self.connect_spinbox_to_state_parameter(self.LeftLaserPulseMaxAmplitudeSpinBox,'laser_l_max_amplitude_%')
        self.connect_spinbox_to_state_parameter(self.RightLaserPulseMaxAmplitudeSpinBox,'laser_r_max_amplitude_%')

        ''' Connecting Galvo controls '''
        self.connect_spinbox_to_state_parameter(self.GalvoFrequencySpinBox,'galvo_r_frequency')
        self.connect_spinbox_to_state_parameter(self.GalvoFrequencySpinBox,'galvo_l_frequency')
        self.connect_spinbox_to_state_parameter(self.LeftGalvoAmplitudeSpinBox,'galvo_l_amplitude')
        self.connect_spinbox_to_state_parameter(self.LeftGalvoAmplitudeSpinBox,'galvo_r_amplitude')
        self.connect_spinbox_to_state_parameter(self.LeftGalvoPhaseSpinBox,'galvo_l_phase')
        self.connect_spinbox_to_state_parameter(self.RightGalvoPhaseSpinBox,'galvo_r_phase')

        ''' Connecting ETL controls '''
        self.connect_spinbox_to_state_parameter(self.LeftETLOffsetSpinBox,'etl_l_offset')
        self.connect_spinbox_to_state_parameter(self.RightETLOffsetSpinBox,'etl_r_offset')
        self.connect_spinbox_to_state_parameter(self.LeftETLAmplitudeSpinBox,'etl_l_amplitude')
        self.connect_spinbox_to_state_parameter(self.RightETLAmplitudeSpinBox,'etl_r_amplitude')
        self.connect_spinbox_to_state_parameter(self.LeftETLDelaySpinBox,'etl_l_delay_%')
        self.connect_spinbox_to_state_parameter(self.RightETLDelaySpinBox,'etl_r_delay_%')
        self.connect_spinbox_to_state_parameter(self.LeftETLRampRisingSpinBox,'etl_l_ramp_rising_%')
        self.connect_spinbox_to_state_parameter(self.RightETLRampRisingSpinBox, 'etl_r_ramp_rising_%')
        self.connect_spinbox_to_state_parameter(self.LeftETLRampFallingSpinBox, 'etl_l_ramp_falling_%')
        self.connect_spinbox_to_state_parameter(self.RightETLRampFallingSpinBox, 'etl_r_ramp_falling_%')

        '''
        LeftLaserPulseDelaySpinBox
        RightLaserPulseDelaySpinBox
        LeftLaserPulseLengthSpinBox
        RightLaserPulseLengthSpinBox
        LeftLaserPulseMaxAmplitude
        RightLaserPulseMaxAmplitude

        GalvoFrequencySpinBox
        LeftGalvoOffsetSpinbox
        RightGalvoOffsetSpinbox

        LeftGalvoAmplitudeSpinBox
        LeftGalvoPhaseSpinBox
        RightGalvoPhaseSpinBox

        LeftETLDelaySpinBox
        RightETLDelaySpinBox
        LeftETLRampRisingSpinbox
        RightETLRampRisingSpinbox
        LeftETLRampFallingSpinBox
        RightETLRampFallingSpinBox

        LeftETLOffsetSpinBox
        RightETLOffsetSpinBox
        LeftETLAmplitudeSpinBox
        RightETLAmplitudeSpinBox
        '''

    def connect_combobox_to_state_parameter(self, combobox, option_list, state_parameter):
        '''
        Helper method to connect and initialize a combobox from the config

        Args:
            combobox (QtWidgets.QComboBox): Combobox in the GUI to be connected
            option_list (list): List of selection options
            state_parameter (str): State parameter (has to exist in the config)
        '''
        combobox.addItems(option_list)
        combobox.currentTextChanged.connect(lambda currentText: self.sig_state_request.emit({state_parameter : currentText}))
        combobox.setCurrentText(self.cfg.startup[state_parameter])

    def connect_spinbox_to_state_parameter(self, spinbox, state_parameter, conversion_factor=1):
        '''
        Helper method to connect and initialize a spinbox from the config

        Args:
            spinbox (QtWidgets.QSpinBox or QtWidgets.QDoubleSpinbox): Spinbox in
                    the GUI to be connected
            state_parameter (str): State parameter (has to exist in the config)
            conversion_factor (float): Conversion factor. If the config is in
                                       seconds, the spinbox displays ms:
                                       conversion_factor = 1000. If the config is
                                       in seconds and the spinbox displays
                                       microseconds: conversion_factor = 1000000
        '''
        spinbox.valueChanged.connect(lambda currentValue: self.sig_state_request.emit({state_parameter : currentValue/conversion_factor}))
        spinbox.setValue(self.cfg.startup[state_parameter]*conversion_factor)

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        #self.enable_external_gui_updates = True
        #self.block_signals_from_controls(True)
        self.sig_execute_script.emit(script)

    def block_signals_from_controls(self, bool):
        self.FilterComboBox.blockSignals(bool)
        self.ZoomComboBox.blockSignals(bool)
        self.ShutterComboBox.blockSignals(bool)
        self.LaserComboBox.blockSignals(bool)
        self.LaserIntensitySlider.blockSignals(bool)
        self.CameraExposureTimeSpinbox.blockSignals(bool)
        self.CameraLineIntervalSpinbox.blockSignals(bool)

    def update_gui_from_state(self):
           
        self.block_signals_from_controls(True)
        with QtCore.QMutexLocker(self.state_model_mutex):
            self.FilterComboBox.setCurrentText(self.state_model.state['filter'])
            self.ZoomComboBox.setCurrentText(self.state_model.state['zoom'])
            self.ShutterComboBox.setCurrentText(self.state_model.state['shutterconfig'])
            self.LaserComboBox.setCurrentText(self.state_model.state['laser'])
            self.LaserIntensitySlider.setValue(self.state_model.state['intensity'])
            self.CameraExposureTimeSpinbox.setValue(self.state_model.state['camera_exposure_time'])
            self.CameraLineIntervalSpinbox.setValue(self.state_model.state['camera_line_interval'])
        self.block_signals_from_controls(False)
        

    def live(self):
        print('Going live')
        self.sig_state_request.emit({'state':'live'})

    def disable_gui(self):
        pass

    def enable_gui(self):
        self.enable_external_gui_updates = False
        self.block_signals_from_controls(False)
