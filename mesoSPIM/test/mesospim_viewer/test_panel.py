"""The simple interface: our panel over a bare engine, driven in a headless Chromium.

Every control writes engine layer state and nothing else, so each test asks the
engine what changed rather than the panel.
"""

from __future__ import annotations

import time

import pytest

from mesoSPIM.src.mesospim_viewer import Viewer


def _shown(view: Viewer):
    view.fit()
    return view.start()


def test_the_panel_lists_channels_by_acquisition_with_the_engines_own_controls(pages, stacks):
    view = Viewer(ui="simple")
    for stack in stacks:
        view.add(stack, layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        seen = page.evaluate(
            """() => ({
              chrome: document.documentElement.dataset.chrome,
              nativePanel: document.querySelector('.neuroglancer-layer-panel') !== null,
              groups: [...document.querySelectorAll('.group')].map(g => g.dataset.group),
              rows: [...document.querySelectorAll('.channel')].map(r => r.dataset.layer),
              windows: [...document.querySelectorAll('.channel .controls .neuroglancer-invlerp-widget, .channel .controls [class*="invlerp"]')].length,
              swatches: [...document.querySelectorAll('.channel .swatch')].map(s => s.style.background),
              scaleBar: window.viewer.showScaleBar.value, axes: window.viewer.showAxisLines.value,
            })"""
        )
        assert seen["chrome"] == "simple" and seen["nativePanel"] is False
        assert seen["groups"] == ["overview"]
        assert seen["rows"] == ["overview · 488", "overview · 561"]
        assert seen["windows"] >= 2, "each row carries the engine's window control"
        assert seen["swatches"] == ["rgb(0, 255, 102)", "rgb(255, 51, 255)"]
        assert seen["scaleBar"] is True and seen["axes"] is False
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_the_eye_hides_a_channel_and_the_group_eye_hides_them_all(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        visible = "() => window.viewer.layerManager.managedLayers.map(m => m.visible)"
        assert page.evaluate(visible) == [True, True]
        page.click('.channel[data-layer="overview · 561"] button.eye')
        assert page.evaluate(visible) == [True, False]
        assert page.evaluate(
            "() => document.querySelector('.channel[data-layer=\"overview · 561\"]').classList.contains('hidden')"
        )
        page.click('.group[data-group="overview"] > .row > button.eye')
        assert page.evaluate(visible) == [False, False]
        page.click('.group[data-group="overview"] > .row > button.eye')
        assert page.evaluate(visible) == [True, True]
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_2d_and_3d_swap_the_layout_and_the_volume_rendering(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        state = "() => ({layout: window.viewer.layout.toJSON(), modes: window.viewer.layerManager.managedLayers.map(m => m.layer.volumeRenderingMode.toJSON() ?? 'off'), on: [...document.querySelectorAll('.view button.on')].map(b => b.dataset.layout)})"
        assert page.evaluate(state) == {"layout": "xy", "modes": ["off", "off"], "on": ["xy"]}
        page.click('.view button[data-layout="3d"]')
        assert page.evaluate(state) == {"layout": "3d", "modes": ["max", "max"], "on": ["3d"]}
        page.click('.view button[data-layout="xy"]')
        assert page.evaluate(state) == {"layout": "xy", "modes": ["off", "off"], "on": ["xy"]}
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_the_sliders_step_through_depth_and_time(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        sliders = "() => Object.fromEntries([...document.querySelectorAll('.axis-slider')].map(s => [s.id, {hidden: s.hidden, min: s.querySelector('input').min, max: s.querySelector('input').max, reading: s.querySelector('.reading').textContent}]))"
        seen = page.evaluate(sliders)
        assert (
            seen["slider-z"]["min"] == "0"
            and seen["slider-z"]["max"] == "23"
            and not seen["slider-z"]["hidden"]
        )
        assert (
            seen["slider-t"]["min"] == "0"
            and seen["slider-t"]["max"] == "2"
            and not seen["slider-t"]["hidden"]
        )
        assert seen["slider-z"]["reading"].endswith("/ 24") and seen["slider-t"][
            "reading"
        ].endswith("/ 3")

        page.evaluate(
            "() => { const i = document.querySelector('#slider-t input'); i.value = '2'; i.dispatchEvent(new Event('input')); }"
        )
        page.evaluate(
            "() => { const i = document.querySelector('#slider-z input'); i.value = '5'; i.dispatchEvent(new Event('input')); }"
        )
        position = page.evaluate(
            "() => { const v = window.viewer; const s = v.navigationState.position.coordinateSpace.value; const p = v.navigationState.position.value; return Object.fromEntries(s.names.map((n, i) => [n, p[i]])); }"
        )
        assert position["t"] == pytest.approx(2.0) and position["z"] == pytest.approx(5.0)
        assert page.evaluate(sliders)["slider-z"]["reading"] == "6 / 24"

        # Python moving the camera moves the slider too
        view.look_at(z=12 * 5.0)  # micrometres: 5 um planes
        deadline = time.time() + 5
        while time.time() < deadline and page.evaluate(sliders)["slider-z"]["reading"] != "13 / 24":
            time.sleep(0.1)
        assert page.evaluate(sliders)["slider-z"]["reading"] == "13 / 24"
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_adjustments_in_the_panel_survive_a_tile_landing(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        page.click('.channel[data-layer="overview · 561"] button.eye')
        page.click('.view button[data-layout="3d"]')
        # the detail slider to its top step, the gain up a little
        page.evaluate(
            """() => {
              const detail = document.querySelector('.card.volume input.detail');
              detail.value = detail.max;
              detail.dispatchEvent(new Event('input'));
              const gain = document.querySelector('.card.volume input.gain');
              gain.value = '2';
              gain.dispatchEvent(new Event('input'));
            }"""
        )
        view.add(stacks[1], layer="overview")
        deadline = time.time() + 20
        sources = (
            "() => window.viewer.layerManager.managedLayers.map(m => m.layer.dataSources.length)"
        )
        while time.time() < deadline and page.evaluate(sources) != [2, 2]:
            time.sleep(0.2)
        assert page.evaluate(sources) == [2, 2]
        assert page.evaluate(
            "() => window.viewer.layerManager.managedLayers.map(m => m.visible)"
        ) == [True, False]
        assert page.evaluate(
            "() => window.viewer.layerManager.managedLayers.map(m => m.layer.volumeRenderingMode.toJSON())"
        ) == ["max", "max"]
        assert page.evaluate(
            "() => window.viewer.layerManager.managedLayers.map(m => [m.layer.volumeRenderingDepthSamplesTarget.value, m.layer.volumeRenderingGain.value])"
        ) == [[1024, 2], [1024, 2]]
        assert page.evaluate(
            "() => [...document.querySelectorAll('.channel')].map(r => r.classList.contains('hidden'))"
        ) == [False, True]
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_the_panel_folds_away_and_comes_back(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        width = (
            "() => document.querySelector('.mesospim-panel')?.getBoundingClientRect().width ?? 0"
        )
        picture = (
            "() => window.viewer.display.panels.values().next().value.renderViewport.logicalWidth"
        )
        assert page.evaluate(width) > 250
        narrow = page.evaluate(picture)
        page.click(".panel-head button.fold")
        time.sleep(0.5)
        assert page.evaluate(width) == 0
        assert page.evaluate(picture) > narrow, "the picture takes the room the panel gave up"
        page.click("#fold")
        time.sleep(0.5)
        assert page.evaluate(width) > 250
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_the_histogram_is_drawn_inside_the_row(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
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
        page.close()
    finally:
        view.stop()


def test_the_dropdown_offers_the_sessions_acquisitions_and_reports_a_choice(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    chosen = []
    view.on_choice(chosen.append)
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        assert page.evaluate("() => document.querySelector('.card.acquisition').hidden") is True

        view.offer_acquisitions(["run_03", "run_02", "run_01"], 0)
        deadline = time.time() + 5
        options = "() => [...document.querySelectorAll('.card.acquisition option')].map(o => o.textContent)"
        while time.time() < deadline and len(page.evaluate(options)) != 3:
            time.sleep(0.1)
        assert page.evaluate(options) == ["run_03 (current)", "run_02", "run_01"]
        assert page.evaluate("() => document.querySelector('.card.acquisition').hidden") is False
        # the dropdown sits above the view switch
        assert page.evaluate(
            "() => [...document.querySelectorAll('.panel-body > .card')].map(c => c.className)"
        )[:1] == ["card acquisition"]
        assert page.evaluate(
            "() => document.querySelector('.stage-overlay .segmented.view') !== null"
        )

        page.select_option("select.chooser", "2")
        deadline = time.time() + 5
        while time.time() < deadline and not chosen:
            time.sleep(0.1)
        assert chosen == [2]

        view.offer_acquisitions(["run_03", "run_02", "run_01"], 2)
        deadline = time.time() + 5
        while (
            time.time() < deadline
            and page.evaluate("() => document.querySelector('select.chooser').value") != "2"
        ):
            time.sleep(0.1)
        assert page.evaluate("() => document.querySelector('select.chooser').value") == "2"

        # A folder of acquisitions opened from disk: nothing there is being acquired.
        view.offer_acquisitions(["run_03", "run_02", "run_01"], 0, live=False)
        deadline = time.time() + 5
        while time.time() < deadline and page.evaluate(options)[0] != "run_03":
            time.sleep(0.1)
        assert page.evaluate(options) == ["run_03", "run_02", "run_01"]
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_the_3d_card_drives_projection_detail_gain_planes_and_the_look(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="overview")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        assert page.evaluate("() => document.querySelector('.card.volume').hidden") is True
        page.click('.view button[data-layout="3d"]')
        assert page.evaluate("() => document.querySelector('.card.volume').hidden") is False
        assert page.evaluate("() => window.viewer.showPerspectiveSliceViews.value") is False, (
            "a pure volume"
        )

        def layers(expression: str):
            return page.evaluate(
                f"() => window.viewer.layerManager.managedLayers.map(m => m.layer).map(l => {expression})"
            )

        assert page.evaluate("() => document.getElementById('slider-t').hidden") is False
        page.click('.card.volume button[data-mode="on"]')
        assert layers("l.volumeRenderingMode.toJSON()") == ["on", "on"]
        assert (
            page.evaluate("() => document.querySelector('.card.volume button.on').dataset.mode")
            == "on"
        )
        page.click('.card.volume button[data-mode="max"]')
        assert layers("l.volumeRenderingMode.toJSON()") == [
            "max",
            "max",
        ]

        page.evaluate(
            "() => { const i = document.querySelector('.card.volume input.detail'); i.value = '3'; i.dispatchEvent(new Event('input')); }"
        )
        assert layers("l.volumeRenderingDepthSamplesTarget.value") == [
            256,
            256,
        ]
        assert (
            page.evaluate(
                "() => document.querySelector('.card.volume input.detail + .reading').textContent"
            )
            == "256 steps"
        )

        page.evaluate(
            "() => { const i = document.querySelector('.card.volume input.gain'); i.value = '2.5'; i.dispatchEvent(new Event('input')); }"
        )
        assert layers("l.volumeRenderingGain.value") == [2.5, 2.5]

        page.click(".card.volume input.slices")
        assert page.evaluate("() => window.viewer.showPerspectiveSliceViews.value") is True

        orientation = "() => window.viewer.projectionOrientation.toJSON() ?? [0, 0, 0, 1]"
        page.click('.card.volume button[data-look="front"]')
        assert page.evaluate(orientation) == pytest.approx([-0.7071, 0, 0, 0.7071], abs=1e-3)
        page.click('.card.volume button[data-look="top"]')
        assert page.evaluate(orientation) == [0, 0, 0, 1]
        page.click('.view button[data-layout="xy"]')
        assert page.evaluate("() => document.querySelector('.card.volume').hidden") is True
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def _numbered(path):
    """A store whose every voxel says where it is: 1000 per time point plus 200 per plane."""
    import json

    import numpy as np

    from mesoSPIM.src.mesospim_viewer.demo import _write_array

    data = np.zeros((3, 1, 4, 64, 64), np.uint16)
    for t in range(3):
        for z in range(4):
            data[t, 0, z] = 1000 * (t + 1) + 200 * z
    _write_array(path / "0", data, (1, 1, 1, 64, 64))
    axes = [{"name": "t", "type": "time"}, {"name": "c", "type": "channel"}]
    axes += [{"name": name, "type": "space", "unit": "micrometer"} for name in "zyx"]
    scale = {"type": "scale", "scale": [1, 1, 1, 1, 1]}
    (path / ".zgroup").write_text('{"zarr_format": 2}')
    (path / ".zattrs").write_text(
        json.dumps({"multiscales": [{"version": "0.4", "axes": axes, "datasets": [{"path": "0", "coordinateTransformations": [scale]}]}]})
    )
    return path


# What the middle of the picture says, in the numbering of _numbered.
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


def test_the_sliders_show_the_plane_and_time_point_they_name(pages, tmp_path):
    view = Viewer(ui="simple")
    view.add(_numbered(tmp_path / "numbered.ome.zarr"), layer="numbered", window=(0, 5000), colours=["#ffffff"])
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=1)
        for t in range(3):
            for z in range(4):
                page.evaluate(
                    f"() => {{ for (const [id, v] of [['#slider-t', {t}], ['#slider-z', {z}]]) {{"
                    " const i = document.querySelector(id + ' input'); i.value = String(v); i.dispatchEvent(new Event('input')); } }"
                )
                time.sleep(0.3)  # the engine asks for the new plane's chunks on its next frame
                pages.drawn(page, layers=1)
                readings = page.evaluate(
                    "() => ['#slider-t', '#slider-z'].map(id => document.querySelector(id + ' .reading').textContent)"
                )
                assert readings == [f"{t + 1} / 3", f"{z + 1} / 4"]
                assert page.evaluate(READ_MIDDLE) == pytest.approx(1000 * (t + 1) + 200 * z, abs=30), (t, z)
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_an_acquisition_opens_on_its_first_time_point(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="run_01")
    url = _shown(view)
    reading = "() => document.querySelector('#slider-t .reading').textContent"
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        page.wait_for_function(f"() => ({reading})() === '1 / 3'", timeout=5000)

        # The operator's choice stays while more tiles of the same acquisition land...
        page.evaluate(
            "() => { const i = document.querySelector('#slider-t input'); i.value = '2'; i.dispatchEvent(new Event('input')); }"
        )
        view.add(stacks[1], layer="run_01")
        page.wait_for_function("() => window.viewer.layerManager.managedLayers[0].layer.dataSources.length === 2")
        pages.drawn(page, layers=2)
        time.sleep(0.5)
        assert page.evaluate(reading) == "3 / 3"

        # ...and another acquisition opens on its own first time point.
        view.remove("run_01")
        view.add(stacks[0], layer="run_02")
        page.wait_for_function("() => window.viewer.layerManager.managedLayers[0]?.name.startsWith('run_02')")
        pages.drawn(page, layers=2)
        page.wait_for_function(f"() => ({reading})() === '1 / 3'", timeout=5000)
        assert not errors, errors
        page.close()
    finally:
        view.stop()


# Where the camera looks, in micrometres, how far it is zoomed out, and whether
# the Show all button is offered.
OVERVIEW = """() => {
  const n = window.viewer.navigationState, space = n.position.coordinateSpace.value;
  const at = (axis) => { const i = space.names.indexOf(axis); return n.position.value[i] * space.scales[i] * 1e6; };
  const button = document.querySelector('#show-all');
  return { x: at('x'), y: at('y'), zoom: n.zoomFactor.value, showAll: !!button && !button.hidden };
}"""


def _until(page, script: str, wanted, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    seen = page.evaluate(script)
    while time.time() < deadline and seen != wanted:
        time.sleep(0.1)
        seen = page.evaluate(script)
    return seen


def test_show_all_appears_once_the_view_is_moved_and_frames_everything_again(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="first")
    url = _shown(view)
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=2)
        time.sleep(0.5)
        fitted = page.evaluate(OVERVIEW)
        assert fitted["showAll"] is False, "nothing to bring back while the view frames everything"
        assert fitted["x"] == pytest.approx(80, abs=2)

        # The operator zooms in: the view is theirs, and Show all is offered.
        box = page.locator(".neuroglancer-rendered-data-panel").first.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.keyboard.down("Control")
        page.mouse.wheel(0, -300)
        page.keyboard.up("Control")
        assert _until(page, "() => !document.querySelector('#show-all').hidden", True)
        theirs = page.evaluate(OVERVIEW)
        assert theirs["zoom"] < fitted["zoom"]

        # Another acquisition arrives: the view stays where the operator put it.
        view.add(stacks[1], layer="second")
        page.wait_for_function("() => window.viewer.layerManager.managedLayers.length === 4")
        pages.drawn(page, layers=4)
        time.sleep(1.0)
        assert page.evaluate(OVERVIEW) == theirs

        # Show all frames both and hands the view back to overview mode.
        page.click("#show-all")
        time.sleep(0.5)
        both = page.evaluate(OVERVIEW)
        assert both["showAll"] is False
        assert both["x"] == pytest.approx((0 + 144 + 160) / 2, abs=2)
        assert both["zoom"] > fitted["zoom"]
        assert not errors, errors
        page.close()
    finally:
        view.stop()


def test_each_acquisition_has_a_remove_button_where_python_takes_removals(pages, stacks):
    view = Viewer(ui="simple")
    view.add(stacks[0], layer="first")
    view.add(stacks[1], layer="second")
    url = _shown(view)
    buttons = "() => [...document.querySelectorAll('.group .remove')].map(b => b.closest('.group').dataset.group)"
    try:
        page, errors = pages.open(url, width=1100, height=700)
        pages.drawn(page, layers=4)
        assert page.evaluate(buttons) == [], "no remove buttons where nothing can be removed"

        view.on_remove(view.remove)
        assert _until(page, buttons, ["first", "second"]) == ["first", "second"]
        page.click('.group[data-group="first"] .remove')
        assert _until(page, "() => window.viewer.layerManager.managedLayers.map(m => m.name)",
                      ["second · 488", "second · 561"]) == ["second · 488", "second · 561"]
        assert view.layers == ["second"]

        # A message from Python is shown on the picture, and can be closed.
        notice = "() => { const n = document.querySelector('#notice'); return n && !n.hidden ? n.querySelector('.text').textContent : null; }"
        view.say("notes isn't an OME-Zarr folder the viewer can open.")
        assert _until(page, notice, "notes isn't an OME-Zarr folder the viewer can open.") == (
            "notes isn't an OME-Zarr folder the viewer can open."
        )
        page.click("#notice .close")
        assert page.evaluate(notice) is None
        view.say("notes isn't an OME-Zarr folder the viewer can open.")
        assert _until(page, notice, "notes isn't an OME-Zarr folder the viewer can open.") is not None
        view.say("")
        assert _until(page, notice, None) is None
        assert not errors, errors
        page.close()
    finally:
        view.stop()
