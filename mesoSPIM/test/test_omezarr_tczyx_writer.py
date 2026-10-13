"""
The MP_OME_Zarr_TCZYX_Writer: one (t, c, z, y, x) store per tile, channels along c,
time points appended along t, no chunk or shard ever spanning either.

Run from the repository root:
    python -m pytest mesoSPIM/test/test_omezarr_tczyx_writer.py

Needs numpy, zarr>=3, psutil and indexed (what the writer itself needs); no Qt, no hardware.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

zarr = pytest.importorskip("zarr")

from mesoSPIM.src.plugins.ImageWriterApi import WriteRequest, WriteImage, FinalizeImage
from mesoSPIM.src.plugins.ImageWriters.OmeZarrWriterMPTCZYX import OMEZarrWriterMPTCZYX
from mesoSPIM.src.utils.acquisitions import Acquisition, AcquisitionList

PLANES, Y, X = 20, 256, 192         # small, but big enough for a second pyramid level; frames arrive as (X, Y)
# The writers store a frame as it arrives: the store's y is the request's X and its x the request's Y
# (see 'Z_EST, Y, X = (req.shape[0], req.shape[2], req.shape[1])' in the MP writer).
LASERS = ('488 nm', '561 nm')
TILES = ((100.0, 200.0), (100.0, 296.0))   # (x_pos, y_pos) in um


def acquisition_list(folder: Path, time_index: int) -> AcquisitionList:
    acqs = []
    for x_pos, y_pos in TILES:
        for laser in LASERS:
            acqs.append(Acquisition(
                x_pos=x_pos, y_pos=y_pos, z_start=10.0, z_end=10.0 + 5.0 * (PLANES - 1), z_step=5.0,
                planes=PLANES, laser=laser, filter='Empty', zoom='1x', shutterconfig='Left',
                folder=str(folder), filename=f'Sample.ome_Time{time_index:03d}.zarr',  # as mesoSPIM names a time point
                image_writer_plugin=OMEZarrWriterMPTCZYX.name(),
            ))
    return AcquisitionList(acqs)


def frame(t: int, c: int, tile: int, z: int) -> np.ndarray:
    """A plane whose values say where it belongs."""
    value = 1000 * t + 100 * c + 10 * tile + z
    return np.full((X, Y), value, dtype=np.uint16)


def write_time_point(folder: Path, time_index: int, config: dict) -> None:
    """Drive the plugin the way mesoSPIM_ImageWriter does: a fresh writer per time point,
    open/write_frame/finalize per stack."""
    acq_list = acquisition_list(folder, time_index)
    writer = OMEZarrWriterMPTCZYX()
    for acq in acq_list:
        tile = acq_list.get_tile_index(acq)
        c = acq_list.find_value_index(acq['laser'], 'laser')
        req = WriteRequest(
            uri=os.path.join(acq['folder'], acq['filename']),
            shape=(PLANES, Y, X), dtype='uint16', axes='ZYX',
            x_res=1.0, y_res=1.0, z_res=5.0, unit='microns',
            num_tiles=acq_list.get_n_tiles(), num_channels=acq_list.get_n_lasers(),
            num_rotations=acq_list.get_n_angles(), num_shutters=acq_list.get_n_shutter_configs(),
            acq=acq, acq_list=acq_list, writer_config_file_values=config,
        )
        writer.open(req)
        for z in range(PLANES):
            writer.write_frame(WriteImage(
                image=frame(time_index, c, tile, z), current_image_counter=z, tile_number=tile,
                laser=acq['laser'], shutter=acq['shutterconfig'], rot=acq['rot'],
                x_res=1.0, y_res=1.0, z_res=5.0, acq=acq, acq_list=acq_list,
            ))
        writer.finalize(FinalizeImage(acq=acq, acq_list=acq_list))


def files_under(root: Path) -> dict:
    return {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob('*') if p.is_file()}


@pytest.mark.xfail(
    sys.platform == "win32", strict=False,
    reason="OmeZarrWriterMP.finalize closes the parent's shared-memory handle before the writer "
           "process has attached; on Windows the block then no longer exists ('wnsm_...' not found). "
           "Stacks this short finish before the process starts.",
)
@pytest.mark.parametrize("config", [
    pytest.param({'ome_version': '0.5', 'shards': None, 'base_chunks': (8, 64, 64), 'target_chunks': (8, 32, 32)}, id="v3-chunks"),
    pytest.param({'ome_version': '0.5', 'shards': (8, 192, 256), 'base_chunks': (8, 64, 64), 'target_chunks': (8, 32, 32)}, id="v3-shards"),
    pytest.param({'ome_version': '0.4', 'base_chunks': (8, 64, 64), 'target_chunks': (8, 32, 32)}, id="v2"),
])
def test_two_time_points_of_two_tiles_and_channels(tmp_path, config):
    write_time_point(tmp_path, 0, config)
    acquisition = tmp_path / 'Sample.ome.zarr'
    stores = sorted(p.name for p in acquisition.iterdir() if p.is_dir())
    assert stores == ['Mag1_Tile0_Sh0_Rot0.ome.zarr', 'Mag1_Tile1_Sh0_Rot0.ome.zarr']
    assert not list(tmp_path.glob('*Time*')), "the time mark never reaches the disk"

    before = files_under(acquisition)
    write_time_point(tmp_path, 1, config)
    after = files_under(acquisition)

    # Appending a time point only adds files: nothing written for t=0 is touched again,
    # which is what keeps every shard a single write.
    rewritten = [name for name, stamp in before.items() if after.get(name) != stamp and not name.endswith(('zarr.json', '.zarray', '.zattrs', '.zgroup'))]
    assert rewritten == [], rewritten
    assert len(after) > len(before)

    v2 = config['ome_version'] == '0.4'
    for tile, store in enumerate(stores):
        root = zarr.open_group(acquisition / store, mode='r')
        attrs = dict(root.attrs)
        ome = attrs if v2 else attrs['ome']
        multiscale = ome['multiscales'][0]
        assert (multiscale.get('version') if v2 else ome['version']) == config['ome_version']
        assert [axis['name'] for axis in multiscale['axes']] == ['t', 'c', 'z', 'y', 'x']
        assert multiscale['axes'][1]['type'] == 'channel'
        transforms = multiscale['datasets'][0]['coordinateTransformations']
        assert transforms[0]['scale'] == [1.0, 1.0, 5.0, 1.0, 1.0]
        assert transforms[1]['translation'] == [0.0, 0.0, 10.0, TILES[tile][1], TILES[tile][0]]
        assert [channel['label'] for channel in ome['omero']['channels']] == ['488', '561']
        assert ome['omero']['channels'][0]['color'] == '00FF66'

        level0 = root['0']
        assert level0.shape == (2, 2, PLANES, X, Y)
        assert level0.chunks[:2] == (1, 1)
        if config.get('shards'):
            assert level0.shards[:2] == (1, 1)
            assert level0.shards[2] == level0.chunks[2], "a shard is one z-chunk deep: one write"
        for t in range(2):
            for c in range(2):
                expected = np.stack([frame(t, c, tile, z) for z in range(PLANES)])
                assert np.array_equal(level0[t, c], expected), (tile, t, c)
        level1 = root['1']
        assert level1.shape[:2] == (2, 2) and level1.chunks[:2] == (1, 1)
        assert level1[1, 1].max() > 0, "the coarser level was written for the last stack too"


def test_the_time_suffix_is_read_and_stripped():
    split = OMEZarrWriterMPTCZYX.split_time_index
    # mesoSPIM's own placing of the mark, before the last suffix
    assert split('/data/run/Sample.ome_Time003.zarr') == ('/data/run/Sample.ome.zarr', 3)
    assert split('/data/run/Sample.ome.zarr') == ('/data/run/Sample.ome.zarr', 0)
    assert split('/data/run/Sample_Time003.ome.zarr') == ('/data/run/Sample.ome.zarr', 3)
    assert split(r'C:\data\run\Sample.ome_Time012.zarr') == (r'C:\data\run\Sample.ome.zarr', 12)
    assert OMEZarrWriterMPTCZYX.channel_label('488 nm') == '488'


def test_a_shard_deeper_than_a_chunk_is_refused(tmp_path):
    acq_list = acquisition_list(tmp_path, 0)
    acq = acq_list[0]
    req = WriteRequest(
        uri=os.path.join(acq['folder'], acq['filename']), shape=(PLANES, Y, X), dtype='uint16', axes='ZYX',
        x_res=1.0, y_res=1.0, z_res=5.0, num_tiles=2, num_channels=2, num_rotations=1, num_shutters=1,
        acq=acq, acq_list=acq_list,
        writer_config_file_values={'shards': (16, 192, 256), 'base_chunks': (8, 64, 64), 'target_chunks': (8, 32, 32)},
    )
    with pytest.raises(ValueError, match="one z-chunk deep"):
        OMEZarrWriterMPTCZYX().open(req)


def test_the_plugin_registers_beside_the_mp_writer():
    from mesoSPIM.src.plugins.ImageWriterApi import ImageWriter
    assert isinstance(OMEZarrWriterMPTCZYX(), ImageWriter)
    assert OMEZarrWriterMPTCZYX.name() == 'MP_OME_Zarr_TCZYX_Writer'
    assert OMEZarrWriterMPTCZYX.file_names().IncludeChannel is False


def test_the_fast_shard_writer_puts_a_stack_at_its_time_point_and_channel(tmp_path):
    """The fast writer compresses and writes whole shards itself, which is what lets the
    microscope save sharded OME-Zarr at full speed. A tczyx store holds one stack per time
    point and channel, so the writer has to put each shard there and nowhere else."""
    from zarr.codecs import BloscCodec
    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import FastShardWriter

    root = zarr.open_group(str(tmp_path / "tile.ome.zarr"), mode="w", zarr_format=3)
    array = root.create_array(
        name="0", shape=(2, 2, 8, 40, 24), chunks=(1, 1, 4, 16, 16), shards=(1, 1, 8, 32, 32),
        dtype="uint16", compressors=[BloscCodec(cname="zstd", clevel=5)],
    )
    writer = FastShardWriter.for_array(array, lead=(1, 0))
    assert writer is not None, "a sharded, compressed tczyx array takes the fast path"
    assert writer.can_write(0, 8) and not writer.can_write(0, 4)

    stack = np.arange(8 * 40 * 24, dtype=np.uint16).reshape(8, 40, 24)
    writer.write(0, stack)

    assert np.array_equal(array[1, 0], stack), "the stack is read back where it was written"
    for t, c in ((0, 0), (0, 1), (1, 1)):
        assert not array[t, c].any(), f"time point {t}, channel {c} is left untouched"


def test_without_a_place_the_fast_shard_writer_refuses_a_tczyx_array(tmp_path):
    """Written without a time point and channel, a shard would land in the wrong place."""
    from zarr.codecs import BloscCodec
    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import FastShardWriter

    root = zarr.open_group(str(tmp_path / "tile.ome.zarr"), mode="w", zarr_format=3)
    array = root.create_array(
        name="0", shape=(2, 2, 8, 40, 24), chunks=(1, 1, 4, 16, 16), shards=(1, 1, 8, 32, 32),
        dtype="uint16", compressors=[BloscCodec(cname="zstd", clevel=5)],
    )
    assert FastShardWriter.for_array(array) is None


def test_a_sharded_tczyx_store_is_written_through_the_fast_shard_writer(tmp_path):
    """Two channels of one time point, written as the writer process writes them but in one
    process: each stack takes the fast path and is read back at its own channel."""
    from zarr.codecs import BloscCodec
    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer import (
        ChunkScheme, PyramidSpec,
    )
    from mesoSPIM.src.plugins.support_files.ImageWriters.OmeZarrWriterMP.omezarr_writer_tczyx import (
        TCZYX, Live3DPyramidWriterTCZYX,
    )

    planes, y, x = 16, 64, 48
    path = tmp_path / "Mag1_Tile0_Sh0_Rot0.ome.zarr"
    stacks = {}
    for c in (0, 1):
        writer = Live3DPyramidWriterTCZYX(
            PyramidSpec(z_size_estimate=planes, y=y, x=x, levels=2),
            TCZYX(t=0, c=c, n_channels=2, channel_labels=("488", "561"), channel_colors=("00FF66", "FFBF1A")),
            path=str(path), chunk_scheme=ChunkScheme(base=(8, 32, 32), target=(8, 32, 32)),
            compressor=BloscCodec(cname="zstd", clevel=5), shard_shape=(8, 64, 64),
            async_close=False, max_inflight_chunks=1,
        )
        assert writer.fast_writers[0] is not None, "level 0 takes the fast path"
        rng = np.random.default_rng(c)
        stacks[c] = rng.integers(0, 4000, size=(planes, y, x), dtype=np.uint16)
        for plane in stacks[c]:
            writer.push_slice(plane)
        writer.close()

    level0 = zarr.open_group(str(path), mode="r")["0"]
    assert level0.shape == (1, 2, planes, y, x)
    for c in (0, 1):
        assert np.array_equal(level0[0, c], stacks[c]), f"channel {c} is read back as written"
