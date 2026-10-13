"""The stack the microscope is acquiring right now, shown from memory.

What is on disk during a stack is not a picture yet. The writers save a slab
of planes at a time, and the small copies of the image -- the ones a view of
the whole specimen is drawn from -- only after several slabs, or when the stack
closes. A viewer that reads the disk therefore shows a tile, zoomed out, about
when the tile is finished.

So the tile being acquired is not read from disk at all. mesoSPIM-control
already hands the newest camera frame to its camera window; the same frame is
thinned out here into a small stack held in memory (:class:`PreviewStack`), and
the page reads that as one more source: a little zarr store whose planes exist
the moment the camera delivered them. It costs the acquisition one thinned-out
copy of a frame and no disk reads, and it works whatever format the run is
saved in.

When the stack is complete on disk the page is given the real data in its
place (``watch.py`` does the hand-over).

Nothing here knows about Qt or about mesoSPIM-control's classes:
``mesoSPIM_DataViewer.py`` turns the microscope's signals into
:class:`Stack` descriptions and frames.
"""

from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .omezarr import Channel, robust_window

# A preview is at most this many voxels across and this many planes deep: a
# stack of any size then costs at most 512 * 512 * 256 * 2 bytes, 128 MB, and
# typically a quarter of that.
MAX_ACROSS = 512
MAX_PLANES = 256


def thinning(frame_shape: tuple[int, int], max_across: int = MAX_ACROSS) -> int:
    """Every how many pixels of a frame the preview keeps one."""
    return max(1, math.ceil(max(frame_shape) / max_across))


def thin(frame, max_across: int = MAX_ACROSS):
    """A frame thinned out for the preview, as a copy of its own.

    Done the moment a frame is handed over, so the camera may reuse the frame's
    memory straight after.
    """
    import numpy as np

    step = thinning(frame.shape, max_across)
    return np.ascontiguousarray(frame[::step, ::step])


@dataclass(frozen=True)
class Stack:
    """What the microscope says about the stack it is about to acquire.

    Lengths are micrometres, in the order z, y, x, as the stack is written:
    ``frame`` is the (y, x) shape of a frame as it goes to the writer.
    """

    acquisition: str  # the run's name, as the panel lists it
    channel: str  # "488"
    channels: tuple[str, ...]  # every channel of the run, in the order they are saved
    planes: int
    frame: tuple[int, int]
    voxel_um: tuple[float, float, float]
    origin_um: tuple[float, float, float]
    time_point: int = 0
    tile: str = ""  # "Tile 3", for the panel
    tiles: int = 0  # how many tiles the run has, when known
    colour: str | None = None
    # Where the run and this stack are saved, when that is OME-Zarr the viewer reads:
    # the acquisition's folder, and the store the stack lands in.
    folder: Path | None = None
    store: Path | None = None

    @property
    def channel_index(self) -> int:
        return self.channels.index(self.channel) if self.channel in self.channels else 0


class PreviewStack:
    """A thinned-out copy of a stack, filled plane by plane, read as a zarr store.

    Every ``step`` -th pixel across and every ``every`` -th plane is kept. The
    store is zarr v2, uncompressed, shaped ``(t, c, z, y, x)`` like the tiles
    the microscope saves: one time point, as many channels as the run has (so
    the same channel layer reads this stack's channel at the same index as it
    reads it from the tile on disk), and one chunk file per plane, which exists
    once the plane has arrived.
    """

    def __init__(self, stack: Stack, *, max_across: int = MAX_ACROSS, max_planes: int = MAX_PLANES) -> None:
        import numpy as np

        self.stack = stack
        height, width = stack.frame
        self.step = thinning((height, width), max_across)
        self.every = max(1, math.ceil(stack.planes / max_planes))
        self.shape = (
            max(1, math.ceil(stack.planes / self.every)),
            math.ceil(height / self.step),
            math.ceil(width / self.step),
        )
        self.data = np.zeros(self.shape, dtype="<u2")
        self.top = -1  # the highest plane of the preview that has arrived
        self.plane = -1  # the stack's own plane that arrived last
        self.window: tuple[float, float] | None = None
        self._lock = threading.Lock()
        self._metadata = self._describe()

    # -- filling ---------------------------------------------------------------

    def add(self, index: int, frame) -> list[str]:
        """Take the stack's plane ``index``; return the chunk files that now exist.

        Frames may skip planes -- the microscope passes on every other one, or
        fewer when it is busy -- so a plane of the preview that no frame fell on
        is filled with the next one that arrives: the preview never has a hole.
        """
        import numpy as np

        if index < 0 or self.data.size == 0:
            return []
        at = min(index // self.every, self.shape[0] - 1)
        thinned = np.asarray(frame)
        if thinned.shape != self.shape[1:]:  # a whole frame; thinned out already otherwise
            thinned = thinned[:: self.step, :: self.step]
        if thinned.shape != self.shape[1:]:
            return []
        with self._lock:
            self.plane = max(self.plane, index)
            if at <= self.top:
                # A plane of the preview stands for several of the stack's. The
                # first frame that falls on it stays: a plane that is on screen
                # is not written again under the viewer's eyes.
                return []
            first = self.top + 1
            self.data[first : at + 1] = thinned
            self.top = at
            if self.window is None:
                self.window = robust_window(thinned)
        return [self.chunk_file(z) for z in range(first, at + 1)]

    def finish(self) -> list[str]:
        """The stack is acquired: fill the last planes, if the last frames were passed
        over, with the newest one, and return the chunk files that now exist.

        Only a short tail is filled. A stack that was stopped half way stays as
        far as it got."""
        with self._lock:
            last = self.shape[0] - 1
            missing = last - self.top
            if self.top < 0 or missing <= 0 or missing > max(2, self.shape[0] // 10):
                return []
            first = self.top + 1
            self.data[first:] = self.data[self.top]
            self.top = last
        return [self.chunk_file(z) for z in range(first, last + 1)]

    def chunk_file(self, z: int) -> str:
        return f"0/0/{self.stack.channel_index}/{z}/0/0"

    @property
    def bytes(self) -> int:
        return int(self.data.nbytes)

    @property
    def newest_um(self) -> float | None:
        """The depth of the preview's plane that arrived last, or None before the first.

        The middle of that plane of the preview, which may stand for several of
        the stack's: a view placed there draws this plane and no later one."""
        if self.top < 0:
            return None
        return self.stack.origin_um[0] + self.top * self.every * self.stack.voxel_um[0]

    # -- being read by the page ------------------------------------------------

    def read(self, path: str) -> bytes | None:
        """The file ``path`` of the store, or None where there is none (yet)."""
        described = self._metadata.get(path)
        if described is not None:
            return described
        parts = path.split("/")
        if len(parts) != 6 or parts[0] != "0" or not all(part.isdigit() for part in parts):
            return None
        _, t, c, z, y, x = (int(part) for part in parts)
        if (t, y, x) != (0, 0, 0) or c != self.stack.channel_index:
            return None
        with self._lock:
            if z > self.top:
                return None
            return self.data[z].tobytes()

    def _describe(self) -> dict[str, bytes]:
        stack = self.stack
        planes, height, width = self.shape
        channels = max(1, len(stack.channels))
        dz, dy, dx = stack.voxel_um
        z0, y0, x0 = stack.origin_um
        axes = [
            {"name": "t", "type": "time"},
            {"name": "c", "type": "channel"},
            {"name": "z", "type": "space", "unit": "micrometer"},
            {"name": "y", "type": "space", "unit": "micrometer"},
            {"name": "x", "type": "space", "unit": "micrometer"},
        ]
        transformations = [
            {"type": "scale", "scale": [1.0, 1.0, dz * self.every, dy * self.step, dx * self.step]},
            {"type": "translation", "translation": [float(stack.time_point), 0.0, z0, y0, x0]},
        ]
        attributes = {
            "multiscales": [
                {
                    "version": "0.4",
                    "name": "preview",
                    "axes": axes,
                    "datasets": [{"path": "0", "coordinateTransformations": transformations}],
                }
            ]
        }
        array = {
            "zarr_format": 2,
            "shape": [1, channels, planes, height, width],
            "chunks": [1, 1, 1, height, width],
            "dtype": "<u2",
            "compressor": None,
            "filters": None,
            "fill_value": 0,
            "order": "C",
            "dimension_separator": "/",
        }
        return {
            ".zgroup": json.dumps({"zarr_format": 2}).encode(),
            ".zattrs": json.dumps(attributes).encode(),
            "0/.zarray": json.dumps(array).encode(),
        }

    def channel(self) -> Channel:
        return Channel(label=self.stack.channel, color=self.stack.colour, window=self.window)


@dataclass
class Held:
    """A stack that is shown from its preview, and what is kept back of its tile on disk."""

    preview: PreviewStack
    name: str  # the preview's name on the viewer
    layer: str
    began: float
    ended: float | None = None  # when the microscope finished acquiring it
    store: Path | None = None  # the tile on disk it is written into, once known
    stack: tuple[int, int] | None = None  # its (time point, channel) inside that store
    files: list[str] = field(default_factory=list)  # landed, and kept back from the page
    released: bool = False  # the page has been given the stack from disk
