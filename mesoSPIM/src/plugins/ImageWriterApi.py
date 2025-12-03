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
        The first entry in the list is used as the default extension in filename_wizard.
        """

    def ensure_path(self, path_like):
        if isinstance(path_like, Path):
            return path_like
        else:
            return Path(path_like)

    def remove_leading_dot(self,path:str) -> str:
        return path[1:] if path.startswith('.') else path

    def compatible_suffix(self, req: WriteRequest) -> bool:
        '''Return True if the uri suffix is compatible with this writer'''
        path = str(req.uri)
        compatible_extensions = ['.' + x if x[0] != '.' else x for x in self.file_extensions()] # Ensure leading '.' on extensions
        return any([path.endswith(ext) for ext in compatible_extensions])

    def open(self, req: WriteRequest) -> None:
        """
        Allocate outputs/stores; may create multiscales, groups, labels, etc.
        Equivalent to prepare method in mesoSPIM_ImageWriter
        Establish self.writer
        """
        self.req = req

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

    @property
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

        # Used in mesoSpim_ImageWriter.write_metadata
        # Used in mesoSpim_Core.append_timing_info_to_metadata
        self.metadata_file = self.req.uri + '_meta.txt'
        # Used in mesoSpim_ImageWriter.write_metadata
        self.metadata_file_describes_this_path = self.req.uri

        # Placeholder prior to adding data processing plugins
        path = Path(self.req.uri)
        self.MIP_path = path.with_name('MAX_' + path.name + '.tif').as_posix()

    def __getattribute__(self, name):
        attr = object.__getattribute__(self, name)
        if name == "open" and callable(attr):
            def wrapped_open(request, **kwargs):
                # Automatically append open(WriteRequest) to self.req for use by other methods and run self.metadata_file_info()
                self.req = request
                try:
                    self.metadata_file_info()
                except Exception:
                    # So that self.metadata_file_info can be overwritten and not error
                    # Overwritten methods will require that self.metadata_file_info() be called in the open method
                    pass
                return attr(request, **kwargs)

            return wrapped_open
        return attr