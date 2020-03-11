'''
Core for the mesoSPIM project
=============================
'''
import os
import numpy as np
import time
from scipy import signal
import csv
import traceback

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
from .mesoSPIM_State import mesoSPIM_StateSingleton

from .devices.shutters.Demo_Shutter import Demo_Shutter
from .devices.shutters.NI_Shutter import NI_Shutter

from .mesoSPIM_Camera import mesoSPIM_Camera

from .devices.lasers.Demo_LaserEnabler import Demo_LaserEnabler
from .devices.lasers.mesoSPIM_LaserEnabler import mesoSPIM_LaserEnabler

from .mesoSPIM_Serial import mesoSPIM_Serial
# from .mesoSPIM_DemoSerial import mesoSPIM_Serial
from .mesoSPIM_WaveFormGenerator import mesoSPIM_WaveFormGenerator, mesoSPIM_DemoWaveFormGenerator

from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import convert_seconds_to_string
from .utils.demo_threads import mesoSPIM_DemoThread

class mesoSPIM_Core(QtCore.QObject):
    '''This class is the pacemaker of a mesoSPIM

    Signals it can send:

    '''

    sig_finished = QtCore.pyqtSignal()

    sig_update_gui_from_state = QtCore.pyqtSignal(bool)

    sig_state_request = QtCore.pyqtSignal(dict)
    sig_state_request_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_position = QtCore.pyqtSignal(dict)

    sig_status_message = QtCore.pyqtSignal(str)
    sig_warning = QtCore.pyqtSignal(str)

    sig_progress = QtCore.pyqtSignal(dict)

    ''' Camera-related signals '''
    sig_prepare_image_series = QtCore.pyqtSignal(Acquisition)
    sig_add_images_to_image_series = QtCore.pyqtSignal()
    sig_add_images_to_image_series_and_wait_until_done = QtCore.pyqtSignal()
    sig_end_image_series = QtCore.pyqtSignal()

    sig_prepare_live = QtCore.pyqtSignal()
    sig_get_live_image = QtCore.pyqtSignal()
    sig_get_snap_image = QtCore.pyqtSignal()
    sig_end_live = QtCore.pyqtSignal()

    ''' Movement-related signals: '''
    sig_move_relative = QtCore.pyqtSignal(dict)
    sig_move_relative_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_move_absolute = QtCore.pyqtSignal(dict)
    sig_move_absolute_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_stop_movement = QtCore.pyqtSignal()
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()

    sig_mark_rotation_position = QtCore.pyqtSignal()
    sig_go_to_rotation_position = QtCore.pyqtSignal()
    sig_go_to_rotation_position_and_wait_until_done = QtCore.pyqtSignal()

    ''' ETL-related signals '''
    sig_save_etl_config = QtCore.pyqtSignal()

    def __init__(self, config, parent):
        super().__init__()

        ''' Assign the parent class to a instance variable for callbacks '''
        self.parent = parent
        self.cfg = self.parent.cfg

        self.state = mesoSPIM_StateSingleton()
        self.state['state']='init'

        ''' The signal-slot switchboard '''
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.parent.sig_execute_script.connect(self.execute_script)

        self.parent.sig_move_relative.connect(self.move_relative)
        # self.parent.sig_move_relative_and_wait_until_done.connect(lambda dict: self.move_relative(dict, wait_until_done=True))
        self.parent.sig_move_absolute.connect(self.move_absolute)
        # self.parent.sig_move_absolute_and_wait_until_done.connect(lambda dict: self.move_absolute(dict, wait_until_done=True))
        self.parent.sig_zero_axes.connect(self.zero_axes)
        self.parent.sig_unzero_axes.connect(self.unzero_axes)
        self.parent.sig_stop_movement.connect(self.stop_movement)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)
        self.parent.sig_mark_rotation_position.connect(self.sig_mark_rotation_position.emit)
        self.parent.sig_go_to_rotation_position.connect(self.sig_go_to_rotation_position.emit)

        self.parent.sig_save_etl_config.connect(self.sig_save_etl_config.emit)

        #logger.info('Core internal thread affinity in init: '+str(id(self.thread())))

        ''' Set the Camera thread up '''
        self.camera_thread = QtCore.QThread()
        #self.camera_worker = mesoSPIM_HamamatsuCamera(self)
        self.camera_worker = mesoSPIM_Camera(self)
        #logger.info('Camera worker thread affinity before moveToThread? Answer:'+str(id(self.camera_worker.thread())))
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_worker.sig_update_gui_from_state.connect(self.sig_update_gui_from_state.emit)
        self.camera_worker.sig_status_message.connect(self.send_status_message_to_gui)
        #logger.info('Camera worker thread affinity after moveToThread? Answer:'+str(id(self.camera_worker.thread())))
        ''' Set the serial thread up '''
        self.serial_thread = QtCore.QThread()
        self.serial_worker = mesoSPIM_Serial(self)
        self.serial_worker.moveToThread(self.serial_thread)

        #self.serial_worker.sig_position.connect(lambda dict: self.sig_position.emit(dict))
        self.serial_worker.sig_position.connect(self.sig_position.emit)

        # ''' Setting another demo thread up '''
        # self.demo_thread = QtCore.QThread()
        # self.demo_worker = mesoSPIM_DemoThread()
        # self.sig_state_request.connect(self.demo_worker.report_thread_id)
        # self.demo_worker.moveToThread(self.demo_thread)
        # self.demo_thread.start()

        # ''' HICKUP DEBUGGING '''
        # self.z_start_measured = 0.0
        # self.z_end_measured = 0.0
        # self.hickup_delta_z = 0.0

        ''' Start the threads '''
        self.camera_thread.start()
        #logger.info('Camera worker thread affinity after starting the thread? Answer:'+str(id(self.camera_worker.thread())))
        self.serial_thread.start()

        # ''' Get the demo thread set up and start it '''

        #logger.info('Camera thread running? Answer:'+str(self.camera_thread.isRunning()))
        #logger.info('Serial thread running? Answer:'+str(self.serial_thread.isRunning()))

        #logger.info(f'Core: Camera Thread priority: {self.camera_thread.priority()}')
        #logger.info(f'Core: Serial Thread priority: {self.serial_thread.priority()}')

        ''' Setting waveform generation up '''
        if self.cfg.waveformgeneration == 'NI':
            self.waveformer = mesoSPIM_WaveFormGenerator(self)
        elif self.cfg.waveformgeneration == 'DemoWaveFormGeneration':
            self.waveformer = mesoSPIM_DemoWaveFormGenerator(self)

        self.waveformer.sig_update_gui_from_state.connect(self.sig_update_gui_from_state.emit)
        self.sig_state_request.connect(self.waveformer.state_request_handler)
        self.sig_state_request_and_wait_until_done.connect(self.waveformer.state_request_handler)
        ''' If this line is activated while the waveformer and the core live in the same thread, a deadlock results '''
        #self.sig_state_request_and_wait_until_done.connect(self.waveformer.state_request_handler, type=3)

        ''' Setting the shutters up '''
        left_shutter_line = self.cfg.shutterdict['shutter_left']
        right_shutter_line = self.cfg.shutterdict['shutter_right']

        if self.cfg.shutter == 'NI':
            self.shutter_left = NI_Shutter(left_shutter_line)
            self.shutter_right = NI_Shutter(right_shutter_line)
        elif self.cfg.shutter == 'Demo':
            self.shutter_left = Demo_Shutter(left_shutter_line)
            self.shutter_right = Demo_Shutter(right_shutter_line)

        self.shutter_left.close()
        self.shutter_right.close()
        self.state['shutterstate'] = False

        ''' Setting the laserenabler up '''
        if self.cfg.laser == 'NI':
            self.laserenabler = mesoSPIM_LaserEnabler(self.cfg.laserdict)
        elif self.cfg.laser == 'Demo':
            self.laserenabler = Demo_LaserEnabler(self.cfg.laserdict)

        self.state['state']='idle'
        self.state['current_framerate'] = self.cfg.startup['average_frame_rate']
        self.state['snap_folder'] = self.cfg.startup['snap_folder']

        self.start_time = 0

        self.stopflag = False

        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

        # self.acquisition_list_rotation_position = {}

    def __del__(self):
        '''Cleans the threads up after deletion, waits until the threads
        have truly finished their life.

        Make sure to keep this up to date with the number of threads
        '''
        try:
            self.camera_thread.quit()
            self.serial_thread.quit()

            self.camera_thread.wait()
            self.serial_thread.wait()
        except:
            pass


    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            # print('Core Thread: State request: Key: ', key, ' Value: ', value)
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
                       'galvo_r_amplitude',
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
                       'camera_display_snap_subsampling',
                       'camera_display_acquisition_subsampling',
                       'camera_sensor_mode',
                       'camera_binning',
                       ):
                self.sig_state_request.emit({key : value})

    def set_state(self, state):
        if state == 'live':
            self.state['state']='live'
            self.sig_state_request.emit({'state':'live'})
            logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))
            #logger.info('Core internal thread affinity in live: '+str(id(self.thread())))
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
            # print('Core: Stopping requested')
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
        self.stopflag = True
        ''' This stopflag is a bit risky, needs to be updated'''
        self.state['state']='idle'
        self.sig_update_gui_from_state.emit(False)
        self.sig_finished.emit()

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
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'filter' : filter})
        else:
            self.sig_state_request.emit({'filter' : filter})

    @QtCore.pyqtSlot(dict)
    def set_zoom(self, zoom, wait_until_done=False, update_etl=True):
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'zoom' : zoom})
            if update_etl:
                self.sig_state_request_and_wait_until_done.emit({'set_etls_according_to_zoom' : zoom})
        else:
            self.sig_state_request.emit({'zoom' : zoom})
            if update_etl:
                self.sig_state_request.emit({'set_etls_according_to_zoom' : zoom})

    @QtCore.pyqtSlot(str)
    def set_laser(self, laser, wait_until_done=False, update_etl=True):
        self.laserenabler.enable(laser)
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'laser' : laser})
            if update_etl:
                self.sig_state_request_and_wait_until_done.emit({'set_etls_according_to_laser' : laser})
        else:
            self.sig_state_request.emit({'laser':laser})
            if update_etl:
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

    # @QtCore.pyqtSlot(dict)
    # def move_relative_and_wait_until_done(self, dict):
    #     self.move_relative(dict, wait_until_done=True)

    @QtCore.pyqtSlot(dict)
    def move_absolute(self, dict, wait_until_done=False):
        if wait_until_done:
            self.sig_move_absolute_and_wait_until_done.emit(dict)
        else:
            self.sig_move_absolute.emit(dict)

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
        self.state['shutterconfig'] = shutterconfig

    @QtCore.pyqtSlot()
    def open_shutters(self):
        shutterconfig = self.state['shutterconfig']

        if shutterconfig == 'Both':
            self.shutter_left.open()
            self.shutter_right.open()
        elif shutterconfig == 'Left':
            self.shutter_left.open()
            self.shutter_right.close()
        elif shutterconfig == 'Right':
            self.shutter_right.open()
            self.shutter_left.close()
        else:
            self.shutter_right.open()
            self.shutter_left.open()

        self.state['shutterstate'] = True

    @QtCore.pyqtSlot()
    def close_shutters(self):
        self.shutter_left.close()
        self.shutter_right.close()
        self.state['shutterstate'] = False

    '''
    Sub-Imaging modes
    '''
    def snap(self):
        self.sig_prepare_live.emit()
        self.open_shutters()
        self.snap_image()
        self.sig_get_snap_image.emit()
        self.close_shutters()

        ''' Doubled code'''
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = timestr + '.tif'

        self.write_snap_metadata(filename)

        self.sig_end_live.emit()
        self.sig_finished.emit()
        QtWidgets.QApplication.processEvents()

    def snap_image(self):
        '''Snaps a single image after updating the waveforms.

        Can be used in acquisitions where changing waveforms are required,
        but there is additional overhead due to the need to write the
        waveforms into the buffers of the NI cards.
        '''

        self.waveformer.create_tasks()
        self.waveformer.write_waveforms_to_tasks()
        self.waveformer.start_tasks()
        self.waveformer.run_tasks()
        self.waveformer.stop_tasks()
        self.waveformer.close_tasks()

    def prepare_image_series(self):
        '''Prepares an image series without waveform update'''
        self.waveformer.create_tasks()
        self.waveformer.write_waveforms_to_tasks()

    def snap_image_in_series(self):
        '''Snaps and image from a series without waveform update'''
        self.waveformer.start_tasks()
        self.waveformer.run_tasks()
        self.waveformer.stop_tasks()

    def close_image_series(self):
        '''Cleans up after series without waveform update'''
        self.waveformer.close_tasks()

    '''
    Execution code for major imaging modes starts here
    '''

    def live(self):
        self.stopflag = False
        self.sig_prepare_live.emit()

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

    def start(self, row=None):
        self.stopflag = False

        if row==None:
            acq_list = self.state['acq_list']
        else:
            acq_list = self.state['acq_list']
            acquisition = self.state['acq_list'][row]
            acq_list = AcquisitionList([acquisition])
            
        nonexisting_folders_list = acq_list.check_for_nonexisting_folders()
        filename_list = acq_list.check_for_existing_filenames()
        duplicates_list = acq_list.check_for_duplicated_filenames()

        if nonexisting_folders_list != []:
            self.sig_warning.emit('The following folders do not exist - stopping! \n'+self.list_to_string_with_carriage_return(nonexisting_folders_list))
            self.sig_finished.emit()
        elif filename_list != []:
            self.sig_warning.emit('The following files already exist - stopping! \n'+self.list_to_string_with_carriage_return(filename_list))
            self.sig_finished.emit()
        elif duplicates_list != []:
            self.sig_warning.emit('The following filenames are duplicated - stopping! \n' +self.list_to_string_with_carriage_return(duplicates_list))
            self.sig_finished.emit()
        else:
            self.sig_update_gui_from_state.emit(True)
            self.prepare_acquisition_list(acq_list)
            self.run_acquisition_list(acq_list)
            self.close_acquisition_list(acq_list)
            self.sig_update_gui_from_state.emit(False)

    def prepare_acquisition_list(self, acq_list):
        '''
        Housekeeping: Prepare the acquisition list
        '''
        self.image_count = 0
        self.acquisition_count = 0
        self.total_acquisition_count = len(acq_list)
        self.total_image_count = acq_list.get_image_count()
        self.start_time = time.time()


    def run_acquisition_list(self, acq_list):
        for acq in acq_list:
            if not self.stopflag:
                self.prepare_acquisition(acq)
                self.run_acquisition(acq)
                self.close_acquisition(acq)

    def close_acquisition_list(self, acq_list):
        self.sig_status_message.emit('Closing Acquisition List')

        if not self.stopflag:
            current_rotation = self.state['position']['theta_pos']
            startpoint = acq_list.get_startpoint()
            target_rotation = startpoint['theta_abs']

            if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1:
                ''' Go to rotation position '''
                self.sig_go_to_rotation_position_and_wait_until_done.emit()
                self.move_absolute({'theta_abs':target_rotation}, wait_until_done=True)

            self.move_absolute(acq_list.get_startpoint())
            self.set_filter(acq_list[0]['filter'])
            self.set_laser(acq_list[0]['laser'], wait_until_done=False, update_etl=False)
            self.set_zoom(acq_list[0]['zoom'], wait_until_done=False, update_etl=False)
            ''' This is for the GUI to update properly, otherwise ETL values for previous laser might be displayed '''
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 1)

            self.sig_state_request.emit({'etl_l_amplitude' : acq_list[0]['etl_l_amplitude']})
            self.sig_state_request.emit({'etl_r_amplitude' : acq_list[0]['etl_r_amplitude']})
            self.sig_state_request.emit({'etl_l_offset' : acq_list[0]['etl_l_offset']})
            self.sig_state_request.emit({'etl_r_offset' : acq_list[0]['etl_r_offset']})
            self.set_intensity(acq_list[0]['intensity'])
            time.sleep(0.1) # tiny sleep period to allow Main Window indicators to catch up
            self.sig_finished.emit()

    def preview_acquisition(self, z_update=True):
        self.stopflag = False

        row = self.state['selected_row']

        if row==None:
            pass
            # print('No row selected!')
        else:
            self.sig_update_gui_from_state.emit(True)
            acq = self.state['acq_list'][row]

            ''' Rotation handling goes here '''
            current_rotation = self.state['position']['theta_pos']
            startpoint = acq.get_startpoint()
            target_rotation = startpoint['theta_abs']

            ''' Create a flag when rotation is required: '''
            if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1:
                rotationflag = True 
            else:
                rotationflag = False

            ''' Remove z-coordinate from dict so that z is not updated during preview: '''
            if z_update is False:
                ''' If a rotation is necessary, z will be updated '''
                if rotationflag == False: 
                    del startpoint['z_abs']                

            ''' Check if sample has to be rotated, allow some tolerance '''
            if rotationflag:
                self.sig_status_message.emit('Going to rotation position')
                self.sig_go_to_rotation_position_and_wait_until_done.emit()
                self.sig_status_message.emit('Rotating sample')
                self.move_absolute({'theta_abs':target_rotation}, wait_until_done=True)

            self.sig_status_message.emit('Setting Filter')
            self.set_filter(acq['filter'], wait_until_done=True)

            self.sig_status_message.emit('Going to start position')
            self.move_absolute(startpoint, wait_until_done=False)

            self.sig_status_message.emit('Setting Shutter')
            self.set_shutterconfig(acq['shutterconfig'])
            self.sig_status_message.emit('Setting Zoom & Laser')
            self.set_zoom(acq['zoom'], wait_until_done=False, update_etl=False)
            self.set_intensity(acq['intensity'], wait_until_done=True)
            self.set_laser(acq['laser'], wait_until_done=True, update_etl=False)
            ''' This is for the GUI to update properly, otherwise ETL values for previous laser might be displayed '''
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 1)

            self.sig_state_request.emit({'etl_l_amplitude' : acq['etl_l_amplitude']})
            self.sig_state_request.emit({'etl_r_amplitude' : acq['etl_r_amplitude']})
            self.sig_state_request.emit({'etl_l_offset' : acq['etl_l_offset']})
            self.sig_state_request.emit({'etl_r_offset' : acq['etl_r_offset']})

            self.sig_status_message.emit('Ready for preview...')
            self.sig_update_gui_from_state.emit(False)

        self.state['state'] = 'idle'

    def prepare_acquisition(self, acq):
        '''
        Housekeeping: Prepare the acquisition
        '''
        logger.info(f'Core: Running Acquisition #{self.acquisition_count} with Filename: {acq["filename"]}')

        self.sig_status_message.emit('Going to start position')
        ''' Rotation handling goes here:

        If target rotation different than current rotation:
            - go to target position
            - rotate to target angle
            -

        '''
        current_rotation = self.state['position']['theta_pos']
        startpoint = acq.get_startpoint()
        target_rotation = startpoint['theta_abs']
        self.acq_start_time = time.time()
        self.acq_start_time_string = time.strftime("%Y%m%d-%H%M%S")

        ''' Check if sample has to be rotated, allow some tolerance '''
        if current_rotation > target_rotation+0.1 or current_rotation < target_rotation-0.1:
            self.sig_go_to_rotation_position_and_wait_until_done.emit()
            self.move_absolute({'theta_abs':target_rotation}, wait_until_done=True)

        self.move_absolute(startpoint, wait_until_done=True)

        self.sig_status_message.emit('Setting Filter & Shutter')
        self.set_shutterconfig(acq['shutterconfig'])
        self.set_filter(acq['filter'], wait_until_done=True)
        self.sig_status_message.emit('Setting Zoom')
        self.set_zoom(acq['zoom'], wait_until_done=False, update_etl=False)
        self.set_intensity(acq['intensity'], wait_until_done=True)
        self.set_laser(acq['laser'], wait_until_done=True, update_etl=False)
        ''' This is for the GUI to update properly, otherwise ETL values for previous laser might be displayed '''
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 1)

        self.sig_state_request.emit({'etl_l_amplitude' : acq['etl_l_amplitude']})
        self.sig_state_request.emit({'etl_r_amplitude' : acq['etl_r_amplitude']})
        self.sig_state_request.emit({'etl_l_offset' : acq['etl_l_offset']})
        self.sig_state_request.emit({'etl_r_offset' : acq['etl_r_offset']})

        self.f_step_generator = acq.get_focus_stepsize_generator()

        self.sig_status_message.emit('Preparing camera: Allocating memory')
        self.sig_prepare_image_series.emit(acq)
        self.prepare_image_series()

        # ''' HICKUP DEBUGGING: Measure z position '''
        # self.z_start_measured = self.state['position']['z_pos']

        self.write_metadata(acq)

    def run_acquisition(self, acq):
        steps = acq.get_image_count()
        self.sig_status_message.emit('Running Acquisition')
        self.open_shutters()

        self.image_acq_start_time = time.time()
        self.image_acq_start_time_string = time.strftime("%Y%m%d-%H%M%S")

        for i in range(steps):
            if self.stopflag is True:
                self.close_image_series()
                self.sig_end_image_series.emit()
                self.sig_finished.emit()
                break
            else:
                self.snap_image_in_series()
                self.sig_add_images_to_image_series.emit()
                #time.sleep(0.02)
                # self.sig_add_images_to_image_series_and_wait_until_done.emit()

                # self.move_relative(acq.get_delta_z_dict(), wait_until_done=True)
                move_dict = acq.get_delta_dict()
                ''' Get the current correct f_step'''
                f_step = self.f_step_generator.__next__()
                if f_step != 0:
                    # print('F step: ', f_step)
                    move_dict.update({'f_rel':f_step})

                self.move_relative(move_dict)

                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 1)
                self.image_count += 1

                ''' Keep track of passed time and predict remaining time '''
                time_passed = time.time() - self.start_time
                time_remaining = self.state['predicted_acq_list_time'] - time_passed

                ''' If the time to set up everything is longer than the predicted 
                acq time, the remaining time turns negative - here a different 
                calcuation should be employed here: '''
                if time_remaining < 0:
                    time_passed = time.time() - self.image_acq_start_time
                    time_remaining = self.state['predicted_acq_list_time'] - time_passed

                self.state['remaining_acq_list_time'] = time_remaining
                framerate = self.image_count / time_passed

                ''' Every 100 images, update the predicted acquisition time '''
                if self.image_count % 100 == 0:
                    framerate = self.image_count / time_passed
                    self.state['predicted_acq_list_time'] = self.total_image_count / framerate
      

                self.send_progress(self.acquisition_count,
                                   self.total_acquisition_count,
                                   i,
                                   steps,
                                   self.total_image_count,
                                   self.image_count,
                                   convert_seconds_to_string(time_passed),
                                   convert_seconds_to_string(time_remaining))

        self.image_acq_end_time = time.time()
        self.image_acq_end_time_string = time.strftime("%Y%m%d-%H%M%S")

        self.close_shutters()

    def close_acquisition(self, acq):

        # ''' HICKUP DEBUGGING '''
        # self.z_end_measured = self.state['position']['z_pos']
        # self.f_end_measured = self.state['position']['f_pos']
        # self.collect_troubleshooting_data(acq)
        # self.append_troubleshooting_info_to_metadata(acq)

        self.sig_status_message.emit('Closing Acquisition: Saving data & freeing up memory')

        if self.stopflag is False:
            # self.move_absolute(acq.get_startpoint(), wait_until_done=True)
            self.close_image_series()
            self.sig_end_image_series.emit()

        self.acq_end_time = time.time()
        self.acq_end_time_string = time.strftime("%Y%m%d-%H%M%S")

        self.append_timing_info_to_metadata(acq)
        self.acquisition_count += 1

    @QtCore.pyqtSlot(str)
    def execute_script(self, script):
        self.sig_update_gui_from_state.emit(True)
        self.state['state']='running_script'
        try:
            exec(script)
        except:
            traceback.print_exc()
        self.sig_finished.emit()
        self.state['state']='idle'
        self.sig_update_gui_from_state.emit(False)

    def lightsheet_alignment_mode(self):
        '''Switches shutters after each image to allow coalignment of both lightsheets'''
        self.stopflag = False
        self.sig_prepare_live.emit()
        '''Needs more careful adjustment of the timing

        TODO: There is no wait period to wait for the shutters to open. Nonetheless, the
        visual of the mode impression is not too bad.
        '''
        while self.stopflag is False:
            self.shutter_left.open()
            self.snap_image()
            self.sig_get_live_image.emit()
            self.shutter_left.close()
            self.shutter_right.open()
            self.snap_image()
            self.sig_get_live_image.emit()
            self.shutter_right.close()
            QtWidgets.QApplication.processEvents()

        self.close_shutters()
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

    def write_line(self, file, key='', value=''):
        ''' Little helper method to write a single line with a key and value for metadata

        Adds a line break at the end.
        '''
        if key !='':
            file.write('['+str(key)+'] '+str(value) + '\n')
        else:
            file.write('\n')

    def write_metadata(self, acq):
        '''
        Writes a metadata.txt file

        Path contains the file to be written
        '''
        path = acq['folder']+'/'+acq['filename']

        metadata_path = os.path.dirname(path)+'/'+os.path.basename(path)+'_meta.txt'

        # print('Metadata_path: ', metadata_path)

        with open(metadata_path,'w') as file:
            self.write_line(file, 'Metadata for file', path)
            self.write_line(file, 'z_stepsize', acq['z_step'])
            self.write_line(file, 'z_planes', acq['planes'])
            self.write_line(file)
            # self.write_line(file, 'COMMENTS')
            # self.write_line(file, 'Comment: ', acq(['comment']))
            # self.write_line(file)
            self.write_line(file, 'CFG')
            self.write_line(file, 'Laser', acq['laser'])
            self.write_line(file, 'Intensity (%)', acq['intensity'])
            self.write_line(file, 'Zoom', acq['zoom'])
            self.write_line(file, 'Pixelsize in um', self.state['pixelsize'])
            self.write_line(file, 'Filter', acq['filter'])
            self.write_line(file, 'Shutter', acq['shutterconfig'])
            self.write_line(file)
            self.write_line(file, 'POSITION')
            self.write_line(file, 'x_pos', acq['x_pos'])
            self.write_line(file, 'y_pos', acq['y_pos'])
            self.write_line(file, 'f_start', acq['f_start'])
            self.write_line(file, 'f_end', acq['f_end'])
            self.write_line(file, 'z_start', acq['z_start'])
            self.write_line(file, 'z_end', acq['z_end'])
            self.write_line(file, 'z_stepsize', acq['z_step'])
            self.write_line(file, 'z_planes', acq.get_image_count())
            self.write_line(file)

            ''' Attention: change to true ETL values ASAP '''
            self.write_line(file,'ETL PARAMETERS')
            self.write_line(file, 'ETL CFG File', self.state['ETL_cfg_file'])
            self.write_line(file,'etl_l_offset', self.state['etl_l_offset'])
            self.write_line(file,'etl_l_amplitude', self.state['etl_l_amplitude'])
            self.write_line(file,'etl_r_offset', self.state['etl_r_offset'])
            self.write_line(file,'etl_r_amplitude', self.state['etl_r_amplitude'])
            self.write_line(file)
            self.write_line(file, 'GALVO PARAMETERS')
            self.write_line(file, 'galvo_l_frequency',self.state['galvo_l_frequency'])
            self.write_line(file, 'galvo_l_amplitude',self.state['galvo_l_amplitude'])
            self.write_line(file, 'galvo_l_offset', self.state['galvo_l_offset'])
            self.write_line(file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
            self.write_line(file, 'galvo_r_offset', self.state['galvo_r_offset'])
            self.write_line(file)
            self.write_line(file, 'CAMERA PARAMETERS')
            self.write_line(file, 'camera_type', self.cfg.camera)
            self.write_line(file, 'camera_exposure', self.state['camera_exposure_time'])
            self.write_line(file, 'camera_line_interval', self.state['camera_line_interval'])
            self.write_line(file, 'x_pixels',self.cfg.camera_parameters['x_pixels'])
            self.write_line(file, 'y_pixels',self.cfg.camera_parameters['y_pixels'])

    def execute_galil_program(self):
        '''Little helper method to execute the program loaded onto the Galil stage:
        allows hand controller to operate'''
        self.sig_state_request.emit({'stage_program' : 'execute'})

    def write_snap_metadata(self, filename):
            path = self.state['snap_folder']+'/'+filename

            metadata_path = os.path.dirname(path)+'/'+os.path.basename(path)+'_meta.txt'

            with open(metadata_path,'w') as file:
                self.write_line(file, 'CFG')
                self.write_line(file, 'Laser', self.state['laser'])
                self.write_line(file, 'Intensity (%)', self.state['intensity'])
                self.write_line(file, 'Zoom', self.state['zoom'])
                self.write_line(file, 'Pixelsize in um', self.state['pixelsize'])
                self.write_line(file, 'Filter', self.state['filter'])
                self.write_line(file, 'Shutter', self.state['shutterconfig'])
                self.write_line(file)
                self.write_line(file, 'POSITION')
                self.write_line(file, 'x_pos', self.state['position']['x_pos'])
                self.write_line(file, 'y_pos', self.state['position']['y_pos'])
                self.write_line(file, 'z_pos', self.state['position']['z_pos'])
                self.write_line(file, 'f_pos', self.state['position']['f_pos'])
                self.write_line(file)

                ''' Attention: change to true ETL values ASAP '''
                self.write_line(file,'ETL PARAMETERS')
                self.write_line(file, 'ETL CFG File', self.state['ETL_cfg_file'])
                self.write_line(file,'etl_l_offset', self.state['etl_l_offset'])
                self.write_line(file,'etl_l_amplitude', self.state['etl_l_amplitude'])
                self.write_line(file,'etl_r_offset', self.state['etl_r_offset'])
                self.write_line(file,'etl_r_amplitude', self.state['etl_r_amplitude'])
                self.write_line(file)
                self.write_line(file, 'GALVO PARAMETERS')
                self.write_line(file, 'galvo_l_frequency',self.state['galvo_l_frequency'])
                self.write_line(file, 'galvo_l_amplitude',self.state['galvo_l_amplitude'])
                self.write_line(file, 'galvo_l_offset', self.state['galvo_l_offset'])
                self.write_line(file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
                self.write_line(file, 'galvo_r_offset', self.state['galvo_r_offset'])
                self.write_line(file)
                self.write_line(file, 'CAMERA PARAMETERS')
                self.write_line(file, 'camera_type', self.cfg.camera)
                self.write_line(file, 'camera_exposure', self.state['camera_exposure_time'])
                self.write_line(file, 'camera_line_interval', self.state['camera_line_interval'])
                self.write_line(file, 'x_pixels',self.cfg.camera_parameters['x_pixels'])
                self.write_line(file, 'y_pixels',self.cfg.camera_parameters['y_pixels'])

    # ''' HICKUP DEBUGGING '''

    # def collect_troubleshooting_data(self, acq):
    #     self.hickup_delta_z = self.z_end_measured - acq['z_end']
    #     self.hickup_delta_f = self.f_end_measured - acq['f_end']
    #     # print('HICKUP Difference: ', self.hickup_delta_z)

    # def append_troubleshooting_info_to_metadata(self, acq):
    #     '''
    #     Appends a metadata.txt file

    #     Path contains the file to be written
    #     '''
    #     path = acq['folder']+'/'+acq['filename']

    #     metadata_path = os.path.dirname(path)+'/'+os.path.basename(path)+'_meta.txt'

    #     with open(metadata_path,'a') as file:
    #         ''' Adding troubleshooting information '''
    #         self.write_line(file)
    #         self.write_line(file, 'TROUBLESHOOTING INFORMATION')
    #         self.write_line(file, 'Z_pos: delta_z end to start after acq', str(self.hickup_delta_z) )
    #         self.write_line(file, 'z_start expected', acq['z_start'])
    #         self.write_line(file, 'z_start measured', str(self.z_start_measured))
    #         self.write_line(file, 'z_end expected', acq['z_end'])
    #         self.write_line(file, 'z_end measured', str(self.z_end_measured))
    #         self.write_line(file, 'F_pos: delta_f end to start after acq', str(self.hickup_delta_f) )
    #         self.write_line(file, 'f_end expected', acq['f_end'])
    #         self.write_line(file, 'f_end measured', str(self.f_end_measured))

    def append_timing_info_to_metadata(self, acq):
        '''
        Appends a metadata.txt file

        Path contains the file to be written
        '''
        path = acq['folder']+'/'+acq['filename']

        metadata_path = os.path.dirname(path)+'/'+os.path.basename(path)+'_meta.txt'

        with open(metadata_path,'a') as file:
            ''' Adding troubleshooting information '''
            self.write_line(file)
            self.write_line(file, 'TIMING INFORMATION')
            self.write_line(file, 'Started stack', self.acq_start_time_string )
            self.write_line(file, 'Started taking images', self.image_acq_start_time_string )
            self.write_line(file, 'Stopped taking images', self.image_acq_end_time_string )
            self.write_line(file, 'Stopped stack', self.acq_end_time_string )
            self.write_line(file, 'Frame rate:', str(acq.get_image_count()/(self.image_acq_end_time-self.image_acq_start_time)))

    @QtCore.pyqtSlot(str)
    def send_status_message_to_gui(self, string):
        self.sig_status_message.emit(string)

    def list_to_string_with_carriage_return(self, input_list):
        mystring = ''
        for i in input_list:
            mystring = mystring + ' \n ' + i    
        return mystring