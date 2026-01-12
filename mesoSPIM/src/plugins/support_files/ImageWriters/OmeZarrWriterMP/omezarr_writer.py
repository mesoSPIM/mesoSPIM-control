import os
import concurrent.futures
import psutil
from pathlib import Path
import math
import tifffile
import threading, queue
import numpy as np
import zarr
from zarr.codecs import BloscCodec, BloscShuffle, ShardingCodec
from dataclasses import dataclass
from typing import Union, Tuple, Optional
from enum import Enum
from xml.etree import ElementTree as ET

### Multiscale writer ###

VERBOSE = True

# at top-level (after imports)
blosc_threads = max(1, os.cpu_count() // 2)
try:
    import blosc2            # zarr v3 uses python-blosc2
    blosc2.set_nthreads(blosc_threads)  # e.g., half your cores
except Exception:
    pass

STORE_PATH = "volume.ome.zarr"

# ---------- Helpers ----------
def ceil_div(a, b):  # integer ceil
    return -(-a // b)

def ds2_mean_uint16(img: np.ndarray) -> np.ndarray:
    y, x = img.shape
    y2 = y - (y & 1); x2 = x - (x & 1)
    out = img[:y2:2, :x2:2].astype(np.uint32)
    out += img[1:y2:2, :x2:2].astype(np.uint32)
    out += img[:y2:2, 1:x2:2].astype(np.uint32)
    out += img[1:y2:2, 1:x2:2].astype(np.uint32)
    out += 2 # +2 to mean round divide by 4
    out[:] = out >> 2
    # pad edge by replication if odd dims:
    if y & 1: out = np.vstack([out, out[-1:]])
    if x & 1: out = np.hstack([out, out[:, -1:]])
    return out.astype(np.uint16)

def dsZ2_mean_uint16(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Mean of two uint16 slices -> uint16."""
    out = a.astype(np.uint32)
    out += b.astype(np.uint32)
    out += 1 # +1 for mean round divide by 2
    out[:] = out >> 1
    return out.astype(np.uint16)

def infer_n_levels(y, x, z_estimate, min_dim=256):
    """Stop when any axis would shrink below min_dim (spatial) or z_estimate//2**L < 1."""
    levels = 1
    while (min(y, x) // (2 ** levels) >= min_dim) and (z_estimate // (2 ** levels) >= 1):
        levels += 1
    return levels


def compute_xy_only_levels(voxel_size):
    """Return how many leading pyramid levels should be XY-only (no Z decimation),
    so that XY spacing never exceeds Z spacing."""
    dz, dy, dx = map(float, voxel_size)
    # how many 2x steps can XY take without exceeding dz?
    ky = 0 if dy <= 0 else max(0, math.floor(math.log2(dz / dy)))
    kx = 0 if dx <= 0 else max(0, math.floor(math.log2(dz / dx)))
    return int(max(0, min(ky, kx)))  # lockstep XY downsampling

def level_factors(level: int, xy_levels: int):
    """Per-level physical scaling factors relative to level 0 for (z,y,x)."""
    if level <= xy_levels:
        zf = 1
    else:
        zf = 2 ** (level - xy_levels)
    yf = 2 ** level
    xf = 2 ** level
    return zf, yf, xf

def plan_levels(y, x, z_estimate, xy_levels, min_dim=256):
    """Total levels given XY-only prelude, then 3D, stopping when
       min(y_l, x_l) < min_dim or z_l < 1."""
    L = 1
    while True:
        zf, yf, xf = level_factors(L, xy_levels)
        y_l = ceil_div(y, yf)
        x_l = ceil_div(x, xf)
        z_l = ceil_div(z_estimate, zf)
        if min(y_l, x_l) < min_dim or z_l < 1:
            break
        L += 1
    return L


@dataclass
class ChunkSpec:
    z: int = 8
    y: int = 512
    x: int = 512

@dataclass
class PyramidSpec:
    z_size_estimate: int   # upper bound; we trim on close()
    y: int
    x: int
    levels: int




@dataclass
class ChunkScheme:
    """
    Per-level chunking policy that evolves from base -> target as levels increase.
    - base applies at level 0 (e.g., z=8, y=512, x=512)
    - at each level l, we:
        zc = min(target.z, base.z * 2**l)         # z chunk grows toward target
        yc = max(target.y, max(1, base.y // 2**l))# y/x chunks shrink toward target
        xc = max(target.x, max(1, base.x // 2**l))
    Then we clamp to the level's array shape.
    """
    base: Tuple[int, int, int] = (1, 1024, 1024)    # (z, y, x) at level 0
    target: Tuple[int, int, int] = (64, 64, 64)   # desired asymptote

    def chunks_for_level(self, level: int, zyx_level_shape: Tuple[int, int, int]) -> Tuple[int, int, int]:
        z_l, y_l, x_l = zyx_level_shape
        bz, by, bx = self.base
        tz, ty, tx = self.target

        zc = min(tz, max(1, bz * (2 ** level)))
        yc = max(ty, max(1, by // (2 ** level)))
        xc = max(tx, max(1, bx // (2 ** level)))

        # Clamp to the level's actual dimensions
        return (min(zc, z_l), min(yc, y_l), min(xc, x_l))




def _validate_divisible(chunks: Tuple[int,int,int], shards: Tuple[int,int,int]) -> bool:
    return all(c % s == 0 for c, s in zip(chunks, shards))

def _ensure_v2_compressor(compressor):
    """
    If a zarr v3 BloscCodec is passed (e.g., OME-Zarr 0.5 style), convert it to a
    numcodecs.Blosc compatible with Zarr v2 (required for OME-Zarr 0.4).
    Otherwise return compressor unchanged.
    """

    compressor_default = 'zstd'
    clevel_default = 5
    shuffle_default = 2

    import numcodecs
    from numcodecs import Blosc as BloscV2
    numcodecs.blosc.set_nthreads(blosc_threads)
    if BloscV2 is not None and isinstance(compressor, BloscCodec):
        cname_attr = getattr(compressor, "cname", compressor_default)
        # handle enum -> string
        cname = getattr(cname_attr, "value", cname_attr)
        if isinstance(cname, str):
            cname = cname.lower()
        clevel = int(getattr(compressor, "clevel", clevel_default))
        shuffle_attr = getattr(compressor, "shuffle", shuffle_default)
        # normalize shuffle to string key if enum
        shuffle_str = getattr(shuffle_attr, "value", shuffle_attr)
        if isinstance(shuffle_str, str):
            shuffle_str = shuffle_str.lower()
        shuffle_map = {
            "noshuffle": 0,
            "shuffle": 1,
            "bitshuffle": 2,
        }
        shuffle_int = shuffle_map.get(shuffle_str, 1 if shuffle_str not in (0, 1, 2) else shuffle_str)
        return BloscV2(cname=cname, clevel=clevel, shuffle=shuffle_int)


def _coerce_shards(chunks: Tuple[int,int,int],
                   desired: Tuple[int,int,int]) -> Tuple[int,int,int]:
    """
    Guaranteed-valid shards for Zarr v3: choose a divisor of each chunk dim,
    <= desired, never 0.
    """
    out = []
    for d, c in zip(desired, chunks):
        d = int(d); c = int(c)
        # clamp to chunk dim first
        s = min(max(1, d), c)
        # step down by gcd until it divides
        g = math.gcd(s, c)
        if g == 0:   # extremely defensive; shouldn't happen
            g = 1
        # If gcd(s, c) < s, try gcd(down, c) until it divides
        while c % g != 0 and g > 1:
            s = max(1, g)
            g = math.gcd(s, c)
        if c % g != 0:
            # worst-case fallback: 1
            g = 1
        out.append(g)
    return tuple(out)

def pick_shards_for_level(
    desired: Tuple[int,int,int] | None,
    chunks: Tuple[int,int,int],
    lvl_shape: Tuple[int,int,int],
) -> Tuple[int,int,int] | None:
    """
    Zarr v3: choose a shard (super-chunk) shape so that
      - shards[i] is a multiple of chunks[i] (>= 1 * chunks[i])
      - shards[i] <= min(desired[i], lvl_shape[i])
      - if desired is None -> no sharding (return None)
    """
    if desired is None:
        return None
    out = []
    for d, c, n in zip(desired, chunks, lvl_shape):
        c = int(c); n = int(n); d = int(d)
        # upper bound can't exceed the level's extent
        cap = min(d, n)
        # at least one chunk per shard
        k = max(1, cap // c)          # number of chunks per shard along this axis
        s = k * c                      # snap to multiple of chunk
        # (s <= cap <= n) and s % c == 0
        out.append(s)
    return tuple(out)

# ---------- Zarr v3 init (multiscales 0.5) ----------
def init_ome_zarr(spec: PyramidSpec, path=STORE_PATH,
                  chunk_scheme: ChunkScheme = ChunkScheme(),
                  compressor=None,
                  voxel_size=(1.0, 1.0, 1.0), unit="micrometer",
                  translation: Tuple[int, int, int] = (0,0,0), # in units
                  xy_levels: int = 0,
                  shard_shape: Tuple[int,int,int] | None = None,
                  ome_version: str = "0.5"):

    # Map OME-NGFF version to Zarr store version
    zarr_version = 2 if ome_version == "0.4" else 3
    root = zarr.open_group(path, mode="a", zarr_version=zarr_version)
    arrs = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        z_l = ceil_div(spec.z_size_estimate, zf)
        y_l = ceil_div(spec.y, yf)
        x_l = ceil_div(spec.x, xf)
        lvl_shape = (z_l, y_l, x_l)

        chunks = chunk_scheme.chunks_for_level(l, lvl_shape)
        # shards_l = pick_shards_for_level(shard_shape, chunks, lvl_shape)
        shards_l = pick_shards_for_level(shard_shape, chunks, lvl_shape) if zarr_version == 3 else None

        name = f"{l}"
        if name in root:
            a = root[name]
            if a.shape != lvl_shape or a.dtype != np.uint16:
                raise ValueError(f"Existing {name}: {a.shape}/{a.dtype} != {lvl_shape}/uint16")
            if a.shape[0] < z_l:
                a.resize((z_l, y_l, x_l))
        elif zarr_version == 3:
            kwargs = dict(name=name, shape=lvl_shape, chunks=chunks, dtype="uint16")
            if compressor is not None:
                # v3: list of codecs
                kwargs["compressors"] = [compressor]
            if shards_l is not None:
                # v3: inner shard (must divide chunks)
                kwargs["shards"] = shards_l
            kwargs["dimension_names"] = ["z", "y", "x"]
            if VERBOSE:
                print(f"[init] creating {name}: shape={lvl_shape} chunks={chunks} shards={shards_l}")
            a = root.create_array(**kwargs)
        else:
            # Zarr v2 path
            if VERBOSE:
                print(f"[init] creating {name} (Zarr v2): shape={lvl_shape} chunks={chunks}")
            v2_comp = _ensure_v2_compressor(compressor)

            # optional: dimension hint for some tools
            try:
                a.attrs["_ARRAY_DIMENSIONS"] = ["z", "y", "x"]
            except Exception:
                pass

            # Work around AsyncGroup.create_array() not accepting `dimension_separator`
            from zarr import create as zcreate
            a = zcreate(
                shape = lvl_shape,
                chunks = chunks,
                dtype = "uint16",
                compressor = v2_comp,  # numcodecs codec
                overwrite = False,
                store = root.store,  # same store as the group
                path = name,  # create under this group
                zarr_format = 2,  # v2 array
                dimension_separator = "/",  # nested directories in .zarray
            )

        arrs.append(a)

    # OME attributes: multiscales with per-axis physical scales
    dz, dy, dx = voxel_size
    datasets = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        s = [dz * zf, dy * yf, dx * xf]
        datasets.append({
            "path": f"{l}",
            "coordinateTransformations": [
                {"type": "scale", "scale": s},
                {"type": "translation", "translation": list(translation)}
                ],
        })

    axes = [
        {"name": "z", "type": "space", "unit": unit},
        {"name": "y", "type": "space", "unit": unit},
        {"name": "x", "type": "space", "unit": unit},
    ]
    if ome_version == "0.5":
        root.attrs["ome"] = {
            "version": "0.5",
            "multiscales": [{
                "axes": axes,
                "datasets": datasets,
                "name": "image",
                "type": "image",
            }],
        }
    else:
        # OME-Zarr 0.4 stores multiscales at top level
        root.attrs["multiscales"] = [{
            "version": "0.4",
            "axes": axes,
            "datasets": datasets,
            "name": "image",
        }]
    return root, arrs




class FlushPad(Enum):
    DUPLICATE_LAST = "duplicate_last"  # repeat last plane to fill the chunk
    ZEROS = "zeros"                    # pad with zeros
    DROP = "drop"                      # do not flush the tail (you'll lose last planes)


# ---------- Live writer: true 3D decimation pipeline ----------
class Live3DPyramidWriter:
    """
    Streams true-3D (2x in z,y,x) pyramid while you acquire slices.
    Buffers complete Z-chunks per level and flushes only when chunks fill -> no read-modify-write.
    """

    def __init__(self, spec: PyramidSpec, voxel_size=(1.0, 1.0, 1.0), path=STORE_PATH, max_workers=None,
                 chunk_scheme: ChunkScheme = ChunkScheme(), compressor=None,
                 flush_pad: FlushPad = FlushPad.DUPLICATE_LAST,
                 ingest_queue_size: int = 8,
                 max_inflight_chunks: int | None = None,
                 async_close: bool = True,
                 shard_shape: Tuple[int, int, int] | None = None,
                 translation: Tuple[int,int,int] = (0,0,0),
                 ome_version: str = "0.5"):

        self.spec = spec
        self.chunk_scheme = chunk_scheme
        self.flush_pad = flush_pad
        self.xy_levels = compute_xy_only_levels(voxel_size)
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
        self.async_close = async_close
        self.finalize_future = None

        self.root, self.arrs = init_ome_zarr(
            spec, path,
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

        # Concurrency primitives
        self.q = queue.Queue(maxsize=ingest_queue_size)
        self.stop = threading.Event()
        self.lock = threading.Lock()  # sequences z-indices & buffers (single writer to RAM)
        self.pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        )
        # Allow at most ~2 chunks per worker in flight (tweak as you like)
        self.max_inflight_chunks = max_inflight_chunks or (self.max_workers * 40)
        self._inflight_sem = threading.Semaphore(self.max_inflight_chunks)

        self.worker = threading.Thread(target=self._consume, daemon=True)
        self.worker.start()

    # ---------- Public API ----------
    def push_slice(self, slice_u16: np.ndarray):
        assert slice_u16.dtype == np.uint16, "slice must be uint16"
        assert slice_u16.shape == (self.spec.y, self.spec.x), \
            f"got {slice_u16.shape}, expected {(self.spec.y, self.spec.x)}"
        self.q.put(slice_u16, block=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.async_close:
            self.close_async()    # Background finalize
        else:
            self.close_sync()     # synchronous finalize
        print("Live3DPyramidWriter: finalized.")

    def close_sync(self):
        self.stop.set()
        self.q.put(None)
        self.worker.join()

        with self.lock:
            # flush odd Z-pair tails at levels >= 1
            self._flush_pair_tails_all_the_way()

            # Flush any partially filled chunks w/o RMW by padding to full chunk size
            for l in range(self.levels):
                if self.buffers[l] is not None and self.buf_fill[l] > 0:
                    self._pad_and_flush_partial_chunk(l)

        self.pool.shutdown(wait=True)

        for l, a in enumerate(self.arrs):
            a.resize((self.z_counts[l], a.shape[1], a.shape[2]))

    # inside class Live3DPyramidWriter

    def close_async(self):
        """
        Start flushing/closing in a background thread and return a Future.
        You can call future.result() later to wait for completion.
        """
        if getattr(self, "_finalize_future", None) is not None:
            raise RuntimeError("close_async already called")
        self._finalize_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.finalize_future = self._finalize_executor.submit(self._finalize)
        return self.finalize_future

    def _finalize(self):
        self.stop.set()
        self.q.put(None)
        self.worker.join()

        with self.lock:
            self._flush_pair_tails_all_the_way()
            for l in range(self.levels):
                if self.buffers[l] is not None and self.buf_fill[l] > 0:
                    self._pad_and_flush_partial_chunk(l)

        # for fut in self.pending_futs:
        #     fut.result()
        self.pool.shutdown(wait=True)

        for l, a in enumerate(self.arrs):
            a.resize((self.z_counts[l], a.shape[1], a.shape[2]))

        # optional: mark completion for external watchers
        try:
            import pathlib
            store_path = getattr(self.root.store, "path", None)
            if store_path:
                pathlib.Path(store_path, ".READY").write_text("ok")
        except Exception:
            pass

    # ---------- Internals ----------

    def _flush_pair_tails_all_the_way(self):
        if not hasattr(self, "_pair_buf"):
            return
        changed = True
        while changed:
            changed = False
            for lvl in range(max(1, self.xy_levels + 1), self.levels):  # start at first 3D level
                buf = self._pair_buf[lvl]
                if buf is None:
                    continue
                if self.flush_pad == FlushPad.DUPLICATE_LAST:
                    tail = dsZ2_mean_uint16(buf, buf)
                elif self.flush_pad == FlushPad.ZEROS:
                    tail = dsZ2_mean_uint16(buf, np.zeros_like(buf, dtype=np.uint16))
                else:  # DROP
                    self._pair_buf[lvl] = None
                    continue
                self._pair_buf[lvl] = None
                zL = self._reserve_z(lvl)
                self._append_to_active_buffer(lvl, zL, tail)
                self._emit_next(lvl + 1, ds2_mean_uint16(tail))
                changed = True

    def _consume(self):
        while True:
            item = self.q.get()
            if item is None or self.stop.is_set():
                break
            self._ingest_raw(item)

    def _reserve_z(self, level: int) -> int:
        z = self.z_counts[level]
        self.z_counts[level] += 1
        return z

    def _submit_write_chunk(self, level: int, z0: int, buf3d: np.ndarray):
        # acquire *before* grabbing the lock (it’s called from inside-lock code now)

        if self.max_inflight_chunks == 1 and self.max_inflight_chunks == 1: # Helps with single threaded debugging
            self.arrs[level][z0:z0 + buf3d.shape[0], :, :] = buf3d
        else:
            self._inflight_sem.acquire()
            fut = self.pool.submit(self._write_chunk_slice, self.arrs[level], z0, buf3d)
            # Release the slot when done (and drop ref to the future immediately)
            fut.add_done_callback(lambda _f: self._inflight_sem.release())

    @staticmethod
    def _write_chunk_slice(arr, z0, buf3d):
        arr[z0:z0 + buf3d.shape[0], :, :] = buf3d  # contiguous, aligned write

    def _ensure_active_buffer(self, level: int, start_z: int):
        """Allocate active chunk buffer for a level if absent, starting at start_z."""
        if self.buffers[level] is None:
            zc = self.zc[level]
            y_l, x_l = self.yx_shapes[level]
            self.buffers[level] = np.empty((zc, y_l, x_l), dtype=np.uint16)
            self.buf_fill[level] = 0
            self.buf_start[level] = start_z

    def _append_to_active_buffer(self, level: int, z_index: int, plane: np.ndarray):
        """Append plane into the active buffer; flush when full."""
        zc = self.zc[level]
        if self.buf_fill[level] == 0:
            # Align start to chunk boundary; with strictly increasing z, z_index should already align when new chunk begins
            start_z = (z_index // zc) * zc
            self._ensure_active_buffer(level, start_z)

        offset = z_index - self.buf_start[level]
        self.buffers[level][offset, :, :] = plane
        self.buf_fill[level] += 1

        if self.buf_fill[level] == zc:
            # Full chunk -> flush and reset
            buf = self.buffers[level]
            z0 = self.buf_start[level]
            # hand a copy to the pool to avoid mutation races
            self.buffers[level] = None
            self.buf_fill[level] = 0
            self.buf_start[level] = z0 + zc
            self._submit_write_chunk(level, z0, buf)

    def _pad_and_flush_partial_chunk(self, level: int):
        """Pad the active buffer to full chunk size (duplicate last or zeros) and flush."""
        zc = self.zc[level]
        fill = self.buf_fill[level]
        if fill == 0:
            return
        buf = self.buffers[level]
        if self.flush_pad == FlushPad.DUPLICATE_LAST:
            last = buf[fill - 1:fill, :, :]
            repeat = np.repeat(last, zc - fill, axis=0)
            padded = np.concatenate([buf[:fill], repeat], axis=0)
        elif self.flush_pad == FlushPad.ZEROS:
            pad = np.zeros((zc - fill, buf.shape[1], buf.shape[2]), dtype=np.uint16)
            padded = np.concatenate([buf[:fill], pad], axis=0)
        else:  # DROP
            # simply discard and roll back z_counts to the start of the partial chunk
            self.z_counts[level] = self.buf_start[level]
            self.buffers[level] = None
            self.buf_fill[level] = 0
            return

        self._submit_write_chunk(level, self.buf_start[level], padded)
        self.buffers[level] = None
        self.buf_fill[level] = 0
        self.buf_start[level] += zc

    def _ingest_raw(self, img0: np.ndarray):
        with self.lock:
            # Level 0: write into active chunk
            z0 = self._reserve_z(0)
            self._append_to_active_buffer(0, z0, img0)

            # Build and cascade upper levels (true 3D, factor 2^L)
            if self.levels > 1:
                self._emit_next(level=1, candidate_xy=ds2_mean_uint16(img0))



    def _emit_next(self, level: int, candidate_xy: np.ndarray):
        if level >= self.levels:
            return

        if level <= self.xy_levels:
            # XY-only stage: append every incoming slice (no Z pairing)
            zL = self._reserve_z(level)
            self._append_to_active_buffer(level, zL, candidate_xy)
            # continue XY decimation upward
            self._emit_next(level + 1, ds2_mean_uint16(candidate_xy))
            return

        # 3D stage: pair consecutive planes along Z
        if not hasattr(self, "_pair_buf"):
            self._pair_buf = [None] * self.levels

        buf = self._pair_buf[level]
        if buf is None:
            self._pair_buf[level] = candidate_xy
            return

        out_3d = dsZ2_mean_uint16(buf, candidate_xy)
        self._pair_buf[level] = None

        zL = self._reserve_z(level)
        self._append_to_active_buffer(level, zL, out_3d)

        # propagate upward with further XY decimation
        self._emit_next(level + 1, ds2_mean_uint16(out_3d))


class XmlWriter:
    def __init__(self, filename, nsetups=1, nilluminations=1, nchannels=1, ntiles=1, nangles=1, ntimes=1):
        self.filename = filename
        self.nsetups = nsetups
        self.group_names = []
        self.nilluminations = nilluminations
        self.nchannels = nchannels
        self.ntiles = ntiles
        self.nangles = nangles
        self.ntimes = ntimes
        self.__version__ = "1.0.0" 
        self.affine_matrices = {}
        self.affine_names = {}
        self.calibrations = {}
        self.voxel_size_xyz = {}
        self.voxel_units = {}
        self.exposure_time = {}
        self.exposure_units = {}
        self.attribute_labels = {}
        self.attribute_counts = {'illumination': self.nilluminations, 'channel': self.nchannels,
                                 'angle': self.nangles, 'tile': self.ntiles}
        self.angle = {}
        self.channel = {}
        self.illumination = {}
        self.tile = {}
        self.stack_shape_zyx = {}


    def append_acquisition(self, iacq, group_name=None, time=0, illumination=0, channel=0, tile=0, angle=0,
                m_affine=None, name_affine='manually defined',
                voxel_size_xyz=(1, 1, 1), voxel_units='px', calibration=(1, 1, 1),
                exposure_time=0, exposure_units='s', stack_shape_zyx=(1,1,1)):
        """
        Append acquisition to XML file structure for BigSticher compatibility
                Parameters:
        -----------
            iacq: int
                Index of the acquisition, >= 0.
            group_name: str
                Name of the folder group for this acquisition. str | None
            nsetups: int
                Total number of setups.
            time: int
            illumination: int
            channel: int
            tile: int
            angle: int
                Indices of the view attributes, >= 0.
            m_affine: a numpy array of shape (3,4), optional.
                Coefficients of affine transformation matrix (m00, m01, ...). The last column is translation in (x,y,z).
            name_affine: str, optional
                Name of the affine transformation.
            voxel_size_xyz: tuple of size 3, optional
                The physical size of voxel, in voxel_units. Default (1, 1, 1).
            voxel_units: str, optional
                Spatial units, default is 'px'.    
            calibration: tuple of size 3, optional
                The anisotropy factors for (x,y,z) voxel calibration. Default (1, 1, 1).
                Leave it default unless you know how it affects transformations.    
            exposure_time: float, optional
                Camera exposure time for this view, default 0.
            exposure_units: str, optional
                Time units for this view, default "s".
            stack_shape_zyx: tuple of size 3, optional
                Shape of the acquired stack in (z,y,x). Default (1,1,1)
        """
        if m_affine is not None:
            self.affine_matrices[iacq] = m_affine.copy()
            self.affine_names[iacq] = name_affine
        self.group_names.append(group_name)
        self.calibrations[iacq] = calibration
        self.voxel_size_xyz[iacq] = voxel_size_xyz
        self.voxel_units[iacq] = voxel_units
        self.exposure_time[iacq] = exposure_time
        self.exposure_units[iacq] = exposure_units
        self.angle[iacq] = angle
        self.channel[iacq] = channel
        self.illumination[iacq] = illumination
        self.tile[iacq] = tile
        self.stack_shape_zyx[iacq] = stack_shape_zyx

    def set_attribute_labels(self, attribute: str, labels: tuple) -> None:
        """
        Set the view attribute labels that will be visible in BDV/BigStitcher, e.g. `'channel': ('488', '561')`.

        Example: `writer.set_attribute_labels('channel', ('488', '561'))`.

        Parameters:
        -----------
            attribute: str
                One of the view attributes: 'illumination', 'channel', 'angle', 'tile'.

            labels: array-like
                Tuple of labels, e.g. for illumination, ('left', 'right'); for channel, ('488', '561').
        """

        assert attribute in self.attribute_counts.keys(), f'Attribute must be one of {self.attribute_counts.keys()}'
        assert len(labels) == self.attribute_counts[attribute], f'Length of labels {len(labels)} must ' \
                                                   f'match the number of attributes {self.attribute_counts[attribute]}'
        self.attribute_labels[attribute] = labels

    def write(self, camera_name="default",  microscope_name="default",
                       microscope_version="0.0", user_name="user"):
        """
        Write XML header file for the OME-Zarr data file to enable BigStitcher compatibility.

        Parameters:
        -----------
            camera_name: str, optional
                Name of the camera (same for all setups at the moment)
            microscope_name: str, optional
            microscope_version: str, optional
            user_name: str, optional
        """
        assert self.ntimes >= 1, "Total number of time points must be at least 1."
        root = ET.Element('SpimData')
        root.set('version', '0.2')
        bp = ET.SubElement(root, 'BasePath')
        bp.set('type', 'relative')
        bp.text = '.'
        # new XML data, added by @nvladimus
        generator = ET.SubElement(root, 'generatedBy')
        library = ET.SubElement(generator, 'library')
        library.set('version', self.__version__)
        library.text = "XmlWriter for OME-Zarr by nvladimus"
        microscope = ET.SubElement(generator, 'microscope')
        ET.SubElement(microscope, 'name').text = microscope_name
        ET.SubElement(microscope, 'version').text = microscope_version
        ET.SubElement(microscope, 'user').text = user_name
        # end of new XML data

        seqdesc = ET.SubElement(root, 'SequenceDescription')
        imgload = ET.SubElement(seqdesc, 'ImageLoader')
        imgload.set('format', 'bdv.multimg.zarr')
        imgload.set('version', '3.0')
        data_type = ET.SubElement(imgload, 'zarr')
        zgroups = ET.SubElement(imgload, 'zgroups')
        data_type.set('type', 'relative')
        data_type.text = os.path.basename(self.filename).replace('.xml', '')
        # write ViewSetups
        viewsets = ET.SubElement(seqdesc, 'ViewSetups')
        for isetup in range(self.nsetups): 
            zgroup = ET.SubElement(zgroups, 'zgroup')
            zgroup.set('setup', str(isetup))
            zgroup.set('tp', '0')
            zgroup.set('path', self.group_names[isetup])
            view = ET.SubElement(viewsets, 'view')
            # zgroup.set('path', f's{isetup}-t0.zarr')
            zgroup.set('indicies', '0 0') # stupid typo instead of 'indices' in BigStitcher :)
            vs = ET.SubElement(viewsets, 'ViewSetup')
            ET.SubElement(vs, 'id').text = str(isetup)
            ET.SubElement(vs, 'name').text = 'setup ' + str(isetup)
            nz, ny, nx = tuple(self.stack_shape_zyx[isetup])
            ET.SubElement(vs, 'size').text = '{} {} {}'.format(nx, ny, nz)
            vox = ET.SubElement(vs, 'voxelSize')
            ET.SubElement(vox, 'unit').text = self.voxel_units[isetup]
            dx, dy, dz = self.voxel_size_xyz[isetup]
            ET.SubElement(vox, 'size').text = '{} {} {}'.format(dx, dy, dz)
            # new XML data, added by @nvladimus
            cam = ET.SubElement(vs, 'camera')
            ET.SubElement(cam, 'name').text = camera_name
            ET.SubElement(cam, 'exposureTime').text = '{}'.format(self.exposure_time[isetup])
            ET.SubElement(cam, 'exposureUnits').text = self.exposure_units[isetup]
            # end of new XML data
            a = ET.SubElement(vs, 'attributes')
            ET.SubElement(a, 'illumination').text = str(self.illumination[isetup])
            ET.SubElement(a, 'channel').text = str(self.channel[isetup])
            ET.SubElement(a, 'tile').text = str(self.tile[isetup])
            ET.SubElement(a, 'angle').text = str(self.angle[isetup])

        # write Attributes
        for attribute in self.attribute_counts.keys():
            attrs = ET.SubElement(viewsets, 'Attributes')
            attrs.set('name', attribute)
            for i_attr in range(self.attribute_counts[attribute]):
                att = ET.SubElement(attrs, attribute.capitalize())
                ET.SubElement(att, 'id').text = str(i_attr)
                if attribute in self.attribute_labels.keys() and i_attr < len(self.attribute_labels[attribute]):
                    name = str(self.attribute_labels[attribute][i_attr])
                else:
                    name = str(i_attr)
                ET.SubElement(att, 'name').text = name

        # Time points
        tpoints = ET.SubElement(seqdesc, 'Timepoints')
        tpoints.set('type', 'range')
        ET.SubElement(tpoints, 'first').text = str(0)
        ET.SubElement(tpoints, 'last').text = str(self.ntimes - 1)

        # Transformations of coordinate system
        vregs = ET.SubElement(root, 'ViewRegistrations')
        for itime in range(self.ntimes):
            for isetup in range(self.nsetups):
                vreg = ET.SubElement(vregs, 'ViewRegistration')
                vreg.set('timepoint', str(itime))
                vreg.set('setup', str(isetup))
                # write arbitrary affine transformation, specific for each view
                if isetup in self.affine_matrices.keys():
                    vt = ET.SubElement(vreg, 'ViewTransform')
                    vt.set('type', 'affine')
                    ET.SubElement(vt, 'Name').text = self.affine_names[isetup]
                    mx_string = np.array2string(self.affine_matrices[isetup].flatten(), formatter={'float':lambda x: "%.6f" % x})
                    ET.SubElement(vt, 'affine').text = mx_string[1:-1].strip()

                # write registration transformation (calibration)
                vt = ET.SubElement(vreg, 'ViewTransform')
                vt.set('type', 'affine')
                ET.SubElement(vt, 'Name').text = 'calibration'
                calx, caly, calz = self.calibrations[isetup]
                ET.SubElement(vt, 'affine').text = \
                    '{} 0.0 0.0 0.0 0.0 {} 0.0 0.0 0.0 0.0 {} 0.0'.format(calx, caly, calz)

        self._xml_indent(root)
        tree = ET.ElementTree(root)
        tree.write(self.filename, xml_declaration=True, encoding='utf-8', method="xml")

    def _xml_indent(self, elem, level=0):
        """Pretty printing function"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self._xml_indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

import multiprocessing as mp
from multiprocessing import shared_memory

def lower_priority() -> None:
    p = psutil.Process(os.getpid())

    if os.name == "nt":
        # Windows: pick a lower priority class
        # Make ome-zarr processing a lower priority yielding cpu cycles to the acquisition loop
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        # psutil.BELOW_NORMAL_PRIORITY_CLASS
        # psutil.IDLE_PRIORITY_CLASS
    else:
        # Linux/Unix: higher nice => lower priority (0 is default)
        p.nice(10)  # 10-19 are common "background" values
    return


def omezarr_writer_worker(
    shm_name: str,
    frame_shape: tuple[int, int],
    ring_size: int,
    writer_kwargs: dict,
    work_q: mp.Queue,
    free_q: mp.Queue,
    write_cache: Path | None,
):
    """
    Child process:
    - Attaches to shared memory
    - Lowers its own cpu priority to yield to acquisition loop
    - Handles saving to write_cache directory and copying data to acquisition destination
    - Creates Live3DPyramidWriter
    - Loops reading slot indices from work_q
    - For each slot, takes the frame from shared memory and pushes it
    - Returns slot to free_q when done
    """

    import numpy as np
    import shutil
    import uuid
    from datetime import datetime

    lower_priority()

    def get_name_write_cache_dir(acq_path) -> Path | None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_char = str(uuid.uuid4()).split('-')[-1]
        return f'{timestamp}_{acq_path.name}.{random_char}'

    # Attach to shared memory
    shm = shared_memory.SharedMemory(name=shm_name)
    Y, X = frame_shape
    ring = np.ndarray((ring_size, Y, X), dtype=np.uint16, buffer=shm.buf)

    if write_cache:
        acq_path = Path(writer_kwargs['path'])
        tmp_location = Path(write_cache) / get_name_write_cache_dir(acq_path)
        writer_kwargs['path'] = tmp_location
        print(f'Acquiring to temp location: {tmp_location}')


    writer = Live3DPyramidWriter(**writer_kwargs)

    try:
        while True:
            slot = work_q.get()
            if slot is None:
                break

            frame = ring[slot]          # view into shared memory
            writer.push_slice(frame)

            # Slot now reusable
            free_q.put(slot)
    finally:
        try:
            writer.close()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Error closing Live3DPyramidWriter in worker")

    if write_cache:
        print(f'Moving {tmp_location} --> {acq_path}')

        acq_path.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        total_loops = 0

        while total_loops < max_retries:
            retry = 0

            for item in tmp_location.iterdir():
                destination_item_path = acq_path / item.name
                try:
                    shutil.move(str(item), str(destination_item_path))
                    print(f"Moved: {item.name}")
                except Exception as e:
                    retry += 1
                    print(f"Failed to move {item.name}: {e}")

            if retry == 0:
                print(f'All files moved successfully from {tmp_location} to {acq_path}')
                remaining = list(tmp_location.iterdir())
                if remaining:
                    print(f"Not removing {tmp_location}, still contains {len(remaining)} items")
                else:
                    tmp_location.rmdir()
                break

            total_loops += 1
            print(f'Retry {total_loops}/{max_retries}: {retry} files failed')

        else:
            print(f'Some files were not copied from {tmp_location} to {acq_path}')

        print(f'Closing writer for {acq_path.name}')
        shm.close()