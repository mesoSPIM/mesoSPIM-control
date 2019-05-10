'''
mesoSPIM Camera class, intended to run in its own thread
'''
import os
import time
import numpy as np

import tifffile

from PyQt5 import QtCore, QtWidgets, QtGui

from .devices.cameras.Demo_Camera import Demo_Camera

try:
    from .devices.cameras.hamamatsu import hamamatsu_camera as cam
except:
    pass

from .mesoSPIM_State import mesoSPIM_StateSingleton

class mesoSPIM_HamamatsuCamera(QtCore.QObject):
    sig_camera_status = QtCore.pyqtSignal(str)
    sig_camera_frame = QtCore.pyqtSignal(np.ndarray)
    sig_finished = QtCore.pyqtSignal()

    sig_update_gui_from_state = QtCore.pyqtSignal(bool)

    sig_state_updated = QtCore.pyqtSignal()

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

        self.camera_line_interval = self.cfg.startup['camera_line_interval']
        self.camera_exposure_time = self.cfg.startup['camera_exposure_time']

        ''' Wiring signals '''
        self.parent.sig_state_request.connect(self.state_request_handler)

        self.parent.sig_prepare_image_series.connect(self.prepare_image_series, type=3)
        self.parent.sig_add_images_to_image_series.connect(self.add_images_to_series)
        self.parent.sig_add_images_to_image_series_and_wait_until_done.connect(self.add_images_to_series, type=3)
        self.parent.sig_end_image_series.connect(self.end_image_series, type=3)

        self.parent.sig_prepare_live.connect(self.prepare_live, type = 3)
        self.parent.sig_get_live_image.connect(self.get_live_image)
        self.parent.sig_get_snap_image.connect(self.get_snap_image)
        self.parent.sig_end_live.connect(self.end_live, type=3)

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

            # Diagnostic output 
            self.hcam.setPropertyValue("output_trigger_active[0]",1) # {'EDGE': 1}
            self.hcam.setPropertyValue("output_trigger_kind[0]",3) #  {'LOW': 1, 'EXPOSURE': 2, 'PROGRAMABLE': 3, 'TRIGGER READY': 4, 'HIGH': 5}
            self.hcam.setPropertyValue("output_trigger_polarity[0]",2) # {'NEGATIVE': 1, 'POSITIVE': 2}
            self.hcam.setPropertyValue("output_trigger_source[0]",4) # {'READOUT END': 2, 'VSYNC': 3, 'HSYNC': 4, 'TRIGGER': 6}

            # Subarray Mode 
            self.hcam.setPropertyValue("output_trigger_active[0]",1)

        elif self.cfg.camera == 'Demo':
            self.hcam = Demo_Camera()

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
            if key in ('camera_exposure_time','camera_line_interval','state','camera_sensor_mode'):
                exec('self.set_'+key+'(value)')

    def set_state(self, requested_state):
        pass

        # if requested_state == ('live' or 'run_selected_acquisition' or 'run_acquisition_list'):
        #     self.live()
        # elif requested_state == 'idle':
        #     self.stop()

    def open(self):
        pass

    def close(self):
        pass

    @QtCore.pyqtSlot()
    def stop(self):
        ''' Stops acquisition '''
        self.stopflag = True

    def set_camera_sensor_mode(self, mode):
        if mode == 'Area':
            self.hcam.setPropertyValue("sensor_mode", 1)
        elif mode == 'ASLM':
            self.hcam.setPropertyValue("sensor_mode", 12)
        else:
            print('Camera mode not support')

    def set_camera_exposure_time(self, time):
        '''
        Sets the exposure time in seconds

        Args:
            time (float): exposure time to set
        '''
        self.camera_exposure_time = time
        self.hcam.setPropertyValue("exposure_time", time)
        self.sig_update_gui_from_state.emit(True)
        self.state['camera_exposure_time'] = time
        self.sig_update_gui_from_state.emit(False)

    def set_camera_line_interval(self, time):
        '''
        Sets the line interval in seconds

        Args:
            time (float): interval time to set
        '''
        self.camera_line_interval = time
        self.hcam.setPropertyValue("internal_line_interval",self.camera_line_interval)
        self.sig_update_gui_from_state.emit(True)
        self.state['camera_line_interval'] = time
        self.sig_update_gui_from_state.emit(False)
    
    def prepare_image_series(self, acq):
        '''
        Row is a row in a AcquisitionList
        '''
        print('Cam: Preparing Image Series')
        self.stopflag = False

        ''' TODO: Needs cam delay, sweeptime, QTimer, line delay, exp_time '''

        self.path = acq['folder']+'/'+acq['filename']

        print('camera path: ', self.path)
        self.z_start = acq['z_start']
        self.z_end = acq['z_end']
        self.z_stepsize = acq['z_step']
        self.max_frame = acq.get_image_count()

        self.fsize = 2048*2048

        self.xy_stack = np.memmap(self.path, mode = "write", dtype = np.uint16, shape = self.fsize * self.max_frame)
        # self.xy_stack_tif = tf.memmap(tif_filename, shape=(self.max_frame, 2048, 2048), dtype = np.uint16)
        # self.xz_stack = np.memmap(self.path[:-4]+'xz.raw', mode = "write", dtype = np.uint16, shape = 2048 * self.max_frame * 2048)
        # self.yz_stack = np.memmap(self.path[:-4]+'yz.raw', mode = "write", dtype = np.uint16, shape = 2048 * self.max_frame * 2048)

        self.hcam.startAcquisition()
        self.cur_image = 0
        print('Cam: Finished Preparing Image Series')
        self.start_time = time.time()

    def add_images_to_series(self):
        
        # QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 1)
        if self.stopflag is False:
            print('Camera: Adding images started')
            if self.cur_image + 1 < self.max_frame:
                [frames, dims] = self.hcam.getFrames()

                # for aframe in frames:
                    
                #     image = aframe.getData()
                #     self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image

                #     image = np.reshape(image, (-1, 2048))
                #     # image = np.rot90(image)
                #     self.sig_camera_frame.emit(image)
                #     # ''' Creating a 512x512 subimage '''
                #     # if self.cur_image % 20 == 0:
                #     #     subimage = image[0:2048:4,0:2048:4]
                #     #     self.sig_camera_frame.emit(subimage)
                #     # image = image.flatten()
                #     print('Done with image: #', self.cur_image)
                #     self.cur_image += 1
                num_frames = len(frames)
                for aframe in frames:
                
                    image = aframe.getData()

                    image = np.reshape(image, (-1, 2048))
                    image = np.rot90(image)

                    # if (num_frames == 1) and (self.cur_image % 2 == 0):
                    #     subimage = image[0:2048:4,0:2048:4]
                    #     self.sig_camera_frame.emit(subimage)
                    
                    self.sig_camera_frame.emit(image)
                    image = image.flatten()
                    self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image
                    
                    print('Done with image: #', self.cur_image)
                    self.cur_image += 1

            print('Camera: Adding images ended')
        else:
            print('Camera: Acquisition stop requested...')

    def end_image_series(self):
        try:
            self.hcam.stopAcquisition()
            del self.xy_stack
            print('Acq finished')
            print("Saved", self.cur_image + 1, "frames")
        except:
            print('Camera: Error when finishing acquisition.')

        self.end_time =  time.time()
        framerate = (self.cur_image + 1)/(self.end_time - self.start_time)
        print('Framerate: ', framerate)
        self.sig_finished.emit()

    def snap_image(self):
        pass

    def prepare_live(self):
        self.hcam.setACQMode(mode = "run_till_abort")
        self.hcam.startAcquisition()

        self.live_image_count = 0 

        self.start_time = time.time()

    def get_live_image(self):
        [frames, _] = self.hcam.getFrames()

        for aframe in frames:
            image = aframe.getData()
            image = np.reshape(image, (-1, 2048))
            image = np.rot90(image)

                 
            self.sig_camera_frame.emit(image)
            self.live_image_count += 1
            self.sig_camera_status.emit(str(self.live_image_count))

    def end_live(self):        
        self.hcam.stopAcquisition()
        self.end_time =  time.time()
        framerate = (self.live_image_count + 1)/(self.end_time - self.start_time)
        print('Framerate: ', framerate)

    def get_snap_image(self):
        [frames, _] = self.hcam.getFrames()

        for aframe in frames:
            image = aframe.getData()
            image = np.reshape(image, (-1, 2048))
            image = np.rot90(image)

            start_number = self.state['start_number']
            num_string = '000000'
            filename = num_string[:-len(str(start_number))]+str(start_number) + '.tif'

            path = self.state['snap_folder']+'/'+filename

            #self.xy_image = np.memmap(path, mode = "write", dtype = np.uint16, shape = 2048*2048)
            
            self.sig_camera_frame.emit(image)

            tifffile.imsave(path, image, photometric='minisblack')

            #image = image.flatten()
            #self.xy_image[0:2048*2048] = image

            self.state['start_number'] = self.state['start_number'] + 1

            #del self.xy_image

# class mesoSPIM_DemoCamera(mesoSPIM_Camera):
#     def __init__(self, config, parent = None):
#         super().__init__(config, parent)
