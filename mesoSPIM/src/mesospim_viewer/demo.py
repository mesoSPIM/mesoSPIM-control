"""Pretend mesoSPIM data, and demos that show it.

    python -m mesoSPIM.src.mesospim_viewer.demo            # four small tiles in a browser
    python -m mesoSPIM.src.mesospim_viewer.demo --no-open  # just serve, print the address
    python -m mesoSPIM.src.mesospim_viewer.demo --live     # a run being acquired, followed live
    python -m mesoSPIM.src.mesospim_viewer.demo --live --window    # the same in the Data viewer window (Qt)
    python -m mesoSPIM.src.mesospim_viewer.demo --live --from-disk # followed from disk alone, without the camera's frames

The plain demo writes four two-channel tiles with numpy alone, two by two with
a small overlap, each an ordinary OME-Zarr 0.4 store (zarr v2, uncompressed
chunks) carrying its stage position as a translation, and shows them placed by
that metadata and once more shifted.

The live demo is a rehearsal of a real run. It writes with the microscope's
own writer -- the pipeline of the ``MP_OME_Zarr_TCZYX_Writer``: zarr v3, zstd,
slabs of 64 planes, the pyramid built as it goes -- frame by frame at a camera's
pace, and hands the viewer the frames the way mesoSPIM-control does. What is on
screen is then what the operator will see at the microscope, including how
late the disk is compared with the camera (``--from-disk`` shows that alone).
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from .viewer import Viewer

VOXEL_UM = (5.0, 1.0, 1.0)  # z, y, x
TILE = (24, 160, 160)  # z, y, x voxels
OVERLAP_UM = 16.0


def _pyramid(volume):
    import numpy as np

    levels = [volume]
    while min(levels[-1].shape[-2:]) >= 32:
        held = levels[-1]
        y, x = (held.shape[-2] // 2) * 2, (held.shape[-1] // 2) * 2
        trimmed = held[..., :y, :x].astype(np.float32)
        smaller = trimmed.reshape(*held.shape[:-2], y // 2, 2, x // 2, 2).mean(axis=(-3, -1))
        levels.append(smaller.astype(np.uint16))
    return levels


def _write_array(folder: Path, data, chunk_shape) -> None:
    """A zarr v2 array with no compression: one file per chunk, C order."""
    import numpy as np

    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".zarray").write_text(
        json.dumps(
            {
                "zarr_format": 2,
                "shape": list(data.shape),
                "chunks": list(chunk_shape),
                "dtype": "<u2",
                "compressor": None,
                "filters": None,
                "fill_value": 0,
                "order": "C",
                "dimension_separator": ".",
            }
        )
    )
    counts = [-(-n // c) for n, c in zip(data.shape, chunk_shape, strict=True)]
    for index in np.ndindex(*counts):
        window = tuple(slice(i * c, (i + 1) * c) for i, c in zip(index, chunk_shape, strict=True))
        piece = data[window]
        if piece.shape != tuple(chunk_shape):
            full = np.zeros(chunk_shape, dtype=np.uint16)
            full[tuple(slice(0, n) for n in piece.shape)] = piece
            piece = full
        (folder / ".".join(str(i) for i in index)).write_bytes(
            piece.astype("<u2").tobytes(order="C")
        )


def _cells(seed: int, timepoints: int):
    """Pretend cells in two channels, as uint16 shaped (t, c, z, y, x)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    z, y, x = TILE
    zz, yy, xx = np.ogrid[0:z, 0:y, 0:x]
    volume = np.zeros((2, z, y, x), dtype=np.float32)
    for centre in rng.uniform([2, 10, 10], [z - 2, y - 10, x - 10], size=(28, 3)):
        blob = np.exp(
            -0.5
            * (
                ((zz - centre[0]) / 2.0) ** 2
                + ((yy - centre[1]) / 5.0) ** 2
                + ((xx - centre[2]) / 5.0) ** 2
            )
        )
        blob[blob < 0.05] = 0.0  # no tails: the ground between cells stays at the background
        volume[0] += blob
        if rng.random() < 0.5:
            volume[1] += blob * rng.uniform(0.5, 1.0)
    frames = []
    for frame in range(timepoints):
        shifted = np.roll(volume, 3 * frame, axis=-1)
        out = np.empty_like(shifted, dtype=np.uint16)
        for c in range(2):
            peak = float(shifted[c].max()) or 1.0
            out[c] = np.clip(400 + shifted[c] / peak * 12000, 0, 65535).astype(np.uint16)
        frames.append(out)
    return np.stack(frames)


def _write_array_v3(folder: Path, data, chunk_shape, names) -> None:
    """A zarr v3 array with no compression: one file per chunk under ``c/``, C order."""
    import numpy as np

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "zarr.json").write_text(
        json.dumps(
            {
                "zarr_format": 3,
                "node_type": "array",
                "shape": list(data.shape),
                "data_type": "uint16",
                "chunk_grid": {
                    "name": "regular",
                    "configuration": {"chunk_shape": list(chunk_shape)},
                },
                "chunk_key_encoding": {"name": "default", "configuration": {"separator": "/"}},
                "fill_value": 0,
                "codecs": [{"name": "bytes", "configuration": {"endian": "little"}}],
                "dimension_names": list(names),
            }
        )
    )
    counts = [-(-n // c) for n, c in zip(data.shape, chunk_shape, strict=True)]
    for index in np.ndindex(*counts):
        window = tuple(slice(i * c, (i + 1) * c) for i, c in zip(index, chunk_shape, strict=True))
        piece = data[window]
        if piece.shape != tuple(chunk_shape):
            full = np.zeros(chunk_shape, dtype=np.uint16)
            full[tuple(slice(0, n) for n in piece.shape)] = piece
            piece = full
        chunk = folder.joinpath("c", *(str(i) for i in index))
        chunk.parent.mkdir(parents=True, exist_ok=True)
        chunk.write_bytes(piece.astype("<u2").tobytes(order="C"))


_AXIS_JSON = {
    "t": {"name": "t", "type": "time", "unit": "second"},
    "c": {"name": "c", "type": "channel"},
    "z": {"name": "z", "type": "space", "unit": "micrometer"},
    "y": {"name": "y", "type": "space", "unit": "micrometer"},
    "x": {"name": "x", "type": "space", "unit": "micrometer"},
}
_OMERO = {
    "488": {"label": "488", "color": "00FF66"},
    "561": {"label": "561", "color": "FF33FF"},
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

    ``axes`` is ``"tczyx"`` or a part of it in that order, such as ``"zyx"`` or
    ``"czyx"``. A store without ``c`` holds the one channel ``channel`` (0 is 488,
    1 is 561), and with ``omero`` says so in its omero block, as a writer saving
    one store per tile and channel should. Without ``t`` it holds the first time
    point. 0.4 is written on zarr v2, 0.5 on zarr v3.
    """
    if version not in ("0.4", "0.5"):
        raise ValueError("version must be 0.4 or 0.5")
    data = _cells(seed, timepoints)
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
    for level, held in enumerate(_pyramid(data)):
        factor = 2**level
        chunks = (*([1] * (leading + 1)), min(64, held.shape[-2]), min(64, held.shape[-1]))
        if version == "0.4":
            _write_array(path / str(level), held, chunks)
        else:
            _write_array_v3(path / str(level), held, chunks, axes)
        datasets.append(
            {
                "path": str(level),
                "coordinateTransformations": [
                    {
                        "type": "scale",
                        "scale": [
                            *([1.0] * leading),
                            VOXEL_UM[0],
                            VOXEL_UM[1] * factor,
                            VOXEL_UM[2] * factor,
                        ],
                    },
                    {"type": "translation", "translation": [*([0.0] * leading), *origin_um]},
                ],
            }
        )
    multiscale = {"name": path.name, "axes": [_AXIS_JSON[a] for a in axes], "datasets": datasets}
    block = {"channels": [dict(_OMERO[label], active=True) for label in labels]}
    if version == "0.4":
        attrs = {"multiscales": [dict(multiscale, version="0.4")]}
        if omero:
            attrs["omero"] = block
        (path / ".zgroup").write_text(json.dumps({"zarr_format": 2}))
        (path / ".zattrs").write_text(json.dumps(attrs, indent=1))
    else:
        ome = {"version": "0.5", "multiscales": [multiscale]}
        if omero:
            ome["omero"] = block
        (path / "zarr.json").write_text(
            json.dumps(
                {"zarr_format": 3, "node_type": "group", "attributes": {"ome": ome}}, indent=1
            )
        )
    return path


def write_tile(
    path: Path, *, origin_um: tuple[float, float, float], seed: int, timepoints: int = 1
) -> Path:
    """One two-channel tile at ``origin_um`` (z, y, x), as OME-Zarr 0.4 with axes t, c, z, y, x.

    With ``timepoints`` above one the cells drift a little from frame to frame,
    which is what a time slider needs to show anything.
    """
    out = _cells(seed, timepoints)  # t, c, z, y, x

    if path.exists():
        shutil.rmtree(path)
    levels = _pyramid(out)
    datasets = []
    for level, data in enumerate(levels):
        factor = 2**level
        # One chunk per time point, channel and plane: the layout the writer uses.
        _write_array(
            path / str(level), data, (1, 1, 1, min(64, data.shape[-2]), min(64, data.shape[-1]))
        )
        datasets.append(
            {
                "path": str(level),
                "coordinateTransformations": [
                    {
                        "type": "scale",
                        "scale": [
                            1.0,
                            1.0,
                            VOXEL_UM[0],
                            VOXEL_UM[1] * factor,
                            VOXEL_UM[2] * factor,
                        ],
                    },
                    {"type": "translation", "translation": [0.0, 0.0, *origin_um]},
                ],
            }
        )
    (path / ".zgroup").write_text(json.dumps({"zarr_format": 2}))
    (path / ".zattrs").write_text(
        json.dumps(
            {
                "multiscales": [
                    {
                        "version": "0.4",
                        "name": path.name,
                        "axes": [
                            {"name": "t", "type": "time", "unit": "second"},
                            {"name": "c", "type": "channel"},
                            {"name": "z", "type": "space", "unit": "micrometer"},
                            {"name": "y", "type": "space", "unit": "micrometer"},
                            {"name": "x", "type": "space", "unit": "micrometer"},
                        ],
                        "datasets": datasets,
                    }
                ],
                "omero": {
                    "channels": [
                        {
                            "label": "488",
                            "color": "00FF66",
                            "active": True,
                            "window": {"min": 0, "max": 65535, "start": 380, "end": 12400},
                        },
                        {
                            "label": "561",
                            "color": "FF33FF",
                            "active": True,
                            "window": {"min": 0, "max": 65535, "start": 380, "end": 12400},
                        },
                    ]
                },
            },
            indent=1,
        )
    )
    return path


def write_tiles(folder: Path, *, across: int = 2, down: int = 2) -> list[Path]:
    """A grid of tiles, each placed by its own metadata, overlapping a little."""
    folder.mkdir(parents=True, exist_ok=True)
    step_y = TILE[1] * VOXEL_UM[1] - OVERLAP_UM
    step_x = TILE[2] * VOXEL_UM[2] - OVERLAP_UM
    tiles = []
    for row in range(down):
        for column in range(across):
            seed = row * across + column
            tiles.append(
                write_tile(
                    folder / f"tile_{row}{column}.ome.zarr",
                    origin_um=(0.0, row * step_y, column * step_x),
                    seed=seed,
                )
            )
    return tiles


def write_a_run(
    root: Path, name: str, *, tiles: int = 4, timepoints: int = 2, pause_s: float = 2.0
) -> None:
    """Write an acquisition the way the microscope does: tile by tile, then time point by
    time point appended to every tile, with a pause between stacks."""
    group = root / f"{name}.ome.zarr"
    group.mkdir(parents=True, exist_ok=True)
    (group / ".zgroup").write_text(json.dumps({"zarr_format": 2}))
    step_y = TILE[1] * VOXEL_UM[1] - OVERLAP_UM
    step_x = TILE[2] * VOXEL_UM[2] - OVERLAP_UM
    for t in range(1, timepoints + 1):
        for tile in range(tiles):
            row, column = divmod(tile, 2)
            write_tile(
                group / f"Mag1_Tile{tile}_Sh0_Rot0.ome.zarr",
                origin_um=(0.0, row * step_y, column * step_x),
                seed=tile,
                timepoints=t,
            )
            print(f"  wrote {name} tile {tile} time point {t - 1}")
            time.sleep(pause_s)


# -- a run the way the microscope does it ------------------------------------------------


class _Specimen:
    """A cheap pretend specimen: blobs on a coarse grid, enlarged for each frame, plus
    camera noise on a camera's offset."""

    def __init__(self, seed: int, planes: int, size: int, channel: int) -> None:
        import numpy as np

        rng = np.random.default_rng(seed * 7 + channel)
        coarse, keys = 64, 10
        zz, yy, xx = np.ogrid[0:keys, 0:coarse, 0:coarse]
        volume = np.zeros((keys, coarse, coarse), np.float32)
        for _ in range(60):
            cz, cy, cx = rng.uniform([0, 0, 0], [keys, coarse, coarse])
            radius = rng.uniform(1.0, 3.5)
            volume += np.exp(
                -0.5 * (((zz - cz) / 1.2) ** 2 + ((yy - cy) / radius) ** 2 + ((xx - cx) / radius) ** 2)
            )
        self.volume = volume * (3000.0 / max(float(volume.max()), 1e-6))
        self.planes, self.keys, self.factor = planes, keys, max(1, size // coarse)
        self.noise = rng.normal(0, 12, size=(4, size, size)).astype(np.float32)
        self.size = size

    def frame(self, z: int):
        import numpy as np

        at = z / max(1, self.planes - 1) * (self.keys - 1)
        below = int(np.floor(at))
        above = min(self.keys - 1, below + 1)
        coarse = (1 - (at - below)) * self.volume[below] + (at - below) * self.volume[above]
        image = np.repeat(np.repeat(coarse, self.factor, axis=0), self.factor, axis=1)
        image = image[: self.size, : self.size] + 110.0 + self.noise[z % len(self.noise)]
        return np.clip(image, 0, 65535).astype(np.uint16)


def acquire(
    root: Path,
    name: str,
    *,
    feed=None,
    tiles: tuple[int, int] = (2, 2),
    channels: tuple[str, ...] = ("488", "561"),
    planes: int = 128,
    size: int = 512,
    frames_per_s: float = 20.0,
    voxel_um: tuple[float, float, float] = (5.0, 1.0, 1.0),
    say=print,
) -> Path:
    """Write an acquisition the way the microscope does, and return its folder.

    Stack after stack -- tile by tile, channel by channel -- frames are pushed at
    ``frames_per_s`` into the writer the ``MP_OME_Zarr_TCZYX_Writer`` uses, set up
    as that plugin sets it up. ``feed`` is told what mesoSPIM-control tells the
    Data viewer: ``begin_stack``, ``add_plane`` for every other frame,
    ``end_stack``, and ``end_run`` (a :class:`~.watch.Library`, or the window).
    """
    import zarr

    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import (
        BloscCodec,
        BloscShuffle,
        ChunkScheme,
        FlushPad,
        PyramidSpec,
        compute_xy_only_levels,
        plan_levels,
    )
    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer_tczyx import (
        TCZYX,
        Live3DPyramidWriterTCZYX,
    )

    from .live import Stack
    from .state import WAVELENGTH_COLOURS

    root.mkdir(parents=True, exist_ok=True)
    folder = root / f"{name}.ome.zarr"
    zarr.open_group(str(folder), mode="a", zarr_format=3)
    rows, columns = tiles
    step = size * voxel_um[2] * 0.9  # a tenth of overlap
    for tile in range(rows * columns):
        row, column = divmod(tile, columns)
        origin = (0.0, row * step, column * step)
        store = folder / f"Mag1_Tile{tile}_Sh0_Rot0.ome.zarr"
        for index, channel in enumerate(channels):
            writer = Live3DPyramidWriterTCZYX(
                spec=PyramidSpec(
                    z_size_estimate=planes,
                    y=size,
                    x=size,
                    levels=plan_levels(size, size, planes, compute_xy_only_levels(voxel_um), min_dim=64),
                ),
                tczyx=TCZYX(
                    t=0,
                    c=index,
                    n_channels=len(channels),
                    channel_labels=tuple(channels),
                    channel_colors=tuple(
                        WAVELENGTH_COLOURS.get(label, "#ffffff").lstrip("#").upper() for label in channels
                    ),
                ),
                voxel_size=voxel_um,
                path=str(store),
                ingest_queue_size=256,
                max_workers=2,
                max_inflight_chunks=8,
                chunk_scheme=ChunkScheme(base=(64, 256, 256), target=(64, 64, 64)),
                compressor=BloscCodec(cname="zstd", clevel=5, shuffle=BloscShuffle.bitshuffle),
                shard_shape=None,
                flush_pad=FlushPad.DUPLICATE_LAST,
                async_close=False,
                translation=origin,
                ome_version="0.5",
            )
            if feed is not None:
                feed.begin_stack(
                    Stack(
                        acquisition=name,
                        channel=channel,
                        channels=tuple(channels),
                        planes=planes,
                        frame=(size, size),
                        voxel_um=voxel_um,
                        origin_um=origin,
                        tile=f"Tile {tile + 1}",
                        tiles=rows * columns,
                        folder=folder,
                        store=store,
                    )
                )
            specimen = _Specimen(tile, planes, size, index)
            began = time.time()
            for z in range(planes):
                frame = specimen.frame(z)
                writer.push_slice(frame)
                if feed is not None and z % 2 == 0:
                    feed.add_plane(z, frame)
                wait = began + (z + 1) / frames_per_s - time.time()
                if wait > 0:
                    time.sleep(wait)
            if feed is not None:
                feed.end_stack()
            writer.close()
            say(f"  acquired {name}, tile {tile + 1} of {rows * columns}, {channel}")
    if feed is not None:
        feed.end_run()
    return folder


def live(args) -> int:
    """A folder being acquired into, shown as it grows."""
    import threading

    root = Path(args.folder)
    root.mkdir(parents=True, exist_ok=True)
    existing = len([p for p in root.iterdir() if p.name.endswith(".ome.zarr")])
    name = f"run_{existing:02d}"

    if args.window:
        from .viewer import _qt
        from .window import make_window_class

        qt = _qt()
        app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication([])
        window = make_window_class()(root)
        window.resize(1280, 820)
        window.show()
        feed = None if args.from_disk else window
        threading.Thread(target=acquire, args=(root, name), kwargs={"feed": feed}, daemon=True).start()
        return app.exec() if hasattr(app, "exec") else app.exec_()

    from .watch import Library

    view = Viewer(port=args.port, ui=args.ui)
    library = Library(view)
    library.watch(root)
    url = view.start()
    print(f"following {root} at {url}")
    if not args.no_open:
        view.open_in_browser()
    feed = None if args.from_disk else library
    threading.Thread(target=acquire, args=(root, name), kwargs={"feed": feed}, daemon=True).start()
    try:
        while True:
            library.poll()
            time.sleep(1.0)
    except KeyboardInterrupt:
        view.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--folder", default="testdata/mesospim_demo", help="where the tiles are written"
    )
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    parser.add_argument("--transparent", action="store_true", help="transparent 2D ground")
    parser.add_argument("--ui", choices=("full", "simple", "bare"), default="simple")
    parser.add_argument(
        "--live",
        action="store_true",
        help="acquire a run with the microscope's own writer and follow it as mesoSPIM-control would",
    )
    parser.add_argument(
        "--window", action="store_true", help="with --live: the Qt Data viewer window"
    )
    parser.add_argument(
        "--from-disk",
        action="store_true",
        help="with --live: follow the run from disk alone, without the camera's frames",
    )
    args = parser.parse_args(argv)
    if args.live:
        return live(args)

    folder = Path(args.folder)
    tiles = write_tiles(folder)
    view = Viewer(port=args.port, transparent=args.transparent, ui=args.ui)
    for tile in tiles:
        view.add(tile, layer="overview")
    # The same tiles again, shifted aside, as a second acquisition placed by hand.
    shift = TILE[2] * VOXEL_UM[2] * 2 + 200
    for tile in tiles:
        view.add(tile, layer="shifted copy", offset={"x": shift}, colours=["#33ccff", "#ffbf1a"])
    view.set_visible("shifted copy", False)
    view.fit()
    url = view.start()
    if not view.page_built:
        print("the page is not built: run `npm ci && npm run build` in mesoSPIM/src/mesospim_viewer/source first")
    print(f"serving {len(tiles)} tiles at {url}")
    if not args.no_open:
        view.open_in_browser()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        view.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
