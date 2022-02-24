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
from distutils.version import StrictVersion
from .mesoSPIM_State import mesoSPIM_StateSingleton
import npy2bdv


class mesoSPIM_ImageWriter(QtCore.QObject):
    def __init__(self, parent=None):
        '''Image and metadata writer class. Parent is mesoSPIM_Camera() object'''
        super().__init__()

        self.parent = parent # a mesoSPIM_Camera() object
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()
        self.running = False

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']

        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.file_extension = ''
        self.bdv_writer = self.tiff_writer = self.tiff_mip_writer = self.mip_image = None
        self.tiff_aliases = ('.tif', '.tiff')
        self.check_versions()

    def check_versions(self):
        """Take care of API changes in different library versions"""
        if StrictVersion(tifffile.__version__) < StrictVersion('2020.9.30'):
            self.tiff_write = tifffile.TiffWriter.save
            print(f"Warning: you are using outdated version of tifffile library {tifffile.__version__}. "
                  f"Upgrade to Python 3.7 and pip-install the latest tifffile version.")
        else:
            self.tiff_write = tifffile.TiffWriter.write

        tifffile.TiffWriter.write = self.tiff_write # rename the entire class method if necessary

    def prepare_acquisition(self, acq, acq_list):
        self.folder = acq['folder']
        self.filename = acq['filename']
        self.path = self.folder+'/'+self.filename
        self.file_root, self.file_extension = os.path.splitext(self.path)
        logger.info(f'Image Writer: Save path: {self.path}')

        self.binning_string = self.state['camera_binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.max_frame = acq.get_image_count()

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
            shape = (self.max_frame, self.x_pixels, self.y_pixels)
            px_size_um = self.cfg.pixelsize[acq['zoom']]
            sign_xyz = (1 - np.array(flip_flags)) * 2 - 1
            if hasattr(self.cfg, "hdf5") and ('transpose_xy' in self.cfg.hdf5.keys())\
                    and self.cfg.hdf5['transpose_xy'] is False:
                tile_translation = (sign_xyz[0] * acq['x_pos'] / px_size_um,
                                    sign_xyz[1] * acq['y_pos'] / px_size_um,
                                    sign_xyz[2] * acq['z_start'] / acq['z_step'])
            else: # Hamamatsu Orca Flash 4 backward compatibility
                tile_translation = (sign_xyz[1] * acq['y_pos'] / px_size_um,
                                    sign_xyz[0] * acq['x_pos'] / px_size_um,
                                    sign_xyz[2] * acq['z_start'] / acq['z_step'])
            affine_matrix = np.array(((1.0, 0.0, 0.0, tile_translation[0]),
                                      (0.0, 1.0, 0.0, tile_translation[1]),
                                      (0.0, 0.0, 1.0, tile_translation[2])))
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

        elif self.file_extension in self.tiff_aliases:
            self.tiff_writer = tifffile.TiffWriter(self.path, imagej=True)

        if acq['processing'] == 'MAX' and self.file_extension in ('.raw', '.tiff', '.tif'):
            self.tiff_mip_writer = tifffile.TiffWriter(self.file_root + "_MAX.tiff", imagej=True)
            self.mip_image = np.zeros((self.y_pixels, self.x_pixels), 'uint16')

        self.cur_image = 0
        self.running = True

    def write_image(self, image, acq, acq_list):
        if self.running:
            xy_res = (1./self.cfg.pixelsize[acq['zoom']], 1./self.cfg.pixelsize[acq['zoom']])
            if self.file_extension == '.h5':
                self.bdv_writer.append_plane(plane=image, z=self.cur_image,
                                             illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                             channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                             angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                             tile=acq_list.get_tile_index(acq)
                                             )
            elif self.file_extension == '.raw':
                self.xy_stack[self.cur_image*self.fsize:(self.cur_image+1)*self.fsize] = image.flatten()
            elif self.file_extension in self.tiff_aliases:
                self.tiff_writer.write(image[np.newaxis,...], contiguous=True, resolution=xy_res,
                                       metadata={'spacing': acq['z_step']})

            if acq['processing'] == 'MAX' and self.file_extension in ('.raw', '.tiff', '.tif'):
                self.mip_image = np.maximum(self.mip_image, image)

            self.cur_image += 1
        else:
            logger.info("No image, running terminated")

    def abort_writing(self):
        """Terminate writing and close all files if STOP button is pressed"""
        if self.running:
            try:
                if self.file_extension == '.h5':
                    self.bdv_writer.close()
                elif self.file_extension == '.raw':
                    del self.xy_stack
                elif self.file_extension in self.tiff_aliases:
                    self.tiff_writer.close()
            except Exception as e:
                    logger.error(f'{e}')
            print("Writing terminated, files closed")
            self.running = False
        else:
            pass

    def end_acquisition(self, acq, acq_list):
        logger.info("end_acquisition() started")
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
            except Exception as e:
                logger.error(f'{e}')
        elif self.file_extension in self.tiff_aliases:
            try:
                self.tiff_writer.close()
            except Exception as e:
                logger.error(f'{e}')

        if acq['processing'] == 'MAX' and self.file_extension in ('.raw', '.tiff', '.tif'):
            try:
                self.tiff_mip_writer.write(self.mip_image)
                self.tiff_mip_writer.close()
            except Exception as e:
                logger.error(f'{e}')

        self.running = False

    def write_snap_image(self, image):
        timestr = time.strftime("%Y%m%d-%H%M%S")
        filename = timestr + '.tif'
        path = self.state['snap_folder'] + '/' + filename
        if os.path.exists(self.state['snap_folder']):
            try:
                tifffile.imsave(path, image, photometric='minisblack')
                self.write_snap_metadata(path)
            except Exception as e:
                logger.error(f"{e}")
        else:
            print(f"Error: Snap folder does not exist: {self.state['snap_folder']}. Choose it from the menu.")

    def write_line(self, file, key='', value=''):
        ''' Little helper method to write a single line with a key and value for metadata
        Adds a line break at the end.
        '''
        if key !='':
            file.write('['+str(key)+'] '+str(value) + '\n')
        else:
            file.write('\n')

    def write_snap_metadata(self, path):
        metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'
        with open(metadata_path, 'w') as file:
            self.write_line(file, 'CFG')
            self.write_line(file, 'Laser', self.state['laser'])
            self.write_line(file, 'Intensity (%)', self.state['intensity'])
            self.write_line(file, 'Zoom', self.state['zoom'])
            self.write_line(file, 'Pixelsize in um', self.state['pixelsize'])
            self.write_line(file, 'Filter', self.state['filter'])
            self.write_line(file, 'Shutter', self.state['shutterconfig'])
            self.write_line(file)
            self.write_line(file, 'POSITION')
            self.write_line(file, 'x_pos', self.state['position']['x_pos'])
            self.write_line(file, 'y_pos', self.state['position']['y_pos'])
            self.write_line(file, 'z_pos', self.state['position']['z_pos'])
            self.write_line(file, 'f_pos', self.state['position']['f_pos'])
            self.write_line(file)
            ''' Attention: change to true ETL values ASAP '''
            self.write_line(file, 'ETL PARAMETERS')
            self.write_line(file, 'ETL CFG File', self.state['ETL_cfg_file'])
            self.write_line(file, 'etl_l_offset', self.state['etl_l_offset'])
            self.write_line(file, 'etl_l_amplitude', self.state['etl_l_amplitude'])
            self.write_line(file, 'etl_r_offset', self.state['etl_r_offset'])
            self.write_line(file, 'etl_r_amplitude', self.state['etl_r_amplitude'])
            self.write_line(file)
            self.write_line(file, 'GALVO PARAMETERS')
            self.write_line(file, 'galvo_l_frequency', self.state['galvo_l_frequency'])
            self.write_line(file, 'galvo_l_amplitude', self.state['galvo_l_amplitude'])
            self.write_line(file, 'galvo_l_offset', self.state['galvo_l_offset'])
            self.write_line(file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
            self.write_line(file, 'galvo_r_offset', self.state['galvo_r_offset'])
            self.write_line(file)
            self.write_line(file, 'CAMERA PARAMETERS')
            self.write_line(file, 'camera_type', self.cfg.camera)
            self.write_line(file, 'camera_exposure', self.state['camera_exposure_time'])
            self.write_line(file, 'camera_line_interval', self.state['camera_line_interval'])
            self.write_line(file, 'x_pixels', self.cfg.camera_parameters['x_pixels'])
            self.write_line(file, 'y_pixels', self.cfg.camera_parameters['y_pixels'])

    def write_metadata(self, acq, acq_list):
        '''
        Writes a metadata.txt file

        Path contains the file to be written
        '''
        path = acq['folder'] + '/' + acq['filename']

        metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'

        # print('Metadata_path: ', metadata_path)
        if acq['filename'][-3:] == '.h5':
            if acq == acq_list[0]:
                self.metadata_file = open(metadata_path, 'w')
        else:
            self.metadata_file = open(metadata_path, 'w')
        self.write_line(self.metadata_file, 'Metadata for file', path)
        self.write_line(self.metadata_file, 'z_stepsize', acq['z_step'])
        self.write_line(self.metadata_file, 'z_planes', acq['planes'])
        self.write_line(self.metadata_file)
        # self.write_line(file, 'COMMENTS')
        # self.write_line(file, 'Comment: ', acq(['comment']))
        # self.write_line(file)
        self.write_line(self.metadata_file, 'CFG')
        self.write_line(self.metadata_file, 'Laser', acq['laser'])
        self.write_line(self.metadata_file, 'Intensity (%)', acq['intensity'])
        self.write_line(self.metadata_file, 'Zoom', acq['zoom'])
        self.write_line(self.metadata_file, 'Pixelsize in um', self.state['pixelsize'])
        self.write_line(self.metadata_file, 'Filter', acq['filter'])
        self.write_line(self.metadata_file, 'Shutter', acq['shutterconfig'])
        self.write_line(self.metadata_file)
        self.write_line(self.metadata_file, 'POSITION')
        self.write_line(self.metadata_file, 'x_pos', acq['x_pos'])
        self.write_line(self.metadata_file, 'y_pos', acq['y_pos'])
        self.write_line(self.metadata_file, 'f_start', acq['f_start'])
        self.write_line(self.metadata_file, 'f_end', acq['f_end'])
        self.write_line(self.metadata_file, 'z_start', acq['z_start'])
        self.write_line(self.metadata_file, 'z_end', acq['z_end'])
        self.write_line(self.metadata_file, 'z_stepsize', acq['z_step'])
        self.write_line(self.metadata_file, 'z_planes', acq.get_image_count())
        self.write_line(self.metadata_file, 'rot', acq['rot'])
        self.write_line(self.metadata_file)

        ''' Attention: change to true ETL values ASAP '''
        self.write_line(self.metadata_file, 'ETL PARAMETERS')
        self.write_line(self.metadata_file, 'ETL CFG File', self.state['ETL_cfg_file'])
        self.write_line(self.metadata_file, 'etl_l_offset', self.state['etl_l_offset'])
        self.write_line(self.metadata_file, 'etl_l_amplitude', self.state['etl_l_amplitude'])
        self.write_line(self.metadata_file, 'etl_r_offset', self.state['etl_r_offset'])
        self.write_line(self.metadata_file, 'etl_r_amplitude', self.state['etl_r_amplitude'])
        self.write_line(self.metadata_file)
        self.write_line(self.metadata_file, 'GALVO PARAMETERS')
        self.write_line(self.metadata_file, 'galvo_l_frequency', self.state['galvo_l_frequency'])
        self.write_line(self.metadata_file, 'galvo_l_amplitude', self.state['galvo_l_amplitude'])
        self.write_line(self.metadata_file, 'galvo_l_offset', self.state['galvo_l_offset'])
        self.write_line(self.metadata_file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
        self.write_line(self.metadata_file, 'galvo_r_offset', self.state['galvo_r_offset'])
        self.write_line(self.metadata_file)
        self.write_line(self.metadata_file, 'CAMERA PARAMETERS')
        self.write_line(self.metadata_file, 'camera_type', self.cfg.camera)
        self.write_line(self.metadata_file, 'camera_exposure', self.state['camera_exposure_time'])
        self.write_line(self.metadata_file, 'camera_line_interval', self.state['camera_line_interval'])
        self.write_line(self.metadata_file, 'x_pixels', self.cfg.camera_parameters['x_pixels'])
        self.write_line(self.metadata_file, 'y_pixels', self.cfg.camera_parameters['y_pixels'])

        if acq['filename'][-3:] == '.h5':
            if acq == acq_list[-1]:
                self.metadata_file.close()
        else:
            self.metadata_file.close()

    def append_timing_info_to_metadata(self, acq, **kwargs):
        '''
        Appends a metadata.txt file
        Arguments:
            acq_start, img_start, img_end, acq_end: strings that contain acquisition and camera start/stop time.
            img_total_time: time count of taking images.
        '''
        for key in kwargs.keys():
            assert key in ('acq_start', 'img_start', 'img_end', 'acq_end', 'img_total_time'), f"Key unknown: {key}"
        path = acq['folder']+'/'+acq['filename']
        metadata_path = os.path.dirname(path)+'/'+os.path.basename(path)+'_meta.txt'
        with open(metadata_path,'a') as file:
            ''' Adding troubleshooting information '''
            self.write_line(file)
            self.write_line(file, 'TIMING INFORMATION')
            self.write_line(file, 'Started stack', kwargs.get('acq_start'))
            self.write_line(file, 'Started taking images', kwargs.get('img_start'))
            self.write_line(file, 'Stopped taking images', kwargs.get('img_end'))
            self.write_line(file, 'Stopped stack', kwargs.get('acq_end'))
            self.write_line(file, 'Frame rate:', str(acq.get_image_count()/kwargs.get('img_total_time')))
