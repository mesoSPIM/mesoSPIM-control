'''
Define a stable Writer API
This API is used as a minimal template for building all image writers
'''

from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable, Tuple
from dataclasses import dataclass

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
    uri: str                             # file path or store URL
    shape: Tuple[int, ...]               # e.g. (C, Z, Y, X) or (Z, Y, X)
    dtype: str
    axes: str                            # e.g. "CZYX", "ZXY", "TCZYX"
    chunks: Optional[Tuple[int, ...]] = None
    compression: Optional[str] = None
    metadata: Dict[str, Any] = None      # imaging + acquisition metadata

@runtime_checkable
class Writer(Protocol):
    """A streaming-friendly writer interface."""
    @classmethod
    def api_version(cls) -> str: ...

    @classmethod
    def name(cls) -> str: ...

    @classmethod
    def capabilities(cls) -> WriterCapabilities: ...

    def open(self, req: WriteRequest) -> None:
        """Allocate outputs/stores; may create multiscales, groups, labels, etc."""

    def write_frame(self, index: Tuple[slice, ...], data: memoryview | Any) -> None:
        """
        Write a block into 'index' (same rank as req.shape).
        - 'data' should support the buffer protocol; accept numpy/dask chunks.
        - Called repeatedly, possibly from multiple threads.
        """

    def finalize(self) -> None:
        """Flush/close handles. Safe to call multiple times."""

    def abort(self) -> None:
        """Best-effort cleanup on failure."""
