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
    # Minimal, format-agnostic metadata needed by all writers
    uri: Path                            # file path or store URL
    shape: Tuple[int, ...]               # e.g. (T, C, Z, Y, X), (C, Z, Y, X), (Z, Y, X), (Y, X)
    dtype: str
    axes: str                            # e.g. "CZYX", "ZXY", "TCZYX"
    x_res: Optional[int] = 1
    y_res: Optional[int] = 1
    z_res: Optional[int] = 1
    unit: Optional[str] = 'microns'
    chunks: Optional[Tuple[int, ...]] = None
    compression: Optional[str] = None
    multiscales: Optional[int] = None
    overwrite: Optional[bool] = None
    metadata: Dict[str, Any] = None      # imaging + acquisition metadata

@runtime_checkable
class Writer(Protocol):
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
        supported by the Writer. Example: ['.ome.zarr', '.zarr']
        """

    def compatible_suffix(self, req: WriteRequest) -> str:
        return ''.join(req.uri.suffixes) in file_extensions()

    def open(self, req: WriteRequest) -> None:
        """
        Allocate outputs/stores; may create multiscales, groups, labels, etc.
        Equivalent to prepare method in mesoSPIM_ImageWriter
        Establish self.writer
        """

    def write_frame(self, index: Tuple[slice, ...], data: memoryview | Any) -> None:
        """
        Write a block into 'index' (same rank as req.shape).
        - 'data' should support the buffer protocol; accept numpy/dask chunks.
        - Called repeatedly, possibly from multiple threads.
        """

    def finalize(self) -> None:
        """
        Flush/close handles. Safe to call multiple times.
        Close self.writer and set =None
        """

    def abort(self) -> None:
        """
        Best-effort cleanup on failure.
        Close self.writer and set =None
        """
