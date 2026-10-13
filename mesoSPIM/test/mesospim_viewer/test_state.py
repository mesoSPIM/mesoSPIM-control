"""A few stores in, a scene out: what Python asks the page to show.

An acquisition becomes one engine layer per channel, all reading the same
sources (``state.py``), and a :class:`Viewer` keeps that scene up to date as
stores are added (``viewer.py``). The point of the redesign is in here: a layer
is described so that the page can change it in place. The shader's text never
changes, what differs between channels travels as control values, every source
has a lasting name, and a store shown again changes nothing unless its shape
has. Python only.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import (
    Channel,
    Layer,
    Placement,
    PreviewStack,
    Stack,
    channel_shader,
    engine_state,
    read_store,
    source_json,
    state_json,
)
from mesoSPIM.src.mesospim_viewer.state import SHADER, Preview, channel_controls, default_colour, dimensions

from .stores import GROUND, Slabs, land, one_store_per_channel, an_acquisition, scale_values, take_chunks, write_store
from .tools import status


def events(view) -> list[dict]:
    """What the page has been told happened, oldest first."""
    return [event for _, event in view._server.scene._events]


def version(view) -> int:
    return view._server.scene.version


def controls(view) -> list[dict]:
    return [layer["shaderControls"] for layer in view.scene["layers"]]


def ranges(view) -> list[list[float] | None]:
    """The black and white points each layer starts from, or None where the page sets them."""
    return [layer["shaderControls"].get("contrast", {}).get("range") for layer in view.scene["layers"]]


def a_stack(**about) -> Stack:
    described = dict(
        acquisition="run",
        channel="488",
        channels=("488", "561"),
        planes=8,
        frame=(32, 32),
        voxel_um=(5.0, 1.0, 1.0),
        origin_um=(0.0, 0.0, 0.0),
    )
    return Stack(**{**described, **about})


# -- one acquisition, one engine layer per channel -------------------------------------


def test_an_acquisition_becomes_one_engine_layer_per_channel_sharing_its_sources(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview", offset={"x": 10.0})
    view.add(tiles[2], layer="overview", origin={"x": 1000.0, "y": 0.0})
    state = view.state
    assert state["layout"] == "xy"
    assert state["displayDimensions"] == ["x", "y", "z"]
    assert [layer["name"] for layer in state["layers"]] == ["overview · 488", "overview · 561"]
    first, second = state["layers"]
    assert first["source"] == second["source"]
    assert (first["localPosition"], second["localPosition"]) == ([0], [1])
    assert first["blend"] == "default" and first["opacity"] == 1.0
    assert first["type"] == "image" and first["visible"] is True

    sources = first["source"]
    assert len(sources) == 3
    assert all(source["url"].endswith("/|zarr2:") for source in sources)
    # A store in its own place carries no transform at all.
    assert "transform" not in sources[0]
    # A shift is the translation column, in voxels of that axis; c stays local (c').
    dims = sources[1]["transform"]["outputDimensions"]
    assert list(dims) == ["t", "c'", "z", "y", "x"]
    assert dims["x"] == [1e-6, "m"] and dims["c'"] == [1, ""]
    assert [row[-1] for row in sources[1]["transform"]["matrix"]] == [0, 0, 0, 0, 10.0]
    # An origin replaces the store's own translation: tile 2 sits at y=144 um.
    assert [row[-1] for row in sources[2]["transform"]["matrix"]] == [0, 0, 0, -144.0, 1000.0]


def test_the_page_is_told_which_acquisition_channel_and_sources_a_layer_has(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview")
    first, second = view.scene["layers"]
    assert (first["_acquisition"], first["_channel"]) == ("overview", "488")
    assert (second["_acquisition"], second["_channel"]) == ("overview", "561")
    assert first["_sources"] == second["_sources"] == ["store-0", "store-1"]
    assert first["_retiring"] == [] and first["_auto"] is False


def test_the_engine_is_given_the_scene_without_the_pages_additions(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    scene, state = view.scene, view.state
    assert state == engine_state(scene)
    assert any(key.startswith("_") for key in scene["layers"][0])
    for mine, theirs in zip(scene["layers"], state["layers"]):
        assert not any(key.startswith("_") for key in theirs)
        assert theirs == {key: value for key, value in mine.items() if not key.startswith("_")}
    assert state["dimensions"] == scene["dimensions"]
    # A scene with nothing in it names no space: the engine keeps its own.
    assert engine_state(state_json([])) == {"layers": [], "layout": "xy", "displayDimensions": ["x", "y", "z"]}


def test_a_scene_must_be_laid_out_in_a_way_the_page_knows(viewers):
    with pytest.raises(ValueError):
        state_json([], layout="sideways")
    with pytest.raises(ValueError):
        viewers(layout="sideways")
    with pytest.raises(ValueError):
        viewers(ui="fancy")
    with pytest.raises(ValueError):
        Layer(name="empty").to_json()


# -- the program is the same for every channel; what differs are its controls -------------


def test_the_shader_text_is_the_same_whatever_the_channel(viewers, tiles, tmp_path):
    assert channel_shader(Channel("a", "#00ff00", window=(100, 2000))) == SHADER
    assert channel_shader(Channel("b", "#ff00ff")) == SHADER == channel_shader()
    assert "#uicontrol invlerp contrast\n" in SHADER
    assert '#uicontrol vec3 color color(default="#ffffff")' in SHADER
    assert "emitRGBA(vec4(color * value, max(value, 1.0 / 255.0)))" in SHADER
    view = viewers()
    view.add(tiles[0], layer="windowed", colours=["#123456", "#654321"], window=(5, 500))
    view.add(write_store(tmp_path / "plain.ome.zarr"), layer="plain")
    assert {layer["shader"] for layer in view.scene["layers"]} == {SHADER}


def test_the_controls_carry_the_window_and_the_colour():
    assert channel_controls(Channel("a", "#00ff00", window=(100, 2000), limits=(0, 4095))) == {
        "color": "#00ff00",
        "contrast": {"range": [100.0, 2000.0], "window": [0.0, 4095.0]},
    }
    # A channel that says nothing about its contrast leaves it to the page.
    assert channel_controls(Channel("b", "#ff00ff")) == {"color": "#ff00ff"}
    assert channel_controls(Channel("c")) == {"color": "#ffffff"}


def test_a_window_without_limits_gets_a_histogram_span_around_it():
    for limits in (None, (0.0, 65535.0)):  # the whole range of a camera says nothing
        contrast = channel_controls(Channel("a", window=(1000, 3000), limits=limits))["contrast"]
        assert contrast["range"] == [1000.0, 3000.0]
        low, high = contrast["window"]
        assert low == 0.0 and high == 5000.0
        assert low <= 1000 and 3000 < high < 65535 / 4, "room on both sides, not the whole data type"
    # Never below zero.
    assert channel_controls(Channel("a", window=(100, 2100)))["contrast"]["window"] == [0.0, 4100.0]
    assert channel_controls(Channel("a", window=(10000, 12000)))["contrast"]["window"] == [9000.0, 14000.0]


def test_the_stores_window_and_colour_reach_the_controls(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="run")
    assert controls(view) == [
        {"color": "#00ff66", "contrast": {"range": [380.0, 12400.0], "window": [0.0, 24420.0]}},
        {"color": "#ff33ff", "contrast": {"range": [380.0, 12400.0], "window": [0.0, 24420.0]}},
    ]
    assert [layer["_auto"] for layer in view.scene["layers"]] == [False, False]


def test_channels_colours_and_window_can_be_overridden(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="scan", channels=["GFP", "RFP"], colours=["#123456", None], window=(5, 500))
    layers = view.scene["layers"]
    assert [layer["name"] for layer in layers] == ["scan · GFP", "scan · RFP"]
    assert [layer["_channel"] for layer in layers] == ["GFP", "RFP"]
    assert layers[0]["shaderControls"]["color"] == "#123456"
    assert layers[1]["shaderControls"]["color"] == "#ff33ff"  # the store's own colour stays
    assert all(layer["shaderControls"]["contrast"]["range"] == [5.0, 500.0] for layer in layers)
    again = viewers()
    again.add(tiles[0], layer="scan", channels=[Channel("DAPI", "#0000ff", window=(1, 2))])
    assert again.scene["layers"][0]["name"] == "scan · DAPI"
    assert again.scene["layers"][0]["shaderControls"]["contrast"]["range"] == [1.0, 2.0]


def test_channels_without_a_colour_are_coloured_by_wavelength_or_in_turn():
    assert default_colour("488", 0, 2) == "#00ff66"
    assert default_colour("640 nm", 3, 4) == "#ff33ff"
    assert default_colour("brightfield", 0, 1) == "#ffffff", "one channel is white"
    assert default_colour("a", 0, 2) != default_colour("b", 1, 2)
    assert default_colour("", 0, 1) == "#ffffff"


def test_a_store_without_a_channel_axis_pins_no_channel(viewers, tmp_path):
    view = viewers()
    view.add(write_store(tmp_path / "zyx.ome.zarr", axes="zyx"), layer="zyx")
    view.add(write_store(tmp_path / "czyx.ome.zarr", axes="czyx"), layer="czyx")
    layers = {layer["name"]: layer for layer in view.state["layers"]}
    assert "localPosition" not in layers["zyx · 488"]
    assert layers["czyx · 488"]["localPosition"] == [0]
    assert layers["czyx · 561"]["localPosition"] == [1]


@pytest.mark.parametrize("version", ["0.4", "0.5"])
def test_one_store_per_channel_becomes_one_layer_per_channel(viewers, tmp_path, version):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, version=version)
    view = viewers()
    for path in sorted(acquisition.glob("*.ome.zarr")):
        view.add(path, layer="run", channel=read_store(path).channels[0])
    layers = view.scene["layers"]
    assert [layer["name"] for layer in layers] == ["run · 488", "run · 561"]
    for layer in layers:
        assert len(layer["source"]) == 2 == len(layer["_sources"]), "each channel reads only its own two tiles"
        assert "localPosition" not in layer
    assert set(layers[0]["_sources"]).isdisjoint(layers[1]["_sources"])
    assert [layer["shaderControls"]["color"] for layer in layers] == ["#00ff66", "#ff33ff"]
    named = viewers()
    named.add(sorted(acquisition.glob("*.ome.zarr"))[0], layer="run", channel="GFP")
    assert [layer["name"] for layer in named.scene["layers"]] == ["run · GFP"]


def test_layers_can_be_hidden_removed_and_relaid(viewers, tiles):
    view = viewers(layout="4panel")
    view.add(tiles[0], layer="one")
    view.add(tiles[1])  # its own layer, named after the store
    assert view.layers == ["one", "tile_01.ome.zarr"]
    assert [store.path for store in view.stores("one")] == [tiles[0].resolve()]
    view.set_visible("one", False)
    assert [layer["visible"] for layer in view.state["layers"]] == [False, False, True, True]
    assert view.remove("one") and not view.remove("one")
    view.set_layout("3d")
    assert view.state["layout"] == "3d"
    assert [layer["name"] for layer in view.state["layers"]] == [
        "tile_01.ome.zarr · 488",
        "tile_01.ome.zarr · 561",
    ]
    with pytest.raises(ValueError):
        view.set_layout("sideways")
    view.clear()
    assert view.state["layers"] == [] and view.layers == []


def test_a_store_can_be_taken_out_of_its_layer(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="run")
    view.add(tiles[1], layer="run")
    assert view.remove_store("run", tiles[0]) is True
    assert view.scene["layers"][0]["_sources"] == ["store-1"]
    assert view.remove_store("run", tiles[0]) is False and view.remove_store("other", tiles[1]) is False
    assert view.remove_store("run", tiles[1]) is True
    assert view.layers == [], "the layer goes with its last store"


# -- a layer is changed, never rebuilt ----------------------------------------------------


def test_a_source_keeps_its_name_and_its_address_when_its_store_is_shown_again(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview")
    before = view.scene
    assert re.search(r"/data/0/\|zarr2:$", before["layers"][0]["source"][0]["url"])
    published = version(view)
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview")
    assert view.scene == before
    assert version(view) == published, "nothing changed, so nothing reaches the page"
    assert events(view) == []


def test_the_names_of_the_sources_outlive_the_layer(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="first")
    view.add(tiles[1], layer="first")
    view.remove("first")
    view.add(tiles[1], layer="second")
    view.add(tiles[0], layer="second")
    assert view.scene["layers"][0]["_sources"] == ["store-1", "store-0"]


def test_a_store_whose_shape_changed_gets_a_new_address_and_no_other_does(viewers, tmp_path, tiles):
    growing = Slabs(tmp_path / "growing.ome.zarr")
    view = viewers()
    view.add(tiles[0], layer="run")
    view.add(growing.path, layer="run")
    before = view.scene["layers"][0]
    published = version(view)
    growing.create(timepoints=2)  # the writer appends a time point: metadata first
    view.add(growing.path, layer="run")
    after = view.scene["layers"][0]
    assert version(view) == published + 1
    assert after["_sources"] == before["_sources"] == ["store-0", "store-1"], "the names stay"
    assert after["source"][0] == before["source"][0], "the other tile is not read again"
    assert before["source"][1]["url"].endswith("/data/1/|zarr3:")
    assert after["source"][1]["url"].endswith("/data/1.1/|zarr3:")
    assert [store.shape[0] for store in view.stores("run")] == [1, 2]
    growing.create(timepoints=3)
    view.add(growing.path, layer="run")
    assert view.scene["layers"][0]["source"][1]["url"].endswith("/data/1.2/|zarr3:")
    # Every address names the same store on the server.
    for address in ("data/1/", "data/1.1/", "data/1.2/"):
        assert status(view.url + address + "zarr.json") == 200, address
    assert status(view.url + "data/7.1/zarr.json") == 404


def test_refreshing_reads_descriptions_again_and_asks_for_what_was_missing(viewers, tmp_path, tiles):
    growing = Slabs(tmp_path / "growing.ome.zarr")
    view = viewers()
    view.add(tiles[0], layer="run")
    view.add(growing.path, layer="run")
    before, published = view.scene, version(view)
    view.refresh()
    assert view.scene == before and version(view) == published
    assert events(view) == [{"type": "landed", "store": "data/0"}, {"type": "landed", "store": "data/1"}]
    growing.create(timepoints=2)
    view.refresh("run")
    assert view.scene["layers"][0]["source"][1]["url"].endswith("/data/1.1/|zarr3:")
    assert view.scene["layers"][0]["source"][0] == before["layers"][0]["source"][0]


def test_landed_files_are_named_to_the_page_once_as_an_event(viewers, tiles):
    view = viewers()
    view.landed(tiles[0], ["0/0.0.0.0.0"])  # before anything is served: nobody to tell
    view.add(tiles[0], layer="run")
    view.add(tiles[1], layer="run")
    published = version(view)
    view.landed(tiles[1], ["0/0.0.5.0.0", "0/0.0.5.0.1"])
    view.landed(tiles[1], [])  # nothing landed, nothing said
    view.landed(tiles[2], ["0/0.0.0.0.0"])  # not a store that is shown
    view.landed(tiles[0])  # everything that was found missing
    assert events(view) == [
        {"type": "landed", "store": "data/1", "files": ["0/0.0.5.0.0", "0/0.0.5.0.1"]},
        {"type": "landed", "store": "data/0"},
    ]
    assert version(view) == published, "an event is not a new scene"


# -- the space the picture is drawn in -------------------------------------------------------


def test_the_dimensions_are_the_finest_voxel_size_shown(viewers, tiles, tmp_path):
    view = viewers()
    assert view.scene["dimensions"] == {}
    view.add(tiles[0], layer="coarse")
    assert view.scene["dimensions"] == {
        "x": [pytest.approx(1e-6), "m"],
        "y": [pytest.approx(1e-6), "m"],
        "z": [pytest.approx(5e-6), "m"],
        "t": [1, ""],
    }
    # A finer stack shown later decides, whatever arrived first.
    fine = write_store(tmp_path / "fine.ome.zarr", axes="zyx")
    attrs = (fine / ".zattrs").read_text().replace('"micrometer"', '"nanometer"')
    (fine / ".zattrs").write_text(attrs)
    view.add(fine, layer="fine")
    space = view.scene["dimensions"]
    assert space["z"] == [pytest.approx(5e-9), "m"] and space["x"] == [pytest.approx(1e-9), "m"]
    view.remove("coarse")
    assert "t" not in view.scene["dimensions"], "no store with a time axis is left"


def test_the_dimensions_take_in_a_preview(viewers):
    layer = Layer(
        name="run",
        previews=[Preview(id="live-1", url="live/live-1/|zarr2:", channel=Channel("488"), voxel_um=(2.0, 0.5, 0.5))],
    )
    assert dimensions([layer]) == {
        "x": [pytest.approx(0.5e-6), "m"],
        "y": [pytest.approx(0.5e-6), "m"],
        "z": [pytest.approx(2e-6), "m"],
        "t": [1, ""],
    }
    assert dimensions([Layer(name="none")]) == {}


def test_a_source_is_an_address_and_a_transform_only_when_shifted(tiles):
    store = read_store(tiles[1])
    assert source_json(Placement(store=store, url="u")) == {"url": "u"}
    assert source_json(Placement(store=store, url="u", origin={"x": 144.0})) == {"url": "u"}, "where it is already"
    shifted = source_json(Placement(store=store, url="u", offset={"z": 10.0}))
    assert [row[-1] for row in shifted["transform"]["matrix"]] == [0, 0, 2.0, 0, 0], "in voxels: 5 um planes"
    assert shifted["transform"]["outputDimensions"]["z"] == [pytest.approx(5e-6), "m"]


# -- stacks shown from memory ----------------------------------------------------------------


def test_a_preview_joins_its_channels_layer_at_the_stores_channel_index(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="run")
    name = view.add_preview("run", PreviewStack(a_stack(channel="561")), Channel("561"))
    assert name == "live-1"
    green, magenta = view.scene["layers"]
    assert green["_sources"] == ["store-0"] and len(green["source"]) == 1
    assert magenta["_sources"] == ["store-0", "live-1"]
    assert magenta["source"][1] == {"url": f"{view.url}live/live-1/|zarr2:"}
    assert (green["localPosition"], magenta["localPosition"]) == ([0], [1])
    assert status(view.url + "live/live-1/.zattrs") == 200


def test_a_preview_alone_makes_its_layer_and_pins_its_own_channel_index(viewers):
    view = viewers()
    view.add_preview("run", PreviewStack(a_stack(channel="561")), Channel("561", "#ff33ff"))
    (layer,) = view.scene["layers"]
    assert layer["name"] == "run · 561" and layer["_sources"] == ["live-1"]
    assert layer["localPosition"] == [1], "the second channel of the preview's own store"
    assert layer["shaderControls"] == {"color": "#ff33ff"} and layer["_auto"] is True
    assert view.scene["dimensions"]["z"] == [pytest.approx(5e-6), "m"]
    # The next channel of the run: a layer of its own, beside the first.
    view.add_preview("run", PreviewStack(a_stack(channel="488")), Channel("488"))
    assert [(layer["name"], layer["localPosition"]) for layer in view.scene["layers"]] == [
        ("run · 561", [1]),
        ("run · 488", [0]),
    ]


def test_a_preview_over_stores_without_a_channel_axis_is_read_at_its_index(viewers, tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition)
    view = viewers()
    for path in sorted(acquisition.glob("*.ome.zarr")):
        view.add(path, layer="run", channel=read_store(path).channels[0])
    view.add_preview("run", PreviewStack(a_stack(channel="561")), Channel("561"))
    green, magenta = view.scene["layers"]
    assert "localPosition" not in green
    assert magenta["localPosition"] == [1] and magenta["_sources"][-1] == "live-1"


def test_a_preview_is_retired_and_then_removed(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="run")
    name = view.add_preview("run", PreviewStack(a_stack()), Channel("488"))
    assert view.scene["layers"][0]["_retiring"] == []
    view.retire_preview(name)
    assert view.scene["layers"][0]["_retiring"] == [name]
    assert view.scene["layers"][0]["_sources"] == ["store-0", name], "still shown while the tile takes over"
    published = version(view)
    view.retire_preview(name)
    assert version(view) == published
    assert view.remove_preview(name) is True and view.remove_preview(name) is False
    assert view.scene["layers"][0]["_sources"] == ["store-0"]
    assert status(view.url + f"live/{name}/.zattrs") == 404, "its memory is let go"
    # A layer that held nothing but a preview goes with it.
    alone = view.add_preview("tiffs", PreviewStack(a_stack()), Channel("488"))
    assert view.layers == ["run", "tiffs"]
    view.remove_preview(alone)
    assert view.layers == ["run"]


def test_planes_of_a_preview_are_announced_as_landed_files(viewers):
    view = viewers()
    preview = PreviewStack(a_stack())
    name = view.add_preview("run", preview, Channel("488"))
    view.preview_landed(name, preview.add(0, np.full((32, 32), 500, np.uint16)))
    view.preview_landed(name, [])
    assert events(view) == [{"type": "landed", "store": "live/live-1", "files": ["0/0/0/0/0/0"]}]


# -- the contrast a channel starts with ----------------------------------------------------------


def test_without_a_window_in_the_store_the_contrast_is_set_from_the_data(viewers, tmp_path):
    store = write_store(tmp_path / "plain.ome.zarr")  # an omero block, no window
    assert all(channel.window is None for channel in read_store(store).channels)
    view = viewers()
    view.add(store, layer="run")
    for low, high in ranges(view):
        assert low == GROUND
        assert 2000.0 < high <= 12400.0 * 1.1
    for layer in view.scene["layers"]:
        low, high = layer["shaderControls"]["contrast"]["window"]
        assert low < GROUND and high > layer["shaderControls"]["contrast"]["range"][1]
        assert layer["_auto"] is False, "set once, from the data: the page leaves it alone"


def test_a_store_without_data_yet_gets_its_contrast_once_data_lands(viewers, tmp_path):
    store = write_store(tmp_path / "landing.ome.zarr")
    taken = take_chunks(store)
    view = viewers()
    view.add(store, layer="run")
    assert ranges(view) == [None, None]
    assert view.measure("run") is False
    land(taken)
    assert view.measure("run", store) is True
    first = ranges(view)
    assert all(window is not None and window[0] == GROUND for window in first)
    assert view.measure("run") is False and view.measure("nothing such") is False
    # Decided once: a brighter tile landing later does not move it.
    bright = write_store(tmp_path / "bright.ome.zarr", seed=5)
    scale_values(bright, 4)
    view.add(bright, layer="run")
    assert ranges(view) == first


def test_a_store_added_unmeasured_gets_no_contrast_from_its_data(viewers, tmp_path):
    """For a store that is being written: what is on disk of it so far says little
    about its brightness, so its contrast is left to the page."""
    store = write_store(tmp_path / "plain.ome.zarr")  # holds data, names no window
    measured, left = viewers(), viewers()
    measured.add(store, layer="run")
    left.add(store, layer="run", measure=False)
    assert all(window is not None and window[0] == GROUND for window in ranges(measured))
    assert ranges(left) == [None, None]
    assert all("contrast" not in held for held in controls(left))
    assert [layer["_auto"] for layer in left.scene["layers"]] == [True, True], "the page sets it from the screen"
    assert [layer["_auto"] for layer in measured.scene["layers"]] == [False, False]
    # Apart from the contrast the two scenes are the same.
    strip = lambda view: [
        {key: value for key, value in layer.items() if key not in ("shaderControls", "_auto", "source")}
        for layer in view.scene["layers"]
    ]
    assert strip(left) == strip(measured)
    # Shown again unmeasured -- a time point was appended, say -- it still has none...
    published = version(left)
    left.add(store, layer="run", measure=False)
    assert ranges(left) == [None, None] and version(left) == published
    # ...until someone asks for it: the default, or measure().
    assert left.measure("run") is True
    assert ranges(left) == ranges(measured)


def test_adding_unmeasured_leaves_a_contrast_that_is_set_alone(viewers, tmp_path):
    store = write_store(tmp_path / "plain.ome.zarr")
    view = viewers()
    view.add(store, layer="run")
    first = ranges(view)
    bright = write_store(tmp_path / "bright.ome.zarr", seed=5)
    scale_values(bright, 4)
    view.add(bright, layer="run", measure=False)
    assert ranges(view) == first and len(view.stores("run")) == 2
    # A window the store names itself is not a measurement: it is used either way.
    named = viewers()
    named.add(store, layer="run", window=(500, 900), measure=False)
    assert ranges(named) == [[500.0, 900.0], [500.0, 900.0]]


def test_showing_a_store_again_measures_it_if_it_had_no_data_before(viewers, tmp_path):
    store = write_store(tmp_path / "landing.ome.zarr")
    taken = take_chunks(store)
    view = viewers()
    view.add(store, layer="run")
    land(taken)
    view.add(store, layer="run")
    assert all(window is not None for window in ranges(view))
    assert view.scene["layers"][0]["source"][0]["url"].endswith("/data/0/|zarr2:"), "at the same address"


def test_a_channel_arriving_later_gets_its_own_contrast(viewers, tmp_path):
    view = viewers()
    green = write_store(tmp_path / "t0_488.ome.zarr", axes="zyx", channel=0)
    view.add(green, layer="run", channel=read_store(green).channels[0])
    assert [window is not None for window in ranges(view)] == [True]
    magenta = write_store(tmp_path / "t0_561.ome.zarr", axes="zyx", channel=1)
    scale_values(magenta, 2)
    view.add(magenta, layer="run", channel=read_store(magenta).channels[0])
    green_window, magenta_window = ranges(view)
    assert magenta_window[0] == 2 * GROUND and magenta_window[1] > green_window[1]


def test_a_window_can_be_given_and_auto_switched_from_python(viewers, tmp_path):
    store = write_store(tmp_path / "landing.ome.zarr")
    take_chunks(store)
    view = viewers()
    view.add(store, layer="run")
    view.set_window("run", "488", (700, 3230))
    assert ranges(view) == [[700.0, 3230.0], None]
    view.set_window("run", "488", (1, 2), only_if_unset=True)
    assert ranges(view)[0] == [700.0, 3230.0], "the first one stays"
    view.set_window("run", "488", (800, 900))
    assert ranges(view)[0] == [800.0, 900.0]
    view.set_window("nothing such", "488", (1, 2))



def test_the_page_sets_the_contrast_itself_where_nobody_has_or_while_a_run_is_written(viewers, tmp_path, tiles):
    store = write_store(tmp_path / "landing.ome.zarr")
    take_chunks(store)
    view = viewers()
    view.add(store, layer="landing")
    view.add(tiles[0], layer="run")
    auto = lambda: {layer["name"]: layer["_auto"] for layer in view.scene["layers"]}
    # No window from the store, none measured: the page's to set. A window in the store: not.
    assert auto() == {"landing · 488": True, "landing · 561": True, "run · 488": False, "run · 561": False}
    view.set_window("landing", "488", (700, 3230))
    assert auto()["landing · 488"] is False and auto()["landing · 561"] is True
    # An acquisition that is being written: nobody knows its brightness yet.
    published = version(view)
    view.set_auto("run", True)
    assert auto()["run · 488"] is True and auto()["run · 561"] is True
    assert version(view) == published + 1
    view.set_auto("run", True)
    assert version(view) == published + 1, "said twice, published once"
    view.set_auto("run", False)
    assert auto()["run · 488"] is False
