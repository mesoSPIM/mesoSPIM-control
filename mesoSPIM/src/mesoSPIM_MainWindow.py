# mesoSPIM MainWindow
import tifffile
import logging
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from PyQt5.uic import loadUi

''' Disabled taskbar button progress display due to problems with Anaconda default'''
# if sys.platform == 'win32':
#     from PyQt5.QtWinExtras import QWinTaskbarButton

from .mesoSPIM_CameraWindow import mesoSPIM_CameraWindow
from .mesoSPIM_AcquisitionManagerWindow import mesoSPIM_AcquisitionManagerWindow
from .mesoSPIM_Optimizer import mesoSPIM_Optimizer
from .WebcamWindow import WebcamWindow
from .mesoSPIM_ContrastWindow import mesoSPIM_ContrastWindow
from .mesoSPIM_ScriptWindow import mesoSPIM_ScriptWindow # do not delete this line, it is actually used in exec()
from .mesoSPIM_TileViewWindow import mesoSPIM_TileViewWindow
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .mesoSPIM_Core import mesoSPIM_Core
from .devices.joysticks.mesoSPIM_JoystickHandlers import mesoSPIM_JoystickHandler

logger = logging.getLogger(__name__)


class LogDisplayHandler(QtCore.QObject, logging.Handler):
    """ Handler class to display log in a TextDisplay widget. A thread-safe version, callable from non-GUI threads."""
    new_record = QtCore.pyqtSignal(object)

    def __init__(self, parent):
        super().__init__(parent)
        super(logging.Handler).__init__()
        formatter = Formatter('%(levelname)s:%(module)s:%(funcName)s:%(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.new_record.emit(msg)  # <---- emit signal here


class Formatter(logging.Formatter):
    """ Formatter of the LogDisplayHandler class."""
    def formatException(self, ei):
        result = super(Formatter, self).formatException(ei)
        return result

    def format(self, record):
        s = super(Formatter, self).format(record)
        if record.exc_text:
            s = s.replace('\n', '')
        return s


class mesoSPIM_MainWindow(QtWidgets.QMainWindow):
    """ Main application window which instantiates worker objects and moves them to a thread. """
    # sig_live = QtCore.pyqtSignal()
    sig_stop = QtCore.pyqtSignal()
    sig_finished = QtCore.pyqtSignal()
    sig_enable_gui = QtCore.pyqtSignal(bool)
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_execute_script = QtCore.pyqtSignal(str)
    sig_move_relative = QtCore.pyqtSignal(dict)
    sig_move_absolute = QtCore.pyqtSignal(dict)
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()
    sig_center_sample = QtCore.pyqtSignal()

    sig_save_etl_config = QtCore.pyqtSignal()
    sig_poke_demo_thread = QtCore.pyqtSignal()
    sig_launch_optimizer = QtCore.pyqtSignal(dict)
    sig_launch_contrast_window = QtCore.pyqtSignal()

    def __init__(self, package_directory, config, title="mesoSPIM Main Window"):
        super().__init__()
        # Initial housekeeping
        self.cfg = config
        self.package_directory = package_directory
        self.script_window_counter = 0
        self.update_gui_from_state_flag = False

        # Instantiate the one and only mesoSPIM state '''
        self.state = mesoSPIM_StateSingleton()
        self.state.sig_updated.connect(self.update_gui_from_state)
        self.state['package_directory'] = package_directory

        # Setting up the user interface windows
        loadUi(self.package_directory + '/gui/mesoSPIM_MainWindow.ui', self)
        self.setWindowTitle(title)

        # Connect log display widget
        self.log_display_handler = LogDisplayHandler(self)
        self.log_display_handler.new_record.connect(self.LogTextDisplay.appendPlainText)

        self.camera_window = mesoSPIM_CameraWindow(self)
        self.camera_window.show()

        self.acquisition_manager_window = mesoSPIM_AcquisitionManagerWindow(self)
        self.acquisition_manager_window.show()

        self.tile_view_window = mesoSPIM_TileViewWindow(self)
        self.tile_view_window.show()

        self.webcam_window = None
        self.check_config_file()
        self.open_webcam_window()

        # arrange the windows on the screen, tiled
        if hasattr(self.cfg, 'ui_options') and 'window_pos' in self.cfg.ui_options.keys():
            window_pos = self.cfg.ui_options['window_pos']
        else:
            window_pos = (100, 100)
        self.move(window_pos[0], window_pos[1])
        self.camera_window.move(window_pos[0] + self.width() + 50, window_pos[1])
        self.tile_view_window.move(window_pos[0] + self.width() + self.camera_window.width() + 2*50, window_pos[1])
        self.acquisition_manager_window.move(window_pos[0], window_pos[1] + self.height() + 50)
        if self.webcam_window:
            self.webcam_window.move(window_pos[0] + self.width() + self.camera_window.width() + 2*50, window_pos[1] + self.height())

        # set up some Acq manager signals
        self.acquisition_manager_window.sig_warning.connect(self.display_warning)
        self.acquisition_manager_window.sig_move_absolute.connect(self.sig_move_absolute.emit)

        # Setting up the threads
        logger.debug('Ideal thread count: '+str(int(QtCore.QThread.idealThreadCount())))
        self.core_thread = QtCore.QThread()
        # Entry point: Work on thread affinity here
        self.core = mesoSPIM_Core(self.cfg, self)

        self.core.moveToThread(self.core_thread)
        self.core.waveformer.moveToThread(self.core_thread)
        self.core.serial_worker.moveToThread(self.core_thread) # does not really affect the thread affinity, todo
        self.core.serial_worker.stage.moveToThread(self.core_thread)

        # Get buttons & connections ready
        self.initialize_and_connect_menubar()
        self.initialize_and_connect_widgets()

        # launch ETL menu
        self.choose_etl_config()

        # Widget list for blockSignals during status updates
        self.widgets_to_block = []
        self.parent_widgets_to_block = [self.ETLTabWidget, self.ParameterTabWidget, self.ControlGroupBox]
        self.create_widget_list(self.parent_widgets_to_block, self.widgets_to_block)

        # The signal switchboard, Core -> MainWindow
        # Memo: with type=QtCore.Qt.DirectConnection the slot is invoked immediately when the signal is emitted. The slot is executed in the signalling thread (Core).
        self.core.sig_finished.connect(self.finished)
        self.core.sig_position.connect(self.update_position_indicators)
        self.core.sig_update_gui_from_state.connect(self.enable_gui_updates_from_state)
        self.core.sig_status_message.connect(self.display_status_message)
        self.core.sig_progress.connect(self.update_progressbars)
        self.core.sig_warning.connect(self.display_warning)

        self.sig_move_absolute.connect(self.core.move_absolute, type=QtCore.Qt.QueuedConnection)
        # Set stages, revolver, filter to initialization positions defined in the config file:
        #self.sig_move_to_ini_position.connect(self.core.move_to_initial_positions, type=QtCore.Qt.QueuedConnection)

        self.optimizer = None
        self.contrast_window = None

        # The signal switchboard, MainWindow -> Core
        self.sig_launch_optimizer.connect(self.launch_optimizer)
        self.sig_launch_contrast_window.connect(self.launch_contrast_window)

        ''' Start the thread '''
        self.core_thread.start(QtCore.QThread.HighPriority)

        try:
            self.thread().setPriority(QtCore.QThread.HighestPriority)
            logger.debug('Main Window Thread priority: '+str(self.thread().priority()))
        except:
            logger.error(f'Main Window: Printing Thread priority failed.')

        logger.debug(f'Main Window: Core thread priority: {self.core_thread.priority()}')

        self.joystick = mesoSPIM_JoystickHandler(self)
        self.enable_gui_updates_from_state(False)

    def check_config_file(self):
        """Checks missing blocks in config file and gives suggestions.
        Todo: all new config options
        """
        gen_msg = "You are using outdated config file, check project github with the most recent template (demo_config.py):"
        if not hasattr(self.cfg, 'ui_options'):
            spec_msg = "\n - 'ui_options' is missing"
            logger.info(gen_msg + spec_msg)
            print(gen_msg + spec_msg)
        else:
            if not ('button_sleep_ms_xyzft' in self.cfg.ui_options.keys()):
                spec_msg = "\n - 'button_sleep_ms_xyzft' is missing"
                logger.info(gen_msg + spec_msg)
                print(gen_msg + spec_msg)

        if not hasattr(self.cfg, 'scale_galvo_amp_with_zoom'):
            print("INFO: Config file: parameter 'scale_galvo_amp_with_zoom' (True, False) is missing. Default is False.")
            self.state['galvo_amp_scale_w_zoom'] = False
        else:
            self.state['galvo_amp_scale_w_zoom'] = self.cfg.scale_galvo_amp_with_zoom
        self.checkBoxScaleWZoom.setChecked(self.state['galvo_amp_scale_w_zoom'])

        if 'f_objective_exchange' in self.cfg.stage_parameters.keys():
            msg = f"Objective exchange in f-position {self.cfg.stage_parameters['f_objective_exchange']} ('f_objective_exchange' in stage parameters of the config file)."
            if self.cfg.stage_parameters['f_min'] <= self.cfg.stage_parameters['f_objective_exchange'] <= self.cfg.stage_parameters['f_max']:
                pass
            else:
                msg = "ERROR: 'f_objective_exchange' is not within the allowed range of 'f_min' and 'f_max'"
                logger.error(msg), print(msg)
        else:
            msg = "Objective exchange in the current f-position. To set the safe f-position for objective exchange, add 'f_objective_exchange' to the stage parameters in the config file."
        logger.warning(msg)
        print(msg)

    def open_webcam_window(self):
        """Open USB webcam window using cam ID specified in config file."""
        if self.webcam_window is None: # first call
            if hasattr(self.cfg, 'ui_options') and ('usb_webcam_ID' in self.cfg.ui_options.keys()):
                self.webcam_window = WebcamWindow(self.cfg.ui_options['usb_webcam_ID'])
            else: # create a dummy 
                self.webcam_window = WebcamWindow(None)
        else: # open previously closed window
            self.webcam_window.show()

    def open_tile_view_window(self):
        self.tile_view_window.show()


    def __del__(self):
        """Cleans the threads up after deletion, waits until the threads
        have truly finished their life.

        Make sure to keep this up to date with the number of threads
        """
        try:
            self.core_thread.quit()
            self.core_thread.wait()
        except:
            pass

    def close_app(self):
        self.camera_window.close()
        self.acquisition_manager_window.close()
        if self.optimizer:
            self.optimizer.close()
        try:
            self.webcam_window.close()
        except:
            pass
        if self.contrast_window:
            self.contrast_window.close()
        self.tile_view_window.close()
        self.close()

    def open_tiff(self):
        """Open and display a TIFF file (stack), eg for demo and debugging purposes."""
        tiff_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, 'Open TIFF', "./", "TIFF files (*tif; *tiff)")
        if tiff_path:
            try:
                stack = tifffile.imread(tiff_path)
                self.camera_window.set_image(stack)
                logger.info(f"Loaded TIFF file from {tiff_path}, dimensions {stack.shape}")
            except Exception as e:
                logger.exception(f"{e}")
        else:
            logger.info(f"Loaded TIFF file path is None")

    def get_state_parameter(self, state_parameter):
        return self.state[state_parameter]

    def check_instances(self, widget):
        ''' 
        Method to check whether a widget belongs to one of the Qt Classes specified.

        Args:
            widget (QtWidgets.QWidget): Widget to check 

        Returns:
            return_value (bool): True if widget is in the list, False if not.
        '''
        if isinstance(widget, (QtWidgets.QSpinBox, 
                                QtWidgets.QDoubleSpinBox,
                                QtWidgets.QSlider,
                                QtWidgets.QComboBox,
                                QtWidgets.QPushButton)):
            return True 
        else:
            return False

    def create_widget_list(self, list, widget_list):
        """
        Helper method to recursively loop through all the widgets in a list and their children.
        Args:
            list (list): List of QtWidgets.QWidget objects
        """
        for widget in list:
            if list != ([] or None):
                if self.check_instances(widget):
                    # print(widget.objectName())
                    widget_list.append(widget)
                list = widget.children()
                self.create_widget_list(list, widget_list)
            else:
                return None

    @QtCore.pyqtSlot(str)
    def display_status_message(self, string):
        """
        Displays a message in the status bar for a time in ms
        """
        self.statusBar().showMessage(string)

    def pos2str(self, position):
        """ Little helper method for converting positions to strings """
        return '%.1f' % position

    @QtCore.pyqtSlot(dict)
    def update_position_indicators(self, dict):
        for key, pos_dict in dict.items():
            if key == 'position':
                self.x_position, self.y_position, self.z_position = pos_dict['x_pos'], pos_dict['y_pos'], pos_dict['z_pos']
                self.f_position, self.theta_position = pos_dict['f_pos'], pos_dict['theta_pos']
                self.X_Position_Indicator.setText(self.pos2str(self.x_position)+' µm')
                self.Y_Position_Indicator.setText(self.pos2str(self.y_position)+' µm')
                self.Z_Position_Indicator.setText(self.pos2str(self.z_position)+' µm')
                self.Focus_Position_Indicator.setText(self.pos2str(self.f_position)+' µm')
                self.Rotation_Position_Indicator.setText(self.pos2str(self.theta_position)+'°')
                #self.state['position'] = dict['position'] # this must be done in the core thread

    @QtCore.pyqtSlot(dict)
    def update_progressbars(self,dict):
        cur_acq = dict['current_acq']
        tot_acqs = dict['total_acqs']
        cur_image = dict['current_image_in_acq']
        images_in_acq = dict['images_in_acq']
        tot_images = dict['total_image_count']
        image_count = dict['image_counter']
        time_passed_string = dict['time_passed_string']
        remaining_time_string = dict['remaining_time_string']
        fps = self.state['current_framerate']

        self.AcquisitionProgressBar.setValue(int((cur_image+1)/images_in_acq*100))
        self.TotalProgressBar.setValue(int((image_count+1)/tot_images*100))

        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setValue(int((image_count+1)/tot_images*100))
        '''

        self.AcquisitionProgressBar.setFormat('%p% Image: '+ str(cur_image+1) + '/' + str(images_in_acq) + '  FPS: ' + '{:.1f}'.format(fps))
        self.TotalProgressBar.setFormat('%p% Acq: '+ str(cur_acq+1) +\
                                        '/' + str(tot_acqs) +\
                                         ' ' + ' Image: '+ str(image_count) +\
                                        '/' + str(tot_images) + ' ' +\
                                            'Time: ' + time_passed_string + \
                                            ' Remaining: ' + remaining_time_string)

    def create_script_window(self):
        """
        Creates a script window and binds it to a self.scriptwindow0 ... n instanceself.

        This happens dynamically using exec which should be replaced at
        some point with a factory pattern.
        """
        windowstring = 'self.scriptwindow'+str(self.script_window_counter)
        exec(windowstring+ '= mesoSPIM_ScriptWindow(self)')
        exec(windowstring+'.setWindowTitle("Script Window #'+str(self.script_window_counter)+'")')
        exec(windowstring+'.show()')
        exec(windowstring+'.sig_execute_script.connect(self.execute_script)')
        self.script_window_counter += 1

    def initialize_and_connect_menubar(self):
        self.actionExit.triggered.connect(self.close_app)
        self.actionOpen_TIFF.triggered.connect(self.open_tiff)
        self.actionOpen_Camera_Window.triggered.connect(self.camera_window.show)
        self.actionOpen_Webcam_Window.triggered.connect(self.open_webcam_window)
        self.actionOpen_Acquisition_Manager.triggered.connect(self.acquisition_manager_window.show)
        self.actionOpen_Tile_Overview.triggered.connect(self.tile_view_window.show)
        self.actionCascade_windows.triggered.connect(self.cascade_all_windows)

    def initialize_and_connect_widgets(self):
        """ Connecting the menu actions """
        self.openScriptEditorButton.clicked.connect(self.create_script_window)

        ''' Connecting the movement & zero buttons '''
        if 'flip_XYZFT_button_polarity' in self.cfg.ui_options.keys():
            x_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][0] else 1
            y_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][1] else 1
            z_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][2] else 1
            f_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][3] else 1
            t_sign = -1 if self.cfg.ui_options['flip_XYZFT_button_polarity'][4] else 1
        else:
            logger.warning('flip_XYZFT_button_polarity key not found in config file. Assuming all buttons are positive.')
        self.xPlusButton.pressed.connect(lambda: self.move_relative({'x_rel': - x_sign*self.xyzIncrementSpinbox.value()}))
        self.xMinusButton.pressed.connect(lambda: self.move_relative({'x_rel': x_sign*self.xyzIncrementSpinbox.value()}))
        self.yPlusButton.pressed.connect(lambda: self.move_relative({'y_rel': y_sign*self.xyzIncrementSpinbox.value()}))
        self.yMinusButton.pressed.connect(lambda: self.move_relative({'y_rel': - y_sign*self.xyzIncrementSpinbox.value()}))
        self.zPlusButton.pressed.connect(lambda: self.move_relative({'z_rel': z_sign*self.xyzIncrementSpinbox.value()}))
        self.zMinusButton.pressed.connect(lambda: self.move_relative({'z_rel': - z_sign*self.xyzIncrementSpinbox.value()}))
        self.focusPlusButton.pressed.connect(lambda: self.move_relative({'f_rel': f_sign*self.focusIncrementSpinbox.value()}))
        self.focusMinusButton.pressed.connect(lambda: self.move_relative({'f_rel': - f_sign*self.focusIncrementSpinbox.value()}))
        self.rotPlusButton.pressed.connect(lambda: self.move_relative({'theta_rel': t_sign*self.rotIncrementSpinbox.value()}))
        self.rotMinusButton.pressed.connect(lambda: self.move_relative({'theta_rel': - t_sign*self.rotIncrementSpinbox.value()}))

        self.xyzrotStopButton.pressed.connect(self.sig_stop_movement.emit)

        self.xyZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['x','y']) if bool is True else self.sig_unzero_axes.emit(['x','y']))
        self.zZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['z']) if bool is True else self.sig_unzero_axes.emit(['z']))
        self.focusZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['f']) if bool is True else self.sig_unzero_axes.emit(['f']))
        self.focusAutoButton.clicked.connect(lambda: self.sig_launch_optimizer.emit({'mode': 'focus', 'amplitude': 300}))
        self.rotZeroButton.clicked.connect(lambda bool: self.sig_zero_axes.emit(['theta']) if bool is True else self.sig_unzero_axes.emit(['theta']))
        self.xyzLoadButton.clicked.connect(self.sig_load_sample.emit)
        self.xyzUnloadButton.clicked.connect(self.sig_unload_sample.emit)
        self.centerButton.clicked.connect(self.sig_center_sample.emit)
        self.launchOptimizerButton.clicked.connect(lambda: self.sig_launch_optimizer.emit({'mode': 'etl_offset', 'amplitude': 0.5}))
        self.ContrastWindowButton.clicked.connect(lambda: self.sig_launch_contrast_window.emit())

        ''' Disabling UI buttons if necessary '''
        if hasattr(self.cfg, 'ui_options'):
            if self.cfg.ui_options['enable_x_buttons'] is False:
                self.enable_move_buttons('x', False)

            if self.cfg.ui_options['enable_y_buttons'] is False:
                self.enable_move_buttons('y', False)

            if self.cfg.ui_options['enable_x_buttons'] is False and self.cfg.ui_options['enable_y_buttons'] is False:
                self.xyZeroButton.setEnabled(False)

            if self.cfg.ui_options['enable_z_buttons'] is False:
                self.enable_move_buttons('z', False)
                self.zZeroButton.setEnabled(False)

            if self.cfg.ui_options['enable_f_buttons'] is False:
                self.enable_move_buttons('f', False)
                self.focusZeroButton.setEnabled(False)

            if 'enable_f_zero_button' in self.cfg.ui_options.keys():
                self.focusZeroButton.setEnabled(self.cfg.ui_options['enable_f_zero_button'])

            if self.cfg.ui_options['enable_rotation_buttons'] is False:
                self.enable_move_buttons('theta', False)
                self.rotZeroButton.setEnabled(False)

            if self.cfg.ui_options['enable_loading_buttons'] is False:
                self.xyzLoadButton.setEnabled(False)
                self.xyzUnloadButton.setEnabled(False)

        ''' Connecting state-changing buttons '''
        self.LiveButton.clicked.connect(self.run_live)
        self.SnapButton.clicked.connect(self.run_snap)
        self.RunSelectedAcquisitionButton.clicked.connect(self.run_selected_acquisition)
        self.RunAcquisitionListButton.clicked.connect(self.run_acquisition_list)
        self.StopButton.clicked.connect(lambda: self.sig_state_request.emit({'state':'idle'}))
        #self.StopButton.clicked.connect(lambda: print('Stopping'))
        self.LightsheetSwitchingModeButton.clicked.connect(self.run_lightsheet_alignment_mode)
        self.VisualModeButton.clicked.connect(self.run_visual_mode)

        self.ETLIncrementSpinBox.valueChanged.connect(self.update_etl_increments)
        self.ZeroLeftETLButton.toggled.connect(self.zero_left_etl)
        self.ZeroRightETLButton.toggled.connect(self.zero_right_etl)
        self.freezeGalvoButton.toggled.connect(self.zero_galvo_amp)

        self.ChooseETLcfgButton.clicked.connect(self.choose_etl_config)
        self.SaveETLParametersButton.clicked.connect(self.save_etl_config)

        self.ChooseSnapFolderButton.clicked.connect(self.choose_snap_folder)
        self.SnapFolderIndicator.setText(self.state['snap_folder'])
        self.ETLconfigIndicator.setText(self.state['ETL_cfg_file'])

        self.ShutterComboBox.currentIndexChanged.connect(self.update_GUI_by_shutter_state)

        self.widget_to_state_parameter_assignment=(
            (self.FilterComboBox, 'filter',1),
            (self.FilterComboBox, 'filter',1),
            (self.ZoomComboBox, 'zoom',1),
            (self.ShutterComboBox, 'shutterconfig',1),
            (self.LaserComboBox, 'laser',1),
            (self.LaserIntensitySlider, 'intensity', 1),
            (self.LaserIntensitySpinBox, 'intensity', 1),
            (self.CameraExposureTimeSpinBox, 'camera_exposure_time',1000),
            #(self.CameraLineIntervalSpinBox,'camera_line_interval',1000000),
            (self.CameraTriggerDelaySpinBox,'camera_delay_%',1),
            (self.CameraTriggerPulseLengthSpinBox, 'camera_pulse_%',1),
            (self.SweeptimeSpinBox,'sweeptime',1000),
            (self.LeftLaserPulseDelaySpinBox,'laser_l_delay_%',1),
            (self.RightLaserPulseDelaySpinBox,'laser_r_delay_%',1),
            (self.LeftLaserPulseLengthSpinBox,'laser_l_pulse_%',1),
            (self.RightLaserPulseLengthSpinBox,'laser_r_pulse_%',1),
            (self.LeftLaserPulseMaxAmplitudeSpinBox,'laser_l_max_amplitude_%',1),
            (self.RightLaserPulseMaxAmplitudeSpinBox,'laser_r_max_amplitude_%',1),
            (self.GalvoFrequencySpinBox,'galvo_r_frequency',1),
            (self.GalvoFrequencySpinBox,'galvo_l_frequency',1),
            (self.LeftGalvoAmplitudeSpinBox,'galvo_l_amplitude',1),
            (self.LeftGalvoAmplitudeSpinBox,'galvo_r_amplitude',1),
            (self.LeftGalvoPhaseSpinBox,'galvo_l_phase',1),
            (self.RightGalvoPhaseSpinBox,'galvo_r_phase',1),
            (self.LeftGalvoOffsetSpinBox, 'galvo_l_offset',1),
            (self.RightGalvoOffsetSpinBox, 'galvo_r_offset',1),
            (self.LeftETLOffsetSpinBox,'etl_l_offset',1),
            (self.RightETLOffsetSpinBox,'etl_r_offset',1),
            (self.LeftETLAmplitudeSpinBox,'etl_l_amplitude',1),
            (self.RightETLAmplitudeSpinBox,'etl_r_amplitude',1),
            (self.LeftETLDelaySpinBox,'etl_l_delay_%',1),
            (self.RightETLDelaySpinBox,'etl_r_delay_%',1),
            (self.LeftETLRampRisingSpinBox,'etl_l_ramp_rising_%',1),
            (self.RightETLRampRisingSpinBox, 'etl_r_ramp_rising_%',1),
            (self.LeftETLRampFallingSpinBox, 'etl_l_ramp_falling_%',1),
            (self.RightETLRampFallingSpinBox, 'etl_r_ramp_falling_%',1),
        )

        for widget, state_parameter, conversion_factor in self.widget_to_state_parameter_assignment:
            self.connect_widget_to_state_parameter(widget, state_parameter, conversion_factor)

        ''' Connecting the microscope controls '''

        ''' List for subsampling factors - comboboxes need a list of strings'''
        subsampling_list = [str(i) for i in self.cfg.camera_parameters['subsampling']]

        self.connect_combobox_to_state_parameter(self.FilterComboBox,self.cfg.filterdict.keys(),'filter')
        self.connect_combobox_to_state_parameter(self.ZoomComboBox,self.cfg.zoomdict.keys(),'zoom')
        self.connect_combobox_to_state_parameter(self.ShutterComboBox,self.cfg.shutteroptions,'shutterconfig')
        self.connect_combobox_to_state_parameter(self.LaserComboBox,self.cfg.laserdict.keys(),'laser')
        # self.connect_combobox_to_state_parameter(self.CameraSensorModeComboBox,['ASLM','Area'],'camera_sensor_mode')
        self.connect_combobox_to_state_parameter(self.LiveSubSamplingComboBox,subsampling_list,'camera_display_live_subsampling', int_conversion = True)
        self.connect_combobox_to_state_parameter(self.AcquisitionSubSamplingComboBox,subsampling_list,'camera_display_acquisition_subsampling', int_conversion = True)
        # self.connect_combobox_to_state_parameter(self.CameraSensorModeComboBox,['ASLM','Area'],'camera_sensor_mode')
        self.connect_combobox_to_state_parameter(self.BinningComboBox, self.cfg.binning_dict.keys(),'camera_binning')

        self.checkBoxScaleWZoom.stateChanged.connect(self.scale_galvo_amp_w_zoom)
        self.LaserIntensitySlider.valueChanged.connect(self.set_laser_intensity)
        self.LaserIntensitySpinBox.valueChanged.connect(self.set_laser_intensity)
        self.LaserIntensitySlider.setValue(self.cfg.startup['intensity'])

    def enable_move_buttons(self, axis='x', state=True):
        if axis == 'x':
            self.xPlusButton.setEnabled(state)
            self.xMinusButton.setEnabled(state)
        elif axis == 'y':
            self.yPlusButton.setEnabled(state)
            self.yMinusButton.setEnabled(state)
        elif axis == 'z':
            self.zPlusButton.setEnabled(state)
            self.zMinusButton.setEnabled(state)
        elif axis == 'f':
            self.focusPlusButton.setEnabled(state)
            self.focusMinusButton.setEnabled(state)
        elif axis == 'theta':
            self.rotPlusButton.setEnabled(state)
            self.rotMinusButton.setEnabled(state)
        else:
            raise ValueError(f'axis = {axis} is unknown.')

    @QtCore.pyqtSlot(dict)
    def move_relative(self, pos_dict):
        assert len(pos_dict) == 1, f"Position dictionary expects only one entry, got {pos_dict}"
        key, value = list(pos_dict.keys())[0], list(pos_dict.values())[0]
        self.sig_move_relative.emit(pos_dict)
        if hasattr(self.cfg, 'ui_options') and ('button_sleep_ms_xyzft' in self.cfg.ui_options.keys()):
            axis = key[:-4]
            index = ['x', 'y', 'z', 'f', 'theta'].index(axis)
            sleep_ms = self.cfg.ui_options['button_sleep_ms_xyzft'][index]
            if sleep_ms > 0:
                self.enable_move_buttons(axis, False)
                QtCore.QTimer().singleShot(sleep_ms, lambda: self.enable_move_buttons(axis, True))
            else:
                pass

    @QtCore.pyqtSlot(int)
    def set_laser_intensity(self, value):
        self.sig_state_request.emit({'intensity': value})
        self.LaserIntensitySlider.setValue(value)
        self.LaserIntensitySpinBox.setValue(value)

    @QtCore.pyqtSlot()
    def scale_galvo_amp_w_zoom(self):
        self.state['galvo_amp_scale_w_zoom'] = self.checkBoxScaleWZoom.isChecked()

    @QtCore.pyqtSlot()
    def update_GUI_by_shutter_state(self):
        ''' Disables controls for the opposite ETL to avoid overriding parameters '''
        if self.ShutterComboBox.currentText() == 'Left':
            self.LeftETLOffsetSpinBox.setEnabled(True)
            self.LeftETLAmplitudeSpinBox.setEnabled(True)
            self.ZeroLeftETLButton.setEnabled(True)
            self.RightETLOffsetSpinBox.setEnabled(False)
            self.RightETLAmplitudeSpinBox.setEnabled(False)
            self.ZeroRightETLButton.setEnabled(False)
        elif self.ShutterComboBox.currentText() == 'Right':
            self.RightETLOffsetSpinBox.setEnabled(True)
            self.RightETLAmplitudeSpinBox.setEnabled(True)
            self.ZeroRightETLButton.setEnabled(True)
            self.LeftETLOffsetSpinBox.setEnabled(False)
            self.LeftETLAmplitudeSpinBox.setEnabled(False)
            self.ZeroLeftETLButton.setEnabled(False)
        else: # In case of "Both" (or if something completely different is in the config file)
            self.RightETLOffsetSpinBox.setEnabled(True)
            self.RightETLAmplitudeSpinBox.setEnabled(True)
            self.ZeroRightETLButton.setEnabled(True)
            self.LeftETLOffsetSpinBox.setEnabled(True)
            self.LeftETLAmplitudeSpinBox.setEnabled(True)
            self.ZeroLeftETLButton.setEnabled(True)

    def connect_widget_to_state_parameter(self, widget, state_parameter, conversion_factor):
        '''
        Helper method to (currently) connect spinboxes
        '''
        if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            self.connect_spinbox_to_state_parameter(widget, state_parameter, conversion_factor)

    def connect_combobox_to_state_parameter(self, combobox, option_list, state_parameter, int_conversion = False):
        '''
        Helper method to connect and initialize a combobox from the config

        Args:
            combobox (QtWidgets.QComboBox): Combobox in the GUI to be connected
            option_list (list): List of selection options
            state_parameter (str): State parameter (has to exist in the config)
        '''
        combobox.addItems(option_list)
        if not int_conversion:
            self.sig_state_request.emit({state_parameter: self.cfg.startup[state_parameter]})  # force update of the state
            combobox.setCurrentText(self.cfg.startup[state_parameter])
            combobox.currentTextChanged.connect(lambda currentText: self.sig_state_request.emit({state_parameter : currentText}), type=QtCore.Qt.QueuedConnection) # Execute in the Core (receiver) thread

        else:
            self.sig_state_request.emit({state_parameter: int(self.cfg.startup[state_parameter])})  # force update of the state
            combobox.setCurrentText(str(self.cfg.startup[state_parameter]))
            combobox.currentTextChanged.connect(lambda currentParameter: self.sig_state_request.emit({state_parameter : int(currentParameter)}), type=QtCore.Qt.QueuedConnection) # Execute in the Core (receiver) thread


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
        spinbox.valueChanged.connect(lambda currentValue: self.sig_state_request.emit({state_parameter : currentValue/conversion_factor}), type=QtCore.Qt.QueuedConnection)
        spinbox.setValue(self.cfg.startup[state_parameter]*conversion_factor)

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.sig_execute_script.emit(script)

    def block_signals_from_controls(self, bool):
        '''
        Helper method to allow blocking of signals from all kinds of controls.

        Needs a list in self.widgets_to_block which has to be created during 
        mesoSPIM_MainWindow.__init__()
        
        Args:
            bool (bool): True if widgets are supposed to be blocked, False if unblocking is desired.
        '''
        for widget in self.widgets_to_block:
            widget.blockSignals(bool)

    def update_widget_from_state(self, widget, state_parameter_string, conversion_factor):
        if isinstance(widget, QtWidgets.QComboBox):
            widget.setCurrentText(self.state[state_parameter_string])
        elif isinstance(widget, (QtWidgets.QSlider,QtWidgets.QDoubleSpinBox,QtWidgets.QSpinBox)):
            widget.setValue(self.state[state_parameter_string]*conversion_factor)
    
    @QtCore.pyqtSlot()
    def update_gui_from_state(self):
        '''
        Updates the GUI controls after a state_change
        if the self.update_gui_from_state_flag is enabled.
        '''
        if self.update_gui_from_state_flag:
            self.block_signals_from_controls(True)
            for widget, state_parameter, conversion_factor in self.widget_to_state_parameter_assignment:
                self.update_widget_from_state(widget, state_parameter, conversion_factor)   
            self.acquisition_manager_window.set_selected_row(self.state['selected_row'])
            self.block_signals_from_controls(False)
            logger.debug('GUI updated from state')

    def run_snap(self):
        self.sig_state_request.emit({'state':'snap'})
        self.set_progressbars_to_busy()
        self.enable_mode_control_buttons(False)
        self.enable_stop_button(True)
        
    def run_live(self):
        self.sig_state_request.emit({'state':'live'})
        logger.debug('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))
        self.sig_poke_demo_thread.emit()
        self.set_progressbars_to_busy()
        self.enable_mode_control_buttons(False)
        self.enable_stop_button(True)

    def run_selected_acquisition(self):
        row = self.acquisition_manager_window.get_first_selected_row()

        if row is None:
            self.display_warning('No row selected - stopping!')
        else:
            # print('selected row:', row)
            self.state['selected_row'] = row
            self.sig_state_request.emit({'state':'run_selected_acquisition'})
            self.enable_mode_control_buttons(False)
            self.enable_gui_updates_from_state(True)
            self.enable_stop_button(True)
            self.enable_gui(False)
            ''' Disabled taskbar button progress display due to problems with Anaconda default
            if sys.platform == 'win32':
                self.win_taskbar_button.progress().setVisible(True)
            '''

    def run_acquisition_list(self):
        self.state['selected_row'] = -1
        self.sig_state_request.emit({'state':'run_acquisition_list'})
        self.enable_mode_control_buttons(False)
        self.enable_gui_updates_from_state(True)
        self.enable_stop_button(True)
        self.enable_gui(False)
        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setVisible(True)
        '''

    def run_lightsheet_alignment_mode(self):
        self.sig_state_request.emit({'state':'lightsheet_alignment_mode'})
        self.set_progressbars_to_busy()
        self.enable_mode_control_buttons(False)
        self.enable_stop_button(True)
        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setVisible(False)
        '''
    
    def run_visual_mode(self):
        self.sig_state_request.emit({'state':'visual_mode'})
        self.set_progressbars_to_busy()
        self.enable_mode_control_buttons(False)
        self.enable_stop_button(True)
        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setVisible(False)
        '''

    @QtCore.pyqtSlot(dict)
    def launch_optimizer(self, ini_dict=None):
        self.sig_move_relative.emit({'f_rel': 5})  # a hack to fix Galil stage coupling, between F and X/Y stages.
        time.sleep(0.1)
        self.sig_move_relative.emit({'f_rel': -5})  # a hack to fix Galil stage coupling, between F and X/Y stages.
        if not self.optimizer:
            self.optimizer = mesoSPIM_Optimizer(self)
            self.optimizer.set_parameters(ini_dict)
        else:
            self.optimizer.set_parameters(ini_dict)
            self.optimizer.show()

    @QtCore.pyqtSlot()
    def launch_contrast_window(self):
        if not self.contrast_window:
            self.contrast_window = mesoSPIM_ContrastWindow(self)
            self.core.camera_worker.sig_camera_frame.connect(self.contrast_window.set_image)
        else:
            self.contrast_window.active = True
            self.contrast_window.show()

    @QtCore.pyqtSlot(bool)
    def enable_gui_updates_from_state(self, boolean):
        self.update_gui_from_state_flag = boolean

    def enable_stop_button(self, boolean):
        self.StopButton.setEnabled(boolean)
    
    def enable_gui(self, boolean):
        self.TabWidget.setEnabled(boolean)
        self.ControlGroupBox.setEnabled(boolean)
        self.sig_enable_gui.emit(boolean)

    def enable_mode_control_buttons(self, boolean):
        self.LiveButton.setEnabled(boolean)
        self.SnapButton.setEnabled(boolean)
        self.RunSelectedAcquisitionButton.setEnabled(boolean)
        self.RunAcquisitionListButton.setEnabled(boolean)
        self.VisualModeButton.setEnabled(boolean)
        self.LightsheetSwitchingModeButton.setEnabled(boolean)

    def finished(self):
        self.enable_gui_updates_from_state(False)
        self.enable_stop_button(False)
        self.enable_mode_control_buttons(True)
        self.enable_gui(True)
        self.set_progressbars_to_standard()

    def set_progressbars_to_busy(self):
        '''If min and max of a progress bar are 0, it shows a "busy" indicator'''
        self.AcquisitionProgressBar.setMinimum(0)
        self.AcquisitionProgressBar.setMaximum(0)
        self.TotalProgressBar.setMinimum(0)
        self.TotalProgressBar.setMaximum(0)
        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setVisible(False)
        '''
    
    def set_progressbars_to_standard(self):
        self.AcquisitionProgressBar.setMinimum(0)
        self.AcquisitionProgressBar.setMaximum(100)
        self.TotalProgressBar.setMinimum(0)
        self.TotalProgressBar.setMaximum(100)
        ''' Disabled taskbar button progress display due to problems with Anaconda default
        if sys.platform == 'win32':
            self.win_taskbar_button.progress().setValue(0)
            self.win_taskbar_button.progress().setVisible(False)
        '''

    def update_etl_increments(self):
        increment = self.ETLIncrementSpinBox.value()

        self.LeftETLOffsetSpinBox.setSingleStep(increment)
        self.RightETLOffsetSpinBox.setSingleStep(increment)
        self.LeftETLAmplitudeSpinBox.setSingleStep(increment)
        self.RightETLAmplitudeSpinBox.setSingleStep(increment)
   
    def zero_left_etl(self):
        ''' Zeros the amplitude of the left ETL for faster alignment '''
        if self.ZeroLeftETLButton.isChecked():
            self.ETL_L_amp_backup = self.LeftETLAmplitudeSpinBox.value()
            self.LeftETLAmplitudeSpinBox.setValue(0)
            self.LeftETLAmplitudeSpinBox.setEnabled(False)
            self.SaveETLParametersButton.setEnabled(False)
            self.ChooseETLcfgButton.setEnabled(False)
            if self.ShutterComboBox.currentText() == 'Both':
                self.RightETLOffsetSpinBox.setEnabled(False)
                self.RightETLAmplitudeSpinBox.setEnabled(False)
                self.ZeroRightETLButton.setEnabled(False)
        else:
            self.LeftETLAmplitudeSpinBox.setValue(self.ETL_L_amp_backup)
            self.LeftETLAmplitudeSpinBox.setEnabled(True)
            self.SaveETLParametersButton.setEnabled(True)
            self.ChooseETLcfgButton.setEnabled(True)
            if self.ShutterComboBox.currentText() == 'Both':
                self.RightETLOffsetSpinBox.setEnabled(True)
                self.RightETLAmplitudeSpinBox.setEnabled(True)
                self.ZeroRightETLButton.setEnabled(True)

    def zero_right_etl(self):
        ''' Zeros the amplitude of the right ETL for faster alignment '''
        if self.ZeroRightETLButton.isChecked():
            self.ETL_R_amp_backup = self.RightETLAmplitudeSpinBox.value()
            self.RightETLAmplitudeSpinBox.setValue(0)
            self.RightETLAmplitudeSpinBox.setEnabled(False)
            self.SaveETLParametersButton.setEnabled(False)
            self.ChooseETLcfgButton.setEnabled(False)
            if self.ShutterComboBox.currentText() == 'Both':
                self.LeftETLOffsetSpinBox.setEnabled(False)
                self.LeftETLAmplitudeSpinBox.setEnabled(False)
                self.ZeroLeftETLButton.setEnabled(False)
        else:
            self.RightETLAmplitudeSpinBox.setValue(self.ETL_R_amp_backup)
            self.RightETLAmplitudeSpinBox.setEnabled(True)
            self.SaveETLParametersButton.setEnabled(True)
            self.ChooseETLcfgButton.setEnabled(True)
            if self.ShutterComboBox.currentText() == 'Both':
                self.LeftETLOffsetSpinBox.setEnabled(True)
                self.LeftETLAmplitudeSpinBox.setEnabled(True)
                self.ZeroLeftETLButton.setEnabled(True)

    def zero_galvo_amp(self):
        '''Set the amplitude of both galvos to zero, or back to where it was, depending on button state'''
        if self.freezeGalvoButton.isChecked():
            self.galvo_amp_backup = self.LeftGalvoAmplitudeSpinBox.value()
            self.LeftGalvoAmplitudeSpinBox.setValue(0)
            self.freezeGalvoButton.setText('Unfreeze galvos')
        else:
            self.LeftGalvoAmplitudeSpinBox.setValue(self.galvo_amp_backup)
            self.freezeGalvoButton.setText('Freeze galvos')

    def choose_etl_config(self):
        ''' File dialog for choosing the config file
        '''
        path , _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open ETL config file, specific for immersion medium and stationary cuvette size',
                                                         self.state['ETL_cfg_file'],  filter='CSV file (*.csv)')
        ''' To avoid crashes, only set the cfg file when a file has been selected:'''
        if path:
            self.state['ETL_cfg_file'] = path
            self.ETLconfigIndicator.setText(path)
            logger.info(f'Main Window: Chose ETL Config File: {path}')
            self.sig_state_request.emit({'ETL_cfg_file' : path})
        else:
            logger.debug(f'Choose ETL Config File cancelled')

    def save_etl_config(self):
        ''' Save current ETL parameters into config '''
        self.sig_save_etl_config.emit()

    def display_warning(self, string):
        warning = QtWidgets.QMessageBox.warning(None,'mesoSPIM Warning', string, QtWidgets.QMessageBox.Ok)

    def choose_snap_folder(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Open csv File', self.state['snap_folder'])
        if path:
            self.state['snap_folder'] = path
            self.SnapFolderIndicator.setText(path)
            print('Chosen Snap Folder:', path)

    def cascade_all_windows(self):
        if hasattr(self.cfg, 'ui_options') and 'window_pos' in self.cfg.ui_options.keys():
            window_pos = self.cfg.ui_options['window_pos']
        else:
            window_pos = (100, 100)
        self.move(window_pos[0], window_pos[1])
        self.camera_window.move(window_pos[0] + 100, window_pos[1] + 100)
        self.acquisition_manager_window.move(window_pos[0] + 200, window_pos[1] + 200)
        if self.webcam_window:
            self.webcam_window.move(window_pos[0] + 300, window_pos[1] + 300)
