"""The mesoSPIM view: a few stores in, a neuroglancer state out, a picture on screen.

Three groups. The first two need only Python and numpy and always run; the
last drives the built page in a headless Chromium and skips, saying so, when
the page is not built or no browser is available.
"""

from __future__ import annotations

import json
import time
import urllib.request

import pytest

from mesoSPIM.src.mesospim_viewer import Channel, NotAStore, Viewer, channel_shader, read_store
from mesoSPIM.src.mesospim_viewer.demo import write_tile

# -- reading a store -------------------------------------------------------------


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
    assert store.channel_count == 2


def test_the_reader_refuses_what_is_not_in_the_contract(tmp_path):
    with pytest.raises(NotAStore):
        read_store(tmp_path)  # nothing there

    czyx = tmp_path / "czyx.ome.zarr"
    write_tile(czyx, origin_um=(0, 0, 0), seed=1)
    attrs = json.loads((czyx / ".zattrs").read_text())
    attrs["multiscales"][0]["axes"].pop(0)
    (czyx / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotAStore, match="axes"):
        read_store(czyx)

    old = tmp_path / "old.ome.zarr"
    write_tile(old, origin_um=(0, 0, 0), seed=1)
    attrs = json.loads((old / ".zattrs").read_text())
    attrs["multiscales"][0]["version"] = "0.3"
    (old / ".zattrs").write_text(json.dumps(attrs))
    with pytest.raises(NotAStore, match="0.4"):
        read_store(old)

    # How the arrays are chunked is the writer's business, not the reader's.
    per_channel = tmp_path / "per_channel.ome.zarr"
    write_tile(per_channel, origin_um=(0, 0, 0), seed=1)
    array = json.loads((per_channel / "0" / ".zarray").read_text())
    assert array["chunks"][:3] == [1, 1, 1]
    assert read_store(per_channel).channel_count == 2


def test_a_zarr3_store_is_read_from_zarr_json(tmp_path):
    store = tmp_path / "v3.ome.zarr"
    (store / "0").mkdir(parents=True)
    (store / "zarr.json").write_text(
        json.dumps(
            {
                "zarr_format": 3,
                "node_type": "group",
                "attributes": {
                    "ome": {
                        "version": "0.5",
                        "multiscales": [
                            {
                                "axes": [
                                    {"name": "t", "type": "time", "unit": "second"},
                                    {"name": "c", "type": "channel"},
                                    {"name": "z", "type": "space", "unit": "micrometer"},
                                    {"name": "y", "type": "space", "unit": "micrometer"},
                                    {"name": "x", "type": "space", "unit": "micrometer"},
                                ],
                                "datasets": [
                                    {
                                        "path": "0",
                                        "coordinateTransformations": [
                                            {"type": "scale", "scale": [1, 1, 4, 0.5, 0.5]},
                                            {
                                                "type": "translation",
                                                "translation": [0, 0, 0, 10, 20],
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                },
            }
        )
    )
    (store / "0" / "zarr.json").write_text(
        json.dumps(
            {
                "zarr_format": 3,
                "node_type": "array",
                "shape": [1, 3, 10, 100, 100],
                "data_type": "uint16",
                "chunk_grid": {
                    "name": "regular",
                    "configuration": {"chunk_shape": [1, 3, 10, 100, 100]},
                },
                "codecs": [
                    {
                        "name": "sharding_indexed",
                        "configuration": {
                            "chunk_shape": [1, 3, 1, 50, 50],
                            "codecs": [{"name": "bytes"}],
                        },
                    }
                ],
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


# -- building the state ----------------------------------------------------------


def test_an_acquisition_becomes_one_engine_layer_per_channel_sharing_its_sources(tiles):
    view = Viewer()
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview", offset={"x": 10.0})
    view.add(tiles[2], layer="overview", origin={"x": 1000.0, "y": 0.0})
    try:
        state = view.state
    finally:
        view.stop()
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


def test_the_shader_is_the_engines_own_with_the_stores_window_and_colour():
    shader = channel_shader(Channel("a", "#00ff00", window=(100, 2000), limits=(0, 65535)))
    assert "#uicontrol invlerp contrast(range=[100.0, 2000.0], window=[0.0, 65535.0])" in shader
    assert '#uicontrol vec3 color color(default="#00ff00")' in shader
    assert "emitRGBA(vec4(color * value, max(value, 1.0 / 255.0)))" in shader
    assert channel_shader(Channel("b", "#ff00ff")).startswith("#uicontrol invlerp contrast()")


def test_channels_colours_and_window_can_be_overridden(tiles):
    view = Viewer()
    view.add(
        tiles[0], layer="scan", channels=["GFP", "RFP"], colours=["#123456", None], window=(5, 500)
    )
    try:
        layers = view.state["layers"]
    finally:
        view.stop()
    assert [layer["name"] for layer in layers] == ["scan · GFP", "scan · RFP"]
    assert 'color(default="#123456")' in layers[0]["shader"]
    assert 'color(default="#ff33ff")' in layers[1]["shader"]  # the store's own colour stays
    assert all("range=[5.0, 500.0]" in layer["shader"] for layer in layers)


def test_layers_can_be_hidden_removed_and_relaid(tiles):
    view = Viewer(layout="4panel")
    view.add(tiles[0], layer="one")
    view.add(tiles[1])  # its own layer, named after the store
    try:
        assert view.layers == ["one", "tile_01.ome.zarr"]
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
        assert view.state["layers"] == []
    finally:
        view.stop()


def test_showing_a_store_again_or_refreshing_bumps_its_revision(tiles):
    view = Viewer()
    view.add(tiles[0], layer="overview")
    try:
        assert view.state["layers"][0]["_revision"] == 0
        view.add(tiles[0], layer="overview")
        assert view.state["layers"][0]["_revision"] == 1
        assert len(view.state["layers"][0]["source"]) == 1
        view.refresh()
        assert view.state["layers"][0]["_revision"] == 2
    finally:
        view.stop()


# -- serving ---------------------------------------------------------------------


def _get(url: str, headers: dict | None = None):
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status, dict(answer.headers), answer.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def test_the_server_serves_store_bytes_with_ranges_and_the_scene(tiles):
    view = Viewer()
    view.add(tiles[0], layer="overview")
    url = view.start()
    try:
        status, _, body = _get(f"{url}api/state?since=-1")
        assert status == 200
        answer = json.loads(body)
        assert answer["version"] >= 1
        assert answer["state"]["layers"][0]["name"] == "overview · 488"
        assert answer["ui"] == {"transparent": False, "chrome": "full"}

        source = answer["state"]["layers"][0]["source"][0]["url"].split("|")[0]
        status, headers, body = _get(source + ".zattrs")
        assert status == 200 and b"multiscales" in body
        status, headers, whole = _get(source + "0/0.0.0.0.0")
        assert status == 200 and headers["Accept-Ranges"] == "bytes"
        status, headers, part = _get(source + "0/0.0.0.0.0", {"Range": "bytes=10-19"})
        assert status == 206 and part == whole[10:20]
        assert headers["Content-Range"] == f"bytes 10-19/{len(whole)}"
        status, _, _ = _get(source + ".zattrs", {"If-None-Match": headers["ETag"]})
        assert status in (200, 304)
        assert _get(source + "../../etc/passwd")[0] == 404
        assert _get(f"{url}data/99/.zattrs")[0] == 404

        # A change is versioned, and a waiting page is woken by it.
        version = answer["version"]
        started = time.monotonic()
        view.look_at(x=5.0)
        status, _, body = _get(f"{url}api/state?since={version}&wait=5")
        assert time.monotonic() - started < 4
        answer = json.loads(body)
        assert answer["version"] > version
        assert answer["camera"] == {"position": {"x": 5.0}}
    finally:
        view.stop()


def test_reports_from_the_page_come_back_in_micrometres(tiles):
    view = Viewer()
    view.add(tiles[0], layer="overview")
    url = view.start()
    heard = []
    view.on_pick(heard.append)
    try:
        report = {
            "names": ["t", "z", "y", "x"],
            "scales": [1, 5e-6, 1e-6, 1e-6],
            "units": ["s", "m", "m", "m"],
            "position": [0, 4, 30, 200],
        }
        request = urllib.request.Request(
            f"{url}api/pick",
            data=json.dumps(report).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=5).read()
        request = urllib.request.Request(
            f"{url}api/view",
            data=json.dumps(report).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=5).read()
        assert heard == [
            {
                "t": 0.0,
                "z": pytest.approx(20.0),
                "y": pytest.approx(30.0),
                "x": pytest.approx(200.0),
            }
        ]
        assert view.position == heard[0]
    finally:
        view.stop()


# -- the picture -----------------------------------------------------------------

READ_ALPHA = """() => {
  const display = window.viewer.display; display.draw();
  const gl = display.gl, canvas = display.canvas;
  const pixels = new Uint8Array(canvas.width * canvas.height * 4);
  gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  const seen = { clear: 0, opaque: 0, lit: 0 };
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i + 3] === 0) seen.clear++; else if (pixels[i + 3] === 255) seen.opaque++;
    if (pixels[i + 3] === 255 && pixels[i] + pixels[i + 1] + pixels[i + 2] > 60) seen.lit++;
  }
  return seen;
}"""


def test_four_tiles_draw_as_two_channel_layers_over_the_same_sources(pages, tiles):
    view = Viewer()
    for tile in tiles:
        view.add(tile, layer="overview")
    url = view.start()
    picks = []
    view.on_pick(picks.append)
    try:
        page, errors = pages.open(url)
        seen = pages.drawn(page, layers=2)
        assert [layer["name"] for layer in seen["layers"]] == ["overview · 488", "overview · 561"]
        for layer in seen["layers"]:
            assert layer["sources"] == 4 and layer["errors"] == []
            assert layer["channelRank"] == 0, "c is a local dimension, pinned per layer"
        assert seen["names"] == ["t", "z", "y", "x"]
        assert [seen["names"][i] for i in seen["shown"]] == ["x", "y", "z"]
        time.sleep(1.0)
        alpha = page.evaluate(READ_ALPHA)
        assert alpha["clear"] == 0 and alpha["lit"] > 5000, alpha

        # The camera goes where Python says, in micrometres...
        view.look_at(x=100.0, y=50.0)
        deadline = time.time() + 5
        while time.time() < deadline and (view.position or {}).get("x") != pytest.approx(100.0):
            time.sleep(0.1)
        assert view.position["x"] == pytest.approx(100.0) and view.position["y"] == pytest.approx(
            50.0
        )

        # ...and a double-click names the point under the mouse, in micrometres.
        box = page.locator("canvas").first.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        # The engine works out what is under the pointer on its next frame, and
        # drops a double-click it cannot place yet: wait until it can.
        page.wait_for_function("() => window.viewer.mouseState.active", timeout=5000)
        page.mouse.dblclick(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        deadline = time.time() + 5
        while time.time() < deadline and not picks:
            time.sleep(0.1)
        assert picks and picks[0]["x"] == pytest.approx(100.0, abs=1.0)
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_adding_a_tile_keeps_the_operators_adjustments(pages, tiles):
    view = Viewer()
    view.add(tiles[0], layer="overview")
    url = view.start()
    try:
        page, errors = pages.open(url)
        pages.drawn(page, layers=2)
        page.evaluate(
            """() => { const l = window.viewer.layerManager.managedLayers[0].layer;
                      l.opacity.value = 0.3; l.shaderControlState.state.get('color').trackable.restoreState('#0000ff'); }"""
        )
        view.add(tiles[1], layer="overview")
        deadline = time.time() + 20
        while time.time() < deadline:
            seen = pages.describe(page)
            if seen and seen["layers"] and seen["layers"][0]["sources"] == 2:
                break
            time.sleep(0.2)
        held = page.evaluate(
            """() => { const l = window.viewer.layerManager.managedLayers[0].layer;
                      return { opacity: l.opacity.value, colour: l.shaderControlState.state.get('color').trackable.toJSON() }; }"""
        )
        assert held == {"opacity": 0.3, "colour": "#0000ff"}
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_a_store_that_gains_a_time_point_is_read_again(pages, tmp_path):
    store = write_tile(tmp_path / "growing.ome.zarr", origin_um=(0, 0, 0), seed=3, timepoints=1)
    view = Viewer()
    view.add(store, layer="growing")
    url = view.start()
    try:
        page, errors = pages.open(url)
        pages.drawn(page, layers=2)
        extent = "() => { const b = window.viewer.navigationState.position.coordinateSpace.value.bounds; return b.upperBounds[0] - b.lowerBounds[0]; }"
        assert page.evaluate(extent) == 1
        page.evaluate(
            "() => { window.viewer.layerManager.managedLayers[1].layer.shaderControlState.state.get('color').trackable.restoreState('#ff0000'); }"
        )
        # The writer appends a time point in place, then says so.
        write_tile(store, origin_um=(0, 0, 0), seed=3, timepoints=3)
        view.add(store, layer="growing")
        deadline = time.time() + 20
        while time.time() < deadline and page.evaluate(extent) != 3:
            time.sleep(0.25)
        assert page.evaluate(extent) == 3
        pages.drawn(page, layers=2)
        colour = "() => window.viewer.layerManager.managedLayers[1].layer.shaderControlState.state.get('color').trackable.toJSON()"
        assert page.evaluate(colour) == "#ff0000"
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_a_transparent_ground_is_clear_outside_the_tiles_and_opaque_inside(pages, tiles):
    view = Viewer(transparent=True, ui="bare")
    view.add(tiles[0], layer="overview")
    url = view.start()
    try:
        page, errors = pages.open(url)
        pages.drawn(page, layers=2)
        time.sleep(1.0)
        alpha = page.evaluate(READ_ALPHA)
        assert alpha["clear"] > 100_000, alpha
        assert alpha["opaque"] > 100_000, alpha
        assert alpha["lit"] > 5000, alpha
        assert page.evaluate("() => document.documentElement.dataset.chrome") == "bare"
        assert page.evaluate("() => document.querySelector('.neuroglancer-layer-panel')") is None
        assert not errors, errors
        page.close()
    finally:
        view.stop()
