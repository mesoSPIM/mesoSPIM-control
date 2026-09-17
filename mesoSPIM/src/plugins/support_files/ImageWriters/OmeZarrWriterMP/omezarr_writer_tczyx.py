"""
The (t, c, z, y, x) layout for the multi-process OME-Zarr writer.

Everything the MP_OME_Zarr_TCZYX_Writer needs beyond omezarr_writer.py lives here, and
omezarr_writer.py itself is not touched: the live pyramid pipeline (Live3DPyramidWriter)
is reused as it is, and only sees its arrays through a small window that puts every
write at [t, c] of a five-dimensional array.

One store per tile. Each z-stack the microscope acquires lands at [t, c] of the same
arrays: channels are the c axis, time points are appended along t. Chunks and shards get
a leading (1, 1) so none of them ever spans a channel or a time point -- a later channel
or time point only ever adds files, and a shard written once is never rewritten.
"""
import concurrent.futures
import queue
import threading
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Tuple

import numpy as np
import zarr

from . import omezarr_writer as base
from .omezarr_writer import (
    STORE_PATH, ChunkScheme, FlushPad, Live3DPyramidWriter, PyramidSpec,
    _ensure_v2_compressor, ceil_div, compute_xy_only_levels, level_factors, lower_priority,
    pick_shards_for_level,
)


@dataclass
class TCZYX:
    """Where a stack lands in its tile's store, and what the store says about its channels."""
    t: int                                  # time point this stack lands at (appended if new)
    c: int                                  # channel this stack lands at
    n_channels: int                         # the c extent, fixed when the store is created
    channel_labels: Tuple[str, ...] = ()    # omero labels, e.g. ("488", "561")
    channel_colors: Tuple[str, ...] = ()    # omero colours as "RRGGBB"


def omero_block(tczyx: TCZYX) -> dict:
    channels = []
    for i in range(tczyx.n_channels):
        label = tczyx.channel_labels[i] if i < len(tczyx.channel_labels) else f"channel {i}"
        entry = {"label": label, "active": True}
        if i < len(tczyx.channel_colors) and tczyx.channel_colors[i]:
            entry["color"] = tczyx.channel_colors[i]
        channels.append(entry)
    return {"channels": channels}


class StackWindow:
    """
    A (z, y, x) window onto one [t, c] of a (t, c, z, y, x) array.

    It offers the little Live3DPyramidWriter asks of an array -- shape, dtype, slice
    assignment and resize -- so the pipeline writes into a tczyx store without knowing.
    """

    def __init__(self, array, t: int, c: int, fresh: bool):
        self.array = array
        self.t = t
        self.c = c
        self.fresh = fresh    # created by this stack, so it is this stack that trims its depth

    @property
    def shape(self):
        return self.array.shape[2:]

    @property
    def dtype(self):
        return self.array.dtype

    def __setitem__(self, key, value):
        z = key[0] if isinstance(key, tuple) else key
        rest = tuple(key[1:]) if isinstance(key, tuple) else ()
        # A padded last chunk is cut at the array's end: a store that already held a stack
        # keeps the depth that stack was trimmed to.
        stop = min(z.stop, self.array.shape[2])
        n = stop - z.start
        if n <= 0:
            return
        self.array[(self.t, self.c, slice(z.start, stop)) + rest] = value[:n]

    def resize(self, shape):
        """The pipeline trims each level to the planes written when a stack closes; a store
        that held a stack already was trimmed then, and every stack of a tile has the same
        depth, so only an array this stack created is resized."""
        if self.fresh:
            self.array.resize(self.array.shape[:2] + tuple(shape))


def init_ome_zarr_tczyx(spec: PyramidSpec, path, tczyx: TCZYX,
                        chunk_scheme: ChunkScheme = ChunkScheme(),
                        compressor=None,
                        voxel_size=(1.0, 1.0, 1.0), unit="micrometer",
                        translation: Tuple[int, int, int] = (0, 0, 0),  # in units
                        xy_levels: int = 0,
                        shard_shape: Tuple[int, int, int] | None = None,
                        ome_version: str = "0.5"):
    """
    Create the multiscale (t, c, z, y, x) arrays of a tile's store, or open them for the
    next channel or time point, and return (root, windows): one StackWindow per level onto
    [t, c]. The OME metadata is written with the first stack and never changes after: a
    later stack only grows the t extent.

    Mirrors init_ome_zarr in omezarr_writer.py for the array creation.
    """
    zarr_version = 2 if ome_version == "0.4" else 3
    root = zarr.open_group(path, mode="a", zarr_version=zarr_version)
    lead = (tczyx.t + 1, tczyx.n_channels)
    lead_chunk = (1, 1)
    dims = ["t", "c", "z", "y", "x"]
    windows = []
    fresh = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        z_l = ceil_div(spec.z_size_estimate, zf)
        y_l = ceil_div(spec.y, yf)
        x_l = ceil_div(spec.x, xf)
        lvl_shape = (z_l, y_l, x_l)
        chunks = chunk_scheme.chunks_for_level(l, lvl_shape)
        shards_l = pick_shards_for_level(shard_shape, chunks, lvl_shape) if zarr_version == 3 else None

        name = f"{l}"
        if name in root:
            # The same tile again: its next channel or time point. Its z was trimmed when
            # the first stack closed and is never touched again; only t may grow.
            a = root[name]
            if a.shape[1:2] != lead[1:] or a.shape[3:] != lvl_shape[1:] or a.dtype != np.uint16:
                raise ValueError(f"Existing {name}: {a.shape}/{a.dtype} does not fit {lead + lvl_shape}/uint16")
            if a.shape[0] < lead[0]:
                a.resize((lead[0],) + a.shape[1:])
            fresh.append(False)
        elif zarr_version == 3:
            kwargs = dict(name=name, shape=lead + lvl_shape, chunks=lead_chunk + chunks, dtype="uint16")
            if compressor is not None:
                kwargs["compressors"] = [compressor]
            if shards_l is not None:
                kwargs["shards"] = lead_chunk + shards_l
            kwargs["dimension_names"] = dims
            if base.VERBOSE:
                print(f"[init] creating {name}: shape={kwargs['shape']} chunks={kwargs['chunks']} shards={kwargs.get('shards')}")
            a = root.create_array(**kwargs)
            fresh.append(True)
        else:
            if base.VERBOSE:
                print(f"[init] creating {name} (Zarr v2): shape={lead + lvl_shape} chunks={lead_chunk + chunks}")
            # Work around AsyncGroup.create_array() not accepting `dimension_separator`
            from zarr import create as zcreate
            a = zcreate(
                shape=lead + lvl_shape,
                chunks=lead_chunk + chunks,
                dtype="uint16",
                compressor=_ensure_v2_compressor(compressor),
                overwrite=False,
                store=root.store,
                path=name,
                zarr_format=2,
                dimension_separator="/",
            )
            try:
                a.attrs["_ARRAY_DIMENSIONS"] = dims  # dimension hint for some tools
            except Exception:
                pass
            fresh.append(True)
        windows.append(StackWindow(a, tczyx.t, tczyx.c, fresh[-1]))

    if not all(fresh):
        return root, windows

    # OME attributes, written once with the first stack: multiscales with per-axis
    # physical scales, and the channels in an omero block.
    dz, dy, dx = voxel_size
    datasets = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        datasets.append({
            "path": f"{l}",
            "coordinateTransformations": [
                {"type": "scale", "scale": [1.0, 1.0, dz * zf, dy * yf, dx * xf]},
                {"type": "translation", "translation": [0.0, 0.0] + list(translation)},
            ],
        })
    axes = [
        {"name": "t", "type": "time"},
        {"name": "c", "type": "channel"},
        {"name": "z", "type": "space", "unit": unit},
        {"name": "y", "type": "space", "unit": unit},
        {"name": "x", "type": "space", "unit": unit},
    ]
    multiscale = {"axes": axes, "datasets": datasets, "name": "image"}
    if ome_version == "0.5":
        root.attrs["ome"] = {
            "version": "0.5",
            "multiscales": [dict(multiscale, type="image")],
            "omero": omero_block(tczyx),
        }
    else:
        root.attrs["multiscales"] = [dict(multiscale, version="0.4")]
        root.attrs["omero"] = omero_block(tczyx)
    return root, windows


class Live3DPyramidWriterTCZYX(Live3DPyramidWriter):
    """
    Live3DPyramidWriter writing into one [t, c] of a tile's (t, c, z, y, x) store.

    The pipeline is the parent's, untouched: buffering, downsampling, chunk writes and the
    trim of z at close all go through the StackWindows in self.arrs.
    """

    def __init__(self, spec: PyramidSpec, tczyx: TCZYX, voxel_size=(1.0, 1.0, 1.0), path=STORE_PATH,
                 max_workers=None,
                 chunk_scheme: ChunkScheme = ChunkScheme(), compressor=None,
                 flush_pad: FlushPad = FlushPad.DUPLICATE_LAST,
                 ingest_queue_size: int = 8,
                 max_inflight_chunks: int | None = None,
                 async_close: bool = True,
                 shard_shape: Tuple[int, int, int] | None = None,
                 translation: Tuple[int, int, int] = (0, 0, 0),
                 ome_version: str = "0.5"):
        # Mirrors Live3DPyramidWriter.__init__ with the store opened as tczyx. The parent's
        # constructor is not called: it would create (z, y, x) arrays at the same path.
        import os
        self.spec = spec
        self.chunk_scheme = chunk_scheme
        self.flush_pad = flush_pad
        self.xy_levels = compute_xy_only_levels(voxel_size)
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
        self.async_close = async_close
        self.finalize_future = None

        self.root, self.arrs = init_ome_zarr_tczyx(
            spec, path, tczyx,
            chunk_scheme=chunk_scheme, compressor=compressor,
            voxel_size=voxel_size, xy_levels=self.xy_levels,
            shard_shape=shard_shape, translation=translation,
            ome_version=ome_version,
        )

        self.levels = spec.levels
        self.z_counts = [0] * self.levels
        self.buffers = [None] * self.levels
        self.buf_fill = [0] * self.levels
        self.buf_start = [0] * self.levels
        self.zc = []
        self.yx_shapes = []
        for l in range(self.levels):
            zf, yf, xf = level_factors(l, self.xy_levels)
            z_l = ceil_div(self.spec.z_size_estimate, zf)
            y_l = ceil_div(self.spec.y, yf)
            x_l = ceil_div(self.spec.x, xf)
            zc, yc, xc = self.chunk_scheme.chunks_for_level(l, (z_l, y_l, x_l))
            self.zc.append(zc)
            self.yx_shapes.append((y_l, x_l))

        self.q = queue.Queue(maxsize=ingest_queue_size)
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.max_inflight_chunks = max_inflight_chunks or (self.max_workers * 40)
        self._inflight_sem = threading.Semaphore(self.max_inflight_chunks)

        self.worker = threading.Thread(target=self._consume, daemon=True)
        self.worker.start()


def omezarr_writer_worker_tczyx(
    shm_name: str,
    frame_shape: tuple[int, int],
    ring_size: int,
    writer_kwargs: dict,
    work_q,
    free_q,
):
    """
    Child process, as omezarr_writer_worker without the write cache (a stack moved into a
    store that already holds other channels would nest the folders): attaches to the shared
    memory ring, lowers its priority, owns a Live3DPyramidWriterTCZYX, and pushes every
    frame it is handed a slot for.
    """
    lower_priority()
    # The child returns free ring slots through this queue; do not let its feeder thread
    # keep the process alive once the acquisition is over.
    free_q.cancel_join_thread()

    shm = shared_memory.SharedMemory(name=shm_name)
    Y, X = frame_shape
    ring = np.ndarray((ring_size, Y, X), dtype=np.uint16, buffer=shm.buf)

    writer = Live3DPyramidWriterTCZYX(**writer_kwargs)
    try:
        while True:
            slot = work_q.get()
            if slot is None:
                break
            writer.push_slice(ring[slot])   # a view into shared memory
            free_q.put(slot)                # the slot is reusable
    finally:
        try:
            writer.close()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Error closing Live3DPyramidWriterTCZYX in worker")
        shm.close()
