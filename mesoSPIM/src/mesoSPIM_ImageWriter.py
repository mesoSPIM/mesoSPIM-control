'''
mesoSPIM Image Writer class, intended to run in the Camera Thread and handle file I/O
'''

import os
from pathlib import Path
import time
import numpy as np
import tifffile
import logging
logger = logging.getLogger(__name__)
import sys
from PyQt5 import QtCore
from distutils.version import StrictVersion
from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import write_line, gb_size_of_array_shape, replace_with_underscores, log_cpu_core
from .plugins.ImageWriterApi import WriteRequest, WriteImage, FinalizeImage
from .plugins.utils import get_image_writer_from_name, get_image_writer_class_from_name

class mesoSPIM_ImageWriter(QtCore.QObject):
    def __init__(self, parent, frame_queue):
        '''Image and metadata writer class. Parent is mesoSPIM_Camera() object'''
        super().__init__()

        self.parent = parent # a mesoSPIM_Camera() object
        self.cfg = parent.cfg
        self.frame_queue = frame_queue

        self.state = self.parent.state # a mesoSPIM_StateSingleton() object
        self.running_flag = self.abort_flag = False

        self.x_pixels = self.cfg.camera_parameters['x_pixels']
        self.y_pixels = self.cfg.camera_parameters['y_pixels']

        self.binning_string = self.cfg.camera_parameters['binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)

        self.file_extension = ''
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

        if hasattr(self.cfg, 'buffering'):
            msg = "Option 'buffering = {...}' in config file is deprecated from v.1.10.0 and will be ignored, \
 due to improved program performance. You can delete it from the config file."
            logger.info(msg)
            print(msg)

    def prepare_acquisition(self, acq, acq_list):

        if acq == acq_list[0]:
            self.writer_name = acq['image_writer_plugin']
            self.writer = get_image_writer_class_from_name(self.writer_name)() # Get and init () the writer class


        # Extract config values for writer from config file - field = 'name' attribute from Writer plugin
        chunks = compression_method = compression_level = multiscales = overwrite = writer_config_file_values = None
        if hasattr(self.cfg, self.writer_name):
            writer_cfg_value = getattr(self.cfg, self.writer_name)
            chunks = writer_cfg_value.get('chunks', None)
            compression_method = writer_cfg_value.get('compression_method', None)
            compression_level = writer_cfg_value.get('compression_level', 0)
            multiscales = writer_cfg_value.get('multiscales', None)
            overwrite = writer_cfg_value.get('overwrite', False)
            writer_config_file_values = writer_cfg_value

        self.folder = acq['folder']
        self.filename = replace_with_underscores(acq['filename'])
        self.path = os.path.realpath(self.folder + '/' + self.filename)
        # self.MIP_path = os.path.realpath(self.folder + '/MAX_' + self.filename + '.tiff')
        self.file_root, self.file_extension = os.path.splitext(self.path)
        # logger.info(f'Save path: {self.path}')

        self.binning_string = self.state['camera_binning']  # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.max_frame = acq.get_image_count()

        px_size_um = self.cfg.pixelsize[acq['zoom']]

        write_request = WriteRequest(
            uri = self.path,
            shape = (self.max_frame, self.y_pixels, self.x_pixels), #(z,y,x)
            dtype = 'uint16',
            axes = 'ZYX',
            x_res = px_size_um,
            y_res = px_size_um,
            z_res = acq['z_step'],
            unit = 'microns',
            chunks = chunks,
            compression_method = compression_method,
            compression_level = compression_level,
            multiscales = multiscales,
            overwrite = overwrite,
            num_tiles = acq_list.get_n_tiles(),
            num_channels = acq_list.get_n_lasers(),
            num_rotations = acq_list.get_n_angles(),
            num_shutters = acq_list.get_n_shutter_configs(),
            acq = acq,
            acq_list = acq_list,
            writer_config_file_values = writer_config_file_values
        )

        logger.info(f'Opening ImageWriter: {wself.writer.name}')
        self.writer.open(write_request)
        self.MIP_path = self.writer.MIP_path

        # Place holder prior to image processing plugins
        if acq['processing'] == 'MAX':
            self.tiff_mip_writer = tifffile.TiffWriter(self.MIP_path, imagej=True)
            self.mip_image = np.zeros((self.x_pixels, self.y_pixels), 'uint16')

        self.cur_image_counter = 0
        self.abort_flag = False
        self.running_flag = True
        self.acq = acq
        self.acq_list = acq_list

        logger.info(f'Save path: {write_request.uri}')

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def write_images(self, acq, acq_list):
        """Write available images to disk. 
        The actual images are passed via `self.frame_queue` from the Camera thread, NOT via the signal/slot mechanism as before,\
             starting from v.1.10.0. This is to avoid the overhead of signal/slot mechanism and to improve performance."""
        if self.running_flag:
            while len(self.frame_queue) > 0:
                logger.debug('image queue length: ' + str(len(self.frame_queue)))
                image = np.rot90(self.frame_queue.popleft())
                self.image_to_disk(acq, acq_list, image)
        else:
            logger.debug('self.running_flag = False, no images written')

    def image_to_disk(self, acq, acq_list, image):
        logger.debug('image_to_disk() started')
        log_cpu_core(logger, msg='image_to_disk()')
        if self.cur_image_counter % 5 == 0:
            self.parent.sig_status_message.emit('Writing to disk...')

        xy_res = (1. / self.cfg.pixelsize[acq['zoom']], 1. / self.cfg.pixelsize[acq['zoom']])

        write = WriteImage(
            image = image,
            current_image_counter = self.cur_image_counter,
            tile_number=acq_list.get_tile_index(acq),
            laser=acq_list.find_value_index(acq['laser'], 'laser'),
            shutter=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
            rot=acq_list.find_value_index(acq['rot'], 'rot'),
            x_res=xy_res,
            y_res=xy_res,
            z_res=acq['z_step'],
            unit='microns',
            acq = acq,
            acq_list = acq_list,
        )

        self.writer.write_frame(write)

        # Place holder prior to image processing plugins
        if acq['processing'] == 'MAX':
            self.mip_image[:] = np.maximum(self.mip_image, image)

        self.cur_image_counter += 1
        logger.debug('image_to_disk() ended')

    @QtCore.pyqtSlot()
    def abort_writing(self):
        """Terminate writing and close all files if STOP button is pressed"""
        self.abort_flag = True
        if self.running_flag:
            try:
                self.writer.abort()
                self.metadata_file.close()
            except Exception as e:
                logger.error(f'{e}')
            self.parent.sig_status_message.emit("Writing terminated, files closed")
            self.running_flag = False
            self.abort_flag = False
        else:
            pass

    @QtCore.pyqtSlot(Acquisition, AcquisitionList)
    def end_acquisition(self, acq, acq_list):
        finalize_imsge = FinalizeImage(
            acq = acq,
            acq_list = acq_list,
        )
        logger.info("end_acquisition() started")
        try:
            self.writer.finalize(finalize_imsge)
        except Exception as e:
            logger.error(f'{e}')

        # Place holder prior to image processing plugins
        if acq['processing'] == 'MAX':
            try:
                self.tiff_mip_writer.write(self.mip_image)
                self.tiff_mip_writer.close()
            except Exception as e:
                logger.error(f'{e}')

        self.running_flag = False

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
            #write_line(file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
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

        metadata_path = self.writer.metadata_file
        path = self.writer.metadata_file_describes_this_path
        # path = acq['folder'] + '/' + acq['filename']
        # metadata_path = os.path.dirname(path) + '/' + os.path.basename(path) + '_meta.txt'

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
        #write_line(self.metadata_file, 'galvo_r_amplitude', self.state['galvo_r_amplitude'])
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
