"""The picture: the built page in a headless Chromium, drawing what Python shows.

These tests are about the engine's layers. The one thing the redesign promises
is watched throughout: a layer is made once and then changed in place. A tile
that lands, files that land in a tile, a contrast measured later, a time point
appended -- none of them may make a new engine layer object (which would blank
the picture and reset its controls), and none may make the page ask again for a
chunk it has already drawn. ``pages`` counts both: the layer objects the page
has made, and every file it asks the server for.

They skip, saying so, when the page is not built or no browser is available.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import Channel, Library, PreviewStack, Stack, read_store
from mesoSPIM.src.mesospim_viewer.demo import write_tile

from .conftest import CONTRAST, PICTURE, WHERE
from .stores import GROUND, an_acquisition, land, one_store_per_channel, take_chunks, write_store
from .tools import until

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

# Pixels in a channel's colour (green for 488, magenta for 561): neither the grey
# ground outside the picture, nor the yellow box around it, nor black.
COLOURED_PIXELS = """() => {
  const display = window.viewer.display; display.draw();
  const gl = display.gl, canvas = display.canvas;
  const pixels = new Uint8Array(canvas.width * canvas.height * 4);
  gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let coloured = 0;
  for (let i = 0; i < pixels.length; i += 4) if (Math.abs(pixels[i] - pixels[i + 1]) > 40) coloured++;
  return coloured;
}"""

# The middle of the canvas, in blocks: each block's mean green (the 488 channel)
# and magenta (561), so two pictures can be compared place by place.
READ_BLOCKS = """(share) => {
  const display = window.viewer.display; display.draw();
  const gl = display.gl, canvas = display.canvas;
  const w = canvas.width, h = canvas.height;
  const pixels = new Uint8Array(w * h * 4);
  gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  const n = 8, x0 = Math.round(w * (1 - share) / 2), y0 = Math.round(h * (1 - share) / 2);
  const bw = Math.floor(w * share / n), bh = Math.floor(h * share / n);
  const blocks = [];
  for (let by = 0; by < n; by++) for (let bx = 0; bx < n; bx++) {
    let green = 0, magenta = 0;
    for (let y = y0 + by * bh; y < y0 + (by + 1) * bh; y++) for (let x = x0 + bx * bw; x < x0 + (bx + 1) * bw; x++) {
      const i = (y * w + x) * 4;
      green += pixels[i + 1]; magenta += (pixels[i] + pixels[i + 2]) / 2;
    }
    blocks.push([green / (bw * bh), magenta / (bw * bh)]);
  }
  return blocks;
}"""

CAMERA = """() => { const n = window.viewer.navigationState;
  return { position: Array.from(n.position.value), zoom: n.zoomFactor.value }; }"""

SET_CAMERA = """(camera) => { const n = window.viewer.navigationState;
  n.position.value = Float32Array.from(camera.position); n.zoomFactor.value = camera.zoom; }"""

# What the operator may have adjusted on the first layer.
ADJUST = """() => { const l = window.viewer.layerManager.managedLayers[0].layer;
  l.opacity.value = 0.3; l.shaderControlState.state.get('color').trackable.restoreState('#0000ff'); }"""
ADJUSTED = """() => { const l = window.viewer.layerManager.managedLayers[0].layer;
  return { opacity: l.opacity.value, colour: l.shaderControlState.state.get('color').trackable.toJSON() }; }"""

SOURCES = "() => window.viewer.layerManager.managedLayers.map(m => m.layer.dataSources.length)"

# What the very middle of the picture shows, as a voxel value: for a white channel
# whose contrast runs from 0 to `top`.
READ_MIDDLE = """(top) => {
  const display = window.viewer.display; display.draw();
  const box = document.querySelector('.neuroglancer-rendered-data-panel').getBoundingClientRect();
  const canvas = display.canvas.getBoundingClientRect();
  const x = Math.round(box.left + box.width / 2 - canvas.left);
  const y = Math.round(display.canvas.height - (box.top + box.height / 2 - canvas.top));
  const pixel = new Uint8Array(4);
  display.gl.readPixels(x, y, 1, 1, display.gl.RGBA, display.gl.UNSIGNED_BYTE, pixel);
  return pixel[1] / 255 * top;
}"""


def _camera_settles(page, *, timeout_s: float = 10.0) -> dict:
    """The camera once it has stopped moving for half a second."""
    deadline = time.time() + timeout_s
    seen = page.evaluate(CAMERA)
    while time.time() < deadline:
        time.sleep(0.5)
        now = page.evaluate(CAMERA)
        if now == seen:
            return now
        seen = now
    return seen


def _asked_twice(pages, page, drawn_before: set[str], since: int) -> list[str]:
    """The chunks the page had been given before, and has asked for again since."""
    return sorted(set(pages.chunks_asked(page, since)) & drawn_before)


# -- stores in, a picture out ----------------------------------------------------------


def test_four_tiles_draw_as_two_channel_layers_over_the_same_sources(pages, viewers, tiles):
    view = viewers()
    for tile in tiles:
        view.add(tile, layer="overview")
    url = view.start()
    picks = []
    view.on_pick(picks.append)
    page, errors = pages.open(url)
    seen = pages.drawn(page, layers=2)
    assert [layer["name"] for layer in seen["layers"]] == ["overview · 488", "overview · 561"]
    for layer in seen["layers"]:
        assert layer["sources"] == 4 and layer["errors"] == []
        assert layer["channelRank"] == 0, "c is a local dimension, pinned per layer"
    assert sorted(seen["names"]) == ["t", "x", "y", "z"]
    assert [seen["names"][i] for i in seen["shown"]] == ["x", "y", "z"]
    assert pages.layer_objects(page)["made"] == 2
    time.sleep(1.0)
    alpha = page.evaluate(READ_ALPHA)
    assert alpha["clear"] == 0 and alpha["lit"] > 5000, alpha

    # The camera goes where Python says, in micrometres...
    view.look_at(x=100.0, y=50.0)
    until(lambda: view.position, lambda at: (at or {}).get("x") == pytest.approx(100.0), 5)
    assert view.position["x"] == pytest.approx(100.0) and view.position["y"] == pytest.approx(50.0)

    # ...and a double-click names the point under the mouse, in micrometres.
    box = page.locator("canvas").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    # The engine works out what is under the pointer on its next frame, and
    # drops a double-click it cannot place yet: wait until it can.
    page.wait_for_function("() => window.viewer.mouseState.active", timeout=5000)
    page.mouse.dblclick(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    until(lambda: picks, timeout_s=5)
    assert picks and picks[0]["x"] == pytest.approx(100.0, abs=1.0)
    assert not errors, errors


@pytest.mark.parametrize(
    ("axes", "version"), [("zyx", "0.4"), ("zyx", "0.5"), ("czyx", "0.5"), ("tzyx", "0.4")]
)
def test_the_engine_draws_each_layout(pages, viewers, tmp_path, axes, version):
    view = viewers()
    view.add(write_store(tmp_path / "tile.ome.zarr", axes=axes, version=version), layer="tile")
    page, errors = pages.open(view.start())
    seen = pages.drawn(page, layers=2 if "c" in axes else 1)
    for layer in seen["layers"]:
        assert layer["errors"] == [] and layer["sources"] == 1
    assert sorted(n for n in seen["names"] if n in "tzyx") == sorted(a for a in axes if a != "c")
    assert [seen["names"][i] for i in seen["shown"]] == ["x", "y", "z"]
    assert page.evaluate(PICTURE)["lit"] > 5000
    assert not errors, errors


def test_the_engine_draws_one_store_per_channel_as_two_channels(pages, viewers, tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    one_store_per_channel(acquisition, version="0.5")
    view = viewers()
    for path in sorted(acquisition.glob("*.ome.zarr")):
        view.add(path, layer="run", channel=read_store(path).channels[0])
    page, errors = pages.open(view.start())
    seen = pages.drawn(page, layers=2)
    assert [layer["name"] for layer in seen["layers"]] == ["run · 488", "run · 561"]
    for layer in seen["layers"]:
        assert layer["errors"] == [] and layer["sources"] == 2
    time.sleep(0.5)
    assert not errors, errors


def test_a_transparent_ground_is_clear_outside_the_tiles_and_opaque_inside(pages, viewers, tiles):
    view = viewers(transparent=True, ui="bare")
    view.add(tiles[0], layer="overview")
    page, errors = pages.open(view.start())
    pages.drawn(page, layers=2)
    time.sleep(1.0)
    alpha = page.evaluate(READ_ALPHA)
    assert alpha["clear"] > 100_000, alpha
    assert alpha["opaque"] > 100_000, alpha
    assert alpha["lit"] > 5000, alpha
    assert page.evaluate("() => document.documentElement.dataset.chrome") == "bare"
    assert page.evaluate("() => document.querySelector('.neuroglancer-layer-panel')") is None
    assert not errors, errors


def test_a_tile_among_others_draws_as_it_does_alone(pages, viewers, tiles):
    """Every tile of a layer is drawn the same way, not only the first one.

    The engine draws each tile of a layer separately, the first straight onto
    the empty picture and every later one over what is already there. Tile 1
    is shown alone, then as the second of four, with the same camera: the
    middle of the tile, away from the overlaps, must look the same.
    """
    pictures = []
    camera = None
    for shown in ([tiles[1]], tiles):
        view = viewers(ui="bare")
        for tile in shown:
            view.add(tile, layer="overview")
        page, errors = pages.open(view.start())
        pages.drawn(page, layers=2)
        if camera is None:
            view.look_at(x=144.0 + 80.0, y=80.0, z=12 * 5.0)  # the middle of tile 1
            time.sleep(1.0)
            camera = page.evaluate(CAMERA)
        else:
            page.evaluate(SET_CAMERA, camera)
        pages.drawn(page, layers=2)
        time.sleep(1.0)
        pictures.append(page.evaluate(READ_BLOCKS, 0.5))
        assert not errors, errors
        page.close()
    alone, among = pictures
    assert sum(green > 5 for green, _ in alone) > 5, alone
    for i in range(len(alone)):
        for channel in (0, 1):
            assert among[i][channel] == pytest.approx(alone[i][channel], abs=3.0), (
                f"block {i}: alone {alone[i]}, among others {among[i]}"
            )


# -- a layer is changed in place, never rebuilt ----------------------------------------------


def test_adding_a_tile_keeps_the_operators_adjustments(pages, viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    page, errors = pages.open(view.start())
    pages.drawn(page, layers=2)
    before = pages.layer_objects(page)
    page.evaluate(ADJUST)
    view.add(tiles[1], layer="overview")
    pages.drawn(page, layers=2, sources=2)
    assert page.evaluate(ADJUSTED) == {"opacity": 0.3, "colour": "#0000ff"}
    assert pages.layer_objects(page) == before, "the same two layer objects as before"
    assert not errors, errors


def test_nothing_that_happens_to_an_acquisition_rebuilds_a_layer_or_reads_a_drawn_chunk_again(
    pages, viewers, tiles, tmp_path
):
    """The regression the redesign is for. An acquisition is shown, and then, as in
    a run: a tile lands, files land in a tile that was shown half written, another
    tile lands, the contrast is given later. Through all of it the page keeps
    the two layer objects it made first, and asks for no chunk a second time
    that it has been given once."""
    half = write_tile(tmp_path / "half.ome.zarr", origin_um=(0, 144, 0), seed=7)
    late = take_chunks(half, lambda chunk: int(chunk.name.split(".")[2]) >= 12)  # planes 12 and up, every copy
    plain = write_store(tmp_path / "plain.ome.zarr")  # an acquisition whose contrast is not known yet
    waiting = take_chunks(plain)
    view = viewers(ui="simple")
    view.add(tiles[0], layer="run")
    view.add(plain, layer="plain")
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=4)
    made = pages.layer_objects(page)
    assert made["made"] == 4 and sorted(made["now"]) == ["plain · 488", "plain · 561", "run · 488", "run · 561"]
    page.evaluate(ADJUST)

    def step(what: str, change, *, sources: list[int]) -> list[str]:
        """Do one thing; return the files the page asked for because of it."""
        given, since = pages.chunks_read(page), len(pages.asked(page))
        change()
        until(lambda: page.evaluate(SOURCES), lambda seen: seen == sources, 20)
        assert page.evaluate(SOURCES) == sources, what
        time.sleep(0.5)  # the engine asks for what it now needs on its next frames
        pages.drawn(page, layers=4)
        assert pages.layer_objects(page) == made, f"{what}: a layer was rebuilt"
        assert _asked_twice(pages, page, given, since) == [], f"{what}: drawn chunks were read again"
        assert page.evaluate(ADJUSTED) == {"opacity": 0.3, "colour": "#0000ff"}, what
        return pages.asked(page)[since:]

    asked = step("a tile lands", lambda: view.add(tiles[1], layer="run"), sources=[2, 2, 1, 1])
    assert asked and all(path.startswith("data/2/") for path in asked), "only the new tile is read"

    asked = step("a half-written tile is shown", lambda: view.add(half, layer="run"), sources=[3, 3, 1, 1])
    assert asked and all(path.startswith("data/3/") for path in asked)

    asked = step("its files land", lambda: view.landed(half, land(late, half)), sources=[3, 3, 1, 1])
    assert asked and all(path.startswith("data/3/") for path in asked)
    assert {path.removeprefix("data/3/") for path in asked} <= {
        path.relative_to(half).as_posix() for path in late
    }, "exactly the files that were named"

    asked = step("the other acquisition's files land", lambda: view.landed(plain, land(waiting, plain)), sources=[3, 3, 1, 1])
    assert asked and all(path.startswith("data/1/") for path in asked)

    assert view.measure("plain") is True
    measured = view.scene["layers"][2]["shaderControls"]["contrast"]["range"]
    asked = step("a contrast is measured later", lambda: None, sources=[3, 3, 1, 1])
    assert asked == [], "a control moved: nothing to read"
    at_measured = lambda seen: seen == pytest.approx(measured, abs=1)  # the control holds whole counts
    assert at_measured(until(lambda: page.evaluate(CONTRAST)["plain · 488"]["range"], at_measured, 10)), "moved in place"

    asked = step("one more tile lands", lambda: view.add(tiles[2], layer="run"), sources=[4, 4, 1, 1])
    assert asked and all(path.startswith("data/4/") for path in asked)
    assert pages.layer_objects(page)["made"] == 4, "four layers were made when the page opened, and none since"
    assert not errors, errors


def test_a_store_shown_before_its_chunks_landed_draws_them_once_they_are_named(pages, viewers, tmp_path):
    """What the live window does for every stack: the store is shown the moment the
    writer has made its arrays, when every chunk is still missing, and the page
    is told which files have landed. It reads exactly those: the layer is not
    rebuilt, and a chunk that is still missing is not asked for again."""
    store = write_tile(tmp_path / "landing.ome.zarr", origin_um=(0, 0, 0), seed=3)
    chunks = take_chunks(store)
    first = {path: data for path, data in chunks.items() if path.name.startswith("0.0.")}  # the 488 channel
    rest = {path: data for path, data in chunks.items() if path not in first}
    view = viewers(ui="bare")
    view.add(store, layer="landing")
    page, errors = pages.open(view.start())
    pages.drawn(page, layers=2)
    time.sleep(1.0)
    made = pages.layer_objects(page)
    missing = pages.chunks_asked(page)
    assert missing and pages.chunks_read(page) == set(), "everything the picture needs was asked for, and is not there"
    assert len(missing) == len(set(missing)), "each once"
    # Only the engine's red axis line is coloured while nothing is on disk.
    assert page.evaluate(COLOURED_PIXELS) < 2000, "nothing on disk, nothing drawn"

    since = len(pages.asked(page))
    view.landed(store, land(first, store))
    coloured = until(lambda: page.evaluate(COLOURED_PIXELS), lambda seen: seen > 5000, 20, 0.5)
    assert coloured > 5000, "the chunks that landed are not drawn"
    pages.drawn(page, layers=2)
    again = pages.chunks_asked(page, since)
    assert again and len(again) == len(set(again))
    assert set(again) == {path for path in missing if "/0.0." in path}, "the ones that landed, of those it needs"
    assert all("/0.1." not in path for path in again), "what is still missing is not asked for again"
    assert pages.layer_objects(page) == made, "the layer was not rebuilt"

    # Without names -- a writer that does not say what it wrote -- everything
    # found missing is read again, and nothing that was drawn.
    since, given = len(pages.asked(page)), pages.chunks_read(page)
    land(rest)
    view.landed(store)
    until(lambda: pages.chunks_asked(page, since), lambda seen: len(seen) >= len(missing) - len(again), 20)
    pages.drawn(page, layers=2)
    assert set(pages.chunks_asked(page, since)) == set(missing) - set(again)
    assert set(pages.chunks_asked(page, since)) & given == set()
    assert pages.layer_objects(page) == made
    assert not errors, errors


def test_a_store_that_gains_a_time_point_is_the_only_source_read_again(pages, viewers, tiles, tmp_path):
    store = write_tile(tmp_path / "growing.ome.zarr", origin_um=(0, 0, 0), seed=3, timepoints=1)
    view = viewers()
    view.add(store, layer="growing")
    view.add(tiles[1], layer="growing")
    page, errors = pages.open(view.start())
    pages.drawn(page, layers=2, sources=2)
    made = pages.layer_objects(page)
    extent = """() => { const s = window.viewer.navigationState.position.coordinateSpace.value;
                        const t = s.names.indexOf('t'); return s.bounds.upperBounds[t] - s.bounds.lowerBounds[t]; }"""
    assert page.evaluate(extent) == 1
    page.evaluate(ADJUST)
    # The writer appends time points in place; the store is shown again.
    write_tile(store, origin_um=(0, 0, 0), seed=3, timepoints=3)
    since = len(pages.asked(page))
    view.add(store, layer="growing")
    assert until(lambda: page.evaluate(extent), lambda seen: seen == 3, 20) == 3
    pages.drawn(page, layers=2, sources=2)
    asked = pages.asked(page)[since:]
    assert asked and all(path.startswith("data/0.1/") for path in asked), "the other tile is left alone"
    assert pages.layer_objects(page) == made, "the layers are the ones made first"
    assert page.evaluate(ADJUSTED) == {"opacity": 0.3, "colour": "#0000ff"}
    assert not errors, errors


# -- framing: the view takes in what lands, until the operator moves it ------------------------------


def test_the_view_refits_as_tiles_arrive_until_the_operator_moves_it(pages, viewers, tiles):
    view = viewers(ui="simple")
    view.add(tiles[0], layer="run")
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    one = _camera_settles(page)
    x, y = (page.evaluate(DESCRIBE_NAMES).index(name) for name in "xy")

    # A second tile lands to the right: the view widens to show both.
    view.add(tiles[1], layer="run")
    pages.drawn(page, layers=2, sources=2)
    two = _camera_settles(page)
    assert two["zoom"] > one["zoom"] * 1.3, (one, two)
    assert two["position"][x] == pytest.approx((0 + 144 + 160) / 2, abs=2)  # between both
    assert page.evaluate("() => window.mesospim.framing.value") is True

    # The operator zooms in with the mouse wheel: from now on the view is theirs.
    box = page.locator(".neuroglancer-rendered-data-panel").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -300)
    theirs = _camera_settles(page)
    assert theirs["zoom"] < two["zoom"]
    assert page.evaluate("() => window.mesospim.framing.value") is False
    view.add(tiles[2], layer="run")
    pages.drawn(page, layers=2, sources=3)
    assert _camera_settles(page) == theirs

    # Asking for a fit hands the view back: it frames everything and follows again.
    view.fit()
    refit = _camera_settles(page)
    assert refit["zoom"] > theirs["zoom"]
    view.add(tiles[3], layer="run")
    pages.drawn(page, layers=2, sources=4)
    four = _camera_settles(page)
    assert four["position"][x] == pytest.approx((0 + 144 + 160) / 2, abs=2)
    assert four["position"][y] == pytest.approx((0 + 144 + 160) / 2, abs=12), "between both rows, clear of the sliders"
    assert not errors, errors


DESCRIBE_NAMES = "() => Array.from(window.viewer.navigationState.position.coordinateSpace.value.names)"


# -- one acquisition in place of another ------------------------------------------------------------------


def test_a_new_acquisition_elsewhere_is_framed_when_it_takes_the_place_of_the_last(pages, viewers, tmp_path):
    """What happens at the microscope with every run after the first: the library
    takes the last acquisition off, asks for a fit, and adds the tiles of the
    new one, which lies wherever the stage now is."""
    write_tile(an_acquisition(tmp_path, "run_a") / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path)
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    assert page.evaluate(WHERE)["um"]["x"] == pytest.approx(80, abs=2)

    time.sleep(0.05)
    write_tile(an_acquisition(tmp_path, "run_b") / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 3000), seed=2)
    library.poll()
    assert library.shown == ["run_b"]
    page.wait_for_function("() => window.viewer.layerManager.managedLayers[0]?.name.startsWith('run_b')")
    over_it = lambda x: x == pytest.approx(3080, abs=5)
    assert over_it(until(lambda: page.evaluate(WHERE)["um"].get("x"), over_it, 15)), (
        "the view is not over the new acquisition (it lies from x = 3000 to 3160 um)"
    )
    pages.drawn(page, layers=2, timeout_s=15)
    assert page.evaluate(PICTURE)["lit"] > 3000
    assert page.evaluate("() => window.mesospim.framing.value") is True, "and it goes on framing what lands"
    assert not errors, errors


def test_replacing_every_layer_in_one_scene_keeps_the_view_on_the_picture(pages, viewers, stacks):
    """One acquisition goes and another comes, and the page hears of both at once --
    as it does whenever it asks a moment late. The picture's space must come out
    right all the same, with the view inside it."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run_01")
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    before = pages.drawn(page, layers=2)
    assert before["names"] == ["x", "y", "z", "t"]
    with view._server.scene._changed:  # nobody is answered until both are done
        view.remove("run_01")
        view.add(stacks[0], layer="run_02")
    page.wait_for_function("() => window.viewer.layerManager.managedLayers[0]?.name.startsWith('run_02')")
    time.sleep(1.0)
    after = pages.describe(page)
    where = page.evaluate(WHERE)["voxels"]
    assert 0 <= where["z"] <= 23 and 0 <= where["t"] <= 2, (
        f"the view is outside the stack: {where}, in a space of {after['names']} (it was {before['names']})"
    )
    pages.drawn(page, layers=2, timeout_s=15)
    assert page.evaluate(PICTURE)["lit"] > 3000
    assert not errors, errors


# -- following: the view goes to the newest plane, until the operator steps away -----------------------

FOLLOWING = """() => {
  const live = document.querySelector('#live');
  return { following: window.mesospim.following.value, acquiring: window.mesospim.acquiring.value,
           button: live.hidden ? null : live.querySelector('.text').textContent };
}"""


def _plane(page) -> dict:
    """The plane and time point on screen."""
    voxels = page.evaluate(WHERE)["voxels"]
    return {"z": round(voxels["z"]), "t": round(voxels.get("t", 0))}


def test_the_view_follows_the_newest_plane_until_the_operator_steps_away(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")  # 24 planes of 5 um, three time points
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    assert page.evaluate(FOLLOWING) == {"following": True, "acquiring": False, "button": None}

    # Python says where the newest plane is: the view goes there, and says it is live.
    view.look_at_newest(z=50.0, t=1.0)
    assert until(lambda: _plane(page), lambda at: at == {"z": 10, "t": 1}) == {"z": 10, "t": 1}
    assert page.evaluate(FOLLOWING) == {"following": True, "acquiring": True, "button": "Live"}
    view.look_at_newest(z=75.0, t=1.0)
    assert until(lambda: _plane(page), lambda at: at["z"] == 15) == {"z": 15, "t": 1}

    # The operator steps to another plane: the view is theirs, and stays.
    page.evaluate(
        "() => { const i = document.querySelector('#slider-z input'); i.value = '3'; i.dispatchEvent(new Event('input')); }"
    )
    assert page.evaluate(FOLLOWING) == {"following": False, "acquiring": True, "button": "Back to live"}
    view.look_at_newest(z=100.0, t=1.0)
    time.sleep(1.0)
    assert _plane(page) == {"z": 3, "t": 1}, "the planes keep coming, the view stays where it was put"

    # Live takes it back to the newest plane, and it follows again.
    page.click("#live")
    assert until(lambda: _plane(page), lambda at: at["z"] == 20) == {"z": 20, "t": 1}
    assert page.evaluate(FOLLOWING) == {"following": True, "acquiring": True, "button": "Live"}
    view.look_at_newest(z=105.0, t=2.0)
    assert until(lambda: _plane(page), lambda at: at == {"z": 21, "t": 2}) == {"z": 21, "t": 2}

    # Nothing is running any more: the button goes, the view stays.
    view.look_at_newest()
    assert until(lambda: page.evaluate(FOLLOWING), lambda seen: not seen["acquiring"])["button"] is None
    assert _plane(page) == {"z": 21, "t": 2}
    assert not errors, errors


def test_stepping_through_time_also_ends_following_and_panning_does_not(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    view.look_at_newest(z=50.0, t=2.0)
    until(lambda: _plane(page), lambda at: at == {"z": 10, "t": 2})
    # Zooming into the tile being acquired does not stop the planes from coming.
    box = page.locator(".neuroglancer-rendered-data-panel").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -300)
    until(lambda: page.evaluate("() => window.mesospim.framing.value"), lambda framing: framing is False)
    assert page.evaluate(FOLLOWING)["following"] is True
    view.look_at_newest(z=60.0, t=2.0)
    assert until(lambda: _plane(page), lambda at: at["z"] == 12)["z"] == 12
    # Stepping back in time does.
    page.evaluate(
        "() => { const i = document.querySelector('#slider-t input'); i.value = '0'; i.dispatchEvent(new Event('input')); }"
    )
    assert page.evaluate(FOLLOWING) == {"following": False, "acquiring": True, "button": "Back to live"}
    # A new run is followed from its start, whatever was done during the last.
    view.look_at_newest()
    until(lambda: page.evaluate(FOLLOWING), lambda seen: not seen["acquiring"])
    view.look_at_newest(z=5.0, t=0.0)
    assert until(lambda: page.evaluate(FOLLOWING), lambda seen: seen["acquiring"])["following"] is True
    assert until(lambda: _plane(page), lambda at: at["z"] == 1) == {"z": 1, "t": 0}
    assert not errors, errors


# -- a stack shown from memory, plane by plane -----------------------------------------------------------


def _numbered_frame(z: int, size: int = 64) -> np.ndarray:
    """A frame whose every pixel says which plane it is: 1000 for the first, 200 more for each."""
    return np.full((size, size), 1000 + 200 * z, np.uint16)


def _a_preview(view, planes: int = 12) -> tuple[PreviewStack, str]:
    stack = Stack(
        acquisition="run", channel="488", channels=("488",), planes=planes, frame=(64, 64),
        voxel_um=(5.0, 1.0, 1.0), origin_um=(0.0, 0.0, 0.0),
    )
    preview = PreviewStack(stack)
    name = view.add_preview("run", preview, Channel("488", "#ffffff"))
    view.set_window("run", "488", (0, 5000))
    return preview, name


def test_a_preview_fed_plane_by_plane_is_drawn_and_never_blinks_between_planes(pages, viewers):
    """Following a stack as the camera delivers it: each new plane is announced
    with the chunk that holds it, and the view steps there only once that chunk
    can be drawn. Sampled a few times a plane, the middle of the picture always
    shows the plane the view is on: never the black of a plane not loaded yet."""
    view = viewers(ui="simple")
    preview, name = _a_preview(view)
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=1)
    made = pages.layer_objects(page)
    seen = []
    for z in range(12):
        view.preview_landed(name, preview.add(z, _numbered_frame(z)))
        view.look_at_newest(z=preview.newest_um, t=0.0, preview=name, chunk=[0, 0, z, 0, 0])
        deadline = time.time() + 0.6
        while time.time() < deadline:
            at, value = _plane(page)["z"], page.evaluate(READ_MIDDLE, 5000)
            if _plane(page)["z"] == at:  # the view did not step between the two looks
                seen.append((at, round(value)))
    until(lambda: _plane(page), lambda at: at["z"] == 11, 5)
    seen.append((_plane(page)["z"], round(page.evaluate(READ_MIDDLE, 5000))))
    # Before the first plane arrived the view sat in the middle of the empty stack;
    # from the first plane on, what is on screen is the plane the view is on.
    first = next(i for i, (at, value) in enumerate(seen) if at == 0 and value > 0)
    drawn = seen[first:]
    planes = [at for at, _ in drawn]
    assert planes == sorted(planes) and planes[-1] == 11, "forward, to the last plane"
    assert len(set(planes)) >= 8, f"most planes were on screen in their turn: {sorted(set(planes))}"
    assert len(drawn) > 20
    wrong = [(at, value) for at, value in drawn if abs(value - (1000 + 200 * at)) > 60]
    assert wrong == [], f"planes on screen that were not drawn (plane, value): {wrong}"
    assert pages.layer_objects(page) == made
    assert all(path.startswith(f"live/{name}/") for path in pages.asked(page))
    assert not errors, errors


def test_a_finished_stack_is_handed_from_its_preview_to_the_tile_without_a_gap(pages, viewers, tmp_path):
    tile = write_tile(tmp_path / "tile.ome.zarr", origin_um=(0, 0, 0), seed=1)
    view = viewers(ui="simple")
    view.add(tile, layer="run")
    # While the stack is being written the page gets none of its files...
    view.guard(tile, lambda file: file.rsplit("/", 1)[-1][0].isdigit())
    # ...and shows the stack from memory instead.
    stack = Stack(
        acquisition="run", channel="488", channels=("488", "561"), planes=24, frame=(160, 160),
        voxel_um=(5.0, 1.0, 1.0), origin_um=(0.0, 0.0, 0.0),
    )
    preview = PreviewStack(stack)
    name = view.add_preview("run", preview, Channel("488"))
    for z in range(24):
        view.preview_landed(name, preview.add(z, np.full((160, 160), 9000, np.uint16)))
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    made = pages.layer_objects(page)
    assert page.evaluate(SOURCES) == [2, 1]
    assert pages.chunks_read(page) and all(path.startswith(f"live/{name}/") for path in pages.chunks_read(page))
    lit = page.evaluate(PICTURE)["lit"]
    assert lit > 20_000, "the preview is on screen"

    # The stack is whole on disk: its files are let through and named, and the preview retired.
    view.guard(tile, None)
    view.landed(tile)
    view.retire_preview(name)
    samples = []
    deadline = time.time() + 15
    while time.time() < deadline and page.evaluate(SOURCES) != [1, 1]:
        samples.append(page.evaluate(PICTURE)["lit"])
        time.sleep(0.1)
    assert page.evaluate(SOURCES) == [1, 1], "the page lets the preview go once the tile is drawn"
    samples.append(page.evaluate(PICTURE)["lit"])
    assert min(samples) > 5000, f"the stack dropped out of the picture during the hand-over: {samples}"
    assert any(path.startswith("data/0/") for path in pages.chunks_read(page))
    # Python lets the preview's memory go a while later: nothing changes on screen.
    view.remove_preview(name)
    time.sleep(1.0)
    pages.drawn(page, layers=2, sources=1)
    assert pages.layer_objects(page) == made
    assert page.evaluate(PICTURE)["lit"] > 5000
    assert not errors, errors


# -- contrast that sets itself --------------------------------------------------------------------------------


def _an_acquisition_nobody_knows_the_brightness_of(view, tmp_path, *, leave_out=lambda chunk: False):
    """A store shown when it held nothing, so that no window was measured, and filled since.
    ``leave_out`` picks chunks that stay missing: the engine counts those as zeros."""
    store = write_store(tmp_path / "plain.ome.zarr")
    taken = take_chunks(store)
    view.add(store, layer="run")
    land({path: data for path, data in taken.items() if not leave_out(path)})
    assert all("contrast" not in layer["shaderControls"] and layer["_auto"] for layer in view.scene["layers"])
    return store


def test_a_channel_without_a_window_gets_its_contrast_from_what_is_on_screen(pages, viewers, tmp_path):
    view = viewers(ui="simple")
    # A strip of the picture is not written yet: zeros to the engine, and not data.
    _an_acquisition_nobody_knows_the_brightness_of(
        view, tmp_path, leave_out=lambda chunk: chunk.name.endswith(".2")
    )
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    start = page.evaluate(CONTRAST)
    assert all(channel["auto"] for channel in start.values())
    settled = until(
        lambda: page.evaluate(CONTRAST),
        lambda seen: all(channel["range"][1] < 30000 for channel in seen.values()),
        timeout_s=15,
        every_s=0.5,
    )
    # The pretend cells sit on a ground of 400 and peak at 12400.
    for name, channel in settled.items():
        low, high = channel["range"]
        assert GROUND * 0.5 <= low <= GROUND * 2, f"{name}: the black point is the ground, not the zeros: {channel}"
        assert 2000 < high <= 12400 * 1.2, f"{name}: the white point is just above the brightest cells: {channel}"
    assert page.evaluate(PICTURE)["lit"] > 3000, "and the picture is not black"
    assert not errors, errors


def test_auto_also_measures_a_picture_that_stands_still(pages, viewers, tmp_path):
    """Once the tiles are drawn nothing moves on screen, so the engine draws no
    further frame of its own accord. The contrast has to be measured all the
    same: an acquisition opened from disk is exactly such a picture.

    The histogram's span is put at one here, above the zeros, so that the first
    measurement can count at once: what is tested is only that it happens."""
    view = viewers(ui="simple")
    _an_acquisition_nobody_knows_the_brightness_of(view, tmp_path)
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    time.sleep(1.0)
    page.evaluate(
        """() => { for (const m of window.viewer.layerManager.managedLayers) {
          m.layer.shaderControlState.state.get('contrast').trackable.restoreState({ range: [0, 65535], window: [1, 65535] }); } }"""
    )
    settled = until(
        lambda: page.evaluate(CONTRAST),
        lambda seen: all(channel["range"][1] < 30000 for channel in seen.values()),
        timeout_s=12,
        every_s=0.5,
    )
    assert all(channel["auto"] for channel in settled.values())
    for name, channel in settled.items():
        assert channel["range"][1] < 30000, f"{name} was never measured: {channel}"
    assert not errors, errors


def test_moving_the_contrast_by_hand_ends_auto_and_the_auto_button_brings_it_back(pages, viewers, tmp_path):
    view = viewers(ui="simple")
    _an_acquisition_nobody_knows_the_brightness_of(view, tmp_path)
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    row = '.channel[data-layer="run · 488"]'
    buttons = "() => [...document.querySelectorAll('.channel .auto')].map(b => b.classList.contains('on'))"
    page.wait_for_selector(f"{row} .neuroglancer-invlerp-widget")
    assert page.evaluate(buttons) == [True, True]
    # A press inside the engine's own window control: the operator is setting the contrast.
    widget = page.locator(f"{row} .neuroglancer-invlerp-widget").first.bounding_box()
    page.mouse.move(widget["x"] + widget["width"] / 2, widget["y"] + widget["height"] / 2)
    page.mouse.down()
    page.mouse.up()
    assert until(lambda: page.evaluate(buttons), lambda on: on == [False, True]) == [False, True]
    auto = {name: channel["auto"] for name, channel in page.evaluate(CONTRAST).items()}
    assert auto == {"run · 488": False, "run · 561": True}, "only the channel that was touched"
    theirs = page.evaluate(CONTRAST)["run · 488"]["range"]
    # Python saying the run is being written does not take it back from them.
    view.set_auto("run", True)
    time.sleep(1.0)
    assert page.evaluate(CONTRAST)["run · 488"] | {"window": None} == {"auto": False, "range": theirs, "window": None}
    # The Auto button in the row does.
    page.click(f"{row} .auto")
    assert page.evaluate(buttons) == [True, True]
    assert page.evaluate("() => window.mesospim.isAuto('run · 488')") is True
    page.click(f"{row} .auto")
    assert page.evaluate(buttons) == [False, True], "and it switches off again"
    assert not errors, errors


def test_python_switches_auto_on_while_a_run_is_written_and_off_after(pages, viewers, tiles):
    view = viewers(ui="simple")
    view.add(tiles[0], layer="run")  # its store names a window
    view.fit()
    page, errors = pages.open(view.start(), width=1100, height=700)
    pages.drawn(page, layers=2)
    auto = lambda: [channel["auto"] for channel in page.evaluate(CONTRAST).values()]
    assert auto() == [False, False]
    view.set_auto("run", True)
    assert until(auto, lambda on: on == [True, True]) == [True, True]
    view.set_auto("run", False)
    assert until(auto, lambda on: on == [False, False]) == [False, False]
    assert pages.layer_objects(page)["made"] == 2
    assert not errors, errors
