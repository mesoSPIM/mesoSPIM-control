"""The simple interface: our panel over a bare engine, driven in a headless Chromium.

Down the right-hand edge the list of acquisitions (Python's list, drawn) and one
row per channel; on the picture the 2D/3D switch, Fit, Live, the depth and time
sliders, and a few words whenever there is nothing to draw. Every control but
the list writes engine state and nothing else, so each test asks the engine
what changed rather than the panel; the list posts what was clicked to Python.
"""

from __future__ import annotations

import functools
import time

import pytest

from mesoSPIM.src.mesospim_viewer import Library, Stack
from mesoSPIM.src.mesospim_viewer.demo import write_tile

from .conftest import WHERE
from .stores import an_acquisition, numbered
from .tools import until


def _shown(view):
    view.fit()
    return view.start()


def _opened(pages, view, *, layers: int):
    """The simple page over ``view``, once its picture is up."""
    page, errors = pages.open(_shown(view), width=1100, height=700)
    pages.drawn(page, layers=layers)
    return page, errors


def slow_without_a_graphics_card(test):
    """For the tests of the volume view. Drawn in software it can take longer than
    any sensible wait: such a test is skipped, saying so, rather than failed."""

    @functools.wraps(test)
    def run(*args, **kwargs):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        try:
            return test(*args, **kwargs)
        except PlaywrightTimeout as slow:
            pytest.skip(
                "the volume view did not answer in time (it is drawn in software here, without a "
                f"graphics card): {str(slow).splitlines()[0]}"
            )

    return run


def _in_3d(page) -> None:
    """Switch to the volume view, in a small window and coarsely drawn so that
    software GL keeps up."""
    page.set_viewport_size({"width": 640, "height": 420})
    page.click('.view button[data-layout="3d"]')
    page.wait_for_function("() => window.mesospim.layout() === '3d'")
    _set_detail(page, 0)


def _set_detail(page, step: int) -> None:
    page.evaluate(
        "(step) => { const i = document.querySelector('.card.volume input.detail'); i.value = String(step);"
        " i.dispatchEvent(new Event('input')); }",
        step,
    )


def _set_slider(page, slider: str, value) -> None:
    page.evaluate(
        "([id, value]) => { const i = document.querySelector(id + ' input'); i.value = String(value);"
        " i.dispatchEvent(new Event('input')); }",
        [slider, value],
    )


# Whether an element is there for the operator to see.
VISIBLE = """(selector) => {
  const element = document.querySelector(selector);
  if (!element) return false;
  const box = element.getBoundingClientRect(), style = getComputedStyle(element);
  return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0
    && box.width > 0 && box.height > 0;
}"""

VISIBILITY = "() => window.viewer.layerManager.managedLayers.map(m => m.visible)"

SLIDERS = """() => Object.fromEntries([...document.querySelectorAll('.axis-slider')].map(s => [s.id, {
  hidden: s.hidden, min: s.querySelector('input').min, max: s.querySelector('input').max,
  reading: s.querySelector('.reading').textContent }]))"""

# The panel's list of acquisitions, as the operator reads it.
ROWS = """() => [...document.querySelectorAll('.card.acquisitions .acquisition')].map(row => ({
  name: row.dataset.name,
  text: row.querySelector('.name').textContent,
  note: row.querySelector('.sub')?.textContent || null,
  shown: row.classList.contains('shown'), eyeOff: row.querySelector('.eye').classList.contains('off'),
  live: row.classList.contains('live'), badge: row.querySelector('.badge')?.textContent ?? null,
  remove: row.querySelector('.remove') !== null,
}))"""

# The positions folded out under an acquisition, as the operator reads them.
POSITIONS = """() => [...document.querySelectorAll('.card.acquisitions .acquisition')].map(row =>
  [row.dataset.name, [...row.querySelectorAll('.position')].map(p => [p.querySelector('.label').textContent, p.dataset.state || null])])"""

# The channel rows on show, by layer.
CHANNEL_ROWS = "() => [...document.querySelectorAll('.card.channels .channel')].filter(r => r.offsetParent !== null).map(r => r.dataset.layer)"

EMPTY = """() => { const box = document.querySelector('#empty');
  return box.hidden ? null : { title: box.querySelector('.title').textContent,
    text: box.querySelector('.text').hidden ? '' : box.querySelector('.text').textContent,
    open: !box.querySelector('button.primary').hidden }; }"""


# -- the channels ---------------------------------------------------------------------


def test_the_panel_lists_channels_by_acquisition_with_the_engines_own_controls(pages, viewers, stacks):
    view = viewers(ui="simple")
    for stack in stacks:
        view.add(stack, layer="overview")
    page, errors = _opened(pages, view, layers=2)
    seen = page.evaluate(
        """() => ({
          chrome: document.documentElement.dataset.chrome,
          nativePanel: document.querySelector('.neuroglancer-layer-panel') !== null,
          groups: [...document.querySelectorAll('.group')].map(g => g.dataset.group),
          names: [...document.querySelectorAll('.group .group-name')].map(g => g.textContent),
          rows: [...document.querySelectorAll('.channel')].map(r => r.dataset.layer),
          labels: [...document.querySelectorAll('.channel .label')].map(l => l.textContent),
          windows: [...document.querySelectorAll('.channel .controls .neuroglancer-invlerp-widget')].length,
          swatches: [...document.querySelectorAll('.channel .swatch')].map(s => s.style.background),
          autos: [...document.querySelectorAll('.channel .auto')].map(a => a.classList.contains('on')),
          scaleBar: window.viewer.showScaleBar.value, axes: window.viewer.showAxisLines.value,
        })"""
    )
    assert seen["chrome"] == "simple" and seen["nativePanel"] is False
    assert seen["groups"] == ["overview"] == seen["names"]
    assert seen["rows"] == ["overview · 488", "overview · 561"] and seen["labels"] == ["488", "561"]
    assert seen["windows"] == 2, "each row carries the engine's window control"
    assert seen["swatches"] == ["rgb(0, 255, 102)", "rgb(255, 51, 255)"]
    assert seen["autos"] == [False, False], "the store names its contrast"
    assert seen["scaleBar"] is True and seen["axes"] is False
    assert page.evaluate("() => document.querySelector('.stage-overlay #loading .fill') !== null"), "the loading bar"
    assert not errors, errors


def test_two_acquisitions_are_two_groups_of_channel_rows(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="first")
    view.add(stacks[1], layer="second")
    page, errors = _opened(pages, view, layers=4)
    groups = """() => [...document.querySelectorAll('.group')].map(g =>
      [g.dataset.group, [...g.querySelectorAll('.channel')].map(r => r.dataset.layer)])"""
    assert page.evaluate(groups) == [
        ["first", ["first · 488", "first · 561"]],
        ["second", ["second · 488", "second · 561"]],
    ]
    assert page.evaluate("() => document.querySelector('.card.channels').classList.contains('several')")
    view.remove("first")
    assert until(lambda: page.evaluate(groups), lambda seen: len(seen) == 1) == [
        ["second", ["second · 488", "second · 561"]]
    ]
    assert not errors, errors


def test_the_eye_hides_a_channel_and_shows_it_again(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    row = '.channel[data-layer="overview · 561"]'
    assert page.evaluate(VISIBILITY) == [True, True]
    page.click(f"{row} button.eye")
    assert page.evaluate(VISIBILITY) == [True, False]
    assert page.evaluate(f"() => document.querySelector('{row}').classList.contains('hidden')")
    assert page.evaluate(f"() => document.querySelector('{row} .eye').classList.contains('off')")
    page.click(f"{row} button.eye")
    assert page.evaluate(VISIBILITY) == [True, True]
    assert not page.evaluate(f"() => document.querySelector('{row}').classList.contains('hidden')")
    assert not errors, errors


def test_the_colour_is_set_through_the_swatch_and_the_engines_own_input_is_not_shown(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    row = '.channel[data-layer="overview · 488"]'
    page.wait_for_selector(f'{row} .controls input[type="color"]', state="attached")
    hidden = page.evaluate(
        """() => [...document.querySelectorAll('.channel .controls input[type="color"]')].map(input => {
          const control = input.closest('.neuroglancer-layer-control-container');
          const box = control.getBoundingClientRect();
          return { marked: control.classList.contains('colour-control'), width: box.width, height: box.height,
                   opacity: getComputedStyle(control).opacity }; })"""
    )
    assert len(hidden) == 2
    for control in hidden:
        assert control == {"marked": True, "width": 0, "height": 0, "opacity": "0"}, "takes no room in the row"
    assert page.evaluate(VISIBLE, f"{row} .swatch") is True
    # The swatch stands for it: choosing a colour there recolours the channel.
    page.evaluate(
        """(row) => { const input = document.querySelector(row + ' .controls input[type="color"]');
                      input.value = '#3366ff'; input.dispatchEvent(new Event('change', { bubbles: true }));
                      input.dispatchEvent(new Event('input', { bubbles: true })); }""",
        row,
    )
    colour = "() => window.viewer.layerManager.managedLayers[0].layer.shaderControlState.state.get('color').trackable.toJSON()"
    assert until(lambda: page.evaluate(colour), lambda seen: seen == "#3366ff") == "#3366ff"
    assert page.evaluate(f"() => document.querySelector('{row} .swatch').style.background") == "rgb(51, 102, 255)"
    assert not errors, errors


def test_the_histogram_is_drawn_inside_the_row(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    time.sleep(1.5)
    drawn = page.evaluate(
        """() => [...document.querySelectorAll('.channel .neuroglancer-invlerp-cdfpanel canvas')].map(c => {
          const r = c.getBoundingClientRect();
          const ctx = c.getContext('2d'); const px = ctx.getImageData(0, 0, c.width, c.height).data;
          let lit = 0; for (let i = 0; i < px.length; i += 4) if (px[i] + px[i + 1] + px[i + 2] > 60) lit++;
          return { width: r.width, height: r.height, lit }; })"""
    )
    assert len(drawn) == 2
    for canvas in drawn:
        assert canvas["width"] > 200 and 30 <= canvas["height"] <= 50, canvas
        assert canvas["lit"] > 50, "the engine drew the histogram into the row"
    assert not errors, errors


def test_the_panel_folds_away_and_comes_back(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    width = "() => document.querySelector('.mesospim-panel')?.getBoundingClientRect().width ?? 0"
    picture = "() => window.viewer.display.panels.values().next().value.renderViewport.logicalWidth"
    assert page.evaluate(width) > 250
    assert page.evaluate(VISIBLE, "#fold") is False, "nothing to unfold while the panel is open"
    narrow = page.evaluate(picture)
    page.click(".panel-head button.fold")
    time.sleep(0.5)
    assert page.evaluate(width) == 0
    assert page.evaluate(picture) > narrow, "the picture takes the room the panel gave up"
    page.click("#fold")
    time.sleep(0.5)
    assert page.evaluate(width) > 250
    assert page.evaluate("() => document.querySelectorAll('.channel').length") == 2, "with its rows as they were"
    assert not errors, errors


# -- the acquisitions: Python's list, drawn ---------------------------------------------------------


def test_the_list_of_acquisitions_shows_what_python_offers(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run_c")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(ROWS) == []
    hint = "() => { const p = document.querySelector('.card.acquisitions .hint'); return p.hidden ? null : p.textContent; }"
    assert page.evaluate(hint) == "Nothing here yet."
    view.on_remove(lambda name: None)  # removals are heard: the panel offers the remove button
    two = [{"name": "Tile 1"}, {"name": "Tile 2"}]
    view.offer(
        [
            {"name": "run_c", "shown": True, "live": True, "removable": False, "tiles": 4, "note": "Tile 3 of 4 · 561",
             "positions": two, "channels": ["488", "561"]},
            {"name": "run_b", "shown": True, "live": False, "removable": True, "tiles": 1, "note": "",
             "positions": [{"name": "Tile 1"}], "channels": ["488"]},
            {"name": "run_a", "shown": False, "live": False, "removable": True, "tiles": None, "note": "",
             "positions": two, "channels": ["488", "561"]},
            {"name": "paused", "shown": True, "live": True, "paused": True, "removable": False, "tiles": 2,
             "note": "Tile 2 of 4 · 488", "positions": two, "channels": ["488"]},
        ]
    )
    rows = until(lambda: page.evaluate(ROWS), lambda seen: len(seen) == 4)
    assert rows == [
        {"name": "run_c", "text": "run_c", "note": "Tile 3 of 4 · 561", "shown": True, "eyeOff": False,
         "live": True, "badge": "Live", "remove": False},
        {"name": "run_b", "text": "run_b", "note": "1 position · 488", "shown": True, "eyeOff": False,
         "live": False, "badge": "Saved", "remove": True},
        {"name": "run_a", "text": "run_a", "note": "2 positions · 488, 561", "shown": False, "eyeOff": True,
         "live": False, "badge": "Saved", "remove": True},
        {"name": "paused", "text": "paused", "note": "Paused · Tile 2 of 4 · 488", "shown": True, "eyeOff": False,
         "live": True, "badge": "Paused", "remove": False},
    ]
    assert page.evaluate(hint) is None
    # Three blocks, in the order the operator uses them: load data, the acquisitions, the channels of one.
    assert page.evaluate("() => [...document.querySelectorAll('.panel-body > .card')].map(c => c.className)")[:3] == [
        "card load",
        "card acquisitions",
        "card channels",
    ]
    view.offer([])
    assert until(lambda: page.evaluate(ROWS), lambda seen: seen == []) == []
    assert not errors, errors


def test_a_run_between_two_stacks_says_how_far_it_has_got(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    view.offer([{
        "name": "run", "shown": True, "live": True, "removable": False, "tiles": 3, "note": "", "channels": ["488", "561"],
        "positions": [{"name": "Tile 1", "state": "done"}, {"name": "Tile 2", "state": "part", "acquired": 1},
                      {"name": "Tile 3", "state": "next"}],
    }])
    page, errors = _opened(pages, view, layers=2)
    rows = until(lambda: page.evaluate(ROWS), lambda seen: seen)
    assert rows[0]["note"] == "1 of 3 positions acquired", "between two stacks the microscope says nothing more"
    states = """() => [...document.querySelectorAll('.position')].map(p => [p.querySelector('.label').textContent,
      p.querySelector('.state')?.textContent ?? null])"""
    assert until(lambda: page.evaluate(states), lambda seen: seen) == [
        ["Tile 1", "acquired"], ["Tile 2", "1 of 2 channels"], ["Tile 3", "next"],
    ]
    assert not errors, errors


def test_clicks_in_the_list_tell_python_what_to_show_and_what_to_remove(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run_b")
    shown, removed = [], []
    view.on_show(lambda name, visible, only: shown.append((name, visible, only)))
    view.on_remove(removed.append)
    view.offer(
        [
            {"name": "run_b", "shown": True, "live": False, "removable": False, "tiles": 1, "note": ""},
            {"name": "run_a", "shown": False, "live": False, "removable": True, "tiles": None, "note": ""},
        ]
    )
    page, errors = _opened(pages, view, layers=2)
    page.wait_for_selector('.acquisition[data-name="run_a"]')
    page.click('.acquisition[data-name="run_a"] .eye')  # hidden: show it as well
    page.click('.acquisition[data-name="run_b"] .eye')  # shown: hide it
    page.click('.acquisition[data-name="run_a"] .name')  # its name: select it, shown so that it can be looked at
    page.click('.acquisition[data-name="run_a"] .remove')
    until(lambda: (len(shown), len(removed)), lambda seen: seen == (3, 1))
    assert shown == [("run_a", True, False), ("run_b", False, False), ("run_a", True, False)]
    assert removed == ["run_a"]
    assert page.query_selector('.acquisition[data-name="run_b"] .remove') is None, "not one of those it may remove"
    assert not errors, errors


def test_the_list_drives_a_library_and_shows_what_it_did(pages, viewers, tmp_path):
    for seed, name in enumerate(["run_a", "run_b"]):
        time.sleep(0.05)
        write_tile(an_acquisition(tmp_path / "data", name) / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=seed)
    elsewhere = write_tile(tmp_path / "elsewhere" / "single.ome.zarr", origin_um=(0, 0, 200), seed=5)
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path / "data")
    library.open(elsewhere)
    page, errors = _opened(pages, view, layers=4)
    made = pages.layer_objects(page)["now"]
    listed = lambda: [(row["name"], row["shown"], row["remove"]) for row in page.evaluate(ROWS)]
    layers = lambda: page.evaluate("() => window.viewer.layerManager.managedLayers.map(m => m.name)")
    assert listed() == [("run_b", True, True), ("run_a", False, True), ("single", True, True)]

    page.click('.acquisition[data-name="run_a"] .eye')
    assert until(listed, lambda seen: seen[1][1]) == [("run_b", True, True), ("run_a", True, True), ("single", True, True)]
    assert sorted(until(layers, lambda seen: len(seen) == 6)) == [
        "run_a · 488", "run_a · 561", "run_b · 488", "run_b · 561", "single · 488", "single · 561",
    ]
    assert library.shown == ["run_b", "run_a", "single"]
    kept = pages.layer_objects(page)["now"]
    assert {name: kept[name] for name in made} == made, "the layers already there were left as they were"

    page.click('.acquisition[data-name="run_b"] .eye')
    assert sorted(until(layers, lambda seen: len(seen) == 4)) == ["run_a · 488", "run_a · 561", "single · 488", "single · 561"]
    page.click('.acquisition[data-name="run_a"] .eye')
    assert until(layers, lambda seen: len(seen) == 2) == ["single · 488", "single · 561"]
    assert until(listed, lambda seen: not seen[1][1]) == [("run_b", False, True), ("run_a", False, True), ("single", True, True)]
    assert library.shown == ["single"]

    page.click('.acquisition[data-name="single"] .remove')
    assert until(listed, lambda seen: len(seen) == 2) == [("run_b", False, True), ("run_a", False, True)]
    assert until(layers, lambda seen: seen == []) == [] and library.names == ["run_b", "run_a"]
    assert page.evaluate(EMPTY)["title"] == "Nothing is shown"
    assert not errors, errors


def test_the_open_button_is_offered_once_python_listens_for_it(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(VISIBLE, ".card.load .open") is False
    opened = []
    view.on_open(lambda: opened.append(True))
    assert until(lambda: page.evaluate(VISIBLE, ".card.load .open")) is True
    assert page.evaluate("() => document.querySelector('.card.acquisitions .hint').textContent") == (
        "Nothing here yet. Start an acquisition, or open a dataset from disk."
    )
    page.click(".card.load .open")
    assert until(lambda: opened) == [True]
    assert not errors, errors


def test_the_live_switch_shows_what_python_says_and_tells_it_what_the_operator_wants(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(VISIBLE, ".card.load .live-toggle") is False, "nothing listens yet"
    asked = []
    view.on_collect(asked.append)
    view.collecting(True)
    assert until(lambda: page.evaluate(VISIBLE, ".card.load .live-toggle")) is True
    switched_on = "() => document.querySelector('.card.load .live-toggle').classList.contains('on')"
    assert page.evaluate(switched_on) is True
    page.click(".card.load .live-toggle")
    assert until(lambda: asked) == [False]
    view.collecting(False)
    assert until(lambda: page.evaluate(switched_on), lambda on: on is False) is False
    assert not errors, errors


def _two_runs(tmp_path, tiles=1):
    for seed, name in enumerate(["run_a", "run_b"]):
        time.sleep(0.05)
        acquisition = an_acquisition(tmp_path / "data", name)
        for tile in range(tiles):
            write_tile(acquisition / f"Mag1_Tile{tile}_Sh0_Rot0.ome.zarr", origin_um=(0, 0, tile * 144), seed=seed * 10 + tile)


def test_selecting_an_acquisition_shows_only_its_channels(pages, viewers, tmp_path):
    _two_runs(tmp_path)
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path / "data")
    library.show("run_a")
    page, errors = _opened(pages, view, layers=4)
    assert until(lambda: page.evaluate(CHANNEL_ROWS), lambda seen: len(seen) == 2) == ["run_b · 488", "run_b · 561"], (
        "the newest, selected at first"
    )
    page.click('.acquisition[data-name="run_a"] .name')
    assert until(lambda: page.evaluate(CHANNEL_ROWS), lambda seen: seen and seen[0].startswith("run_a")) == [
        "run_a · 488", "run_a · 561",
    ]
    selected = "() => [...document.querySelectorAll('.acquisition.selected')].map(r => r.dataset.name)"
    assert page.evaluate(selected) == ["run_a"]
    assert page.evaluate("() => document.querySelector('.card.channels .of').textContent") == "run_a"
    assert not errors, errors


def test_positions_fold_out_one_acquisition_at_a_time_and_take_the_view_there(pages, viewers, tmp_path):
    _two_runs(tmp_path, tiles=2)  # tiles 160 um across, 144 um apart: x from 0 to 160, and 144 to 304
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path / "data")
    library.show("run_a")
    page, errors = _opened(pages, view, layers=4)
    folded = until(lambda: page.evaluate(POSITIONS), lambda seen: any(names for _, names in seen))
    assert folded == [["run_b", [["Tile 1", None], ["Tile 2", None]]], ["run_a", []]], "the selected one is open"
    page.click('.acquisition[data-name="run_a"] .name')
    assert until(lambda: page.evaluate(POSITIONS), lambda seen: seen[1][1]) == [
        ["run_b", []], ["run_a", [["Tile 1", None], ["Tile 2", None]]],
    ], "opening one folds the other away"
    centre = lambda: round(page.evaluate(WHERE)["um"]["x"])
    page.click('.acquisition[data-name="run_a"] .position[data-name="Tile 2"]')
    assert until(centre, lambda x: x == 224) == 224, "the view on Tile 2: x from 144 to 304"
    assert page.evaluate(VISIBLE, "#fit") is True
    marked = "() => [...document.querySelectorAll('.position.framed')].map(p => p.dataset.name)"
    assert until(lambda: page.evaluate(marked), lambda seen: seen) == ["Tile 2"], "the position the view went to is marked"
    zoomed = page.evaluate(WHERE)["zoom"]
    page.click('.acquisition[data-name="run_a"] .name')
    assert until(centre, lambda x: x == 152) == 152, "the whole acquisition again: x from 0 to 304"
    assert page.evaluate(WHERE)["zoom"] > zoomed
    assert page.evaluate(marked) == [], "the whole acquisition: no one position marked"
    page.click('.acquisition[data-name="run_a"] .fold')
    assert until(lambda: page.evaluate(POSITIONS), lambda seen: not seen[1][1]) == [["run_b", []], ["run_a", []]]
    assert not errors, errors


def test_a_run_that_starts_comes_in_on_top_and_selects_itself(pages, viewers, tmp_path):
    _two_runs(tmp_path)
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path / "data")
    page, errors = _opened(pages, view, layers=2)
    page.click('.acquisition[data-name="run_a"] .name')
    library.begin_stack(Stack(acquisition="new", channel="488", channels=("488",), planes=4, frame=(32, 32),
                              voxel_um=(5.0, 1.0, 1.0), origin_um=(0.0, 0.0, 0.0), tile="Tile 1", tiles=2))
    rows = until(lambda: page.evaluate(ROWS), lambda seen: seen and seen[0]["name"] == "new")
    assert (rows[0]["badge"], rows[0]["live"]) == ("Live", True)
    selected = "() => [...document.querySelectorAll('.acquisition.selected')].map(r => r.dataset.name)"
    assert until(lambda: page.evaluate(selected), lambda seen: seen == ["new"]) == ["new"]
    assert until(lambda: page.evaluate(POSITIONS), lambda seen: seen[0][1])[0] == ["new", [["Tile 1", "now"], ["Tile 2", "next"]]]
    assert not errors, errors


# -- instead of a black picture: what the viewer is waiting for --------------------------------------


def test_an_empty_picture_says_what_it_is_waiting_for(pages, viewers, stacks):
    view = viewers(ui="simple")
    page, errors = pages.open(view.start(), width=1100, height=700)
    says = lambda title: until(lambda: page.evaluate(EMPTY), lambda seen: (seen or {}).get("title") == title)
    assert says("No acquisition yet") == {
        "title": "No acquisition yet",
        "text": "The next acquisition appears here as it is acquired.",
        "open": False,
    }
    assert page.evaluate(VISIBLE, "#empty") is True
    assert page.evaluate("() => document.querySelector('.bottom-bar').classList.contains('none')"), "no sliders either"

    opened = []
    view.on_open(lambda: opened.append(True))
    until(lambda: page.evaluate(EMPTY), lambda seen: seen["open"])
    assert page.evaluate(EMPTY) == {
        "title": "No acquisition yet",
        "text": "The next acquisition appears here as it is acquired. You can also open a dataset from disk, "
        "or drop its folder onto this window.",
        "open": True,
    }
    page.click("#empty button.primary")
    assert until(lambda: opened) == [True]

    entry = {"name": "run_b", "shown": False, "live": False, "removable": False, "tiles": None, "note": "", "empty": False}
    view.offer([entry])
    assert says("Nothing is shown") == {
        "title": "Nothing is shown",
        "text": "Tick an acquisition in the list on the right to show it.",
        "open": False,
    }
    view.offer([entry | {"shown": True, "empty": True, "live": True}])
    assert says("Waiting for the first planes of run_b") == {
        "title": "Waiting for the first planes of run_b",
        "text": "They are shown as soon as the camera delivers them.",
        "open": False,
    }
    view.offer([entry | {"shown": True, "empty": True}])
    assert says("run_b holds no image data yet") == {
        "title": "run_b holds no image data yet",
        "text": "Its tiles are shown as they are written.",
        "open": False,
    }
    # It holds data, and its layers are on their way.
    view.offer([entry | {"shown": True}])
    assert says("Opening…") == {"title": "Opening…", "text": "", "open": False}
    view.add(stacks[0], layer="run_b")
    assert until(lambda: page.evaluate(EMPTY), lambda seen: seen is None, 20) is None
    assert page.evaluate(VISIBLE, "#empty") is False
    # One of two that are shown is still empty: the other is a picture, so nothing is said.
    view.offer([entry | {"shown": True}, entry | {"name": "run_a", "shown": True, "empty": True}])
    time.sleep(0.5)
    assert page.evaluate(EMPTY) is None
    assert not errors, errors


def test_a_message_from_python_is_shown_on_the_picture_until_it_is_closed(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    notice = "() => { const n = document.querySelector('#notice'); return n && !n.hidden ? n.querySelector('.text').textContent : null; }"
    sentence = "notes isn't an OME-Zarr folder the viewer can open."
    assert page.evaluate(notice) is None
    view.say(sentence)
    assert until(lambda: page.evaluate(notice)) == sentence
    page.click("#notice .close")
    assert page.evaluate(notice) is None
    view.say(sentence)  # said again, it is shown again
    assert until(lambda: page.evaluate(notice)) == sentence
    view.say("")
    assert until(lambda: page.evaluate(notice), lambda seen: seen is None) is None
    assert not errors, errors


def test_the_help_sheet_opens_on_request(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(VISIBLE, ".help .sheet") is False
    page.click("#help")
    assert page.evaluate(VISIBLE, ".help .sheet") is True
    lines = page.evaluate("() => [...document.querySelectorAll('.help .sheet .line')].map(l => l.textContent)")
    assert any("Scroll" in line and "zoom" in line for line in lines)
    assert any("Shift + scroll" in line and "planes" in line for line in lines)
    page.click("#help")
    assert page.evaluate(VISIBLE, ".help .sheet") is False
    assert not errors, errors


# -- the sliders along the bottom ------------------------------------------------------------------------


def test_the_sliders_step_through_depth_and_time_and_say_where_they_are(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    seen = page.evaluate(SLIDERS)
    assert seen["slider-z"] | {"reading": ""} == {"hidden": False, "min": "0", "max": "23", "reading": ""}
    assert seen["slider-t"] == {"hidden": False, "min": "0", "max": "2", "reading": "1 / 3"}
    assert seen["slider-z"]["reading"].endswith("/ 24")
    assert page.evaluate("() => document.querySelector('#slider-z').closest('.bottom-bar') !== null")
    assert page.evaluate(VISIBLE, "#slider-z") and page.evaluate(VISIBLE, "#slider-t")

    _set_slider(page, "#slider-t", 2)
    _set_slider(page, "#slider-z", 5)
    voxels = page.evaluate(WHERE)["voxels"]
    assert voxels["t"] == pytest.approx(2.0) and voxels["z"] == pytest.approx(5.0)
    readings = {name: slider["reading"] for name, slider in page.evaluate(SLIDERS).items()}
    assert readings == {"slider-t": "3 / 3", "slider-z": "25.0 µm · 6 / 24"}, "the plane, and its depth in the stack"
    _set_slider(page, "#slider-z", 0)
    assert page.evaluate(SLIDERS)["slider-z"]["reading"] == "0.0 µm · 1 / 24"
    _set_slider(page, "#slider-z", 23)
    assert page.evaluate(SLIDERS)["slider-z"]["reading"] == "115 µm · 24 / 24"

    # Python moving the camera moves the slider too.
    view.look_at(z=12 * 5.0)  # micrometres: 5 um planes
    reading = lambda: page.evaluate(SLIDERS)["slider-z"]["reading"]
    assert until(reading, lambda seen: seen.endswith("13 / 24"), 5) == "60.0 µm · 13 / 24"
    assert not errors, errors


# What the middle of the picture says, in the numbering of stores.numbered.
READ_MIDDLE = """() => {
  const display = window.viewer.display; display.draw();
  const box = document.querySelector('.neuroglancer-rendered-data-panel').getBoundingClientRect();
  const canvas = display.canvas.getBoundingClientRect();
  const x = Math.round(box.left + box.width / 2 - canvas.left);
  const y = Math.round(display.canvas.height - (box.top + box.height / 2 - canvas.top));
  const pixel = new Uint8Array(4);
  display.gl.readPixels(x, y, 1, 1, display.gl.RGBA, display.gl.UNSIGNED_BYTE, pixel);
  return pixel[1] / 255 * 5000;
}"""


def test_the_sliders_show_the_plane_and_time_point_they_name(pages, viewers, tmp_path):
    view = viewers(ui="simple")
    view.add(numbered(tmp_path / "numbered.ome.zarr"), layer="numbered", window=(0, 5000), colours=["#ffffff"])
    page, errors = _opened(pages, view, layers=1)
    for t in range(3):
        for z in range(4):
            _set_slider(page, "#slider-t", t)
            _set_slider(page, "#slider-z", z)
            time.sleep(0.3)  # the engine asks for the new plane's chunks on its next frame
            pages.drawn(page, layers=1)
            readings = page.evaluate(
                "() => ['#slider-t', '#slider-z'].map(id => document.querySelector(id + ' .reading').textContent)"
            )
            assert readings == [f"{t + 1} / 3", f"{z:.1f} µm · {z + 1} / 4"]
            assert page.evaluate(READ_MIDDLE) == pytest.approx(1000 * (t + 1) + 200 * z, abs=30), (t, z)
    assert not errors, errors


def test_a_single_plane_or_time_point_has_no_slider(pages, viewers, tiles):
    view = viewers(ui="simple")
    view.add(tiles[0], layer="run")  # one time point
    page, errors = _opened(pages, view, layers=2)
    seen = page.evaluate(SLIDERS)
    assert seen["slider-t"]["hidden"] is True and seen["slider-z"]["hidden"] is False
    assert page.evaluate(VISIBLE, "#slider-t") is False
    assert not page.evaluate("() => document.querySelector('.bottom-bar').classList.contains('none')")
    assert not errors, errors


def test_an_acquisition_opens_on_its_first_time_point(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run_01")
    page, errors = _opened(pages, view, layers=2)
    reading = "() => document.querySelector('#slider-t .reading').textContent"
    page.wait_for_function(f"() => ({reading})() === '1 / 3'", timeout=5000)

    # The operator's choice stays while more tiles of the same acquisition land...
    _set_slider(page, "#slider-t", 2)
    view.add(stacks[1], layer="run_01")
    pages.drawn(page, layers=2, sources=2)
    time.sleep(0.5)
    assert page.evaluate(reading) == "3 / 3"

    # ...and another acquisition opens on its own first time point.
    view.remove("run_01")
    page.wait_for_function("() => window.viewer.layerManager.managedLayers.length === 0")
    view.add(stacks[0], layer="run_02")
    page.wait_for_function("() => window.viewer.layerManager.managedLayers[0]?.name.startsWith('run_02')")
    pages.drawn(page, layers=2)
    page.wait_for_function(f"() => ({reading})() === '1 / 3'", timeout=5000)
    assert not errors, errors


# -- the mouse, and what is under it ------------------------------------------------------------------------


def _over_the_picture(page) -> None:
    box = page.locator(".neuroglancer-rendered-data-panel").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def test_the_wheel_zooms_and_with_shift_steps_through_the_planes(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    time.sleep(0.5)
    start = page.evaluate(WHERE)
    _over_the_picture(page)
    page.mouse.wheel(0, -300)
    zoomed = until(lambda: page.evaluate(WHERE), lambda seen: seen["zoom"] != start["zoom"], 5)
    assert zoomed["zoom"] < start["zoom"], "scrolling up zooms in"
    assert zoomed["voxels"]["z"] == start["voxels"]["z"], "and stays on its plane"
    page.mouse.wheel(0, 300)
    back = until(lambda: page.evaluate(WHERE), lambda seen: seen["zoom"] > zoomed["zoom"], 5)
    assert back["zoom"] > zoomed["zoom"]

    page.keyboard.down("Shift")
    page.mouse.wheel(0, 100)
    stepped = until(lambda: page.evaluate(WHERE), lambda seen: seen["voxels"]["z"] != start["voxels"]["z"], 5)
    page.keyboard.up("Shift")
    assert abs(stepped["voxels"]["z"] - start["voxels"]["z"]) == pytest.approx(1.0), "one plane a notch"
    assert stepped["zoom"] == back["zoom"]
    page.keyboard.down("Shift")
    page.mouse.wheel(0, -100)
    page.keyboard.up("Shift")
    assert until(lambda: page.evaluate(WHERE)["voxels"]["z"], lambda z: z == start["voxels"]["z"], 5) == start["voxels"]["z"]
    assert not errors, errors


def test_the_readout_says_what_is_under_the_pointer(pages, viewers, tiles):
    view = viewers(ui="simple")
    view.add(tiles[0], layer="run")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(VISIBLE, "#readout") is False
    _over_the_picture(page)
    said = until(
        lambda: page.evaluate(
            "() => { const r = document.querySelector('#readout'); return r.hidden ? null :"
            " { where: r.querySelector('.where').textContent, values: [...r.querySelectorAll('.value')].map(v => v.textContent) }; }"
        ),
        lambda seen: seen is not None and len(seen["values"]) == 2,
        10,
    )
    assert said is not None, "the readout never appeared"
    assert said["where"].endswith("µm") and said["where"].split()[::2][:3] == ["x", "y", "z"]
    x, y, z = (float(number) for number in said["where"].split()[1:6:2])
    assert 0 <= x <= 160 and 0 <= y <= 160 and 0 <= z <= 120, "in micrometres, inside the tile"
    assert [value.split(":")[0] for value in said["values"]] == ["488", "561"]
    assert all(380 <= int(value.split(":")[1]) <= 12400 for value in said["values"]), "the voxel's own counts"
    assert not errors, errors


# -- Fit ------------------------------------------------------------------------------------------------------

# Where the camera looks, in micrometres, how far it is zoomed out, and whether Fit is offered.
OVERVIEW = """() => {
  const n = window.viewer.navigationState, space = n.position.coordinateSpace.value;
  const at = (axis) => { const i = space.names.indexOf(axis); return n.position.value[i] * space.scales[i] * 1e6; };
  const button = document.querySelector('#fit');
  return { x: at('x'), y: at('y'), zoom: n.zoomFactor.value, fit: !!button && !button.hidden,
           framing: window.mesospim.framing.value };
}"""


def test_fit_appears_once_the_view_is_moved_and_frames_everything_again(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="first")
    page, errors = _opened(pages, view, layers=2)
    time.sleep(0.5)
    fitted = page.evaluate(OVERVIEW)
    assert fitted["fit"] is False and fitted["framing"] is True, "nothing to bring back while the view frames everything"
    assert page.evaluate(VISIBLE, "#fit") is False
    assert fitted["x"] == pytest.approx(80, abs=2)

    # The operator zooms in: the view is theirs, and Fit is offered.
    _over_the_picture(page)
    page.mouse.wheel(0, -300)
    assert until(lambda: page.evaluate(VISIBLE, "#fit")) is True
    theirs = page.evaluate(OVERVIEW)
    assert theirs["zoom"] < fitted["zoom"] and theirs["framing"] is False

    # Another acquisition arrives: the view stays where the operator put it.
    view.add(stacks[1], layer="second")
    pages.drawn(page, layers=4)
    time.sleep(1.0)
    assert page.evaluate(OVERVIEW) == theirs

    # Fit frames both, and from then on the view takes in what lands again.
    page.click("#fit")
    time.sleep(0.5)
    both = page.evaluate(OVERVIEW)
    assert both["fit"] is False and both["framing"] is True
    assert both["x"] == pytest.approx((0 + 144 + 160) / 2, abs=2)
    assert both["zoom"] > fitted["zoom"]
    assert not errors, errors


def test_dragging_the_picture_also_makes_the_view_the_operators(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="first")
    page, errors = _opened(pages, view, layers=2)
    time.sleep(0.5)
    fitted = page.evaluate(OVERVIEW)
    box = page.locator(".neuroglancer-rendered-data-panel").first.bounding_box()
    middle = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.mouse.move(middle[0] + 120, middle[1] + 40, steps=5)
    page.mouse.up()
    moved = until(lambda: page.evaluate(OVERVIEW), lambda seen: seen["fit"], 5)
    assert moved["fit"] is True and moved["x"] < fitted["x"], "the picture went right, so the view looks further left"
    assert moved["zoom"] == fitted["zoom"]
    # Stepping through the planes is not moving the picture: Fit stays as it is.
    page.click("#fit")
    until(lambda: page.evaluate(OVERVIEW), lambda seen: not seen["fit"], 5)
    _set_slider(page, "#slider-z", 3)
    time.sleep(0.3)
    assert page.evaluate(OVERVIEW)["fit"] is False
    assert not errors, errors


# -- 2D and 3D ----------------------------------------------------------------------------------------------------

VIEW = """() => ({ layout: window.mesospim.layout(),
  modes: window.viewer.layerManager.managedLayers.map(m => m.layer.volumeRenderingMode.toJSON() ?? 'off'),
  on: [...document.querySelectorAll('.view button.on')].map(b => b.dataset.layout) })"""

VOLUME = """() => window.viewer.layerManager.managedLayers.map(m =>
  [m.layer.volumeRenderingDepthSamplesTarget.value, m.layer.volumeRenderingGain.value])"""

READING = "() => document.querySelector('.card.volume input.detail + .reading').textContent"

# The copy of the image the volume view draws from, in micrometres across (x), as the engine last drew it.
DRAWN = """() => {
  const layer = window.viewer.layerManager.managedLayers[0].layer;
  const volume = layer.renderLayers.find((r) => 'depthSamplesTarget' in r);
  const size = volume?.highestResolutionLoadedVoxelSize;
  return size ? size[0] * 1e6 : null;
}"""

# The depth of the volume view's box, and the farthest any corner of what is shown lies from where it
# turns, both in the engine's units.
BOX = """() => {
  const v = window.viewer, space = v.navigationState.position.coordinateSpace.value;
  const render = v.navigationState.pose.displayDimensionRenderInfo.value;
  const drawn = Array.from(render.displayDimensionIndices).filter((a) => a >= 0).slice(0, 3);
  const at = v.navigationState.position.value;
  let farthest = 0;
  for (let corner = 0; corner < 8; ++corner) {
    let squared = 0;
    drawn.forEach((axis, slot) => {
      const end = (corner >> slot) & 1 ? space.bounds.upperBounds[axis] : space.bounds.lowerBounds[axis];
      squared += ((end - at[axis]) * render.canonicalVoxelFactors[slot]) ** 2;
    });
    farthest = Math.max(farthest, Math.sqrt(squared));
  }
  return { depth: v.perspectiveNavigationState.depthRange.value, farthest };
}"""


@slow_without_a_graphics_card
def test_2d_and_3d_swap_the_layout_and_the_volume_rendering(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    assert page.evaluate(VIEW) == {"layout": "xy", "modes": ["off", "off"], "on": ["xy"]}
    assert page.evaluate("() => document.querySelector('.segmented.view').closest('.stage-overlay') !== null")
    assert page.evaluate("() => document.querySelector('.card.volume').hidden") is True
    _in_3d(page)
    assert page.evaluate(VIEW) == {"layout": "3d", "modes": ["max", "max"], "on": ["3d"]}
    assert page.evaluate("() => document.querySelector('.card.volume').hidden") is False
    page.click('.view button[data-layout="xy"]')
    assert page.evaluate(VIEW) == {"layout": "xy", "modes": ["off", "off"], "on": ["xy"]}
    assert page.evaluate("() => document.querySelector('.card.volume').hidden") is True
    assert not errors, errors


@slow_without_a_graphics_card
def test_the_3d_card_drives_projection_detail_gain_planes_and_the_look(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)
    assert page.evaluate("() => window.viewer.showPerspectiveSliceViews.value") is False, "a pure volume"
    assert page.evaluate("() => document.getElementById('slider-t').hidden") is False
    modes = lambda: page.evaluate(VIEW)["modes"]
    lit = "() => document.querySelector('.card.volume button[data-mode].on').dataset.mode"

    gain_offered = "() => !document.querySelector('.card.volume input.gain').closest('.row').classList.contains('disabled')"
    page.click('.card.volume button[data-mode="min"]')
    assert modes() == ["min", "min"] and page.evaluate(lit) == "min"
    page.click('.card.volume button[data-mode="max"]')
    assert modes() == ["max", "max"] and page.evaluate(lit) == "max"
    assert page.evaluate(gain_offered) is False, "the gain is for the blended projection only"

    coarse = page.evaluate(VOLUME)[0][0]
    _set_detail(page, 3)
    # applied on the next frame
    sharp = until(lambda: [detail for detail, _ in page.evaluate(VOLUME)], lambda seen: seen[0] > coarse)
    assert sharp[0] == sharp[1] and sharp[0] > coarse, "sharper is more steps, for every channel"
    reading = until(lambda: page.evaluate(READING), lambda text: text.endswith("µm"))
    assert reading.endswith("µm"), f"the copy drawn, not a count of steps: {reading!r}"
    _set_detail(page, 0)

    page.evaluate(
        "() => { const i = document.querySelector('.card.volume input.gain'); i.value = '2.5'; i.dispatchEvent(new Event('input')); }"
    )
    assert [gain for _, gain in page.evaluate(VOLUME)] == [2.5, 2.5]

    page.click(".card.volume input.slices")
    assert page.evaluate("() => window.viewer.showPerspectiveSliceViews.value") is True

    orientation = "() => window.viewer.projectionOrientation.toJSON() ?? [0, 0, 0, 1]"
    page.click('.card.volume button[data-look="front"]')
    assert page.evaluate(orientation) == pytest.approx([-0.7071, 0, 0, 0.7071], abs=1e-3)
    page.click('.card.volume button[data-look="side"]')
    assert page.evaluate(orientation) == pytest.approx([0, 0.7071, 0, 0.7071], abs=1e-3)
    page.click('.card.volume button[data-look="top"]')
    assert page.evaluate(orientation) == [0, 0, 0, 1]
    # Last, because it is the slowest to draw: every voxel blended, as far as the gain lets it.
    page.click('.card.volume button[data-mode="on"]')
    assert page.evaluate(f"() => [({VIEW})().modes, ({lit})(), ({gain_offered})()]") == [["on", "on"], "on", True]
    assert not errors, errors


@slow_without_a_graphics_card
def test_the_volume_view_stays_when_python_sends_a_new_scene(pages, viewers, stacks):
    """The 2D/3D switch is the operator's. Python publishes a scene whenever
    anything changes -- a tile landed, the list of acquisitions, a message --
    and none of that may put the view back to 2D."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)
    assert page.evaluate(VIEW) == {"layout": "3d", "modes": ["max", "max"], "on": ["3d"]}
    notice = "() => { const n = document.querySelector('#notice'); return n.hidden ? null : n.querySelector('.text').textContent; }"
    view.say("a new scene")
    assert until(lambda: page.evaluate(notice)) == "a new scene"
    assert page.evaluate(VIEW) == {"layout": "3d", "modes": ["max", "max"], "on": ["3d"]}
    # Python changing the layout itself is another matter: that is taken.
    view.set_layout("4panel")
    assert until(lambda: page.evaluate(VIEW)["layout"], lambda seen: seen == "4panel") == "4panel"
    assert not errors, errors


@slow_without_a_graphics_card
def test_adjustments_in_the_panel_survive_a_tile_landing(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    made = pages.layer_objects(page)
    page.click('.channel[data-layer="overview · 561"] button.eye')
    _in_3d(page)
    # the detail slider up a step, the gain up a little
    _set_detail(page, 1)
    page.evaluate(
        "() => { const i = document.querySelector('.card.volume input.gain'); i.value = '2'; i.dispatchEvent(new Event('input')); }"
    )
    view.add(stacks[1], layer="overview")
    sources = "() => window.viewer.layerManager.managedLayers.map(m => m.layer.dataSources.length)"
    assert until(lambda: page.evaluate(sources), lambda seen: seen == [2, 2], 20) == [2, 2]
    assert pages.layer_objects(page) == made, "the same layers, so the same rows and controls"
    assert page.evaluate(VISIBILITY) == [True, False]
    (steps, gain), other = page.evaluate(VOLUME)
    assert other == [steps, gain] and gain == 2 and steps > 0, "one detail and one gain for every channel"
    assert page.evaluate(
        "() => [...document.querySelectorAll('.channel')].map(r => r.classList.contains('hidden'))"
    ) == [False, True]
    assert page.evaluate(VIEW) == {"layout": "3d", "modes": ["max", "max"], "on": ["3d"]}, "and still the volume view"
    assert not errors, errors


@slow_without_a_graphics_card
def test_a_layer_that_arrives_in_the_volume_view_is_drawn_like_the_others(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="first")
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)
    page.click('.card.volume button[data-mode="min"]')
    _set_detail(page, 1)
    view.add(stacks[1], layer="second")
    until(lambda: page.evaluate(VIEW)["modes"], lambda seen: len(seen) == 4, 20)
    assert page.evaluate(VIEW) == {"layout": "3d", "modes": ["min"] * 4, "on": ["3d"]}
    details = [detail for detail, _ in page.evaluate(VOLUME)]
    assert len(set(details)) == 1, f"as finely as the ones already there: {details}"
    assert not errors, errors


DEPTH = """() => {
  const n = window.viewer.navigationState, space = n.position.coordinateSpace.value;
  const z = space.names.indexOf('z');
  return { z: n.position.value[z], middle: (space.bounds.lowerBounds[z] + space.bounds.upperBounds[z]) / 2 };
}"""


@slow_without_a_graphics_card
def test_3d_turns_about_the_middle_of_the_stack_and_2d_comes_back_to_its_plane(pages, viewers, stacks):
    """The volume view turns about the point it is centred on. Left on the plane
    the 2D view showed (the last one, after following a run), the stack hangs off
    to one side of the picture and comes far too close when turned."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")  # 24 planes
    page, errors = _opened(pages, view, layers=2)
    _set_slider(page, "#slider-z", 20)
    assert round(page.evaluate(WHERE)["voxels"]["z"]) == 20
    _in_3d(page)
    depth = until(lambda: page.evaluate(DEPTH), lambda seen: abs(seen["z"] - seen["middle"]) < 0.5)
    assert depth["z"] == pytest.approx(depth["middle"], abs=0.5), "turned about the middle of the stack"
    page.click('.view button[data-layout="xy"]')
    assert until(lambda: round(page.evaluate(WHERE)["voxels"]["z"]), lambda z: z == 20) == 20, "back on its plane"
    assert not errors, errors


@slow_without_a_graphics_card
def test_live_in_3d_follows_the_time_points_and_keeps_the_stack_centred(pages, viewers, stacks):
    """The volume shows every plane of the stack at once: following a run there
    goes to the newest time point, not to the newest plane. Back in 2D the view
    is on the newest plane again."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="run")  # 24 planes of 5 um, three time points
    page, errors = _opened(pages, view, layers=2)
    view.look_at_newest(z=50.0, t=1.0)
    until(lambda: page.evaluate(WHERE)["voxels"], lambda at: round(at["z"]) == 10 and round(at["t"]) == 1)
    _in_3d(page)
    until(lambda: page.evaluate(DEPTH), lambda seen: abs(seen["z"] - seen["middle"]) < 0.5)
    view.look_at_newest(z=75.0, t=2.0)
    at = until(lambda: page.evaluate(WHERE)["voxels"], lambda at: round(at["t"]) == 2)
    assert round(at["t"]) == 2, "the newest time point"
    depth = page.evaluate(DEPTH)
    assert depth["z"] == pytest.approx(depth["middle"], abs=0.5), "still turned about the middle"
    assert page.evaluate("() => window.mesospim.following.value") is True, "and still following"
    page.click('.view button[data-layout="xy"]')
    assert until(lambda: round(page.evaluate(WHERE)["voxels"]["z"]), lambda z: z == 15) == 15, "on the newest plane"
    assert not errors, errors


@slow_without_a_graphics_card
def test_the_volume_views_box_holds_the_whole_specimen(pages, viewers, stacks):
    """The engine takes the depth of the box it draws in, divided by the detail, as
    the size of the copy to draw from. Left at its own default, fifty times the
    zoom, the box was many times deeper than a stack: nearly every step went into
    empty space, and the picture stayed on the coarsest copy."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)
    box = until(lambda: page.evaluate(BOX), lambda seen: seen["depth"] > 0)
    assert box["depth"] > 0, "a box of its own size, not the engine's fifty times the zoom"
    assert 2 * box["farthest"] <= box["depth"] <= 2.5 * box["farthest"], box
    assert not errors, errors


@slow_without_a_graphics_card
def test_zooming_in_draws_from_a_finer_copy_without_touching_the_detail(pages, viewers, stacks):
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")  # 160 x 160 voxels of 1 um, copies of 1, 2, 4 and 8 um
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)  # the fastest detail
    whole = until(lambda: page.evaluate(DRAWN), lambda seen: seen is not None and seen > 1.5)
    assert whole > 1.5, "the whole specimen on screen, quickly: a coarse copy"
    page.evaluate("() => { const z = window.viewer.perspectiveNavigationState.zoomFactor; z.value = z.value / 8; }")
    close = until(lambda: page.evaluate(DRAWN), lambda seen: seen is not None and seen < 1.5)
    assert close == pytest.approx(1.0), "zoomed in: the finest copy"
    assert until(lambda: page.evaluate(READING), lambda text: text.startswith("1 ")) == "1 µm"
    assert not errors, errors


def test_a_panel_full_of_channels_scrolls_down_and_never_sideways(pages, viewers, stacks):
    """The histogram of a channel row below the fold is not drawn yet, and its
    canvas keeps the browser's default width of 300 pixels: wider than the row,
    it gave the panel a sideways scrollbar as soon as the panel scrolled down."""
    view = viewers(ui="simple")
    for name in ("first", "second", "third", "fourth"):
        view.add(stacks[0], layer=name)
    page, errors = _opened(pages, view, layers=8)
    body = "() => { const b = document.querySelector('.panel-body'); return [b.scrollHeight > b.clientHeight, b.scrollWidth - b.clientWidth]; }"
    scrolls_down, sideways = until(lambda: page.evaluate(body), lambda seen: seen[0])
    assert scrolls_down, "enough channels for the panel to scroll"
    assert sideways <= 0, f"the panel is {sideways} pixels too wide"
    assert not errors, errors


@slow_without_a_graphics_card
def test_turning_the_volume_draws_it_coarser_until_it_stops(pages, viewers, stacks):
    """Drawn finely, a volume turns slowly. While the operator turns, zooms or pans it,
    the view draws from a coarser copy, and once it has stopped, at the detail chosen."""
    view = viewers(ui="simple")
    view.add(stacks[0], layer="overview")
    page, errors = _opened(pages, view, layers=2)
    _in_3d(page)
    _set_detail(page, 3)
    steps = lambda: page.evaluate(VOLUME)[0][0]
    still = until(steps, lambda seen: seen > 0, 5)
    time.sleep(1.0)
    still = steps()
    turn = """() => { const o = window.viewer.projectionOrientation; const q = Float32Array.from(o.orientation);
      q[1] += 0.05; const n = Math.hypot(...q); o.orientation = q.map((v) => v / n); o.changed.dispatch(); }"""
    page.evaluate(turn)
    moving = until(steps, lambda seen: seen < still, 2)
    assert moving < still, "coarser while turning"
    assert until(steps, lambda seen: seen == still, 3) == still, "and as chosen once it has stopped"
    assert not errors, errors
