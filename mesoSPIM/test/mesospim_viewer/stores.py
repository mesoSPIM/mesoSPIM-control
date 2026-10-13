"""Pretend OME-Zarr stores for the tests, written with numpy alone.

``demo.py`` writes the tile the microscope's own writer saves (``write_tile``);
what is here are the other things a test needs: a store in any of the layouts
the viewer opens (:func:`write_store`), an acquisition's folder, a store whose
every voxel says where it is (:func:`numbered`), and a store that is written
the way the microscope writes one, a slab of planes at a time
(:class:`Slabs`).
"""

from __future__ import annotations

import functools
import json
import shutil
from pathlib import Path

import numpy as np

VOXEL_UM = (5.0, 1.0, 1.0)  # z, y, x
SHAPE = (24, 160, 160)  # z, y, x
GROUND = 400  # the camera's background in every pretend picture
PEAK = 12000  # ...and how far the brightest cell rises above it

AXES = {
    "t": {"name": "t", "type": "time", "unit": "second"},
    "c": {"name": "c", "type": "channel"},
    "z": {"name": "z", "type": "space", "unit": "micrometer"},
    "y": {"name": "y", "type": "space", "unit": "micrometer"},
    "x": {"name": "x", "type": "space", "unit": "micrometer"},
}
OMERO = {
    "488": {"label": "488", "color": "00FF66"},
    "561": {"label": "561", "color": "FF33FF"},
}


@functools.lru_cache(maxsize=32)
def cells(seed: int, timepoints: int = 1, shape: tuple[int, int, int] = SHAPE) -> np.ndarray:
    """Pretend cells in two channels on a flat ground, as uint16 shaped (t, c, z, y, x).

    Kept from one call to the next, since many tests write the same tile: read it, do not change it.
    """
    rng = np.random.default_rng(seed)
    z, y, x = shape
    zz, yy, xx = np.ogrid[0:z, 0:y, 0:x]
    volume = np.zeros((2, z, y, x), dtype=np.float32)
    for centre in rng.uniform([2, 10, 10], [z - 2, y - 10, x - 10], size=(28, 3)):
        blob = np.exp(
            -0.5 * (((zz - centre[0]) / 2.0) ** 2 + ((yy - centre[1]) / 5.0) ** 2 + ((xx - centre[2]) / 5.0) ** 2)
        )
        blob[blob < 0.05] = 0.0
        volume[0] += blob
        volume[1] += blob * rng.uniform(0.5, 1.0)
    frames = []
    for frame in range(timepoints):
        shifted = np.roll(volume, 3 * frame, axis=-1)
        out = np.empty(shifted.shape, dtype=np.uint16)
        for c in range(2):
            peak = float(shifted[c].max()) or 1.0
            out[c] = np.clip(GROUND + shifted[c] / peak * PEAK, 0, 65535).astype(np.uint16)
        frames.append(out)
    out = np.stack(frames)
    out.setflags(write=False)
    return out


def pyramid(volume: np.ndarray) -> list[np.ndarray]:
    levels = [volume]
    while min(levels[-1].shape[-2:]) >= 32:
        held = levels[-1]
        y, x = (held.shape[-2] // 2) * 2, (held.shape[-1] // 2) * 2
        trimmed = held[..., :y, :x].astype(np.float32)
        smaller = trimmed.reshape(*held.shape[:-2], y // 2, 2, x // 2, 2).mean(axis=(-3, -1))
        levels.append(smaller.astype(np.uint16))
    return levels


def array_json(shape, chunks, version: str, names: str = "", separator: str = ".") -> tuple[str, dict]:
    """The file that describes an uncompressed uint16 array, and what goes in it."""
    if version == "0.4":
        return ".zarray", {
            "zarr_format": 2,
            "shape": list(shape),
            "chunks": list(chunks),
            "dtype": "<u2",
            "compressor": None,
            "filters": None,
            "fill_value": 0,
            "order": "C",
            "dimension_separator": separator,
        }
    return "zarr.json", {
        "zarr_format": 3,
        "node_type": "array",
        "shape": list(shape),
        "data_type": "uint16",
        "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": list(chunks)}},
        "chunk_key_encoding": {"name": "default", "configuration": {"separator": "/"}},
        "fill_value": 0,
        "codecs": [{"name": "bytes", "configuration": {"endian": "little"}}],
        "dimension_names": list(names),
    }


def chunk_file(index, version: str, separator: str = ".") -> str:
    """A chunk's file below its array's folder, with ``/``."""
    if version == "0.4":
        return separator.join(str(i) for i in index)
    return "/".join(["c", *(str(i) for i in index)])


def chunk_bytes(data: np.ndarray, index, chunks) -> bytes:
    window = tuple(slice(i * c, (i + 1) * c) for i, c in zip(index, chunks))
    piece = data[window]
    if piece.shape != tuple(chunks):
        full = np.zeros(chunks, dtype=np.uint16)
        full[tuple(slice(0, n) for n in piece.shape)] = piece
        piece = full
    return piece.astype("<u2").tobytes(order="C")


def write_array(folder: Path, data: np.ndarray, chunks, version: str = "0.4", names: str = "") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    name, described = array_json(data.shape, chunks, version, names)
    (folder / name).write_text(json.dumps(described))
    counts = [-(-n // c) for n, c in zip(data.shape, chunks)]
    for index in np.ndindex(*counts):
        target = folder / chunk_file(index, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(chunk_bytes(data, index, chunks))


def group_json(path: Path, multiscale: dict, version: str, omero: dict | None) -> None:
    """The group's own description: OME-Zarr 0.4 on zarr v2, or 0.5 on zarr v3."""
    path.mkdir(parents=True, exist_ok=True)
    if version == "0.4":
        attrs = {"multiscales": [dict(multiscale, version="0.4")]}
        if omero:
            attrs["omero"] = omero
        (path / ".zgroup").write_text(json.dumps({"zarr_format": 2}))
        (path / ".zattrs").write_text(json.dumps(attrs, indent=1))
    else:
        ome = {"version": "0.5", "multiscales": [multiscale]}
        if omero:
            ome["omero"] = omero
        (path / "zarr.json").write_text(
            json.dumps({"zarr_format": 3, "node_type": "group", "attributes": {"ome": ome}}, indent=1)
        )


def dataset_json(level: int, leading: int, origin_um, voxel_um=VOXEL_UM) -> dict:
    factor = 2**level
    return {
        "path": str(level),
        "coordinateTransformations": [
            {"type": "scale", "scale": [*([1.0] * leading), voxel_um[0], voxel_um[1] * factor, voxel_um[2] * factor]},
            {"type": "translation", "translation": [*([0.0] * leading), *origin_um]},
        ],
    }


def write_store(
    path: Path,
    *,
    axes: str = "tczyx",
    version: str = "0.4",
    origin_um: tuple[float, float, float] = (0.0, 0.0, 0.0),
    seed: int = 0,
    timepoints: int = 1,
    channel: int = 0,
    omero: bool = True,
) -> Path:
    """One pretend tile with the axes given, as OME-Zarr ``version`` (0.4 or 0.5).

    ``axes`` is ``"tczyx"`` or a part of it in that order. A store without ``c``
    holds the one channel ``channel`` (0 is 488, 1 is 561) and, with ``omero``,
    says so in its omero block. The omero block names and colours the channels
    and gives no contrast window.
    """
    data = cells(seed, timepoints)
    if "t" not in axes:
        data = data[:1]
    if "c" not in axes:
        data = data[:, channel : channel + 1]
    labels = ["488", "561"] if "c" in axes else [["488", "561"][channel]]
    data = data.reshape([n for n, name in zip(data.shape, "tczyx") if name in axes])
    if path.exists():
        shutil.rmtree(path)
    leading = len(axes) - 3
    datasets = []
    for level, held in enumerate(pyramid(data)):
        chunks = (*([1] * (leading + 1)), min(64, held.shape[-2]), min(64, held.shape[-1]))
        write_array(path / str(level), held, chunks, version, axes)
        datasets.append(dataset_json(level, leading, origin_um))
    multiscale = {"name": path.name, "axes": [AXES[a] for a in axes], "datasets": datasets}
    block = {"channels": [dict(OMERO[label], active=True) for label in labels]} if omero else None
    group_json(path, multiscale, version, block)
    return path


def an_acquisition(root: Path, name: str) -> Path:
    """An acquisition the way the tczyx writer lays it out: a zarr group that holds tile stores."""
    group = root / f"{name}.ome.zarr"
    group.mkdir(parents=True)
    (group / ".zgroup").write_text('{"zarr_format": 2}')
    return group


def one_store_per_channel(acquisition: Path, *, version: str = "0.4", omero: bool = True) -> None:
    """Two tiles in two channels, one (z, y, x) store each: four stores."""
    for tile in range(2):
        for channel, laser in enumerate(["488", "561"]):
            write_store(
                acquisition / f"Mag1_Tile{tile}_Ch{laser}_Sh0_Rot0.ome.zarr",
                axes="zyx",
                version=version,
                origin_um=(0.0, 0.0, tile * 144.0),
                seed=tile,
                channel=channel,
                omero=omero,
            )


def chunk_files(store: Path) -> list[Path]:
    """Every chunk file of a store, of every copy."""
    return sorted(
        path
        for path in store.rglob("*")
        if path.is_file() and not path.name.startswith(".") and path.name != "zarr.json"
    )


def take_chunks(store: Path, wanted=lambda path: True) -> dict[Path, bytes]:
    """Take chunk files out of a store, as if they were still to be written; they
    are returned for :func:`land` to put back."""
    taken = {path: path.read_bytes() for path in chunk_files(store) if wanted(path)}
    for path in taken:
        path.unlink()
    return taken


def land(chunks: dict[Path, bytes], store: Path | None = None) -> list[str]:
    """Write chunk files back; with ``store``, return their paths below it, with ``/``."""
    for path, data in chunks.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return [path.relative_to(store).as_posix() for path in chunks] if store is not None else []


def scale_values(store: Path, factor: int) -> None:
    """Multiply every voxel of a pretend uncompressed store by ``factor``."""
    for chunk in chunk_files(store):
        data = np.frombuffer(chunk.read_bytes(), dtype="<u2") * factor
        chunk.write_bytes(data.astype("<u2").tobytes())


def numbered(path: Path) -> Path:
    """A store whose every voxel says where it is: 1000 per time point plus 200 per plane."""
    data = np.zeros((3, 1, 4, 64, 64), np.uint16)
    for t in range(3):
        for z in range(4):
            data[t, 0, z] = 1000 * (t + 1) + 200 * z
    write_array(path / "0", data, (1, 1, 1, 64, 64))
    multiscale = {
        "axes": [{"name": "t", "type": "time"}, AXES["c"], AXES["z"], AXES["y"], AXES["x"]],
        "datasets": [{"path": "0", "coordinateTransformations": [{"type": "scale", "scale": [1, 1, 1, 1, 1]}]}],
    }
    group_json(path, multiscale, "0.4", None)
    return path


class Slabs:
    """A (t, c, z, y, x) tile written the way the microscope writes one.

    The arrays are made when the first stack starts, all chunks still missing;
    then the planes of one stack -- one time point of one channel -- land a
    slab at a time: ``slab`` planes deep, and across the sensor in files of
    ``across`` pixels. One copy only, so every file is of the finest.
    """

    def __init__(
        self,
        path: Path,
        *,
        planes: int = 20,
        slab: int = 8,
        size: int = 64,
        across: int = 32,
        channels: tuple[str, ...] = ("488", "561"),
        timepoints: int = 1,
        version: str = "0.5",
        origin_um: tuple[float, float, float] = (0.0, 0.0, 0.0),
        seed: int = 0,
    ) -> None:
        self.path = path
        self.planes, self.slab, self.size, self.across = planes, slab, size, across
        self.channels = channels
        self.version = version
        self.origin_um = origin_um
        self.chunks = (1, 1, slab, across, across)
        both = cells(seed, 1, (planes, size, size))[0]
        # As many channels as asked for, taking turns between the two pretend ones.
        self.data = np.stack([both[c % 2] for c in range(len(channels))])
        self.create(timepoints)

    @property
    def shape(self) -> tuple[int, ...]:
        return (self.timepoints, len(self.channels), self.planes, self.size, self.size)

    @property
    def slabs(self) -> int:
        return -(-self.planes // self.slab)

    def create(self, timepoints: int) -> None:
        """Make the arrays, or grow them along time: metadata only."""
        self.timepoints = timepoints
        name, described = array_json(self.shape, self.chunks, self.version, "tczyx")
        (self.path / "0").mkdir(parents=True, exist_ok=True)
        (self.path / "0" / name).write_text(json.dumps(described))
        multiscale = {
            "name": self.path.name,
            "axes": [AXES[a] for a in "tczyx"],
            "datasets": [dataset_json(0, 2, self.origin_um)],
        }
        omero = {"channels": [{"label": label, "color": "00FF66", "active": True} for label in self.channels]}
        group_json(self.path, multiscale, self.version, omero)

    def files(self, slab: int, *, t: int = 0, c: int = 0) -> list[str]:
        """The files of one slab of one stack, as paths below the store with ``/``."""
        count = -(-self.size // self.across)
        return [
            "0/" + chunk_file((t, c, slab, y, x), self.version)
            for y in range(count)
            for x in range(count)
        ]

    def write(self, slab: int, *, t: int = 0, c: int = 0, only: int | None = None, skip: int = 0) -> list[str]:
        """Land one slab of one stack and return its files: all of them, or only the
        first ``only``, or all but the first ``skip`` (which landed before)."""
        written = self.files(slab, t=t, c=c)[skip:only]
        for file in written:
            parts = file.replace(".", "/").split("/")
            y, x = int(parts[-2]), int(parts[-1])
            data = chunk_bytes(self.data[c][None, None], (0, 0, slab, y, x), self.chunks)
            target = self.path / file
            target.parent.mkdir(parents=True, exist_ok=True)
            # Under another name first, as zarr does: a reader never sees half a file.
            partial = target.with_name(target.name + ".partial")
            partial.write_bytes(data)
            partial.replace(target)
        return written

    def write_stack(self, *, t: int = 0, c: int = 0) -> list[str]:
        return [file for slab in range(self.slabs) for file in self.write(slab, t=t, c=c)]
