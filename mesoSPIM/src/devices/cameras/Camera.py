from abc import ABC, abstractmethod
from PyQt5 import QtCore
import numpy as np

#TODO: make us of coroutines?
class Camera(QtCore.QObject): #, ABC
    sig_camera_status = QtCore.pyqtSignal(str)
    sig_camera_frame = QtCore.pyqtSignal(np.ndarray)
    sig_finished = QtCore.pyqtSignal()

    sig_state_updated = QtCore.pyqtSignal()

    def __init__(self, parent = None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.parent.sig_prepare_image_series.connect(self.prepare_image_series, type=3)
        self.parent.sig_add_images_to_image_series.connect(self.add_images_to_series)
        self.parent.sig_add_images_to_image_series_and_wait_until_done.connect(self.add_images_to_series, type=3)
        self.parent.sig_end_image_series.connect(self.end_image_series, type=3)

        self.parent.sig_prepare_live.connect(self.prepare_live, type = 3)
        self.parent.sig_get_live_image.connect(self.get_live_image)
        self.parent.sig_end_live.connect(self.end_live, type=3)

        self.sig_camera_status.connect(lambda status: print(status))

    
    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            print('Camera Thread: State request: Key: ', key, ' Value: ', value)
            '''
            The request handling is done with exec() to write fewer lines of
            code.
            '''
            if key in ('camera_exposure_time','camera_line_interval','state'):
                exec('self.set_'+key+'(value)')

    @abstractmethod
    def set_state(self, requested_state):
        pass
    @abstractmethod
    def open(self):
        pass
    @abstractmethod
    def close(self):
        pass
    @abstractmethod
    def stop(self):
        pass
    @abstractmethod
    def set_camera_exposure_time(self, time):
        pass
    @abstractmethod
    def set_camera_line_interval(self, time):
        pass
    @abstractmethod
    def prepare_image_series(self, acq):
        pass
    @abstractmethod
    def add_images_to_series(self):
        pass
    @abstractmethod
    def end_image_series(self):
        pass
    @abstractmethod
    def snap_image(self):
        pass
    @abstractmethod
    def prepare_live(self):
        pass
    @abstractmethod
    def get_live_image(self):
        pass
    @abstractmethod
    def end_live(self):
        pass
