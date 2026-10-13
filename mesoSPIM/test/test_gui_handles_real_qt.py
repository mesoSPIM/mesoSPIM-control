"""The Remote Control's handles on mesoSPIM's windows, against the real windows (offscreen).

The camera window is the one the operator watches: these tests build it as mesoSPIM does, show it a
frame, and check that each handle does what the window's own controls do, and that what get_display
reports is what the window shows, in the frame's own pixels (as get_frame gives them) and in um.
"""
import collections
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5 import QtWidgets  # noqa: E402

from mesoSPIM.src.mesoSPIM_CameraWindow import mesoSPIM_CameraWindow  # noqa: E402
from mesoSPIM.src.mesoSPIM_State import mesoSPIM_StateSingleton  # noqa: E402
from mesoSPIM.src.remote_control import gui_handles  # noqa: E402

PACKAGE = Path(__file__).resolve().parents[1]
PIXEL_UM = 6.5


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def main(app):
    """What the camera window and the handles need of mesoSPIM's main window: its config, state and
    Core's display queue, holding one 2048 x 2048 frame shown at subsampling 2."""
    cfg = SimpleNamespace(camera_parameters={"x_pixels": 2048, "y_pixels": 2048},
                          startup={"camera_display_live_subsampling": 2},
                          pixelsize={"1x": PIXEL_UM}, ui_options={"dark_mode": False})
    state = mesoSPIM_StateSingleton()          # mesoSPIM's own state object: a mapping without dict's methods
    for key, value in {"state": "idle", "camera_display_live_subsampling": 2, "zoom": "1x", "shutterconfig": "Left"}.items():
        state[key] = value
    frame = (np.arange(2048 * 2048, dtype=np.uint32) % 4000).astype(np.uint16).reshape(2048, 2048)
    core = SimpleNamespace(frame_queue_display=collections.deque([frame]))
    window = SimpleNamespace(cfg=cfg, state=state, core=core, package_directory=str(PACKAGE))
    window.camera_window = mesoSPIM_CameraWindow(window)
    window.camera_window.update_image_from_deque()
    yield window
    window.camera_window.close()


def apply(main, name, args):
    handles = gui_handles.GuiHandles(main)
    outcome = handles.apply(name, args)
    return outcome, handles.read()


def test_levels_set_remotely_are_the_window_s_levels(main):
    outcome, display = apply(main, "set_display", {"levels": [150, 2500]})
    assert outcome["status"] == "applied"
    assert tuple(main.camera_window.histogram.getLevels()) == pytest.approx((150, 2500))
    assert display["camera_window"]["levels"] == pytest.approx([150, 2500])


def test_adjust_levels_is_the_window_s_own_percentile_stretch(main):
    apply(main, "set_display", {"adjust_levels": {"low_percentile": 10, "high_percentile": 90}})
    shown = main.camera_window.image_view.getImageItem().image
    assert tuple(main.camera_window.histogram.getLevels()) == pytest.approx(
        (np.percentile(shown, 10), np.percentile(shown, 90)))


@pytest.mark.parametrize("name", ["grey", "viridis", "thermal", "magma"])
def test_a_lookup_table_is_applied_and_reported_by_name(main, name):
    outcome, display = apply(main, "set_display", {"colormap": name})
    assert outcome["status"] == "applied" and display["camera_window"]["colormap"] == name
    from pyqtgraph.graphicsItems.GradientEditorItem import Gradients
    shown = main.camera_window.histogram.gradient.saveState()     # the gradient the histogram draws with
    assert sorted((round(p, 6), tuple(c)) for p, c in shown["ticks"]) == \
        sorted((round(p, 6), tuple(c)) for p, c in Gradients[name]["ticks"])


def test_an_unknown_lookup_table_is_refused_with_the_names_there_are(main):
    outcome, _ = apply(main, "set_display", {"colormap": "rainbowish"})
    assert outcome["status"] == "failed" and "viridis" in outcome["error"]


def test_a_box_roi_is_placed_in_frame_pixels_and_read_back_in_frame_pixels_and_um(main):
    """The window shows every 2nd pixel: frame pixels in, frame pixels out; the window holds half."""
    outcome, display = apply(main, "set_display", {"overlay": "box", "box_roi": {"x": 400, "y": 600, "width": 200, "height": 100}})
    assert outcome["status"] == "applied"
    cw = main.camera_window
    assert cw.overlay == "box" and cw.overlayCombo.currentText() == "Box roi"
    assert tuple(cw.roi_box.pos()) == pytest.approx((200, 300)) and tuple(cw.roi_box.size()) == pytest.approx((100, 50))
    box = display["camera_window"]["box_roi"]
    assert (box["x"], box["y"], box["width"], box["height"]) == pytest.approx((400, 600, 200, 100))
    assert (box["width_um"], box["height_um"]) == pytest.approx((200 * PIXEL_UM, 100 * PIXEL_UM))
    # its centre, from the frame's centre: (500 - 1024, 650 - 1024) pixels
    assert (box["offset_x"], box["offset_y"]) == pytest.approx((-524, -374))
    assert (box["offset_x_um"], box["offset_y_um"]) == pytest.approx((-524 * PIXEL_UM, -374 * PIXEL_UM))


def test_a_box_dragged_in_the_window_is_reported_where_it_now_is(main):
    apply(main, "set_display", {"overlay": "box", "box_roi": {"x": 400, "y": 600, "width": 200, "height": 100}})
    main.camera_window.roi_box.setPos((50, 60))            # the operator drags it
    _, display = apply(main, "set_display", {})
    box = display["camera_window"]["box_roi"]
    assert (box["x"], box["y"]) == pytest.approx((100, 120))


def test_a_line_roi_is_placed_and_its_length_read_in_pixels_and_um(main):
    outcome, display = apply(main, "set_display", {"overlay": "line", "line_roi": {"x1": 100, "y1": 200, "x2": 400, "y2": 600}})
    assert outcome["status"] == "applied" and main.camera_window.overlay == "line"
    line = display["camera_window"]["line_roi"]
    assert (line["x1"], line["y1"], line["x2"], line["y2"]) == pytest.approx((100, 200, 400, 600))
    assert line["length"] == pytest.approx(500) and line["length_um"] == pytest.approx(500 * PIXEL_UM)
    assert main.camera_window.get_line_length_px() == pytest.approx(250)      # the window's own measure, display pixels


def test_the_overlay_follows_the_window_s_own_choice(main):
    for overlay, shown in (("none", "Overlay: none"), ("light_sheet_marker", "LS marker"), ("line", "Line roi")):
        outcome, display = apply(main, "set_display", {"overlay": overlay})
        assert outcome["status"] == "applied"
        assert main.camera_window.overlayCombo.currentText() == shown and display["camera_window"]["overlay"] == overlay


def test_the_view_is_set_in_frame_pixels_and_fit_brings_back_the_whole_frame(main):
    """The view keeps square pixels, as the window does: the asked region is shown whole and centred,
    one side fits it exactly, the other widens to the window's shape."""
    _, display = apply(main, "set_display", {"view": {"x": 0, "y": 0, "width": 512, "height": 512}})
    (x0, x1), (y0, y1) = main.camera_window.image_view.getView().viewRange()
    assert x0 <= 0.5 and x1 >= 255.5 and y0 <= 0.5 and y1 >= 255.5             # the asked region, whole
    assert min(x1 - x0, y1 - y0) == pytest.approx(256, abs=1)                    # one side fits it
    assert (x0 + x1) / 2 == pytest.approx(128, abs=1) and (y0 + y1) / 2 == pytest.approx(128, abs=1)
    view = display["camera_window"]["view"]
    assert view["x"] == pytest.approx(x0 * 2) and view["width"] == pytest.approx((x1 - x0) * 2)   # reported as shown
    _, display = apply(main, "set_display", {"view": "fit"})
    view = display["camera_window"]["view"]
    assert view["x"] <= 0 and view["y"] <= 0 and view["width"] >= 2048 and view["height"] >= 2048


def test_a_box_outside_the_frame_is_refused_and_nothing_changes(main):
    apply(main, "set_display", {"overlay": "box", "box_roi": {"x": 0, "y": 0, "width": 100, "height": 100}})
    outcome, display = apply(main, "set_display", {"box_roi": {"x": 2000, "y": 0, "width": 100, "height": 100}})
    assert outcome["status"] == "failed" and "outside the frame" in outcome["error"]
    assert display["camera_window"]["box_roi"]["x"] == pytest.approx(0)


def test_the_display_names_the_frame_it_is_measured_in(main):
    _, display = apply(main, "set_display", {})
    camera = display["camera_window"]
    assert camera["frame"] == {"width": 2048, "height": 2048, "shown_every": 2, "pixel_um": PIXEL_UM}
    assert "status" in camera and camera["visible"] in (True, False)


def test_a_failing_read_is_reported_and_never_stops_mesospim(main):
    """The copy of what the windows show is a convenience: if reading a window fails, get_display says
    why and mesoSPIM carries on (the handles are built while mesoSPIM starts)."""
    handles = gui_handles.GuiHandles(main)
    main.camera_window.image_view = None                     # a window in a state the handles cannot read
    handles.refresh()
    assert handles.display()["error"].startswith("reading the windows failed: AttributeError")


def test_before_the_first_frame_the_display_is_read_from_the_configured_camera(app):
    """As mesoSPIM starts: the camera window is built, no frame has come yet."""
    state = mesoSPIM_StateSingleton()
    for key, value in {"state": "init", "camera_display_live_subsampling": 2, "zoom": "1x", "shutterconfig": "Left"}.items():
        state[key] = value
    # a camera that is not square: the window shows its frames turned, x_pixels as the height
    cfg = SimpleNamespace(camera_parameters={"x_pixels": 2960, "y_pixels": 5056},
                          startup={"camera_display_live_subsampling": 2},
                          pixelsize={"1x": PIXEL_UM}, ui_options={"dark_mode": False})
    window = SimpleNamespace(cfg=cfg, state=state, core=SimpleNamespace(frame_queue_display=collections.deque()),
                             package_directory=str(PACKAGE))
    window.camera_window = mesoSPIM_CameraWindow(window)
    try:
        handles = gui_handles.GuiHandles(window)
        handles.refresh()
        shown = handles.display()
        assert "error" not in shown, shown.get("error")
        assert shown["camera_window"]["frame"] == {"width": 5056, "height": 2960, "shown_every": 2, "pixel_um": PIXEL_UM}
        assert (window.camera_window.x_image_width, window.camera_window.y_image_width) == (5056, 2960)   # as the window has it
    finally:
        window.camera_window.close()


def test_a_lookup_table_of_one_s_own_and_its_colour_mode(main):
    ticks = [[0.0, [0, 0, 0, 255]], [0.5, [255, 0, 0, 255]], [1.0, [255, 255, 0, 255]]]
    outcome, display = apply(main, "set_display", {"colormap_ticks": ticks, "colormap_mode": "hsv"})
    assert outcome["status"] == "applied"
    state = main.camera_window.histogram.gradient.saveState()
    assert state["mode"] == "hsv" and sorted([p, list(c)] for p, c in state["ticks"]) == ticks
    camera = display["camera_window"]
    assert camera["colormap"] == "custom" and camera["colormap_ticks"] == ticks and camera["colormap_mode"] == "hsv"


def test_the_histogram_s_range_and_the_inverted_axes(main):
    outcome, display = apply(main, "set_display", {"histogram_range": [0, 5000], "invert_x": True, "invert_y": False})
    assert outcome["status"] == "applied"
    low, high = main.camera_window.histogram.item.vb.viewRange()[1]
    assert (low, high) == pytest.approx((0, 5000), abs=1)
    assert main.camera_window.image_view.getView().xInverted() is True
    camera = display["camera_window"]
    assert camera["invert_x"] is True and camera["invert_y"] is False and camera["histogram_range"] == pytest.approx([0, 5000], abs=1)


def test_the_image_view_s_own_roi_shows_its_profile(main):
    main.camera_window.show()
    outcome, display = apply(main, "set_display", {"profile_roi": {"shown": True, "x": 200, "y": 400, "width": 600, "height": 100}})
    assert outcome["status"] == "applied"
    view = main.camera_window.image_view
    assert view.ui.roiBtn.isChecked() and tuple(view.roi.pos()) == pytest.approx((100, 200))
    profile = display["camera_window"]["profile_roi"]
    assert profile["shown"] and (profile["x"], profile["y"], profile["width"]) == pytest.approx((200, 400, 600))
    assert len(profile["profile"]["mean"]) > 1
    _, display = apply(main, "set_display", {"profile_roi": {"shown": False}})
    assert not view.ui.roiBtn.isChecked() and display["camera_window"]["profile_roi"] == {"shown": False}


def test_normalization_as_the_image_view_s_menu_sets_it(main):
    outcome, display = apply(main, "set_display", {"normalization": {"mode": "divide", "frame": True}})
    assert outcome["status"] == "applied"
    ui = main.camera_window.image_view.ui
    assert ui.normDivideRadio.isChecked() and ui.normFrameCheck.isChecked()
    assert display["camera_window"]["normalization"] == {"mode": "divide", "roi": False, "frame": True, "time_range": False}
    apply(main, "set_display", {"normalization": {"mode": "off", "frame": False}})
    assert ui.normOffRadio.isChecked()


def test_a_stack_opened_in_the_camera_window_steps_through_its_frames(main, tmp_path):
    import tifffile
    stack = (np.arange(6 * 64 * 64) % 3000).astype(np.uint16).reshape(6, 64, 64)
    path = tmp_path / "stack.tif"
    tifffile.imwrite(path, stack)
    handles = gui_handles.GuiHandles(main)
    outcome = handles.apply("open_image_file", {"path": str(path)})
    assert outcome["status"] == "applied" and outcome["result"]["shape"] == [6, 64, 64]
    frames = main.camera_window.image_view.image
    count = frames.shape[0]                                    # the window subsamples a stack along its first axis too
    outcome = handles.apply("set_display", {"frame_index": count - 1})
    assert outcome["status"] == "applied" and main.camera_window.image_view.currentIndex == count - 1
    assert handles.read()["camera_window"]["frames"] == {"count": count, "index": count - 1}
    outcome = handles.apply("set_display", {"frame_index": count})
    assert outcome["status"] == "failed" and f"0..{count - 1}" in outcome["error"]


def test_frame_index_without_a_stack_says_what_it_is_for(main):
    outcome, _ = apply(main, "set_display", {"frame_index": 0})
    assert outcome["status"] == "failed" and "open_image_file" in outcome["error"]


def test_a_picture_of_the_camera_window_comes_back_as_png_or_as_a_file(main, tmp_path):
    import base64
    main.camera_window.show()
    handles = gui_handles.GuiHandles(main)
    outcome = handles.apply("get_picture", {"window": "camera", "max_size": 256})
    assert outcome["status"] == "applied"
    picture = outcome["result"]
    assert base64.b64decode(picture["base64"])[:8] == b"\x89PNG\r\n\x1a\n" and max(picture["width"], picture["height"]) <= 256
    path = tmp_path / "camera.png"
    outcome = handles.apply("get_picture", {"window": "camera", "path": str(path), "max_size": 4096})
    assert outcome["status"] == "applied" and path.stat().st_size > 1000


# --- the two handlers whose dialogs stand in a remote caller's way, repeated exactly -------------
CONFIG_TEXT = ("startup = {\n    'sweeptime': 0.1,  # s\n    \"camera_exposure_time\": 0.02,\n    'galvo_l_frequency': 99.9,\n"
               "    'camera_binning': '1x1',\n}\n")


def test_save_to_config_writes_exactly_what_the_window_s_own_save_writes(app, tmp_path, monkeypatch):
    from PyQt5 import QtWidgets as W
    from mesoSPIM.src.mesoSPIM_MainWindow import mesoSPIM_MainWindow
    state = mesoSPIM_StateSingleton()
    for i, key in enumerate(gui_handles.CONFIG_PARAMETERS):
        state[key] = round(0.5 + i * 1.25, 3)
    state["camera_binning"] = "2x2"
    by_window, by_call = tmp_path / "window_config.py", tmp_path / "call_config.py"
    by_window.write_text(CONFIG_TEXT, encoding="utf-8")
    by_call.write_text(CONFIG_TEXT, encoding="utf-8")
    monkeypatch.setattr(W.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(by_window), "")))
    monkeypatch.setattr(W.QMessageBox, "question", staticmethod(lambda *a, **k: W.QMessageBox.Yes))
    monkeypatch.setattr(W.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    window = SimpleNamespace(cfg=SimpleNamespace(__file__=str(by_window)), state=state)
    mesoSPIM_MainWindow.save_parameters_to_config(window)                  # the window's own Save, dialogs answered
    appended = gui_handles.parameters_to_config(str(by_call), state, str(by_call))
    assert by_call.read_text(encoding="utf-8") == by_window.read_text(encoding="utf-8")
    assert "'sweeptime': 0.5" in by_call.read_text(encoding="utf-8") and "camera_exposure_time" not in appended


@pytest.mark.parametrize("flip", [False, True])
def test_auto_illumination_lights_the_tiles_exactly_as_the_window_s_own_button(flip):
    from mesoSPIM.src.mesoSPIM_AcquisitionManagerWindow import mesoSPIM_AcquisitionManagerWindow
    xs = [500.0, -1200.0, 0.0, 3000.0, 0.0, 250.0, -40.0]

    class Model:
        def __init__(self):
            self.sides = {}

        def rowCount(self):
            return len(xs)

        def getXPosition(self, row):
            return xs[row]

        def setShutterconfig(self, row, side):
            self.sides[row] = side

    window = SimpleNamespace(model=Model(), cfg=SimpleNamespace(ui_options={"flip_auto_LR_illumination": flip}),
                             display_information=lambda *a: None)       # the confirmation box, answered OK
    mesoSPIM_AcquisitionManagerWindow.auto_illumination(window)
    assert gui_handles.illumination_by_x(xs, flip) == [window.model.sides[row] for row in range(len(xs))]


# --- the Utils menu's analyses: the same numbers as the tools' own windows ---------------------
def quiet_dialogs(monkeypatch):
    from PyQt5 import QtWidgets as W
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(W.QMessageBox, name, staticmethod(lambda *a, **k: None))


def test_the_psf_analysis_is_the_psf_tool_s_own(app, tmp_path, monkeypatch):
    """The tool's own 3-bead simulation (lateral FWHM 1.0 um, axial 2.0 um), analysed by its window and
    by the call: the same beads, the same widths, and the widths it was built with."""
    import tifffile
    from mesoSPIM.src.utils.psf_gui_qt import PSFMainWindow
    quiet_dialogs(monkeypatch)
    window = PSFMainWindow()
    window.simulate_demo()                                           # loads the stack and runs the window's analysis
    path = tmp_path / "beads.tif"
    tifffile.imwrite(path, window.im.astype(np.uint16))
    result = gui_handles.psf_analysis({"path": str(path), "magnification": window.mag, "pixel_pitch_um": window.pixel_pitch_micron,
                                       "z_step_um": window.px_axial_micron, "min_intensity": window.thresh_edit.value(),
                                       "min_bead_distance_um": window.min_bead_distance_um, "z_fit_window_um": window.z_fit_window_um})
    by_window = window.stats_df
    assert result["beads_found"] == len(by_window) == 3
    assert [b["fwhm_lateral_um"] for b in result["beads"]] == pytest.approx(list(by_window["FWHMlat"]))
    assert [b["fwhm_axial_um"] for b in result["beads"]] == pytest.approx(list(by_window["FWHMax"]))
    assert result["fwhm_lateral_um"]["median"] == pytest.approx(1.0, rel=0.1)
    assert result["fwhm_axial_um"]["median"] == pytest.approx(2.0, rel=0.1)
    window.close()


def focus_tilted_stack(path, tilt):
    """A textured z-stack whose sharpest plane moves across X by `tilt` planes."""
    import tifffile
    from scipy.ndimage import gaussian_filter
    texture = np.random.default_rng(1).random((128, 256)) * 3000 + 200
    planes = []
    for z in range(21):
        plane = np.empty_like(texture)
        for block in range(8):
            columns = slice(block * 32, (block + 1) * 32)
            best = 10 + tilt * (block - 3.5) / 3.5
            plane[:, columns] = gaussian_filter(texture, sigma=0.4 + 0.6 * abs(z - best))[:, columns]
        planes.append(plane)
    tifffile.imwrite(path, np.array(planes).astype(np.uint16))
    return str(path)


def test_the_field_curvature_analysis_is_the_tool_s_own(app, tmp_path, monkeypatch):
    from mesoSPIM.src.utils.field_curvature_gui_qt import FieldCurvatureMainWindow
    quiet_dialogs(monkeypatch)
    paths = [focus_tilted_stack(tmp_path / "flat.tif", 0), focus_tilted_stack(tmp_path / "tilted.tif", 4)]
    window = FieldCurvatureMainWindow(filenames=paths)
    window.run_analysis()
    result = gui_handles.field_curvature_analysis({"channels": [{"path": p} for p in paths], "magnification": window.mag,
                                                   "pixel_pitch_um": window.pixel_pitch_micron, "z_step_um": window.z_step_micron,
                                                   "n_rois_x": int(window.n_rois_x_edit.value()), "n_rois_y": int(window.n_rois_y_edit.value())})
    for channel in result["channels"]:
        by_window = window.metrics[channel["path"]]
        assert channel["metrics"] == pytest.approx({k: float(v) for k, v in by_window.items()})
        assert np.allclose(channel["best_focus_um"], window.z_profiles[channel["path"]])
    flat, tilted = result["channels"]
    assert np.ptp(tilted["sections_um"]["x"]) > np.ptp(flat["sections_um"]["x"])      # the tilt is in the sections
    detrended = gui_handles.field_curvature_analysis({"channels": [{"path": p} for p in paths], "z_step_um": window.z_step_micron,
                                                      "magnification": window.mag, "pixel_pitch_um": window.pixel_pitch_micron,
                                                      "n_rois_x": 16, "n_rois_y": 16, "tilt_reference": paths[1]})
    assert detrended["channels"][1]["sections_um"]["tilt_subtracted"] is True
    assert np.ptp(detrended["channels"][1]["sections_um"]["x"]) < np.ptp(tilted["sections_um"]["x"])
    window.close()



def test_an_outcome_is_published_only_with_the_display_it_led_to(main):
    """Found by the live sweep: the outcome "applied" was kept before the copy of the windows was
    renewed, so a caller polling in between read the old levels next to it."""
    handles = gui_handles.GuiHandles(main)
    handles.refresh()
    seen = []
    keep = handles.keep

    def keep_and_look(number, outcome):
        seen.append(handles.display()["camera_window"]["levels"])      # what a poll would read with the outcome
        keep(number, outcome)
    handles.keep = keep_and_look
    handles.perform(1, "set_display", {"levels": [111, 2222]})
    assert seen == [[111.0, 2222.0]]
