"""A small neuroglancer view for the mesoSPIM control software.

Stdlib-only Python that serves a handful of OME-Zarr stores to a native
neuroglancer page, places them by transform, mixes each store's channels in one
layer, and reports the camera back. See README.md beside this file.
"""

from .omezarr import Axis, Channel, NotAStore, NotSupported, Store, read_store
from .state import LAYOUTS, Layer, Placement, channel_shader, source_json, state_json
from .viewer import PAGE_DIR, Viewer
from .watch import Acquisition, Acquisitions, Follower, Opened, Watcher

__all__ = [
    "Axis",
    "Channel",
    "LAYOUTS",
    "Layer",
    "NotAStore",
    "NotSupported",
    "PAGE_DIR",
    "Placement",
    "Store",
    "Viewer",
    "Watcher",
    "Follower",
    "Opened",
    "Acquisition",
    "Acquisitions",
    "channel_shader",
    "read_store",
    "source_json",
    "state_json",
]
