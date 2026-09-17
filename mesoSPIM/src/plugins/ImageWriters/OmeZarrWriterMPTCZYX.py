import os
import re
from pathlib import Path
import logging
logger = logging.getLogger(__name__)
import numpy as np
from typing import Union

import multiprocessing as mp

from mesoSPIM.src.plugins.ImageWriterApi import (
    WriterCapabilities, WriteRequest, API_VERSION, FileNaming, FinalizeImage
)
from mesoSPIM.src.plugins.ImageWriters.OmeZarrWriterMP import OMEZarrWriterMP

# Install zarr via pip if needed
from mesoSPIM.src.plugins.utils import install_and_import
install_and_import('zarr', version='3.1.3')
import zarr

from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import (
    PyramidSpec, ChunkScheme, plan_levels, compute_xy_only_levels, FlushPad, BloscCodec, BloscShuffle,
)
from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer_tczyx import (
    TCZYX, omezarr_writer_worker_tczyx,
)

# The time index mesoSPIM writes into file names while running a time lapse. It
# goes in front of the LAST suffix, so 'Sample.ome.zarr' becomes
# 'Sample.ome_Time003.zarr' (see mesoSPIM_AcquisitionManagerWindow.append_time_index_to_filenames).
_TIME_SUFFIX = re.compile(r'_Time(\d+)')

# Default false colours for the omero block, by excitation wavelength (nm).
_CHANNEL_COLORS = {'405': '5A73FF', '488': '00FF66', '561': 'FFBF1A', '640': 'FF33FF', '647': 'FF33FF', '785': 'FFFFFF'}


class OMEZarrWriterMPTCZYX(OMEZarrWriterMP):
    '''
    A Multiprocess OME-Zarr Image Writer Plugin that writes ONE (t, c, z, y, x) store per tile.

    This is the MP_OME_Zarr_Writer with a different layout on disk and nothing else changed:
    the frames travel through the same shared-memory ring buffer to a writer process that
    runs the same live multiscale pipeline (Live3DPyramidWriter, untouched, writing through
    a window onto [t, c] of the store's arrays; see omezarr_writer_tczyx.py).

    Layout
        <folder>/<Sample>.ome.zarr/Mag{mag}_Tile{tile}_Sh{shutter}_Rot{rot}.ome.zarr
    Every channel of a tile is one index along c, in the order the lasers appear in the
    acquisition list, and every time point of a time lapse is one index along t. The
    '_Time###' suffix mesoSPIM appends to file names between time points is read to find t
    and stripped from the path, so all time points of a run land in the same stores.
    Channel names and colours go into the omero block, the stage position into the
    coordinateTransformations, as with the other OME-Zarr writers.

    Chunks and shards never span channels or time points: every chunk and every shard
    covers exactly one (t, c). Which channels and time points still come is not known
    when a store is created, so keeping them out of every shard means a later stack
    only ever ADDS files; nothing already on disk is rewritten.

    A shard is written in one go. The live pipeline buffers complete z-chunks over the
    full sensor and writes each as one assignment, so a shard whose z equals the chunk's z
    is one write. A shard deeper than a chunk would be written in several parts, each
    reading the shard back and rewriting it, which is very slow: this writer therefore
    refuses a shard deeper than the base chunk. Shards are off by default (one file per
    chunk), which measured as fast as sharding for this layout; switch them on to limit
    the number of files.

    Not supported here: the BigStitcher XML (a (z, y, x)-per-stack description; use the
    MP_OME_Zarr_Writer if you need it) and 'write_cache' (moving a finished stack into a
    store that already holds other channels would nest the folders).

    OPTIONAL: Place the following entry into the mesoSPIM configuration file and change as needed

    MP_OME_Zarr_TCZYX_Writer = {
        'ome_version': '0.5', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
        'generate_multiscales': True, #True, False. False: only the primary data is saved. True: multiscale data is generated
        'compression': 'zstd', # None, 'zstd', 'lz4'
        'compression_level': 5, # 1-9
        'shards': None, # None (one file per chunk) or a (z,y,x) tuple; z must equal base_chunks z. Ignored if ome_version "0.4"
        'base_chunks': (64,256,256), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
        'target_chunks': (64,64,64), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)

        # Multiprocess options
        'ring_buffer_size': 512, # The number of frames buffered into shared memory for the MP writer.
        }
    '''

    def __init__(self):
        super().__init__()
        # The writer process of each store still running, so that the next channel or
        # time point of a tile waits for the previous one before opening the same store.
        self._store_processes: dict[str, mp.Process] = {}
        # The queues of every process still running. finalize() drops the writer's own
        # references straight away; if the parent's were the last ones, the queues'
        # semaphores would be unlinked while a child that is still starting up (a short
        # stack, a slow disk) tries to attach to them, and it would die on the spot.
        self._queues_in_use: list = []

    @classmethod
    def name(cls) -> str:
        return 'MP_OME_Zarr_TCZYX_Writer'

    @classmethod
    def capabilities(cls):
        return WriterCapabilities(
            dtype=["uint16"],
            ndim=[5],
            supports_chunks=True,
            supports_compression=True,
            supports_multiscale=True,
            supports_overwrite=False,
            streaming_safe=True,
        )

    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        # '.zarr' as well: with the time mark in place the name ends in '_Time003.zarr'.
        return ['.ome.zarr', '.zarr']

    @classmethod
    def file_names(cls):
        return FileNaming(
            # Passed to filename_wizard for selection of file formats in UI
            FormatSelectionOption = 'MP OME Zarr TCZYX: ~.ome.zarr', # Selection Box Test when selecting file format
            WindowTitle = "Autogenerate OME Zarr File Names",
            WindowSubTitle = "One (t, c, z, y, x) OME Zarr store per tile, inside one '.ome.zarr' folder",
            WindowDescription = cls.name(), # Unique description to register with ui
            IncludeMag = True,
            IncludeTile = False,
            IncludeChannel = False,    # channels are the c axis of each tile's store
            IncludeFilter = False,
            IncludeShutter = False,
            IncludeRotation = False,
            IncludeSuffix = None,      # Str suffix to be appended to the end of filenames
            SingleFileFormat = True,   # Will all tiles be written into 1 file (.h5 for example)
            IncludeAllChannelsInSingleFileFormat = False,
        )

    @staticmethod
    def split_time_index(uri: str) -> tuple[str, int]:
        '''The acquisition path without its '_Time###' mark, and the time index (0 without one).'''
        path = Path(uri)
        matches = list(_TIME_SUFFIX.finditer(path.name))
        if not matches:
            return uri, 0
        last = matches[-1]
        name = path.name[:last.start()] + path.name[last.end():]
        return str(path.with_name(name)), int(last.group(1))

    @staticmethod
    def channel_label(laser: str) -> str:
        '''"488 nm" -> "488"'''
        return laser[:-3] if laser.endswith(' nm') else laser

    def open(self, req: WriteRequest) -> None:
        assert self.compatible_suffix(req), f'URI suffix not compatible with {self.name()}'

        #######################
        ####  GET Defaults  ###
        #######################
        ome_version = '0.5'             # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
        generate_multiscales = True     # True, False. False: only the primary data is saved. True: multiscale data is generated
        compression = 'zstd'            # None, 'zstd', 'lz4'
        compression_level = 5           # 1-9
        shards = None                   # None (one file per chunk) or a (z,y,x) tuple with z == base_chunks z; ignored if ome_version "0.4"
        base_chunks = (64, 256, 256)    # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
        target_chunks = (64, 64, 64)    # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)

        # Multiprocess options
        ring_buffer_size = 512          # number of frames that can be queued at once

        #####################################
        ####  Load from Config if defined ###
        #####################################
        if req.writer_config_file_values:
            ome_version = req.writer_config_file_values.get('ome_version', ome_version)
            generate_multiscales = req.writer_config_file_values.get('generate_multiscales', generate_multiscales)
            if 'compression' in req.writer_config_file_values:
                # Deals with case where compression is None in config so it is retained
                compression = req.writer_config_file_values.get('compression')
            compression_level = req.writer_config_file_values.get('compression_level', compression_level)
            shards = req.writer_config_file_values.get('shards', shards)
            base_chunks = req.writer_config_file_values.get('base_chunks', base_chunks)
            target_chunks = req.writer_config_file_values.get('target_chunks', target_chunks)
            ring_buffer_size = req.writer_config_file_values.get('ring_buffer_size', ring_buffer_size)
            for unsupported in ('write_big_stitcher_xml', 'write_cache'):
                if req.writer_config_file_values.get(unsupported):
                    logger.warning(f"{self.name()}: '{unsupported}' is not supported by this writer and is ignored")

        if shards is not None and ome_version != '0.4' and int(shards[0]) != int(base_chunks[0]):
            raise ValueError(
                f"{self.name()}: a shard must be exactly one z-chunk deep so that it is written in one go "
                f"(shards z={shards[0]}, base_chunks z={base_chunks[0]}); a deeper shard would be rewritten "
                "for every chunk landing in it"
            )

        # Save req so metadata_file_info can see it
        self.req = req
        acq = req.acq
        acq_list = req.acq_list

        # Logic for naming files and metadata
        # Define descriptive group name for this tile: the channel is an index inside the store
        mag = acq['zoom'][:-1]  # remove x at end
        rot = acq['rot']
        shutter_id = acq['shutterconfig']
        shutter_id = 0 if shutter_id == 'Left' else 1
        tile = acq_list.get_tile_index(acq)
        group_name = f'Mag{mag}_Tile{tile}_Sh{shutter_id}_Rot{rot}.ome.zarr'
        self.omezarr_group_name = group_name

        # Where this stack lands: the store of its tile, at (t, c)
        self.acquisition_path, time_index = self.split_time_index(req.uri)
        lasers = acq_list.get_unique_attr_list('laser')
        channel_index = lasers.index(acq['laser'])
        self.channel_label_of_this_stack = self.channel_label(acq['laser'])
        self.current_acquire_file_path = self.acquisition_path + '/' + self.omezarr_group_name
        self.metadata_file_path = req.uri + '_' + self.omezarr_group_name + '_meta.txt'

        # create the acquisition group on the first stack of the run
        if time_index == 0 and acq == acq_list[0]:
            zarr_version = 2 if ome_version == "0.4" else 3
            zarr.open_group(self.acquisition_path, mode="a", zarr_version=zarr_version)
        self.xml_writer = None

        # An earlier stack of this same store (another channel, or the previous time point)
        # may still be finishing in the background: its trim of z and this stack's growth of t
        # must not meet. Other tiles keep running in the background as before.
        self._wait_for_store(self.current_acquire_file_path)

        px_size_zyx = (req.z_res, req.y_res, req.x_res)

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

        shard_shape = tuple(shards) if shards is not None else None
        scheme = ChunkScheme(base=tuple(base_chunks), target=tuple(target_chunks))

        compressor = compression
        if compression:
            compressor = BloscCodec(cname=compression, clevel=compression_level, shuffle=BloscShuffle.bitshuffle)

        tczyx = TCZYX(
            t=time_index,
            c=channel_index,
            n_channels=len(lasers),
            channel_labels=tuple(self.channel_label(laser) for laser in lasers),
            channel_colors=tuple(_CHANNEL_COLORS.get(self.channel_label(laser), '') for laser in lasers),
        )

        # Setup multiprocessing ring buffer
        self._create_shared_ringbuffer(ring_buffer_size, req.shape[1], req.shape[2])
        shm_name = self._shm.name

        # --- Create queues ---
        ctx = mp.get_context("spawn")
        self._work_q = ctx.Queue(maxsize=ring_buffer_size)
        self._free_q = ctx.Queue(maxsize=ring_buffer_size)

        # Initialize free-slot queue with all indices
        for i in range(ring_buffer_size):
            self._free_q.put(i)

        # --- Spawn writer process, which owns Live3DPyramidWriter ---
        writer_kwargs = dict(
            spec=spec,
            voxel_size=px_size_zyx,
            path=self.current_acquire_file_path,
            ingest_queue_size=256,
            max_workers=2,
            max_inflight_chunks=8,
            chunk_scheme=scheme,
            compressor=compressor,
            shard_shape=shard_shape,
            flush_pad=FlushPad.DUPLICATE_LAST,
            async_close=False, # Force sync close to ensure all data is written before proceeding, sync not compatible with Multiprocess
            translation=(acq['z_start'], acq['y_pos'], acq['x_pos']),
            ome_version=ome_version,
            tczyx=tczyx,
        )

        self._writer_proc = ctx.Process(
            target=omezarr_writer_worker_tczyx,  # From omezarr_writer_tczyx.py
            args=(shm_name, (Y, X), ring_buffer_size, writer_kwargs, self._work_q, self._free_q),
            daemon=True,
        )

        self._writer_proc.start()

        # remember this writer as "in the background", and as the one holding this store
        self._background_writers.append((self._writer_proc, shm_name))
        self._store_processes[self.current_acquire_file_path] = self._writer_proc
        self._queues_in_use.append((self._work_q, self._free_q))
        logger.debug("Added a new writer process to the list, total writer processes running: %d", len(self._background_writers))

        self.omezarr_writer = None  # keep attribute for compatibility

        self.metadata_file_info()

    def finalize(self, finalize_image: FinalizeImage) -> None:
        super().finalize(finalize_image)
        acq = finalize_image.acq
        acq_list = finalize_image.acq_list
        if acq == acq_list[-1]:
            # The end of a time point: let every store settle before the next time point
            # (or the end of the run) so nothing is left half-written in the background.
            self._wait_for_background_writers()
            self._store_processes.clear()
            self._queues_in_use.clear()

    def _wait_for_store(self, store_path: str) -> None:
        '''Block until the writer process last given this store has finished.'''
        proc = self._store_processes.pop(store_path, None)
        if proc is None or not proc.is_alive():
            return
        logger.info(f'{self.name()}: waiting for the previous stack of {Path(store_path).name} to finish')
        proc.join()

    def metadata_file_info(self) -> str:
        """
        Return the file name for the current metadata file.
        One metadata file per stack: the store name says which tile, the suffix which channel,
        and the time index stays in req.uri.
        """
        self.metadata_file = self.req.uri + f'_{self.omezarr_group_name}_Ch{self.channel_label_of_this_stack}_meta.txt'
        self.metadata_file_describes_this_path = Path(self.current_acquire_file_path).as_posix()

        # Placeholder prior to adding data processing plugins
        path = Path(self.req.uri + f'_{self.omezarr_group_name}_Ch{self.channel_label_of_this_stack}')
        self.MIP_path = path.with_name('MAX_' + path.name + '.tif').as_posix()
