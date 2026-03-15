"""
Neural Denoise Processor - PyTorch-based temporal denoising using neural networks

This processor uses pre-trained PyTorch models to denoise images using temporal
information from multiple frames. It supports models that take 1, 3, 5, 7, 9, or 11 frames.
"""

import logging
import torch.autograd.grad_mode
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np

from mesoSPIM.src.plugins.ImageProcessorApi import ImageProcessor, ProcessorCapabilities, API_VERSION

# Install zarr via pip if needed
from mesoSPIM.src.plugins.utils import install_and_import
install_and_import('torch')
install_and_import('torchvision')

logger = logging.getLogger(__name__)


class NeuralDenoiseProcessor(ImageProcessor):
    """Neural network-based temporal denoising processor.
    
    Uses a PyTorch model that takes N frames (must be odd: 1, 3, 5, 7, 9, 11)
    and returns the middle frame denoised.
    
    Buffer algorithm:
    - Current frame is always at middle position (index N//2)
    - Missing future frames are padded with current frame
    - First N//2 frames are passed through (no output)
    - After that, return denoised middle frame
    - At end, flush remaining by padding with last frame
    """

    def __init__(self):
        self.num_frames = 3  # Default to 3-frame model
        self.device = 'auto'
        self._model = None
        self._torch = None
        self._buffer = deque(maxlen=self.num_frames)
        self._frame_index = 0
        self._pending_outputs = deque()
        self._last_frame = None

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return 'NeuralDenoise'

    @classmethod
    def description(cls) -> str:
        return 'Neural network temporal denoising (PyTorch). Requires model files in support_files.'

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
            if num_frames % 2 == 0:
                num_frames += 1  # Make odd
            if num_frames not in [1, 3, 5, 7, 9, 11]:
                logger.warning(f"Invalid num_frames {num_frames}, using 3")
                num_frames = 3
            
            # Reset buffer if num_frames changed
            if num_frames != self.num_frames:
                self.num_frames = num_frames
                self._buffer = deque(maxlen=self.num_frames)
                self._frame_index = 0
                self._pending_outputs.clear()
        
        if 'device' in params:
            self.device = params['device']

    def get_config(self) -> Dict[str, Any]:
        return {
            'num_frames': self.num_frames,
            'device': self.device,
        }

    def reset(self) -> None:
        """Reset the frame buffer and counter."""
        self._buffer.clear()
        self._frame_index = 0
        self._pending_outputs.clear()
        self._last_frame = None

    def _normalize(self, tensor):
        '''Convert to values betwen 0-1 and normalize'''
        tensor /= 65534
        mean = tensor.mean()
        std = tensor.std()
        tensor -= mean
        tensor /= std
        return tensor, mean, std

    def _denormalize(self, tensor, mean, std):
        tensor *= std
        tensor += mean
        tensor *= 65534
        return tensor


    def _load_model(self):
        """Lazy load the PyTorch model."""
        if self._model is not None:
            return
        
        try:
            import torch
            self._torch = torch
        except ImportError:
            print('Failed to import torch')
            logger.error("PyTorch not installed. NeuralDenoiseProcessor requires PyTorch.")
            raise ImportError("PyTorch is required for NeuralDenoiseProcessor. "
                            "Install with: pip install torch")
        
        # Determine device
        if self.device == 'auto':
            self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self._device = torch.device(self.device)
        
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
            # Load model - adjust based on your model architecture
            # This is a placeholder - adjust based on actual model format
            print('Trying to load model')
            from mesoSPIM.src.plugins.support_files.ImageProcessors.NeuralDenoise.autoencoder3DLowProfile import \
                Autoencoder
            self._model = Autoencoder()
            self._model.load_state_dict(torch.load(model_path, map_location=self._device))
            self._model.eval()
            # print('Compiling model')
            # self._model = torch.compile(self._model, mode="reduce-overhead")


            # self._model = torch.jit.load(model_path, map_location=self._device)
            # self._model.eval()
            # logger.info(f"Loaded neural denoising model: {model_path}")
        except Exception as e:
            print('Failed to load model')
            logger.error(f"Failed to load model: {e}")
            raise

    def _prepare_buffer(self, current_frame: np.ndarray) -> np.ndarray:
        """Prepare the buffer with current frame at middle position.
        
        Buffer structure: [?, ?, current, ?, ?] with current at index num_frames//2
        Missing frames (before or after current) are padded with current_frame.
        """
        n = self.num_frames
        mid = n // 2
        
        # Current frame index
        idx = self._frame_index
        
        # Build frame stack
        frame_stack = []
        
        for i in range(n):
            target_idx = idx - mid + i  # The frame index this position should have
            
            if target_idx < 0:
                # Frame doesn't exist yet - pad with current
                frame_stack.append(current_frame.copy())
            elif target_idx <= idx:
                # Frame from the past - already in buffer
                # Find it in buffer (buffer stores frames in order)
                buffer_list = list(self._buffer)
                past_frame_idx = target_idx
                # Map target_idx to buffer position
                # Buffer contains frames from (idx - len(buffer) + 1) to idx
                buffer_start = self._frame_index - len(self._buffer) + 1
                if buffer_start <= past_frame_idx <= self._frame_index:
                    buf_pos = past_frame_idx - buffer_start
                    if buf_pos < len(buffer_list):
                        frame_stack.append(buffer_list[buf_pos].copy())
                    else:
                        frame_stack.append(current_frame.copy())
                else:
                    frame_stack.append(current_frame.copy())
            elif target_idx == idx + 1:
                # Next frame - doesn't exist yet, will be current next time
                # For now, use current as placeholder
                # Actually, for our algorithm, we pad with CURRENT
                frame_stack.append(current_frame.copy())
            else:
                # Future frame - use current as placeholder
                frame_stack.append(current_frame.copy())
        
        return np.stack(frame_stack, axis=0)

    def process_frame(self, image: np.ndarray) -> np.ndarray:
        """Process a single frame through the temporal denoising buffer.
        
        Buffer algorithm (for N=3 example):
        - Frame 0: buffer=[F0,F0,F0], return original (first N//2 = 1 frame returns unchanged)
        - Frame 1: buffer=[F0,F0,F1], return denoised(F0)
        - Frame 2: buffer=[F0,F1,F2], return denoised(F1)
        - etc.
        
        The key: buffer is padded with OLDEST frame at start, CURRENT frame at end
        """
        print('Trying to process frame')
        # Lazy load model on first use
        if self._model is None:
            try:
                self._load_model()
            except Exception as e:
                print(f"Failed to load neural denoising model: {e}. Passing through unprocessed.")
                logger.warning(f"Failed to load neural denoising model: {e}. Passing through unprocessed.")
                return image
        
        n = self.num_frames
        mid = n // 2
        
        # Add current frame to buffer
        self._buffer.append(image.copy())
        self._last_frame = image.copy()
        
        current_buffer_len = len(self._buffer)
        
        # First N//2 frames: return original (buffer not ready for denoising)
        if current_buffer_len <= mid:
            return image
        
        # Build frame stack for denoising
        # Pad with oldest frame at start, current frame at end
        buffer_list = list(self._buffer)
        
        # Oldest frame in buffer
        oldest = buffer_list[0]
        # Current (newest) frame in buffer
        newest = buffer_list[-1]
        
        # Build stack: [oldest, oldest, ..., oldest, buffer[0], buffer[1], ..., newest]
        # Total n frames, with middle being the output frame
        
        # For buffer length L > n//2:
        # - We output the frame at position (L - n//2 - 1) in the original sequence
        # - Stack should be padded to have that frame in the middle
        
        frame_stack = []
        
        # Number of frames we have from the "past" relative to output
        past_frames_needed = mid  # We need mid frames before the output frame
        
        # How many past frames do we actually have in buffer?
        # Buffer contains frames: [output_frame - (L-1), ..., output_frame - 1, current]
        # We want output_frame = buffer[past_frames_needed - 1]
        
        output_frame_index = current_buffer_len - mid - 1
        
        for i in range(n):
            idx = output_frame_index - mid + i
            
            if idx < 0:
                # Before first frame in buffer - pad with oldest
                frame_stack.append(oldest.copy())
            elif idx < current_buffer_len:
                # Frame exists in buffer
                frame_stack.append(buffer_list[idx].copy())
            else:
                # Beyond current buffer - pad with newest (current frame)
                frame_stack.append(newest.copy())
        
        # Stack frames into tensor
        frame_array = np.stack(frame_stack, axis=0)
        
        # Convert to tensor (add channel dimension if needed)
        if frame_array.ndim == 3:
            frame_array = frame_array[:, np.newaxis, :, :]  # N x 1 x H x W
        
        # Run inference
        frame_tensor = self._torch.from_numpy(frame_array).float().to(self._device)

        try:
            with torch.inference_mode():
                print('In inference mode')
                # with torch.autocast(device_type=self._device.type, dtype=torch.bfloat16):
                # print('Next Step Inference')
                frame_tensor, mean, std = self._normalize(frame_tensor)
                output = self._model(frame_tensor)
                output = self._denormalize(output, mean, std)
                print(f'Frame Processed shape: {output.shape}')
        except Exception as e:
            print(f'Inference failed: {e}')
            logger.error(f"Inference failed: {e}")
            return image
        
        # Extract middle frame (the denoised output)
        if isinstance(output, tuple):
            output = output[0]
        
        result = output[mid].cpu().numpy()
        
        # Remove channel dimension if present
        if result.ndim == 3 and result.shape[0] == 1:
            result = result[0]
        
        return result

    def flush(self) -> Optional[np.ndarray]:
        """Flush remaining frames at end of acquisition.
        
        Returns the last denoised frame if any remain in the buffer.
        """
        if self._model is None or self._last_frame is None:
            return None
        
        n = self.num_frames
        mid = n // 2
        
        # If buffer has fewer than N frames, pad with last frame
        buffer_list = list(self._buffer)
        
        if len(buffer_list) == 0:
            return None
        
        # We need to output the frame at position (len(buffer) - 1 - mid)
        # which is the last "middle" position we haven't output yet
        
        # Actually, let's just output the last frame with whatever we have
        # Pad buffer to full size with last frame
        while len(buffer_list) < n:
            buffer_list.append(self._last_frame.copy())
        
        # Now we have full buffer, but we need to shift to output the remaining frames
        # For simplicity, just output one more denoised frame using padded buffer
        if len(buffer_list) >= n:
            # Use last n frames
            frame_stack = buffer_list[-n:]
            frame_array = np.stack(frame_stack, axis=0)
            if frame_array.ndim == 3:
                frame_array = frame_array[:, np.newaxis, :, :]
            
            frame_tensor = self._torch.from_numpy(frame_array).float().to(self._device)
            
            with self._torch.no_grad():
                output = self._model(frame_tensor)
            
            if isinstance(output, tuple):
                output = output[0]
            
            result = output[mid].cpu().numpy()
            if result.ndim == 3 and result.shape[0] == 1:
                result = result[0]
            
            return result
        
        return None
