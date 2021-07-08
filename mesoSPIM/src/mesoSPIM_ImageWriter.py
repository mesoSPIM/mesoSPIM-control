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
from PyQt5 import QtCore

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
            if hasattr(self.cfg, "hdf5"):
                subsamp = self.cfg.hdf5['subsamp']
                compression = self.cfg.hdf5['compression']
                flip_flags = self.cfg.hdf5['flip_xyz']
            else:
                subsamp = ((1, 1, 1),)
                compression = None
                flip_flags = (False, False, False)
            # create writer object if the view is first in the list
            if acq == acq_list[0]:
                self.bdv_writer = npy2bdv.BdvWriter(self.path,
                                                    nilluminations=acq_list.get_n_shutter_configs(),
                                                    nchannels=acq_list.get_n_lasers(),
                                                    nangles=acq_list.get_n_angles(),
                                                    ntiles=acq_list.get_n_tiles(),
                                                    blockdim=((1, 256, 256),),
                                                    subsamp=subsamp,
                                                    compression=compression)
            # x and y need to be exchanged to account for the image rotation
            shape = (self.max_frame, self.y_pixels, self.x_pixels)
            px_size_um = self.cfg.pixelsize[acq['zoom']]
            sign_xyz = (1 - np.array(flip_flags)) * 2 - 1
            affine_matrix = np.array(((1.0, 0.0, 0.0, sign_xyz[0] * acq['x_pos']/px_size_um),
                                      (0.0, 1.0, 0.0, sign_xyz[1] * acq['y_pos']/px_size_um),
                                      (0.0, 0.0, 1.0, sign_xyz[2] * acq['z_start']/acq['z_step'])))
            self.bdv_writer.append_view(stack=None, virtual_stack_dim=shape,
                                        illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                        channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                        angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                        tile=acq_list.get_tile_index(acq),
                                        voxel_units='um',
                                        voxel_size_xyz=(px_size_um, px_size_um, acq['z_step']),
                                        calibration=(1.0, 1.0, acq['z_step']/px_size_um),
                                        m_affine=affine_matrix,
                                        name_affine="Translation to Regular Grid"
                                        )
        elif self.file_extension == '.raw':
            self.fsize = self.x_pixels*self.y_pixels
            self.xy_stack = np.memmap(self.path, mode="write", dtype=np.uint16, shape=self.fsize * self.max_frame)

        elif self.file_extension == '.tiff':
            self.tiff_writer = tifffile.TiffWriter(self.path)
'''
use .write() instead of .save() if version >=2020.9.30
Explore the options:
bigtiff : bool
	If True, the BigTIFF format is used.
byteorder : {'<', '>', '=', '|'}
	The endianness of the data in the file.
	By default, this is the system's native byte order.
append : bool
	If True and 'file' is an existing standard TIFF file, image data
	and tags are appended to the file.
	Appending data may corrupt specifically formatted TIFF files
	such as OME-TIFF, LSM, STK, ImageJ, or FluoView.
imagej : bool
	If True and not 'ome', write an ImageJ hyperstack compatible file.
	This format can handle data types uint8, uint16, or float32 and
	data shapes up to 6 dimensions in TZCYXS order.
	RGB images (S=3 or S=4) must be uint8.
	ImageJ's default byte order is big-endian but this implementation
	uses the system's native byte order by default.
	ImageJ hyperstacks do not support BigTIFF or compression.
	The ImageJ file format is undocumented.
	When using compression, use ImageJ's Bio-Formats import function.
ome : bool
	If True, write an OME-TIFF compatible file. If None (default),
	the value is determined from the file name extension, the value of
	the 'description' parameter in the first call of the write
	function, and the value of 'imagej'.
	Refer to the OME model for restrictions of this format.
'''
        self.cur_image = 0

    def write_image(self, image, acq, acq_list):
        if self.file_extension == '.h5':
            self.bdv_writer.append_plane(plane=image, z=self.cur_image,
                                         illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                         channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                         angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                         tile=acq_list.get_tile_index(acq)
                                         )
        elif self.file_extension == '.raw':
            image = image.flatten()
            self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image
        elif self.file_extension == '.tiff':
            self.tiff_writer.save(image, contiguous=True)

        self.cur_image += 1
        
    def end_acquisition(self, acq, acq_list):
        if self.file_extension == '.h5':
            if acq == acq_list[-1]:
                try:
                    self.bdv_writer.set_attribute_labels('channel', tuple(acq_list.get_unique_attr_list('laser')))
                    self.bdv_writer.set_attribute_labels('illumination', tuple(acq_list.get_unique_attr_list('shutterconfig')))
                    self.bdv_writer.set_attribute_labels('angle', tuple(acq_list.get_unique_attr_list('rot')))
                    self.bdv_writer.write_xml()
                except:
                    logger.error(f'HDF5 XML could not be written: {sys.exc_info()}')
                try:
                    self.bdv_writer.close()
                except:
                    logger.error(f'HDF5 file could not be closed: {sys.exc_info()}')
        elif self.file_extension == '.raw':
            try:
                del self.xy_stack
            except:
                logger.warning('Raw data stack could not be deleted')
        elif self.file_extension == '.tiff':
            try:
                self.tiff_writer.close()
            except:
                logger.warning('TIFF writer could not be closed')
    
    def write_snap_image(self, image):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = timestr + '.tif'
        path = self.state['snap_folder']+'/'+filename
        tifffile.imsave(path, image, photometric='minisblack')


