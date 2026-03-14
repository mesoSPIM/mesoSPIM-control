"""
Gaussian Blur Processor - Simple spatial denoising
"""

import numpy as np
from typing import Any, Dict, Iterable
from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION


class GaussianBlurProcessor(ImageProcessor):
    """Gaussian blur processor for simple denoising.
    
    Applies Gaussian smoothing to reduce noise. Larger sigma values
    provide more denoising but reduce spatial resolution.
    """

    def __init__(self):
        self.sigma = 1.0

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'GaussianBlur'

    @classmethod
    def description(cls) -> str:
        return 'Gaussian blur for spatial denoising. Larger sigma = more smoothing.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=["uint8", "uint16", "float32"],
            dtype_out=["float32"],
            ndim=[2, 3],
            is_inplace=False,
            streaming_safe=True,
        )

    def configure(self, params: Dict[str, Any]) -> None:
        if 'sigma' in params:
            self.sigma = float(params['sigma'])

    def get_config(self) -> Dict[str, Any]:
        return {'sigma': self.sigma}

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        try:
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(image.astype(np.float32), sigma=self.sigma)
        except ImportError:
            return image
