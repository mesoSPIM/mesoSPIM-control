'''
mesoSPIM Image Writer class, intended to run in the Camera Thread and handle file I/O
'''

import os
import time
import numpy as np
import tifffile
import logging
logger = logging.getLogger(__name__)
import sys
from PyQt5 import QtCore, QtWidgets, QtGui

from .mesoSPIM_State import mesoSPIM_StateSingleton

import npy2bdv

class mesoSPIM_ImageWriter(QtCore.QObject):
    def __init__(self, parent = None):
        super().__init__()

        self.parent = parent
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']
        self.x_pixel_size_in_microns = self.cfg.camera_parameters['x_pixel_size_in_microns']
        self.y_pixel_size_in_microns = self.cfg.camera_parameters['y_pixel_size_in_microns']

        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.file_extension = ''
        self.bdv_writer = None

    def prepare_acquisition(self, acq, acq_list):
        self.folder = acq['folder']
        self.filename = acq['filename']
        self.path = self.folder+'/'+self.filename
        logger.info(f'Image Writer: Save path: {self.path}')

        _ , self.file_extension = os.path.splitext(self.filename)

        self.binning_string = self.state['camera_binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.max_frame = acq.get_image_count()
        self.processing_options_string = acq['processing']

        if self.file_extension == '.h5':
            # create writer object if the view is first in the list
            if acq == acq_list[0]:
                self.bdv_writer = npy2bdv.BdvWriter(self.path,
                                                    nilluminations=acq_list.get_n_shutter_configs(),
                                                    nchannels=acq_list.get_n_lasers(),
                                                    nangles=acq_list.get_n_angles())
            # x and y need to be exchanged to account for the image rotation
            shape = (self.max_frame, self.y_pixels, self.x_pixels)
            self.bdv_writer.append_view(stack=None, virtual_stack_dim=shape,
                                        illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                        channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                        angle=acq_list.find_value_index(acq['rot'], 'rot')
                                        )
        else:
            self.fsize = self.x_pixels*self.y_pixels
            self.xy_stack = np.memmap(self.path, mode = "write", dtype = np.uint16, shape = self.fsize * self.max_frame)
    
        self.cur_image = 0

    def write_image(self, image, acq, acq_list):
        if self.file_extension == '.h5':
            self.bdv_writer.append_plane(plane=image, plane_index=self.cur_image,
                                         illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                         channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                         angle=acq_list.find_value_index(acq['rot'], 'rot')
                                         )
        else:
            image = image.flatten()
            self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image

        self.cur_image += 1
        
    def end_acquisition(self, acq, acq_list):
        if self.file_extension == '.h5':
            if acq == acq_list[-1]:
                try:
                    self.bdv_writer.write_xml_file()
                except:
                    logger.warning(f'HDF5 XML could not be written: {sys.exc_info()}')
                try:
                    self.bdv_writer.close()
                except:
                    logger.warning(f'HDF5 file could not be closed: {sys.exc_info()}')
        else:
            try:
                del self.xy_stack
            except:
                logger.warning('Raw data stack could not be deleted')
    
    def write_snap_image(self, image):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = timestr + '.tif'
        path = self.state['snap_folder']+'/'+filename
        tifffile.imsave(path, image, photometric='minisblack')


