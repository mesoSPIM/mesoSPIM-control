'''
mesoSPIM State class
'''
import numpy as np
from PyQt5 import QtCore

from .utils.acquisitions import AcquisitionList

class mesoSPIM_StateSingleton():
    '''
    Singleton object containing the whole mesoSPIM state.

    Only classes which control.

    Access to attributes is mutex-locked to allow access from multiple threads.

    If more than one state parameter should be set at the same time, the 
    set_parameter 
    '''

    instance = None

    def __new__(cls):
        if not mesoSPIM_StateSingleton.instance:
            mesoSPIM_StateSingleton.instance = mesoSPIM_StateSingleton.__StateObject()

        return mesoSPIM_StateSingleton.instance

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def __setattr__(self, name):
        return setattr(self.instance, name)

    class __StateObject(QtCore.QObject):
        sig_updated = QtCore.pyqtSignal()
        mutex = QtCore.QMutex()

        def __init__(self):
            super().__init__()
            self._state_dict = {
                            'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
                            'acq_list' : AcquisitionList(),
                            'selected_row': -2,
                            'samplerate' : 100000,
                            'sweeptime' : 0.2,
                            'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
                            'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
                            'filename' : 'file.raw',
                            'folder' : 'tmp',
                            'snap_folder' : 'tmp',
                            'file_prefix' : '',
                            'file_suffix' : '000001',
                            'zoom' : '1x',
                            'pixelsize' : 6.55,
                            'laser' : '488 nm',
                            'max_laser_voltage':10,
                            'intensity' : 10,
                            'shutterstate':False, # Is the shutter open or not?
                            'shutterconfig':'Right', # Can be "Left", "Right","Both","Interleaved"
                            'laser_interleaving':False,
                            'filter' : '405-488-561-640-Quadrupleblock',
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
                            'camera_display_snap_subsampling': 1, 
                            'camera_display_acquisition_subsampling': 2,
                            'camera_binning':'1x1',
                            'camera_sensor_mode':'ASLM',
                            'current_framerate':3.8,
                            'predicted_acq_list_time':1,
                            'remaining_acq_list_time':1,
                            }

        def __len__(self):
            return len(self._state_dict) 
        
        def __setitem__(self, key, value):
            '''
            Custom __setitem__ method to allow mutexed access to 
            a state parameter. 

            After the state has been changed, the updated signal is emitted.
            '''
            with QtCore.QMutexLocker(self.mutex):
                self._state_dict.__setitem__(key, value)
            self.sig_updated.emit()

        def __getitem__(self, key):
            '''
            Custom __getitem__ method to allow mutexed access to 
            a state parameter.

            To avoid the state being updated while a parameter is read.
            '''

            with QtCore.QMutexLocker(self.mutex):
                return self._state_dict.__getitem__(key)

        def set_parameters(self, dict):
            '''
            Sometimes, several parameters should be set at once 
            without allowing the state being updated while a parameter is read.
            '''
            with QtCore.QMutexLocker(self.mutex):
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

            with QtCore.QMutexLocker(self.mutex):
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

            with QtCore.QMutexLocker(self.mutex):
                for key in list:
                    return_list.append(self._state_dict.__getitem__(key))
            
            return return_list

        def block_signals(self, boolean):
            self.blockSignals(boolean)
        