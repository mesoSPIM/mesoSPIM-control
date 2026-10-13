"""Reading OME-Zarr: the tiles the microscope writes, and what other writers make.

The viewer reads just enough of a store to place it and name its channels
(``omezarr.py``): OME-Zarr 0.4 or 0.5, with all five axes ``t, c, z, y, x`` or
only some of them. It also reads how a store's arrays are cut into files, to
tell how far a stack has been written, and a small sample of voxels where a
store gives no contrast window. Python and numpy only; what the engine draws of
these stores is in ``test_page.py``.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import NotAStore, NotSupported, omezarr, read_store
from mesoSPIM.src.mesospim_viewer.demo import write_tile
from mesoSPIM.src.mesospim_viewer.omezarr import Level, read_levels, robust_window, sample_window

from .stores import GROUND, Slabs, chunk_files, take_chunks, write_store

LAYOUTS = ["tczyx", "czyx", "tzyx", "zyx"]
VERSIONS = ["0.4", "0.5"]

# -- describing a store ------------------------------------------------------------


def test_a_tile_is_read_as_tczyx_with_its_place_and_channels(tiles):
    store = read_store(tiles[1])
    assert [axis.name for axis in store.axes] == ["t", "c", "z", "y", "x"]
    assert store.format == "zarr2"
    assert store.shape == (1, 2, 24, 160, 160)
    assert store.scale == (1.0, 1.0, 5.0, 1.0, 1.0)
    assert store.translation[4] == pytest.approx(144.0)  # second column, 16 um overlap
    assert [channel.label for channel in store.channels] == ["488", "561"]
    assert store.channels[0].color == "#00ff66"
    assert store.channels[0].window == (380.0, 12400.0)
    assert store.channels[0].limits == (0.0, 65535.0)
    assert store.channel_count == 2 and store.channel_axis == 1
    assert store.axis_index("z") == 2
    assert store.levels[0] == "0" and len(store.levels) >= 3
    with pytest.raises(KeyError):
        store.axis_index("w")


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("axes", LAYOUTS)
def test_every_layout_is_read_in_both_versions(tmp_path, axes, version):
    store = read_store(write_store(tmp_path / "tile.ome.zarr", axes=axes, version=version))
    assert [axis.name for axis in store.axes] == list(axes)
    assert store.format == ("zarr2" if version == "0.4" else "zarr3")
    assert store.channel_count == (2 if "c" in axes else 1)
    assert store.scale[-3:] == (5.0, 1.0, 1.0)


def test_units_are_turned_into_si(tmp_path):
    store = read_store(write_store(tmp_path / "tile.ome.zarr"))
    assert [axis.si for axis in store.axes] == [("s", 1.0), ("", 1.0), ("m", 1e-6), ("m", 1e-6), ("m", 1e-6)]
    assert [axis.is_channel for axis in store.axes] == [False, True, False, False, False]


def test_the_reader_refuses_what_is_not_in_the_contract(tmp_path):
    with pytest.raises(NotAStore):
        read_store(tmp_path)  # nothing there

    # Axes may be left out, but not put in another order.
    tczxy = write_tile(tmp_path / "tczxy.ome.zarr", origin_um=(0, 0, 0), seed=1)
    attrs = json.loads((tczxy / ".zattrs").read_text())
    axes = attrs["multiscales"][0]["axes"]
    axes[3], axes[4] = axes[4], axes[3]
    (tczxy / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotAStore, match="axes"):
        read_store(tczxy)

    old = write_tile(tmp_path / "old.ome.zarr", origin_um=(0, 0, 0), seed=1)
    attrs = json.loads((old / ".zattrs").read_text())
    attrs["multiscales"][0]["version"] = "0.3"
    (old / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotAStore, match="0.4"):
        read_store(old)

    # How the arrays are chunked is the writer's business, not the reader's.
    per_plane = write_tile(tmp_path / "per_plane.ome.zarr", origin_um=(0, 0, 0), seed=1)
    array = json.loads((per_plane / "0" / ".zarray").read_text())
    assert array["chunks"][:3] == [1, 1, 1]
    assert read_store(per_plane).channel_count == 2


def test_axes_without_zyx_are_refused(tmp_path):
    store = write_store(tmp_path / "tile.ome.zarr", axes="czyx")
    attrs = json.loads((store / ".zattrs").read_text())
    attrs["multiscales"][0]["axes"] = attrs["multiscales"][0]["axes"][:-1]
    (store / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotSupported, match="always with z, y and x"):
        read_store(store)


def test_a_refusal_says_why_in_a_few_words_without_the_path(tmp_path):
    with pytest.raises(NotAStore) as nothing:
        read_store(tmp_path)
    assert nothing.value.reason is None and not isinstance(nothing.value, NotSupported)

    broken = tmp_path / "broken.ome.zarr"
    broken.mkdir()
    (broken / ".zattrs").write_text("{not json")
    with pytest.raises(NotAStore) as unread:
        read_store(broken)
    assert unread.value.reason == "its metadata could not be read"

    odd = write_store(tmp_path / "odd.ome.zarr")
    attrs = json.loads((odd / ".zattrs").read_text())
    attrs["multiscales"][0]["axes"][1]["type"] = "space"
    (odd / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotSupported) as typed:
        read_store(odd)
    assert typed.value.reason == "its axis c is not of type channel"

    bare = write_store(tmp_path / "bare.ome.zarr")
    (bare / "0" / ".zarray").unlink()
    with pytest.raises(NotSupported) as shapeless:
        read_store(bare)
    assert shapeless.value.reason == "its image data could not be read"


def test_ome_zarr_0_6_is_refused_with_a_plain_reason(tmp_path):
    store = write_store(tmp_path / "Mag1_Tile0_Sh0_Rot0.ome.zarr", axes="zyx", version="0.5")
    described = json.loads((store / "zarr.json").read_text())
    described["attributes"]["ome"]["version"] = "0.6"
    (store / "zarr.json").write_text(json.dumps(described))
    with pytest.raises(NotSupported, match="0.6, which this viewer does not read yet") as refused:
        read_store(store)
    assert refused.value.reason == "it is OME-NGFF 0.6, which the viewer does not read yet"


def test_a_zarr3_store_is_read_from_zarr_json(tmp_path):
    store = tmp_path / "v3.ome.zarr"
    (store / "0").mkdir(parents=True)
    axes = [{"name": "t", "type": "time", "unit": "second"}, {"name": "c", "type": "channel"}]
    axes += [{"name": name, "type": "space", "unit": "micrometer"} for name in "zyx"]
    transformations = [
        {"type": "scale", "scale": [1, 1, 4, 0.5, 0.5]},
        {"type": "translation", "translation": [0, 0, 0, 10, 20]},
    ]
    multiscale = {"axes": axes, "datasets": [{"path": "0", "coordinateTransformations": transformations}]}
    (store / "zarr.json").write_text(
        json.dumps(
            {
                "zarr_format": 3,
                "node_type": "group",
                "attributes": {"ome": {"version": "0.5", "multiscales": [multiscale]}},
            }
        )
    )
    sharding = {"chunk_shape": [1, 3, 1, 50, 50], "codecs": [{"name": "bytes"}]}
    (store / "0" / "zarr.json").write_text(
        json.dumps(
            {
                "zarr_format": 3,
                "node_type": "array",
                "shape": [1, 3, 10, 100, 100],
                "data_type": "uint16",
                "chunk_grid": {"name": "regular", "configuration": {"chunk_shape": [1, 3, 10, 100, 100]}},
                "codecs": [{"name": "sharding_indexed", "configuration": sharding}],
            }
        )
    )
    read = read_store(store)
    assert read.format == "zarr3"
    assert read.shape == (1, 3, 10, 100, 100)
    assert read.scale == (1, 1, 4, 0.5, 0.5)
    assert read.translation == (0, 0, 0, 10, 20)
    assert [channel.label for channel in read.channels] == []
    assert read.channel_count == 3
    # A file on disk is a shard: that is what a look at the folder counts.
    assert read_levels(read) == (Level(path="0", shape=(1, 3, 10, 100, 100), files=(1, 3, 10, 100, 100)),)


def test_scale_and_translation_are_composed_in_order(tmp_path):
    store = write_store(tmp_path / "tile.ome.zarr", axes="zyx", origin_um=(10.0, 20.0, 30.0))
    attrs = json.loads((store / ".zattrs").read_text())
    attrs["multiscales"][0]["coordinateTransformations"] = [{"type": "scale", "scale": [2.0, 2.0, 2.0]}]
    (store / ".zattrs").write_text(json.dumps(attrs))
    read = read_store(store)
    assert read.scale == (10.0, 2.0, 2.0)
    assert read.translation == (20.0, 40.0, 60.0)


# -- how a store is cut into files ---------------------------------------------------


@pytest.mark.parametrize("version", VERSIONS)
def test_the_levels_are_read_finest_first_with_what_one_file_holds(tmp_path, version):
    store = read_store(write_store(tmp_path / "tile.ome.zarr", version=version))
    levels = read_levels(store)
    assert [level.path for level in levels] == list(store.levels) == ["0", "1", "2", "3"]
    assert levels[0].shape == (1, 2, 24, 160, 160) and levels[0].files == (1, 1, 1, 64, 64)
    assert levels[1].shape == (1, 2, 24, 80, 80)
    assert levels[3].shape == (1, 2, 24, 20, 20) and levels[3].files == (1, 1, 1, 20, 20)
    assert [levels[0].count(axis) for axis in range(5)] == [1, 2, 24, 3, 3]


def test_a_level_that_is_being_created_is_left_out_with_those_after_it(tmp_path):
    path = write_store(tmp_path / "tile.ome.zarr")
    (path / "2" / ".zarray").unlink()
    assert [level.path for level in read_levels(read_store(path))] == ["0", "1"]
    (path / "0" / ".zarray").write_text("{half a fi")
    with pytest.raises(NotSupported):
        read_store(path)


def test_a_chunk_file_says_where_in_the_array_it_sits():
    level = Level(path="0", shape=(2, 2, 128, 512, 512), files=(1, 1, 64, 256, 256))
    assert level.index_of("c/0/1/5/3/2") == (0, 1, 5, 3, 2)  # zarr v3
    assert level.index_of("0.1.5.3.2") == (0, 1, 5, 3, 2)  # zarr v2, as the demo tiles are written
    assert level.index_of("0/1/5/3/2") == (0, 1, 5, 3, 2)  # zarr v2 with folders
    assert level.index_of("zarr.json") is None
    assert level.index_of(".zarray") is None
    assert level.index_of("c/0/1/5/3") is None, "one index short"
    assert level.index_of("c/0/1/5/3/2.partial") is None
    assert level.index_of("") is None
    assert level.count(2) == 2 and level.count(3) == 2
    assert Level(path="0", shape=(20,), files=(8,)).count(0) == 3


# -- a contrast window from the data --------------------------------------------------


def test_a_robust_window_runs_from_the_ground_to_just_under_the_brightest():
    rng = np.random.default_rng(0)
    values = rng.normal(400, 5, size=(64, 64)).astype(np.uint16)
    values[20:30, 20:30] = 3000  # a structure
    plain = robust_window(values)
    values[5, 5] = 65535  # one hot pixel
    low, high = robust_window(values)
    assert (low, high) == plain, "one hot pixel does not move the window"
    assert 380 <= low <= 400
    assert 3000 <= high < 3400, "opened up by a tenth above the structure"


def test_flat_or_empty_data_has_no_window():
    assert robust_window(np.full((16, 16), 400, np.uint16)) is None
    assert robust_window(np.zeros((0,), np.uint16)) is None
    # Nearly flat: the percentiles coincide, the extremes still tell.
    nearly = np.full(10_000, 400, np.uint16)
    nearly[0] = 500
    assert robust_window(nearly) == (400.0, pytest.approx(510.0))


def test_a_store_without_a_window_is_sampled_for_one(tmp_path):
    store = read_store(write_store(tmp_path / "plain.ome.zarr"))
    assert all(channel.window is None for channel in store.channels)
    for channel in (0, 1):
        low, high = sample_window(store, channel)
        # The pretend cells sit on a ground of 400 and peak at 12400; the coarsest
        # copy of the image averages the peaks down a little.
        assert low == GROUND
        assert 2000.0 < high <= 12400.0 * 1.1
    zyx = read_store(write_store(tmp_path / "zyx.ome.zarr", axes="zyx", version="0.5"))
    assert sample_window(zyx)[0] == GROUND


def test_a_store_that_holds_nothing_yet_gives_no_window(tmp_path):
    path = write_store(tmp_path / "landing.ome.zarr")
    take_chunks(path)
    assert chunk_files(path) == []
    assert sample_window(read_store(path), 0) is None
    tile = Slabs(tmp_path / "slabs.ome.zarr")
    assert sample_window(read_store(tile.path), 0) is None
    # Voxels still at the fill value are not data: one slab says what the ground is.
    tile.write(0)
    assert sample_window(read_store(tile.path), 0)[0] == GROUND


def test_the_sample_comes_from_the_finest_copy_written_yet(tmp_path):
    path = write_store(tmp_path / "landing.ome.zarr")
    levels = read_store(path).levels
    assert len(levels) >= 3
    # The coarsest copy is the last to get its chunks while a stack is written.
    take_chunks(path, lambda chunk: chunk.parent.name != levels[0])
    window = sample_window(read_store(path))
    assert window is not None and window[0] == GROUND, window


def test_a_copy_whose_planes_are_too_big_to_read_is_not_sampled(tmp_path, monkeypatch):
    path = write_store(tmp_path / "big.ome.zarr")
    monkeypatch.setattr(omezarr, "SAMPLE_BYTES", 1)
    assert sample_window(read_store(path)) is None
