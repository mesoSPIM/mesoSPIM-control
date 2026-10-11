"""The Remote Control's handles on mesoSPIM's windows: what an operator can do and see there, by call.

Calls over TCP, MCP and the AI Assistant reach the instrument through Core. Much of what the operator
does lives only in the windows, though: the camera window's levels, lookup table, view and regions of
interest, the contrast map, the tile overview, the main window's tabs and readouts, the acquisition
table's grouping, which windows are open. This module reaches those windows from outside and works
them with their own controls and methods (the overlay drop-down, set_roi, the histogram's gradient,
the image view's ROI button, the grouping buttons, the menu's actions), so a window behaves exactly as
when the operator does the same, and nothing in mesoSPIM's own files changes for it. What the calls
accept is decided in commands.py, with the same validators as every other call; this module only
carries out what was accepted.

Window work happens on the GUI thread, and Core must never wait for that thread (it may itself be
waiting for Core). So a display call is handed to the GUI thread and returns at once with a request
number; the GUI thread carries it out and keeps a copy of what the windows show, which get_display
reads without waiting. Positions in the camera window are spoken in the camera frame's own pixels
(x the column, y the row, as get_frame gives the frame) and in micrometres, whatever subsampling the
window shows the frame at.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""
import base64
import importlib.util
import re
import statistics
import itertools
import logging
import os
import threading
from pathlib import Path

import numpy as np
from PyQt5 import QtCore, QtWidgets

from .dispatcher import ValidationError, fail_operation, finish_operation

logger = logging.getLogger(__name__)

# The camera window's overlay drop-down, by the names the calls use.
OVERLAYS = {"none": "Overlay: none", "box": "Box roi", "line": "Line roi", "light_sheet_marker": "LS marker"}
OVERLAY_OF_WINDOW = {None: "none", "box": "box", "line": "line", "LS marker": "light_sheet_marker"}
NORMALIZATIONS = ("off", "subtract", "divide")
GROUPINGS = ("none", "laser", "illumination", "selected")
# The windows a call can show, hide or picture, by the names the calls use.
WINDOWS = ("main", "camera", "acquisition_manager", "tile_overview", "webcam", "contrast", "processor_chain", "optimizer")
PICTURE_MAX = 4096
PROFILE_POINTS = 256
KEPT_OUTCOMES = 50
REFRESH_MS = 250
WEBCAM_TIMEOUT_MS = 5000


def presets():
    """The lookup tables the histograms offer: pyqtgraph's gradient presets. Read from pyqtgraph's own
    table of them without importing pyqtgraph, which needs a running Qt; the calls check names on
    Core's thread too."""
    spec = importlib.util.find_spec("pyqtgraph")
    path = Path(spec.origin).parent / "graphicsItems" / "GradientPresets.py"
    module = importlib.util.module_from_spec(importlib.util.spec_from_file_location("gradient_presets", path))
    module.__spec__.loader.exec_module(module)
    return module.Gradients


def colormaps():
    return list(presets())


def frame_size(core, cfg):
    """(width, height) of the camera frame as the windows show it: the frame on display, else the
    camera's configured size, turned as the camera window turns it (its x_image_width is the
    configured y_pixels: "flipped to account for image rotation")."""
    queue = getattr(core, "frame_queue_display", None)
    if queue:
        height, width = queue[0].shape[-2:]
    else:
        camera = cfg.camera_parameters
        width, height = camera["y_pixels"], camera["x_pixels"]
    return int(width), int(height)


# The Parameters-tab values MainWindow.save_parameters_to_config writes back into a config file, in
# its order. Kept equal to that handler by test_gui_handles_real_qt (it runs both on one file).
CONFIG_PARAMETERS = (
    "sweeptime", "camera_exposure_time", "camera_delay_%", "camera_pulse_%",
    "laser_l_delay_%", "laser_r_delay_%", "laser_l_pulse_%", "laser_r_pulse_%",
    "laser_l_max_amplitude_%", "laser_r_max_amplitude_%",
    "galvo_l_frequency", "galvo_r_frequency", "galvo_l_offset", "galvo_r_offset", "galvo_l_phase", "galvo_r_phase",
    "etl_l_delay_%", "etl_r_delay_%", "etl_l_ramp_rising_%", "etl_r_ramp_rising_%",
    "etl_l_ramp_falling_%", "etl_r_ramp_falling_%",
    "camera_binning", "camera_display_live_subsampling", "camera_display_acquisition_subsampling",
)


def parameters_to_config(config_file, state, save_path):
    """Save to config without its dialogs: what MainWindow.save_parameters_to_config writes, read from
    config_file and written to save_path. Each value replaces its entry where the file has one; the
    rest are appended as a startup.update (format 2: they live in the hardware file). Returns the
    keys appended."""
    params = {key: state[key] for key in CONFIG_PARAMETERS}
    with open(config_file, "r", encoding="utf-8") as file:
        content = file.read()
    skipped = []
    for key, value in params.items():
        pattern = r"(['\"]" + re.escape(key) + r"['\"]\s*:\s*)([^,\n#]+)"
        new_content, count = re.subn(pattern, r"\g<1>" + repr(value), content)
        if count > 0:
            content = new_content
        else:
            skipped.append(key)
    if skipped:
        content += ("\n\nstartup.update({\n" + "".join(f"    {k!r}: {params[k]!r},\n" for k in skipped) + "})\n")
    with open(save_path, "w", encoding="utf-8") as file:
        file.write(content)
    return skipped


def illumination_by_x(x_positions, flip=False):
    """Auto L/R illumination without its confirmation box: AcquisitionManagerWindow.auto_illumination's
    rule. A tile left of the median X is lit from the right, the others from the left; the config's
    ui_options flip_auto_LR_illumination swaps the two. Kept equal to that handler by the tests."""
    median = statistics.median(x_positions)
    sides = []
    for x in x_positions:
        side = "Right" if x < median else "Left"
        sides.append({"Left": "Right", "Right": "Left"}[side] if flip else side)
    return sides


ANALYSES = ("analyse_psf", "analyse_field_curvature")
LISTED_BEADS = 500


def finite(value):
    """A number for JSON: NaN (a fit that failed) as None."""
    value = float(value)
    return None if not np.isfinite(value) else value


def psf_analysis(args):
    """Utils > PSF (beads) analysis's Run analysis (utils.psf_gui_qt), without its window: the same
    options from the same parameters (lateral pixel = pixel pitch / magnification, axial = the Z
    step), saturated beads left out when the stack has saturated pixels, the same compute() and the
    same per-bead table; the medians and spreads the window plots, as numbers."""
    from tifffile import imread
    from ..utils import psf_gui_qt as psf

    stack = np.asarray(imread(args["path"]))
    if stack.ndim != 3:
        raise ValidationError(f"expected a 3D (z, y, x) stack, got shape {list(stack.shape)}")
    saturation = None
    if np.issubdtype(stack.dtype, np.integer) and np.any(stack == np.iinfo(stack.dtype).max):
        saturation = int(np.iinfo(stack.dtype).max)
    z_min, z_max = args.get("z_min", 0), args.get("z_max", stack.shape[0] - 1)
    if not 0 <= z_min < z_max <= stack.shape[0] - 1:
        raise ValidationError(f"z_min and z_max must satisfy 0 <= z_min < z_max <= {stack.shape[0] - 1}")
    lateral = args["pixel_pitch_um"] / args["magnification"]
    options = {"pxPerUmAx": 1.0 / args["z_step_um"], "pxPerUmLat": 1.0 / lateral,
               "windowUm": [args["z_fit_window_um"], args["min_bead_distance_um"], args["min_bead_distance_um"]],
               "thresh": args["min_intensity"], "saturationValue": saturation}
    psf_list, beads, maxima, centers, _ = psf.compute(stack.astype(np.float32)[z_min:z_max + 1], options)
    rows = []
    for i, ((_, lateral_fit, axial_fit), maximum, centre) in enumerate(zip(psf_list, maxima, centers)):
        rows.append({"bead_id": i + 1, "z": finite(centre[0] + z_min), "y": finite(centre[1]), "x": finite(centre[2]),
                     "max_intensity": finite(maximum),
                     "fwhm_lateral_um": finite(lateral_fit[3]) if lateral_fit is not None else None,
                     "fwhm_axial_um": finite(axial_fit[3]) if axial_fit is not None else None})

    def spread(key):
        values = np.array([r[key] for r in rows if r[key] is not None], dtype=float)
        if not len(values):
            return {"median": None, "std": None, "count": 0}
        return {"median": finite(np.median(values)), "std": finite(np.std(values, ddof=0)), "count": int(len(values))}

    return {"path": args["path"], "shape": list(stack.shape), "z_range": [z_min, z_max], "pixel_um": {"lateral": lateral,
            "axial": args["z_step_um"]}, "saturation_value": saturation, "beads_found": len(rows),
            "fwhm_lateral_um": spread("fwhm_lateral_um"), "fwhm_axial_um": spread("fwhm_axial_um"),
            "beads": rows[:LISTED_BEADS]}


def field_curvature_analysis(args):
    """Utils > Field curvature / chromatic shift's Run analysis (utils.field_curvature_gui_qt),
    without its window: per channel the same contrast table, z-profile (best-focus depth of each ROI)
    and summary metrics (depth of field, sag, best plane), and the central X and Y sections with the
    reference channel's tilt subtracted when asked, as the window plots them."""
    from tifffile import TiffFile
    from ..utils import field_curvature_gui_qt as curvature

    n_x, n_y, z_step = args["n_rois_x"], args["n_rois_y"], args["z_step_um"]
    pixel_mm = args["pixel_pitch_um"] / args["magnification"] / 1000.0
    profiles, channels = {}, []
    for channel in args["channels"]:
        table, saturated = curvature.contrast_table_from_stack(channel["path"], n_y, n_x)
        profile = curvature.z_profile_from_table(table, z_step)
        with TiffFile(channel["path"]) as tif:
            frame = tif.pages[0].shape
        metrics = curvature.summary_metrics(table, z_step, frame[1] * pixel_mm, frame[0] * pixel_mm)
        profiles[channel["path"]] = profile
        channels.append({**channel, "saturated_planes": int(saturated), "planes": int(table.shape[0]),
                         "metrics": {key: finite(value) for key, value in metrics.items()},
                         "best_focus_um": [[finite(v) for v in row] for row in profile]})
    reference = profiles.get(args.get("tilt_reference"))
    for channel in channels:
        profile = profiles[channel["path"]]
        section_y, section_x = profile[:, n_x // 2], profile[n_y // 2, :]
        if reference is not None:
            section_y = section_y - curvature.linear_trend(reference[:, n_x // 2])
            section_x = section_x - curvature.linear_trend(reference[n_y // 2, :])
        channel["sections_um"] = {"x": [finite(v) for v in section_x], "y": [finite(v) for v in section_y],
                                  "tilt_subtracted": reference is not None}
    return {"field_of_view_mm": [frame[1] * pixel_mm, frame[0] * pixel_mm], "channels": channels}


def ticks_of(state):
    return sorted([round(float(position), 6), [int(c) for c in color]] for position, color in state["ticks"])


class ImageViewHandle:
    """A pyqtgraph ImageView as the operator works it: its histogram (levels, lookup table, the
    gradient's ticks and colour mode, the histogram's range), the view (region, inverted axes), its
    own ROI button with the profile under the image, and the Menu's normalisation. The camera and
    contrast windows each have one. Positions are in `every` image pixels per view pixel."""

    def __init__(self):
        self.colormap = None
        self.colormap_ticks = None

    def image_view(self):
        raise NotImplementedError

    def every(self):
        return 1

    def read(self):
        view, every = self.image_view(), self.every()
        histogram = view.getHistogramWidget()
        (x0, x1), (y0, y1) = view.getView().viewRange()
        low, high = histogram.getLevels()
        gradient = histogram.gradient.saveState()
        box = view.getView()
        stack = view.image                                             # the whole image or stack the view holds
        shown = {
            "levels": [float(low), float(high)],
            "colormap": self.current_colormap(),
            "colormap_ticks": ticks_of(gradient),
            "colormap_mode": gradient["mode"],
            "histogram_range": [float(v) for v in histogram.item.vb.viewRange()[1]],
            "view": {"x": x0 * every, "y": y0 * every, "width": (x1 - x0) * every, "height": (y1 - y0) * every},
            "invert_x": bool(box.xInverted()), "invert_y": bool(box.yInverted()),
            "normalization": self.normalization(),
        }
        if view.ui.roiBtn.isChecked():
            (x, y), (w, h) = tuple(view.roi.pos()), tuple(view.roi.size())
            profile = {"shown": True, "x": x * every, "y": y * every, "width": w * every, "height": h * every}
            if view.roiCurves:
                xs, ys = view.roiCurves[0].getData()
                if ys is not None and len(ys):
                    step = max(1, int(np.ceil(len(ys) / PROFILE_POINTS)))
                    profile["profile"] = {"x": [float(v) for v in xs[::step]], "mean": [float(v) for v in ys[::step]]}
            shown["profile_roi"] = profile
        else:
            shown["profile_roi"] = {"shown": False}
        if stack is not None and stack.ndim == 3:
            shown["frames"] = {"count": int(stack.shape[0]), "index": int(view.currentIndex)}
        return shown

    def normalization(self):
        ui = self.image_view().ui
        mode = "subtract" if ui.normSubtractRadio.isChecked() else "divide" if ui.normDivideRadio.isChecked() else "off"
        return {"mode": mode, "roi": ui.normROICheck.isChecked(), "frame": ui.normFrameCheck.isChecked(),
                "time_range": ui.normTimeRangeCheck.isChecked()}

    def current_colormap(self):
        """The name of the lookup table the histogram holds: the one set here, else the preset its
        ticks match, else "custom" (the gradient was edited, by hand or with colormap_ticks)."""
        state = self.image_view().getHistogramWidget().gradient.saveState()
        ticks = ticks_of(state)
        if self.colormap is not None and ticks == self.colormap_ticks:
            return self.colormap
        for name, preset in presets().items():
            if ticks_of(preset) == ticks and preset.get("mode", "rgb") == state["mode"]:
                return name
        return "custom"

    def apply(self, args):
        view, every = self.image_view(), self.every()
        histogram = view.getHistogramWidget()
        if "colormap" in args:
            histogram.gradient.loadPreset(args["colormap"])
            self.colormap, self.colormap_ticks = args["colormap"], ticks_of(histogram.gradient.saveState())
        if "colormap_ticks" in args or "colormap_mode" in args:
            state = histogram.gradient.saveState()
            if "colormap_ticks" in args:
                state["ticks"] = [(position, tuple(color)) for position, color in args["colormap_ticks"]]
            state["mode"] = args.get("colormap_mode", state["mode"])
            histogram.gradient.restoreState(state)
        if "levels" in args:
            view.setLevels(*args["levels"])
        if "histogram_range" in args:
            histogram.setHistogramRange(*args["histogram_range"], padding=0)
        if "invert_x" in args:
            view.getView().invertX(args["invert_x"])
        if "invert_y" in args:
            view.getView().invertY(args["invert_y"])
        if "view" in args:
            box = view.getView()
            if args["view"] == "fit":
                box.autoRange(padding=0)
            else:
                region = args["view"]
                box.setRange(xRange=(region["x"] / every, (region["x"] + region["width"]) / every),
                             yRange=(region["y"] / every, (region["y"] + region["height"]) / every), padding=0)
        if "profile_roi" in args:
            profile = args["profile_roi"]
            view.ui.roiBtn.setChecked(profile["shown"])               # the image view's own ROI button
            if profile["shown"] and "x" in profile:
                view.roi.setPos((profile["x"] / every, profile["y"] / every), finish=False)
                view.roi.setSize((profile["width"] / every, profile["height"] / every))
        if "normalization" in args:
            norm, ui = args["normalization"], view.ui
            radio = {"off": ui.normOffRadio, "subtract": ui.normSubtractRadio, "divide": ui.normDivideRadio}
            radio[norm.get("mode", self.normalization()["mode"])].setChecked(True)
            for key, check in (("roi", ui.normROICheck), ("frame", ui.normFrameCheck), ("time_range", ui.normTimeRangeCheck)):
                if key in norm:
                    check.setChecked(norm[key])


class CameraWindowHandle(ImageViewHandle):
    """The camera window: the live view, its overlays and regions of interest, in frame pixels and um."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    @property
    def window(self):
        return self.main_window.camera_window

    def image_view(self):
        return self.window.image_view

    def every(self):
        """How many frame pixels one window pixel stands for: the window shows every n-th pixel."""
        shown = self.window.image_view.getImageItem().image
        queue = getattr(self.main_window.core, "frame_queue_display", None)
        if shown is not None and queue:
            return max(1, int(round(queue[0].shape[-1] / shown.shape[-1])))
        return int(self.main_window.state["camera_display_live_subsampling"])   # what set_image will use

    def frame_size(self):
        return frame_size(self.main_window.core, self.main_window.cfg)

    def pixel_um(self):
        return float(self.main_window.cfg.pixelsize[self.main_window.state["zoom"]])

    def read(self):
        window, every, um = self.window, self.every(), self.pixel_um()
        width, height = self.frame_size()
        shown = {"visible": window.isVisible(),
                 "frame": {"width": width, "height": height, "shown_every": every, "pixel_um": um}}
        shown.update(super().read())
        shown["overlay"] = OVERLAY_OF_WINDOW.get(window.overlay, str(window.overlay))
        shown["status"] = window.status_label.text()
        if window.overlay == "box":
            (x, y), (w, h) = tuple(window.roi_box.pos()), tuple(window.roi_box.size())
            box = {"x": x * every, "y": y * every, "width": w * every, "height": h * every}
            box.update(width_um=box["width"] * um, height_um=box["height"] * um,
                       offset_x=box["x"] + box["width"] / 2 - width / 2, offset_y=box["y"] + box["height"] / 2 - height / 2)
            box.update(offset_x_um=box["offset_x"] * um, offset_y_um=box["offset_y"] * um)
            shown["box_roi"] = box
        if window.overlay == "line":
            (x1, y1), (x2, y2) = self.line_ends()
            line = {"x1": x1 * every, "y1": y1 * every, "x2": x2 * every, "y2": y2 * every}
            line["length"] = float(np.hypot(line["x2"] - line["x1"], line["y2"] - line["y1"]))
            line["length_um"] = line["length"] * um
            shown["line_roi"] = line
        return shown

    def line_ends(self):
        image = self.window.image_view.getImageItem()
        ends = []
        for handle in self.window.roi_line.handles[:2]:
            point = self.window.roi_line.mapToItem(image, handle["pos"])
            ends.append((point.x(), point.y()))
        return ends

    def apply(self, args):
        window, every = self.window, self.every()
        overlay = args.get("overlay") or ("box" if "box_roi" in args else "line" if "line_roi" in args else None)
        if overlay is not None:
            window.overlayCombo.setCurrentText(OVERLAYS[overlay])      # the window's own choice of overlay
        if "box_roi" in args:
            box = args["box_roi"]
            window.set_roi("box", (box["x"] / every, box["y"] / every, box["width"] / every, box["height"] / every))
        if "line_roi" in args:
            line, image = args["line_roi"], window.image_view.getImageItem()
            for handle, (x, y) in zip(window.roi_line.getHandles()[:2], ((line["x1"], line["y1"]), (line["x2"], line["y2"]))):
                point = window.roi_line.mapFromItem(image, QtCore.QPointF(x / every, y / every))
                window.roi_line.movePoint(handle, window.roi_line.mapToParent(point), finish=False)
            window.roi_line.sigRegionChangeFinished.emit(window.roi_line)
        super().apply(args)
        if "adjust_levels" in args:
            adjust = args["adjust_levels"] if isinstance(args["adjust_levels"], dict) else {}
            window.adjust_levels(adjust.get("low_percentile", 25), adjust.get("high_percentile", 99.99))
        if "frame_index" in args:
            frames = window.image_view.image
            if frames is None or frames.ndim != 3:
                raise ValidationError("the camera window shows a single frame; frame_index is for a stack opened with open_image_file")
            if not 0 <= args["frame_index"] < frames.shape[0]:
                raise ValidationError(f"frame_index must be 0..{frames.shape[0] - 1}")
            window.image_view.setCurrentIndex(args["frame_index"])


class ContrastWindowHandle(ImageViewHandle):
    """The contrast window: an 8 x 8 map of the live frame's contrast, (max - min) / (max + min) of
    each cell, in its own image view. Positions are in map cells."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    @property
    def window(self):
        return getattr(self.main_window, "contrast_window", None)

    def image_view(self):
        if self.window is None:
            raise ValidationError("the contrast window is not open: set_windows {show: ['contrast']} opens it")
        return self.window.image_view

    def read(self):
        window = self.window
        if window is None:
            return {"visible": False}
        shown = {"visible": window.isVisible(), "active": bool(getattr(window, "active", False))}
        shown.update(super().read())
        image = window.image_view.getImageItem().image
        if image is not None and image.ndim == 2:
            shown["map"] = [[round(float(v), 4) for v in row] for row in image]
            width, height = frame_size(self.main_window.core, self.main_window.cfg)
            shown["cell"] = {"width": width / image.shape[1], "height": height / image.shape[0]}
        return shown


class TileOverviewHandle:
    """The tile overview: its scale and where its view is scrolled to (0..1 of each scroll bar)."""

    def __init__(self, main_window):
        self.main_window = main_window

    @property
    def window(self):
        return self.main_window.tile_view_window

    def read(self):
        window = self.window
        return {"visible": window.isVisible(), "scale": window.doubleSpinBox_scale.value(),
                "scroll": {"x": fraction(window.tile_overview.horizontalScrollBar()),
                           "y": fraction(window.tile_overview.verticalScrollBar())}}

    def apply(self, args):
        window = self.window
        if "scale" in args:
            window.doubleSpinBox_scale.setValue(args["scale"])            # its own box: on_scale_changed redraws
        if "scroll" in args:
            for key, bar in (("x", window.tile_overview.horizontalScrollBar()), ("y", window.tile_overview.verticalScrollBar())):
                if key in args["scroll"]:
                    bar.setValue(int(round(bar.minimum() + args["scroll"][key] * (bar.maximum() - bar.minimum()))))


class MainWindowHandle:
    """The main window: its tab, and the readouts the operator reads there (the status bar, the three
    progress bars, the time-lapse estimate)."""

    def __init__(self, main_window):
        self.main_window = main_window

    def tabs(self):
        widget = self.main_window.TabWidget
        return [widget.tabText(i) for i in range(widget.count())]

    def read(self):
        window = self.main_window
        bars = {"acquisition": window.AcquisitionProgressBar, "time_point": window.TimePointProgressBar,
                "total": window.TotalProgressBar}
        return {
            "visible": window.isVisible(),
            "tab": window.TabWidget.tabText(window.TabWidget.currentIndex()),
            "tabs": self.tabs(),
            "status_message": window.statusBar().currentMessage(),
            "progress": {name: {"percent": bar.value(), "text": bar.text()} for name, bar in bars.items()},
            "time_lapse_estimate": window.TimelapseEstimateLabel.text(),
            "alignment_toggles": {"zero_left_etl": window.ZeroLeftETLButton.isChecked(),
                                  "zero_right_etl": window.ZeroRightETLButton.isChecked(),
                                  "freeze_galvo": window.freezeGalvoButton.isChecked()},
        }

    def apply(self, args):
        if "tab" in args:
            tabs = self.tabs()
            if args["tab"] not in tabs:
                raise ValidationError(f"tab {args['tab']!r} is not one of {tabs}")
            self.main_window.TabWidget.setCurrentIndex(tabs.index(args["tab"]))


class AcquisitionManagerHandle:
    """The acquisition manager's table as the operator arranges it: which rows are selected, how the
    rows are grouped (an edit to a group's first row then goes to every row of the group), and its
    estimates of the list's time and size."""

    def __init__(self, main_window):
        self.main_window = main_window

    @property
    def window(self):
        return self.main_window.acquisition_manager_window

    def grouping(self):
        window = self.window
        for name, button in (("laser", window.GroupByChannelButton), ("illumination", window.GroupByIlluminationButton),
                             ("selected", window.GroupSelectedButton)):
            if button.isChecked():
                return name
        return "none"

    def selected_rows(self):
        return sorted({index.row() for index in self.window.table.selectionModel().selectedRows()})

    def read(self):
        window = self.window
        return {"visible": window.isVisible(), "grouping": self.grouping(), "selected_rows": self.selected_rows(),
                "time_estimate": window.AcquisitionTimeLabel.text(), "size_estimate": window.PredictedSizeLabel.text()}

    def apply(self, args):
        window = self.window
        if "select_rows" in args:
            rows = args["select_rows"]
            count = window.model.rowCount()
            if any(not 0 <= row < count for row in rows):
                raise ValidationError(f"select_rows must be rows 0..{count - 1}")
            # Whole rows, as a click and Ctrl-clicks on the row headers select them (the window's own
            # set_selected_row selects one cell, which Qt does not count as a selected row).
            selection = window.table.selectionModel()
            selection.clearSelection()
            for row in rows:
                selection.select(window.model.index(row, 0), QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
        if "group" in args:
            buttons = {"laser": window.GroupByChannelButton, "illumination": window.GroupByIlluminationButton,
                       "selected": window.GroupSelectedButton}
            current = self.grouping()
            if current != "none" and current != args["group"]:
                buttons[current].setChecked(False)                     # its own ungroup
            if args["group"] != "none":
                if args["group"] == "selected" and len(self.selected_rows()) < 2:
                    raise ValidationError("grouping selected rows needs two or more selected rows: select_rows first")
                buttons[args["group"]].setChecked(True)


class GuiHandles(QtCore.QObject):
    """Lives on the GUI thread. apply() carries out one request there; read() is what the windows
    show. In mesoSPIM, requests arrive from Core's thread through request(), queued, and the copy
    that get_display reads is refreshed after each request and every REFRESH_MS."""

    sig_request = QtCore.pyqtSignal(int, str, object)
    sig_operation = QtCore.pyqtSignal(object, str, str, object)          # core, operation id, name, args

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.camera = CameraWindowHandle(main_window)
        self.contrast = ContrastWindowHandle(main_window)
        self.tile_overview = TileOverviewHandle(main_window)
        self.main = MainWindowHandle(main_window)
        self.acquisition_manager = AcquisitionManagerHandle(main_window)
        self.numbers = itertools.count(1)
        self.lock = threading.Lock()
        self.outcomes = {}
        self.shown = {}
        self.sig_request.connect(self.perform, type=QtCore.Qt.QueuedConnection)
        self.sig_operation.connect(self.operate, type=QtCore.Qt.QueuedConnection)
        self.operating = None                                         # the window feature running now, if any
        self.timer = None
        self.webcam_capture = None
        self.webcam_pending = {}                                       # capture id -> (request number, args)

    def start(self):
        """Keep the copy fresh while mesoSPIM runs (not in tests, which call read() themselves)."""
        self.refresh()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.setInterval(REFRESH_MS)
        self.timer.start()

    # --- from any thread ----------------------------------------------------------------------
    def request(self, name, args):
        """Hand one request to the GUI thread and return its number at once."""
        number = next(self.numbers)
        with self.lock:
            self.outcomes[number] = {"status": "queued"}
        self.sig_request.emit(number, name, args)
        return number

    def operation(self, core, operation_id, name, args):
        """Hand an instrument operation that only a window can carry out to the GUI thread; the
        operation stays processing (it holds the busy gate) until that thread finishes it."""
        self.sig_operation.emit(core, operation_id, name, args)

    def display(self, number=None):
        """The latest copy of what the windows show, with one request's outcome when asked for."""
        with self.lock:
            shown = dict(self.shown)
            if number is not None:
                shown["request"] = {"number": number, **self.outcomes.get(number, {"status": "unknown"})}
        return shown

    # --- on the GUI thread --------------------------------------------------------------------
    @QtCore.pyqtSlot(int, str, object)
    def perform(self, number, name, args):
        if name == "get_picture" and (args or {}).get("window") == "webcam":
            self.capture_webcam(number, args)                          # completes when the picture arrives
            return
        if name in ANALYSES:
            threading.Thread(target=self.analyse, args=(number, name, args), daemon=True,
                             name=f"Remote Control {name}").start()   # minutes on big stacks: off the GUI thread
            return
        self.record(number, self.apply(name, args))

    def analyse(self, number, name, args):
        """One analysis, in its own thread, as the Utils tools run in a process of their own: it never
        touches the instrument or a window; its outcome is kept for get_display {request}."""
        try:
            result = {"analyse_psf": psf_analysis, "analyse_field_curvature": field_curvature_analysis}[name](args)
            outcome = {"status": "applied", "result": result}
        except ValidationError as error:
            outcome = {"status": "failed", "error": str(error)}
        except Exception as error:
            logger.exception("Remote Control: %s failed", name)
            outcome = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
        self.keep(number, outcome)

    def keep(self, number, outcome):
        """Keep one request's outcome (from any thread)."""
        with self.lock:
            self.outcomes[number] = outcome
            for old in sorted(self.outcomes)[:-KEPT_OUTCOMES]:
                del self.outcomes[old]

    @QtCore.pyqtSlot(object, str, str, object)
    def operate(self, core, operation_id, name, args):
        """Carry out a window's instrument feature, renew the copy of the windows, then end the
        operation: a caller that sees it end sees the windows as it left them."""
        handlers = {"set_alignment_toggles": self.set_alignment_toggles, "optimize": self.optimize,
                    "finish_optimization": self.finish_optimization}
        self.operating = name
        try:
            result, error = handlers[name](args), None
        except ValidationError as refused:
            result, error = None, refused
        except Exception as raised:                                    # the window raised: say so, keep going
            logger.exception("Remote Control: %s failed in the window", name)
            result, error = None, f"{type(raised).__name__}: {raised}"
        finally:
            self.operating = None
        self.refresh()
        if error is None:
            finish_operation(core, operation_id, result)
        else:
            fail_operation(core, operation_id, error)

    def set_alignment_toggles(self, args):
        """The ETL tab's AmpL=0 and AmpR=0 and Freeze galvos, pressed as the operator presses them: their
        own handlers keep the amplitude to restore and lock the boxes that go with them."""
        window = self.main_window
        buttons = {"zero_left_etl": window.ZeroLeftETLButton, "zero_right_etl": window.ZeroRightETLButton,
                   "freeze_galvo": window.freezeGalvoButton}
        for key, value in args.items():
            button = buttons[key]
            if button.isChecked() != value and not button.isEnabled():
                shutter = window.state["shutterconfig"]
                side = {"zero_left_etl": "Left", "zero_right_etl": "Right"}.get(key)
                why = (f"with shutterconfig {shutter!r} the {side.lower()} ETL is not in use" if side and shutter in ("Left", "Right")
                       else "the other ETL is zeroed with both light sheets on")
                raise ValidationError(f"{key} is disabled in the window now: {why}")
            button.setChecked(value)
        return self.alignment_toggles()

    def alignment_toggles(self):
        window = self.main_window
        return {"zero_left_etl": window.ZeroLeftETLButton.isChecked(), "zero_right_etl": window.ZeroRightETLButton.isChecked(),
                "freeze_galvo": window.freezeGalvoButton.isChecked()}

    def optimize(self, args):
        """The optimizer as AUTO Focus and Launch Optimizer open it, run with its own Run: it snaps
        points frames across +- range around the current value, scores each within the camera window's
        box ROI (the whole frame without one), and fits the best. Its result window then waits for
        finish_optimization, as for the operator's Accept or Discard."""
        window = self.main_window
        if window.camera_window.image_view.getImageItem().image is None:     # the optimizer reads it as it opens
            raise ValidationError("the camera window has shown no frame yet: start live first, as for AUTO Focus")
        if "roi" in args:
            box, every = args["roi"], self.camera.every()
            window.camera_window.overlayCombo.setCurrentText(OVERLAYS["box"])
            window.camera_window.set_roi("box", (box["x"] / every, box["y"] / every, box["width"] / every, box["height"] / every))
        try:
            window.launch_optimizer({"mode": args["mode"], "amplitude": args["range"], "n_points": args["points"]})
        except AssertionError as error:                                # its own check: ETL modes need one shutter
            raise ValidationError(f"the optimizer refused: {error}") from None
        optimizer = window.optimizer
        # Its Run reads the mode, search interval and number of points back from its own fields, and a
        # change of mode sets that mode's defaults into them: so the mode first, then the two numbers.
        optimizer.comboBoxMode.setCurrentIndex(optimizer.modes_list.index(args["mode"]))
        optimizer.searchAmpDoubleSpinBox.setValue(args["range"])
        optimizer.nPointsSpinBox.setValue(args["points"])
        optimizer.run_optimization()
        return {"mode": optimizer.mode, "parameter": optimizer.state_key if optimizer.mode != "focus" else "f_pos",
                "old": float(optimizer.ini_state), "new": float(optimizer.new_state),
                "points": [float(v) for v in optimizer.search_grid], "sharpness": [float(v) for v in optimizer.metric_array],
                "waiting_for": "finish_optimization {accept}"}

    def finish_optimization(self, args):
        optimizer = getattr(self.main_window, "optimizer", None)
        results = getattr(optimizer, "results_window", None)
        if results is None:
            raise ValidationError("there is no optimization result to accept or discard: optimize first")
        new = float(optimizer.new_state)
        (results.acceptButton if args["accept"] else results.discardButton).click()
        return {"accepted": args["accept"], "value": new if args["accept"] else None}

    def record(self, number, outcome):
        """Renew the copy of the windows, then keep the request's outcome (on the GUI thread): a
        caller that sees the outcome sees the display it led to, never the one before it."""
        self.refresh()
        self.keep(number, outcome)

    def capture_webcam(self, number, args):
        """The webcam's picture is drawn by the video system, which neither a window grab nor (on
        Windows) a video probe sees: it is a still capture from the window's own QCamera, to memory.
        The request stays queued until the picture arrives, or fails after WEBCAM_TIMEOUT_MS."""
        from PyQt5 import QtMultimedia
        window = getattr(self.main_window, "webcam_window", None)
        camera = getattr(window, "webcam", None)
        if window is None or not window.isVisible() or camera is None:
            self.record(number, {"status": "failed",
                                 "error": "the webcam window is not open: set_windows {show: ['webcam']} opens it"})
            return
        if self.webcam_capture is None or self.webcam_capture.camera is not camera:
            capture = QtMultimedia.QCameraImageCapture(camera, self)
            capture.setCaptureDestination(QtMultimedia.QCameraImageCapture.CaptureToBuffer)
            capture.imageCaptured.connect(self.webcam_captured)
            capture.error.connect(self.webcam_failed)
            capture.camera = camera
            self.webcam_capture = capture
        capture_id = self.webcam_capture.capture()
        if capture_id < 0:
            self.record(number, {"status": "failed", "error": f"the webcam could not capture: {self.webcam_capture.errorString()}"})
            return
        self.webcam_pending[capture_id] = (number, args)
        QtCore.QTimer.singleShot(WEBCAM_TIMEOUT_MS, lambda: self.webcam_timed_out(capture_id))

    def webcam_captured(self, capture_id, image):
        if capture_id in self.webcam_pending:
            number, args = self.webcam_pending.pop(capture_id)
            try:
                self.record(number, {"status": "applied", "result": self.picture_result(image, args)})
            except ValidationError as error:
                self.record(number, {"status": "failed", "error": str(error)})

    def webcam_failed(self, capture_id, _error, text):
        if capture_id in self.webcam_pending:
            number, _args = self.webcam_pending.pop(capture_id)
            self.record(number, {"status": "failed", "error": f"the webcam could not capture: {text}"})

    def webcam_timed_out(self, capture_id):
        if capture_id in self.webcam_pending:
            number, _args = self.webcam_pending.pop(capture_id)
            self.record(number, {"status": "failed", "error": f"the webcam sent no picture within {WEBCAM_TIMEOUT_MS / 1000:g} s"})

    def apply(self, name, args):
        """Carry out one accepted request; the outcome says applied (with a result, if any) or why not."""
        from .commands import check_display
        handlers = {"set_display": self.set_display, "set_windows": self.set_windows, "get_picture": self.get_picture,
                    "open_image_file": self.open_image_file, "set_table_view": self.set_table_view,
                    "refresh_processor_chain": self.refresh_processor_chain}
        try:
            if name not in handlers:
                raise ValidationError(f"no window handle for {name!r}")
            if name == "set_display":                                   # the frame may have changed size since
                args = check_display(self.camera.frame_size(), args)
            result = handlers[name](args or {})
        except ValidationError as error:
            return {"status": "failed", "error": str(error)}
        except Exception as error:                                     # the window raised: say so, keep going
            logger.exception("Remote Control: %s failed in the window", name)
            return {"status": "failed", "error": f"{type(error).__name__}: {error}"}
        return {"status": "applied", **({"result": result} if result is not None else {})}

    def set_display(self, args):
        window = args.get("window", "camera")
        settings = {k: v for k, v in args.items() if k != "window"}
        {"camera": self.camera, "contrast": self.contrast, "tile_overview": self.tile_overview,
         "main": self.main}[window].apply(settings)

    def set_windows(self, args):
        """Show, hide and arrange windows as the View menu and the windows' own close buttons do."""
        window = self.main_window
        openers = {
            "main": window.show,
            "camera": window.camera_window.show,                       # View > Open Camera Window
            "acquisition_manager": window.acquisition_manager_window.show,
            "tile_overview": window.tile_view_window.show,
            "webcam": window.open_webcam_window,
            "contrast": window.launch_contrast_window,                 # Alignment > Open image contrast window
            "processor_chain": window.launch_processor_chain_window,   # Plugins > Processor Chain
        }
        for name in args.get("show", ()):
            if name == "optimizer":
                raise ValidationError("the optimizer opens with optimize, which sets what it searches")
            openers[name]()
            self.of(name).raise_()
        for name in args.get("hide", ()):
            if name == "main":
                raise ValidationError("the main window stays: hiding it would hide mesoSPIM")
            shown = self.of(name)
            if shown is not None:
                shown.close()                                          # as its close button: the contrast window goes inactive
        if args.get("cascade"):
            window.cascade_all_windows()

    def of(self, name):
        window = self.main_window
        attribute = {"camera": "camera_window", "acquisition_manager": "acquisition_manager_window",
                     "tile_overview": "tile_view_window", "webcam": "webcam_window", "contrast": "contrast_window",
                     "processor_chain": "processor_chain_window", "optimizer": "optimizer"}
        return window if name == "main" else getattr(window, attribute[name], None)   # None: not built yet

    def windows(self):
        return {name: bool(self.of(name) is not None and self.of(name).isVisible()) for name in WINDOWS}

    def get_picture(self, args):
        """A picture of a window as it is on screen, returned as PNG or saved to a file (the image
        view's own Export saves what it shows the same way). The webcam's picture is drawn by the
        video system: see capture_webcam."""
        name = args["window"]
        shown = self.of(name)
        if shown is None or not shown.isVisible():
            raise ValidationError(f"the {name} window is not open: set_windows {{show: [{name!r}]}} opens it")
        if name == "main":
            area = shown.findChild(QtWidgets.QScrollArea)
            picture = area.widget().grab().toImage() if area is not None else shown.grab().toImage()
        else:
            picture = shown.grab().toImage()
        return self.picture_result(picture, args)

    def picture_result(self, picture, args):
        """A picture as get_picture returns it: at most max_size on its longer side, PNG in the
        outcome, or saved to path."""
        largest = args.get("max_size", PICTURE_MAX)
        if max(picture.width(), picture.height()) > largest:
            picture = picture.scaled(largest, largest, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        if "path" in args:
            if not picture.save(args["path"]):
                raise ValidationError(f"could not save the picture to {args['path']!r}")
            return {"path": args["path"], "width": picture.width(), "height": picture.height()}
        data = QtCore.QByteArray()
        buffer = QtCore.QBuffer(data)
        buffer.open(QtCore.QIODevice.WriteOnly)
        picture.save(buffer, "PNG")
        return {"format": "png", "width": picture.width(), "height": picture.height(),
                "base64": base64.b64encode(bytes(data)).decode("ascii")}

    def open_image_file(self, args):
        """File > Open TIFF without its file dialog: the stack goes into the camera window as the menu
        puts it there (MainWindow.open_tiff)."""
        import tifffile
        path = args["path"]
        if not os.path.isfile(path):
            raise ValidationError(f"{path!r} is not a file")
        stack = tifffile.imread(path)
        self.main_window.camera_window.set_image(stack)
        logger.info(f"Remote Control: loaded TIFF file from {path}, dimensions {stack.shape}")
        return {"path": path, "shape": list(stack.shape)}

    def refresh_processor_chain(self, _args):
        """An open Processor Chain window shows the chain a call set, with its own refresh."""
        window = getattr(self.main_window, "processor_chain_window", None)
        if window is not None:
            window.refresh_from_chain()

    def set_table_view(self, args):
        self.acquisition_manager.apply(args)

    def read(self):
        """What each window shows; a window the main window does not have (yet) is left out."""
        window = self.main_window
        shown = {}
        if getattr(window, "camera_window", None) is not None:
            shown["camera_window"] = self.camera.read()
        if getattr(window, "TabWidget", None) is not None:
            shown["main_window"] = self.main.read()
        if getattr(window, "acquisition_manager_window", None) is not None:
            shown["acquisition_manager"] = self.acquisition_manager.read()
        if getattr(window, "tile_view_window", None) is not None:
            shown["tile_overview"] = self.tile_overview.read()
        if hasattr(window, "contrast_window"):
            shown["contrast_window"] = self.contrast.read()
        if all(hasattr(window, a) for a in ("camera_window", "acquisition_manager_window", "tile_view_window")):
            shown["windows"] = self.windows()
        return shown

    @QtCore.pyqtSlot()
    def refresh(self):
        """Renew the copy get_display reads. Reading a window must never stop mesoSPIM (this runs while
        it starts, and on a timer): a failure is logged and is what get_display then reports."""
        try:
            shown = self.read()
        except Exception as error:
            logger.exception("Remote Control: reading the windows for get_display failed")
            shown = {"error": f"reading the windows failed: {type(error).__name__}: {error}"}
        with self.lock:
            self.shown = shown


def fraction(bar):
    span = bar.maximum() - bar.minimum()
    return (bar.value() - bar.minimum()) / span if span else 0.0

