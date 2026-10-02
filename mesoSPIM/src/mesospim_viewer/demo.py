"""Pretend mesoSPIM tiles, written with numpy alone, and a demo that shows them.

    python -m mesoSPIM.src.mesospim_viewer.demo            # writes tiles, opens a browser
    python -m mesoSPIM.src.mesospim_viewer.demo --no-open  # just serve, print the address
    python -m mesoSPIM.src.mesospim_viewer.demo --live     # a run being written, followed as it lands
    python -m mesoSPIM.src.mesospim_viewer.demo --live --window   # the same in the Data viewer window (Qt)

Four two-channel tiles are laid out two by two with a small overlap, each an
ordinary OME-Zarr 0.4 store (zarr v2, uncompressed chunks) carrying its stage
position as a translation. The demo places them once by that metadata and once
more shifted, to show both ways of putting a tile somewhere.
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


def live(args) -> int:
    """A folder being written into, shown as it grows."""
    import threading

    root = Path(args.folder)
    root.mkdir(parents=True, exist_ok=True)
    existing = len([p for p in root.iterdir() if p.name.endswith(".ome.zarr")])
    name = f"run_{existing:02d}"
    writer = threading.Thread(target=write_a_run, args=(root, name), daemon=True)
    if args.window:
        from .viewer import _qt
        from .window import make_window_class

        qt = _qt()
        app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication([])
        window = make_window_class()(root)
        window.resize(1200, 800)
        window.show()
        writer.start()
        return app.exec() if hasattr(app, "exec") else app.exec_()

    from .watch import Follower

    view = Viewer(port=args.port)
    follower = Follower(view, root)
    url = view.start()
    print(f"following {root} at {url}")
    if not args.no_open:
        view.open_in_browser()
    writer.start()
    try:
        while True:
            follower.poll()
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
        "--live", action="store_true", help="write a run tile by tile and follow it"
    )
    parser.add_argument(
        "--window", action="store_true", help="with --live: the Qt Data viewer window"
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
