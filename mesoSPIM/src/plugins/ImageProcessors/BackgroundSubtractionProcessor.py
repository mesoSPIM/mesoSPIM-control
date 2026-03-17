"""
Background Subtraction Processor - Rolling ball background estimation
"""

import numpy as np
from typing import Any, Dict, Iterable
from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION


class BackgroundSubtractionProcessor(ImageProcessor):
    """Background subtraction using rolling ball or constant offset.
    
    Estimates background using a rolling ball algorithm and subtracts it.
    Alternative mode uses a simple constant threshold subtraction.
    """

    def __init__(self):
        self.method = 'rolling_ball'
        self.radius = 50
        self.threshold = 0
        self._background = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'BackgroundSubtraction'

    @classmethod
    def description(cls) -> str:
        return 'Subtract background using rolling ball or constant threshold.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=["uint8", "uint16", "float32"],
            dtype_out=["float32"],
            ndim=[2, 3],
            is_inplace=False,
            streaming_safe=False,
        )

    @classmethod
    def parameter_descriptions(cls) -> Dict[str, Dict[str, Any]]:
        return {
            'method': {
                'type': 'str',
                'default': 'rolling_ball',
                'choices': ['rolling_ball', 'threshold'],
                'description': 'Background estimation mode.',
            },
            'radius': {
                'type': 'int',
                'default': 50,
                'min': 1,
                'max': 1000,
                'step': 1,
                'description': 'Uniform filter radius used for rolling-ball approximation.',
            },
            'threshold': {
                'type': 'float',
                'default': 0.0,
                'min': 0.0,
                'max': 65535.0,
                'step': 1.0,
                'decimals': 1,
                'description': 'Constant value subtracted in threshold mode.',
            },
        }

    def configure(self, params: Dict[str, Any]) -> None:
        if 'method' in params:
            self.method = params['method']
        if 'radius' in params:
            self.radius = int(params['radius'])
        if 'threshold' in params:
            self.threshold = float(params['threshold'])

    def get_config(self) -> Dict[str, Any]:
        return {
            'method': self.method,
            'radius': self.radius,
            'threshold': self.threshold,
        }

    def reset(self) -> None:
        self._background = None

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        image = image.astype(np.float32)
        
        if self.method == 'rolling_ball':
            return self._rolling_ball_subtraction(image)
        elif self.method == 'threshold':
            return self._threshold_subtraction(image)
        else:
            return image

    def _rolling_ball_subtraction(self, image: np.ndarray) -> np.ndarray:
        try:
            from scipy.ndimage import uniform_filter
            background = uniform_filter(image, size=2 * self.radius + 1, mode='reflect')
            result = image - background
            result = np.clip(result, 0, None)
            return result
        except ImportError:
            return image

    def _threshold_subtraction(self, image: np.ndarray) -> np.ndarray:
        result = image - self.threshold
        return np.clip(result, 0, None)
