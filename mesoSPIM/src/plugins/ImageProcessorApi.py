"""
Image Processor Plugin API

Defines a stable interface for building image processing plugins
that intercept and transform camera frames in real-time.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol, runtime_checkable
from dataclasses import dataclass
import numpy as np

API_VERSION = "0.0.1"


@dataclass
class ProcessorCapabilities:
    """Capabilities of an image processor."""
    dtype_in: Iterable[str]              # Input dtypes, e.g. ["uint16", "float32"]
    dtype_out: Iterable[str]             # Output dtypes
    ndim: Iterable[int]                  # Supported dimensions, e.g. [2, 3]
    is_inplace: bool                     # Whether processor modifies in place
    streaming_safe: bool                  # Whether processor works in streaming mode


@runtime_checkable
class ImageProcessor(Protocol):
    """
    A streaming-friendly image processor interface.
    
    Processors intercept camera frames and transform them before
    they are displayed or saved to disk.
    """

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str: ...
    
    @classmethod
    def description(cls) -> str: ...

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities: ...

    @classmethod
    def file_extensions(cls) -> Optional[list[str]]:
        """Return supported file extensions, or None if not file-based."""
        return None

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        """
        Process a single frame and return the processed result.
        
        Args:
            image: Input image array (2D or 3D)
            
        Returns:
            Processed image array of same shape.

            Built-in mesoSPIM processors are expected to return writer-ready
            ``uint16`` data in the normal acquisition pipeline, even if they use
            floating-point math internally.
        """
        raise NotImplementedError

    def process_frame_inplace(self, image: np.ndarray) -> None:
        """
        Process a frame in place (for processors that support it).
        
        Default implementation calls process_frame and assigns result.
        Override this for in-place processing for better performance.
        """
        result = self.process_frame(image)
        image[:] = result

    def configure(self, params: Dict[str, Any]) -> None:
        """
        Configure processor with parameters.
        
        Args:
            params: Dictionary of configuration parameters
        """
        
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration parameters.
        
        Returns:
            Dictionary of current configuration
        """
        return {}

    def reset(self) -> None:
        """Reset processor state (useful for streaming/acquisitions)."""
        pass


@runtime_checkable
class ImageProcessorWithConfig(ImageProcessor, Protocol):
    """Extended protocol for processors with configurable parameters."""
    
    @classmethod
    def parameter_descriptions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Return descriptions of configurable parameters.
        
        Returns:
            Dict mapping parameter names to their specs:
            {
                'param_name': {
                    'type': 'int' | 'float' | 'bool' | 'str',
                    'default': default_value,
                    'min': min_value,  # for int/float
                    'max': max_value,  # for int/float
                    'step': step_value,  # optional for int/float widgets
                    'decimals': decimal_count,  # optional for float widgets
                    'choices': [allowed, values],  # optional for enums/dropdowns
                    'description': 'human readable description'
                }
            }
        """
        return {}


def create_processor(name: str, params: Optional[Dict[str, Any]] = None) -> ImageProcessor:
    """
    Factory function to create a processor by name.
    
    Args:
        name: Processor name (from ImageProcessor.name())
        params: Optional configuration parameters
        
    Returns:
        Instance of the requested processor
    """
    from ..plugins.utils import get_image_processor_class_from_name
    
    processor_class = get_image_processor_class_from_name(name)
    if processor_class is None:
        raise ValueError(f"Unknown processor: {name}")
    
    processor = processor_class()
    if params:
        processor.configure(params)
    return processor
