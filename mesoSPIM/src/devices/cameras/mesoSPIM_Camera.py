'''
mesoSPIM Camera class, intended to run in its own thread
'''
import numpy as np

from PyQt5 import QtCore, QtWidgets, QtGui

from .hamamatsu import hamamatsu_camera as cam

class mesoSPIM_HamamatsuCamera(QtCore.QObject):
    sig_camera_status = QtCore.pyqtSignal(str)
    sig_camera_frame = QtCore.pyqtSignal(np.ndarray)
    sig_finished = QtCore.pyqtSignal()
    sig_state_updated = QtCore.pyqtSignal()

    def __init__(self, parent = None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg

        self.stopflag = False

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']
        self.x_pixel_size_in_microns = self.cfg.camera_parameters['x_pixel_size_in_microns']
        self.y_pixel_size_in_microns = self.cfg.camera_parameters['y_pixel_size_in_microns']

        self.camera_exposure_time = self.cfg.startup['camera_exposure_time']
        self.camera_line_interval = self.cfg.startup['camera_line_interval']

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.sig_camera_status.connect(lambda status: print(status))

        ''' Hamamatsu-specific code '''
        self.camera_id = self.cfg.camera_parameters['camera_id']

        if self.cfg.camera == 'HamamatsuOrcaFlash':
            self.hcam = cam.HamamatsuCameraMR(camera_id=self.camera_id)
            ''' Debbuging information '''
            print("camera 0 model:", self.hcam.getModelInfo(self.camera_id))

            ''' Ideally, the Hamamatsu Camera properties should be set in this order '''
            ''' mesoSPIM mode parameters '''
            self.hcam.setPropertyValue("sensor_mode", self.cfg.camera_parameters['sensor_mode'])

            ''' mesoSPIM mode parameters: OLD '''
            # self.hcam.setPropertyValue("sensor_mode", 12) # 12 for progressive

            self.hcam.setPropertyValue("defect_correct_mode", self.cfg.camera_parameters['defect_correct_mode'])
            self.hcam.setPropertyValue("exposure_time", self.camera_exposure_time)
            self.hcam.setPropertyValue("binning", self.cfg.camera_parameters['binning'])
            self.hcam.setPropertyValue("readout_speed", self.cfg.camera_parameters['readout_speed'])

            self.hcam.setPropertyValue("trigger_active", self.cfg.camera_parameters['trigger_active'])
            self.hcam.setPropertyValue("trigger_mode", self.cfg.camera_parameters['trigger_mode']) # it is unclear if this is the external lightsheeet mode - how to check this?
            self.hcam.setPropertyValue("trigger_polarity", self.cfg.camera_parameters['trigger_polarity']) # positive pulse
            self.hcam.setPropertyValue("trigger_source", self.cfg.camera_parameters['trigger_source']) # external
            self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)

    def __del__(self):
        self.hcam.shutdown()

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

    def set_state_parameter(self, key, value):
        '''
        Sets the state of the parent (in most cases, mesoSPIM_MainWindow)

        In order to do this, a QMutexLocker has to be acquired

        Args:
            key (str): State dict key
            value (str, float, int): Value to set
        '''
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                self.parent.state[key]=value
            else:
                print('Set state parameters failed: Key ', key, 'not in state dictionary!')
        self.sig_state_updated.emit()

    def get_state_parameter(self, key):
        with QtCore.QMutexLocker(self.parent.state_mutex):
            if key in self.parent.state:
                return self.parent.state[key]
            else:
                print('Getting state parameter failed: Key ', key, 'not in state dictionary!')

    def set_state(self, requested_state):
        if requested_state == 'live':
            self.live()
        elif requested_state == 'idle':
            self.stop()

    def open(self):
        pass

    def close(self):
        pass

    @QtCore.pyqtSlot()
    def stop(self):
        ''' Stops acquisition '''
        self.stopflag = True

    def set_camera_exposure_time(self, time):
        '''
        Sets the exposure time in seconds

        Args:
            time (float): exposure time to set
        '''
        self.camera_exposure_time = time
        self.hcam.setPropertyValue("exposure_time", time)
        self.set_state_parameter('camera_exposure_time', time)

    def set_camera_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        self.camera_line_interval = time
        self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)
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
        '''
        camera running in live mode
        '''

        self.stopflag = False
        self.hcam.setACQMode(mode = "run_till_abort")
        self.hcam.startAcquisition()

        i = 0
        while self.stopflag is False:
            [frames, dims] = self.hcam.getFrames()

            for aframe in frames:
                image = aframe.getData()
                image = np.reshape(image, (-1, 2048))
                image = np.rot90(image)

                self.sig_camera_frame.emit(image)

                i += 1

                self.sig_camera_status.emit(str(i))

                QtWidgets.QApplication.processEvents()

        self.hcam.stopAcquisition()

        self.sig_finished.emit()

# class mesoSPIM_DemoCamera(mesoSPIM_Camera):
#     def __init__(self, config, parent = None):
#         super().__init__(config, parent)
