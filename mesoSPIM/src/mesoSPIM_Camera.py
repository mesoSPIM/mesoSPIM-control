'''
mesoSPIM Camera class, intended to run in its own thread
'''

import time
import numpy as np

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
from .mesoSPIM_ImageWriter import mesoSPIM_ImageWriter
from .utils.acquisitions import AcquisitionList, Acquisition


class mesoSPIM_Camera(QtCore.QObject):
    '''Top-level class for all cameras'''
    sig_camera_frame = QtCore.pyqtSignal(np.ndarray)
    sig_finished = QtCore.pyqtSignal()
    sig_update_gui_from_state = QtCore.pyqtSignal(bool)
    sig_status_message = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super().__init__()

        self.parent = parent # a mesoSPIM_Core() object
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()
        self.image_writer = mesoSPIM_ImageWriter(self)
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
        self.camera_display_acquisition_subsampling = self.cfg.startup['camera_display_acquisition_subsampling']

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler) # from mesoSPIM_Core() to mesoSPIM_Camera()
        self.parent.sig_prepare_image_series.connect(self.prepare_image_series, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_add_images_to_image_series.connect(self.add_images_to_series, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_add_images_to_image_series_and_wait_until_done.connect(self.add_images_to_series, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_write_metadata.connect(self.image_writer.write_metadata, type=QtCore.Qt.QueuedConnection)
        # The following connection can cause problems when disk is too slow (e.g. writing TIFF files on HDD drive):
        self.parent.sig_end_image_series.connect(self.end_image_series, type=QtCore.Qt.BlockingQueuedConnection)

        self.parent.sig_prepare_live.connect(self.prepare_live, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_get_live_image.connect(self.get_live_image)
        self.parent.sig_get_snap_image.connect(self.snap_image)
        self.parent.sig_end_live.connect(self.end_live, type=QtCore.Qt.BlockingQueuedConnection)

        ''' Set up the camera '''
        if self.cfg.camera == 'HamamatsuOrca':
            self.camera = mesoSPIM_HamamatsuCamera(self)
        elif self.cfg.camera == 'Photometrics':
            self.camera = mesoSPIM_PhotometricsCamera(self)
        elif self.cfg.camera == 'PCO':
            self.camera = mesoSPIM_PCOCamera(self)
        elif self.cfg.camera == 'DemoCamera':
            self.camera = mesoSPIM_DemoCamera(self)

        self.camera.open_camera()

    def __del__(self):
        try:
            self.camera.close_camera()
        except:
            pass

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        '''The request handling is done with exec() to write fewer lines of code. '''
        for key, value in zip(dict.keys(), dict.values()):
            if key in ('camera_exposure_time',
                        'camera_line_interval',
                        'state',
                        'camera_display_live_subsampling',
                        'camera_display_acquisition_subsampling',
                        'camera_binning'):
                exec('self.set_'+key+'(value)')
            elif key == 'state':
                if value == 'live':
                    logger.debug('Thread ID during live: '+str(int(QtCore.QThread.currentThreadId())))

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
        self.state['camera_display_live_subsampling'] = factor

    def set_camera_display_acquisition_subsampling(self, factor):
        self.camera_display_acquisition_subsampling = factor
        self.state['camera_display_acquisition_subsampling'] = factor

    def set_camera_binning(self, value):
        logger.info('Setting camera binning: '+value)
        self.camera.set_binning(value)
        self.state['camera_binning'] = value

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def prepare_image_series(self, acq, acq_list):
        '''
        Row is a row in a AcquisitionList
        '''
        logger.info('Camera: Preparing Image Series')
        self.stopflag = False
        self.image_writer.prepare_acquisition(acq, acq_list)
        self.max_frame = acq.get_image_count()
        self.processing_options_string = acq['processing']
        self.camera.initialize_image_series()
        self.cur_image = 0
        logger.info(f'Camera: Finished Preparing Image Series')
        self.start_time = time.time()

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def add_images_to_series(self, acq, acq_list):
        if self.cur_image == 0:
            logger.debug('Thread ID during add images: '+str(int(QtCore.QThread.currentThreadId())))

        if self.stopflag is False:
            if self.cur_image < self.max_frame:
                images = self.camera.get_images_in_series()
                for image in images:
                    image = np.rot90(image)
                    self.sig_camera_frame.emit(image[0:self.x_pixels:self.camera_display_acquisition_subsampling,
                                               0:self.y_pixels:self.camera_display_acquisition_subsampling])
                    self.image_writer.write_image(image, acq, acq_list)
                    self.cur_image += 1

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def end_image_series(self, acq, acq_list):
        logger.debug("end_image_series() started")
        try:
            self.camera.close_image_series()
            logger.debug("self.camera.close_image_series()")
        except Exception as e:
            logger.error(f'Camera: Image Series could not be closed: {e}')

        self.image_writer.end_acquisition(acq, acq_list)

        self.end_time = time.time()
        framerate = (self.cur_image + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Framerate: {framerate:.2f}')
        self.sig_finished.emit()

    @QtCore.pyqtSlot(bool)
    def snap_image(self, write_flag=True):
        """"Snap an image and display it"""
        image = self.camera.get_image()
        image = np.rot90(image)[::self.camera_display_acquisition_subsampling, ::self.camera_display_acquisition_subsampling]
        self.sig_camera_frame.emit(image)
        if write_flag:
            self.image_writer.write_snap_image(image)

    @QtCore.pyqtSlot()
    def prepare_live(self):
        self.camera.initialize_live_mode()
        self.live_image_count = 0
        self.start_time = time.time()
        logger.info('Camera: Preparing Live Mode')

    @QtCore.pyqtSlot()
    def get_live_image(self):
        images = self.camera.get_live_image()

        for image in images:
            image = np.rot90(image)

            self.sig_camera_frame.emit(image[0:self.x_pixels:self.camera_display_live_subsampling,
                                       0:self.y_pixels:self.camera_display_live_subsampling])
            self.live_image_count += 1
            #self.sig_camera_status.emit(str(self.live_image_count))

    @QtCore.pyqtSlot()
    def end_live(self):
        self.camera.close_live_mode()
        self.end_time = time.time()
        framerate = (self.live_image_count + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Finished Live Mode: Framerate: {framerate:.2f}')


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
        self.x_binning = int(binning_string[0])
        self.y_binning = int(binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.state['camera_binning'] = str(self.x_binning)+'x'+str(self.y_binning)

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

        self.count = 0

        self.line = np.linspace(0,6*np.pi,self.x_pixels)
        self.line = 400*np.sin(self.line)+1200

    def open_camera(self):
        logger.info('Initialized Demo Camera')

    def close_camera(self):
        logger.info('Closed Demo Camera')
    
    def set_binning(self, binning_string):
        self.x_binning = int(binning_string[0])
        self.y_binning = int(binning_string[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        ''' Changing the number of pixels also affects the random image, so we need to update self.line '''
        self.line = np.linspace(0,6*np.pi,self.x_pixels)
        self.line = 400*np.sin(self.line)+1200
        self.state['camera_binning'] = str(self.x_binning)+'x'+str(self.y_binning)

    def _create_random_image(self):
        data = np.array([np.roll(self.line, 4*i+self.count) for i in range(0, self.y_pixels)], dtype='uint16')
        data = data + (np.random.normal(size=(self.y_pixels, self.x_pixels))*100)
        data = np.around(data).astype('uint16')
        self.count += 20
        return data

    def get_images_in_series(self):
        return [self._create_random_image()]

    def get_image(self):
        return self._create_random_image()

    def get_live_image(self):
        return [self._create_random_image()]


class mesoSPIM_HamamatsuCamera(mesoSPIM_GenericCamera):
    def __init__(self, parent = None):
        super().__init__(parent)

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
        self.hcam.setPropertyValue("binning", self.cfg.camera_parameters['binning'])
        if 'readout_speed' in self.cfg.camera_parameters.keys():
            self.hcam.setPropertyValue("readout_speed", self.cfg.camera_parameters['readout_speed'])
        else:
            logger.warning('No readout speed specified in the configuration file. Using default value.')
        if 'high_dynamic_range_mode' in self.cfg.camera_parameters.keys():
            self.hcam.setPropertyValue("high_dynamic_range_mode", self.cfg.camera_parameters['high_dynamic_range_mode'])
        else:
            logger.warning('No "high_dynamic_range_mode" specified in the configuration file. Using default value.')

        self.hcam.setPropertyValue("trigger_active", self.cfg.camera_parameters['trigger_active'])
        self.hcam.setPropertyValue("trigger_mode", self.cfg.camera_parameters['trigger_mode']) # it is unclear if this is the external lightsheeet mode - how to check this?
        self.hcam.setPropertyValue("trigger_polarity", self.cfg.camera_parameters['trigger_polarity']) # positive pulse
        self.hcam.setPropertyValue("trigger_source", self.cfg.camera_parameters['trigger_source']) # external
        self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)
        self.hcam.setPropertyValue("exposure_time", self.camera_exposure_time)
        self.print_camera_properties(message='Camera properties after initialization')

    def print_camera_properties(self, message='Camera properties'):
        ''' Camera properties '''
        logger.debug(message)
        props = self.hcam.getProperties()
        for i, id_name in enumerate(sorted(props.keys())):
            [p_value, p_type] = self.hcam.getPropertyValue(id_name)
            p_rw = self.hcam.getPropertyRW(id_name)
            read_write = ""
            if p_rw[0]:
                read_write += "read"
            if p_rw[1]:
                read_write += ", write"
            logger.debug(f"  {i} ) {id_name}, = {p_value}  type is: {p_type}, {read_write}")
            text_values = self.hcam.getPropertyText(id_name)
            if len(text_values) > 0:
                logger.debug("          option / value")
                for key in sorted(text_values, key=text_values.get):
                    logger.debug(f"         {key} / {text_values[key]}")

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
        self.x_binning = int(binningstring[0])
        self.y_binning = int(binningstring[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.state['camera_binning'] = str(self.x_binning)+'x'+str(self.y_binning)

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
        self.pvcam.set_param(param_id = self.const.PARAM_READOUT_PORT, value = self.cfg.camera_parameters['readout_port'])
        self.pvcam.set_param(self.const.PARAM_GAIN_INDEX, self.cfg.camera_parameters['gain_index'])
        self.pvcam.exp_out_mode = self.cfg.camera_parameters['exp_out_mode']
        self.pvcam.exp_res = 0 # 0 for ms

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
        print('Exp Time :', time)
        exp_time_ms = int(self.camera_exposure_time * 1000)
        self.pvcam.exp_time = exp_time_ms
        self.camera_exposure_time = time

    def set_line_interval(self, time):
        print('Setting line interval is not implemented, set the interval in the config file')

    def set_binning(self, binningstring):
        self.x_binning = int(binningstring[0])
        self.y_binning = int(binningstring[2])
        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.pvcam.binning = (self.x_binning, self.y_binning)
        self.state['camera_binning'] = str(self.x_binning)+'x'+str(self.y_binning)
        
    def get_image(self):
        frame , _ , _ = self.pvcam.poll_frame()
        return frame['pixel_data']
    
    def initialize_image_series(self):
        ''' The Photometrics cameras expect integer exposure times, otherwise they default to the minimum value '''
        exp_time_ms = int(self.camera_exposure_time * 1000)
        self.pvcam.exp_time = exp_time_ms
        self.pvcam.start_live()

    def get_images_in_series(self):
        # print('Exp Time in series:', self.pvcam.exp_time)
        frame , _ , _ = self.pvcam.poll_frame()
        return [frame['pixel_data']]
    
    def close_image_series(self):
        logger.debug("Calling self.pvcam.finish()")
        self.pvcam.finish()

    def initialize_live_mode(self):
        ''' The Photometrics cameras expect integer exposure times, otherwise they default to the minimum value '''
        exp_time_ms = int(self.camera_exposure_time * 1000)
        self.pvcam.exp_time = exp_time_ms
        self.pvcam.start_live()
        logger.info('Initializing live mode with exp time: '+str(exp_time_ms))
    
    def get_live_image(self):
        # print('Exp Time in live:', self.pvcam.exp_time)
        frame , _ , _ = self.pvcam.poll_frame()
        return [frame['pixel_data']]
    
    def close_live_mode(self):
        # print('Live mode finished')
        self.pvcam.finish()
        

class mesoSPIM_PCOCamera(mesoSPIM_GenericCamera):
    def __init__(self, parent = None):
        super().__init__(parent)
        logger.info('PCO Cam initialized')
    
    def open_camera(self):
        import pco
        self.cam = pco.Camera() # no logging 
        # self.cam = pco.Camera(debuglevel='verbose', timestamp='on')

        self.cam.sdk.set_cmos_line_timing('on', self.cfg.camera_parameters['line_interval']) # 75 us delay
        self.cam.set_exposure_time(self.cfg.camera_parameters['exp_time'])
        # self.cam.sdk.set_cmos_line_exposure_delay(80, 0) # 266 lines = 20 ms / 75 us
        self.cam.configuration = {'trigger' : self.cfg.camera_parameters['trigger']}

        line_time = self.cam.sdk.get_cmos_line_timing()['line time']
        lines_exposure = self.cam.sdk.get_cmos_line_exposure_delay()['lines exposure']
        t = self.cam.get_exposure_time()
        #print('Exposure Time: {:9.6f} s'.format(t))
        #print('Line Time: {:9.6f} s'.format(line_time))
        #print('Number of Lines: {:d}'.format(lines_exposure))

        self.cam.record(number_of_images=4, mode='fifo')

    def close_camera(self):
        self.cam.stop()
        self.cam.close()

    def set_exposure_time(self, time):
        self.cam.set_exposure_time(time)
        self.camera_exposure_time = time
        
    def set_line_interval(self, time):
        print('Setting line interval is not implemented, set the interval in the config file')
        
    def set_binning(self, binningstring):
        pass
                
    def get_image(self):
        image, meta = self.cam.image(image_number=-1)
        return image
        
    def initialize_image_series(self):
        pass
    
    def get_images_in_series(self):
        image, meta = self.cam.image(image_number=-1)
        return [image]

    def close_image_series(self):
        pass

    def initialize_live_mode(self):
        pass

    def get_live_image(self):
        image, meta = self.cam.image(image_number=-1)
        return [image]

    def close_live_mode(self):
        pass

    