"""The little a viewer needs to know about an OME-Zarr store.

Neuroglancer reads the store itself; this module reads just enough of the same
metadata to *place* the store (its axes, voxel size and translation) and to
*name* its channels (the ``omero`` block, when there is one), with the standard
library only. Both OME-Zarr generations are read: 0.4 on zarr v2 (``.zattrs``)
and 0.5 on zarr v3 (``zarr.json``).

One thing reads image data: :func:`sample_window`, for a channel whose store
gives no contrast window, looks at a small coarse sample of its pixels. It uses
the ``zarr`` package mesoSPIM-control writes its stores with, and does without
when it is missing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# OME axis unit spellings, and what neuroglancer turns them into: a base SI unit
# and a factor. Mirrors OME_UNITS in neuroglancer's datasource/zarr/ome.js.
_UNITS: dict[str, tuple[str, float]] = {
    "": ("", 1.0),
    "meter": ("m", 1.0),
    "decimeter": ("m", 1e-1),
    "centimeter": ("m", 1e-2),
    "millimeter": ("m", 1e-3),
    "micrometer": ("m", 1e-6),
    "micron": ("m", 1e-6),
    "nanometer": ("m", 1e-9),
    "picometer": ("m", 1e-12),
    "angstrom": ("m", 1e-10),
    "m": ("m", 1.0),
    "cm": ("m", 1e-2),
    "mm": ("m", 1e-3),
    "um": ("m", 1e-6),
    "µm": ("m", 1e-6),  # micro sign
    "μm": ("m", 1e-6),  # greek mu
    "nm": ("m", 1e-9),
    "second": ("s", 1.0),
    "millisecond": ("s", 1e-3),
    "microsecond": ("s", 1e-6),
    "minute": ("s", 60.0),
    "hour": ("s", 3600.0),
    "s": ("s", 1.0),
    "ms": ("s", 1e-3),
}


class NotAStore(ValueError):
    """The path does not hold OME-Zarr this viewer accepts.

    Accepted: OME-NGFF 0.4 on zarr v2, or 0.5 on zarr v3, whose axes are
    ``t, c, z, y, x`` or some of them, in that order, always with ``z, y, x``.
    So a ``(t, c, z, y, x)`` store opens, and so do ``(z, y, x)``, ``(c, z, y, x)``
    and ``(t, z, y, x)``: an axis that is left out counts as one step long. How the
    arrays are chunked or sharded is not looked at, but for a quick picture a
    chunk should hold one time point of one channel, as the acquisition software
    writes them.

    ``reason`` is set where the folder is recognised as an OME-Zarr store but
    cannot be shown: why, in a few words without the path, for a sentence that
    names the folder itself. It is None for a folder that is no store at all.
    """

    def __init__(self, message: str, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


class NotSupported(NotAStore):
    """The path is an OME-Zarr image, but in a form this viewer does not read.

    Kept apart from a folder that is no image at all, so that such a store is
    reported as what it is rather than mistaken for a folder of acquisitions.
    """


VERSIONS = {"0.4": "zarr2", "0.5": "zarr3"}
AXES = ("t", "c", "z", "y", "x")


@dataclass(frozen=True)
class Axis:
    name: str
    type: str  # "space", "time", "channel" or ""
    unit: str  # as written in the store, e.g. "micrometer"; "" when absent

    @property
    def si(self) -> tuple[str, float]:
        """The base SI unit and the factor from the written unit to it."""
        return _UNITS.get(self.unit, ("", 1.0))

    @property
    def is_channel(self) -> bool:
        return self.type == "channel"


@dataclass(frozen=True)
class Channel:
    label: str
    color: str | None = None  # "#rrggbb"
    window: tuple[float, float] | None = None  # black and white points
    limits: tuple[float, float] | None = None  # the range the sliders cover
    active: bool = True


@dataclass(frozen=True)
class Store:
    path: Path
    format: str  # "zarr2" or "zarr3"
    axes: tuple[Axis, ...]
    scale: tuple[float, ...]  # level 0, per axis, in the axis's written unit
    translation: tuple[float, ...]  # level 0, per axis, in the written unit
    shape: tuple[int, ...]  # level 0
    channels: tuple[Channel, ...]
    levels: tuple[str, ...] = ()  # the pyramid's array paths, finest first

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def channel_axis(self) -> int | None:
        for index, axis in enumerate(self.axes):
            if axis.is_channel:
                return index
        return None

    def axis_index(self, name: str) -> int:
        for index, axis in enumerate(self.axes):
            if axis.name == name:
                return index
        raise KeyError(f"{self.path.name} has no axis called {name!r}")

    @property
    def channel_count(self) -> int:
        at = self.channel_axis
        return self.shape[at] if at is not None else 1


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _hex(color: object) -> str | None:
    if not isinstance(color, str):
        return None
    digits = color.lstrip("#")
    if len(digits) != 6:
        return None
    try:
        int(digits, 16)
    except ValueError:
        return None
    return f"#{digits.lower()}"


def _pair(block: object, low: str, high: str) -> tuple[float, float] | None:
    if not isinstance(block, dict):
        return None
    try:
        a, b = float(block[low]), float(block[high])
    except (KeyError, TypeError, ValueError):
        return None
    return (a, b) if b > a else None


def _omero_channels(omero: object) -> list[Channel]:
    if not isinstance(omero, dict) or not isinstance(omero.get("channels"), list):
        return []
    found = []
    for index, raw in enumerate(omero["channels"]):
        if not isinstance(raw, dict):
            continue
        window = raw.get("window")
        found.append(
            Channel(
                label=str(raw.get("label") or f"channel {index}"),
                color=_hex(raw.get("color")),
                window=_pair(window, "start", "end"),
                limits=_pair(window, "min", "max"),
                active=bool(raw.get("active", True)),
            )
        )
    return found


def _transforms(rank: int, transforms: object) -> tuple[list[float], list[float]]:
    """Compose a list of OME coordinate transformations into (scale, translation).

    Applied in order, as neuroglancer does: a later transformation acts on the
    result of the earlier one.
    """
    scale = [1.0] * rank
    translation = [0.0] * rank
    if not isinstance(transforms, list):
        return scale, translation
    for step in transforms:
        if not isinstance(step, dict):
            continue
        kind = step.get("type")
        if kind == "scale" and isinstance(step.get("scale"), list):
            for i, s in enumerate(step["scale"][:rank]):
                scale[i] *= float(s)
                translation[i] *= float(s)
        elif kind == "translation" and isinstance(step.get("translation"), list):
            for i, t in enumerate(step["translation"][:rank]):
                translation[i] += float(t)
    return scale, translation


def _array_shape(level: Path) -> list[int] | None:
    """The shape of an array, from zarr v3's ``zarr.json`` or v2's ``.zarray``."""
    for description in (level / "zarr.json", level / ".zarray"):
        described = _read_json(description)
        if isinstance(described, dict) and isinstance(described.get("shape"), list):
            return [int(n) for n in described["shape"]]
    return None


def _check_axes(root: Path, axes: tuple[Axis, ...]) -> None:
    """Refuse axes other than ``t, c, z, y, x`` or an in-order part of them with z, y, x."""
    names = [axis.name for axis in axes]
    in_order = [name for name in AXES if name in names]
    if names != in_order or not {"z", "y", "x"} <= set(names):
        raise NotSupported(
            f"{root} declares axes {names}; accepted are {list(AXES)} or some of them, "
            "in that order, always with z, y and x",
            reason=f"its axes are {', '.join(names)}, not t, c, z, y, x or some of them in that order",
        )
    for axis in axes:
        if axis.name == "c" and axis.type != "channel":
            raise NotSupported(
                f"{root}: axis c must be of type 'channel'", reason="its axis c is not of type channel"
            )


def read_store(path: str | Path) -> Store:
    """Describe the OME-Zarr store at ``path``."""
    root = Path(path).expanduser().resolve()
    attrs: dict | None
    fmt: str
    if (root / "zarr.json").is_file():
        fmt = "zarr3"
        described = _read_json(root / "zarr.json") or {}
        attrs = described.get("attributes") if isinstance(described, dict) else None
    elif (root / ".zattrs").is_file():
        fmt = "zarr2"
        attrs = _read_json(root / ".zattrs")
    else:
        raise NotAStore(f"{root} holds neither zarr.json nor .zattrs")
    if not isinstance(attrs, dict):
        raise NotAStore(
            f"{root}: the store's attributes could not be read", reason="its metadata could not be read"
        )

    ome = attrs.get("ome") if isinstance(attrs.get("ome"), dict) else attrs
    multiscales = ome.get("multiscales")
    if not isinstance(multiscales, list) or not multiscales or not isinstance(multiscales[0], dict):
        raise NotAStore(f"{root} carries no OME multiscales metadata")
    multiscale = multiscales[0]
    version = str(ome.get("version", multiscale.get("version", "")))
    if version.startswith("0.6"):
        # 0.6 moved the axes and reshaped the transformations; the neuroglancer the
        # page is built on (2.41) does not read it yet, so neither does this viewer.
        raise NotSupported(
            f"{root} is OME-NGFF {version}, which this viewer does not read yet; "
            "accepted are 0.4 on zarr v2 and 0.5 on zarr v3",
            reason=f"it is OME-NGFF {version}, which the viewer does not read yet",
        )
    if VERSIONS.get(version) != fmt:
        raise NotSupported(
            f"{root} is OME-NGFF {version or 'of no stated version'!s} on {fmt}; "
            "accepted are 0.4 on zarr v2 and 0.5 on zarr v3",
            reason=f"it is OME-NGFF {version or 'of no stated version'!s} on {fmt}, "
            "not 0.4 on zarr v2 or 0.5 on zarr v3",
        )

    axes = tuple(
        Axis(
            name=str(axis.get("name", i)),
            type=str(axis.get("type", "")),
            unit=str(axis.get("unit", "") or ""),
        )
        for i, axis in enumerate(multiscale.get("axes", []))
        if isinstance(axis, dict)
    )
    _check_axes(root, axes)
    rank = len(axes)
    datasets = multiscale.get("datasets")
    if not isinstance(datasets, list) or not datasets or not isinstance(datasets[0], dict):
        raise NotSupported(
            f"{root}: the multiscale names no datasets", reason="its metadata names no image data"
        )
    level0 = datasets[0]
    inner_scale, inner_translation = _transforms(rank, level0.get("coordinateTransformations"))
    outer_scale, outer_translation = _transforms(rank, multiscale.get("coordinateTransformations"))
    scale = [inner_scale[i] * outer_scale[i] for i in range(rank)]
    translation = [
        inner_translation[i] * outer_scale[i] + outer_translation[i] for i in range(rank)
    ]

    level_path = root / str(level0.get("path", "0"))
    shape = _array_shape(level_path)
    if shape is None or len(shape) != rank:
        raise NotSupported(
            f"{root}: level {level0.get('path', '0')!s} has no readable array shape",
            reason="its image data could not be read",
        )

    omero = ome.get("omero", attrs.get("omero"))
    channels = _omero_channels(omero)
    return Store(
        path=root,
        format=fmt,
        axes=axes,
        scale=tuple(scale),
        translation=tuple(translation),
        shape=tuple(shape),
        channels=tuple(channels),
        levels=tuple(
            str(dataset.get("path", index))
            for index, dataset in enumerate(datasets)
            if isinstance(dataset, dict)
        ),
    )


# How many planes of a copy are looked at to set a channel's contrast.
SAMPLE_PLANES = 16
# A copy is sampled only while one plane of it costs at most this much to read. A
# plane's chunks are decoded whole, so a plane of the finest copy of a big tile,
# whose chunks run to hundreds of megabytes, is left alone.
SAMPLE_BYTES = 32 * 2**20


def sample_window(store: Store, channel: int | None = None) -> tuple[float, float] | None:
    """The darkest and brightest value of one channel, in a small coarse sample.

    For a channel whose store gives no contrast window: the writers of the
    acquisition software leave it out, and the engine's default of the whole
    0..65535 range shows a camera's few thousand counts as nearly black. The
    sample is what the operator's Min-Max button would find on a picture of the
    whole stack: the coarsest copy in the store's pyramid, at the first time
    point, through up to ``SAMPLE_PLANES`` planes spread over the depth.

    While a store is being written, the coarsest copy is the last to get its
    chunks -- one chunk of it covers a good part of the stack's depth -- so a
    copy that holds nothing yet is passed over for the next finer one, as far
    as one whose planes are still cheap to read (``SAMPLE_BYTES``). The
    contrast is then set from the first planes to land.

    ``channel`` is the index along the store's channel axis (None for a store
    without one). Voxels still at the array's fill value have not been written
    yet and are left out, so a store the microscope has only just begun gives
    None, as does one whose sample is flat or that cannot be read; the caller
    asks again when more has landed.
    """
    try:
        import numpy as np
        import zarr
    except ImportError:
        logger.info("zarr is not installed: the contrast of %s is not set from its data", store.path)
        return None
    for level in reversed(store.levels or ("0",)):
        try:
            array = zarr.open_array(store=str(store.path / level), mode="r")
            if _plane_bytes(store, array) > SAMPLE_BYTES:
                return None  # and the finer copies cost more still
            selection = []
            for axis, length in zip(store.axes, array.shape):
                if axis.name == "t":
                    selection.append(0)
                elif axis.is_channel:
                    selection.append(channel or 0)
                elif axis.name == "z" and length > SAMPLE_PLANES:
                    selection.append(np.linspace(0, length - 1, SAMPLE_PLANES).round().astype(int))
                else:
                    selection.append(slice(None))
            sample = np.asarray(array.get_orthogonal_selection(tuple(selection)))
        except Exception as error:  # noqa: BLE001 -- a store being written may be half there
            logger.debug("no contrast sample from %s/%s: %s", store.path, level, error)
            return None
        written = sample[sample != array.fill_value] if array.fill_value is not None else sample
        if written.size == 0:
            continue  # nothing of this copy is written yet
        low, high = float(written.min()), float(written.max())
        if high > low:
            return (low, high)
    return None


def _plane_bytes(store: Store, array) -> int:
    """What reading one plane of ``array`` decodes: every chunk the plane crosses, whole."""
    chunks = tuple(array.chunks)
    total = array.dtype.itemsize
    for index, axis in enumerate(store.axes):
        if axis.name == "z":
            total *= chunks[index]
        elif axis.name in ("y", "x"):
            total *= array.shape[index]
    return total
