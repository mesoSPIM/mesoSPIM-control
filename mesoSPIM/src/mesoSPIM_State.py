'''
mesoSPIM State class
'''
import threading

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker
import logging
logger = logging.getLogger(__name__)
from .utils.acquisitions import AcquisitionList

class mesoSPIM_StateSingleton(QObject):
    '''
    Singleton object containing the whole mesoSPIM state.

    Only classes which control.

    Access to attributes is mutex-locked to allow access from multiple threads.

    If more than one state parameter should be set at the same time, the 
    set_parameter 
    '''

    instance = None
    _lock = threading.Lock()
    sig_updated = pyqtSignal()
    mutex = QMutex()

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            with cls._lock:
                cls.instance = super().__new__(cls, *args, **kwargs)
        return cls.instance

    def __init__(self):
        super().__init__()
        self._state_dict = {
                        'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script', 'run_acquisition_list', 'run_selected_acquisition', 'lightsheet_alignment_mode'
                        'acq_list' : AcquisitionList(),
                        'selected_row': -2,
                        'samplerate' : 100000,
                        'sweeptime' : 0.2,
                        'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0}, # relative position, including user-specified offset
                        'position_absolute' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0}, 
                        'ttl_movement_enabled_during_acq' : False,
                        'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
                        'filename' : 'file.tif',
                        'folder' : 'tmp',
                        'snap_folder' : 'tmp',
                        'file_prefix' : '',
                        'file_suffix' : '000001',
                        'zoom' : '2x', # TODO: proper zoom initialization. If this zoom is not in config file, ETL parameters do not update at the startup
                        'pixelsize' : 1.0,
                        'laser' : '488 nm',
                        'max_laser_voltage':1,
                        'intensity' : 10,
                        'shutterstate':False, # Is the shutter open or not?
                        'shutterconfig':'Right', # Can be "Left", "Right","Both","Interleaved"
                        'laser_interleaving':False,
                        'filter' : 'Empty',
                        'etl_l_delay_%' : 7.5,
                        'etl_l_ramp_rising_%' : 85,
                        'etl_l_ramp_falling_%' : 2.5,
                        'etl_l_amplitude' : 0.7,
                        'etl_l_offset' : 2.3,
                        'etl_r_delay_%' : 2.5,
                        'etl_r_ramp_rising_%' : 5,
                        'etl_r_ramp_falling_%' : 85,
                        'etl_r_amplitude' : 0.65,
                        'etl_r_offset' : 2.36,
                        'galvo_l_frequency' : 99.9,
                        'galvo_l_amplitude' : 6,
                        'galvo_l_offset' : 0,
                        'galvo_l_duty_cycle' : 50,
                        'galvo_l_phase' : np.pi/2,
                        'galvo_r_frequency' : 99.9,
                        'galvo_r_amplitude' : 6,
                        'galvo_r_offset' : 0,
                        'galvo_r_duty_cycle' : 50,
                        'galvo_r_phase' : np.pi/2,
                        'laser_l_delay_%' : 10,
                        'laser_l_pulse_%' : 87,
                        'laser_l_max_amplitude_%' : 100,
                        'laser_r_delay_%' : 10,
                        'laser_r_pulse_%' : 87,
                        'laser_r_max_amplitude_%' : 100,
                        'camera_delay_%' : 10,
                        'camera_pulse_%' : 1,
                        'camera_exposure_time':0.02,
                        'camera_line_interval':0.000075,
                        'camera_display_live_subsampling': 1,
                        'camera_display_acquisition_subsampling': 2,
                        'camera_binning':'1x1',
                        'camera_sensor_mode':'ASLM',
                        'current_framerate':2.5,
                        'predicted_acq_list_time':1,
                        'package_directory': '',
                        'galvo_amp_scale_w_zoom': False,
                        'moving_to_target': False, # A dirty way to know if moving with wait_untile_done=True is finished from another thread
                        }

    def __len__(self):
        return len(self._state_dict) 
    
    def __setitem__(self, key, value):
        '''
        Custom __setitem__ method to allow mutexed access to 
        a state parameter. 

        After the state has been changed, the updated signal is emitted.
        '''
        with QMutexLocker(self.mutex):
            self._state_dict.__setitem__(key, value)
            logger.debug('State changed: {} = {}'.format(key, value))
        self.sig_updated.emit()

    def __getitem__(self, key):
        '''
        Custom __getitem__ method to allow mutexed access to 
        a state parameter.

        To avoid the state being updated while a parameter is read.
        '''

        with QMutexLocker(self.mutex):
            return self._state_dict.__getitem__(key)

    def set_parameters(self, dict):
        '''
        Sometimes, several parameters should be set at once 
        without allowing the state being updated while a parameter is read.
        '''
        with QMutexLocker(self.mutex):
            for key, value in dict.items():
                self._state_dict.__setitem__(key, value)
        self.sig_updated.emit()

    def get_parameter_dict(self, list):
        '''
        For a list of keys, get a state dict with the current values back.

        All the values are read out under a QMutexLocker so that 
        the state cannot be updated at the same time.
        '''
        return_dict = {}

        with QMutexLocker(self.mutex):
            for key in list:
                return_dict[key] = self._state_dict.__getitem__(key)
        
        return return_dict

    def get_parameter_list(self, list):
        '''
        For a list of keys, get a state list with the current values back.

        This is especially useful for unpacking.

        All the values are read out under a QMutexLocker so that 
        the state cannot be updated at the same time.
        '''
        return_list = []

        with QMutexLocker(self.mutex):
            for key in list:
                return_list.append(self._state_dict.__getitem__(key))
        
        return return_list

    def block_signals(self, boolean):
        self.blockSignals(boolean)
        