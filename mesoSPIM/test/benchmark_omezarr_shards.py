"""
How fast the live OME-Zarr pipeline writes with shards written at once, with no shards,
and with shards written in several parts.

    python -m mesoSPIM.test.benchmark_omezarr_shards [folder] [--planes N] [--yx 2048]

Writes one (t, c, z, y, x) stack per configuration through Live3DPyramidWriter (the same
code the MP writers run in their writer process) and prints MB/s and the number of files.
The stack is a smooth pattern with noise, so compression has something to do.

The point being measured: a shard is one file holding many chunks. A write that covers a
whole shard produces it in one go; a write that covers part of one makes zarr read the
shard back, merge, and rewrite it. The live pipeline writes one z-chunk over the full
sensor per assignment, so a shard exactly one chunk deep is one write and a deeper one is
several. The tczyx writer refuses the deeper shape; this shows why.
"""
import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP import omezarr_writer as ow
from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import (
    BloscCodec, BloscShuffle, ChunkScheme, FlushPad, PyramidSpec, compute_xy_only_levels, plan_levels,
)
from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer_tczyx import (
    TCZYX, Live3DPyramidWriterTCZYX,
)


def planes_like_a_specimen(n: int, yx: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:yx, 0:yx]
    field = (np.sin(y / 37.0) * np.cos(x / 53.0) + 1.0) * 6000.0
    for z in range(n):
        plane = field * (0.5 + 0.5 * np.sin(z / 9.0)) + rng.integers(0, 400, (yx, yx))
        yield np.clip(plane, 0, 65535).astype(np.uint16)


def run(folder: Path, planes: int, yx: int, chunk_z: int, shards, label: str) -> dict:
    ow.VERBOSE = False
    path = folder / f"{label}.ome.zarr"
    if path.exists():
        shutil.rmtree(path)
    voxel = (5.0, 1.0, 1.0)
    levels = plan_levels(yx, yx, planes, compute_xy_only_levels(voxel), min_dim=64)
    spec = PyramidSpec(z_size_estimate=planes, y=yx, x=yx, levels=levels)
    compressor = BloscCodec(cname="zstd", clevel=5, shuffle=BloscShuffle.bitshuffle)
    frames = list(planes_like_a_specimen(planes, yx))  # generated before the clock starts
    started = time.perf_counter()
    writer = Live3DPyramidWriterTCZYX(
        spec, TCZYX(t=0, c=0, n_channels=1, channel_labels=("488",)),
        voxel_size=voxel, path=str(path), max_workers=2, max_inflight_chunks=8,
        chunk_scheme=ChunkScheme(base=(chunk_z, 256, 256), target=(chunk_z, 64, 64)),
        compressor=compressor, shard_shape=shards, flush_pad=FlushPad.DUPLICATE_LAST,
        async_close=False, ome_version="0.5",
    )
    for frame in frames:
        writer.push_slice(frame)
    writer.close()
    seconds = time.perf_counter() - started
    megabytes = planes * yx * yx * 2 / 1e6
    files = sum(1 for p in path.rglob("*") if p.is_file())
    return {"label": label, "seconds": seconds, "MB/s": megabytes / seconds, "files": files}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", nargs="?", default=None, help="where to write (a temporary folder by default)")
    parser.add_argument("--planes", type=int, default=128)
    parser.add_argument("--yx", type=int, default=2048)
    parser.add_argument("--chunk-z", type=int, default=32)
    args = parser.parse_args(argv)
    folder = Path(args.folder) if args.folder else Path(tempfile.mkdtemp(prefix="omezarr-bench-"))
    z = args.chunk_z
    configurations = [
        ("no shards, one file per chunk", None),
        ("shards one chunk deep, written at once", (z, args.yx, args.yx)),
        (f"shards {2 * z} deep, written in two parts", (2 * z, args.yx, args.yx)),
    ]
    print(f"{args.planes} planes of {args.yx}x{args.yx} uint16, chunk z={z}, zstd-5, into {folder}")
    results = []
    for label, shards in configurations:
        # a deeper shard needs a chunk scheme whose z stays at chunk_z so the shard spans two chunks
        result = run(folder, args.planes, args.yx, z, shards, label.split(",")[0].replace(" ", "_"))
        result["label"] = label
        results.append(result)
        print(f"  {label:45s} {result['seconds']:7.2f} s  {result['MB/s']:7.1f} MB/s  {result['files']:6d} files")
    if not args.folder:
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
