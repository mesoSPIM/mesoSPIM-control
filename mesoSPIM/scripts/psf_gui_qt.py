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
MAG = 5.0 # effective magnification of the system
PIXEL_PITCH_MICRON = 4.25
PX_LATERAL_MICRON = PIXEL_PITCH_MICRON/MAG
PX_AXIAL_MICRON = 1.0
THRESHOLD = 700


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

from tifffile import imread


# =============================
#  ANALYSIS FUNCTIONS
# =============================

def inside(shape, center, window):
    return np.all([
        (center[i] - window[i] // 2 >= 0) &
        (center[i] + window[i] // 2 <= shape[i])
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

    centersM = np.asarray([
        [
            c[0] / options["pxPerUmAx"],
            c[1] / options["pxPerUmLat"],
            c[2] / options["pxPerUmLat"],
        ]
        for c in centers
    ])
    print("centersM done")

    if len(centersM) == 1:
        centers_keep = centers
    elif len(centersM) >= 2:
        distance_matrix = pairwise_distances(centersM)
        distance_matrix.sort(axis=1)
        centerDists = distance_matrix[:, 1]
        print("centerDists done")

        min_distance = float(min(options["windowUm"]))
        keep = np.where(centerDists > min_distance)[0]
        centers = centers[keep, :]

        keep_inside = np.where([inside(im.shape, x, window) for x in centers])[0]
        print(f'keepBeads() done: {len(keep_inside)} found')
        centers_keep = centers[keep_inside, :]
    else:
        centers_keep = np.zeros((0, 3), dtype=int)

    return centers_keep


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
    def __init__(self, parent=None, width=10, height=20, dpi=300):
        self.fig = plt.Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)


# =============================
#  MAIN WINDOW (PyQt5)
# =============================

class PSFMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

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

        # Default options
        self.options = {
            "pxPerUmAx": 1.0/PX_AXIAL_MICRON,
            "pxPerUmLat": 1.0/PX_LATERAL_MICRON,
            "windowUm": [15.0, 15.0, 15.0],
            "thresh": THRESHOLD,
        }

        self._init_ui()

    # ---------- UI setup ----------

    def _init_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        # Controls
        controls = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls)

        controls.addWidget(QtWidgets.QLabel("Threshold:"))
        self.thresh_edit = QtWidgets.QDoubleSpinBox()
        self.thresh_edit.setRange(0, 1e9)
        self.thresh_edit.setValue(self.options["thresh"])
        self.thresh_edit.setDecimals(1)
        controls.addWidget(self.thresh_edit)

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

        controls.addSpacing(10)
        self.run_button = QtWidgets.QPushButton("Run analysis")
        self.run_button.clicked.connect(self.run_analysis)
        controls.addWidget(self.run_button)

        controls.addSpacing(20)
        self.info_label = QtWidgets.QLabel("No image loaded")
        controls.addWidget(self.info_label)

        controls.addStretch(1)

        # Matplotlib canvas
        self.canvas = MplCanvas(self, width=12, height=20, dpi=100)
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

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

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
            self.FOV_Y_um, self.FOV_X_um = im.shape[1] * PX_LATERAL_MICRON, im.shape[2] * PX_LATERAL_MICRON
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
            return

        if im.ndim != 3:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Expected 3D stack, got shape {im.shape}"
            )
            return

        self.im = im.astype(np.float32)
        self.filename = fname

        zmax = self.im.shape[0] - 1
        self.zmin_edit.setRange(0, zmax)
        self.zmax_edit.setRange(0, zmax)
        self.zmin_edit.setValue(0)
        self.zmax_edit.setValue(zmax)

        self.info_label.setText(
            f"Loaded: {os.path.basename(fname)}, shape={self.im.shape}"
        )
        # Cconstruct experiment_key
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

        # Compute stats; guard against all-NaN columns
        def safe_median(series):
            vals = series.to_numpy()
            if np.all(np.isnan(vals)):
                return np.nan
            return np.nanmedian(vals)

        def safe_std(series):
            vals = series.to_numpy()
            if np.all(np.isnan(vals)):
                return np.nan
            return np.nanstd(vals, ddof=0)

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

        try:
            fig = self.canvas.fig
            # Ensure layout is up to date before saving
            fig.tight_layout(pad=1.0, w_pad=0.8, h_pad=1.2)
            fig.savefig(fname, dpi=300, format="png")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save PNG:\n{e}")

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

        self.stats_df = pd.DataFrame(rows).set_index("bead_id")

        self.info_label.setText(f"{len(self.beads)} beads found; stats computed")
        self.update_plots()

    # ---------- Plotting ----------

    def clear_plots(self):
        self.canvas.fig.clear()
        self.canvas.draw()

    def update_plots(self):
        """
        Layout:
            Top row (small): 2 histograms (axial, lateral)
            Bottom row (large): 2 PSF maps (axial, lateral) that are taller and wider,
            visually dominating the page.

        We use GridSpec to give more space to the bottom row and slightly more width
        to the image plots.
        """
        if self.stats_df is None or self.stats_df.empty or self.smoothed is None:
            self.clear_plots()
            return

        fig = self.canvas.fig
        fig.clear()

        import matplotlib.gridspec as gridspec

        # Adjust overall figure size if you want bigger plots in absolute terms
        # (this affects the embedded canvas size too, but you can tune as needed)
        fig.set_size_inches(10, 8)  # width, height in inches

        # GridSpec: 2 rows, 2 columns, but with unequal row heights
        # row_heights: top row = 1, bottom row = 2.5 (so bottom ~70% of height)
        gs = gridspec.GridSpec(
            2, 2,
            height_ratios=[1.0, 2.5],
            width_ratios=[1.0, 1.0],
            figure=fig
        )

        # ---------- Top row: histograms (smaller) ----------
        ax_hist_axial = fig.add_subplot(gs[0, 0])
        ax_hist_lat   = fig.add_subplot(gs[0, 1])

        axial_vals = self.stats_df["FWHMax"].tolist()
        lat_vals   = self.stats_df["FWHMlat"].tolist()

        ax_hist_axial.hist(axial_vals, 20, range=(1, 6))
        ax_hist_axial.set_xlim([1, 6])
        ax_hist_axial.set_xlabel("Axial FWHM (µm)")
        ax_hist_axial.set_xticks(range(1, 7))
        ax_hist_axial.set_ylabel("# Beads")

        ax_hist_lat.hist(lat_vals, 20, range=(1, 6))
        ax_hist_lat.set_xlim([1, 6])
        ax_hist_lat.set_xticks(range(1, 7))
        ax_hist_lat.set_xlabel("Lateral FWHM (µm)")
        ax_hist_lat.set_ylabel("# Beads")

        # ---------- Bottom row: PSF maps (larger) ----------
        ax_im_axial = fig.add_subplot(gs[1, 0])
        ax_im_lat   = fig.add_subplot(gs[1, 1])

        smoothed_img = self.smoothed   # already 2D max-projection
        cmap = "jet"

        # Axial FWHM map
        ax_im_axial.imshow(smoothed_img, cmap="gray", aspect="equal", extent=(0, self.FOV_X_um, 0, self.FOV_Y_um))
        overlay0 = ax_im_axial.scatter(
            (self.stats_df["X"]*PX_LATERAL_MICRON).tolist(),
            (self.stats_df["Y"]*PX_LATERAL_MICRON).tolist(),
            c=self.stats_df["FWHMax"].tolist(),
            cmap=cmap,
            vmin=0,
            vmax=5,
            s=20,   # marker size; increase if you want larger dots
            edgecolors="none"
        )
        ax_im_axial.set_title("PSF: Axial FWHM")
        ax_im_axial.set_xlabel("FOV_X (µm)")
        ax_im_axial.set_ylabel("FOV_Y (µm)")
        cbar0 = fig.colorbar(overlay0, ax=ax_im_axial, fraction=0.040, pad=0.02)
        #cbar0.set_label("Axial FWHM (µm)")

        # Lateral FWHM map
        ax_im_lat.imshow(smoothed_img, cmap="gray", aspect="equal", extent=(0, self.FOV_X_um, 0, self.FOV_Y_um))
        overlay1 = ax_im_lat.scatter(
            (self.stats_df["X"]*PX_LATERAL_MICRON).tolist(),
            (self.stats_df["Y"]*PX_LATERAL_MICRON).tolist(),
            c=self.stats_df["FWHMlat"].tolist(),
            cmap=cmap,
            vmin=0,
            vmax=5,
            s=20,
            edgecolors="none"
        )
        ax_im_lat.set_title("PSF: Lateral FWHM")
        ax_im_lat.set_xlabel("FOV_X (µm)")
        ax_im_lat.set_ylabel("FOV_Y (µm)")
        cbar1 = fig.colorbar(overlay1, ax=ax_im_lat, fraction=0.040, pad=0.02)
        cbar1.set_label("FWHM (µm)")

        # Make layout tight but leave some breathing room
        fig.tight_layout(pad=1.0, w_pad=0.7, h_pad=0.7)
        self.canvas.draw()

# =============================
#  ENTRY POINT
# =============================

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = PSFMainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()