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
import npy2bdv
from .utils.acquisitions import AcquisitionList, Acquisition
from .utils.utility_functions import write_line, gb_size_of_array_shape, replace_with_underscores, log_cpu_core
from .utils.omezarr_writer import (PyramidSpec, ChunkScheme,
                                   Live3DPyramidWriter, plan_levels,
                                   compute_xy_only_levels, FlushPad,
                                   BloscCodec, BloscShuffle
                                   )


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
        self.bdv_writer = self.tiff_writer\
            = self.tiff_mip_writer = self.mip_image\
            = self.omezarr_writer = None
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

        if hasattr(self.cfg, 'buffering'):
            msg = "Option 'buffering = {...}' in config file is deprecated from v.1.10.0 and will be ignored, \
 due to improved program performance. You can delete it from the config file."
            logger.info(msg)
            print(msg)

    def prepare_acquisition(self, acq, acq_list):
        self.folder = acq['folder']
        self.filename = replace_with_underscores(acq['filename'])
        self.path = os.path.realpath(self.folder+'/'+self.filename)
        self.MIP_path = os.path.realpath(self.folder +'/MAX_'+ self.filename + '.tiff')
        # self.file_root, self.file_extension = os.path.splitext(self.path)
        self.file_extension = ''.join(Path(self.path).suffixes)
        logger.info(f'Save path: {self.path}')

        self.binning_string = self.state['camera_binning'] # Should return a string in the form '2x4'
        self.x_binning = int(self.binning_string[0])
        self.y_binning = int(self.binning_string[2])

        self.x_pixels = int(self.x_pixels / self.x_binning)
        self.y_pixels = int(self.y_pixels / self.y_binning)
        self.max_frame = acq.get_image_count()

        print(f'{self.file_extension=}')
        if self.file_extension == '.ome.zarr':
            if hasattr(self.cfg, "ome_zarr"):
                compression = self.cfg.ome_zarr['compression']
                compression_level = self.cfg.ome_zarr['compression_level']
                shards = self.cfg.ome_zarr['shards']
                base_chunks = self.cfg.ome_zarr['base_chunks']
                target_chunks = self.cfg.ome_zarr['target_chunks']
                async_finalize = self.cfg.ome_zarr['async_finalize']
            else:
                compression = 'zstd'
                compression_level = 5
                shards = None
                base_chunks = (256,256,256)
                target_chunks = (256,256,256)
                async_finalize = True

            Z_EST, Y, X = (self.max_frame, self.x_pixels, self.y_pixels)
            px_size_zyx = (acq['z_step'], self.cfg.pixelsize[acq['zoom']], self.cfg.pixelsize[acq['zoom']])

            xy_levels = compute_xy_only_levels(px_size_zyx)
            levels = plan_levels(Y, X, Z_EST, xy_levels, min_dim=64)

            spec = PyramidSpec(
                z_size_estimate=Z_EST,  # big upper bound; we'll truncate at the end
                y=Y, x=X, levels=levels,
            )

            shard_shape = shards
            scheme = ChunkScheme(base=base_chunks, target=target_chunks)

            compressor = compression
            if compression:
                compressor = BloscCodec(cname=compression, clevel=compression_level, shuffle=BloscShuffle.bitshuffle)

            self.omezarr_writer = Live3DPyramidWriter(
                    spec,
                    voxel_size=px_size_zyx,
                    path=self.path,
                    max_workers=os.cpu_count() // 2,
                    chunk_scheme=scheme,
                    compressor=compressor,  # keep off for max ingest speed
                    # compressor=BloscCodec(cname="zstd", clevel=5, shuffle=BloscShuffle.bitshuffle),
                    # compressor=BloscCodec(cname="lz4", clevel=1, shuffle=BloscShuffle.bitshuffle),
                    shard_shape=shard_shape,
                    flush_pad=FlushPad.DUPLICATE_LAST,  # keeps alignment, no RMW
                    async_close=async_finalize,
            )

        elif self.file_extension == '.h5':
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
            self.tiff_mip_writer = tifffile.TiffWriter(self.MIP_path, imagej=True)
            self.mip_image = np.zeros((self.x_pixels, self.y_pixels), 'uint16')

        self.cur_image_counter = 0
        self.abort_flag = False
        self.running_flag = True
        self.acq = acq
        self.acq_list = acq_list

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
        xy_res = (1./self.cfg.pixelsize[acq['zoom']], 1./self.cfg.pixelsize[acq['zoom']])

        if self.file_extension == '.ome.zarr':
            self.omezarr_writer.push_slice(image)
        elif self.file_extension == '.h5':
            self.bdv_writer.append_plane(plane=image, z=self.cur_image_counter,
                                            illumination=acq_list.find_value_index(acq['shutterconfig'], 'shutterconfig'),
                                            channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                            angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                            tile=acq_list.get_tile_index(acq)
                                            )
            # flush H5 every 100 frames 
            if (self.cur_image_counter + 1) % 100 == 0:
                self.bdv_writer._file_object_h5.flush()
                logger.debug(f'flushed at {self.cur_image_counter + 1} frames to disk')
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
        logger.debug('image_to_disk() ended')
    
    @QtCore.pyqtSlot()
    def abort_writing(self):
        """Terminate writing and close all files if STOP button is pressed"""
        self.abort_flag = True
        if self.running_flag:
            try:
                if self.file_extension == '.ome.zarr':
                    self.omezarr_writer.__exit__(None, None, None)
                elif self.file_extension == '.h5':
                    self.bdv_writer.close()
                elif self.file_extension == '.raw':
                    del self.xy_stack
                elif self.file_extension in (self.tiff_aliases + self.bigtiff_aliases):
                    self.tiff_writer.close()
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
        logger.info("end_acquisition() started")
        if self.file_extension == '.ome.zarr':
            self.omezarr_writer.__exit__(None, None, None)
        elif self.file_extension == '.h5':
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
            else:
                self.bdv_writer._file_object_h5.flush()
                logger.info(f'flushed H5')
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
