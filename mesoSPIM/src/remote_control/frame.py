"""Describe the last camera frame for a remote client: numbers for any model, a small PNG for one
that can see.

The frame is the array mesoSPIM keeps for its own display (``core.frame_queue_display``), so
nothing here touches the camera. The numbers are computed from the full frame and are the same
whether or not the image is requested, so a text-only client gets the same basis for a decision
as a vision-capable one.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import base64
import io

import numpy as np

# Percentiles the display stretch and the numbers use; sampled on a stride so a 15-megapixel frame
# stays cheap.
_STRETCH = (1.0, 99.5)
_MAX_SAMPLES = 1_000_000
_FOCUS_SIDE = 512   # the focus measure bins the frame to about this many pixels on its longer side
# get_frame's focus_metric: the Laplacian energy below, or the Auto-Focus Optimizer's DCT-Shannon
FOCUS_METRICS = ("laplacian", "dct_shannon")


def _sample(frame):
    step = max(1, int(np.sqrt(frame.size / _MAX_SAMPLES)))
    return frame[::step, ::step]


def frame_stats(frame, focus_metric="laplacian"):
    """Numbers a model can act on: exposure (saturation, background, dynamic range), focus by
    ``focus_metric`` (one of FOCUS_METRICS), and where the signal sits in the field."""
    sample = _sample(frame).astype(np.float32)
    p1, p10, p50, p90, p99, p999 = np.percentile(sample, (1, 10, 50, 90, 99, 99.9))
    if np.issubdtype(frame.dtype, np.integer):
        full_scale = float(np.iinfo(frame.dtype).max)
    else:
        full_scale = float(sample.max()) or 1.0
    bright = sample > p1 + 0.25 * (p999 - p1)
    rows, cols = np.nonzero(bright)
    centroid = (
        {"row": float(rows.mean() / sample.shape[0]), "col": float(cols.mean() / sample.shape[1])}
        if rows.size
        else None
    )
    return {
        "shape": [int(frame.shape[0]), int(frame.shape[1])],
        "dtype": str(frame.dtype),
        "full_scale": full_scale,
        "min": float(sample.min()),
        "max": float(sample.max()),
        "mean": float(sample.mean()),
        "percentiles": {"p1": float(p1), "p10": float(p10), "p50": float(p50), "p90": float(p90),
                        "p99": float(p99), "p99_9": float(p999)},
        "background": float(p10),
        "saturated_fraction": float(np.mean(sample >= full_scale)),
        "bright_fraction": float(bright.mean()),
        "signal_centroid": centroid,  # 0..1 of height and width, None when the frame is flat
        "focus_measure": focus_measure(frame) if focus_metric == "laplacian" else dct_shannon(frame),
        "focus_metric": focus_metric,
    }


def focus_measure(frame):
    """Laplacian energy over the squared signal: higher is sharper, and the same at any intensity
    or exposure. The second derivative answers to detail, not to a smooth body or a gradient in the
    background. The brightest 0.1% is clipped and the frame binned to about _FOCUS_SIDE pixels, so a
    hot pixel or a saturated patch does not decide it; the camera noise's share, estimated from the
    pixel-to-pixel differences, is taken off, so a dim frame far from focus does not read sharp.
    Only comparable between frames of the same scene at the same zoom, which is what a focus search
    does."""
    frame = np.minimum(frame, np.percentile(_sample(frame), 99.9))
    binned = bin_frame(frame, max(2, int(np.ceil(max(frame.shape) / _FOCUS_SIDE))))
    if binned.shape[0] < 3 or binned.shape[1] < 3:
        return 0.0
    laplacian = (binned[:-2, 1:-1] + binned[2:, 1:-1] + binned[1:-1, :-2] + binned[1:-1, 2:]
                 - 4 * binned[1:-1, 1:-1])
    across = np.diff(binned, axis=1)
    noise = 1.4826 * float(np.median(np.abs(across - np.median(across)))) / np.sqrt(2)   # one pixel's noise
    energy = float(np.mean(laplacian ** 2)) - 20 * noise ** 2                         # a Laplacian of noise: 20 times
    signal = float(np.mean(np.clip(binned - np.percentile(binned, 10), 0, None)))
    return max(energy, 0.0) / signal ** 2 if signal > 0 else 0.0


def dct_shannon(frame):
    """The Auto-Focus Optimizer's measure: the Shannon entropy of the frame's DCT, higher is sharper.
    Like the Optimizer it reads the raw frame, not a binned copy."""
    from ..utils.optimization import shannon_dct

    return float(shannon_dct(frame))


def bin_frame(frame, factor):
    """Bin the frame ``factor`` x ``factor``: each pixel the mean of its block, as a camera bins."""
    if factor <= 1:
        return frame.astype(np.float32)
    rows = (frame.shape[0] // factor) * factor
    cols = (frame.shape[1] // factor) * factor
    block = frame[:rows, :cols].astype(np.float32)
    return block.reshape(rows // factor, factor, cols // factor, factor).mean(axis=(1, 3))


def downsample(frame, max_size):
    """Bin the frame so its longer side is at most ``max_size`` pixels."""
    return bin_frame(frame, int(np.ceil(max(frame.shape) / max_size)))


def to_png(frame, max_size=None, bin_factor=None):
    """A contrast-stretched 8-bit PNG of the frame: binned by ``bin_factor`` when given, else with
    its longer side at most ``max_size``."""
    from PIL import Image  # a matplotlib dependency, so always present in the application

    small = bin_frame(frame, bin_factor) if bin_factor else downsample(frame, max_size)
    low, high = np.percentile(small, _STRETCH)
    if high <= low:
        high = low + 1.0
    stretched = np.clip((small - low) / (high - low), 0.0, 1.0)
    image = Image.fromarray((stretched * 255).astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), image.size


def describe_frame(frame, max_size=1024, include_image=True, bin_factor=None, array_side=None,
                   focus_metric="laplacian"):
    """The `get_frame` document: stats always (from the full frame), the PNG (base64) when asked
    for, binned by ``bin_factor`` or bounded by ``max_size``, and with ``array_side`` the frame
    itself as 16-bit values, binned so its longer side is at most that (a small copy to keep)."""
    frame = np.asarray(frame)
    if frame.ndim != 2 or frame.size == 0:
        raise ValueError(f"expected a 2-D frame, got shape {frame.shape}")
    document = {"available": True, "stats": frame_stats(frame, focus_metric)}
    if include_image:
        png, (width, height) = to_png(frame, max_size, bin_factor)
        document["image"] = {
            "format": "png",
            "width": width,
            "height": height,
            "stretch_percentiles": list(_STRETCH),
            "base64": base64.b64encode(png).decode("ascii"),
        }
    if array_side:
        factor = int(np.ceil(max(frame.shape) / array_side))
        small = np.clip(np.rint(bin_frame(frame, factor)), 0, 65535).astype("<u2")
        document["array"] = {"shape": list(small.shape), "bin": factor,
                             "base64": base64.b64encode(small.tobytes()).decode("ascii")}
    return document


def array_of(document):
    """The 16-bit frame in a get_frame document's "array"."""
    array = document["array"]
    return np.frombuffer(base64.b64decode(array["base64"]), dtype="<u2").reshape(array["shape"])
