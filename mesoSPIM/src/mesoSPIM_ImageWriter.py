'''
mesoSPIM Image Writer class, intended to run in the Camera Thread and handle file I/O
'''

import os
import time
import numpy as np
import psutil
import tifffile
import logging
logger = logging.getLogger(__name__)
import sys
from PyQt5 import QtCore
from distutils.version import StrictVersion
from .mesoSPIM_State import mesoSPIM_StateSingleton
import npy2bdv
from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import write_line, gb_size_of_array_shape, replace_with_underscores


class mesoSPIM_ImageWriter(QtCore.QObject):
    def __init__(self, parent=None):
        '''Image and metadata writer class. Parent is mesoSPIM_Camera() object'''
        super().__init__()

        self.parent = parent # a mesoSPIM_Camera() object
        self.cfg = parent.cfg

        self.state = mesoSPIM_StateSingleton()
        self.running_flag = self.abort_flag = False

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
        self.bigtiff_aliases = ('.btf', '.tf2', '.tf8')
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

    def acquisition_shape(self):
        '''Return a tuple of acquisition shape (z,y,x)'''
        return (self.max_frame, self.x_pixels, self.y_pixels)

    def allocate_ram(self):
        '''Return a numpy array filled with zeros that maximizes for available RAM
        but leaves a percentage of RAM free.

        If shape of the acquisition is smaller, allocate the smaller array.
        '''
        self.buffering_on = False
        if not hasattr(self.cfg, 'buffering') or not self.cfg.buffering['use_ram_buffer']:
            msg = 'No RAM buffer specified in config file. Continuing without RAM buffer. To turn on RAM buffering, add a "buffering" dictionary to the config file.'
            logger.info(msg)
            print(msg)
            buffer_shape = (1, self.x_pixels, self.y_pixels)
        else:
            self.buffering_on = True
            percent_ram_free = self.cfg.buffering['percent_ram_free']
            ram = psutil.virtual_memory()
            must_remain_free_GB = ram.total*(percent_ram_free/100)
            max_amount_useable = ram.available - must_remain_free_GB
            size_of_1_image = self.y_pixels * self.x_pixels * 16 / 8 # Assume np.uint16

            if max_amount_useable < size_of_1_image:
                # Case where there is not enough RAM for even 1 image
                msg = f'There is not enough RAM available to maintain {percent_ram_free} percent free RAM: Continuing acquisition without RAM buffer'
                logger.warning(msg)
                print(msg)

            z_layers_to_allocate = int(max_amount_useable // size_of_1_image) - 1
            z_layers_to_allocate = z_layers_to_allocate if z_layers_to_allocate >= 1 else 1

            if gb_size_of_array_shape(self.acquisition_shape()) <= max_amount_useable/1024**3:
                buffer_shape = self.acquisition_shape()
            else:
                buffer_shape = (z_layers_to_allocate, self.x_pixels, self.y_pixels)
        return np.zeros(buffer_shape, dtype='uint16')

    def less_than_gb(self, gb):
        '''Is the size of the acquisition array smaller than some size in gigabytes'''
        num_pix = self.max_frame * self.y_pixels * self.x_pixels
        size = (num_pix*16/8) / (1024**3) # in gigabytes
        if size < gb:
            return True
        else:
            return False

    def remove_image_buffer(self):
        self.image_buffer = None  # Clear RAM

    def ram_percent_remaing_free(self):
        ram = psutil.virtual_memory()
        total = ram.total
        free = ram.free
        return (free/total)*100

    def prepare_acquisition(self, acq, acq_list):
        self.folder = acq['folder']
        self.filename = replace_with_underscores(acq['filename'])
        self.path = os.path.realpath(self.folder+'/'+self.filename)
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
            if hasattr(self.cfg, "hdf5") and ('transpose_xy' in self.cfg.hdf5.keys()) and self.cfg.hdf5['transpose_xy']:
                tile_translation = (sign_xyz[1] * acq['y_pos'] / px_size_um,
                                    sign_xyz[0] * acq['x_pos'] / px_size_um,
                                    sign_xyz[2] * acq['z_start'] / acq['z_step'])
            else:
                tile_translation = (sign_xyz[0] * acq['x_pos'] / px_size_um,
                                    sign_xyz[1] * acq['y_pos'] / px_size_um,
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

        elif self.file_extension in self.bigtiff_aliases:
            self.tiff_writer = tifffile.TiffWriter(self.path, bigtiff=True)

        if acq['processing'] == 'MAX' and self.file_extension in (('.raw',) + self.tiff_aliases + self.bigtiff_aliases):
            self.tiff_mip_writer = tifffile.TiffWriter(self.file_root + "_MAX.tiff", imagej=True)
            self.mip_image = np.zeros((self.y_pixels, self.x_pixels), 'uint16')

        self.cur_image_counter = 0
        self.written_image_counter = 0
        self.abort_flag = False
        self.running_flag = True

        self.acq = acq
        self.acq_list = acq_list

        #Create a RAM buffer for acquisition that keeps {self.percent_ram_free} of total RAM free
        self.image_buffer = self.allocate_ram()

    def write_image(self, image, acq, acq_list):
        if self.buffering_on:
            logger.debug('Copy image to RAM buffer started')
            self.image_buffer[self.written_image_counter % self.image_buffer.shape[0]] = image # this single operation takes 40-50 ms to complete. Note that both 0 % 1 and 0 % 1 == 0, dangerous!
            logger.debug('Copy image to RAM buffer ended') 
        self.written_image_counter += 1
        if (self.written_image_counter % self.image_buffer.shape[0] == 0) or (self.written_image_counter == self.max_frame) or self.abort_flag:
            self.image_to_disk(acq, acq_list, image)

    def image_to_disk(self, acq, acq_list, image):
        logger.debug('image_to_disk() started') # 60 ms total in demo mode, v.1.9.0
        self.parent.parent.sig_status_message.emit('Flushing data to disk...')
        while True:
            if self.buffering_on:
                logger.debug('Copy image from RAM buffer started')
                image = self.image_buffer[self.cur_image_counter % self.image_buffer.shape[0]] # Note that both 0 % 1 and 1 % 1 == 0, dangerous!
                logger.debug('Copy image from RAM buffer ended')
            else:
                pass # use the 'image' directly
            xy_res = (1./self.cfg.pixelsize[acq['zoom']], 1./self.cfg.pixelsize[acq['zoom']])
            if self.file_extension == '.h5':
                self.bdv_writer.append_plane(plane=image, z=self.cur_image_counter,
                                             illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                             channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                             angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                             tile=acq_list.get_tile_index(acq)
                                             )
            elif self.file_extension == '.raw':
                self.xy_stack[self.cur_image_counter * self.fsize:(self.cur_image_counter + 1) * self.fsize] = image.flatten()
            elif self.file_extension in self.tiff_aliases:
                self.tiff_writer.write(image[np.newaxis,...], contiguous=True, resolution=xy_res,
                                       metadata={'spacing': acq['z_step'], 'unit': 'um'})
            elif self.file_extension in self.bigtiff_aliases:
                self.tiff_writer.write(image[np.newaxis,...], contiguous=False, resolution=xy_res, # tile=(1024,1024), compression='lzw', #compression requires imagecodecs
                                       metadata={'spacing': acq['z_step'], 'unit': 'um'})

            if acq['processing'] == 'MAX' and self.file_extension in (('.raw',) + self.tiff_aliases + self.bigtiff_aliases):
                self.mip_image[:] = np.maximum(self.mip_image, image)

            self.cur_image_counter += 1
            # Terminate loop if the full buffer has been dumped to disk or if all images from acquisition have been dumped to disk
            if self.cur_image_counter % self.image_buffer.shape[0] == 0 or self.cur_image_counter == self.max_frame or self.buffering_on == False:
                self.parent.parent.sig_status_message.emit('Running Acquisition')
                break
            elif self.abort_flag and self.cur_image_counter == self.written_image_counter:
                self.parent.parent.sig_status_message.emit('Running Acquisition')
                break

        if not self.running_flag:
            logger.info("No image, running terminated")
        logger.debug('image_to_disk() ended')

    def abort_writing(self):
        """Terminate writing and close all files if STOP button is pressed"""
        self.abort_flag = True
        if self.running_flag:
            try:
                self.image_to_disk(self.acq, self.acq_list)  # Flush remaining buffer to disk
                if self.file_extension == '.h5':
                    self.bdv_writer.close()
                elif self.file_extension == '.raw':
                    del self.xy_stack
                elif self.file_extension in (self.tiff_aliases + self.bigtiff_aliases):
                    self.tiff_writer.close()
                self.metadata_file.close()
            except Exception as e:
                logger.error(f'{e}')
            print("Writing terminated, files closed")
            self.running_flag = False
            self.remove_image_buffer() #Free RAM
            self.abort_flag = False
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
        elif self.file_extension in (self.tiff_aliases + self.bigtiff_aliases):
            try:
                self.tiff_writer.close()
            except Exception as e:
                logger.error(f'{e}')

        if acq['processing'] == 'MAX' and self.file_extension in (('.raw',) + self.tiff_aliases + self.bigtiff_aliases):
            try:
                self.tiff_mip_writer.write(self.mip_image)
                self.tiff_mip_writer.close()
            except Exception as e:
                logger.error(f'{e}')

        self.running_flag = False
        self.remove_image_buffer()  # Free RAM

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

    def write_snap_metadata(self, path):
        metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'
        with open(metadata_path, 'w') as file:
            write_line(file, 'CFG')
            write_line(file, 'Laser', self.state['laser'])
            write_line(file, 'Intensity (%)', self.state['intensity'])
            write_line(file, 'Zoom', self.state['zoom'])
            write_line(file, 'Pixelsize in um', self.state['pixelsize'])
            write_line(file, 'Filter', self.state['filter'])
            write_line(file, 'Shutter', self.state['shutterconfig'])
            write_line(file)
            write_line(file, 'POSITION')
            write_line(file, 'x_pos', self.state['position']['x_pos'])
            write_line(file, 'y_pos', self.state['position']['y_pos'])
            write_line(file, 'z_pos', self.state['position']['z_pos'])
            write_line(file, 'f_pos', self.state['position']['f_pos'])
            write_line(file)
            ''' Attention: change to true ETL values ASAP '''
            write_line(file, 'ETL PARAMETERS')
            write_line(file, 'ETL CFG File', self.state['ETL_cfg_file'])
            write_line(file, 'etl_l_offset', self.state['etl_l_offset'])
            write_line(file, 'etl_l_amplitude', self.state['etl_l_amplitude'])
            write_line(file, 'etl_r_offset', self.state['etl_r_offset'])
            write_line(file, 'etl_r_amplitude', self.state['etl_r_amplitude'])
            write_line(file)
            write_line(file, 'GALVO PARAMETERS')
            write_line(file, 'galvo_l_frequency', self.state['galvo_l_frequency'])
            write_line(file, 'galvo_l_amplitude', self.state['galvo_l_amplitude'])
            write_line(file, 'galvo_l_offset', self.state['galvo_l_offset'])
            write_line(file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
            write_line(file, 'galvo_r_offset', self.state['galvo_r_offset'])
            write_line(file)
            write_line(file, 'CAMERA PARAMETERS')
            write_line(file, 'camera_type', self.cfg.camera)
            write_line(file, 'camera_exposure', self.state['camera_exposure_time'])
            write_line(file, 'camera_line_interval', self.state['camera_line_interval'])
            write_line(file, 'x_pixels', self.cfg.camera_parameters['x_pixels'])
            write_line(file, 'y_pixels', self.cfg.camera_parameters['y_pixels'])

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def write_metadata(self, acq, acq_list):
        logger.debug("write_metadata() started")
        ''' Writes a metadata.txt file. Path contains the file to be written '''
        path = acq['folder'] + '/' + acq['filename']
        metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'

        if acq['filename'][-3:] == '.h5':
            if acq == acq_list[0]:
                self.metadata_file = open(metadata_path, 'w')
            else:
                self.metadata_file = open(metadata_path, 'a')
        else:
            self.metadata_file = open(metadata_path, 'w')

        write_line(self.metadata_file, 'Metadata for file', path)
        write_line(self.metadata_file)
        # write_line(file, 'COMMENTS')
        # write_line(file, 'Comment: ', acq(['comment']))
        # write_line(file)
        write_line(self.metadata_file, 'CFG')
        write_line(self.metadata_file, 'Laser', acq['laser'])
        write_line(self.metadata_file, 'Intensity (%)', acq['intensity'])
        write_line(self.metadata_file, 'Zoom', acq['zoom'])
        write_line(self.metadata_file, 'Pixelsize in um', self.state['pixelsize'])
        write_line(self.metadata_file, 'Filter', acq['filter'])
        write_line(self.metadata_file, 'Shutter', acq['shutterconfig'])
        write_line(self.metadata_file)
        write_line(self.metadata_file, 'POSITION')
        write_line(self.metadata_file, 'x_pos', acq['x_pos'])
        write_line(self.metadata_file, 'y_pos', acq['y_pos'])
        write_line(self.metadata_file, 'f_start', acq['f_start'])
        write_line(self.metadata_file, 'f_end', acq['f_end'])
        write_line(self.metadata_file, 'z_start', acq['z_start'])
        write_line(self.metadata_file, 'z_end', acq['z_end'])
        write_line(self.metadata_file, 'z_stepsize', acq['z_step'])
        write_line(self.metadata_file, 'z_planes', acq.get_image_count())
        write_line(self.metadata_file, 'rot', acq['rot'])
        write_line(self.metadata_file)
        ''' Attention: change to true ETL values ASAP '''
        write_line(self.metadata_file, 'ETL PARAMETERS')
        write_line(self.metadata_file, 'ETL CFG File', self.state['ETL_cfg_file'])
        write_line(self.metadata_file, 'etl_l_offset', self.state['etl_l_offset'])
        write_line(self.metadata_file, 'etl_l_amplitude', self.state['etl_l_amplitude'])
        write_line(self.metadata_file, 'etl_r_offset', self.state['etl_r_offset'])
        write_line(self.metadata_file, 'etl_r_amplitude', self.state['etl_r_amplitude'])
        write_line(self.metadata_file)
        write_line(self.metadata_file, 'GALVO PARAMETERS')
        write_line(self.metadata_file, 'galvo_l_frequency', self.state['galvo_l_frequency'])
        write_line(self.metadata_file, 'galvo_l_amplitude', self.state['galvo_l_amplitude'])
        write_line(self.metadata_file, 'galvo_l_offset', self.state['galvo_l_offset'])
        write_line(self.metadata_file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
        write_line(self.metadata_file, 'galvo_r_offset', self.state['galvo_r_offset'])
        write_line(self.metadata_file)
        write_line(self.metadata_file, 'CAMERA PARAMETERS')
        write_line(self.metadata_file, 'camera_type', self.cfg.camera)
        write_line(self.metadata_file, 'camera_exposure', self.state['camera_exposure_time'])
        write_line(self.metadata_file, 'camera_line_interval', self.state['camera_line_interval'])
        write_line(self.metadata_file, 'x_pixels', self.cfg.camera_parameters['x_pixels'])
        write_line(self.metadata_file, 'y_pixels', self.cfg.camera_parameters['y_pixels'])
        write_line(self.metadata_file)
        self.metadata_file.close()
        logger.debug("write_metadata() ended")
