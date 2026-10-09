"""The focus metric choice: shannon_dct reads the whole image, get_frame takes focus_metric, and the
Assistant's focus curve never mixes two metrics. No PyQt5, no hardware.

Run from mesoSPIM/: python -m pytest test/test_focus_metric.py -q
"""

import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from src.utils.optimization import shannon_dct
from src.remote_control.commands import _accept_get_frame
from src.remote_control.dispatcher import ValidationError
from src.remote_control.frame import frame_stats
from src.ai_assistant.frames import _focus


def _sample(seed=0):
    rng = np.random.default_rng(seed)
    image = np.zeros((512, 512))
    image[rng.integers(0, 512, 400), rng.integers(0, 512, 400)] = 1000.0
    return image, rng


def test_shannon_dct_reads_the_whole_image():
    image, _ = _sample()
    corner = image.copy()
    corner[256:, :] = 0
    corner[:, 256:] = 0
    assert shannon_dct(image) != shannon_dct(corner)    # was equal: only the top-left quarter counted


def test_both_metrics_fall_with_blur():
    image, rng = _sample()
    for metric in ("laplacian", "dct_shannon"):
        values = [frame_stats((gaussian_filter(image, s) + rng.normal(100, 3, image.shape)).astype(np.float32),
                              metric)["focus_measure"] for s in (1, 3, 8)]
        assert values[0] > values[2] and values[0] >= values[1] >= values[2], (metric, values)   # the Laplacian reads 0 under its noise floor


def test_get_frame_focus_metric():
    assert _accept_get_frame(None, {})["focus_metric"] == "laplacian"
    assert _accept_get_frame(None, {"focus_metric": "dct_shannon"})["focus_metric"] == "dct_shannon"
    with pytest.raises(ValidationError):
        _accept_get_frame(None, {"focus_metric": "brenner"})


def test_focus_curve_uses_the_newest_frames_metric():
    def frame(f, focus, metric):
        return {"t": 0, "position": {"x": 0, "y": 0, "z": 0, "f": f},
                "measures": {"focus": focus, "focus_metric": metric}}
    # The DCT frame at f=20 has a small value that would lose against the Laplacian ones if mixed.
    usable = [frame(0, 50.0, "laplacian"), frame(10, 90.0, "laplacian"),
              frame(10, 0.002, "dct_shannon"), frame(20, 0.003, "dct_shannon")]
    best = _focus(usable, now=0)
    assert best["focus_metric"] == "dct_shannon" and best["f"] == 20 and best["frames_used"] == 2
