"""The little a viewer needs to know about an OME-Zarr store, read with the
standard library only.

Neuroglancer reads the store itself; this module reads just enough of the same
metadata to *place* the store (its axes, voxel size and translation) and to
*name* its channels (the ``omero`` block, when there is one). Both OME-Zarr
generations are read: 0.4 on zarr v2 (``.zattrs``) and 0.5 on zarr v3
(``zarr.json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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

    Accepted: OME-NGFF 0.4 on zarr v2 or 0.5 on zarr v3, with exactly the five
    axes ``t, c, z, y, x`` in that order. That is the shape the acquisition
    software writes, and holding every store to it keeps the rest of the code
    free of special cases. How the arrays are chunked or sharded is not looked
    at: a chunk per time point and channel is the layout the viewer reads best.
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
        raise NotAStore(f"{root}: the store's attributes could not be read")

    ome = attrs.get("ome") if isinstance(attrs.get("ome"), dict) else attrs
    multiscales = ome.get("multiscales")
    if not isinstance(multiscales, list) or not multiscales or not isinstance(multiscales[0], dict):
        raise NotAStore(f"{root} carries no OME multiscales metadata")
    multiscale = multiscales[0]
    version = str(ome.get("version", multiscale.get("version", "")))
    if VERSIONS.get(version) != fmt:
        raise NotAStore(
            f"{root} is OME-NGFF {version or 'of no stated version'!s} on {fmt}; "
            "accepted are 0.4 on zarr v2 and 0.5 on zarr v3"
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
    if tuple(axis.name for axis in axes) != AXES:
        raise NotAStore(
            f"{root} declares axes {[axis.name for axis in axes]}; accepted is exactly {list(AXES)}"
        )
    if axes[1].type != "channel":
        raise NotAStore(f"{root}: axis c must be of type 'channel'")
    rank = len(axes)
    datasets = multiscale.get("datasets")
    if not isinstance(datasets, list) or not datasets or not isinstance(datasets[0], dict):
        raise NotAStore(f"{root}: the multiscale names no datasets")
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
        raise NotAStore(f"{root}: level {level0.get('path', '0')!s} has no readable array shape")

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
    )
