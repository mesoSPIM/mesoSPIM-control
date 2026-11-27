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

from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import log_cpu_core, timed
from .utils.config_loader import is_demo
from .mesoSPIM_ProcessorChain import ProcessorChain


class mesoSPIM_Camera(QtCore.QObject):
    '''Top-level class for all cameras'''
    sig_camera_frame = QtCore.pyqtSignal()
    sig_snap_image_ready = QtCore.pyqtSignal()  # emitted after snap; image is in frame_queue_display
    sig_write_images = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    # Tells the ImageWriter to finalize the file. Emitted from the Camera thread (not the Core
    # thread) so that Qt's per-sender-thread ordering guarantees it is delivered *after* the
    # sig_write_images of the last plane -- otherwise the final frame is dropped, see
    # end_image_series() below.
    sig_end_acquisition = QtCore.pyqtSignal(Acquisition, AcquisitionList)
    sig_finished = QtCore.pyqtSignal()
    sig_end_image_series_done = QtCore.pyqtSignal()  # emitted after end_image_series cleanup is complete
    sig_update_gui_from_state = QtCore.pyqtSignal()
    sig_status_message = QtCore.pyqtSignal(str)

    def __init__(self, parent, frame_queue, frame_queue_display):
        super().__init__()

        self.parent = parent # a mesoSPIM_Core() object
        self.cfg = parent.cfg
        self.frame_queue = frame_queue
        self.frame_queue_display = frame_queue_display

        self.state = self.parent.state # a mesoSPIM_StateSingleton() object
        #self.image_writer = mesoSPIM_ImageWriter(self)
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
        if 'camera_display_temporal_subsampling' in self.cfg.startup.keys():
            self.camera_display_temporal_subsampling = self.cfg.startup['camera_display_temporal_subsampling']
        else:
            self.camera_display_temporal_subsampling = 2
        logger.debug(f'Camera display temporal subsampling factor: {self.camera_display_temporal_subsampling}')

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler) # from mesoSPIM_Core() to mesoSPIM_Camera()
        self.parent.sig_prepare_image_series.connect(self.prepare_image_series, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_add_images_to_image_series.connect(self.add_images_to_series, type=QtCore.Qt.QueuedConnection)
        # self.parent.sig_add_images_to_image_series_and_wait_until_done.connect(self.add_images_to_series, type=QtCore.Qt.BlockingQueuedConnection)
        #self.parent.sig_write_metadata.connect(self.image_writer.write_metadata, type=QtCore.Qt.BlockingQueuedConnection)

        self.parent.sig_prepare_live.connect(self.prepare_live, type=QtCore.Qt.BlockingQueuedConnection)
        self.parent.sig_get_live_image.connect(self.get_live_image)
        self.parent.sig_get_snap_image.connect(self.snap_image)
        self.parent.sig_end_live.connect(self.end_live, type=QtCore.Qt.BlockingQueuedConnection)

        ''' Set up the actual camera '''
        if self.cfg.camera == 'HamamatsuOrca':
            self.camera = mesoSPIM_HamamatsuCamera(self)
        elif self.cfg.camera == 'Photometrics':
            self.camera = mesoSPIM_PhotometricsCamera(self)
        elif self.cfg.camera == 'PCO':
            self.camera = mesoSPIM_PCOCamera(self)
        elif is_demo(self.cfg.camera):
            self.camera = mesoSPIM_DemoCamera(self)

        self.camera.open_camera()
        logger.info('Camera initialized')

        self.processor_chain = ProcessorChain()

    def __del__(self):
        try:
            self.camera.close_camera()
        except:
            pass

    @QtCore.pyqtSlot(dict)
    def state_request_handler(self, dict):
        _dispatch = {
            'camera_exposure_time':                  self.set_camera_exposure_time,
            'camera_line_interval':                  self.set_camera_line_interval,
            'state':                                 self.set_state,
            'camera_display_live_subsampling':       self.set_camera_display_live_subsampling,
            'camera_display_acquisition_subsampling': self.set_camera_display_acquisition_subsampling,
            'camera_binning':                        self.set_camera_binning,
        }
        for key, value in zip(dict.keys(), dict.values()):
            if key in _dispatch:
                _dispatch[key](value)

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
        self.state['camera_exposure_time'] = time
        #self.sig_update_gui_from_state.emit()

    def set_camera_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        self.camera.set_line_interval(time)
        self.camera_line_interval = time
        self.state['camera_line_interval'] = time
        #self.sig_update_gui_from_state.emit()

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
        self.drain_requests_done = 0  # add_images_to_series() calls completed; the Core paces requests on it
        #self.image_writer.prepare_acquisition(acq, acq_list)
        self.max_frame = acq.get_image_count()
        self.processing_options_string = acq['processing']
        self.cur_image = 0  # before the camera call: the Core polls it even if that call fails
        try:
            self.camera.initialize_image_series()
        except Exception:
            # Raised in a Qt slot this would only reach the console, and the Core would
            # launch a stack the camera is not ready for. Log it where it can be found.
            logger.exception('Camera: initialize_image_series() failed')
            raise
        logger.info(f'Camera: Finished Preparing Image Series')
        self.start_time = time.time()
        
        self.processor_chain.reset()

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    @timed
    @log_cpu_core
    def add_images_to_series(self, acq, acq_list):
        try:
            self._add_images_to_series(acq, acq_list)
        finally:
            self.drain_requests_done = getattr(self, 'drain_requests_done', 0) + 1

    def _add_images_to_series(self, acq, acq_list):
        if self.cur_image == 0:
            logger.debug('Thread name during add images: '+ QtCore.QThread.currentThread().objectName())

        if self.stopflag is False:
            if self.cur_image < self.max_frame:
                logger.debug(f'Adding images to series')
                images = self.camera.get_images_in_series()
                logger.debug(f'Got {len(images)} images')
                if not images:
                    return  # timed out waiting for a frame; the caller decides whether to ask again
                images = images[:self.max_frame - self.cur_image]

                if self.processor_chain.is_enabled:
                    images = [self.processor_chain.process(img) for img in images]
                
                self.frame_queue.extend(images) # push the list of images into queue
                # show an image every other timepoint to prevent GUI freezing in long acquisitions
                if self.cur_image % self.camera_display_temporal_subsampling == 0:
                    self.frame_queue_display.append(images[0].T[::-1]) # push the first image into the display queue
                    self.sig_camera_frame.emit() # signal the GUI to update the display
                # tell the image writer to write the images in queue
                self.sig_write_images.emit(acq, acq_list)
                self.cur_image += len(images)

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def end_image_series(self, acq, acq_list):
        logger.debug("end_image_series() started")
        try:
            self.camera.close_image_series()
            logger.debug("self.camera.close_image_series()")
        except Exception as e:
            logger.error(f'Camera: Image Series could not be closed: {e}')

        if self.stopflag is False and self.cur_image != self.max_frame:
            logger.error(f'Camera: acquired {self.cur_image} frames, expected {self.max_frame}')

        # Tell the ImageWriter to finalize. This runs in the Camera thread, after the
        # add_images_to_series() call of the last plane has already emitted sig_write_images,
        # so the writer is guaranteed to see that frame before it closes the file.
        self.sig_end_acquisition.emit(acq, acq_list)

        self.end_time = time.time()
        framerate = (self.cur_image + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Framerate: {framerate:.2f}')
        self.sig_finished.emit()
        self.sig_end_image_series_done.emit()

    @QtCore.pyqtSlot(bool)
    @log_cpu_core
    def snap_image(self, write_flag=True):
        """"Snap an image and display it"""
        image = self.camera.get_image().T[::-1]
        
        if self.processor_chain.is_enabled:
            image = self.processor_chain.process(image)
        
        self.frame_queue_display.append(image) # push the first image into the display queue
        logger.info(f"Image appended to display queue: len(frame_queue_display)={len(self.frame_queue_display)}")
        self.sig_camera_frame.emit() # signal the GUI to update the display
        if write_flag:
            self.sig_snap_image_ready.emit()

    @QtCore.pyqtSlot()
    def prepare_live(self):
        self.camera.initialize_live_mode()
        self.live_image_count = 0
        self.start_time = time.time()
        logger.info('Camera: Preparing Live Mode')
        
        self.processor_chain.reset()

    @QtCore.pyqtSlot()
    @log_cpu_core
    def get_live_image(self):
        images = self.camera.get_live_image()
        for image in images:
            processed_image = image.T[::-1]
            
            if self.processor_chain.is_enabled:
                processed_image = self.processor_chain.process(processed_image)
            
            self.frame_queue_display.append(processed_image) # push the first image into the display queue
            self.sig_camera_frame.emit() # signal the GUI to update the display
            self.live_image_count += 1
            #self.sig_camera_status.emit(str(self.live_image_count))

    @QtCore.pyqtSlot()
    def end_live(self):
        self.camera.close_live_mode()
        self.end_time = time.time()
        framerate = (self.live_image_count + 1)/(self.end_time - self.start_time)
        logger.info(f'Camera: Finished Live Mode: Framerate: {framerate:.2f}')


class mesoSPIM_GenericCamera(QtCore.QObject):
    '''Abstract base class for all mesoSPIM camera drivers.

    Concrete subclasses override the hardware-interaction methods listed below.
    The base class reads sensor dimensions and binning from ``cfg.camera_parameters``
    and provides no-op stubs for every camera lifecycle method.

    Lifecycle sequence expected by :class:`mesoSPIM_Core`:

    * **Live mode**: ``open_camera`` → ``initialize_live_mode`` → ``get_live_image``
      (repeated) → ``close_live_mode`` → ``close_camera``
    * **Acquisition**: ``open_camera`` → ``initialize_image_series`` →
      ``get_images_in_series`` (repeated) → ``close_image_series`` → ``close_camera``

    All subclass instances run in the **Camera thread** (a high-priority
    ``QThread`` spawned in :class:`mesoSPIM_Core`).
    '''

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.cfg = parent.cfg

        self.state = self.parent.state # the mesoSPIM_StateSingleton() object

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
    '''Software-only camera driver for use without physical hardware.

    Generates synthetic sinusoidal fringe images so that the GUI, image
    writer, and acquisition-sequencing logic can be exercised without a
    physical camera.  Used for development, demos, and CI/testing.
    '''
    def __init__(self, parent):
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
        data = np.array([np.roll(self.line, 4*i + self.count) for i in range(0, self.y_pixels)], dtype='uint16')
        self.count += 20
        return data

    def get_images_in_series(self):
        return [self._create_random_image()]

    def get_image(self):
        return self._create_random_image()

    def get_live_image(self):
        return [self._create_random_image()]


class mesoSPIM_HamamatsuCamera(mesoSPIM_GenericCamera):
    '''Camera driver for Hamamatsu ORCA-Flash / ORCA-Fusion cameras.

    Uses the `hamamatsu_camera` Python wrapper (a ctypes-based interface to
    the DCAM-API SDK included in ``devices/cameras/hamamatsu/``).
    Sensor mode, defect correction, binning, and readout speed are applied at
    ``open_camera()`` time from ``cfg.camera_parameters``.
    '''
    def __init__(self, parent):
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
    '''Camera driver for Photometrics (Teledyne) sCMOS cameras.

    Uses the ``pyvcam`` Python SDK.  Requires the PVCAM runtime to be installed
    on the host PC.  Camera properties (speed table index, port index, gain,
    exposure mode) are configured in ``cfg.camera_parameters``.
    '''
    def __init__(self, parent):
        super().__init__(parent)

    def open_camera(self):
        from pyvcam import pvc
        from pyvcam import constants as const
        from pyvcam.camera import Camera

        self.const = const
        self.pvc = pvc
        from importlib.metadata import version
        pyvcam_version = version('pyvcam')
        logger.info(f'PyVCAM version: {pyvcam_version}')
        # Image series need 2.2+: reset_frame_counter and a live-mode frame backlog. 2.1.x keeps
        # only the latest frame, so frames are lost whenever the drain falls behind.
        if tuple(int(x) for x in pyvcam_version.split('.')[:2]) < (2, 2):
            logger.warning(f'PyVCAM {pyvcam_version} is older than the tested 2.2.4 and can drop frames '
                           f'in image series; upgrade with: pip install pyvcam==2.2.4')

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
    
    # Longest wait for one frame in an image series. Generous for any sweeptime, but finite:
    # with WAIT_FOREVER a drain request that no frame answers (e.g. the last request of a
    # continuous stack that came up short) blocked the camera thread for good, so it never
    # ran end_image_series() and the image writer was never finalized.
    SERIES_POLL_TIMEOUT_MS = 5000
    # Frames taken per drain call: everything already buffered, so a slow round trip from
    # the Core cannot limit the frame rate. Bounded so one call cannot starve the writer.
    SERIES_MAX_FRAMES_PER_CALL = 16

    def initialize_image_series(self):
        ''' The Photometrics cameras expect integer exposure times, otherwise they default to the minimum value '''
        exp_time_ms = int(self.camera_exposure_time * 1000)
        self.pvcam.exp_time = exp_time_ms
        # PVCAM circular buffer. When frames are not drained fast enough the oldest are
        # overwritten, so at continuous frame rates this is the slack for drain hiccups:
        # PyVCAM's default of 16 frames is only 1.3 s at 12 FPS.
        buffer_frames = int(self.cfg.camera_parameters.get('series_buffer_frames', 16))
        # Keep the buffer under 2 GiB: a 100-frame (3 GB) buffer of 5056x2960 frames made
        # start_live() fail on 2026-10-01, consistent with a signed 32-bit buffer size.
        frame_bytes = self.x_pixels * self.y_pixels * 2
        max_frames = max(1, (2**31 - 1) // frame_bytes)
        if buffer_frames > max_frames:
            logger.warning(f'Photometrics: series_buffer_frames={buffer_frames} '
                           f'({buffer_frames * frame_bytes / 2**30:.2f} GiB) exceeds the 2 GiB buffer limit; '
                           f'using {max_frames} frames')
            buffer_frames = max_frames
        try:
            self.pvcam.start_live(buffer_frame_count=buffer_frames)
        except Exception:
            if buffer_frames <= 16:
                raise
            logger.exception(f'Photometrics: start_live() with a {buffer_frames}-frame buffer failed; '
                             f'retrying with the PyVCAM default of 16 frames')
            buffer_frames = 16
            self.pvcam.start_live(buffer_frame_count=buffer_frames)
        self.max_frame_count = 0  # frames the camera captured this series
        # PyVCAM < 2.2 (2.1.6 on the rig) has no reset_frame_counter and never resets frame_count,
        # so count from the first frame of the series (TypeError on 2026-10-05)
        self.first_frame_count = None
        logger.info(f'Photometrics image series: circular buffer of {buffer_frames} frames '
                    f'({buffer_frames * frame_bytes / 2**30:.2f} GiB)')

    def get_images_in_series(self):
        '''Return every frame already buffered, waiting up to SERIES_POLL_TIMEOUT_MS for the first one.

        Returns an empty list on timeout.
        '''
        images = []
        timeout_ms = self.SERIES_POLL_TIMEOUT_MS
        while len(images) < self.SERIES_MAX_FRAMES_PER_CALL:
            try:
                frame, _, frame_count = self.pvcam.poll_frame(timeout_ms=timeout_ms)
            except Exception as e:
                if not images:
                    logger.warning(f'Photometrics: no frame within {timeout_ms} ms ({e})')
                break
            # ponytail: undercounts if frames were overwritten before the first poll
            if self.first_frame_count is None:
                self.first_frame_count = int(frame_count)
            self.max_frame_count = max(self.max_frame_count, int(frame_count) - self.first_frame_count + 1)
            images.append(frame['pixel_data'])
            timeout_ms = 1  # after the first frame, take only what is already waiting
        return images
    
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
    '''Camera driver for PCO pco.edge sCMOS cameras in lightsheet (CMOS line timing) mode.

    Written for the ``pco`` Python package 2.x (``pip install pco``; API checked: 2.6.0).
    The rolling shutter reads one line per ``line_interval``, in the direction set by
    ``camera_parameters['readout_direction']`` ('top bottom', or 'inverse' = bottom to top),
    and each line is exposed for round(exposure / line interval) line times. Each frame starts
    on the camera TTL ('external exposure start & software trigger').

    Frames are buffered in a pco recorder in 'fifo' mode: ``recorded_image_count`` is the number
    of unread frames and ``image(0)`` reads the oldest one. When the fifo is full the camera
    pauses (it misses triggers) instead of overwriting frames.

    The recorder is started once, in open_camera(), and left running: stopping it takes 2.27 s in
    the pco SDK (recorder.stop_record, 2026-11-26), which made STOP laggy and would add 2.27 s per
    stack. Live mode and image series start by discarding frames left over from earlier.
    Line timing and exposure can only change while the recorder is stopped, so a change of
    exposure or line interval stops and restarts it (one 2.27 s pause).

    Line time and exposure: startup['camera_line_interval'] and startup['camera_exposure_time'] (s).
    camera_parameters keys: 'trigger', and optional 'readout_direction' (default 'top bottom') and
    'series_buffer_frames' (default 64).
    '''
    # Longest wait for one frame (s): generous for any sweeptime, but finite (see the Photometrics driver).
    SERIES_POLL_TIMEOUT_S = 5.0
    # Frames taken per drain call: everything already buffered, bounded so one call cannot starve the writer.
    SERIES_MAX_FRAMES_PER_CALL = 16

    def __init__(self, parent):
        super().__init__(parent)
        self.cam = None
        self.recording = False
        self.recording_frames = 0
        # Line time and exposure come from startup['camera_line_interval'] / ['camera_exposure_time'] (set by
        # mesoSPIM_GenericCamera), the same values the GUI shows and the metadata records.
        for key in ('line_interval', 'exp_time'):
            if key in self.cfg.camera_parameters:
                logger.warning(f"PCO: camera_parameters['{key}'] is ignored; set startup['camera_line_interval'] "
                               f"and startup['camera_exposure_time'] instead")
        self.readout_direction = self.cfg.camera_parameters.get('readout_direction', 'top bottom')
        if self.readout_direction not in ('top bottom', 'inverse'):
            raise ValueError(f"PCO: camera_parameters['readout_direction'] = {self.readout_direction!r}; "
                             f"lightsheet mode needs 'top bottom' or 'inverse'")
        logger.info('PCO Cam initialized')

    def open_camera(self):
        import pco
        self.cam = pco.Camera()
        logger.info(f'PCO: opened {self.cam.camera_name}, serial {self.cam.camera_serial}')
        self.cam.configuration = {'trigger': self.cfg.camera_parameters['trigger']}
        self._apply_lightsheet()
        self.buffer_frames = int(self.cfg.camera_parameters.get('series_buffer_frames', 64))
        self._start_recording(self.buffer_frames)
        logger.info(f'PCO: recording into a fifo of {self.buffer_frames} frames '
                    f'({self.buffer_frames * self.x_pixels * self.y_pixels * 2 / 2**30:.2f} GiB)')

    def close_camera(self):
        if self.cam is None:
            return
        self._stop_recording()
        self.cam.close()
        self.cam = None

    # ------------------------------------------------------------------ settings
    def _apply_lightsheet(self):
        '''Send line time, exposure lines and readout direction. The recorder must be stopped.'''
        lines_exposure = max(1, int(round(self.camera_exposure_time / self.camera_line_interval)))
        arg = {'line time': self.camera_line_interval, 'lines exposure': lines_exposure}
        # 'top bottom' is the lightsheet default. The pco.edge 4.2 bi USB firmware rejects
        # set_interface_output_format() altogether (0x80031020, "not supported by this hardware",
        # 2026-11-26), so it is only sent when the readout is to be inverted.
        if self.readout_direction != 'top bottom':
            arg['scmos readout'] = self.readout_direction
        try:
            self.cam.lightsheet_configuration = arg
        except Exception as e:
            if 'scmos readout' not in arg:
                raise
            raise RuntimeError(f"PCO: this camera does not accept readout_direction = {self.readout_direction!r} ({e}). "
                               f"Set camera_parameters['readout_direction'] = 'top bottom' and rotate the camera "
                               f"by 180 deg instead.") from e
        # read back with the sdk calls: the lightsheet_configuration getter also queries the
        # interface output format, which this firmware does not support
        lt = self.cam.sdk.get_cmos_line_timing()
        lines = self.cam.sdk.get_cmos_line_exposure_delay()['lines exposure']
        exposure = lt['line time'] * lines
        logger.info(f"PCO lightsheet: line timing {lt['parameter']}, line time {lt['line time'] * 1e6:.2f} us, "
                    f"{lines} lines exposure = {exposure * 1e3:.3f} ms, readout {self.readout_direction}")
        if abs(lt['line time'] - self.camera_line_interval) > 1e-3 * self.camera_line_interval:
            logger.warning(f"PCO: line time is {lt['line time'] * 1e6:.2f} us, requested {self.camera_line_interval * 1e6:.2f} us")

    def _reconfigure(self):
        '''Apply new timing; restart the recorder if it was running (live mode).'''
        if self.cam is None:
            return
        frames = self.recording_frames if self.recording else 0
        self._stop_recording()
        self._apply_lightsheet()
        if frames:
            self._start_recording(frames)

    def set_exposure_time(self, time):
        self.camera_exposure_time = time
        self._reconfigure()

    def set_line_interval(self, time):
        self.camera_line_interval = time
        self._reconfigure()

    def set_binning(self, binningstring):
        if binningstring != '1x1':
            logger.warning(f'PCO: binning {binningstring} is not supported in lightsheet mode, keeping 1x1')
        self.state['camera_binning'] = '1x1'

    # ------------------------------------------------------------------ recorder
    def _start_recording(self, frames):
        self.cam.record(number_of_images=frames, mode='fifo')
        self.recording = True
        self.recording_frames = frames

    def _stop_recording(self):
        if self.recording:
            self.cam.stop()
            self.recording = False

    def _discard_waiting(self):
        '''Drop frames left in the fifo (e.g. from the end of the previous live session).'''
        n = 0
        while self.cam.recorded_image_count > 0:
            self.cam.image(image_index=0)
            n += 1
        if n:
            logger.debug(f'PCO: discarded {n} stale frame(s)')

    def _read_frames(self, max_frames, timeout_s):
        '''Wait up to timeout_s for a frame, then return up to max_frames already waiting, oldest first.'''
        try:
            self.cam.wait_for_new_image(delay=True, timeout=timeout_s)
        except TimeoutError:
            return []
        images = []
        while len(images) < max_frames and self.cam.recorded_image_count > 0:
            image, _ = self.cam.image(image_index=0)
            images.append(image)
        return images

    # ------------------------------------------------------------------ live / snap
    def initialize_live_mode(self):
        self._discard_waiting()

    def get_live_image(self):
        # one frame per sweep; drain all waiting frames so the fifo never fills, show the newest
        images = self._read_frames(self.buffer_frames, self.SERIES_POLL_TIMEOUT_S)
        if not images:
            logger.warning(f'PCO: no live frame within {self.SERIES_POLL_TIMEOUT_S} s')
        return images[-1:]

    def get_image(self):
        images = self._read_frames(self.buffer_frames, self.SERIES_POLL_TIMEOUT_S)
        if not images:
            raise TimeoutError(f'PCO: no frame within {self.SERIES_POLL_TIMEOUT_S} s')
        return images[-1]

    def close_live_mode(self):
        pass  # recorder keeps running, see the class docstring

    # ------------------------------------------------------------------ image series
    def initialize_image_series(self):
        self._discard_waiting()

    def get_images_in_series(self):
        '''Return every frame already buffered, waiting up to SERIES_POLL_TIMEOUT_S for the first one.

        Returns an empty list on timeout.
        '''
        images = self._read_frames(self.SERIES_MAX_FRAMES_PER_CALL, self.SERIES_POLL_TIMEOUT_S)
        if not images:
            logger.warning(f'PCO: no frame within {self.SERIES_POLL_TIMEOUT_S} s')
        return images

    def close_image_series(self):
        pass  # recorder keeps running, see the class docstring

    