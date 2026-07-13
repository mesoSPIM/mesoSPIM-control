"""
Difference of Gaussians Processor - Band-pass spatial filtering.
"""

import logging
import math
from typing import Any, Dict, Tuple

import numpy as np

from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION
from mesoSPIM.src.plugins.utils import count_domain_to_uint16

# Install zarr via pip if needed
from mesoSPIM.src.plugins.utils import install_and_import
install_and_import('torch', index_url="https://download.pytorch.org/whl/cu128")

logger = logging.getLogger(__name__)


class DifferenceOfGaussiansProcessor(ImageProcessor):
    """Difference-of-Gaussians filter with torch CPU/GPU execution."""

    def __init__(self):
        self.sigma_low = 1.0
        self.sigma_high = 2.5
        self.device = 'auto'
        self._torch = None
        self._resolved_device = None
        self._kernel_cache = {}
        self._warned_missing_torch = False
        self._warned_cuda_fallback = False

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'DifferenceOfGaussians'

    @classmethod
    def description(cls) -> str:
        return 'Difference-of-Gaussians band-pass filter with torch CPU/GPU execution.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=['uint8', 'uint16', 'float32'],
            dtype_out=['uint16'],
            ndim=[2],
            is_inplace=False,
            streaming_safe=True,
        )

    @classmethod
    def parameter_descriptions(cls) -> Dict[str, Dict[str, Any]]:
        return {
            'sigma_low': {
                'type': 'float',
                'default': 1.0,
                'min': 0.0,
                'max': 100.0,
                'step': 0.1,
                'decimals': 2,
                'description': 'Sigma for the narrower Gaussian blur in pixels.',
            },
            'sigma_high': {
                'type': 'float',
                'default': 2.0,
                'min': 0.1,
                'max': 200.0,
                'step': 0.1,
                'decimals': 2,
                'description': 'Sigma for the broader Gaussian blur in pixels; must be larger than sigma_low.',
            },
            'device': {
                'type': 'str',
                'default': 'auto',
                'choices': ['auto', 'cpu', 'cuda'],
                'description': 'Processing device: auto selects CUDA if available, otherwise CPU.',
            },
        }

    def configure(self, params: Dict[str, Any]) -> None:
        if 'sigma_low' in params:
            self.sigma_low = max(0.1, float(params['sigma_low']))
        if 'sigma_high' in params:
            self.sigma_high = max(0.1, float(params['sigma_high']))
        if 'device' in params:
            self.device = str(params['device'])

        self._kernel_cache.clear()
        self._resolved_device = None
        self._warned_cuda_fallback = False

    def get_config(self) -> Dict[str, Any]:
        return {
            'sigma_low': self.sigma_low,
            'sigma_high': self.sigma_high,
            'device': self.device,
        }

    def reset(self) -> None:
        self._resolved_device = None
        self._warned_cuda_fallback = False

    def _ensure_torch(self):
        if self._torch is not None:
            return self._torch

        try:
            import torch
            self._torch = torch
            return torch
        except ImportError:
            if not self._warned_missing_torch:
                logger.warning('PyTorch is not installed; DifferenceOfGaussiansProcessor will pass through frames unchanged.')
                self._warned_missing_torch = True
            return None

    def _resolve_device(self):
        torch = self._ensure_torch()
        if torch is None:
            return None

        if self.device == 'cpu':
            target = torch.device('cpu')
        elif self.device == 'cuda':
            if torch.cuda.is_available():
                target = torch.device('cuda')
            else:
                if not self._warned_cuda_fallback:
                    logger.warning('CUDA requested for DifferenceOfGaussiansProcessor but not available; falling back to CPU.')
                    self._warned_cuda_fallback = True
                target = torch.device('cpu')
        else:
            target = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        self._resolved_device = target
        return target

    def _validate_sigmas(self) -> bool:
        if self.sigma_low <= 0:
            logger.warning('DifferenceOfGaussiansProcessor requires sigma_low > 0; passing through frame unchanged.')
            return False
        if self.sigma_high <= self.sigma_low:
            logger.warning('DifferenceOfGaussiansProcessor requires sigma_high > sigma_low; passing through frame unchanged.')
            return False
        return True

    def _get_gaussian_kernel(self, sigma: float, device) -> Tuple[Any, Any]:
        torch = self._torch
        cache_key = (float(sigma), str(device))
        if cache_key in self._kernel_cache:
            return self._kernel_cache[cache_key]

        radius = max(1, int(math.ceil(4.0 * sigma)))
        coords = torch.arange(-radius, radius + 1, device=device, dtype=torch.float32)
        kernel = torch.exp(-(coords ** 2) / (2.0 * sigma * sigma))
        kernel /= kernel.sum()

        kernel_x = kernel.view(1, 1, 1, -1)
        kernel_y = kernel.view(1, 1, -1, 1)
        self._kernel_cache[cache_key] = (kernel_x, kernel_y)
        return kernel_x, kernel_y

    def _gaussian_blur(self, image_tensor, sigma: float):
        torch = self._torch
        kernel_x, kernel_y = self._get_gaussian_kernel(sigma, image_tensor.device)
        pad_x = kernel_x.shape[-1] // 2
        pad_y = kernel_y.shape[-2] // 2

        blurred = torch.nn.functional.pad(image_tensor, (pad_x, pad_x, 0, 0), mode='reflect')
        blurred = torch.nn.functional.conv2d(blurred, kernel_x)
        blurred = torch.nn.functional.pad(blurred, (0, 0, pad_y, pad_y), mode='reflect')
        blurred = torch.nn.functional.conv2d(blurred, kernel_y)
        return blurred

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        if image.ndim != 2:
            logger.warning(f'DifferenceOfGaussiansProcessor expects 2D input, got shape {image.shape}. Passing through unchanged.')
            return count_domain_to_uint16(image)

        if not self._validate_sigmas():
            return count_domain_to_uint16(image)

        device = self._resolve_device()
        if device is None:
            return count_domain_to_uint16(image)

        image = np.ascontiguousarray(image.astype(np.float32, copy=False))

        try:
            torch = self._torch
            image_tensor = torch.from_numpy(image).to(device=device, dtype=torch.float32)
            image_tensor = image_tensor.unsqueeze(0).unsqueeze(0)

            if self.sigma_low == 0:
                blur_low = image_tensor
            else:
                blur_low = self._gaussian_blur(image_tensor, self.sigma_low)
            blur_high = self._gaussian_blur(image_tensor, self.sigma_high)
            dog = blur_low - blur_high
            dog = torch.clamp(dog, min=0.0)

            result = dog.squeeze(0).squeeze(0).detach().cpu().numpy()
            result = count_domain_to_uint16(result)
            return result
        except Exception as exc:
            logger.warning(f'DifferenceOfGaussiansProcessor failed: {exc}. Passing through frame unchanged.')
            return count_domain_to_uint16(image)
