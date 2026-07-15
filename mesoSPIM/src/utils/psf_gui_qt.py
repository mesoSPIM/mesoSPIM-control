#!/usr/bin/env python3
"""
Single-file PyQt5 GUI application for bead PSF analysis.

- Open 3D TIF z-stack
- Set threshold and z-range
- Run bead detection & PSF fitting
- Show two figures in one window:
    Top row: histograms of axial and lateral FWHM
    Bottom row: smoothed max-projection with bead scatter colored by FWHM
- Save per-bead PSF plots as PDF
- Save bead statistics as TXT and CSV
"""
# Default system parameters
MAG = 5.0 # effective magnification of the system
PIXEL_PITCH_MICRON = 4.25
PX_LATERAL_MICRON = PIXEL_PITCH_MICRON/MAG
PX_AXIAL_MICRON = 1.0
THRESHOLD = 700
MIN_BEAD_DISTANCE_UM = 15.0   # minimum distance between beads in microns
Z_FIT_WINDOW_UM = 30.0        # axial (Z) extent of the per-bead fitting window, in microns
HIST_XMAX_AX_UM = 6.0         # upper x-axis limit for the axial FWHM histogram, in microns
HIST_XMAX_LAT_UM = 6.0        # upper x-axis limit for the lateral FWHM histogram, in microns
COLORBAR_MAX_AX_UM = 5.0      # upper color-scale limit for the axial FWHM map, in microns
COLORBAR_MAX_LAT_UM = 5.0     # upper color-scale limit for the lateral FWHM map, in microns


import os
import sys
import numpy as np
import pandas as pd

from PyQt5 import QtCore, QtWidgets

from skimage.filters import gaussian
from skimage.feature import peak_local_max
from scipy.optimize import curve_fit
from sklearn.metrics import pairwise_distances

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages

from tifffile import imread, imwrite


# =============================
#  ANALYSIS FUNCTIONS
# =============================

def inside(shape, center, window):
    """A bead's fitting window must fit inside the volume with room to spare.
    Strict inequalities: a window that exactly touches the edge leaves zero
    margin, so there's no guarantee the profile has decayed back to baseline
    within it (e.g. a bead sitting right at the top/bottom of the acquired
    Z-stack)."""
    return np.all([
        (center[i] - window[i] // 2 > 0) &
        (center[i] + window[i] // 2 < shape[i])
        for i in range(3)
    ])


def volume(im, center, window):
    if not inside(im.shape, center, window):
        return None

    z0 = center[0] - window[0] // 2
    z1 = center[0] + window[0] // 2
    y0 = center[1] - window[1] // 2
    y1 = center[1] + window[1] // 2
    x0 = center[2] - window[2] // 2
    x1 = center[2] + window[2] // 2

    vol = im[z0:z1, y0:y1, x0:x1].astype("float64")

    baseline = vol[[0, 1], [0, 1], [0, 1]].mean()
    vol = vol - baseline
    if vol.max() > 0:
        vol = vol / vol.max()

    return vol


def findBeads(im, window, thresh, min_dist=1):
    """
    Uses a 2D gaussian filter to smooth the data with a sigma of 1
    Returns centers and the max projection of the smoothed image.
    """
    smoothed = gaussian(
        im,
        1,
        mode="nearest",
        truncate=1.0,
        preserve_range=True,
    )
    centers = peak_local_max(
        smoothed,
        min_distance=min_dist,
        threshold_abs=thresh,
        exclude_border=True,
    )
    print(f"findBeads() done: {len(centers)} found")
    return centers, smoothed.max(axis=0)   # <-- 2D image here


def getCenters(im, options):
    window = [
        options["windowUm"][0] * options["pxPerUmAx"],
        options["windowUm"][1] * options["pxPerUmLat"],
        options["windowUm"][2] * options["pxPerUmLat"],
    ]
    window = [round(x) for x in window]

    centers, smoothed = findBeads(im, window, options["thresh"])
    centers = keepBeads(im, window, centers, options)

    beads = [volume(im, x, window) for x in centers]
    maxima = [im[x[0], x[1], x[2]] for x in centers]

    print(f"getCenters() done: {len(centers)} found")
    return beads, maxima, centers, smoothed   # smoothed is 2D


def keepBeads(im, window, centers, options):
    if centers is None or len(centers) == 0:
        return np.zeros((0, 3), dtype=int)

    if len(centers) >= 2:
        centersM = np.asarray([
            [
                c[0] / options["pxPerUmAx"],
                c[1] / options["pxPerUmLat"],
                c[2] / options["pxPerUmLat"],
            ]
            for c in centers
        ])
        min_distance = float(min(options["windowUm"]))
        distance_matrix = pairwise_distances(centersM)

        # Greedy non-max suppression: candidates within min_distance of each other are
        # almost certainly sub-peaks of the same bead (e.g. multiple noisy local maxima
        # along a single bead that is elongated/out-of-focus), so keep only the
        # brightest one per cluster instead of discarding every candidate involved.
        intensities = np.asarray([im[c[0], c[1], c[2]] for c in centers])
        order = np.argsort(intensities)[::-1]
        suppressed = np.zeros(len(centers), dtype=bool)
        keep = []
        for i in order:
            if suppressed[i]:
                continue
            keep.append(i)
            suppressed |= distance_matrix[i] <= min_distance
        centers = centers[keep, :]

    keep_inside = np.where([inside(im.shape, x, window) for x in centers])[0]
    centers_keep = centers[keep_inside, :]

    n_excluded_edge = len(centers) - len(centers_keep)
    if n_excluded_edge > 0:
        print(f'keepBeads(): {n_excluded_edge} candidate(s) excluded - too close to a '
              f'stack edge for the current fitting window')

    saturation_value = options.get("saturationValue")
    if saturation_value is not None and len(centers_keep) > 0:
        def window_is_saturated(c):
            z0, z1 = c[0] - window[0] // 2, c[0] + window[0] // 2
            y0, y1 = c[1] - window[1] // 2, c[1] + window[1] // 2
            x0, x1 = c[2] - window[2] // 2, c[2] + window[2] // 2
            return bool(np.any(im[z0:z1, y0:y1, x0:x1] >= saturation_value))

        not_saturated = np.array([not window_is_saturated(c) for c in centers_keep])
        n_excluded_sat = int(np.sum(~not_saturated))
        if n_excluded_sat > 0:
            print(f'keepBeads(): {n_excluded_sat} candidate(s) excluded - saturated '
                  f'pixel(s) in the fitting window')
        centers_keep = centers_keep[not_saturated]

    print(f'keepBeads() done: {len(centers_keep)} found')

    return centers_keep


def safe_median(series):
    """Median of a pandas Series, guarding against all-NaN input."""
    vals = series.to_numpy()
    if np.all(np.isnan(vals)):
        return np.nan
    return np.nanmedian(vals)


def safe_std(series):
    """Standard deviation of a pandas Series, guarding against all-NaN input."""
    vals = series.to_numpy()
    if np.all(np.isnan(vals)):
        return np.nan
    return np.nanstd(vals, ddof=0)


def gauss(x, a, mu, sigma, b):
    return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2)) + b


def fit(yRaw, scale):
    y = yRaw - (yRaw[0] + yRaw[-1]) / 2
    x = (np.arange(y.shape[0]) - y.shape[0] / 2.0)

    try:
        popt, pcov = curve_fit(gauss, x, y, p0=[1, 0, 1, 0])
        FWHM = 2.3548 * popt[2] / scale
        yFit = gauss(x, *popt)
    except Exception:
        yFit, FWHM = None, None

    return x, y, yFit, FWHM


def getSlices(average, method="local_peak"):
    if method == "max":
        latProfile = (average.mean(axis=0).mean(axis=1) +
                      average.mean(axis=0).mean(axis=1)) / 2
        axProfile = (average.mean(axis=1).mean(axis=1) +
                     average.mean(axis=2).mean(axis=1)) / 2
    else:
        center = peak_local_max(
            average, min_distance=2, threshold_abs=0.99,
            exclude_border=True, num_peaks=1
        )
        if len(center) > 0:
            center = center[0]
            latProfile = (average[center[0], :, center[2]] +
                          average[center[0], center[1], :]) / 2
            axProfile = average[:, center[1], center[2]]
        else:
            latProfile, axProfile = None, None

    return latProfile, axProfile


def getPSF(bead, options):
    latProfile, axProfile = getSlices(bead)

    if latProfile is not None:
        latFit = fit(latProfile, options["pxPerUmLat"])
    else:
        latFit = (None, None, None, None)

    if axProfile is not None:
        axFit = fit(axProfile, options["pxPerUmAx"])
    else:
        axFit = (None, None, None, None)

    data = pd.DataFrame(
        [latFit[3], axFit[3]],
        index=["FWHMlat", "FWHMax"]
    ).T

    return data, latFit, axFit


def compute(im, options):
    beads, maxima, centers, smoothed = getCenters(im, options)
    psf_list = [getPSF(b, options) for b in beads]
    return psf_list, beads, maxima, centers, smoothed


def plot_psf_subplot(ax, fit_tuple, scale, Max, title):
    x, y, yFit, FWHM = fit_tuple

    if yFit is None or FWHM is None:
        ax.text(0.5, 0.5, "Fit failed",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title(title)
        return None

    x_um = x.astype(float) / scale
    y_norm = y / yFit.max()
    yFit_norm = yFit / yFit.max()

    ax.plot(x_um, yFit_norm, lw=2, label="Fit")
    ax.plot(x_um, y_norm, "ok", ms=3, label="Data")
    ax.set_xlim([-x.shape[0] / 2 / scale, x.shape[0] / 2 / scale])
    ax.set_ylim([0, 1.1])
    ax.set_xlabel("Distance (µm)")
    ax.set_ylabel("Norm. intensity")
    ax.set_title(title)
    ax.text(0.05, 0.95, f"FWHM = {FWHM:.2f} µm",
            transform=ax.transAxes, va="top")
    ax.text(0.05, 0.85, f"Brightness = {Max:.2f}",
            transform=ax.transAxes, va="top")
    ax.legend(fontsize=8)

    return FWHM


# =============================
#  MATPLOTLIB CANVAS
# =============================

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, dpi=100):
        self.fig = plt.Figure(dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.fig.get_axes():
            return
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        dpi = self.fig.get_dpi()
        self.fig.set_size_inches(w / dpi, h / dpi, forward=False)
        try:
            self.fig.tight_layout(pad=1.0, w_pad=0.7, h_pad=0.7)
        except Exception:
            pass
        self.draw_idle()


# =============================
#  MAIN WINDOW (PyQt5)
# =============================

class PSFMainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, stack=None, mag=None, pixel_pitch_micron=None,
                 z_step_micron=None, filename=None):
        """
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget, so the window can be launched embedded in another Qt app
            (e.g. mesoSPIM_control) instead of only as a standalone application.
        stack : np.ndarray, optional
            3D (Z, Y, X) image stack to preload, e.g. straight from an acquisition,
            without going through "Open TIF...".
        mag : float, optional
            Effective system magnification. Defaults to MAG.
        pixel_pitch_micron : float, optional
            Camera pixel pitch in microns. Defaults to PIXEL_PITCH_MICRON.
        z_step_micron : float, optional
            Z stepsize in microns. Defaults to PX_AXIAL_MICRON.
        filename : str, optional
            Name to associate with a preloaded *stack* (used for the experiment key
            and info label). Not a path that gets read from disk.
        """
        super().__init__(parent)

        self.setWindowTitle("Bead PSF Analysis (www.mesoSPIM.org). GPL-3 License.")
        self.resize(720, 1280)

        # Data holders
        self.im = None
        self.filename = None
        self.psf_list = None
        self.beads = None
        self.maxima = None
        self.centers = None
        self.smoothed = None  # 3D smoothed image (for max-projection)
        self.stats_df = None  # PSF DataFrame (FWHMlat, FWHMax, X, Y, Z, Max)

        # System parameters (editable via GUI)
        self.mag = mag if mag is not None else MAG
        self.pixel_pitch_micron = pixel_pitch_micron if pixel_pitch_micron is not None else PIXEL_PITCH_MICRON
        self.px_axial_micron = z_step_micron if z_step_micron is not None else PX_AXIAL_MICRON
        self.px_lateral_micron = self.pixel_pitch_micron / self.mag
        self.min_bead_distance_um = MIN_BEAD_DISTANCE_UM
        self.z_fit_window_um = Z_FIT_WINDOW_UM

        # Plot display ranges (editable via GUI, redraw only - no re-analysis needed)
        self.hist_xmax_ax_um = HIST_XMAX_AX_UM
        self.hist_xmax_lat_um = HIST_XMAX_LAT_UM
        self.colorbar_max_ax_um = COLORBAR_MAX_AX_UM
        self.colorbar_max_lat_um = COLORBAR_MAX_LAT_UM

        # Default options
        self.options = {
            "pxPerUmAx": 1.0/self.px_axial_micron,
            "pxPerUmLat": 1.0/self.px_lateral_micron,
            "windowUm": [self.z_fit_window_um, self.min_bead_distance_um, self.min_bead_distance_um],
            "thresh": THRESHOLD,
            "saturationValue": None,  # set in load_stack() from the file's integer dtype, if any
        }
        self.saturation_value = None

        self._init_ui()
        self.setAcceptDrops(True)

        if stack is not None:
            self.load_stack(stack, filename=filename)

    # ---------- UI setup ----------

    def _init_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        # System parameters
        params_group = QtWidgets.QGroupBox("System Parameters")
        params_layout = QtWidgets.QHBoxLayout()
        params_group.setLayout(params_layout)
        vbox.addWidget(params_group)

        params_layout.addWidget(QtWidgets.QLabel("Magnification:"))
        self.mag_edit = QtWidgets.QDoubleSpinBox()
        self.mag_edit.setRange(0.1, 100.0)
        self.mag_edit.setValue(self.mag)
        self.mag_edit.setDecimals(2)
        self.mag_edit.setSingleStep(1.0)
        self.mag_edit.valueChanged.connect(self.update_system_parameters)
        params_layout.addWidget(self.mag_edit)

        params_layout.addSpacing(10)
        params_layout.addWidget(QtWidgets.QLabel("Camera pixel pitch (µm):"))
        self.pixel_pitch_edit = QtWidgets.QDoubleSpinBox()
        self.pixel_pitch_edit.setRange(0.1, 10.0)
        self.pixel_pitch_edit.setValue(self.pixel_pitch_micron)
        self.pixel_pitch_edit.setDecimals(2)
        self.pixel_pitch_edit.setSingleStep(0.1)
        self.pixel_pitch_edit.valueChanged.connect(self.update_system_parameters)
        params_layout.addWidget(self.pixel_pitch_edit)

        params_layout.addSpacing(10)
        params_layout.addWidget(QtWidgets.QLabel("Z-step (µm):"))
        self.px_axial_edit = QtWidgets.QDoubleSpinBox()
        self.px_axial_edit.setRange(0.01, 10.0)
        self.px_axial_edit.setValue(self.px_axial_micron)
        self.px_axial_edit.setDecimals(2)
        self.px_axial_edit.setSingleStep(0.1)
        self.px_axial_edit.valueChanged.connect(self.update_system_parameters)
        params_layout.addWidget(self.px_axial_edit)

        params_layout.addStretch(1)

        # Analysis controls
        controls = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls)

        controls.addWidget(QtWidgets.QLabel("Min intensity:"))
        self.thresh_edit = QtWidgets.QDoubleSpinBox()
        self.thresh_edit.setRange(0, 20000)
        self.thresh_edit.setValue(self.options["thresh"])
        self.thresh_edit.setDecimals(1)
        controls.addWidget(self.thresh_edit)

        controls.addSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Min dist betw beads (µm):"))
        self.min_bead_dist_edit = QtWidgets.QDoubleSpinBox()
        self.min_bead_dist_edit.setRange(1.0, 100.0)
        self.min_bead_dist_edit.setValue(self.min_bead_distance_um)
        self.min_bead_dist_edit.setDecimals(1)
        self.min_bead_dist_edit.setSingleStep(1.0)
        self.min_bead_dist_edit.valueChanged.connect(self.update_min_bead_distance)
        controls.addWidget(self.min_bead_dist_edit)

        controls.addSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Z fit window (µm):"))
        self.z_fit_window_edit = QtWidgets.QDoubleSpinBox()
        self.z_fit_window_edit.setRange(1.0, 200.0)
        self.z_fit_window_edit.setValue(self.z_fit_window_um)
        self.z_fit_window_edit.setDecimals(1)
        self.z_fit_window_edit.setSingleStep(1.0)
        self.z_fit_window_edit.setToolTip(
            "Axial extent of the per-bead fitting window. Independent of 'Min dist "
            "betw beads', so it can be widened for beads with a broad/wiggly axial "
            "profile (e.g. stage jitter) without also enlarging the lateral crop."
        )
        self.z_fit_window_edit.valueChanged.connect(self.update_z_fit_window)
        controls.addWidget(self.z_fit_window_edit)

        controls.addSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Z min:"))
        self.zmin_edit = QtWidgets.QSpinBox()
        self.zmin_edit.setRange(0, 100000)
        self.zmin_edit.setValue(0)
        controls.addWidget(self.zmin_edit)

        controls.addSpacing(10)
        controls.addWidget(QtWidgets.QLabel("Z max:"))
        self.zmax_edit = QtWidgets.QSpinBox()
        self.zmax_edit.setRange(0, 100000)
        self.zmax_edit.setValue(0)
        controls.addWidget(self.zmax_edit)

        controls.addStretch(1)

        # Second row of controls
        controls2 = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls2)

        self.run_button = QtWidgets.QPushButton("Run analysis")
        self.run_button.clicked.connect(self.run_analysis)
        controls2.addWidget(self.run_button)

        controls2.addSpacing(20)
        self.info_label = QtWidgets.QLabel("No image loaded")
        controls2.addWidget(self.info_label)

        controls2.addStretch(1)

        # Third row of controls: plot display ranges (redraw only, no re-analysis)
        controls3 = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls3)

        def make_range_spinbox(label_text, initial_value, tooltip):
            controls3.addWidget(QtWidgets.QLabel(label_text))
            edit = QtWidgets.QDoubleSpinBox()
            edit.setRange(1.0, 200.0)
            edit.setValue(initial_value)
            edit.setDecimals(1)
            edit.setSingleStep(1.0)
            edit.setToolTip(tooltip)
            edit.valueChanged.connect(self.update_plot_ranges)
            controls3.addWidget(edit)
            controls3.addSpacing(10)
            return edit

        self.hist_xmax_ax_edit = make_range_spinbox(
            "Hist X max, axial (µm):", self.hist_xmax_ax_um,
            "Upper x-axis limit for the axial FWHM histogram. Redraws the "
            "existing plots; does not require re-running the analysis."
        )
        self.hist_xmax_lat_edit = make_range_spinbox(
            "Hist X max, lateral (µm):", self.hist_xmax_lat_um,
            "Upper x-axis limit for the lateral FWHM histogram. Redraws the "
            "existing plots; does not require re-running the analysis."
        )
        self.colorbar_max_ax_edit = make_range_spinbox(
            "Colorbar max, axial (µm):", self.colorbar_max_ax_um,
            "Upper color-scale limit for the axial FWHM map. Redraws the "
            "existing plots; does not require re-running the analysis."
        )
        self.colorbar_max_lat_edit = make_range_spinbox(
            "Colorbar max, lateral (µm):", self.colorbar_max_lat_um,
            "Upper color-scale limit for the lateral FWHM map. Redraws the "
            "existing plots; does not require re-running the analysis."
        )

        controls3.addStretch(1)

        # Matplotlib canvas
        self.canvas = MplCanvas(self, dpi=100)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                    QtWidgets.QSizePolicy.Expanding)
        self.canvas.setSizePolicy(size_policy)
        vbox.addWidget(self.canvas)

        # Menus
        self._init_menus()

    def _init_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QtWidgets.QAction("Open TIF...", self)
        open_action.triggered.connect(self.open_tif)
        file_menu.addAction(open_action)

        simulate_action = QtWidgets.QAction("Simulate...", self)
        simulate_action.setToolTip(
            "Generate a synthetic 3-bead stack of known FWHM using the current "
            "system parameters, and run the analysis - a quick demo/sanity check."
        )
        simulate_action.triggered.connect(self.simulate_demo)
        file_menu.addAction(simulate_action)

        file_menu.addSeparator()

        save_txt_action = QtWidgets.QAction("Save stats as TXT...", self)
        save_txt_action.triggered.connect(self.save_txt)
        file_menu.addAction(save_txt_action)

        save_csv_action = QtWidgets.QAction("Save stats as CSV...", self)
        save_csv_action.triggered.connect(self.save_csv)
        file_menu.addAction(save_csv_action)

        save_png_action = QtWidgets.QAction("Save figure as PNG (300 DPI)...", self)
        save_png_action.triggered.connect(self.save_png_figure)
        file_menu.addAction(save_png_action)

        save_psf_action = QtWidgets.QAction("Save average PSF as TIF...", self)
        save_psf_action.triggered.connect(self.save_average_psf)
        file_menu.addAction(save_psf_action)

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # ---------- Parameter updates ----------

    def update_system_parameters(self):
        """Update system parameters and recalculate derived values."""
        self.mag = float(self.mag_edit.value())
        self.pixel_pitch_micron = float(self.pixel_pitch_edit.value())
        self.px_axial_micron = float(self.px_axial_edit.value())
        
        # Recalculate lateral pixel size
        self.px_lateral_micron = self.pixel_pitch_micron / self.mag
        
        # Update options
        self.options["pxPerUmAx"] = 1.0 / self.px_axial_micron
        self.options["pxPerUmLat"] = 1.0 / self.px_lateral_micron
        
        # Recalculate FOV if image is loaded
        if self.im is not None:
            self.FOV_Y_um = self.im.shape[1] * self.px_lateral_micron
            self.FOV_X_um = self.im.shape[2] * self.px_lateral_micron
            # Update plots if they exist
            if self.stats_df is not None and not self.stats_df.empty:
                self.update_plots()

    def update_min_bead_distance(self):
        """Update minimum bead distance parameter (also the lateral fitting window)."""
        self.min_bead_distance_um = float(self.min_bead_dist_edit.value())
        self.options["windowUm"][1] = self.min_bead_distance_um
        self.options["windowUm"][2] = self.min_bead_distance_um

    def update_z_fit_window(self):
        """Update the axial (Z) fitting window, independent of the lateral window."""
        self.z_fit_window_um = float(self.z_fit_window_edit.value())
        self.options["windowUm"][0] = self.z_fit_window_um

    def update_plot_ranges(self):
        """Update the histogram/colorbar display ranges and redraw the existing
        results, without re-running the bead detection/fitting analysis."""
        self.hist_xmax_ax_um = float(self.hist_xmax_ax_edit.value())
        self.hist_xmax_lat_um = float(self.hist_xmax_lat_edit.value())
        self.colorbar_max_ax_um = float(self.colorbar_max_ax_edit.value())
        self.colorbar_max_lat_um = float(self.colorbar_max_lat_edit.value())
        if self.stats_df is not None and not self.stats_df.empty:
            self.update_plots()

    # ---------- File operations ----------

    def open_tif(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open TIF z-stack", "",
            "TIF files (*.tif *.tiff);;All files (*)"
        )
        if not fname:
            return

        try:
            im = imread(fname)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
            return

        self.load_stack(im, filename=fname)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(url.toLocalFile().lower().endswith((".tif", ".tiff")) for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".tif", ".tiff")):
                try:
                    im = imread(path)
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
                    return
                self.load_stack(im, filename=path)
                return

    def simulate_demo(self):
        """Generate a synthetic 3-bead TIFF stack of known FWHM, using the current
        system parameters (magnification, pixel pitch, Z-step), load it, and run
        the analysis - a quick, no-file-needed demo/sanity check of the tool."""
        FWHM_LAT_UM = 1.0
        FWHM_AX_UM = 2.0
        amplitude, baseline = 5000.0, 300.0

        sigma_lat_px = (FWHM_LAT_UM / 2.3548) / self.px_lateral_micron
        sigma_ax_px = (FWHM_AX_UM / 2.3548) / self.px_axial_micron

        # Size the volume with generous margin around the current Z fit window and
        # min bead-separation settings, so all 3 beads are reliably detected
        # regardless of whatever the user currently has configured.
        z_half_px = int(np.ceil(1.5 * self.z_fit_window_um / 2.0 / self.px_axial_micron)) + 5
        lat_half_px = int(np.ceil(1.5 * self.min_bead_distance_um / self.px_lateral_micron)) + 10

        shape = (2 * z_half_px + 1, 4 * lat_half_px, 4 * lat_half_px)
        z0 = z_half_px
        centers = [
            (z0, lat_half_px, lat_half_px),
            (z0, lat_half_px, 3 * lat_half_px),
            (z0, 3 * lat_half_px, 2 * lat_half_px),
        ]

        zz, yy, xx = np.meshgrid(
            np.arange(shape[0]), np.arange(shape[1]), np.arange(shape[2]), indexing="ij"
        )
        im = np.full(shape, baseline, dtype=np.float64)
        for z_c, y_c, x_c in centers:
            r2 = (
                (zz - z_c) ** 2 / (2 * sigma_ax_px ** 2)
                + (yy - y_c) ** 2 / (2 * sigma_lat_px ** 2)
                + (xx - x_c) ** 2 / (2 * sigma_lat_px ** 2)
            )
            im = im + amplitude * np.exp(-r2)
        im = im.astype(np.uint16)

        self.load_stack(im, filename="simulated_3beads.tif")
        self.thresh_edit.setValue(baseline + amplitude * 0.2)
        self.run_analysis()
        self.info_label.setText(
            f"Simulated 3 beads (ground truth FWHM: lateral={FWHM_LAT_UM:.2f} µm, "
            f"axial={FWHM_AX_UM:.2f} µm). {self.info_label.text()}"
        )

    def load_stack(self, im, filename=None):
        """
        Load a 3D (Z, Y, X) image stack into the analysis window, whether it came
        from "Open TIF..." or was handed in directly (e.g. from mesoSPIM_control
        right after an acquisition).
        """
        im = np.asarray(im)

        if im.ndim != 3:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Expected 3D stack, got shape {im.shape}"
            )
            return

        self.FOV_Y_um = im.shape[1] * self.px_lateral_micron
        self.FOV_X_um = im.shape[2] * self.px_lateral_micron

        self.saturation_value = None
        if np.issubdtype(im.dtype, np.integer):
            sat_value = np.iinfo(im.dtype).max
            n_sat = int(np.sum(im == sat_value))
            if n_sat > 0:
                self.saturation_value = sat_value
                pct = 100.0 * n_sat / im.size
                QtWidgets.QMessageBox.warning(
                    self, "Saturation warning",
                    f"{n_sat:,} pixels ({pct:.2f}%) are saturated "
                    f"(value = {sat_value}, dtype = {im.dtype}).\n"
                    "Beads with any saturated pixel in their fitting window will be "
                    "excluded from the analysis automatically."
                )
        self.options["saturationValue"] = self.saturation_value

        self.im = im.astype(np.float32)
        self.filename = filename

        zmax = self.im.shape[0] - 1
        self.zmin_edit.setRange(0, zmax)
        self.zmax_edit.setRange(0, zmax)
        self.zmin_edit.setValue(0)
        self.zmax_edit.setValue(zmax)

        label = os.path.basename(self.filename) if self.filename else "in-memory stack"
        self.info_label.setText(f"Loaded: {label}, shape={self.im.shape}")

        # use TIF file name (without path) as experiment key
        if self.filename:
            self.experiment_key = os.path.splitext(os.path.basename(self.filename))[0]
        else:
            self.experiment_key = "experiment"

        self.clear_plots()
        self.psf_list = self.beads = self.maxima = self.centers = self.smoothed = None
        self.stats_df = None

    def save_txt(self):
        """
        Save only summary statistics to TXT, matching the notebook style:

            experiment_key

            #Beads: N

            Median lateral FWHM (+/- std): m_lat +/- s_lat um
            MIN, MAX lateral FWHM: min_lat, max_lat um

            Median axial FWHM  (+/- std): m_ax +/- s_ax um
            MIN, MAX axial FWHM: min_ax, max_ax um
        """
        if self.stats_df is None or self.stats_df.empty:
            QtWidgets.QMessageBox.warning(self, "Warning", "No bead statistics to save.")
            return

        # Convenience alias, like PSF in the notebook
        PSF = self.stats_df

        n_beads = len(PSF)

        med_lat = safe_median(PSF["FWHMlat"])
        std_lat = safe_std(PSF["FWHMlat"])
        min_lat = float(PSF["FWHMlat"].min()) if n_beads > 0 else np.nan
        max_lat = float(PSF["FWHMlat"].max()) if n_beads > 0 else np.nan

        med_ax = safe_median(PSF["FWHMax"])
        std_ax = safe_std(PSF["FWHMax"])
        min_ax = float(PSF["FWHMax"].min()) if n_beads > 0 else np.nan
        max_ax = float(PSF["FWHMax"].max()) if n_beads > 0 else np.nan

        # Build the string 
        s = (
            f"{self.experiment_key}\n"
            f"\n#Beads: {n_beads}"
            f"\n\nMedian lateral FWHM (+/- std): "
            f"{round(med_lat, 2) if not np.isnan(med_lat) else 'nan'}  "
            f"+/- {round(std_lat, 2) if not np.isnan(std_lat) else 'nan'} um"
            f"\n\nMIN, MAX lateral FWHM: "
            f"{round(min_lat, 2) if not np.isnan(min_lat) else 'nan'}, "
            f"{round(max_lat, 2) if not np.isnan(max_lat) else 'nan'} um"
            f"\n\nMedian axial FWHM  (+/- std): "
            f"{round(med_ax, 2) if not np.isnan(med_ax) else 'nan'} "
            f"+/- {round(std_ax, 2) if not np.isnan(std_ax) else 'nan'} um"
            f"\n\nMIN, MAX axial FWHM: "
            f"{round(min_ax, 2) if not np.isnan(min_ax) else 'nan'}, "
            f"{round(max_ax, 2) if not np.isnan(max_ax) else 'nan'} um\n"
        )

        # Ask where to save
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save summary stats as TXT", f"bead-summary-stats({self.experiment_key}).txt",
            "Text files (*.txt)"
        )
        if not fname:
            return
        if not fname.lower().endswith(".txt"):
            fname += ".txt"

        try:
            with open(fname, "w") as f:
                print(s)   # optional: also print to console, like in notebook
                f.write(s)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save TXT:\n{e}")


    def save_csv(self):
        if self.stats_df is None:
            QtWidgets.QMessageBox.warning(self, "Warning", "No bead statistics to save.")
            return

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save stats as CSV", f"beads-full-stats({self.experiment_key}).csv",
            "CSV files (*.csv)"
        )
        if not fname:
            return
        if not fname.lower().endswith(".csv"):
            fname += ".csv"

        try:
            self.stats_df.to_csv(fname, index=True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save CSV:\n{e}")


    def save_png_figure(self):
        """
        Save the current 4-panel figure (histograms + PSF maps)
        as a single PNG at 300 DPI.
        """
        if self.stats_df is None or self.stats_df.empty or self.smoothed is None:
            QtWidgets.QMessageBox.warning(self, "Warning", "No plots to save yet.")
            return

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save current figure as PNG (300 DPI)",
            f"psf-summary({self.experiment_key}).png",
            "PNG images (*.png)"
        )
        if not fname:
            return
        if not fname.lower().endswith(".png"):
            fname += ".png"

        EXPORT_W_IN, EXPORT_H_IN = 9.0, 12.0  # fixed export dimensions (inches @ 300 DPI), 3:4
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            export_fig = plt.Figure(figsize=(EXPORT_W_IN, EXPORT_H_IN), dpi=300)
            FigureCanvasAgg(export_fig)  # attach non-interactive Agg backend for rendering
            if self.filename:
                export_fig.suptitle(os.path.basename(self.filename), fontsize=12, y=0.995)
            self._populate_figure(export_fig, annotate_stats=True)
            export_fig.tight_layout(pad=1.0, w_pad=0.8, h_pad=1.2, rect=[0, 0, 1, 0.99])
            export_fig.savefig(fname, dpi=300, format="png")
            plt.close(export_fig)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save PNG:\n{e}")

    def save_average_psf(self):
        """Average normalised sub-volumes around each detected bead and save as a 3D TIF."""
        if self.im is None or self.centers is None or len(self.centers) == 0:
            QtWidgets.QMessageBox.warning(self, "Warning", "Run analysis first to detect beads.")
            return

        xy_um = 10.0
        z_planes = 20
        xy_px = round(xy_um / self.px_lateral_micron)
        if xy_px % 2 == 0:
            xy_px += 1  # odd → bead centre lands on the middle pixel
        window = [z_planes, xy_px, xy_px]

        # self.centers are in sub_im coordinates (offset by zmin); map back to full image
        zmin = int(self.zmin_edit.value())
        vols, skipped = [], 0
        for c in self.centers:
            c_full = c.copy()
            c_full[0] += zmin
            vol = volume(self.im, c_full, window)
            if vol is not None:
                vols.append(vol)
            else:
                skipped += 1

        if not vols:
            QtWidgets.QMessageBox.warning(
                self, "Warning",
                "No beads have enough margin for PSF extraction with the current window.\n"
                f"Required: {z_planes} z-planes × {xy_px}×{xy_px} px lateral."
            )
            return

        avg_psf = (np.mean(np.stack(vols, axis=0), axis=0) * 65535).clip(0, 65535).astype(np.uint16)

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save average PSF",
            f"avg-psf({self.experiment_key}).tif",
            "TIF files (*.tif *.tiff)"
        )
        if not fname:
            return
        if not fname.lower().endswith(('.tif', '.tiff')):
            fname += '.tif'

        try:
            imwrite(
                fname, avg_psf,
                imagej=True,
                resolution=(1.0 / self.px_lateral_micron, 1.0 / self.px_lateral_micron),
                metadata={'spacing': self.px_axial_micron, 'unit': 'um', 'axes': 'ZYX'},
            )
            msg = f"Average PSF saved from {len(vols)} beads, shape {avg_psf.shape}"
            if skipped:
                msg += f" ({skipped} bead(s) skipped: too close to image edge)"
            self.info_label.setText(msg)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save PSF TIF:\n{e}")

    # ---------- Analysis ----------

    def run_analysis(self):
        if self.im is None:
            QtWidgets.QMessageBox.warning(self, "Warning", "Load a TIF z-stack first.")
            return

        thresh = float(self.thresh_edit.value())
        zmin = int(self.zmin_edit.value())
        zmax = int(self.zmax_edit.value())

        if zmin < 0 or zmax >= self.im.shape[0] or zmin >= zmax:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Invalid Z range. Valid range is [0, {self.im.shape[0]-1}] and zmin < zmax."
            )
            return

        self.options["thresh"] = thresh

        sub_im = self.im[zmin:zmax+1, :, :]
        print(f"Running analysis on z-range [{zmin}, {zmax}] (shape={sub_im.shape})")

        try:
            psf_list, beads, maxima, centers, smoothed = compute(sub_im, self.options)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Analysis failed:\n{e}")
            return

        self.psf_list = psf_list
        self.beads = beads
        self.maxima = maxima
        self.centers = centers
        self.smoothed = smoothed  # 3D smoothed stack

        # Build PSF DataFrame like in your notebook: FWHMax, FWHMlat, X, Y, Z
        rows = []
        for i, (psf, Max, c) in enumerate(zip(self.psf_list, self.maxima, self.centers)):
            data, latFit, axFit = psf
            latFWHM = latFit[3] if latFit is not None else np.nan
            axFWHM = axFit[3] if axFit is not None else np.nan
            rows.append({
                "bead_id": i + 1,
                "Z": c[0] + zmin,
                "Y": c[1],
                "X": c[2],
                "MaxIntensity": Max,
                "FWHMlat": latFWHM,
                "FWHMax": axFWHM,
            })

        columns = ["bead_id", "Z", "Y", "X", "MaxIntensity", "FWHMlat", "FWHMax"]
        self.stats_df = pd.DataFrame(rows, columns=columns).set_index("bead_id")

        if not rows:
            self.info_label.setText(
                "0 beads found. Try lowering 'Min intensity' or 'Min dist betw beads'."
            )
        else:
            self.info_label.setText(f"{len(self.beads)} beads found; stats computed")
        self.update_plots()

    # ---------- Plotting ----------

    def clear_plots(self):
        self.canvas.fig.clear()
        self.canvas.draw()

    def _populate_figure(self, fig, annotate_stats=False):
        """Draw histograms and PSF maps onto *fig*. Uses current self.stats_df / self.smoothed.
        If annotate_stats is True, print median +/- std as a text line above each histogram
        (used for PNG export)."""
        import matplotlib.gridspec as gridspec

        gs = gridspec.GridSpec(
            2, 2,
            height_ratios=[1.0, 2.5],
            width_ratios=[1.0, 1.0],
            figure=fig
        )

        ax_hist_axial = fig.add_subplot(gs[0, 0])
        ax_hist_lat   = fig.add_subplot(gs[0, 1])

        axial_vals = self.stats_df["FWHMax"].tolist()
        lat_vals   = self.stats_df["FWHMlat"].tolist()

        ax_hist_axial.hist(axial_vals, 20, range=(0, self.hist_xmax_ax_um))
        ax_hist_axial.set_xlim([0, self.hist_xmax_ax_um])
        ax_hist_axial.set_xlabel("Axial FWHM (µm)")
        ax_hist_axial.set_ylabel("# Beads")

        ax_hist_lat.hist(lat_vals, 20, range=(0, self.hist_xmax_lat_um))
        ax_hist_lat.set_xlim([0, self.hist_xmax_lat_um])
        ax_hist_lat.set_xlabel("Lateral FWHM (µm)")
        ax_hist_lat.set_ylabel("# Beads")

        if annotate_stats:
            med_ax = safe_median(self.stats_df["FWHMax"])
            std_ax = safe_std(self.stats_df["FWHMax"])
            med_lat = safe_median(self.stats_df["FWHMlat"])
            std_lat = safe_std(self.stats_df["FWHMlat"])
            for ax, med, std in ((ax_hist_axial, med_ax, std_ax), (ax_hist_lat, med_lat, std_lat)):
                ax.text(
                    0.5, 1.02, f"median = {med:.2f} ± {std:.2f} µm",
                    transform=ax.transAxes, ha="center", va="bottom", fontsize=9
                )

        ax_im_axial = fig.add_subplot(gs[1, 0])
        ax_im_lat   = fig.add_subplot(gs[1, 1])

        smoothed_img = self.smoothed
        cmap = "jet"

        ax_im_axial.imshow(smoothed_img, cmap="gray", aspect="equal",
                           extent=(0, self.FOV_X_um, 0, self.FOV_Y_um))
        overlay0 = ax_im_axial.scatter(
            (self.stats_df["X"] * self.px_lateral_micron).tolist(),
            (self.FOV_Y_um - self.stats_df["Y"] * self.px_lateral_micron).tolist(),
            c=self.stats_df["FWHMax"].tolist(),
            cmap=cmap, vmin=0, vmax=self.colorbar_max_ax_um, s=20, edgecolors="none"
        )
        ax_im_axial.set_title("PSF: Axial FWHM")
        ax_im_axial.set_xlabel("FOV_X (µm)")
        ax_im_axial.set_ylabel("FOV_Y (µm)")
        fig.colorbar(overlay0, ax=ax_im_axial, fraction=0.040, pad=0.02)

        ax_im_lat.imshow(smoothed_img, cmap="gray", aspect="equal",
                         extent=(0, self.FOV_X_um, 0, self.FOV_Y_um))
        overlay1 = ax_im_lat.scatter(
            (self.stats_df["X"] * self.px_lateral_micron).tolist(),
            (self.FOV_Y_um - self.stats_df["Y"] * self.px_lateral_micron).tolist(),
            c=self.stats_df["FWHMlat"].tolist(),
            cmap=cmap, vmin=0, vmax=self.colorbar_max_lat_um, s=20, edgecolors="none"
        )
        ax_im_lat.set_title("PSF: Lateral FWHM")
        ax_im_lat.set_xlabel("FOV_X (µm)")
        ax_im_lat.set_ylabel("FOV_Y (µm)")
        fig.colorbar(overlay1, ax=ax_im_lat, fraction=0.040, pad=0.02).set_label("FWHM (µm)")

    def update_plots(self):
        if self.stats_df is None or self.stats_df.empty or self.smoothed is None:
            self.clear_plots()
            return

        fig = self.canvas.fig
        fig.clear()

        # Sync figure size to the current canvas widget size so subplots fill the window.
        dpi = fig.get_dpi()
        w_in = max(self.canvas.width(), 100) / dpi
        h_in = max(self.canvas.height(), 100) / dpi
        fig.set_size_inches(w_in, h_in, forward=False)

        self._populate_figure(fig)
        fig.tight_layout(pad=1.0, w_pad=0.7, h_pad=0.7)
        self.canvas.draw()

# =============================
#  ENTRY POINT
# =============================

def main():
    """Standalone entry point. Also used by mesoSPIM_control, which launches this
    script as a separate process (via subprocess.Popen) rather than embedding it in
    its own process, so a long-running analysis can't block the main GUI."""
    import argparse

    parser = argparse.ArgumentParser(description="Bead PSF Analysis tool")
    parser.add_argument("tiff_path", nargs="?", default=None,
                         help="TIFF z-stack to preload on startup")
    parser.add_argument("--mag", type=float, default=None, help="System magnification")
    parser.add_argument("--pixel-pitch", type=float, default=None, dest="pixel_pitch",
                         help="Camera pixel pitch in microns")
    parser.add_argument("--z-step", type=float, default=None, dest="z_step",
                         help="Z stepsize in microns")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = PSFMainWindow(mag=args.mag, pixel_pitch_micron=args.pixel_pitch, z_step_micron=args.z_step)
    if args.tiff_path:
        try:
            im = imread(args.tiff_path)
            win.load_stack(im, filename=args.tiff_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(win, "Error", f"Failed to open file:\n{e}")
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()