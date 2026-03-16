"""
Neural Denoise Processor - PyTorch-based temporal denoising using neural networks

This processor uses pre-trained PyTorch models to denoise images using temporal
information from multiple frames. It supports models that take 1, 3, 5, 7, 9, or 11 frames.
"""

import logging
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np

from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION

# Install zarr via pip if needed
from mesoSPIM.src.plugins.utils import install_and_import
install_and_import('torch', index_url="https://download.pytorch.org/whl/cu128")
# install_and_import('torchvision', index_url="https://download.pytorch.org/whl/cu128")

logger = logging.getLogger(__name__)


class NeuralDenoiseProcessor(ImageProcessor):
    """Neural network-based temporal denoising processor.

    Uses a PyTorch model that takes N frames and returns a denoised prediction
    for the LAST frame in the temporal stack. In principle, more frames should give better results,
    but with diminishing returns and increased latency.

    Buffer algorithm:
    - On first frame, fill the entire buffer with that frame
    - On each new frame, append it and drop the oldest frame
    - Every call returns a denoised version of the most recently arrived frame
    """

    def __init__(self):
        self.num_frames = 3  # Default to 3-frame model
        self.device = 'auto'
        self._model = None
        self._torch = None
        self._buffer = deque(maxlen=self.num_frames)
        self._last_frame = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'NeuralDenoise'

    @classmethod
    def description(cls) -> str:
        return 'Neural network temporal denoising using a PyTorch model that predicts the newest frame from a temporal stack.'

    @classmethod
    def capabilities(cls) -> ProcessorCapabilities:
        return ProcessorCapabilities(
            dtype_in=["uint8", "uint16", "float32"],
            dtype_out=["uint8", "uint16", "float32"],
            ndim=[2, 3],
            is_inplace=False,
            streaming_safe=False,
        )

    @classmethod
    def parameter_descriptions(cls) -> Dict[str, Dict[str, Any]]:
        return {
            'num_frames': {
                'type': 'int',
                'default': 3,
                'min': 1,
                'max': 11,
                'description': 'Number of frames for temporal denoising (1, 3, 5, 7, 9, or 11). '
                               'Must have corresponding denoise_Nframe.pth model file.'
            },
            'device': {
                'type': 'str',
                'default': 'auto',
                'description': 'Device for inference: "auto" (GPU if available), "cuda", or "cpu"'
            }
        }

    def configure(self, params: Dict[str, Any]) -> None:
        """Configure the processor with parameters."""
        if 'num_frames' in params:
            num_frames = int(params['num_frames'])
            if num_frames not in [1, 3, 5, 7, 9, 11]:
                logger.warning(f"Invalid num_frames {num_frames}, using 3")
                num_frames = 3
            
            # Reset buffer if num_frames changed
            if num_frames != self.num_frames:
                self.num_frames = num_frames
                self._buffer = deque(maxlen=self.num_frames)
        
        if 'device' in params:
            self.device = params['device']

    def get_config(self) -> Dict[str, Any]:
        return {
            'num_frames': self.num_frames,
            'device': self.device,
        }

    def reset(self) -> None:
        """Reset the frame buffer and counter."""
        self._buffer = deque(maxlen=self.num_frames)
        self._last_frame = None

    def _normalize(self, tensor):
        """
        Emulate skimage uint16 -> float conversion, then z-score normalize.
        Expects input tensor values corresponding to uint16 intensities.
        """
        tensor /= 65535.0
        mean = tensor.mean()
        std = tensor.std()
        std = std.clamp_min(1e-6)
        tensor -= mean
        tensor /= std
        return tensor, mean, std

    def _denormalize(self, tensor, mean, std):
        """
        Undo z-score normalization, returning float-domain image
        comparable to skimage img_as_float output.
        """
        tensor *= std
        tensor += mean
        # tensor *= 65534
        return tensor


    def _load_model(self):
        """Lazy load the PyTorch model."""
        if self._model is not None:
            return
        
        try:
            import torch
            # import torch.autograd.grad_mode
            self._torch = torch
        except ImportError:
            print('Failed to import torch')
            logger.error("PyTorch not installed. NeuralDenoiseProcessor requires PyTorch.")
            raise ImportError("PyTorch is required for NeuralDenoiseProcessor. "
                            "Install with: pip install torch")
        
        # Determine device
        if self.device == 'auto':
            self._device = self._torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self._device = self._torch.device(self.device)
        
        logger.info(f"NeuralDenoiseProcessor using device: {self._device}")
        
        # Find model file
        model_dir = Path(__file__).parents[1] / 'support_files' / 'ImageProcessors' / 'NeuralDenoise'
        model_path = model_dir / f'denoise_{self.num_frames}frame.pth'
        
        if not model_path.exists():
            logger.error(f"Model file not found: {model_path}")
            raise FileNotFoundError(f"Neural denoising model not found: {model_path}. "
                                   f"Place denoise_{self.num_frames}frame.pth in the support_files directory.")
        
        logger.info(f"Loading model from: {model_path}")
        
        try:

            print('Trying to load model')
            from mesoSPIM.src.plugins.support_files.ImageProcessors.NeuralDenoise.autoencoder3DLowProfile import \
                Autoencoder
            self._model = Autoencoder().to(self._device)
            state_dict = self._torch.load(model_path, map_location=self._device)
            self._model.load_state_dict(state_dict)
            self._model.eval()

            """
            Compile is causing errors probably due to windows. Linux has better support.
            
            Inference failed: Cannot find a working triton installation. Either the package is not installed or it is too old. More information on installing Triton can be found at: https://github.com/triton-lang/triton

            Set TORCHDYNAMO_VERBOSE=1 for the internal stack trace (please do this especially if you're reporting a bug to PyTorch). For even more developer context, set TORCH_LOGS="+dynamo"

            try:
                print('Compiling model')
                self._model = self._torch.compile(self._model, mode="reduce-overhead")
            except:
                print('Model compilation failed, using uncompiled model')
                logger.warning("Model compilation failed, using uncompiled model. This may result in slower inference.")
            """

            # self._model = self._torch.jit.load(model_path, map_location=self._device)
            # self._model.eval()
            # logger.info(f"Loaded neural denoising model: {model_path}")
        except Exception as e:
            print('Failed to load model')
            logger.error(f"Failed to load model: {e}")
            raise

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        """Process a single frame through the temporal denoising buffer.

        New workflow for last-frame prediction:
        - First frame fills the whole buffer
        - Each subsequent frame shifts buffer by one
        - Model predicts denoised version of the newest frame
        """
        if self._model is None:
            try:
                self._load_model()
            except Exception as e:
                print(f"Failed to load neural denoising model: {e}. Passing through unprocessed.")
                logger.warning(f"Failed to load neural denoising model: {e}. Passing through unprocessed.")
                return image

        input_dtype = image.dtype
        image_copy = image.copy()
        self._last_frame = image_copy

        # First frame: fill the entire buffer with copies of the first frame
        if len(self._buffer) == 0:
            self._buffer = deque(
                [image_copy.copy() for _ in range(self.num_frames)],
                maxlen=self.num_frames
            )
        else:
            # Later frames: append newest, automatically drop oldest
            self._buffer.append(image_copy)

        # Stack buffer into (D, H, W)
        frame_array = np.stack(list(self._buffer), axis=0)

        # Add batch dimension -> (1, D, H, W)
        frame_tensor = self._torch.from_numpy(frame_array).float().unsqueeze(0).to(self._device)

        try:
            with self._torch.inference_mode():
                if self._device.type == "cuda":
                    with self._torch.autocast(device_type="cuda", dtype=self._torch.float16):
                        frame_tensor, mean, std = self._normalize(frame_tensor)
                        output = self._model(frame_tensor)
                        output = self._denormalize(output, mean, std)
                else:
                    frame_tensor, mean, std = self._normalize(frame_tensor)
                    output = self._model(frame_tensor)
                    output = self._denormalize(output, mean, std)
        except Exception as e:
            print(f"Inference failed: {e}")
            logger.error(f"Inference failed: {e}")
            return image

        if isinstance(output, tuple):
            output = output[0]

        # Model output should be (1, 1, H, W)
        result = output[0, 0].detach().float().cpu().numpy()

        # Cast back to original input dtype
        # denormalize maintains float 0-1 range, so we can just scale and cast back to uint16 or uint8
        result = np.clip(result, 0.0, 1.0)
        if input_dtype == np.uint16:
            result = np.rint(result * 65535.0).astype(np.uint16, copy=False)
        elif input_dtype == np.uint8:
            result = np.rint(result * 255.0).astype(np.uint8, copy=False)
        elif input_dtype == np.float32:
            result = result.astype(np.float32, copy=False)
        else:
            logger.warning(f"Unexpected input dtype {input_dtype}, returning float32")
            result = result.astype(np.float32, copy=False)

        return result

    def flush(self) -> Optional[np.ndarray]:
        """No flush output needed for last-frame prediction."""
        return None
