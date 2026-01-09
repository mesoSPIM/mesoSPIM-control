import os
from pathlib import Path
import time
import logging
logger = logging.getLogger(__name__)
import numpy as np
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from mesoSPIM.src.plugins.ImageWriterApi import (
    ImageWriter, WriterCapabilities, WriteRequest, API_VERSION, FileNaming, WriteImage, FinalizeImage
)

# Install zarr via pip if needed
from mesoSPIM.src.plugins.utils import install_and_import
install_and_import('zarr', version='3.1.3')
import zarr

from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriter.omezarr_writer import (
    PyramidSpec, ChunkScheme,
    Live3DPyramidWriter, plan_levels,
    compute_xy_only_levels, FlushPad,
    BloscCodec, BloscShuffle,
    XmlWriter
)


class OMEZarrWriter(ImageWriter):
    '''
    Write Tiles as OME-Zarr
    Each tile is written into a different folder inside a larger .ome.zarr folder.
    This writer also produces a BigStitcher XML file (only for ome zarr v0.4) for easy import into BigStitcher


    OME.ZARR parameters
    This ImageWriter generates ome.zarr specification multiscale data on the fly during acquisition.
    The default parameter should work pretty well for most setups with little to no performance degradation
    during acquisition. Defaults include compression which will save disk space and can also improve
    performance because less data is written to disk. Data are written into shards which limits the number of
    files generated on disk.

    Chunks can be set to adjust with each multiscale. Base and target chunks are defined and will start
    with the base shape and automatically shift towards target with each scale. Chunks have a big influence on IO.
    Bigger chunks means less and more efficient IO, very small chunks will degrade performance on some hardware.
    Test on your hardware.

    ome_version: default: "0.5". Selects whether to write ome-zarr v0.5 (zarr v3 and support for sharding) or
    v0.4 (zarr v2 and NO support for sharding). If "0.4" is selected, the 'shards' option is ignored.

    compression: default: zstd-5. This is a good trade off of compute and compression. In our tests, there is
    little to no performance degradation when using this setting.

    generate_multiscales: default: True. True will generate ome-zarr specification multiscale during acquisition.
    False will only save the original resolution data.

    shards are defined by default. Be careful, shard shape must be defined carefully to prevent performance
    degradation. We suggest that shards are shallow in Z and as large as you camera sensor in XY.
    For best performance set the base and target chunks to the same z-depth as your shards.

    async_finalize: default: True. Enables acquisition of the next tile to proceed immediately while the multiscale
    is finalized in the background. On systems with slow IO, data can accumulate in RAM and cause a crash.
    Slow IO can be improved by using bigger chunks. If bigger chunks do not help, use async_finalize: False
    to make mesoSPSIM pause after each tile acquisition until the multiscale is finished generating.


    OPTIONAL: Place the following entry into the mesoSPIM configuration file and change as needed

    OME_Zarr_Writer = {
        'ome_version': '0.5', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
        'generate_multiscales': True, #True, False. False: only the primary data is saved. True: multiscale data is generated
        'compression': 'zstd', # None, 'zstd', 'lz4'
        'compression_level': 5, # 1-9
        'shards': (64,6000,6000), # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
        'base_chunks': (64,256,256), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
        'target_chunks': (64,64,64), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
        'async_finalize': True, # True, False

        # BigStitcher Specific Options
        'write_big_stitcher_xml': True, # True, False
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy': False, # in case X and Y axes need to be swapped for the correct BigStitcher tile positions
        }

        '''

    writer = None
    write_request = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'OME_Zarr_Writer'

    @classmethod
    def capabilities(cls):
        return WriterCapabilities(
            dtype=["uint16"],
            ndim=[2, 3],
            supports_chunks=True,
            supports_compression=True,
            supports_multiscale=True,
            supports_overwrite=False,
            streaming_safe=True,
        )
    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        return ['.ome.zarr', '.zarr']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'OME Zarr: ~.ome.zarr', # Selection Box Test when selecting file format
            WindowTitle = "Autogenerate OME Zarr File Names",
            WindowSubTitle = "Files are saved in OME Zarr '.ome.zarr' format",
            WindowDescription = cls.name(), # Unique description to register with ui
            IncludeMag = True,
            IncludeTile = False,
            IncludeChannel = True,
            IncludeFilter = False,
            IncludeShutter = False,
            IncludeRotation = False,
            IncludeSuffix = None,      # Str suffix to be appended to the end of filenames
            SingleFileFormat = True,  # Will all tiles be written into 1 file (.h5 for example)
            IncludeAllChannelsInSingleFileFormat = True,  # Will put all channels in name if SingleFileFormat==True
        )

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), f'URI suffix not compatible with {self.name()}'

        #######################
        ####  GET Defaults  ###
        #######################
        ome_version = '0.5'  # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
        generate_multiscales = True  # True, False. False: only the primary data is saved. True: multiscale data is generated
        compression = 'zstd'  # None, 'zstd', 'lz4'
        compression_level = 5  # 1-9
        shards = (64, 6000, 6000)  # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
        base_chunks = (64, 256, 256)  # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
        target_chunks = (64, 64, 64)  # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
        async_finalize = True  # True, False

        # BigStitcher XML Options Defaults - for easy drag/drop import into BigStitcher
        write_big_stitcher_xml = True  # True, False
        flip_xyz = (False, False, False)  # match BigStitcher coordinates to mesoSPIM axes.
        transpose_xy = False  # in case X and Y axes need to be swapped for the correct BigStitcher tile positions

        #####################################
        ####  Load from Config if defined ###
        #####################################
        if req.writer_config_file_values:
            ome_version = req.writer_config_file_values.get('ome_version', ome_version)
            generate_multiscales = req.writer_config_file_values.get('generate_multiscales', generate_multiscales)
            if 'compression' in req.writer_config_file_values:
                # Deals with case where compression is None in config so it is retained
                compression = req.writer_config_file_values.get('compression')
            else:
                pass
            compression_level = req.writer_config_file_values.get('compression_level', compression_level)
            shards = req.writer_config_file_values.get('shards', shards)
            base_chunks = req.writer_config_file_values.get('base_chunks', base_chunks)
            target_chunks = req.writer_config_file_values.get('target_chunks', target_chunks)
            async_finalize = req.writer_config_file_values.get('async_finalize', async_finalize)
            write_big_stitcher_xml = req.writer_config_file_values.get('write_big_stitcher_xml', write_big_stitcher_xml)
            flip_xyz = req.writer_config_file_values.get('flip_xyz', flip_xyz)
            transpose_xy = req.writer_config_file_values.get('transpose_xy', transpose_xy)

        acq = req.acq
        acq_list = req.acq_list

        # Logic for naming files and metadata
        # Define descriptive group name for this tile
        mag = acq['zoom'][:-1]  # remove x at end
        laser = acq['laser'][:-3]  # remove nm at end
        rot = acq['rot']
        shutter_id = acq['shutterconfig']
        shutter_id = 0 if shutter_id == 'Left' else 1
        tile = acq_list.get_tile_index(acq)
        filter = acq['filter']
        filter = filter.replace(' ', '_').replace('/', '_')  # clean up filter name for filename
        group_name = f'Mag{mag}_Tile{tile}_Ch{laser}_Flt{filter}_Sh{shutter_id}_Rot{rot}.ome.zarr'
        self.omezarr_group_name = group_name

        self.current_acquire_file_path = req.uri + '/' + self.omezarr_group_name

        self.metadata_file_path = req.uri + '_' + self.omezarr_group_name + '_meta.txt'
        # self.MIP_path = self.first_folder + '/MAX_' + self.filename + '_' + self.omezarr_group_name + '.tiff'
        self.big_stitcher_xml_filename = str(req.uri) + '.xml'

        # create writer object if the view is first in the list
        if acq == acq_list[0]:
            zarr_version = 2 if ome_version == "0.4" else 3
            zarr.open_group(req.uri, mode="a", zarr_version=zarr_version)

            if write_big_stitcher_xml and ome_version == "0.4":
                # the BigStitcher XML overhead
                self.xml_writer = XmlWriter(self.big_stitcher_xml_filename,
                                            nsetups=len(acq_list),
                                            nilluminations=req.num_shutters,
                                            nchannels=req.num_channels,
                                            nangles=req.num_rotations,
                                            ntiles=req.num_tiles,
                                            ntimes=1)
            else:
                self.xml_writer = None

        px_size_zyx = (req.z_res, req.y_res, req.x_res)

        if self.xml_writer:
            sign_xyz = (1 - np.array(flip_xyz)) * 2 - 1

            if transpose_xy:
                tile_translation = (sign_xyz[1] * acq['y_pos'] / px_size_zyx[1],
                                    sign_xyz[0] * acq['x_pos'] / px_size_zyx[2],
                                    sign_xyz[2] * acq['z_start'] / px_size_zyx[0])
            else:
                tile_translation = (sign_xyz[0] * acq['x_pos'] / px_size_zyx[2],
                                    sign_xyz[1] * acq['y_pos'] / px_size_zyx[1],
                                    sign_xyz[2] * acq['z_start'] / px_size_zyx[0])

            affine_matrix = np.array(((1.0, 0.0, 0.0, tile_translation[0]),
                                      (0.0, 1.0, 0.0, tile_translation[1]),
                                      (0.0, 0.0, 1.0, tile_translation[2])))



            self.xml_writer.append_acquisition(iacq=acq_list.index(acq),
                                               group_name=self.omezarr_group_name,
                                               illumination=acq_list.find_value_index(acq['shutterconfig'],
                                                                                      'shutterconfig'),
                                               channel=acq_list.find_value_index(acq['laser'], 'laser'),
                                               angle=acq_list.find_value_index(acq['rot'], 'rot'),
                                               tile=acq_list.get_tile_index(acq),
                                               voxel_units='um',
                                               voxel_size_xyz=(px_size_zyx[2], px_size_zyx[1], px_size_zyx[0]),
                                               calibration=(1.0, 1.0, px_size_zyx[0] / px_size_zyx[2]),
                                               m_affine=affine_matrix,
                                               name_affine="Translation to Regular Grid",
                                               stack_shape_zyx=(req.shape[0], req.shape[2], req.shape[1])
                                               # x and y need to be exchanged to account for the image rotation
                                               )
        # ZARR Writer setup
        Z_EST, Y, X = (req.shape[0], req.shape[2], req.shape[1])

        xy_levels = compute_xy_only_levels(px_size_zyx)
        if generate_multiscales:
            levels = plan_levels(Y, X, Z_EST, xy_levels, min_dim=64)
        else:
            levels = 1

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
            path=self.current_acquire_file_path,
            max_workers=os.cpu_count() // 2,
            chunk_scheme=scheme,
            compressor=compressor,
            shard_shape=shard_shape,
            flush_pad=FlushPad.DUPLICATE_LAST,  # keeps alignment, no RMW
            async_close=async_finalize,
            translation=(acq['z_start'], acq['y_pos'], acq['x_pos']),
            ome_version=ome_version
        )

        self.metadata_file_info()



    def write_frame(self, data: WriteImage):
        self.omezarr_writer.push_slice(data.image)

    def finalize(self, finalize_image=FinalizeImage) -> None:
        self.omezarr_writer.close()

        if self.xml_writer:
            acq = finalize_image.acq
            acq_list = finalize_image.acq_list
            if acq == acq_list[-1]: # On last tile, write BigStitcher XML
                self.xml_writer.set_attribute_labels('channel', tuple(acq_list.get_unique_attr_list('laser')))
                self.xml_writer.set_attribute_labels('illumination', tuple(acq_list.get_unique_attr_list('shutterconfig')))
                self.xml_writer.set_attribute_labels('angle', tuple(acq_list.get_unique_attr_list('rot')))
                self.xml_writer.write()

    def abort(self) -> None:
        self.omezarr_writer.close()

    def metadata_file_info(self) -> str:
        """
        Return the file name for the current metadata file.
        This function should be updated as needed and is called after self.open() for each tile
        Default appends '_meta.txt' to the filename (i.e. WriteRequest.uri)
        Appends to attrs to be used for writing metadata
            self.metadata_file                        # Actual file where metadata is stored
            self.metadata_file_describes_this_path    # The specific file described by self.metadata_file

        Reasonable defaults are set for ImageWriter that are 1_Tile=1_file
        This may need to be overwritten if FileNaming(SingleFileFormat=True)
        """

        self.metadata_file = self.req.uri + f'_{self.omezarr_group_name}_meta.txt'
        self.metadata_file_describes_this_path = Path(self.current_acquire_file_path).as_posix()

        # Placeholder prior to adding data processing plugins
        path = Path(self.req.uri + f'_{self.omezarr_group_name}')
        self.MIP_path = path.with_name('MAX_' + path.name + '.tif').as_posix()