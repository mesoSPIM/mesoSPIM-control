'''
Core for the mesoSPIM project
=============================
'''

import numpy as np
import time
from scipy import signal
import csv
import traceback

'''PyQt5 Imports'''
from PyQt5 import QtWidgets, QtCore, QtGui

'''National Instruments Imports'''
# import nidaqmx
# from nidaqmx.constants import AcquisitionType, TaskMode
# from nidaqmx.constants import LineGrouping, DigitalWidthUnits
# from nidaqmx.types import CtrTime

''' Import mesoSPIM modules '''
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .devices.shutters.NI_Shutter import NI_Shutter
from .mesoSPIM_Camera import mesoSPIM_HamamatsuCamera
from .devices.lasers.mesoSPIM_LaserEnabler import mesoSPIM_LaserEnabler
from .mesoSPIM_Serial import mesoSPIM_Serial
from .mesoSPIM_WaveFormGenerator import mesoSPIM_WaveFormGenerator

class mesoSPIM_Core(QtCore.QObject):
    '''This class is the pacemaker of a mesoSPIM

    Signals it can send:

    '''

    sig_finished = QtCore.pyqtSignal()

    sig_update_gui_from_state = QtCore.pyqtSignal(bool)

    sig_state_request = QtCore.pyqtSignal(dict)
    sig_state_request_and_wait_until_done = QtCore.pyqtSignal(dict)
    sig_position = QtCore.pyqtSignal(dict)
    
    sig_progress = QtCore.pyqtSignal(dict)

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

        self.parent.sig_move_relative.connect(lambda dict: self.move_relative(dict))
        self.parent.sig_move_relative_and_wait_until_done.connect(lambda dict: self.move_relative(dict, wait_until_done=True))
        self.parent.sig_move_absolute.connect(lambda dict: self.move_absolute(dict))
        self.parent.sig_move_absolute_and_wait_until_done.connect(lambda dict: self.move_absolute(dict, wait_until_done=True))
        self.parent.sig_zero_axes.connect(lambda list: self.zero_axes(list))
        self.parent.sig_unzero_axes.connect(lambda list: self.unzero_axes(list))
        self.parent.sig_stop_movement.connect(self.stop_movement)
        self.parent.sig_load_sample.connect(self.sig_load_sample.emit)
        self.parent.sig_unload_sample.connect(self.sig_unload_sample.emit)

        ''' Set the Camera thread up '''
        self.camera_thread = QtCore.QThread()
        self.camera_worker = mesoSPIM_HamamatsuCamera(self)
        self.camera_worker.moveToThread(self.camera_thread)

        ''' Set the serial thread up '''
        self.serial_thread = QtCore.QThread()
        self.serial_worker = mesoSPIM_Serial(self)
        self.serial_worker.moveToThread(self.serial_thread)
        self.serial_worker.sig_position.connect(lambda dict: self.sig_position.emit(dict))

        ''' Start the threads '''
        self.camera_thread.start()
        self.serial_thread.start()

        ''' Setting waveform generation up '''
        self.waveformer = mesoSPIM_WaveFormGenerator(self)
        self.waveformer.sig_update_gui_from_state.connect(lambda flag: self.sig_update_gui_from_state.emit(flag))
        self.sig_state_request.connect(self.waveformer.state_request_handler)
        self.sig_state_request_and_wait_until_done.connect(self.waveformer.state_request_handler)

        ''' Setting the shutters up '''
        left_shutter_line = self.cfg.shutterdict['shutter_left']
        right_shutter_line = self.cfg.shutterdict['shutter_right']

        self.shutter_left = NI_Shutter(left_shutter_line)
        self.shutter_right = NI_Shutter(right_shutter_line)

        self.shutter_left.close()
        self.shutter_right.close()
        self.state['shutterstate'] = False

        ''' Setting the laserenabler up '''
        self.laserenabler = mesoSPIM_LaserEnabler(self.cfg.laserdict)

        self.state['state']='idle'

        self.stopflag = False

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
            print('Core Thread: State request: Key: ', key, ' Value: ', value)
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
                       'intensity',
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
                       'camera_pulse_%'):
                self.sig_state_request.emit({key : value})
            
    def set_state(self, state):
        if state == 'live':
            self.state['state']='live'
            self.sig_state_request.emit({'state':'live'})
            self.live()
        
        elif state == 'run_selected_acquisition':
            self.state['run_selected_acquisition']
            self.sig_state_request.emit({'state':'run_selected_acquisition'})

        elif state == 'run_acquisition_list':
            self.state['run_acquisition_list']
            self.sig_state_request.emit({'state':'run_acquisition_list'})

        elif state == 'idle':
            print('Core: Stopping requested')
            self.sig_state_request.emit({'state':'idle'})
            self.stop()

    def stop(self):
        self.stopflag = True
        ''' This stopflag is a bit risky, needs to be updated'''
        self.state['state']='idle'
        self.sig_finished.emit()

    def send_progress(self,
                      cur_acq,
                      tot_acqs,
                      cur_image,
                      images_in_acq,
                      total_image_count,
                      image_counter):

        dict = {'current_acq':cur_acq,
                'total_acqs' :tot_acqs,
                'current_image_in_acq':cur_image,
                'images_in_acq': images_in_acq,
                'total_image_count':total_image_count,
                'image_counter':image_counter,
        }
        self.sig_progress.emit(dict)

    def set_filter(self, filter, wait_until_done=False):
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'filter' : filter})
        else:
            self.sig_state_request.emit({'filter' : filter})

    def set_zoom(self, zoom, wait_until_done=False):
        if wait_until_done:
            self.sig_state_request_and_wait_until_done.emit({'zoom' : zoom})
        else:
            self.sig_state_request.emit({'zoom' : zoom})

    def set_laser(self, laser):
        self.sig_state_request.emit({'laser':laser})

    def set_intensity(self, intensity):
        self.sig_state_request.emit({'intensity':intensity})

    def set_camera_exposure_time(self, time):
        self.sig_state_request.emit({'camera_exposure_time' : time})

    def set_camera_line_interval(self, time):
        self.sig_state_request.emit({'camera_line_interval' : time})

    def move_relative(self, dict, wait_until_done=False):
        if wait_until_done:
            self.sig_move_relative_and_wait_until_done.emit(dict)
        else:
            self.sig_move_relative.emit(dict)

    def move_absolute(self, dict, wait_until_done=False):
        if wait_until_done:
            self.sig_move_absolute_and_wait_until_done.emit(dict)
        else:
            self.sig_move_absolute.emit(dict)

    def zero_axes(self, list):
        self.sig_zero_axes.emit(list)

    def unzero_axes(self, list):
        self.sig_unzero_axes.emit(list)

    def stop_movement(self):
        self.sig_stop_movement.emit()

    def set_shutterconfig(self, shutterconfig):
        self.state['shutterconfig'] = shutterconfig

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
   
    def close_shutters(self):
        self.shutter_left.close()
        self.shutter_right.close()
        self.state['shutterstate'] = False

    '''
    Execution code for major imaging modes starts here
    '''
    
    def live(self):
        for i in range(25):
            time.sleep(0.1)
            QtWidgets.QApplication.processEvents()
        self.sig_finished.emit()

    
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
