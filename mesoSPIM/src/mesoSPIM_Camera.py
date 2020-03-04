'''
mesoSPIM Camera class, intended to run in its own thread
'''
import os
import time
import numpy as np

import tifffile

import logging
logger = logging.getLogger(__name__)

from PyQt5 import QtCore, QtWidgets, QtGui
'''
try:
    from .devices.cameras.hamamatsu import hamamatsu_camera as cam
except:
    logger.info('Error: Hamamatsu camera could not be imported')
'''
from .mesoSPIM_State import mesoSPIM_StateSingleton
from .utils.acquisitions import AcquisitionList, Acquisition

class mesoSPIM_Camera(QtCore.QObject):
    '''Top-level class for all cameras'''
    sig_camera_frame = QtCore.pyqtSignal(np.ndarray)
    sig_finished = QtCore.pyqtSignal()
    sig_update_gui_from_state = QtCore.pyqtSignal(bool)
    sig_status_message = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        self.stopflag = False

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']
        self.x_pixel_size_in_microns = self.cfg.camera_parameters['x_pixel_size_in_microns']
        self.y_pixel_size_in_microns = self.cfg.camera_parameters['y_pixel_size_in_microns']

        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.camera_line_interval = self.cfg.startup['camera_line_interval']
        self.camera_exposure_time = self.cfg.startup['camera_exposure_time']

        self.camera_display_live_subsampling = self.cfg.startup['camera_display_live_subsampling']
        self.camera_display_snap_subsampling = self.cfg.startup['camera_display_snap_subsampling']
        self.camera_display_acquisition_subsampling = self.cfg.startup['camera_display_acquisition_subsampling']

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.parent.sig_prepare_image_series.connect(self.prepare_image_series, type=3)
        self.parent.sig_add_images_to_image_series.connect(self.add_images_to_series)
        self.parent.sig_add_images_to_image_series_and_wait_until_done.connect(self.add_images_to_series, type=3)
        self.parent.sig_end_image_series.connect(self.end_image_series, type=3)

        self.parent.sig_prepare_live.connect(self.prepare_live, type = 3)
        self.parent.sig_get_live_image.connect(self.get_live_image)
        self.parent.sig_get_snap_image.connect(self.snap_image)
        self.parent.sig_end_live.connect(self.end_live, type=3)

        ''' Set up the camera '''
        if self.cfg.camera == 'HamamatsuOrca':
            self.camera = mesoSPIM_HamamatsuCamera(self)
        elif self.cfg.camera == 'PhotometricsIris15':
            self.camera = mesoSPIM_PhotometricsCamera(self)
        elif self.cfg.camera == 'DemoCamera':
            self.camera = mesoSPIM_DemoCamera(self)

        self.camera.open_camera()

    def __del__(self):
        try:
            self.camera.close_camera()
        except Exception as error:
            logger.info('Error while closing the camera:', str(error))

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        for key, value in zip(dict.keys(),dict.values()):
            # print('Camera Thread: State request: Key: ', key, ' Value: ', value)
            '''
            The request handling is done with exec() to write fewer lines of
            code.
            '''
            if key in ('camera_exposure_time',
                        'camera_line_interval',
                        'state',
                        'camera_display_live_subsampling',
                        'camera_display_snap_subsampling',
                        'camera_display_acquisition_subsampling',
                        'camera_binning'):
                exec('self.set_'+key+'(value)')
            # Log Thread ID during Live: just debugging code
            elif key == 'state':
                if value == 'live':
                    logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    def set_state(self, value):
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
        self.camera.set_exposure_time(time)
        self.camera_exposure_time = time
        self.sig_update_gui_from_state.emit(True)
        self.state['camera_exposure_time'] = time
        self.sig_update_gui_from_state.emit(False)

    def set_camera_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        self.camera.set_line_interval(time)
        self.camera_line_interval = time
        self.sig_update_gui_from_state.emit(True)
        self.state['camera_line_interval'] = time
        self.sig_update_gui_from_state.emit(False)

    def set_camera_display_live_subsampling(self, factor):
        self.camera_display_live_subsampling = factor

    def set_camera_display_snap_subsampling(self, factor):
        self.camera_display_snap_subsampling = factor

    def set_camera_display_acquisition_subsampling(self, factor):
        self.camera_display_acquisition_subsampling = factor

    def set_camera_binning(self, value):
        self.camera.set_binning(value)

    @QtCore.pyqtSlot(Acquisition)
    def prepare_image_series(self, acq):
        '''
        Row is a row in a AcquisitionList
        '''
        logger.info('Camera: Preparing Image Series')
        #print('Cam: Preparing Image Series')
        self.stopflag = False

        ''' TODO: Needs cam delay, sweeptime, QTimer, line delay, exp_time '''

        self.folder = acq['folder']
        self.filename = acq['filename']
        self.path = self.folder+'/'+self.filename
        
        logger.info(f'Camera: Save path: {self.path}')
        self.z_start = acq['z_start']
        self.z_end = acq['z_end']
        self.z_stepsize = acq['z_step']
        self.max_frame = acq.get_image_count()

        self.processing_options_string = acq['processing']

        self.fsize = self.x_pixels*self.y_pixels

        self.xy_stack = np.memmap(self.path, mode = "write", dtype = np.uint16, shape = self.fsize * self.max_frame)

        self.camera.initialize_image_series()
        self.cur_image = 0
        logger.info(f'Camera: Finished Preparing Image Series')
        self.start_time = time.time()

    @QtCore.pyqtSlot()
    def add_images_to_series(self):
        if self.cur_image == 0:
            logger.info('Thread ID during add images: '+str(int(QtCore.QThread.currentThreadId())))

        if self.stopflag is False:
            if self.cur_image < self.max_frame:
                # logger.info('self.cur_image + 1: '+str(self.cur_image + 1))
                images = self.camera.get_images_in_series()
                for image in images:
                    image = np.rot90(image)
                    self.sig_camera_frame.emit(image[0:self.x_pixels:self.camera_display_acquisition_subsampling,0:self.y_pixels:self.camera_display_acquisition_subsampling])
                    image = image.flatten()
                    self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image
                    self.cur_image += 1

    @QtCore.pyqtSlot()
    def end_image_series(self):
        if self.stopflag is False:
            if self.processing_options_string != '':
                if self.processing_options_string == 'MAX':
                    self.sig_status_message.emit('Doing Max Projection')
                    logger.info('Camera: Started Max Projection of '+str(self.max_frame)+' Images')
                    stackview = self.xy_stack.view()
                    stackview.shape = (self.max_frame, self.x_pixels, self.y_pixels)
                    max_proj = np.max(stackview, axis=0)
                    filename = 'MAX_' +self.filename + '.tif'
                    path = self.folder+'/'+filename
                    tifffile.imsave(path, max_proj, photometric='minisblack')
                    logger.info('Camera: Saved Max Projection')
                    self.sig_status_message.emit('Done with image processing')

        try:
            self.camera.close_image_series()
            del self.xy_stack
        except:
            pass

        self.end_time =  time.time()
        framerate = (self.cur_image + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Framerate: {framerate}')
        self.sig_finished.emit()

    @QtCore.pyqtSlot()
    def snap_image(self):
        image = self.camera.get_image()
        image = np.rot90(image)

        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = timestr + '.tif'

        path = self.state['snap_folder']+'/'+filename

        self.sig_camera_frame.emit(image[0:self.x_pixels:self.camera_display_snap_subsampling,0:self.y_pixels:self.camera_display_snap_subsampling])

        tifffile.imsave(path, image, photometric='minisblack')

    @QtCore.pyqtSlot()
    def prepare_live(self):
        self.camera.initialize_live_mode()

        self.live_image_count = 0

        self.start_time = time.time()
        logger.info('Camera: Preparing Live Mode')
        logger.info('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

    @QtCore.pyqtSlot()
    def get_live_image(self):
        images = self.camera.get_live_image()

        for image in images:
            image = np.rot90(image)

            self.sig_camera_frame.emit(image[0:self.x_pixels:self.camera_display_live_subsampling,0:self.y_pixels:self.camera_display_live_subsampling])
            self.live_image_count += 1
            #self.sig_camera_status.emit(str(self.live_image_count))

    @QtCore.pyqtSlot()
    def end_live(self):
        self.camera.close_live_mode()
        self.end_time =  time.time()
        framerate = (self.live_image_count + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Finished Live Mode: Framerate: {framerate}')

class mesoSPIM_GenericCamera(QtCore.QObject):
    ''' Generic mesoSPIM camera class meant for subclassing.'''

    def __init__(self, parent = None):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        self.stopflag = False

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']
        self.x_pixel_size_in_microns = self.cfg.camera_parameters['x_pixel_size_in_microns']
        self.y_pixel_size_in_microns = self.cfg.camera_parameters['y_pixel_size_in_microns']

        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.camera_line_interval = self.cfg.startup['camera_line_interval']
        self.camera_exposure_time = self.cfg.startup['camera_exposure_time']

    def open_camera(self):
        pass

    def close_camera(self):
        pass

    def set_exposure_time(self, time):
        self.camera_exposure_time = time

    def set_line_interval(self, time):
        pass

    def set_binning(self, binning_string):
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

    def initialize_image_series(self):
        pass

    def get_images_in_series(self):
        '''Should return a single numpy array'''
        pass

    def close_image_series(self):
        pass

    def get_image(self):
        '''Should return a single numpy array'''
        pass

    def initialize_live_mode(self):
        pass

    def get_live_image(self):
        pass

    def close_live_mode(self):
        pass

class mesoSPIM_DemoCamera(mesoSPIM_GenericCamera):

    def __init__(self, parent = None):
        super().__init__(parent)

        self.line = np.linspace(0,6*np.pi,self.x_pixels)
        self.line = 400*np.sin(self.line)+1200

        self.count = 0

    def open_camera(self):
        logger.info('Initialized Demo Camera')

    def close_camera(self):
        logger.info('Closed Demo Camera')
    
    def set_binning(self, binning_string):
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.line = np.linspace(0,6*np.pi,self.x_pixels)
        self.line = 400*np.sin(self.line)+1200

    def _create_random_image(self):
        data = np.array([np.roll(self.line, 4*i+self.count) for i in range(0, self.y_pixels)], dtype='uint16')
        data = data + (np.random.normal(size=(self.x_pixels, self.y_pixels))*100)
        data = np.around(data).astype('uint16')
        self.count += 20
        return data

        # return np.random.randint(low=0, high=2**16, size=(self.x_pixels,self.y_pixels), dtype='l')

    def get_images_in_series(self):
        return [self._create_random_image()]

    def get_image(self):
        return self._create_random_image()

    def get_live_image(self):
        return [self._create_random_image()]

class mesoSPIM_HamamatsuCamera(mesoSPIM_GenericCamera):
    def __init__(self, parent = None):
        super().__init__(parent)
        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    def open_camera(self):
        ''' Hamamatsu-specific code '''
        self.camera_id = self.cfg.camera_parameters['camera_id']

        from .devices.cameras.hamamatsu import hamamatsu_camera as cam
        # if self.cfg.camera == 'HamamatsuOrca':
        self.hcam = cam.HamamatsuCameraMR(camera_id=self.camera_id)
        ''' Debbuging information '''
        logger.info(f'Initialized Hamamatsu camera model: {self.hcam.getModelInfo(self.camera_id)}')

        ''' Ideally, the Hamamatsu Camera properties should be set in this order '''
        ''' mesoSPIM mode parameters '''
        self.hcam.setPropertyValue("sensor_mode", self.cfg.camera_parameters['sensor_mode'])

        self.hcam.setPropertyValue("defect_correct_mode", self.cfg.camera_parameters['defect_correct_mode'])
        self.hcam.setPropertyValue("exposure_time", self.camera_exposure_time)
        self.hcam.setPropertyValue("binning", self.cfg.camera_parameters['binning'])
        self.hcam.setPropertyValue("readout_speed", self.cfg.camera_parameters['readout_speed'])

        self.hcam.setPropertyValue("trigger_active", self.cfg.camera_parameters['trigger_active'])
        self.hcam.setPropertyValue("trigger_mode", self.cfg.camera_parameters['trigger_mode']) # it is unclear if this is the external lightsheeet mode - how to check this?
        self.hcam.setPropertyValue("trigger_polarity", self.cfg.camera_parameters['trigger_polarity']) # positive pulse
        self.hcam.setPropertyValue("trigger_source", self.cfg.camera_parameters['trigger_source']) # external
        self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)

    def close_camera(self):
        self.hcam.shutdown()

    def set_camera_sensor_mode(self, mode):
        if mode == 'Area':
            self.hcam.setPropertyValue("sensor_mode", 1)
        elif mode == 'ASLM':
            self.hcam.setPropertyValue("sensor_mode", 12)
        else:
            print('Camera mode not supported')

    def set_exposure_time(self, time):
        self.hcam.setPropertyValue("exposure_time", time)

    def set_line_interval(self, time):
        self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)

    def set_binning(self, binningstring):
        self.hcam.setPropertyValue("binning", binningstring)
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

    def initialize_image_series(self):
        self.hcam.startAcquisition()

    def get_images_in_series(self):
        [frames, _] = self.hcam.getFrames()
        images = [np.reshape(aframe.getData(), (-1,self.x_pixels)) for aframe in frames]
        return images

    def close_image_series(self):
        self.hcam.stopAcquisition()

    def get_image(self):
        [frames, _] = self.hcam.getFrames()
        images = [np.reshape(aframe.getData(), (-1,self.x_pixels)) for aframe in frames]
        return images[0]

    def initialize_live_mode(self):
        self.hcam.setACQMode(mode = "run_till_abort")
        self.hcam.startAcquisition()

    def get_live_image(self):
        [frames, _] = self.hcam.getFrames()
        images = [np.reshape(aframe.getData(), (-1,self.x_pixels)) for aframe in frames]
        return images

    def close_live_mode(self):
        self.hcam.stopAcquisition()

class mesoSPIM_PhotometricsCamera(mesoSPIM_GenericCamera):
    def __init__(self, parent = None):
        super().__init__(parent)
        logger.info('Thread ID at Startup: '+str(int(QtCore.QThread.currentThreadId())))

    def open_camera(self):
        from pyvcam import pvc
        from pyvcam import constants as const
        from pyvcam.camera import Camera

        self.const = const
        self.pvc = pvc

        pvc.init_pvcam()
        self.pvcam = [cam for cam in Camera.detect_camera()][0]

        self.pvcam.open()
        self.pvcam.speed_table_index = self.cfg.camera_parameters['speed_table_index']
        self.pvcam.exp_mode = self.cfg.camera_parameters['exp_mode']
        
        logger.info('Camera Vendor Name: '+str(self.pvcam.get_param(param_id = self.const.PARAM_VENDOR_NAME)))
        logger.info('Camera Product Name: '+str(self.pvcam.get_param(param_id = self.const.PARAM_PRODUCT_NAME)))
        logger.info('Camera Chip Name: '+str(self.pvcam.get_param(param_id = self.const.PARAM_CHIP_NAME)))
        logger.info('Camera System Name: '+str(self.pvcam.get_param(param_id = self.const.PARAM_SYSTEM_NAME)))

        # Exposure mode options: {'Internal Trigger': 1792, 'Edge Trigger': 2304, 'Trigger first': 2048}
        # self.pvcam.set_param(param_id = self.const.PARAM_EXPOSURE_MODE, value = 2304)

        # Exposure out mode options: {'First Row': 0, 'All Rows': 1, 'Any Row': 2, 'Rolling Shutter': 3, 'Line Output': 4}
        # self.pvcam.set_param(param_id = self.const.PARAM_EXPOSE_OUT_MODE, value = 3)

        ''' Setting ASLM parameters '''
        # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
        self.pvcam.set_param(param_id = self.const.PARAM_SCAN_MODE, value = self.cfg.camera_parameters['scan_mode'])
        # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
        self.pvcam.set_param(param_id = self.const.PARAM_SCAN_DIRECTION, value = self.cfg.camera_parameters['scan_direction'])
        # 10.26 us x factor 
        # factor = 6 equals 71.82 us
        self.pvcam.set_param(param_id = self.const.PARAM_SCAN_LINE_DELAY, value = self.cfg.camera_parameters['scan_line_delay'])
        self.pvcam.set_param(param_id = self.const.PARAM_READOUT_PORT, value = 1)
        ''' Setting Binning parameters: '''
        '''
        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])
        '''
        self.pvcam.binning = (self.x_binning, self.y_binning)

        #self.pvcam.set_param(param_id = self.const.PARAM_BINNING_PAR, value = self.y_binning)
        #self.pvcam.set_param(param_id = self.const.PARAM_BINNING_SER, value = self.x_binning)

        # print('Readout port: ', self.pvcam.readout_port)
        
        """ 
        self.report_pvcam_parameter('PMODE',self.const.PARAM_PMODE)
        self.report_pvcam_parameter('GAIN_INDEX',self.const.PARAM_GAIN_INDEX)
        self.report_pvcam_parameter('GAIN_NAME',self.const.PARAM_GAIN_NAME)
        self.report_pvcam_parameter('READOUT PORT',self.const.PARAM_READOUT_PORT)
        self.report_pvcam_parameter('READOUT TIME',self.const.PARAM_READOUT_TIME)
        self.report_pvcam_parameter('IMAGE FORMAT', self.const.PARAM_IMAGE_FORMAT)
        self.report_pvcam_parameter('SPEED TABLE INDEX', self.const.PARAM_SPDTAB_INDEX)
        self.report_pvcam_parameter('BIT DEPTH', self.const.PARAM_BIT_DEPTH)

        
        logger.info('P Mode: '+str(self.pvcam.get_param(param_id = self.const.PARAM_PMODE)))
        logger.info('P Mode options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_PMODE)))
        logger.info('Bit depth: '+str(self.pvcam.get_param(param_id = self.const.PARAM_BIT_DEPTH)))
        logger.info('Exposure time resolution: '+str(self.pvcam.get_param(param_id = self.const.PARAM_EXP_RES)))
        logger.info('Exposure time resolution options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_EXP_RES)))
        logger.info('Exposure mode: '+str(self.pvcam.get_param(param_id = self.const.PARAM_EXPOSURE_MODE)))
        logger.info('Exposure mode options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_EXPOSURE_MODE)))
        logger.info('Exposure out mode: '+str(self.pvcam.get_param(param_id = self.const.PARAM_EXPOSE_OUT_MODE)))
        logger.info('Exposure out mode options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_EXPOSE_OUT_MODE)))
        logger.info('Scan mode: '+str(self.pvcam.get_param(param_id = self.const.PARAM_SCAN_MODE)))
        logger.info('Scan mode options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_SCAN_MODE)))
        logger.info('Scan direction: '+str(self.pvcam.get_param(param_id = self.const.PARAM_SCAN_DIRECTION)))
        logger.info('Scan direction options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_SCAN_DIRECTION)))
        logger.info('Line delay: '+str(self.pvcam.get_param(param_id = self.const.PARAM_SCAN_LINE_DELAY)))
        logger.info('Line time: '+str(self.pvcam.get_param(param_id = self.const.PARAM_SCAN_LINE_TIME)))
        logger.info('Binning SER: '+str(self.pvcam.get_param(param_id = self.const.PARAM_BINNING_SER)))
        logger.info('Binning SER options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_BINNING_SER)))
        logger.info('Binning PAR: '+str(self.pvcam.get_param(param_id = self.const.PARAM_BINNING_PAR)))
        logger.info('Binning PAR options: '+str(self.pvcam.read_enum(param_id = self.const.PARAM_BINNING_PAR)))
        """

    def report_pvcam_parameter(self, description, parameter):
        try:
            logger.info(description+' '+str(self.pvcam.get_param(param_id = parameter)))
            print(description+' '+str(self.pvcam.get_param(param_id = parameter)))
        except:
            pass
        
        try:
            logger.info(description+' '+str(self.pvcam.read_enum(param_id = parameter)))
            print(description+' '+str(str(self.pvcam.read_enum(param_id = parameter))))
        except:
            pass
        
    def close_camera(self):
        self.pvcam.close()
        self.pvc.uninit_pvcam()

    def set_exposure_time(self, time):
        self.camera_exposure_time = time

    def set_line_interval(self, time):
        print('Setting line interval is not implemented, set the interval in the config file')

    def set_binning(self, binningstring):
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.pvcam.binning = (self.x_binning, self.y_binning)
        
    def get_image(self):
        return self.pvcam.get_live_frame()
    
    def initialize_image_series(self):
        ''' The Photometrics cameras expect integer exposure times, otherwise they default to the minimum value '''
        exp_time_ms = int(self.camera_exposure_time * 1000)
        self.pvcam.start_live(exp_time_ms)    

    def get_images_in_series(self):
        return [self.pvcam.get_live_frame()]
    
    def close_image_series(self):
        self.pvcam.stop_live()

    def initialize_live_mode(self):
        ''' The Photometrics cameras expect integer exposure times, otherwise they default to the minimum value '''
        exp_time_ms = int(self.camera_exposure_time * 1000)
        # logger.info('Initializing live mode with exp time: '+str(exp_time_ms))
        self.pvcam.start_live(exp_time_ms)
    
    def get_live_image(self):
        return [self.pvcam.get_live_frame()]

    def close_live_mode(self):
        self.pvcam.stop_live()

    