'''
Define a stable Writer API
This API is used as a minimal template for building all image writers
'''

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple, List, Union
from dataclasses import dataclass
import numpy as np

API_VERSION = "0.0.1"

'''This is currently not used'''
@dataclass(frozen=True)
class WriterCapabilities:
    # What the writer can handle efficiently
    dtype: Iterable[str]                 # e.g. ["uint16", "float32"]
    ndim: Iterable[int]                  # e.g. [2, 3, 4, 5]
    supports_chunks: bool
    supports_compression: bool
    supports_multiscale: bool
    supports_overwrite: bool
    streaming_safe: bool                 # tile-by-tile streaming without global state

@dataclass
class WriteRequest:
    # Minimal, format-agnostic metadata needed by all writers passed when initializing the writer
    uri: Path                            # file path or store URL
    shape: Tuple[int, ...]               # e.g. (T, C, Z, Y, X), (C, Z, Y, X), (Z, Y, X), (Y, X)
    dtype: str
    axes: str                            # e.g. "CZYX", "ZXY", "TCZYX"
    x_res: Optional[int] = 1
    y_res: Optional[int] = 1
    z_res: Optional[int] = 1
    unit: Optional[str] = 'microns'
    chunks: Optional[Tuple[int, ...]] = None
    compression_method: Optional[str] = None
    compression_level: Optional[int] = None
    multiscales: Optional[int] = None
    overwrite: Optional[bool] = None
    num_tiles: int = None
    num_channels: int = None
    num_rotations: int = None
    num_shutters: int = None
    acq: Dict = None  # imaging + acquisition metadata
    acq_list: List = None
    writer_config_file_values: Optional[Dict[str, Any]] = None

@dataclass
class WriteImage:
    # Minimal, format-agnostic metadata needed by all writers passed when initializing the writer
    image: np.ndarray               # z_frame to write
    current_image_counter: int      # z_frame #
    tile_number: int                # Tile number in acquisition grid
    laser: str                      # Excitation laser
    shutter: str                    # 'left', 'right'
    rot: int                        # Angle of rotation
    x_res: int                      # resolution x in unit
    y_res: int                      # resolution y in unit
    z_res: int                      # resolution z in unit
    unit: str = 'microns'
    acq: Dict = None
    acq_list: List = None

@dataclass
class FinalizeImage:
    acq: Dict
    acq_list: List

@dataclass
class FileNaming:
    # Passed to filename_wizard for guiding selection of file formats in UI
    FormatSelectionOption: str # File naming wizard Selection Box Text for selecting a file format
    WindowTitle: str
    WindowSubTitle: str
    WindowDescription: str # Unique description to register with ui

    # What attributes to include in the file names:
    IncludeMag: bool = True
    IncludeTile: bool = True
    IncludeChannel: bool = True
    IncludeShutter: bool = True
    IncludeRotation: bool = True
    IncludeSuffix: Optional[str] = None
    SingleFileFormat: bool = True  # Will all tiles be written into 1 file (.h5 for example)
    IncludeAllChannelsInSingleFileFormat: bool=True #Will put all channels in name if SingleFileFormat==True

@runtime_checkable
class ImageWriter(Protocol):
    """A streaming-friendly writer interface."""

    writer = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str: ...

    @classmethod
    def capabilities(cls) -> WriterCapabilities: ...

    @classmethod
    def file_extensions(cls) -> Union[None, str, list[str]]:
        """
        Return None, a string or list of strings to specify the file extensions
        supported by the Writer. Example: ['ome.zarr', 'zarr']
        """

    def ensure_path(self, path_like):
        if isinstance(path_like, Path):
            return path_like
        else:
            return Path(path_like)

    def remove_leading_dot(self,path:str) -> str:
        return path[1:] if path.startswith('.') else path

    def compatible_suffix(self, req: WriteRequest) -> str:
        '''Return True if the uri suffix is compatible with this writer'''
        path = self.ensure_path(req.uri)
        suffix = ''.join(path.suffixes)
        suffix = self.remove_leading_dot(suffix)
        return suffix in self.file_extensions()

    def open(self, req: WriteRequest) -> None:
        """
        Allocate outputs/stores; may create multiscales, groups, labels, etc.
        Equivalent to prepare method in mesoSPIM_ImageWriter
        Establish self.writer
        """

    def write_frame(self, data: WriteImage) -> None:
        """
        Write a block into 'index' (same rank as req.shape).
        - 'data' should support the buffer protocol; accept numpy/dask chunks.
        - Called repeatedly, possibly from multiple threads.
        """

    def finalize(self, finalize_image: FinalizeImage) -> None:
        """
        Flush/close handles. Safe to call multiple times.
        Close self.writer and set =None
        """

    def abort(self) -> None:
        """
        Best-effort cleanup on failure.
        Close self.writer and set =None
        """
