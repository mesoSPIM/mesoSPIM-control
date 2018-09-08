'''
mesoSPIM State class
'''
import numpy as np
from PyQt5 import QtCore

class mesoSPIM_StateModel(QtCore.QObject):
    '''This class contains the microscope state

    Any access to this global state should only be done via signals sent by 
    the responsible class for actually causing that state change in hardware.

    '''
    sig_state_model_updated = QtCore.pyqtSignal()

    def __init__(self, parent):
        super().__init__()

        self.cfg = parent.cfg
        self.state = self.cfg.startup

    @QtCore.pyqtSlot(dict)
    def set_state(self, dict):
        for key, value in dict.items():
            if key in self.state.keys():
                self.state[key]=value
                if key != 'position':
                    self.sig_state_model_updated.emit()
            else:
                raise NameError('StateModel: Key not found: ')


    def get_state_parameter(self, key):
        if key in self.state.keys():
            return self.state[key]
        else:
            print('Key ', key, ' not in state dict')

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
        updated = QtCore.pyqtSignal()
        mutex = QtCore.QMutex()

        def __init__(self):
            super().__init__()
            self._state_dict = {
                            'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
                            'samplerate' : 100000,
                            'sweeptime' : 0.2,
                            'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
                            'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
                            'filepath' : '/tmp/file.raw',
                            'folder' : '/tmp/',
                            'file_prefix' : '',
                            'start_number' : 1,
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
                            'laser_l_max_amplitude' : 100,
                            'laser_r_delay_%' : 10,
                            'laser_r_pulse_%' : 87,
                            'laser_r_max_amplitude' : 100,
                            'camera_delay_%' : 10,
                            'camera_pulse_%' : 1,
                            'camera_exposure_time':0.02,
                            'camera_line_interval':0.000075,}

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
                self.updated.emit()

        def __getitem__(self, key):
            '''
            Custom __getitem__ method to allow mutexed access to 
            a state parameter.

            To avoid the state being updated while a parameter is read
            '''

            with QtCore.QMutexLocker(self.mutex):
                return self._state_dict.__getitem__(key)

        def set_parameters(self, dict):
            '''
            Sometimes, a 
            '''
            with QtCore.QMutexLocker(self.mutex):
                for key, value in dict.items():
                    self._state_dict.__setitem__(key, value)
                self.updated.emit()

        def get_parameters(self, list):
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
        