#!/h20/home/lab/miniconda3/envs/mesospim_dev/bin/python -i

import os, concurrent.futures
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

### Multiscale writer ###

VERBOSE = True

# at top-level (after imports)
try:
    import blosc2            # zarr v3 uses python-blosc2
    blosc2.set_nthreads(max(1, os.cpu_count() // 2))  # e.g., half your cores
except Exception:
    pass

STORE_PATH = "volume.ome.zarr"

# ---------- Helpers ----------
def ceil_div(a, b):  # integer ceil
    return -(-a // b)

def ds2_mean_uint16(img: np.ndarray) -> np.ndarray:
    y, x = img.shape
    y2 = y - (y & 1); x2 = x - (x & 1)
    a = img[:y2:2, :x2:2].astype(np.uint32)
    b = img[1:y2:2, :x2:2].astype(np.uint32)
    c = img[:y2:2, 1:x2:2].astype(np.uint32)
    d = img[1:y2:2, 1:x2:2].astype(np.uint32)
    out = (a + b + c + d + 2) >> 2              # +2 for rounding
    # pad edge by replication if odd dims:
    if y & 1: out = np.vstack([out, out[-1:]])
    if x & 1: out = np.hstack([out, out[:, -1:]])
    return out.astype(np.uint16)

def dsZ2_mean_uint16(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Mean of two uint16 slices -> uint16."""
    return ((a.astype(np.uint32) + b.astype(np.uint32) + 1) >> 1).astype(np.uint16)

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
                  xy_levels: int = 0,
                  shard_shape: Tuple[int,int,int] | None = None):
    root = zarr.open_group(path, mode="a")
    arrs = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        z_l = ceil_div(spec.z_size_estimate, zf)
        y_l = ceil_div(spec.y, yf)
        x_l = ceil_div(spec.x, xf)
        lvl_shape = (z_l, y_l, x_l)

        chunks = chunk_scheme.chunks_for_level(l, lvl_shape)
        shards_l = pick_shards_for_level(shard_shape, chunks, lvl_shape)

        name = f"s{l}"
        if name in root:
            a = root[name]
            if a.shape != lvl_shape or a.dtype != np.uint16:
                raise ValueError(f"Existing {name}: {a.shape}/{a.dtype} != {lvl_shape}/uint16")
            if a.shape[0] < z_l:
                a.resize((z_l, y_l, x_l))
            if a.attrs.get("dimension_names") != ["z", "y", "x"]:
                a.attrs["dimension_names"] = ["z", "y", "x"]
        else:
            kwargs = dict(name=name, shape=lvl_shape, chunks=chunks, dtype="uint16")
            if compressor is not None:
                # v3: list of codecs
                kwargs["compressors"] = [compressor]
            if shards_l is not None:
                # v3: inner shard (must divide chunks)
                kwargs["shards"] = shards_l
            if VERBOSE:
                print(f"[init] creating {name}: shape={lvl_shape} chunks={chunks} shards={shards_l}")
            a = root.create_array(**kwargs)
            a.attrs["dimension_names"] = ["z", "y", "x"]

        arrs.append(a)

    # multiscales with per-axis physical scales
    dz, dy, dx = voxel_size
    datasets = []
    for l in range(spec.levels):
        zf, yf, xf = level_factors(l, xy_levels)
        s = [dz * zf, dy * yf, dx * xf]
        datasets.append({
            "path": f"s{l}",
            "coordinateTransformations": [{"type": "scale", "scale": s}],
        })

    axes = [
        {"name": "z", "type": "space", "unit": unit},
        {"name": "y", "type": "space", "unit": unit},
        {"name": "x", "type": "space", "unit": unit},
    ]
    root.attrs["ome"] = {
        "version": "0.5",
        "multiscales": [{
            "axes": axes,
            "datasets": datasets,
            "name": "image",
            "type": "image",
        }],
    }
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
                 shard_shape: Tuple[int, int, int] | None = None):

        self.spec = spec
        self.chunk_scheme = chunk_scheme
        self.flush_pad = flush_pad
        self.xy_levels = compute_xy_only_levels(voxel_size)
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
        self.async_close = async_close
        self.finalize_future = None

        self.root, self.arrs = init_ome_zarr(
            spec, path, chunk_scheme=chunk_scheme, compressor=compressor,
            voxel_size=voxel_size, xy_levels=self.xy_levels,
            shard_shape=shard_shape,
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
        if self.async_close:
            self.close_async()    # Background finalize
        else:
            self.close()          # synchronous finalize
        return False

    def close(self):
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
        # exactly what your current close() does, but moved here
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
        # bound in-flight tasks; acquire before submitting
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
            self._submit_write_chunk(level, z0, buf)
            self.buffers[level] = None
            self.buf_fill[level] = 0
            self.buf_start[level] = z0 + zc

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






if __name__ == '__main__':
    import time


    file = '/CBI_FastStore/test_data/mesospim/04CL02_Zhao_Kidney_4x_561_ONLY_2_2_5/kidney_4_Tile6_Ch561_Sh0.btf'
    voxel = (5.0, 2.0, 2.0) # microns (z,y,x)
    file = "/CBI_FastStore/test_data/mesospim/120424/two_color_brain_8x_Tile14_Ch561_Sh0.btf"
    voxel = (2.0, 1.0, 1.0) # microns (z,y,x)

    image = mesospim_btf_helper(file)
    image = image[:]
    print(f'Shape of Image = {image.shape}')

    Z_EST, Y, X  = image.shape

    xy_levels = compute_xy_only_levels(voxel)
    levels = plan_levels(Y, X, Z_EST, xy_levels, min_dim=64)

    spec = PyramidSpec(
        z_size_estimate=Z_EST,  # big upper bound; we'll truncate at the end
        y=Y, x=X, levels=levels,
        #xy_downsample_only=False  # set True if anisotropic Z (fastest)
    )

    # shard_shape = (128, 1024*4, 1024*4)
    shard_shape = None

    scheme = ChunkScheme(base=(256, 256, 256), target=(256, 256, 256))

    with Live3DPyramidWriter(
        spec,
        voxel_size=voxel,
        path="/CBI_FastStore/tmp/volume17.ome.zarr",
        max_workers=os.cpu_count() // 2,
        chunk_scheme=scheme,
        # compressor=None,  # keep off for max ingest speed
        compressor=BloscCodec(cname="zstd", clevel=5, shuffle=BloscShuffle.bitshuffle),
        # compressor=BloscCodec(cname="lz4", clevel=1, shuffle=BloscShuffle.bitshuffle),
        shard_shape=shard_shape,
        flush_pad=FlushPad.DUPLICATE_LAST,  # keeps alignment, no RMW
        async_close = False,
    ) as writer:

        start = time.time()
        for k in range(image.shape[0]):  # your camera loop
            frame = image[k]  # returns np.ndarray (Y,X) uint16
            writer.push_slice(frame)
            frames_per_sec = round(k / (time.time() - start), 2)
            print(f'Frame per sec: {frames_per_sec}')
    fut = writer.finalize_future

























