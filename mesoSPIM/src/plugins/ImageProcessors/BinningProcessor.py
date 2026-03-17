"""
Binning Processor - Pixel binning for downsampling
"""

import numpy as np
from typing import Any, Dict, Iterable
from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION


class BinningProcessor(ImageProcessor):
    """Pixel binning processor for spatial downsampling.
    
    Combines adjacent pixels to reduce image size. Bin factor of 2
    means 2x2 pixels become 1 pixel.
    """

    def __init__(self):
        self.bin_factor = 2
        self.method = 'mean'

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'Binning'

    @classmethod
    def description(cls) -> str:
        return 'Pixel binning for downsampling. bin_factor=2 means 2x2 -> 1 pixel.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=["uint8", "uint16", "float32"],
            dtype_out=["uint16", "float32"],
            ndim=[2, 3],
            is_inplace=False,
            streaming_safe=True,
        )

    @classmethod
    def parameter_descriptions(cls) -> Dict[str, Dict[str, Any]]:
        return {
            'bin_factor': {
                'type': 'int',
                'default': 2,
                'min': 1,
                'max': 16,
                'step': 1,
                'description': 'Square binning factor applied to X and Y.',
            },
            'method': {
                'type': 'str',
                'default': 'mean',
                'choices': ['mean', 'sum', 'max'],
                'description': 'Reduction method used inside each bin.',
            },
        }

    def configure(self, params: Dict[str, Any]) -> None:
        if 'bin_factor' in params:
            self.bin_factor = int(params['bin_factor'])
        if 'method' in params:
            self.method = params['method']

    def get_config(self) -> Dict[str, Any]:
        return {
            'bin_factor': self.bin_factor,
            'method': self.method,
        }

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[-2:]
        bin_factor = self.bin_factor
        
        new_h = h // bin_factor
        new_w = w // bin_factor
        
        if new_h == 0 or new_w == 0:
            return image
        
        if image.ndim == 2:
            cropped = image[:new_h * bin_factor, :new_w * bin_factor]
            reshaped = cropped.reshape(new_h, bin_factor, new_w, bin_factor)
            if self.method == 'mean':
                return reshaped.mean(axis=(1, 3)).astype(image.dtype)
            elif self.method == 'sum':
                return reshaped.sum(axis=(1, 3)).astype(image.dtype)
            elif self.method == 'max':
                return reshaped.max(axis=(1, 3)).astype(image.dtype)
            else:
                return reshaped.mean(axis=(1, 3)).astype(image.dtype)
        else:
            return image
