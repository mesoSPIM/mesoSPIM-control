"""
Identity Processor - Pass-through processor for testing
"""

import numpy as np
from typing import Any, Dict, Iterable
from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION


class IdentityProcessor(ImageProcessor):
    """Pass-through processor that returns the image unchanged.
    
    Useful for testing and as a placeholder in processor chains.
    """

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'Identity'

    @classmethod
    def description(cls) -> str:
        return 'Pass-through processor (no change). Useful for testing.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=["uint8", "uint16", "float32", "float64"],
            dtype_out=["uint8", "uint16", "float32", "float64"],
            ndim=[2, 3],
            is_inplace=True,
            streaming_safe=True,
        )

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        return image.copy() if not image.flags['WRITEABLE'] else image
