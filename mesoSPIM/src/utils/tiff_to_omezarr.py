#!/usr/bin/env python3
"""
TIFF -> OME-Zarr converter (command line and options window).

Converts one or more TIFF stacks (e.g. the tiles and channels of a mesoSPIM acquisition)
into one OME-Zarr container, with one multiscale image per stack and channel, plus a
BigStitcher XML. It uses the same pyramid writer as the MP_OME_Zarr_Writer plugin, so the
output has the same layout as a live acquisition:

    out.ome.zarr/<stack name>.ome.zarr/{0,1,2,...}   one pyramid per stack (and channel)
    out.ome.zarr.xml                                  BigStitcher project

VOXEL SIZE
----------
The original voxel size of every TIFF is kept. It is read, in this order, from:
  1. the TIFF itself: OME-XML PhysicalSizeX/Y/Z, or the ImageJ/TIFF resolution tags
     (XResolution/YResolution) plus the ImageJ 'spacing' (z step);
  2. the mesoSPIM '<file>_meta.txt' next to the TIFF ('Pixelsize in um', 'z_stepsize');
  3. --voxel-size (command line) or the table cell (window), for files that have none.
A file whose voxel size is still unknown is not converted. In the window the voxel size
cells can be edited, which overrides the value found in the file.

TILES AND CHANNELS
------------------
Tile, channel, illumination and angle of each stack come from the mesoSPIM metadata file
(position, laser, shutter, rotation) when there is one, otherwise from the file name
(Tile3, Ch488 / 488nm, Sh0 / Left / Right, Rot0). A TIFF with a channel axis (e.g. an
ImageJ ZCYX hyperstack, or a ScanImage stack with several saved channels) becomes one
image per channel.

OTHER TIFFS
-----------
Any TIFF readable by tifffile works, not only mesoSPIM ones: ImageJ hyperstacks, OME-TIFF,
ScanImage (z step from SI.hStackManager, XY from the resolution tags or the imaging FOV).
The writer stores uint16: uint8 is widened; signed data (ScanImage int16) is clipped at 0
by default (--signed-integers shift adds 32768 instead); float data are refused. Planes are pushed to the writer
exactly as they are stored in the TIFF, so the stored orientation is not changed.

Z CROP
------
z_start / z_end keep planes z_start .. z_end-1 of every stack (0-based, z_end exclusive, like
Python slicing; z_end beyond a stack is clamped). The z translation of the image and of the
BigStitcher tile is shifted by z_start * z step, so cropped stacks stay in place.

USAGE
-----
    python tiff_to_omezarr.py                         # options window
    python tiff_to_omezarr.py a.tif b.tif --gui       # window with the files listed
    python tiff_to_omezarr.py *.tif -o D:/data/sample.ome.zarr
    python tiff_to_omezarr.py *.tif -o out.ome.zarr --levels 4 --compression-level 3
    python tiff_to_omezarr.py stack.tif --z-start 100 --z-end 400   # planes 100-399 only

Defaults: OME-Zarr 0.5 (Zarr v3) with sharding, 5 pyramid levels, zstd level 5, shards
(64, 6000, 6000), chunks (64, auto, auto) -> (64, 64, 64), where 'auto' is the exact divisor of the
plane size closest to 512 (5056 -> 632, 2960 -> 592, 512 -> 512). Shards and target chunks as in
config_benchtop-cDAQ-ASI_user-shardedZARR-12FPS-continuos.py.

www.mesoSPIM.org, GPL-3 License.
"""
import argparse
import dataclasses
import itertools
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import tifffile

# The pyramid writer lives in the plugin support package; make 'mesoSPIM' importable
# when this file is run as a script from any folder.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP import omezarr_writer as ozw  # noqa: E402

ozw.VERBOSE = False

# ---------------------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------------------
DEFAULT_OPTIONS = {
    'ome_version': '0.5',            # '0.5' = Zarr v3 + sharding, '0.4' = Zarr v2, no sharding
    'levels': 5,                     # pyramid levels including full resolution
    'compression': 'zstd',           # 'zstd', 'lz4' or None
    'compression_level': 5,          # 1-9
    'shards': (64, 6000, 6000),      # (z, y, x) max shard size, None = no sharding; 0.5 only
    'base_chunks': (64, 'auto', 'auto'),  # (z, y, x) chunks at level 0; 'auto' -> see auto_chunk()
    'target_chunks': (64, 64, 64),   # (z, y, x) chunks at the smallest level
    'write_big_stitcher_xml': True,
    'flip_xyz': (False, False, False),
    'transpose_xy': False,
    'signed_integers': 'clip',       # signed TIFFs: 'clip' negatives to 0, 'shift' by +32768, 'error'
    'z_start': 0,                    # crop: first plane written (0-based)
    'z_end': None,                   # crop: plane after the last one written (exclusive), None = to the end
    'overwrite': False,
}

COMPRESSIONS = ['zstd', 'lz4', None]
AUTO_CHUNK_TARGET = 512


def auto_chunk(n: int, target: int = AUTO_CHUNK_TARGET) -> int:
    """Chunk size for an axis of n pixels: n / k for the integer k that divides n exactly and
    gives the size closest to target (5056 -> 632, 2960 -> 592, 2048 -> 512). The chunks then
    tile the plane with no partial edge chunk. If no exact divisor lies within target/2 to
    2*target (e.g. a prime n), the plane is split into round(n / target) nearly equal parts."""
    n = int(n)
    if n <= target:
        return max(1, n)
    best = min((n // k for k in range(1, n + 1) if n % k == 0),
               key=lambda c: (abs(c - target), -c))
    if target / 2 <= best <= 2 * target:
        return best
    k = max(1, round(n / target))
    return -(-n // k)


def resolve_chunks(chunks, shape_zyx) -> tuple:
    """Replace 'auto' entries (y, x) by auto_chunk() of that axis."""
    return tuple(auto_chunk(n) if str(c).lower() == 'auto' else int(c) for c, n in zip(chunks, shape_zyx))


def _chunk_ok(v, allow_auto):
    if allow_auto and str(v).lower() == 'auto':
        return True
    try:
        return int(v) >= 1
    except (TypeError, ValueError):
        return False
OME_VERSIONS = ['0.5', '0.4']


def check_options(opts: dict) -> list:
    """Return a list of problems with the options (empty when they are usable)."""
    problems = []
    if opts['ome_version'] not in OME_VERSIONS:
        problems.append(f"ome_version must be one of {OME_VERSIONS}")
    if opts['signed_integers'] not in SIGNED_MODES:
        problems.append(f"signed_integers must be one of {SIGNED_MODES}")
    try:
        z0 = int(opts.get('z_start') or 0)
        z1 = None if opts.get('z_end') in (None, '') else int(opts['z_end'])
        if z0 < 0 or (z1 is not None and z1 <= z0):
            problems.append('z range: need 0 <= z_start < z_end')
    except (TypeError, ValueError):
        problems.append('z_start / z_end must be integers')
    if not 1 <= int(opts['levels']) <= 12:
        problems.append("levels must be 1-12")
    if opts['compression'] not in COMPRESSIONS:
        problems.append(f"compression must be one of {COMPRESSIONS}")
    if opts['compression'] and not 1 <= int(opts['compression_level']) <= 9:
        problems.append("compression_level must be 1-9")
    for key in ('base_chunks', 'target_chunks') + (('shards',) if opts['shards'] else ()):
        v = opts[key]
        if len(v) != 3 or not all(_chunk_ok(n, key == 'base_chunks' and i > 0) for i, n in enumerate(v)):
            problems.append(f"{key} must be three positive integers (z, y, x)"
                            + (" ('auto' allowed for y and x)" if key == 'base_chunks' else ''))
    if opts['ome_version'] == '0.5' and opts['shards'] and not problems:
        if int(opts['shards'][0]) != int(opts['base_chunks'][0]):
            problems.append("shards z must equal base_chunks z (shards are written one z-chunk deep)")
    return problems


# ---------------------------------------------------------------------------------------
# Reading TIFFs
# ---------------------------------------------------------------------------------------
_UNIT_TO_UM = {'um': 1.0, 'µm': 1.0, '\\u00B5m': 1.0, 'micron': 1.0, 'microns': 1.0, 'micrometer': 1.0,
               'nm': 1e-3, 'nanometer': 1e-3, 'mm': 1e3, 'millimeter': 1e3, 'cm': 1e4, 'm': 1e6,
               'meter': 1e6, 'inch': 25400.0}


def _unit_factor(unit) -> Optional[float]:
    if unit is None:
        return 1.0  # OME default unit is micrometre
    return _UNIT_TO_UM.get(str(unit).strip().lower().replace('μ', 'µ'))


def _rational(value) -> Optional[float]:
    try:
        num, den = value
        return num / den if den else None
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def read_tiff_voxel_size(tif: tifffile.TiffFile):
    """(z, y, x) voxel size in um from the TIFF's own metadata, each None if absent, + source."""
    # OME-XML
    if tif.is_ome and tif.ome_metadata:
        try:
            root = ET.fromstring(tif.ome_metadata)
            pixels = next(e for e in root.iter() if e.tag.endswith('Pixels'))
            sizes = []
            for ax in ('Z', 'Y', 'X'):
                v = pixels.get(f'PhysicalSize{ax}')
                f = _unit_factor(pixels.get(f'PhysicalSize{ax}Unit'))
                sizes.append(float(v) * f if v is not None and f else None)
            if sizes[1] or sizes[2]:
                return tuple(sizes), 'TIFF OME-XML'
        except (StopIteration, ET.ParseError, ValueError):
            pass

    page = tif.pages[0]
    tags = page.tags
    xres = _rational(tags['XResolution'].value) if 'XResolution' in tags else None
    yres = _rational(tags['YResolution'].value) if 'YResolution' in tags else None
    ij = tif.imagej_metadata or {}
    res_unit = int(tags['ResolutionUnit'].value) if 'ResolutionUnit' in tags else 2

    factor = None
    source = None
    if ij and ij.get('unit') not in (None, '', 'pixel', 'pixels'):
        factor = _unit_factor(ij['unit'])
        source = 'TIFF ImageJ'
    elif res_unit == 3:      # centimetre
        factor, source = 1e4, 'TIFF resolution'
    elif res_unit == 2 and xres not in (None, 1.0, 72.0):  # inch; 1 and 72 dpi are placeholders
        factor, source = 25400.0, 'TIFF resolution'

    y = x = z = None
    if factor and xres:
        # TIFF rationals are 32-bit: 1/0.85 px/um reads back as 0.8500000001 um. 7 significant
        # digits is below their precision and gives back the value that was written.
        x = float(f'{factor / xres:.7g}')
        y = float(f'{factor / yres:.7g}') if yres else x
        if ij.get('spacing'):
            z = float(ij['spacing']) * factor

    # ScanImage: z step (and the XY pixel size from the FOV, if the tags had none)
    si = scanimage_frame_data(tif)
    if si:
        if z is None:
            step = si.get('SI.hStackManager.actualStackZStepSize') or si.get('SI.hStackManager.stackZStepSize')
            try:
                z = abs(float(step)) or None
            except (TypeError, ValueError):
                pass
        if x is None:
            try:
                fov = np.asarray(si['SI.hRoiManager.imagingFovUm'], dtype=float)
                x = (fov[:, 0].max() - fov[:, 0].min()) / float(si['SI.hRoiManager.pixelsPerLine'])
                y = (fov[:, 1].max() - fov[:, 1].min()) / float(si['SI.hRoiManager.linesPerFrame'])
            except (KeyError, TypeError, ValueError, IndexError):
                x = y = None
        if z is not None or x is not None:
            source = (source + ' + ScanImage') if source else 'ScanImage'
    if x is not None or z is not None:
        return (z, y, x), source
    return (None, None, None), None


def scanimage_frame_data(tif: tifffile.TiffFile) -> dict:
    try:
        return (tif.scanimage_metadata or {}).get('FrameData') or {}
    except Exception:
        return {}


def tiff_layout(tif: tifffile.TiffFile):
    """(shape, axes) of the first series. ScanImage stacks store their saved channels
    interleaved along one page axis; that axis is split into (Z, C) here."""
    series = tif.series[0]
    shape, axes = tuple(series.shape), series.axes
    si = scanimage_frame_data(tif)
    saved = si.get('SI.hChannels.channelSave')
    nch = len(saved) if isinstance(saved, (list, tuple)) else 1
    if nch > 1 and 'C' not in axes and len(axes) == 3 and shape[0] % nch == 0:
        shape, axes = (shape[0] // nch, nch) + shape[1:], 'ZC' + axes[1:]
    return shape, axes


def read_mesospim_metadata(tiff_path) -> dict:
    """Parse the mesoSPIM '<file>_meta.txt' next to a TIFF ('[key] value' lines), {} if none."""
    candidates = [str(tiff_path) + '_meta.txt', str(Path(tiff_path).with_suffix('')) + '_meta.txt']
    for meta in candidates:
        if os.path.isfile(meta):
            out = {}
            with open(meta, 'r', errors='replace') as f:
                for line in f:
                    m = re.match(r'\s*\[([^\]]+)\]\s*(.*?)\s*$', line)
                    if m and m.group(2) != '' and m.group(1) not in out:
                        out[m.group(1)] = m.group(2)
            return out
    return {}


def _meta_float(meta, *keys):
    for k in keys:
        try:
            return float(meta[k])
        except (KeyError, ValueError):
            pass
    return None


class _PageVolume:
    """Plane access through TIFF pages, for files that cannot be memory-mapped (compressed)."""

    def __init__(self, path, series_shape):
        self._tif = tifffile.TiffFile(path)
        self._pages = self._tif.series[0].pages
        self.shape = series_shape

    def page(self, i):
        return self._pages[i].asarray()

    def close(self):
        self._tif.close()


@dataclass
class Source:
    """One image to write: a TIFF file, or one channel of a multichannel TIFF."""
    path: str
    channel_in_file: Optional[int] = None   # index along the file's C/S axis, None if no such axis
    n_channels_in_file: int = 1
    shape_zyx: tuple = (0, 0, 0)
    dtype: str = ''
    axes: str = ''
    voxel_zyx: list = field(default_factory=lambda: [None, None, None])
    voxel_source: str = ''
    meta: dict = field(default_factory=dict)
    tile: int = 0
    channel: int = 0
    illumination: int = 0
    angle: int = 0
    channel_label: str = ''
    translation_zyx_um: tuple = (0.0, 0.0, 0.0)
    has_position: bool = False
    name: str = ''
    labels: tuple = ('Left', '0')     # (illumination, angle) labels for BigStitcher
    z_offset: int = 0                 # first plane of the file that is written (z crop)

    @property
    def voxel_known(self):
        return all(v is not None and v > 0 for v in self.voxel_zyx)


def _split_axes(axes: str, shape: tuple):
    """Return (channel axis or None, list of leading axes collapsed into Z)."""
    yx = [i for i, a in enumerate(axes) if a in 'YX']
    if len(yx) != 2:
        raise ValueError(f"cannot find the Y and X axes in TIFF axes '{axes}'")
    ch = None
    for a in ('C', 'S'):
        if a in axes and shape[axes.index(a)] > 1:
            ch = axes.index(a)
            break
    lead = [i for i in range(len(axes)) if i not in yx and i != ch]
    return ch, lead


def inspect_tiff(path) -> list:
    """Describe a TIFF file as one Source per channel, without reading the pixels."""
    path = str(path)
    with tifffile.TiffFile(path) as tif:
        shape, axes = tiff_layout(tif)
        dtype = tif.series[0].dtype
        (vz, vy, vx), vsource = read_tiff_voxel_size(tif)
    ch_axis, lead = _split_axes(axes, shape)
    yx = [i for i, a in enumerate(axes) if a in 'YX']
    nz = int(np.prod([shape[i] for i in lead])) if lead else 1
    ny, nx = shape[yx[0]], shape[yx[1]]
    nch = shape[ch_axis] if ch_axis is not None else 1

    meta = read_mesospim_metadata(path)
    meta_xy = _meta_float(meta, 'Pixelsize in um')
    meta_z = _meta_float(meta, 'z_stepsize')
    sources_used = [vsource] if vsource else []
    if vy is None and vx is None and meta_xy:
        vy = vx = meta_xy
        sources_used.append('mesoSPIM meta.txt')
    if vz is None and meta_z:
        vz = abs(meta_z)
        if 'mesoSPIM meta.txt' not in sources_used:
            sources_used.append('mesoSPIM meta.txt (z)')
    if vz is None and nz == 1 and vx:
        vz = vx  # a single plane has no z step; any value keeps the pyramid XY-only
    voxel_source = ' + '.join(sources_used)
    # drop float noise such as ScanImage's 0.3000000000000682
    vz, vy, vx = (float(f'{v:.10g}') if v else None for v in (vz, vy, vx))

    out = []
    for c in range(nch):
        out.append(Source(
            path=path,
            channel_in_file=c if ch_axis is not None else None,
            n_channels_in_file=nch,
            shape_zyx=(nz, ny, nx),
            dtype=str(dtype),
            axes=axes,
            voxel_zyx=[vz, vy, vx],
            voxel_source=voxel_source,
            meta=meta,
        ))
    return out


def assign_views(sources: list) -> None:
    """Set tile / channel / illumination / angle indices, labels, positions and names."""
    tile_keys, ch_keys, ill_keys, ang_keys = {}, {}, {}, {}

    def index(table, key):
        return table.setdefault(key, len(table))

    for s in sources:
        meta, stem = s.meta, Path(s.path).name
        stem = re.sub(r'\.ome$', '', re.sub(r'\.tiff?$', '', stem, flags=re.I), flags=re.I)

        # position (um) -> tile
        x, y = _meta_float(meta, 'x_pos'), _meta_float(meta, 'y_pos')
        z = _meta_float(meta, 'z_start', 'z_pos')
        if x is not None and y is not None:
            s.translation_zyx_um = (z or 0.0, y, x)
            s.has_position = True
            tile_key = ('pos', round(x, 3), round(y, 3))
        else:
            m = re.search(r'tile[_-]?(\d+)', stem, re.I)
            tile_key = ('name', int(m.group(1))) if m else ('file', s.path)

        # channel
        if s.channel_in_file is not None:
            label = f'C{s.channel_in_file}'
            ch_key = ('file-ch', s.channel_in_file)
        elif meta.get('Laser'):
            label = meta['Laser'].replace(' ', '')
            ch_key = ('laser', label)
        else:
            m = re.search(r'(?:ch[_-]?(\d+))|(\d{3})\s*nm', stem, re.I)
            label = (m.group(1) or m.group(2)) if m else '0'
            ch_key = ('name', label)

        # illumination
        shutter = meta.get('Shutter')
        if shutter is None:
            m = re.search(r'(?:sh[_-]?(\d))|(left|right)', stem, re.I)
            shutter = (m.group(1) or m.group(2).capitalize()) if m else 'Left'
        # angle
        rot = meta.get('rot')
        if rot is None:
            m = re.search(r'rot[_-]?(-?\d+)', stem, re.I)
            rot = m.group(1) if m else '0'

        s.tile = index(tile_keys, tile_key)
        s.channel = index(ch_keys, ch_key)
        s.channel_label = label
        s.illumination = index(ill_keys, str(shutter))
        s.angle = index(ang_keys, str(rot))
        s.labels = (str(shutter), str(rot))
        suffix = f'_C{s.channel_in_file}' if s.channel_in_file is not None else ''
        s.name = f'{stem}{suffix}.ome.zarr'

    _dedupe_names(sources)


def _dedupe_names(sources):
    seen = {}
    for s in sources:
        n = seen.get(s.name, 0)
        seen[s.name] = n + 1
        if n:
            s.name = s.name.replace('.ome.zarr', f'_{n}.ome.zarr')


# Windows MAX_PATH is 260 characters. Python opts in to long paths, but many viewers do not
# (AGAVE 1.9 reports NOT_FOUND for '<group>/zarr.json' beyond it), so every file of the output
# must stay below this, counting the deepest one: '<out>/<group>/<level>/c/<z>/<y>/<x>'.
MAX_PATH_SAFE = 240
_CHUNK_PATH_RESERVE = len('/0/c/0000/0000/0000') + 1


def short_view_name(s: Source) -> str:
    name = f'Tile{s.tile}_Ch{re.sub(r"[^A-Za-z0-9]+", "", s.channel_label) or s.channel}'
    if s.illumination:
        name += f'_Ill{s.illumination}'
    if s.angle:
        name += f'_Ang{s.angle}'
    return name + '.ome.zarr'


def fit_names_to_path_limit(sources, out_path, log=print) -> None:
    """Shorten group names that would put a file of the output over MAX_PATH_SAFE characters."""
    longest = len(out_path) + 1 + max(len(s.name) for s in sources) + _CHUNK_PATH_RESERVE
    if longest <= MAX_PATH_SAFE:
        return
    for s in sources:
        s.name = short_view_name(s)
    _dedupe_names(sources)
    log(f'Output paths would exceed {MAX_PATH_SAFE} characters (Windows limit for many viewers): '
        f'using short image names ({", ".join(s.name for s in sources[:4])}{", ..." if len(sources) > 4 else ""}). '
        f'The source file of each is listed in the container zarr.json.')
    longest = len(out_path) + 1 + max(len(s.name) for s in sources) + _CHUNK_PATH_RESERVE
    if longest > MAX_PATH_SAFE:
        log(f'WARNING: the output folder path itself is too long ({len(out_path)} characters); '
            f'some viewers will not open it. Choose a shorter output path.')


class PlaneReader:
    """Yields the (y, x) planes of a Source as uint16, in file order."""

    def __init__(self, src: Source):
        self.src = src
        with tifffile.TiffFile(src.path) as tif:
            self.shape, self.axes = tiff_layout(tif)
            npages = len(tif.series[0].pages)
        self.ch_axis, self.lead = _split_axes(self.axes, self.shape)
        self._pages = None
        self._arr = None
        try:
            self._arr = tifffile.memmap(src.path, mode='r')
            if tuple(self._arr.shape) != self.shape:
                self._arr = self._arr.reshape(self.shape)
        except Exception:
            self._arr = None
            lead_shape = [self.shape[i] for i in range(len(self.shape))
                          if self.axes[i] not in 'YXS']
            if npages == int(np.prod(lead_shape) if lead_shape else 1):
                self._pages = _PageVolume(src.path, self.shape)
            else:  # unusual layout, read it whole
                with tifffile.TiffFile(src.path) as tif:
                    self._arr = tif.series[0].asarray().reshape(self.shape)

    def _plane(self, lead_index):
        idx = [slice(None)] * len(self.shape)
        for ax, i in zip(self.lead, lead_index):
            idx[ax] = i
        if self.ch_axis is not None:
            idx[self.ch_axis] = self.src.channel_in_file
        if self._arr is not None:
            return np.asarray(self._arr[tuple(idx)])
        # page access: a page holds Y, X (and S for RGB)
        page_axes = [i for i in range(len(self.axes)) if self.axes[i] not in 'YXS']
        page_shape = [self.shape[i] for i in page_axes]
        full = {ax: i for ax, i in zip(self.lead, lead_index)}
        if self.ch_axis is not None:
            full[self.ch_axis] = self.src.channel_in_file
        page_i = int(np.ravel_multi_index([full[a] for a in page_axes], page_shape)) if page_axes else 0
        plane = self._pages.page(page_i)
        if 'S' in self.axes and plane.ndim == 3:
            plane = plane[..., self.src.channel_in_file or 0]
        return plane

    def __iter__(self):
        lead_shape = [self.shape[i] for i in self.lead]
        self.n_clipped = 0
        indices = np.ndindex(*lead_shape) if lead_shape else iter([()])
        z0 = self.src.z_offset
        for lead_index in itertools.islice(indices, z0, z0 + self.src.shape_zyx[0]):
            plane, clipped = to_uint16(self._plane(lead_index), self.signed)
            self.n_clipped += clipped
            yield plane

    signed = 'clip'

    def close(self):
        if self._pages is not None:
            self._pages.close()
        self._arr = None


SIGNED_MODES = ['clip', 'shift', 'error']


def to_uint16(plane: np.ndarray, signed: str = 'clip'):
    """Return (uint16 plane, number of clipped values).

    uint16 is passed as is, uint8/bool are widened. Signed integers (e.g. ScanImage int16
    after offset subtraction) depend on `signed`: 'clip' sets negative values to 0,
    'shift' adds 32768 (int16 only, lossless), 'error' refuses negative values. Values
    above 65535 (int32/uint32) always raise.
    """
    dt = plane.dtype
    if dt == np.uint16:
        return np.ascontiguousarray(plane), 0
    if dt == np.bool_ or dt.kind == 'u' and dt.itemsize < 2:
        return plane.astype(np.uint16), 0
    if dt.kind not in 'iu':
        raise ValueError(f"{dt} TIFFs are not supported (the OME-Zarr writer stores uint16)")
    if dt.kind == 'i' and signed == 'shift':
        if dt.itemsize > 2:
            raise ValueError(f"'shift' works for int8/int16 only, not {dt}")
        return (plane.astype(np.int32) + 32768).astype(np.uint16), 0
    if plane.size and plane.max() > 65535:
        raise ValueError(f"{dt} values above 65535 cannot be stored as uint16")
    clipped = 0
    if dt.kind == 'i':
        neg = plane < 0
        clipped = int(np.count_nonzero(neg))
        if clipped and signed == 'error':
            raise ValueError(f"{clipped} negative values in a {dt} plane (choose 'clip' or 'shift')")
        if clipped:
            plane = np.where(neg, 0, plane)
    return plane.astype(np.uint16), clipped


def check_dtype(dtype: str) -> Optional[str]:
    dt = np.dtype(dtype)
    if dt == np.uint16 or dt == np.bool_ or dt.kind == 'u' and dt.itemsize < 2:
        return None
    if dt.kind == 'i':
        return f'{dt}: negative values are clipped to 0 or shifted (see signed-integer option)'
    if dt.kind == 'u':
        return f'{dt} (converted to uint16 if the values fit)'
    return f'{dt} is not supported: the writer stores uint16'


# ---------------------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------------------
def pyramid_levels(src: Source, requested: int):
    """Levels actually written: the requested number, capped so the smallest level stays >= 16 px."""
    z, y, x = src.shape_zyx
    xy_levels = ozw.compute_xy_only_levels(tuple(src.voxel_zyx))
    possible = ozw.plan_levels(y, x, z, xy_levels, min_dim=16)
    return max(1, min(int(requested), possible)), xy_levels


def _compressor(opts):
    if not opts['compression']:
        return None
    return ozw.BloscCodec(cname=opts['compression'], clevel=int(opts['compression_level']),
                          shuffle=ozw.BloscShuffle.bitshuffle)


def crop_sources(sources, z_start=0, z_end=None, log=print) -> list:
    """Copies of the sources limited to planes z_start .. z_end-1 (0-based, z_end exclusive,
    None = to the end, clamped to each stack). The z translation moves by z_start * z step,
    so a cropped stack keeps its physical position."""
    z_start = int(z_start or 0)
    if z_start == 0 and z_end is None:
        return list(sources)
    out = []
    for s in sources:
        nz = s.shape_zyx[0]
        z1 = nz if z_end is None else min(int(z_end), nz)
        if z_start >= z1:
            raise ValueError(f'{Path(s.path).name}: z range {z_start}-{z_end} is outside its {nz} planes')
        tz, ty, tx = s.translation_zyx_um
        dz = float(s.voxel_zyx[0])
        out.append(dataclasses.replace(s, z_offset=z_start, shape_zyx=(z1 - z_start,) + tuple(s.shape_zyx[1:]),
                                       translation_zyx_um=(tz + z_start * dz, ty, tx)))
        log(f'{Path(s.path).name}: cropped to planes {z_start}-{z1 - 1} of 0-{nz - 1} ({z1 - z_start} planes)')
    return out


class Cancelled(Exception):
    pass


def convert(sources: list, out_path, opts: dict,
            progress: Optional[Callable[[int, int, str], None]] = None,
            log: Callable[[str], None] = print,
            cancel: Optional[Callable[[], bool]] = None) -> str:
    """Write the sources into one OME-Zarr container (+ BigStitcher XML). Returns the path.

    progress(done_planes, total_planes, message); cancel() -> True stops after the current plane.
    """
    import zarr

    opts = {**DEFAULT_OPTIONS, **opts}
    problems = check_options(opts)
    if problems:
        raise ValueError('; '.join(problems))
    unknown = [Path(s.path).name for s in sources if not s.voxel_known]
    if unknown:
        raise ValueError('voxel size unknown for: ' + ', '.join(unknown))
    bad = [f'{Path(s.path).name}: {check_dtype(s.dtype)}' for s in sources
           if check_dtype(s.dtype) and 'not supported' in check_dtype(s.dtype)]
    if bad:
        raise ValueError('; '.join(bad))

    sources = crop_sources(sources, opts['z_start'], opts['z_end'], log)
    out_path = str(out_path).rstrip('/\\')
    if not out_path.lower().endswith('.zarr'):
        out_path += '.ome.zarr'
    xml_path = out_path + '.xml'
    if os.path.exists(out_path):
        if not opts['overwrite']:
            raise FileExistsError(f'{out_path} exists (use overwrite)')
        log(f'Removing existing {out_path}')
        shutil.rmtree(out_path)

    ome_version = opts['ome_version']
    zarr_version = 2 if ome_version == '0.4' else 3
    shards = tuple(int(v) for v in opts['shards']) if (opts['shards'] and zarr_version == 3) else None
    target_chunks = tuple(int(v) for v in opts['target_chunks'])
    compressor = _compressor(opts)
    fit_names_to_path_limit(sources, out_path, log)
    container = zarr.open_group(out_path, mode='a', zarr_version=zarr_version)
    container.attrs['tiff_to_omezarr'] = {
        'images': {s.name: {'source': s.path, 'channel_in_file': s.channel_in_file,
                            'voxel_size_zyx_um': [float(v) for v in s.voxel_zyx],
                            'voxel_size_from': s.voxel_source or 'entered',
                            'z_planes_of_source': [s.z_offset, s.z_offset + s.shape_zyx[0]]} for s in sources}}

    total = sum(s.shape_zyx[0] for s in sources)
    done = 0
    t_start = time.perf_counter()

    for i, src in enumerate(sources):
        z, y, x = src.shape_zyx
        levels, xy_levels = pyramid_levels(src, opts['levels'])
        voxel = tuple(float(v) for v in src.voxel_zyx)
        base = resolve_chunks(opts['base_chunks'], src.shape_zyx)
        scheme = ozw.ChunkScheme(base=base, target=target_chunks)
        if levels < int(opts['levels']):
            log(f'{Path(src.path).name}: {levels} pyramid levels (stack too small for {opts["levels"]})')
        log(f'[{i + 1}/{len(sources)}] {Path(src.path).name}'
            + (f' channel {src.channel_in_file}' if src.channel_in_file is not None else '')
            + f' -> {src.name}: {z}x{y}x{x} (z,y,x), voxel {voxel} um ({src.voxel_source or "entered"}), '
              f'{levels} levels, level-0 chunks {base}')
        writer = ozw.Live3DPyramidWriter(
            ozw.PyramidSpec(z_size_estimate=z, y=y, x=x, levels=levels),
            voxel_size=voxel,
            path=os.path.join(out_path, src.name),
            chunk_scheme=scheme,
            compressor=compressor,
            shard_shape=shards,
            flush_pad=ozw.FlushPad.DUPLICATE_LAST,
            ingest_queue_size=16,
            async_close=False,
            translation=src.translation_zyx_um,
            ome_version=ome_version,
        )
        reader = PlaneReader(src)
        reader.signed = opts['signed_integers']
        t0 = time.perf_counter()
        z_done = 0
        try:
            for plane in reader:
                if plane.shape != (y, x):
                    raise ValueError(f'plane shape {plane.shape} != {(y, x)}')
                writer.push_slice(plane)
                done += 1
                z_done += 1
                if progress:
                    progress(done, total, f'{src.name}: plane {z_done}/{z}')
                if cancel and cancel():
                    raise Cancelled()
        finally:
            reader.close()
            writer.close()
        dt = time.perf_counter() - t0
        log(f'    done in {dt:.1f} s ({z / dt if dt else 0:.1f} planes/s)')
        if reader.n_clipped:
            log(f'    {reader.n_clipped} negative values ({100 * reader.n_clipped / (z * y * x):.3g}%) set to 0')
        if opts['signed_integers'] == 'shift' and np.dtype(src.dtype).kind == 'i':
            log('    values shifted by +32768 (signed -> unsigned)')

    if opts['write_big_stitcher_xml']:
        write_xml(sources, xml_path, opts, zarr_version)
        log(f'BigStitcher XML: {xml_path}')
    log(f'Finished {out_path} in {time.perf_counter() - t_start:.1f} s')
    return out_path


def write_xml(sources, xml_path, opts, zarr_version):
    def count(attr):
        return max(getattr(s, attr) for s in sources) + 1

    xw = ozw.XmlWriter(xml_path, nsetups=len(sources), nilluminations=count('illumination'),
                       nchannels=count('channel'), ntiles=count('tile'), nangles=count('angle'),
                       ntimes=1, zarr_version=zarr_version)
    sign_xyz = (1 - np.array(opts['flip_xyz'], dtype=int)) * 2 - 1
    for i, s in enumerate(sources):
        dz, dy, dx = (float(v) for v in s.voxel_zyx)
        tz, ty, tx = s.translation_zyx_um
        if opts['transpose_xy']:
            t = (sign_xyz[1] * ty / dy, sign_xyz[0] * tx / dx, sign_xyz[2] * tz / dz)
        else:
            t = (sign_xyz[0] * tx / dx, sign_xyz[1] * ty / dy, sign_xyz[2] * tz / dz)
        affine = np.array(((1.0, 0.0, 0.0, t[0]), (0.0, 1.0, 0.0, t[1]), (0.0, 0.0, 1.0, t[2])))
        xw.append_acquisition(iacq=i, group_name=s.name, illumination=s.illumination, channel=s.channel,
                              tile=s.tile, angle=s.angle, voxel_units='um', voxel_size_xyz=(dx, dy, dz),
                              calibration=(1.0, dy / dx, dz / dx), m_affine=affine,
                              name_affine='Translation to Regular Grid', stack_shape_zyx=s.shape_zyx)

    def labels(attr, label_of):
        out = {}
        for s in sources:
            out.setdefault(getattr(s, attr), label_of(s))
        return tuple(out[k] for k in range(len(out)))

    xw.set_attribute_labels('channel', labels('channel', lambda s: s.channel_label))
    xw.set_attribute_labels('illumination', labels('illumination', lambda s: s.labels[0]))
    xw.set_attribute_labels('angle', labels('angle', lambda s: s.labels[1]))
    xw.write()


def collect_sources(paths, fallback_voxel=None, log=print) -> list:
    sources = []
    for p in paths:
        try:
            sources += inspect_tiff(p)
        except Exception as e:
            log(f'Skipping {p}: {e}')
    if fallback_voxel:
        for s in sources:
            s.voxel_zyx = [v if v else f for v, f in zip(s.voxel_zyx, fallback_voxel)]
            if not s.voxel_source:
                s.voxel_source = '--voxel-size'
    assign_views(sources)
    return sources


# ---------------------------------------------------------------------------------------
# Options window
# ---------------------------------------------------------------------------------------
def run_gui(paths=(), out_path=None, start_dir=None):
    from PyQt5 import QtCore, QtGui, QtWidgets

    def tuple_text(v):
        return ', '.join(str(n) for n in v) if v else 'None'

    def parse_tuple(text, allow_none=False, allow_auto=False):
        text = text.strip()
        if allow_none and text.lower() in ('', 'none'):
            return None
        parts = [p for p in re.split(r'[,\s;x]+', text.strip('()[] ')) if p]
        if len(parts) != 3:
            raise ValueError(f"'{text}' is not three integers (z, y, x)")
        try:
            return tuple(p.lower() if allow_auto and i > 0 and p.lower() == 'auto' else int(p)
                         for i, p in enumerate(parts))
        except ValueError:
            raise ValueError(f"'{text}' is not three integers (z, y, x)"
                             + (" or 'auto' for y and x" if allow_auto else ''))

    class Worker(QtCore.QThread):
        sig_progress = QtCore.pyqtSignal(int, int, str)
        sig_log = QtCore.pyqtSignal(str)
        sig_done = QtCore.pyqtSignal(bool, str)

        def __init__(self, sources, out, opts):
            super().__init__()
            self.sources, self.out, self.opts = sources, out, opts
            self.cancel_requested = False

        def run(self):
            try:
                path = convert(self.sources, self.out, self.opts,
                               progress=self.sig_progress.emit, log=self.sig_log.emit,
                               cancel=lambda: self.cancel_requested)
                self.sig_done.emit(True, path)
            except Cancelled:
                self.sig_done.emit(False, 'Cancelled: the output is incomplete.')
            except Exception as e:
                self.sig_done.emit(False, f'Error: {e}')

    FONT_SIZE = 12  # pt, whole window

    COLS = ['File', 'Ch in file', 'Shape (z, y, x)', 'dtype', 'Voxel z (um)', 'Voxel y (um)',
            'Voxel x (um)', 'Voxel size from', 'Tile', 'Channel', 'Illum.', 'Angle', 'Output name']
    VOX = (4, 5, 6)

    class Window(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('TIFF to OME-Zarr')
            font = self.font()
            font.setPointSize(FONT_SIZE)
            self.setFont(font)  # inherited by every child widget
            avail = QtWidgets.QApplication.desktop().availableGeometry(self)
            self.resize(min(1400, avail.width()), min(1050, avail.height() - 40))
            self.sources = []
            self.worker = None
            self.last_dir = start_dir or os.getcwd()
            lay = QtWidgets.QVBoxLayout(self)

            # files
            box = QtWidgets.QGroupBox('Input TIFF stacks (one per tile / channel; voxel sizes can be edited)')
            bl = QtWidgets.QVBoxLayout(box)
            self.table = QtWidgets.QTableWidget(0, len(COLS))
            self.table.setHorizontalHeaderLabels(COLS)
            self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            # room for ~5 rows: at 12 pt the layout otherwise squeezes the table to one row
            self.table.setMinimumHeight(6 * self.table.verticalHeader().defaultSectionSize())
            self.table.itemChanged.connect(self._cell_edited)
            bl.addWidget(self.table)
            row = QtWidgets.QHBoxLayout()
            for text, slot in (('Add TIFF files...', self.add_files), ('Remove selected', self.remove_selected),
                               ('Clear', self.clear)):
                b = QtWidgets.QPushButton(text)
                b.clicked.connect(slot)
                row.addWidget(b)
            row.addStretch()
            bl.addLayout(row)
            lay.addWidget(box, stretch=3)

            # options
            obox = QtWidgets.QGroupBox('OME-Zarr options')
            form = QtWidgets.QFormLayout(obox)
            d = DEFAULT_OPTIONS
            self.out_edit = QtWidgets.QLineEdit(out_path or '')
            ob = QtWidgets.QPushButton('Browse...')
            ob.clicked.connect(self.browse_out)
            orow = QtWidgets.QHBoxLayout()
            orow.addWidget(self.out_edit)
            orow.addWidget(ob)
            form.addRow('Output (.ome.zarr)', orow)
            self.version = QtWidgets.QComboBox()
            self.version.addItems(['0.5 (Zarr v3, sharding)', '0.4 (Zarr v2, no sharding)'])
            self.version.currentIndexChanged.connect(self._version_changed)
            form.addRow('OME-Zarr version', self.version)
            self.levels = QtWidgets.QSpinBox()
            self.levels.setRange(1, 12)
            self.levels.setValue(d['levels'])
            self.levels.setToolTip('Including full resolution; capped for small stacks')
            form.addRow('Pyramid levels', self.levels)
            self.compression = QtWidgets.QComboBox()
            self.compression.addItems(['zstd', 'lz4', 'none'])
            self.compression.currentIndexChanged.connect(
                lambda: self.clevel.setEnabled(self.compression.currentText() != 'none'))
            form.addRow('Compression (Blosc)', self.compression)
            self.clevel = QtWidgets.QSpinBox()
            self.clevel.setRange(1, 9)
            self.clevel.setValue(d['compression_level'])
            form.addRow('Compression level', self.clevel)
            self.shards = QtWidgets.QLineEdit(tuple_text(d['shards']))
            self.shards.setToolTip('Max shard size (z, y, x), or None. z must equal the base chunk z.')
            form.addRow('Shards (z, y, x)', self.shards)
            self.base = QtWidgets.QLineEdit(tuple_text(d['base_chunks']))
            self.base.setToolTip(f"'auto' (y, x): the exact divisor of the plane size closest to "
                                 f"{AUTO_CHUNK_TARGET}, e.g. 5056 -> 632, 2960 -> 592")
            form.addRow('Chunks at level 0 (z, y, x)', self.base)
            self.target = QtWidgets.QLineEdit(tuple_text(d['target_chunks']))
            form.addRow('Chunks at smallest level (z, y, x)', self.target)
            self.xml = QtWidgets.QCheckBox('Write BigStitcher XML')
            self.xml.setChecked(d['write_big_stitcher_xml'])
            frow = QtWidgets.QHBoxLayout()
            self.flips = [QtWidgets.QCheckBox(f'flip {a}') for a in 'xyz']
            self.transpose = QtWidgets.QCheckBox('transpose x/y')
            for w in [self.xml] + self.flips + [self.transpose]:
                frow.addWidget(w)
            frow.addStretch()
            form.addRow('BigStitcher', frow)
            self.signed = QtWidgets.QComboBox()
            self.signed.addItems(['clip negative values to 0', 'shift by +32768 (lossless)', 'stop on negative values'])
            self.signed.setToolTip('Only for signed-integer TIFFs (e.g. ScanImage int16); the writer stores uint16')
            form.addRow('Signed integer data', self.signed)
            zrow = QtWidgets.QHBoxLayout()
            self.z_start = QtWidgets.QSpinBox()
            self.z_start.setRange(0, 10_000_000)
            self.z_end = QtWidgets.QSpinBox()
            self.z_end.setRange(0, 10_000_000)
            self.z_end.setSpecialValueText('end')  # 0 = to the last plane
            self.z_start.setToolTip('First plane written, 0-based')
            self.z_end.setToolTip("Plane after the last one written (exclusive); 'end' = to the last plane")
            zrow.addWidget(QtWidgets.QLabel('z_start'))
            zrow.addWidget(self.z_start)
            zrow.addWidget(QtWidgets.QLabel('z_end'))
            zrow.addWidget(self.z_end)
            zrow.addWidget(QtWidgets.QLabel('(0-based, z_end exclusive: planes z_start .. z_end-1, all stacks)'))
            zrow.addStretch()
            form.addRow('Crop in Z', zrow)
            self.overwrite = QtWidgets.QCheckBox('Overwrite an existing output')
            form.addRow('', self.overwrite)
            lay.addWidget(obox)

            # run
            rrow = QtWidgets.QHBoxLayout()
            self.convert_btn = QtWidgets.QPushButton('Convert')
            self.convert_btn.clicked.connect(self.start)
            self.cancel_btn = QtWidgets.QPushButton('Cancel')
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.clicked.connect(self.cancel)
            self.progress = QtWidgets.QProgressBar()
            rrow.addWidget(self.convert_btn)
            rrow.addWidget(self.cancel_btn)
            rrow.addWidget(self.progress, stretch=1)
            lay.addLayout(rrow)
            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            mono.setPointSize(FONT_SIZE)
            self.log.setFont(mono)
            self.log.setMinimumHeight(4 * self.log.fontMetrics().lineSpacing())
            lay.addWidget(self.log, stretch=1)

            if paths:
                self._add(paths)

        # ----- files -----
        def add_files(self):
            files, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, 'Select TIFF stacks', self.last_dir, 'TIFF (*.tif *.tiff *.TIF *.TIFF);;All files (*)')
            if files:
                self.last_dir = os.path.dirname(files[0])
                self._add(files)

        def _add(self, files):
            have = {s.path for s in self.sources}
            new = []
            for f in files:
                if os.path.abspath(f) in have:
                    continue
                try:
                    new += inspect_tiff(os.path.abspath(f))
                except Exception as e:
                    self.log.appendPlainText(f'Skipping {f}: {e}')
            self.sources += new
            if not self.out_edit.text() and self.sources:
                first = Path(self.sources[0].path)
                self.out_edit.setText(str(first.with_name(re.sub(r'\.(ome\.)?tiff?$', '', first.name, flags=re.I)
                                                        + '.ome.zarr')))
            self._refresh()

        def remove_selected(self):
            rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
            for r in rows:
                del self.sources[r]
            self._refresh()

        def clear(self):
            self.sources = []
            self._refresh()

        def _refresh(self):
            assign_views(self.sources)
            self.table.blockSignals(True)
            self.table.setRowCount(len(self.sources))
            for r, s in enumerate(self.sources):
                vals = [Path(s.path).name,
                        '' if s.channel_in_file is None else f'{s.channel_in_file}/{s.n_channels_in_file}',
                        ' x '.join(map(str, s.shape_zyx)), s.dtype,
                        *['' if v is None else f'{v:.6g}' for v in s.voxel_zyx],
                        s.voxel_source or 'not found - enter it', str(s.tile), s.channel_label,
                        str(s.illumination), str(s.angle), s.name]
                for c, v in enumerate(vals):
                    item = QtWidgets.QTableWidgetItem(v)
                    if c not in VOX:
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    if c == 0:
                        item.setToolTip(s.path)
                    if (c in VOX and s.voxel_zyx[c - 4] is None) or (c == 3 and check_dtype(s.dtype)):
                        item.setBackground(QtGui.QColor(255, 200, 200))
                        if c == 3:
                            item.setToolTip(check_dtype(s.dtype))
                    self.table.setItem(r, c, item)
            self.table.blockSignals(False)

        def _cell_edited(self, item):
            r, c = item.row(), item.column()
            if c not in VOX:
                return
            s = self.sources[r]
            try:
                v = float(item.text())
                if v <= 0:
                    raise ValueError
            except ValueError:
                v = None
            if v != s.voxel_zyx[c - 4]:
                s.voxel_zyx[c - 4] = v
                s.voxel_source = 'entered' if not s.voxel_source else (
                    s.voxel_source if s.voxel_source.endswith('(edited)') else s.voxel_source + ' (edited)')
            self._refresh()

        # ----- options -----
        def _version_changed(self):
            self.shards.setEnabled(self.version.currentIndex() == 0)

        def browse_out(self):
            f, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Output OME-Zarr', self.out_edit.text() or self.last_dir,
                                                         'OME-Zarr (*.ome.zarr)')
            if f:
                if not f.lower().endswith('.zarr'):
                    f += '.ome.zarr'
                self.out_edit.setText(os.path.normpath(f))

        def options(self):
            comp = self.compression.currentText()
            return {
                'ome_version': OME_VERSIONS[self.version.currentIndex()],
                'levels': self.levels.value(),
                'compression': None if comp == 'none' else comp,
                'compression_level': self.clevel.value(),
                'shards': parse_tuple(self.shards.text(), allow_none=True),
                'base_chunks': parse_tuple(self.base.text(), allow_auto=True),
                'target_chunks': parse_tuple(self.target.text()),
                'write_big_stitcher_xml': self.xml.isChecked(),
                'flip_xyz': tuple(cb.isChecked() for cb in self.flips),
                'transpose_xy': self.transpose.isChecked(),
                'signed_integers': SIGNED_MODES[self.signed.currentIndex()],
                'z_start': self.z_start.value(),
                'z_end': self.z_end.value() or None,
                'overwrite': self.overwrite.isChecked(),
            }

        # ----- run -----
        def start(self):
            try:
                opts = self.options()
                problems = check_options(opts)
                if problems:
                    raise ValueError('\n'.join(problems))
                if not self.sources:
                    raise ValueError('Add at least one TIFF file.')
                missing = [Path(s.path).name for s in self.sources if not s.voxel_known]
                if missing:
                    raise ValueError('Enter the voxel size for:\n' + '\n'.join(missing))
                out = self.out_edit.text().strip()
                if not out:
                    raise ValueError('Choose an output path.')
            except ValueError as e:
                QtWidgets.QMessageBox.warning(self, 'TIFF to OME-Zarr', str(e))
                return
            target = out if out.lower().endswith('.zarr') else out + '.ome.zarr'
            if os.path.exists(target) and not opts['overwrite']:
                if QtWidgets.QMessageBox.question(self, 'TIFF to OME-Zarr', f'{target} exists. Overwrite it?') \
                        != QtWidgets.QMessageBox.Yes:
                    return
                opts['overwrite'] = True
            self.convert_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.progress.setValue(0)
            self.worker = Worker(list(self.sources), out, opts)
            self.worker.sig_progress.connect(self._progress)
            self.worker.sig_log.connect(self.log.appendPlainText)
            self.worker.sig_done.connect(self._done)
            self.worker.start()

        def _progress(self, done, total, msg):
            self.progress.setMaximum(total)
            self.progress.setValue(done)
            self.progress.setFormat(f'%p%  {msg}')

        def cancel(self):
            if self.worker:
                self.worker.cancel_requested = True
                self.cancel_btn.setEnabled(False)

        def _done(self, ok, msg):
            self.convert_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.log.appendPlainText(msg if not ok else f'Done: {msg}')
            if not ok:
                QtWidgets.QMessageBox.warning(self, 'TIFF to OME-Zarr', msg)

        def closeEvent(self, ev):
            if self.worker and self.worker.isRunning():
                if QtWidgets.QMessageBox.question(self, 'TIFF to OME-Zarr',
                                                  'A conversion is running. Cancel it and close?') \
                        != QtWidgets.QMessageBox.Yes:
                    ev.ignore()
                    return
                self.worker.cancel_requested = True
                self.worker.wait()
            ev.accept()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    w = Window()
    w.show()
    return app.exec_()


# ---------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------
def _triple(text):
    if text.lower() == 'none':
        return None
    parts = [p for p in re.split(r'[,\s;x]+', text.strip('()[] ')) if p]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"'{text}' is not three values z,y,x")
    return tuple(parts)


def main(argv=None):
    d = DEFAULT_OPTIONS
    ap = argparse.ArgumentParser(description='Convert TIFF stacks (tiles / channels) into one OME-Zarr '
                                             'container with a BigStitcher XML. Without input files, or '
                                             'with --gui, opens the options window.')
    ap.add_argument('inputs', nargs='*', help='TIFF files')
    ap.add_argument('-o', '--output', help='output .ome.zarr (default: next to the first input)')
    ap.add_argument('--gui', action='store_true', help='open the options window')
    ap.add_argument('--start-dir', help='folder the window file dialogs start in')
    ap.add_argument('--ome-version', choices=OME_VERSIONS, default=d['ome_version'])
    ap.add_argument('--levels', type=int, default=d['levels'], help='pyramid levels incl. full resolution')
    ap.add_argument('--compression', choices=['zstd', 'lz4', 'none'], default=d['compression'])
    ap.add_argument('--compression-level', type=int, default=d['compression_level'])
    ap.add_argument('--shards', type=_triple, default=d['shards'], help="z,y,x or 'none' (0.5 only)")
    ap.add_argument('--base-chunks', type=_triple, default=d['base_chunks'],
                    help="z,y,x; y and x may be 'auto' = exact divisor of the plane size closest to 512")
    ap.add_argument('--target-chunks', type=_triple, default=d['target_chunks'], help='z,y,x')
    ap.add_argument('--voxel-size', type=_triple, help='z,y,x um, used only for files without a voxel size')
    ap.add_argument('--no-xml', action='store_true', help='do not write the BigStitcher XML')
    ap.add_argument('--flip-xyz', type=_triple, default=('0', '0', '0'), help='BigStitcher axis flips, e.g. 1,1,0')
    ap.add_argument('--transpose-xy', action='store_true')
    ap.add_argument('--signed-integers', choices=SIGNED_MODES, default=d['signed_integers'],
                    help='signed TIFFs (e.g. ScanImage int16): clip negatives to 0, shift by +32768, or stop')
    ap.add_argument('--z-start', type=int, default=0, help='crop: first plane written (0-based)')
    ap.add_argument('--z-end', type=int, default=None,
                    help='crop: plane after the last one written (exclusive); default: to the end')
    ap.add_argument('--overwrite', action='store_true')
    a = ap.parse_args(argv)

    if a.gui or not a.inputs:
        return run_gui(a.inputs, a.output, a.start_dir)

    opts = {
        'ome_version': a.ome_version,
        'levels': a.levels,
        'compression': None if a.compression == 'none' else a.compression,
        'compression_level': a.compression_level,
        'shards': tuple(int(v) for v in a.shards) if a.shards else None,
        'base_chunks': tuple(str(v).lower() if str(v).lower() == 'auto' else int(v) for v in a.base_chunks),
        'target_chunks': tuple(int(v) for v in a.target_chunks),
        'write_big_stitcher_xml': not a.no_xml,
        'flip_xyz': tuple(str(v).lower() in ('1', 'true', 'yes') for v in a.flip_xyz),
        'transpose_xy': a.transpose_xy,
        'signed_integers': a.signed_integers,
        'z_start': a.z_start,
        'z_end': a.z_end,
        'overwrite': a.overwrite,
    }
    problems = check_options(opts)
    if problems:
        ap.error('; '.join(problems))
    fallback = tuple(float(v) for v in a.voxel_size) if a.voxel_size else None
    sources = collect_sources(a.inputs, fallback)
    if not sources:
        ap.error('no readable TIFF input')
    missing = [Path(s.path).name for s in sources if not s.voxel_known]
    if missing:
        ap.error('voxel size not found in the TIFF or its _meta.txt for: ' + ', '.join(missing)
                 + ' -- pass --voxel-size z,y,x')
    out = a.output or str(Path(sources[0].path).with_name(
        re.sub(r'\.(ome\.)?tiff?$', '', Path(sources[0].path).name, flags=re.I) + '.ome.zarr'))

    def progress(done, total, msg):
        print(f'\r{done}/{total} planes ({100 * done / total:.0f}%)', end='', flush=True)
        if done == total:
            print()

    try:
        convert(sources, out, opts, progress=progress, log=lambda m: print('\n' + m if m.startswith('[') else m))
    except (ValueError, FileExistsError) as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
