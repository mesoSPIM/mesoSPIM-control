import os
import time
import logging
logger = logging.getLogger(__name__)
import numpy as np
import npy2bdv
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter, WriterCapabilities, WriteRequest, API_VERSION, FileNaming, \
    WriteImage, FinalizeImage


class H5BDVWriter(ImageWriter):
    '''
    Write Tiles in Big Data Viewer .h5 format

    H5_BDV_Writer plugin parameters, if this format is used for data saving (optional).
    Downsampling and compression may slow down writing by 5x - 10x, use with caution.
    Imaris can open these files if no subsampling and no compression is used.

    OPTIONAL: Place the following entry into the mesoSPIM configuration file and change as needed

    H5_BDV_Writer = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
            'compression': None, # None, 'gzip', 'lzf'
            'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
            'transpose_xy': False, # in case X and Y axes need to be swapped for the correct tile positions
            }
    '''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'H5_BDV_Writer'

    @classmethod
    def capabilities(cls):
        return WriterCapabilities(
            dtype=["uint8", "uint16", "float32"],
            ndim=[2, 3],
            supports_chunks=False,
            supports_compression=False,
            supports_multiscale=False,
            supports_overwrite=False,
            streaming_safe=True,
        )
    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        return ['h5']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'H5 BDV files: ~.h5', # Selection Box Test when selecting file format
            WindowTitle = "Autogenerate H5 BDV filenames",
            WindowSubTitle = "Files are saved in Big Stitcher .h5 format",
            WindowDescription = cls.name(), # Unique description to register with ui
            IncludeMag = True,
            IncludeTile = False,
            IncludeChannel = True,
            IncludeShutter = False,
            IncludeRotation = False,
            IncludeSuffix = 'bdv',      # Str suffix to be appended to the end of filenames
            SingleFileFormat = True,  # Will all tiles be written into 1 file (.h5 for example)
            IncludeAllChannelsInSingleFileFormat = True,  # Will put all channels in name if SingleFileFormat==True
        )

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), f'URI suffix not compatible with {self.name()}'

        # Defaults
        subsamp = ((1, 1, 1),)
        compression = None
        flip_flags = (True, True, False)
        transpose_xy = False

        if req.writer_config_file_values:
            subsamp = req.writer_config_file_values.get('subsamp', subsamp)
            compression = req.writer_config_file_values.get('compression', compression)
            flip_flags = req.writer_config_file_values.get('flip_xyz', flip_flags)
            transpose_xy = req.writer_config_file_values.get('transpose_xy', transpose_xy)

        # create writer object if the view is first in the list
        if req.acq == req.acq_list[0]:
            self.writer = npy2bdv.BdvWriter(req.uri,
                                                nilluminations=req.num_shutters,
                                                nchannels=req.num_channels,
                                                nangles=req.num_rotations,
                                                ntiles=req.num_tiles,
                                                blockdim=((1, 256, 256),),
                                                subsamp=subsamp,
                                                compression=compression)

        z_max, x_pixels, y_pixels = req.shape # xy need to be exchanged to account for the image rotation
        shape = (z_max, y_pixels, x_pixels)
        px_size_um = req.x_res
        sign_xyz = (1 - np.array(flip_flags)) * 2 - 1
        if transpose_xy:
            tile_translation = (sign_xyz[1] * req.acq['y_pos'] / px_size_um,
                                sign_xyz[0] * req.acq['x_pos'] / px_size_um,
                                sign_xyz[2] * req.acq['z_start'] / req.acq['z_step'])
        else:
            tile_translation = (sign_xyz[0] * req.acq['x_pos'] / px_size_um,
                                sign_xyz[1] * req.acq['y_pos'] / px_size_um,
                                sign_xyz[2] * req.acq['z_start'] / req.acq['z_step'])
        affine_matrix = np.array(((1.0, 0.0, 0.0, tile_translation[0]),
                                  (0.0, 1.0, 0.0, tile_translation[1]),
                                  (0.0, 0.0, 1.0, tile_translation[2])))
        self.writer.append_view(stack=None, virtual_stack_dim=shape,
                                    illumination=req.acq_list.find_value_index(req.acq['shutterconfig'], 'shutterconfig'),
                                    channel=req.acq_list.find_value_index(req.acq['laser'], 'laser'),
                                    angle=req.acq_list.find_value_index(req.acq['rot'], 'rot'),
                                    tile=req.acq_list.get_tile_index(req.acq),
                                    voxel_units='um',
                                    voxel_size_xyz=(px_size_um, px_size_um, req.acq['z_step']),
                                    calibration=(1.0, 1.0, req.acq['z_step']/px_size_um),
                                    m_affine=affine_matrix,
                                    name_affine="Translation to Regular Grid"
                                    )



    def write_frame(self, data: WriteImage):

        self.writer.append_plane(plane=data.image, z=data.current_image_counter,
                                     illumination=data.acq_list.find_value_index(data.acq['shutterconfig'], 'shutterconfig'),
                                     channel=data.acq_list.find_value_index(data.acq['laser'], 'laser'),
                                     angle=data.acq_list.find_value_index(data.acq['rot'], 'rot'),
                                     tile=data.acq_list.get_tile_index(data.acq)
                                     )
        # flush H5 every 100 frames
        if (data.current_image_counter + 1) % 100 == 0:
            self.writer._file_object_h5.flush()
            logger.debug(f'flushed at {data.current_image_counter + 1} frames to disk')

    def finalize(self, finalize_image=FinalizeImage) -> None:

        acq = finalize_image.acq
        acq_list = finalize_image.acq_list

        if acq == acq_list[-1]:
            try:
                self.writer.set_attribute_labels('channel', tuple(acq_list.get_unique_attr_list('laser')))
                self.writer.set_attribute_labels('illumination',
                                                     tuple(acq_list.get_unique_attr_list('shutterconfig')))
                self.writer.set_attribute_labels('angle', tuple(acq_list.get_unique_attr_list('rot')))
                self.writer.write_xml()
            except:
                pass
                logger.error(f'HDF5 XML could not be written: {sys.exc_info()}')
            try:
                self.writer.close()
            except:
                pass
                logger.error(f'HDF5 file could not be closed: {sys.exc_info()}')
        else:
            self.writer._file_object_h5.flush()
            logger.info(f'flushed H5')

    def abort(self) -> None:
        self.writer.close()