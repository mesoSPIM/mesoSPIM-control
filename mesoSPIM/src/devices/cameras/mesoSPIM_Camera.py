'''
mesoSPIM Camera class, intended to run in its own thread
'''
import numpy as np

from PyQt5 import QtCore, QtWidgets, QtGui

class mesoSPIM_Camera(QtCore.QObject):
    sig_camera_status = pyqtSignal(str)
    sig_frame = pyqtSignal(np.ndarray)

    def __init__(self, parent = None):
        super().__init__()

        self.stopflag = False

    def stop(self):
        ''' Stops acquisition '''
        self.stopflag = True

    def set_exposure_time(self, time):
        '''
        Sets the exposure time in seconds

        Args:
            time (float): exposure time to set
        '''
        pass

    def set_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        pass

    def prepare_image_series(self):
        pass

    def add_images_to_series(self):
        pass

    def end_image_series(self):
        pass

class mesoSPIM_DemoCamera(mesoSPIM_Camera):
    pass

class mesoSPIM_HamamatsuCamera(mesoSPIM_Camera):
    pass
