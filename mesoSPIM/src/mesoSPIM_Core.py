'''
Core for the mesoSPIM project
=============================
'''
import os
import ctypes
import time
import platform
import io
import traceback
from collections import deque
import logging
logger = logging.getLogger(__name__)

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

'''National Instruments Imports'''
# import nidaqmx
# from nidaqmx.constants import AcquisitionType, TaskMode
# from nidaqmx.constants import LineGrouping, DigitalWidthUnits
# from nidaqmx.types import CtrTime

''' Import mesoSPIM modules '''

from .devices.shutters.Demo_Shutter import Demo_Shutter
from .devices.shutters.NI_Shutter import NI_Shutter

from .mesoSPIM_Camera import mesoSPIM_Camera

from .devices.lasers.Demo_LaserEnabler import Demo_LaserEnabler
from .devices.lasers.mesoSPIM_LaserEnabler import mesoSPIM_LaserEnabler

from .mesoSPIM_Serial import mesoSPIM_Serial
from .mesoSPIM_WaveFormGenerator import mesoSPIM_WaveFormGenerator, mesoSPIM_DemoWaveFormGenerator
from .mesoSPIM_ImageWriter import mesoSPIM_ImageWriter

from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import convert_seconds_to_string, format_data_size, write_line, replace_with_underscores, log_cpu_core


class mesoSPIM_Core(QtCore.QObject):
    '''This class is the pacemaker of a mesoSPIM'''

    sig_finished = QtCore.pyqtSignal()
    sig_update_gui_from_state = QtCore.pyqtSignal()
    sig_update_gui_from_shutter_state = QtCore.pyqtSignal() # dirty hack to update the shutter state in the GUI
    # These signals have slots in both mesoSPIM_Serial and mesoSPIM_WaveFormGenerator classes. Potentially dangerous.
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_state_request_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_stop_aquisition = QtCore.pyqtSignal() # STOP signal to both Camera and ImageWriter threads
    sig_position = QtCore.pyqtSignal(dict)
    sig_status_message = QtCore.pyqtSignal(str)
    sig_warning = QtCore.pyqtSignal(str)
    sig_progress = QtCore.pyqtSignal(dict)
    sig_run_timepoint = QtCore.pyqtSignal(int)

    ''' Camera-related signals '''
    sig_prepare_image_series = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    sig_add_images_to_image_series = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    # sig_add_images_to_image_series_and_wait_until_done = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    sig_end_image_series = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    sig_write_metadata = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    sig_prepare_live = QtCore.pyqtSignal()
    sig_get_live_image = QtCore.pyqtSignal()
    sig_get_snap_image = QtCore.pyqtSignal(bool)
    sig_end_live = QtCore.pyqtSignal()

    ''' Movement-related signals: '''
    sig_move_relative = QtCore.pyqtSignal(dict)
    sig_move_relative_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_move_absolute = QtCore.pyqtSignal(dict)
    #sig_move_absolute_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()
    sig_center_sample = QtCore.pyqtSignal()

    sig_polling_stage_position_start, sig_polling_stage_position_stop = QtCore.pyqtSignal(), QtCore.pyqtSignal()

    ''' ETL-related signals '''
    sig_save_etl_config = QtCore.pyqtSignal()

    def __init__(self, config, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent # mesoSPIM_MainWindow class
        self.package_directory = self.parent.package_directory
        self.cfg = self.parent.cfg

        self.state = self.parent.state # mesoSPIM_StateSingleton class
        self.state['state'] = 'init'

        self.frame_queue = deque([])
        self.frame_queue_display = deque([], maxlen=1)    

        ''' The signal-slot switchboard '''
        # Note the name duplication (shadowing)!!
        # parent.sig_state_request -> self.state_request_handler
        # self.sig_state_request -> self.waveformer.state_request_handler
        self.sig_run_timepoint.connect(self.parent.run_timepoint, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_state_request.connect(self.state_request_handler, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_execute_script.connect(self.execute_script, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_move_relative.connect(self.move_relative, type=QtCore.Qt.QueuedConnection)
        #self.parent.sig_move_absolute.connect(self.move_absolute, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_zero_axes.connect(self.zero_axes, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_unzero_axes.connect(self.unzero_axes, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_stop_movement.connect(self.stop_movement, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_center_sample.connect(self.sig_center_sample.emit, type=QtCore.Qt.QueuedConnection)
        self.parent.sig_save_etl_config.connect(self.sig_save_etl_config.emit, type=QtCore.Qt.QueuedConnection)
        self.sig_update_gui_from_shutter_state.connect(self.parent.update_GUI_by_shutter_state, type=QtCore.Qt.QueuedConnection)

        self.camera_thread = QtCore.QThread()
        self.camera_worker = mesoSPIM_Camera(parent=self, frame_queue=self.frame_queue, frame_queue_display=self.frame_queue_display)
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_worker.sig_update_gui_from_state.connect(self.sig_update_gui_from_state.emit)
        self.camera_worker.sig_status_message.connect(self.send_status_message_to_gui)
        self.camera_worker.sig_camera_frame.connect(self.parent.camera_window.update_image_from_deque)
        self.sig_end_image_series.connect(self.camera_worker.end_image_series, type=QtCore.Qt.BlockingQueuedConnection)
        self.sig_stop_aquisition.connect(self.camera_worker.stop, type=QtCore.Qt.QueuedConnection)

        self.image_writer_thread = QtCore.QThread()
        self.image_writer = mesoSPIM_ImageWriter(self, self.frame_queue)
        self.image_writer.moveToThread(self.image_writer_thread)
        self.sig_write_metadata.connect(self.image_writer.write_metadata, type=QtCore.Qt.BlockingQueuedConnection)
        self.sig_end_image_series.connect(self.image_writer.end_acquisition, type=QtCore.Qt.BlockingQueuedConnection)
        self.sig_stop_aquisition.connect(self.image_writer.abort_writing, type=QtCore.Qt.QueuedConnection)

        self.camera_worker.sig_write_images.connect(self.image_writer.write_images, type=QtCore.Qt.QueuedConnection)

        #self.serial_thread = QtCore.QThread() # The serial_worker remains in the Core thread, not separate thread for serial_worker
        self.serial_worker = mesoSPIM_Serial(self)
        # self.serial_worker.moveToThread(self.serial_thread) #legacy
        # If the stage (including the timer) is not manually moved to the serial thread, it will execute within the mesoSPIM_Core event loop - Fabian
        #self.serial_worker.stage.moveToThread(self.serial_thread)
        #self.serial_worker.stage.pos_timer.moveToThread(self.serial_thread)

        self.serial_worker.sig_position.connect(self.sig_position.emit)
        self.serial_worker.sig_status_message.connect(self.send_status_message_to_gui)
        #self.serial_worker.sig_pause.connect(self.pause)
        self.sig_polling_stage_position_start.connect(self.serial_worker.stage.pos_timer.start)
        self.sig_polling_stage_position_stop.connect(self.serial_worker.stage.pos_timer.stop)
        self.sig_move_absolute.connect(self.serial_worker.move_absolute)
        self.sig_move_relative.connect(self.serial_worker.move_relative)
        self.sig_move_relative_and_wait_until_done.connect(lambda sdict: self.serial_worker.move_relative(sdict, wait_until_done=True))
        self.sig_state_request.connect(self.serial_worker.state_request_handler)
        self.sig_state_request_and_wait_until_done.connect(lambda sdict: self.serial_worker.state_request_handler(sdict, wait_until_done=True))
        #self.sig_move_absolute_and_wait_until_done.connect(lambda sdict: self.serial_worker.move_absolute(sdict, wait_until_done=True))

        ''' Start the threads '''
        self.camera_thread.start(QtCore.QThread.HighPriority)
        self.image_writer_thread.start(QtCore.QThread.HighPriority)
        # The serial_worker remains in the Core thread, not separate thread for serial_worker
        #self.serial_thread.start() # legacy

        ''' Setting waveform generation up '''
        if self.cfg.waveformgeneration in ('NI', 'cDAQ'):
            self.waveformer = mesoSPIM_WaveFormGenerator(self)
        elif self.cfg.waveformgeneration == 'DemoWaveFormGeneration':
            self.waveformer = mesoSPIM_DemoWaveFormGenerator(self)

        self.waveformer.sig_update_gui_from_state.connect(self.sig_update_gui_from_state.emit)
        # Signals from Core
        self.sig_state_request.connect(self.waveformer.state_request_handler)
        self.sig_state_request_and_wait_until_done.connect(self.waveformer.state_request_handler)
        ''' If this line is activated while the waveformer and the core live in the same thread, a deadlock results '''
        #self.sig_state_request_and_wait_until_done.connect(self.waveformer.state_request_handler, type=3)

        ''' Setting the shutters up '''
        left_shutter_line = self.cfg.shutterdict['shutter_left']
        right_shutter_line = self.cfg.shutterdict['shutter_right']

        if self.cfg.shutter in ('NI','cDAQ'):
            self.shutter_left = NI_Shutter(left_shutter_line) if left_shutter_line is not None else Demo_Shutter(left_shutter_line)
            self.shutter_right = NI_Shutter(right_shutter_line) if right_shutter_line is not None else Demo_Shutter(right_shutter_line)
        elif self.cfg.shutter == 'Demo':
            self.shutter_left = Demo_Shutter(left_shutter_line)
            self.shutter_right = Demo_Shutter(right_shutter_line)

        self.shutter_left.close()
        self.shutter_right.close()
        self.shutterswitch = self.cfg.shutterswitch if hasattr(self.cfg, 'shutterswitch') else False # backward compatibility with older config files
        self.state['shutterstate'] = False
        self.state['max_laser_voltage'] = self.cfg.startup['max_laser_voltage']

        ''' Setting the laser enabler up '''
        if self.cfg.laser in ('NI', 'cDAQ'):
            self.laserenabler = mesoSPIM_LaserEnabler(self.cfg.laserdict)
        elif 'demo' in self.cfg.laser.lower():
            self.laserenabler = Demo_LaserEnabler(self.cfg.laserdict)

        self.state['current_framerate'] = self.cfg.startup['average_frame_rate']
        self.state['snap_folder'] = self.cfg.startup['snap_folder']
        self.state['camera_display_live_subsampling'] = self.cfg.startup['camera_display_live_subsampling']
        self.state['camera_display_acquisition_subsampling'] = self.cfg.startup['camera_display_acquisition_subsampling']
        self.state['samplerate'] = self.cfg.startup['samplerate']

        self.start_time = 0
        self.stopflag = False
        #self.pauseflag = False

        if 'asi' in self.cfg.stage_parameters['stage_type'].lower(): # TTL option for ASI stages
            assert hasattr(self.cfg,  'asi_parameters'), "Config file for ASI Stages must contain 'asi_parameters' dict."
            self.TTL_mode_enabled_in_cfg = self.read_config_parameter('ttl_motion_enabled', self.cfg.asi_parameters)
        else: # Default all other stages to TTL False
            self.TTL_mode_enabled_in_cfg = False

        self.metadata_file = None
        # self.acquisition_list_rotation_position = {}
        self.state['state'] = 'idle'
        self.time_counter = 0

    def __del__(self):
        '''Cleans the threads up after deletion, waits until the threads
        have truly finished their life.

        Make sure to keep this up to date with the number of threads
        '''
        try:
            self.camera_thread.quit()
            self.camera_thread.wait()
            self.image_writer_thread.quit()
            self.image_writer_thread.wait()
        except:
            pass

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            logger.info(f'State request: Key: {key}, Value: {value}')
            '''
            The request handling is done with exec() to write fewer lines of
            code.
            '''
            if key in ('filter',
                       'zoom',
                       'laser',
                       'intensity',
                       'shutterconfig',
                       'state',
                       'camera_exposure_time',
                       'camera_line_interval'):
                exec('self.set_'+key+'(value)')

            elif key in ('samplerate',
                       'sweeptime',
                       'ETL_cfg_file',
                       'etl_l_delay_%',
                       'etl_l_ramp_rising_%',
                       'etl_l_ramp_falling_%',
                       'etl_l_amplitude',
                       'etl_l_offset',
                       'etl_r_delay_%',
                       'etl_r_ramp_rising_%',
                       'etl_r_ramp_falling_%',
                       'etl_r_amplitude',
                       'etl_r_offset',
                       'galvo_l_frequency',
                       'galvo_l_amplitude',
                       'galvo_l_offset',
                       'galvo_l_duty_cycle',
                       'galvo_l_phase',
                       'galvo_r_frequency',
                       #'galvo_r_amplitude',
                       'galvo_r_offset',
                       'galvo_r_duty_cycle',
                       'galvo_r_phase',
                       'laser_l_delay_%',
                       'laser_l_pulse_%',
                       'laser_l_max_amplitude',
                       'laser_r_delay_%',
                       'laser_r_pulse_%',
                       'laser_r_max_amplitude',
                       'camera_delay_%',
                       'camera_pulse_%',
                       'camera_display_live_subsampling',
                       'camera_display_acquisition_subsampling',
                       'camera_sensor_mode',
                       'camera_binning',
                       'galvo_amp_scale_w_zoom',
                       ):
                self.sig_state_request.emit({key : value})

    def set_state(self, state):
        if state == 'live':
            self.state['state'] = 'live'
            self.sig_state_request.emit({'state':'live'})
            logger.debug('Thread name during live: '+ QtCore.QThread.currentThread().objectName())
            self.live()

        if state == 'snap':
            self.state['state']='snap'
            self.sig_state_request.emit({'state':'snap'})
            self.snap()

        elif state == 'run_selected_acquisition':
            self.state['state']= 'run_selected_acquisition'
            self.sig_state_request.emit({'state':'run_selected_acquisition'})
            self.start(row = self.state['selected_row'])

        elif state == 'run_acquisition_list':
            self.state['state'] = 'run_acquisition_list'
            self.sig_state_request.emit({'state':'run_acquisition_list'})
            self.start(row = None)

        elif state == 'preview_acquisition_with_z_update':
            self.state['state'] = 'preview_acquisition'
            self.preview_acquisition(z_update=True)

        elif state == 'preview_acquisition_without_z_update':
            self.state['state'] = 'preview_acquisition'
            self.preview_acquisition(z_update=False)

        elif state == 'idle':
            self.sig_state_request.emit({'state':'idle'})
            self.stop()

        elif state == 'lightsheet_alignment_mode':
            self.state['state'] = 'lightsheet_alignment_mode'
            self.sig_state_request.emit({'state':'live'})
            self.lightsheet_alignment_mode()

        elif state == 'visual_mode':
            self.state['state'] = 'visual_mode'
            self.sig_state_request.emit({'state':'live'})
            self.visual_mode()

    def stop(self):
        self.stopflag = True # This stopflag is a bit risky, needs to be updated to a more robust solution
        self.sig_stop_aquisition.emit() # send STOP signal to both Camera and ImageWriter threads
        if self.TTL_mode_enabled_in_cfg is True:
            self.sig_state_request.emit({'ttl_movement_enabled_during_acq': False})
        self.sig_polling_stage_position_start.emit()
        self.state['state'] = 'idle'
        self.sig_update_gui_from_state.emit()
        self.sig_finished.emit()
        self.frame_queue.clear() # clear the frame queue


#    @QtCore.pyqtSlot(bool)
#    def pause(self, boolean):
#        self.pauseflag = boolean

    def send_progress(self,
                      cur_acq,
                      tot_acqs,
                      cur_image,
                      images_in_acq,
                      total_image_count,
                      image_counter,
                      time_passed_string,
                      remaining_time_string):

        dict = {'current_acq':cur_acq,
                'total_acqs' :tot_acqs,
                'current_image_in_acq':cur_image,
                'images_in_acq': images_in_acq,
                'total_image_count':total_image_count,
                'image_counter':image_counter,
                'time_passed_string': time_passed_string,
                'remaining_time_string': remaining_time_string,
        }
        self.sig_progress.emit(dict)

    @QtCore.pyqtSlot(dict)
    def set_filter(self, filter, wait_until_done=False):
        self.send_status_message_to_gui('Filter changed to '+filter)
        if wait_until_done:
            logger.debug('Setting filter to '+filter)
            self.serial_worker.set_filter(filter, wait_until_done=True)
            logger.debug('Done setting filter to '+filter)
        else:
            self.sig_state_request.emit({'filter': filter})
        self.send_status_message_to_gui('')

    @QtCore.pyqtSlot(dict)
    def set_zoom(self, zoom, wait_until_done=True, update_etl=True):
        self.send_status_message_to_gui('Setting magnification (zoom) to '+str(zoom))
        # Move to the objective exchange position if necessary
        f_pos_old = None
        self.parent.ZoomComboBox.setEnabled(False)
        if 'f_objective_exchange' in self.cfg.stage_parameters.keys():
            self.sig_warning.emit('Please wait until the zoom change is complete')
            f_pos_old = self.state['position']['f_pos']
            logger.debug('f_pos_old: '+str(f_pos_old))
            self.send_status_message_to_gui('Moving to objective exchange position')
            self.move_absolute({'f_abs': self.cfg.stage_parameters['f_objective_exchange']}, wait_until_done=wait_until_done, use_internal_position=False)
            self.send_status_message_to_gui('At the objective exchange position')
        # Set the zoom/revolver
        self.sig_state_request_and_wait_until_done.emit({'zoom': zoom})
        # Return to the previous f_pos
        if f_pos_old is not None:
            self.send_status_message_to_gui('Moving to the focus position')
            self.move_absolute({'f_abs': f_pos_old}, wait_until_done=wait_until_done, use_internal_position=True)
        self.send_status_message_to_gui('Magnification (zoom) changed')
        self.parent.ZoomComboBox.setEnabled(True)
        if update_etl:
            self.sig_state_request.emit({'set_etls_according_to_zoom': zoom})
        

    @QtCore.pyqtSlot(str)
    def set_laser(self, laser, wait_until_done=False, update_etl=True):
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'laser' : laser})
            if update_etl:
                self.sig_state_request_and_wait_until_done.emit({'set_etls_according_to_laser' : laser})
        else:
            self.sig_state_request.emit({'laser':laser})
            if update_etl:
                #print("ETL updated")
                self.sig_state_request.emit({'set_etls_according_to_laser' : laser})

    @QtCore.pyqtSlot(str)
    def set_intensity(self, intensity, wait_until_done=False):
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'intensity': intensity})
        else:
            self.sig_state_request.emit({'intensity':intensity})

    @QtCore.pyqtSlot(float)
    def set_camera_exposure_time(self, time):
        self.sig_state_request.emit({'camera_exposure_time' : time})

    @QtCore.pyqtSlot(float)
    def set_camera_line_interval(self, time):
        self.sig_state_request.emit({'camera_line_interval' : time})

    @QtCore.pyqtSlot(dict)
    def move_relative(self, dict, wait_until_done=False):
        if wait_until_done:
            self.sig_move_relative_and_wait_until_done.emit(dict)
        else:
            self.sig_move_relative.emit(dict)

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, sdict, wait_until_done=False, use_internal_position=True):
        if wait_until_done:
            logger.debug('Core: move_absolute (wait_until_done=True) has started')
            #self.sig_move_absolute_and_wait_until_done.emit(sdict) # THIS was running in MainWindow thread, very stubbornly, unless changed to direct call. Otherwise it was causing a lot of synchronization problems.
            self.serial_worker.move_absolute(sdict, wait_until_done=True, use_internal_position=use_internal_position)
            logger.debug('Core: move_absolute (wait_until_done=True) has finished')
        else:
            self.sig_move_absolute.emit(sdict)

    @QtCore.pyqtSlot(list)
    def zero_axes(self, list):
        self.sig_zero_axes.emit(list)

    @QtCore.pyqtSlot(list)
    def unzero_axes(self, list):
        self.sig_unzero_axes.emit(list)

    @QtCore.pyqtSlot()
    def stop_movement(self):
        self.sig_stop_movement.emit()

    @QtCore.pyqtSlot(str)
    def set_shutterconfig(self, shutterconfig):
        self.sig_state_request.emit({'shutterconfig': shutterconfig})
        self.sig_update_gui_from_shutter_state.emit()

    @QtCore.pyqtSlot()
    def open_shutters(self):
        '''Here the left/right mode is hacked in
        If shutterswitch = True in the config:
        Assumes that the shutter_left line is the general shutter 
        and the shutter_right line is the left/right switch (Right==True)
        '''
        shutterconfig = self.state['shutterconfig']
        if shutterconfig == 'Both':
            if self.shutterswitch is False:
                self.shutter_left.open()
                self.shutter_right.open()
        elif shutterconfig == 'Left':
            if self.shutterswitch is False:
                self.shutter_left.open()
                self.shutter_right.close()
            else:
                self.shutter_left.open() # open the general shutter
                self.shutter_right.close() # set side-switch to false 

        elif shutterconfig == 'Right':
            if self.shutterswitch is False:
                self.shutter_right.open()
                self.shutter_left.close()
            else:
                self.shutter_left.open() # open the general shutter
                self.shutter_right.open() # set side-switch to true
        else: # BOTH open
            self.shutter_right.open()
            self.shutter_left.open()

        self.state['shutterstate'] = True

    @QtCore.pyqtSlot()
    def close_shutters(self):
        '''
        If shutterswitch = True in the config:
        Assumes that the shutter_left line is the general shutter 
        and the shutter_right line is the left/right switch (Right==True)
        '''
        if self.shutterswitch is False:
          #  self.shutter_left.close()
            self.shutter_right.close()
        else:
            self.shutter_left.close()
        
        self.state['shutterstate'] = False

    '''
    Sub-Imaging modes
    '''
    def snap(self, write_flag=True, laser_blanking=True):
        self.sig_prepare_live.emit()
        self.open_shutters()
        self.snap_image(laser_blanking)
        self.sig_get_snap_image.emit(write_flag)
        self.close_shutters()
        self.sig_end_live.emit()
        self.sig_finished.emit()
        QtWidgets.QApplication.processEvents()

    def snap_image(self, laser_blanking=True):
        '''Snaps a single image after updating the waveforms.

        Can be used in acquisitions where changing waveforms are required,
        but there is additional overhead due to the need to write the
        waveforms into the buffers of the NI cards.
        '''
        log_cpu_core(logger, msg='snap_image()')
        self.waveformer.create_tasks()
        self.waveformer.write_waveforms_to_tasks()
        laser = self.state['laser']
        if laser_blanking:
            self.laserenabler.enable(laser)
        self.waveformer.start_tasks()
        self.waveformer.run_tasks()
        if laser_blanking:
            self.laserenabler.disable_all()
        self.waveformer.stop_tasks()
        self.waveformer.close_tasks()

    def prepare_image_series(self):
        '''Prepares an image series without waveform update'''
        self.waveformer.create_tasks()
        self.waveformer.write_waveforms_to_tasks()

    def snap_image_in_series(self, laser_blanking=True):
        '''Snaps and image from a series without waveform update'''
        log_cpu_core(logger, msg='snap_image_in_series()')
        laser = self.state['laser']
        if laser_blanking:
            self.laserenabler.enable(laser)
        self.waveformer.start_tasks()
        logger.debug("start_tasks() finished")
        self.waveformer.run_tasks()
        logger.debug("run_tasks() finished")
        self.waveformer.stop_tasks()
        logger.debug("stop_tasks() finished")
        if laser_blanking:
            self.laserenabler.disable_all()

    def close_image_series(self):
        '''Cleans up after series without waveform update'''
        log_cpu_core(logger, msg='close_image_series()')
        self.waveformer.close_tasks()
        logger.debug("close_image_series() finished")

    def live(self):
        self.stopflag = False
        self.sig_prepare_live.emit()
        laser = self.state['laser']
        laser_blanking = False if (hasattr(self.cfg, 'laser_blanking') and (self.cfg.laser_blanking in ('stack', 'stacks'))) else True
        self.laserenabler.enable(laser)
        while self.stopflag is False:
            ''' How to handle a possible shutter switch?'''
            self.open_shutters()
            ''' Needs update to use snap image in series '''
            self.snap_image(laser_blanking)
            self.sig_get_live_image.emit()

#            while self.pauseflag is True:
#                time.sleep(0.1)
#                QtWidgets.QApplication.processEvents()

            QtWidgets.QApplication.processEvents()

        self.laserenabler.disable_all()
        self.close_shutters()
        self.sig_end_live.emit()
        self.sig_finished.emit()

    def start(self, row=None):
        self.stopflag = False
        if row is None:
            acq_list = self.state['acq_list']
        else:
            acquisition = self.state['acq_list'][row]
            acq_list = AcquisitionList([acquisition])
            
        nonexisting_folders_list = acq_list.check_for_nonexisting_folders()
        filename_list = acq_list.check_for_existing_filenames()
        duplicates_list = acq_list.check_for_duplicated_filenames()
        files_without_extensions = acq_list.check_filename_extensions()
        free_disk_space_bytes = self.get_free_disk_space(acq_list)
        total_required_bytes = self.get_required_disk_space(acq_list)
        acqusitions_outside_motion_limits = self.check_motion_limits(acq_list)

        if nonexisting_folders_list:
            self.sig_warning.emit('The following folders do not exist - stopping! \n'+self.list_to_string_with_carriage_return(nonexisting_folders_list))
            self.sig_finished.emit()
        elif filename_list:
            self.sig_warning.emit('The following files already exist - stopping! \n'+self.list_to_string_with_carriage_return(filename_list))
            self.sig_finished.emit()
        elif duplicates_list:
            self.sig_warning.emit('The following filenames are duplicated - stopping! \n' +self.list_to_string_with_carriage_return(duplicates_list))
            self.sig_finished.emit()
        elif files_without_extensions:
            self.sig_warning.emit('Some files have no extensions (.raw, .tiff, .h5) - stopping! \n' + self.list_to_string_with_carriage_return(files_without_extensions))
            self.sig_finished.emit()
        elif free_disk_space_bytes < total_required_bytes * 1.1:
            self.sig_warning.emit(f'Insufficient disk space: \n'
                                  f'Free {format_data_size(free_disk_space_bytes)} \n'
                                  f'Required {format_data_size(total_required_bytes)}. \n'
                                  f'Stopping! \n')
            self.sig_finished.emit()
        elif len(acqusitions_outside_motion_limits) > 0:
            self.sig_warning.emit(f'The acquisition list contains positions {acqusitions_outside_motion_limits} outside the motion limits - stopping!')
            self.sig_finished.emit()
        else:
            self.prepare_acquisition_list(acq_list)
            self.run_acquisition_list(acq_list)
            self.close_acquisition_list(acq_list)
            self.sig_update_gui_from_state.emit()

    def get_free_disk_space(self, acq_list):
        """Take the disk location of the first file and compute the free disk space"""
        filename0 = os.path.realpath(acq_list.get_all_filenames()[0])
        disk_name = os.path.splitdrive(filename0)[0]
        if platform.system() == 'Windows':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(disk_name), None, None, ctypes.pointer(free_bytes))
            print(f"Free disk {disk_name} space {format_data_size(free_bytes.value)}")
            return free_bytes.value
        else: # non-Windows case, untested!
            st = os.statvfs(disk_name)
            return st.f_bavail * st.f_frsize

    def get_required_disk_space(self, acq_list):
        """"Compute total image data size from the acquisition list, in bytes"""
        BYTES_PER_PIXEL = 2 # 16-bit camera
        px_per_image = self.camera_worker.x_pixels * self.camera_worker.y_pixels
        total_bytes_required = acq_list.get_image_count() * px_per_image * BYTES_PER_PIXEL
        return total_bytes_required
    
    def check_motion_limits(self, acq_list):
        """
        Check if the motion limits of the stage are violated for each acquisition in the given list.

        Args:
            acq_list (list): A list of dictionaries representing acquisitions, where each dictionary contains
                             the x, y, and z positions.

        Returns:
            list: A list of indices of acquisitions in the input list that violate the motion limits.

        """
        unsafe_list = []
        for i in range(len(acq_list)):
            if not (self.cfg.stage_parameters['x_min'] <= acq_list[i]['x_pos'] - self.serial_worker.stage.int_x_pos_offset <= self.cfg.stage_parameters['x_max']):
                unsafe_list.append(i)
            elif not (self.cfg.stage_parameters['y_min'] <= acq_list[i]['y_pos'] - self.serial_worker.stage.int_y_pos_offset <= self.cfg.stage_parameters['y_max']):
                unsafe_list.append(i)
            elif not (self.cfg.stage_parameters['z_min'] <= acq_list[i]['z_start'] - self.serial_worker.stage.int_z_pos_offset <= self.cfg.stage_parameters['z_max']):
                unsafe_list.append(i)
            elif not (self.cfg.stage_parameters['z_min'] <= acq_list[i]['z_end'] - self.serial_worker.stage.int_z_pos_offset <= self.cfg.stage_parameters['z_max']):
                unsafe_list.append(i)
            else:
                continue
        return unsafe_list
            
    def prepare_acquisition_list(self, acq_list):
        ''' Housekeeping: Prepare the acquisition list '''
        self.image_count = 0
        self.acquisition_count = 0
        self.total_acquisition_count = len(acq_list)
        self.total_image_count = acq_list.get_image_count()
        self.start_time = time.time()

    def run_acquisition_list(self, acq_list):
        for acq in acq_list:
            if not self.stopflag:
                self.prepare_acquisition(acq, acq_list)
                self.run_acquisition(acq, acq_list)
                self.close_acquisition(acq, acq_list)

    def close_acquisition_list(self, acq_list):
        self.sig_status_message.emit('Closing Acquisition List')
        if not self.stopflag:
            current_rotation = self.state['position']['theta_pos']
            startpoint = acq_list.get_startpoint()
            target_rotation = startpoint['theta_abs']

            if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1:
                self.move_absolute({'theta_abs':target_rotation}, wait_until_done=True)

            self.state['state'] = 'idle'
            self.move_absolute(acq_list.get_startpoint(), wait_until_done=True)
            self.sig_polling_stage_position_start.emit()  # resume asking stages about their position

            self.set_filter(acq_list[0]['filter'])
            self.set_laser(acq_list[0]['laser'], wait_until_done=False, update_etl=False)
            if self.state['zoom'] != acq_list[0]['zoom']:
                self.set_zoom(acq_list[0]['zoom'], update_etl=False)
            ''' This is for the GUI to update properly'''
            QtWidgets.QApplication.processEvents()

            self.sig_state_request.emit({'etl_l_amplitude' : acq_list[0]['etl_l_amplitude']})
            self.sig_state_request.emit({'etl_r_amplitude' : acq_list[0]['etl_r_amplitude']})
            self.sig_state_request.emit({'etl_l_offset' : acq_list[0]['etl_l_offset']})
            self.sig_state_request.emit({'etl_r_offset' : acq_list[0]['etl_r_offset']})
            self.set_intensity(acq_list[0]['intensity'])
            time.sleep(0.1) # tiny sleep period to allow Main Window indicators to catch up
            self.sig_finished.emit()
            self.send_status_message_to_gui('Acquisition list closed')
        else:
            self.send_status_message_to_gui('Acquisition stopped')

    def preview_acquisition(self, z_update=True):
        self.stopflag = False
        row = self.state['selected_row']
        acq = self.state['acq_list'][row]

        ''' Rotation handling goes here '''
        current_rotation = self.state['position']['theta_pos']
        startpoint = acq.get_startpoint()
        target_rotation = startpoint['theta_abs']

        ''' Create a flag when rotation is required: '''
        rotationflag = True if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1 else False

        ''' Remove z-coordinate from dict so that z is not updated during preview. If rotation necessary, z_abs is updated'''
        if not z_update and not rotationflag:
                del startpoint['z_abs']

        ''' Check if sample has to be rotated, allow some tolerance '''
        if rotationflag:
            self.sig_status_message.emit('Rotating sample')
            self.move_absolute({'theta_abs': target_rotation}, wait_until_done=False)

        self.sig_status_message.emit('Setting Filter')
        self.set_filter(acq['filter'], wait_until_done=False)

        self.sig_status_message.emit('Going to start position')
        self.move_absolute(startpoint, wait_until_done=False)

        self.sig_status_message.emit('Setting Shutter')
        self.set_shutterconfig(acq['shutterconfig'])
        self.sig_status_message.emit('Setting Zoom & Laser')
        if self.state['zoom'] != acq['zoom']:
            self.sig_status_message.emit('Setting magnification (zoom)')
            self.set_zoom(acq['zoom'], update_etl=False)
        self.set_intensity(acq['intensity'], wait_until_done=False)
        self.set_laser(acq['laser'], wait_until_done=False, update_etl=False)

        self.sig_state_request.emit({'etl_l_amplitude' : acq['etl_l_amplitude']})
        self.sig_state_request.emit({'etl_r_amplitude' : acq['etl_r_amplitude']})
        self.sig_state_request.emit({'etl_l_offset' : acq['etl_l_offset']})
        self.sig_state_request.emit({'etl_r_offset' : acq['etl_r_offset']})

        self.sig_status_message.emit('Ready for preview...')
        self.sig_update_gui_from_state.emit()
        self.state['state'] = 'idle'

    def prepare_acquisition(self, acq, acq_list):
        ''' Housekeeping: Prepare the acquisition  '''
        logger.info(f'Core: Running Acquisition #{self.acquisition_count} with Filename: {acq["filename"]}')
        self.state['selected_row'] = self.acquisition_count # this make sure that the correct row is selected in the GUI
        self.sig_status_message.emit('Going to start position')
        current_rotation = self.state['position']['theta_pos']
        startpoint = acq.get_startpoint()
        target_rotation = startpoint['theta_abs']
        self.acq_start_time = time.time()
        self.acq_start_time_string = time.strftime("%Y%m%d-%H%M%S")
        # stop asking stages about their positions, to avoid messing up serial comm during acquisition:
        self.sig_polling_stage_position_stop.emit()
        self.sig_status_message.emit('Going to start position')
        ''' Check if sample has to be rotated, allow some tolerance '''
        if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1:
            self.move_absolute({'theta_abs': target_rotation}, wait_until_done=True)
        
        self.move_absolute(startpoint, wait_until_done=True)
        self.serial_worker.stage.report_position() # Last Position update before acquisition starts for proper tile view display
        self.sig_status_message.emit('Setting Filter & Shutter')
        self.set_shutterconfig(acq['shutterconfig'])
        self.set_filter(acq['filter'], wait_until_done=True)
        if self.state['zoom'] != acq['zoom']:
            self.sig_status_message.emit('Setting magnification (zoom)')
            self.set_zoom(acq['zoom'], update_etl=False)
        self.set_intensity(acq['intensity'], wait_until_done=True)
        self.set_laser(acq['laser'], wait_until_done=True, update_etl=False)
        ''' This is for the GUI to update properly'''
        QtWidgets.QApplication.processEvents()

        self.sig_state_request.emit({'etl_l_amplitude' : acq['etl_l_amplitude']})
        self.sig_state_request.emit({'etl_r_amplitude' : acq['etl_r_amplitude']})
        self.sig_state_request.emit({'etl_l_offset' : acq['etl_l_offset']})
        self.sig_state_request.emit({'etl_r_offset' : acq['etl_r_offset']})
        self.f_step_generator = acq.get_focus_stepsize_generator()

        if self.TTL_mode_enabled_in_cfg is True:
            ''' The relative movement has to be carried out once with the ASI-controller '''
            self.move_relative(acq.get_delta_z_and_delta_f_dict(inverted=True))
            time.sleep(0.1)
            self.move_relative(acq.get_delta_z_and_delta_f_dict())
            time.sleep(0.1)
            self.sig_state_request.emit({'ttl_movement_enabled_during_acq': True})
            time.sleep(0.05)

        self.sig_status_message.emit('Preparing camera: Allocating memory')
        self.sig_prepare_image_series.emit(acq, acq_list) # signal to the Camera
        self.image_writer.prepare_acquisition(acq, acq_list)
        self.prepare_image_series()
        self.sig_write_metadata.emit(acq, acq_list)

    def run_acquisition(self, acq, acq_list):
        steps = acq.get_image_count()
        self.sig_status_message.emit('Running Acquisition')
        self.open_shutters()
        self.image_acq_start_time = time.time()
        self.image_acq_start_time_string = time.strftime("%Y%m%d-%H%M%S")

        move_dict = acq.get_delta_dict()
        laser = self.state['laser']
        self.laserenabler.enable(laser) # counter-intuitively the TTL laser enabler is slow here. Starts well before and ends well after actual AO waveforms.
        laser_blanking = False if (hasattr(self.cfg, 'laser_blanking') and (self.cfg.laser_blanking in ('stack', 'stacks'))) else True
        for i in range(steps):
            if self.stopflag is True:
                self.close_image_series()
                self.sig_end_image_series.emit(acq, acq_list)
                self.sig_finished.emit()
                break
            else:
                self.snap_image_in_series(laser_blanking)
                self.sig_add_images_to_image_series.emit(acq, acq_list)
                ''' Get the current correct f_step'''
                f_step = self.f_step_generator.__next__()
                if f_step != 0:
                    move_dict.update({'f_rel':f_step})
                else: # clear key if no F-step is required
                    move_dict.pop('f_rel', None)

                logger.debug(f'move_dict: {move_dict}')
                self.move_relative(move_dict)

                ''' The pauseflag allows:
                    - pausing running acquisitions
                    - wait for slow hardware to catch up (e.g. slow stages)
                '''
#                while self.pauseflag is True:
#                    time.sleep(0.02)
#                    QtWidgets.QApplication.processEvents()
                
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
                self.image_count += 1

                ''' Keep track of passed time and predict remaining time '''
                time_passed = time.time() - self.start_time
                time_remaining = time_passed / self.image_count * (self.total_image_count - self.image_count)

                ''' Every 100 images, update the frame rate'''
                if self.image_count % 100 == 0:
                    self.state['current_framerate'] = self.image_count / time_passed

                if ((self.image_count + 1) % 5 == 0) or (self.total_image_count % (self.image_count + 1) == 0):
                    self.send_progress(self.acquisition_count,
                                    self.total_acquisition_count,
                                    i + 1,
                                    steps,
                                    self.total_image_count,
                                    self.image_count + 1,
                                    convert_seconds_to_string(time_passed),
                                    convert_seconds_to_string(time_remaining))
        self.laserenabler.disable_all()
        self.image_acq_end_time = time.time()
        self.image_acq_end_time_string = time.strftime("%Y%m%d-%H%M%S")

        self.close_shutters()

    def close_acquisition(self, acq, acq_list):
        self.sig_status_message.emit('Closing Acquisition: Saving data & freeing up memory')
        if self.stopflag is False:
            self.close_image_series()
            self.sig_end_image_series.emit(acq, acq_list)

        if self.TTL_mode_enabled_in_cfg is True:
            logger.debug('Attempting to set TTL mode to False')
            time.sleep(0.05) # add some buffer time for serial execution
            self.sig_state_request.emit({'ttl_movement_enabled_during_acq' : False})
            time.sleep(0.05)  # buffer time
            logger.debug('TTL mode set to False')

        self.acq_end_time = time.time()
        self.acq_end_time_string = time.strftime("%Y%m%d-%H%M%S")
        self.state['current_framerate'] = acq.get_image_count() / (self.image_acq_end_time - self.image_acq_start_time)
        self.append_timing_info_to_metadata(acq)
        self.acquisition_count += 1

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.state['state'] = 'running_script'
        try:
            exec(script)
        except:
            traceback.print_exc()
        self.sig_finished.emit()
        self.state['state']='idle'
        self.sig_update_gui_from_state.emit()

    def lightsheet_alignment_mode(self):
        '''Switches shutters after each image to allow coalignment of both lightsheets'''
        self.stopflag = False
        self.sig_prepare_live.emit()
        while self.stopflag is False:
            for shutter in ('Left', 'Right'):
                self.set_shutterconfig(shutter)
                self.open_shutters()
                self.snap_image()
                self.sig_get_live_image.emit()
                self.close_shutters()
                time.sleep(0.1)
            QtWidgets.QApplication.processEvents()

        self.sig_end_live.emit()
        self.sig_finished.emit()

    def visual_mode(self):
        old_l_amp = self.state['etl_l_amplitude']
        old_r_amp = self.state['etl_r_amplitude']
        self.sig_state_request.emit({'etl_l_amplitude' : 0})
        self.sig_state_request.emit({'etl_r_amplitude' : 0})
        time.sleep(0.05)

        self.sig_prepare_live.emit()

        self.stopflag = False

        self.open_shutters()
        while self.stopflag is False:
            ''' Needs update to use snap image in series '''
            self.snap_image()
            self.sig_get_live_image.emit()
            QtWidgets.QApplication.processEvents()

            ''' How to handle a possible shutter switch?'''
            self.open_shutters()

        self.close_shutters()
        self.sig_end_live.emit()

        self.sig_finished.emit()

        self.sig_state_request.emit({'etl_l_amplitude' : old_l_amp})
        self.sig_state_request.emit({'etl_r_amplitude' : old_r_amp})

    def execute_galil_program(self):
        '''Little helper method to execute the program loaded onto the Galil stage:
        allows hand controller to operate'''
        self.sig_state_request.emit({'stage_program' : 'execute'})

    @QtCore.pyqtSlot(str)
    def send_status_message_to_gui(self, string):
        self.sig_status_message.emit(string)

    def list_to_string_with_carriage_return(self, input_list):
        mystring = ''
        for i in input_list:
            mystring = mystring + ' \n ' + i    
        return mystring

    def read_config_parameter(self, key, dictionary):
        """Helper method to check if key exists in the dictionary and read its value, or throw a meaningful error"""
        if key not in dictionary.keys():
            message = f"Mandatory parameter {key} not found in dictionary: \n {dictionary} \n" \
                      f"Check config file for missing parameter {key}."
            logger.error(message)
            raise ValueError(message)
        else:
            return dictionary[key]

    def append_timing_info_to_metadata(self, acq):
        '''
        Appends a metadata.txt file
        Path contains the file to be written
        '''
        metadata_path = self.image_writer.writer.metadata_file
        # path = acq['folder'] + '/' + replace_with_underscores(acq['filename'])
        # metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'
        with open(metadata_path, 'a') as file:
            write_line(file, 'TIMING INFORMATION')
            write_line(file, 'Started stack', self.acq_start_time_string)
            write_line(file, 'Started taking images', self.image_acq_start_time_string)
            write_line(file, 'Stopped taking images', self.image_acq_end_time_string)
            write_line(file, 'Stopped stack', self.acq_end_time_string)
            write_line(file, 'Total time of taking images, s', str(round(self.image_acq_end_time - self.image_acq_start_time, 2)))
            write_line(file, 'Total time of stack acquisition, s', str(round(self.acq_end_time - self.acq_start_time, 2)))
            write_line(file, 'Frame rate during taking images, img/s:', str(round(self.state['current_framerate'], 2)))
            write_line(file, '===================== END OF ACQUISITION ======================')
            write_line(file)

    def run_time_lapse(self, tpoints=1, time_interval_sec=60):
        '''A quick and dirty implementation of time lapse via recursive function.'''	
        if self.time_counter >= tpoints:
            print("Timer sequence finished")
            self.time_counter = 0
            return
        print(f"Running time point {self.time_counter} out of {tpoints - 1}...")
        QtCore.QTimer.singleShot(time_interval_sec*1000, lambda: self.run_time_lapse(tpoints, time_interval_sec))
        self.sig_run_timepoint.emit(self.time_counter)
        self.time_counter += 1