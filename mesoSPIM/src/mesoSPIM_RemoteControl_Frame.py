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


def _sample(frame):
    step = max(1, int(np.sqrt(frame.size / _MAX_SAMPLES)))
    return frame[::step, ::step]


def frame_stats(frame):
    """Numbers a model can act on: exposure (saturation, background, dynamic range), focus, and
    where the signal sits in the field."""
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
        "focus_measure": focus_measure(sample),
    }


def focus_measure(sample):
    """Variance of a Laplacian: higher is sharper. Only comparable between frames of the same scene
    at the same zoom, which is what a focus search does."""
    if sample.shape[0] < 3 or sample.shape[1] < 3:
        return 0.0
    laplacian = (
        sample[:-2, 1:-1] + sample[2:, 1:-1] + sample[1:-1, :-2] + sample[1:-1, 2:] - 4 * sample[1:-1, 1:-1]
    )
    scale = float(sample.max() - sample.min()) or 1.0
    return float(laplacian.var() / (scale * scale))


def downsample(frame, max_size):
    """Block-mean the frame so its longer side is at most ``max_size`` pixels."""
    factor = int(np.ceil(max(frame.shape) / max_size))
    if factor <= 1:
        return frame.astype(np.float32)
    rows = (frame.shape[0] // factor) * factor
    cols = (frame.shape[1] // factor) * factor
    block = frame[:rows, :cols].astype(np.float32)
    return block.reshape(rows // factor, factor, cols // factor, factor).mean(axis=(1, 3))


def to_png(frame, max_size):
    """A contrast-stretched 8-bit PNG of the frame, longer side at most ``max_size``."""
    from PIL import Image  # a matplotlib dependency, so always present in the application

    small = downsample(frame, max_size)
    low, high = np.percentile(small, _STRETCH)
    if high <= low:
        high = low + 1.0
    stretched = np.clip((small - low) / (high - low), 0.0, 1.0)
    image = Image.fromarray((stretched * 255).astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), image.size


def describe_frame(frame, max_size=1024, include_image=True):
    """The `get_frame` document: stats always, the PNG (base64) when asked for."""
    frame = np.asarray(frame)
    if frame.ndim != 2 or frame.size == 0:
        raise ValueError(f"expected a 2-D frame, got shape {frame.shape}")
    document = {"available": True, "stats": frame_stats(frame)}
    if include_image:
        png, (width, height) = to_png(frame, max_size)
        document["image"] = {
            "format": "png",
            "width": width,
            "height": height,
            "stretch_percentiles": list(_STRETCH),
            "base64": base64.b64encode(png).decode("ascii"),
        }
    return document
