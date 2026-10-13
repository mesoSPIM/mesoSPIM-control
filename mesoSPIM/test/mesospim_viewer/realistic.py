"""An acquisition written by the microscope's own writer, for the realistic test.

The stacks are saved with ``Live3DPyramidWriterTCZYX`` set up the way the
``MP_OME_Zarr_TCZYX_Writer`` plugin sets it up: OME-Zarr 0.5 on zarr v3,
zstd-compressed, the finest copy in slabs of 64 planes, a pyramid of coarser
copies written behind it. One tile after the other, channel by channel, frames
at a steady rate, as a run goes. Only the specimen is pretend, and small.

:func:`acquire` runs in whatever thread calls it; ``camera`` hears what
mesoSPIM-control would tell the Data viewer (``begin``, ``plane``, ``end``,
``finished``).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from mesoSPIM.src.mesospim_viewer import Stack

COLOURS = {"405": "5A73FF", "488": "00FF66", "561": "FFBF1A", "640": "FF33FF"}
GROUND = 110  # the pretend camera's background
BRIGHTEST = 3000  # ...and how far its brightest structure rises above it


def writer_available() -> str | None:
    """None when the microscope's writer can be used here, else why not."""
    try:
        import zarr  # noqa: F401

        from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP import (  # noqa: F401
            omezarr_writer,
            omezarr_writer_tczyx,
        )
    except Exception as why:  # noqa: BLE001 -- whatever keeps the writer from loading
        return f"the OME-Zarr writer could not be loaded ({why})"
    return None


class Specimen:
    """Blobs on a coarse grid, scaled up to the frame, on a noisy ground."""

    def __init__(self, seed: int, planes: int, size: int, channel: int) -> None:
        rng = np.random.default_rng(seed * 7 + channel)
        self.planes = planes
        coarse, self.keys = 32, 6
        zz, yy, xx = np.ogrid[0 : self.keys, 0:coarse, 0:coarse]
        volume = np.zeros((self.keys, coarse, coarse), np.float32)
        for _ in range(40):
            cz, cy, cx = rng.uniform([0, 0, 0], [self.keys, coarse, coarse])
            radius = rng.uniform(1.0, 3.0)
            volume += np.exp(-0.5 * (((zz - cz) / 1.2) ** 2 + ((yy - cy) / radius) ** 2 + ((xx - cx) / radius) ** 2))
        self.volume = volume * (BRIGHTEST / max(float(volume.max()), 1e-6))
        self.noise = rng.normal(0, 12, size=(4, size, size)).astype(np.float32)
        self.factor = size // coarse

    def frame(self, z: int) -> np.ndarray:
        at = z / max(1, self.planes - 1) * (self.keys - 1)
        below = int(np.floor(at))
        above = min(self.keys - 1, below + 1)
        coarse = (1 - (at - below)) * self.volume[below] + (at - below) * self.volume[above]
        picture = np.repeat(np.repeat(coarse, self.factor, axis=0), self.factor, axis=1)
        picture = picture + GROUND + self.noise[z % len(self.noise)]
        return np.clip(picture, 1, 65535).astype(np.uint16)


def write_stack(
    store: Path, *, t: int, c: int, labels, planes: int, size: int, voxel_um, origin_um, fps: float, seed: int,
    on_plane=None,
) -> None:
    """One stack through the real writer: one time point of one channel of one tile."""
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

    levels = plan_levels(size, size, planes, compute_xy_only_levels(voxel_um), min_dim=64)
    writer = Live3DPyramidWriterTCZYX(
        spec=PyramidSpec(z_size_estimate=planes, y=size, x=size, levels=levels),
        tczyx=TCZYX(
            t=t, c=c, n_channels=len(labels), channel_labels=tuple(labels),
            channel_colors=tuple(COLOURS.get(label, "") for label in labels),
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
        translation=origin_um,
        ome_version="0.5",
    )
    specimen = Specimen(seed, planes, size, c)
    began = time.time()
    for z in range(planes):
        frame = specimen.frame(z)
        writer.push_slice(frame)
        if on_plane is not None:
            on_plane(z, frame)
        wait = began + (z + 1) / fps - time.time()
        if wait > 0:
            time.sleep(wait)
    writer.close()


def acquire(
    root: Path,
    name: str = "run",
    *,
    tiles: int = 2,
    channels=("488", "561"),
    planes: int = 128,
    size: int = 256,
    fps: float = 32.0,
    voxel_um=(5.0, 1.0, 1.0),
    camera=None,
    log=None,
) -> Path:
    """Acquire a run into ``root/<name>.ome.zarr`` and return that folder.

    ``camera(what, ...)`` is called as mesoSPIM-control calls the Data viewer:
    ``("begin", Stack)`` once the writer has opened a stack's store, ``("plane",
    index, frame)`` for every frame, ``("end",)`` when the stack is acquired
    (the writer is still closing it), and ``("finished",)`` after the last.
    ``log`` is a list that hears ``(seconds since the start, what)``.
    """
    import zarr

    began = time.time()
    said = (lambda what: log.append((time.time() - began, what))) if log is not None else (lambda what: None)
    acquisition = root / f"{name}.ome.zarr"
    root.mkdir(parents=True, exist_ok=True)
    zarr.open_group(str(acquisition), mode="a", zarr_format=3)
    step = size * voxel_um[2] * 0.9
    for tile in range(tiles):
        origin = (0.0, 0.0, tile * step)
        store = acquisition / f"Mag1_Tile{tile}_Sh0_Rot0.ome.zarr"
        for c, label in enumerate(channels):
            stack = Stack(
                acquisition=name, channel=label, channels=tuple(channels), planes=planes, frame=(size, size),
                voxel_um=tuple(voxel_um), origin_um=origin, tile=f"Tile {tile + 1}", tiles=tiles,
                folder=acquisition, store=store,
            )
            first = True

            def on_plane(z, frame, stack=stack):
                nonlocal first
                if camera is None:
                    return
                if first:
                    # At the first frame, as mesoSPIM_DataViewer.Feed does: the writer has its store open.
                    camera("begin", stack)
                    first = False
                camera("plane", z, frame)

            said(f"begin tile {tile} {label}")
            write_stack(
                store, t=0, c=c, labels=channels, planes=planes, size=size, voxel_um=voxel_um, origin_um=origin,
                fps=fps, seed=tile, on_plane=on_plane,
            )
            if camera is not None:
                camera("end")
            said(f"end tile {tile} {label}")
    if camera is not None:
        camera("finished")
    said("finished")
    return acquisition
