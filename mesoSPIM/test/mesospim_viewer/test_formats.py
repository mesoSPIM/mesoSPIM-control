"""Opening OME-Zarr in the layouts other writers use, not only the acquisition's own.

The live viewer reads what the mesoSPIM tczyx writer writes. A dataset opened
from disk may come from elsewhere: OME-Zarr 0.4 or 0.5, with all five axes
``t, c, z, y, x`` or only some of them, and sometimes one store per tile *and*
channel. These tests write each of those with the demo writer and check that the
viewer reads them, builds the right layers for the engine, and that the engine
then draws them.
"""

from __future__ import annotations

import json
import time

import pytest

from mesoSPIM.src.mesospim_viewer import (
    NotAStore,
    NotSupported,
    Acquisitions,
    Opened,
    Viewer,
    Watcher,
    read_store,
)
from mesoSPIM.src.mesospim_viewer.demo import write_store

LAYOUTS = ["tczyx", "czyx", "tzyx", "zyx"]
VERSIONS = ["0.4", "0.5"]


def an_acquisition(root, name):
    group = root / f"{name}.ome.zarr"
    group.mkdir(parents=True)
    (group / ".zgroup").write_text('{"zarr_format": 2}')
    return group


def one_store_per_channel(acquisition, *, version="0.4", omero=True):
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


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("axes", LAYOUTS)
def test_every_layout_is_read_in_both_versions(tmp_path, axes, version):
    store = read_store(write_store(tmp_path / "tile.ome.zarr", axes=axes, version=version))
    assert [axis.name for axis in store.axes] == list(axes)
    assert store.format == ("zarr2" if version == "0.4" else "zarr3")
    assert store.channel_count == (2 if "c" in axes else 1)
    assert store.scale[-3:] == (5.0, 1.0, 1.0)


def test_a_store_without_a_channel_axis_pins_no_channel(tmp_path):
    view = Viewer()
    try:
        view.add(write_store(tmp_path / "zyx.ome.zarr", axes="zyx"), layer="zyx")
        view.add(write_store(tmp_path / "czyx.ome.zarr", axes="czyx"), layer="czyx")
        layers = {layer["name"]: layer for layer in view.state["layers"]}
        assert "localPosition" not in layers["zyx · 488"]
        assert layers["czyx · 488"]["localPosition"] == [0]
        assert layers["czyx · 561"]["localPosition"] == [1]
    finally:
        view.stop()


def test_axes_out_of_order_or_without_zyx_are_refused(tmp_path):
    store = write_store(tmp_path / "tile.ome.zarr", axes="czyx")
    attrs = json.loads((store / ".zattrs").read_text())
    attrs["multiscales"][0]["axes"] = attrs["multiscales"][0]["axes"][:-1]
    (store / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotSupported, match="always with z, y and x"):
        read_store(store)


def test_ome_zarr_0_6_is_refused_with_a_plain_reason(tmp_path):
    store = write_store(tmp_path / "Mag1_Tile0_Sh0_Rot0.ome.zarr", axes="zyx", version="0.5")
    described = json.loads((store / "zarr.json").read_text())
    described["attributes"]["ome"]["version"] = "0.6"
    (store / "zarr.json").write_text(json.dumps(described))
    with pytest.raises(NotSupported, match="0.6, which this viewer does not read yet"):
        read_store(store)
    view = Viewer()
    try:
        # Opened on its own, it says so; beside others, it is not taken for an acquisition.
        with pytest.raises(NotSupported, match="0.6"):
            Opened(view, store)
        assert Acquisitions(tmp_path).list() == []
        with pytest.raises(NotSupported, match="0.6"):
            Opened(view, tmp_path)
    finally:
        view.stop()


@pytest.mark.parametrize("version", VERSIONS)
def test_one_store_per_channel_becomes_one_row_per_channel(tmp_path, version):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, version=version)
    view = Viewer()
    try:
        assert len(Watcher(view, acquisition).poll()) == 4
        layers = view.state["layers"]
        assert [layer["name"] for layer in layers] == ["run · 488", "run · 561"]
        for layer in layers:
            assert len(layer["source"]) == 2, "each channel reads only its own two tiles"
            assert "localPosition" not in layer
        assert '"#00ff66"' in layers[0]["shader"] and '"#ff33ff"' in layers[1]["shader"]
    finally:
        view.stop()


def test_without_channel_metadata_the_stores_are_shown_as_one_channel(tmp_path):
    # The channel is taken from inside the store only, never from its name: a store
    # that does not say which channel it holds cannot be told apart from the others.
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, omero=False)
    view = Viewer()
    try:
        Watcher(view, acquisition).poll()
        layers = view.state["layers"]
        assert len(layers) == 1 and len(layers[0]["source"]) == 4
    finally:
        view.stop()


def test_a_single_store_without_channel_axis_opens_on_its_own(tmp_path):
    view = Viewer()
    try:
        Opened(view, write_store(tmp_path / "zyx.ome.zarr", axes="zyx", version="0.5"))
        assert [layer["name"] for layer in view.state["layers"]] == ["zyx · 488"]
    finally:
        view.stop()


# -- what the engine draws --------------------------------------------------------


@pytest.mark.parametrize(
    ("axes", "version"), [("zyx", "0.4"), ("zyx", "0.5"), ("czyx", "0.5"), ("tzyx", "0.4")]
)
def test_the_engine_draws_each_layout(pages, tmp_path, axes, version):
    view = Viewer()
    view.add(write_store(tmp_path / "tile.ome.zarr", axes=axes, version=version), layer="tile")
    url = view.start()
    try:
        page, errors = pages.open(url)
        seen = pages.drawn(page, layers=2 if "c" in axes else 1)
        for layer in seen["layers"]:
            assert layer["errors"] == [] and layer["sources"] == 1
        assert [n for n in seen["names"] if n in "tzyx"] == [a for a in axes if a != "c"]
        assert not errors, errors
    finally:
        view.stop()


def test_the_engine_draws_one_store_per_channel_as_two_channels(pages, tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, version="0.5")
    view = Viewer()
    Opened(view, acquisition)
    url = view.start()
    try:
        page, errors = pages.open(url)
        seen = pages.drawn(page, layers=2)
        assert [layer["name"] for layer in seen["layers"]] == ["run · 488", "run · 561"]
        for layer in seen["layers"]:
            assert layer["errors"] == [] and layer["sources"] == 2
        time.sleep(0.5)
        assert not errors, errors
    finally:
        view.stop()


def test_a_folder_that_is_not_a_dataset_is_refused(tmp_path):
    (tmp_path / "notes").mkdir()
    view = Viewer()
    try:
        with pytest.raises(NotAStore, match="not a dataset the viewer can open"):
            Opened(view, tmp_path / "notes")
    finally:
        view.stop()
