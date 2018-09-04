'''
mesoSPIM Camera class, intended to run in its own thread
'''
import numpy as np

from PyQt5 import QtCore, QtWidgets, QtGui

class mesoSPIM_Camera(QtCore.QObject):
    sig_camera_status = QtCore.pyqtSignal(str)
    sig_frame = QtCore.pyqtSignal(np.ndarray)

    def __init__(self, config, parent = None):
        super().__init__()

        self.parent = parent

        self.stopflag = False

        self.x_pixels = config.camera_parameters['x_pixels']
        self.y_pixels = config.camera_parameters['y_pixels']

    def open(self):
        pass

    def close(self):
        pass

    def stop(self):
        ''' Stops acquisition '''
        self.stopflag = True

    def set_state_parameter(self, key, value):
        '''
        Sets the mesoSPIM state

        In order to do this, a QMutexLocker has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
            else:
                print('Setting state parameter failed: Key ', key, 'not in state dictionary!')

    def get_state_parameter(self, key):
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                return self.parent.state[key]
            else:
                print('Getting state parameter failed: Key ', key, 'not in state dictionary!')

    def set_exposure_time(self, time):
        '''
        Sets the exposure time in seconds

        Args:
            time (float): exposure time to set
        '''
        self.set_state_parameter('camera_exposure', time)

    def set_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        self.set_state_parameter('camera_line_interval', time)

    def prepare_image_series(self):
        pass

    def add_images_to_series(self):
        pass

    def end_image_series(self):
        pass

    def snap_image(self):
        pass

    def live(self):
        pass

class mesoSPIM_DemoCamera(mesoSPIM_Camera):
    def __init__(self, config, parent = None):
        super().__init__(config, parent)

class mesoSPIM_HamamatsuCamera(mesoSPIM_Camera):
    def __init__(self, config, parent = None):
        super().__init__(config, parent)

        # from devices.camera import hamamatsu_camera as self.cam
