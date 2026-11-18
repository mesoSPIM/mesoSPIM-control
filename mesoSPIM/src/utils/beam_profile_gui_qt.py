#!/usr/bin/env python3
"""
Beam profile analysis from an image of a static (non-scanned) excitation beam.

- Open a TIF (snap or stack; a stack is averaged over up to 10 central frames),
  from the file dialog, by drag and drop, or preloaded by mesoSPIM-control
- The beam runs horizontally. Crop rows around it by dragging on the image
- Gaussian fit across the beam in bins of columns, then a hyperbola along it:
    FWHM(x)^2 = FWHM_waist^2 + (1.1774 theta (x - x_waist))^2
- Reports effective NA = n sin(theta), waist FWHM and beam length
  (2zR: the range where FWHM <= sqrt2 x waist FWHM)

Assumptions: Gaussian beam; the detection is focused on the beam. Detection blur and
pixel size are part of the measured waist and length (upper bounds); theta, and so
the NA, does not depend on the pixel size.
"""
import os
import sys

import numpy as np
from scipy.optimize import curve_fit
from scipy.ndimage import median_filter, uniform_filter1d
from tifffile import TiffFile

from PyQt5 import QtWidgets

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import SpanSelector

FWHM_PER_W = np.sqrt(2 * np.log(2))   # intensity FWHM / 1/e^2 radius = 1.1774
FULL_SCALE = (255, 4095, 16383, 65535)  # 8/12/14/16-bit ADC full scale
MAX_FRAMES = 10
OUTLIER_REL = 0.3   # bin FWHM off its 5-bin running median by more than this fraction: excluded


def _gauss(y, A, y0, s, c):
    return A * np.exp(-0.5 * ((y - y0) / s) ** 2) + c


def _observed_fwhm(x, f0, xw, theta):
    return np.sqrt(f0 ** 2 + (FWHM_PER_W * theta * (x - xw)) ** 2)


def saturation(raw):
    """(saturated, max value, pixels at max) for an integer image.
    Saturated: the max is the dtype maximum, or a full-scale ADC value shared by >= 5 pixels."""
    raw = np.asarray(raw)
    if raw.dtype.kind not in "ui":
        return False, float(raw.max()), 0
    m = int(raw.max())
    n = int((raw == m).sum())
    return bool(m == np.iinfo(raw.dtype).max or (m in FULL_SCALE and n >= 5)), m, n


def read_image(path):
    """Return (mean image as float, per-pixel max of the raw frames, number of frames, pixel size in um or None)."""
    with TiffFile(path) as tf:
        series = tf.series[0]
        central = lambda n: list(range(max(0, n // 2 - MAX_FRAMES // 2), min(n, n // 2 + MAX_FRAMES // 2)))
        if len(series.shape) == 2 and len(tf.pages) > 1:      # one series per page (page-per-frame writers)
            frames = np.stack([tf.pages[i].asarray() for i in central(len(tf.pages))])
        else:
            n = int(np.prod(series.shape[:-2])) if len(series.shape) > 2 else 1
            frames = tf.asarray(key=central(n), series=0) if n > MAX_FRAMES else series.asarray()
        px = None
        xres = tf.pages[0].tags.get("XResolution")
        unit = (tf.imagej_metadata or {}).get("unit", "")
        if xres is not None and unit in ("um", "micron", "µm", "\\u00B5m"):
            num, den = xres.value
            px = den / num if num else None
    frames = np.asarray(frames).reshape((-1,) + np.asarray(frames).shape[-2:])
    return frames.mean(0), frames.max(0), frames.shape[0], px


def read_sidecar_laser(path):
    """Laser (e.g. '488 nm') from the mesoSPIM metadata sidecar '<path>_meta.txt', or None."""
    try:
        with open(path + "_meta.txt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("[Laser]"):
                    return line[len("[Laser]"):].strip() or None
    except OSError:
        pass
    return None


def measured_range(xs, fw, ib):
    """Model-free beam range: walk out from the narrowest bin ib to where the measured FWHM first
    exceeds sqrt2 x fw[ib], interpolating the crossings. Returns (x_left, x_right, reaches_edge)."""
    thr = np.sqrt(2) * fw[ib]
    ends, edge = [], False
    for step in (-1, 1):
        i = ib
        while 0 <= i + step < len(fw) and fw[i + step] <= thr:
            i += step
        j = i + step
        if 0 <= j < len(fw):                    # crossing between bins i (inside) and j (outside)
            ends.append(xs[i] + (xs[j] - xs[i]) * (thr - fw[i]) / (fw[j] - fw[i]))
        else:                                   # still inside at the end of the analysed range
            ends.append(xs[i])
            edge = True
    return ends[0], ends[1], edge


def analyse_beam(img, px_um, n=1.0, bin_cols=10):
    """Analyse a 2D image of a beam running along x. Lengths in um."""
    a = np.asarray(img, dtype=float)
    H, W = a.shape
    edge = max(1, min(20, H // 10))
    bg = np.median(np.concatenate([a[:edge].ravel(), a[-edge:].ravel()]))
    y = np.arange(H)
    xs, fw, power = [], [], []
    for x0 in range(0, W - bin_cols + 1, bin_cols):
        prof = np.median(a[:, x0:x0 + bin_cols], axis=1) - bg
        i = int(np.argmax(np.convolve(prof, np.ones(5) / 5, "same")))
        try:
            p, _ = curve_fit(_gauss, y, prof, p0=[max(prof[i], 1e-3), i, 5, 0],
                             bounds=([0, 0, 0.3, -np.inf], [np.inf, H - 1, H, np.inf]), maxfev=5000)
        except (RuntimeError, ValueError):
            continue
        xs.append(x0 + bin_cols / 2)
        fw.append(2 * np.sqrt(2 * np.log(2)) * p[2])
        power.append(p[0] * p[2])
    xs, fw, power = map(np.array, (xs, fw, power))
    keep = fw < H / 4                       # wider than 1/4 of the crop: tails clipped, FWHM biased low
    n_dropped = int((~keep).sum())
    xs, fw, power = xs[keep], fw[keep], power[keep]
    if len(xs) < 5:
        raise ValueError("Beam not found: fewer than 5 column bins could be fitted (crop too narrow?).")
    # Outlier bins (fit locked on dust or a hot pixel): FWHM far from the running median of its neighbours
    med = median_filter(fw, size=5, mode="nearest")
    out = np.abs(fw - med) > OUTLIER_REL * med
    out_x, out_fw = xs[out], fw[out]
    xs, fw, power = xs[~out], fw[~out], power[~out]
    if len(xs) < 5:
        raise ValueError("Beam not found: fewer than 5 consistent column bins.")

    fs = uniform_filter1d(fw, size=3, mode="nearest")    # light smoothing: the min of noisy bins is biased low
    ib = int(np.argmin(fs))
    far = max(np.abs(xs - xs[ib]).max(), 1)
    th0 = min(max((fw.max() - fw[ib]) / FWHM_PER_W / far, 1e-3), 0.5)
    pm, _ = curve_fit(_observed_fwhm, xs, fw, p0=[fw[ib], xs[ib], th0],
                      bounds=([0.05, 0, 1e-4], [20 * fw[ib], W, 1.0]), maxfev=20000)
    f0, xw, theta = pm
    length = 2 * f0 / (FWHM_PER_W * theta)
    m0, m1, m_edge = measured_range(xs, fs, ib)
    return dict(
        x_um=xs * px_um, fwhm_um=fw * px_um, fit_params_px=pm, px_um=px_um,
        outlier_x_um=out_x * px_um, outlier_fwhm_um=out_fw * px_um,
        min_fwhm_um=fs[ib] * px_um, min_x_um=xs[ib] * px_um,
        meas_x0_um=m0 * px_um, meas_x1_um=m1 * px_um, meas_length_um=(m1 - m0) * px_um,
        meas_length_at_edge=m_edge,
        waist_fwhm_um=f0 * px_um, waist_x_um=xw * px_um, theta_rad=theta, na_eff=n * np.sin(theta), n=n,
        two_zR_um=length * px_um, waist_in_image=bool(xs[0] < xw < xs[-1]),
        length_in_image=bool(xw - length / 2 > xs[0] and xw + length / 2 < xs[-1]),
        power_cv=power.std() / power.mean(), n_dropped=n_dropped,
    )


def report(res, warnings=()):
    lines = [
        f"Effective NA   {res['na_eff']:.3f}   (n = {res['n']:.3f})",
        f"Waist FWHM     {res['waist_fwhm_um']:.2f} um   (fit)",
        f"Min FWHM       {res['min_fwhm_um']:.2f} um   (measured, 3-bin mean, at x = {res['min_x_um']:.0f} um)",
        f"Beam length    {res['two_zR_um']:.0f} um   (fit, 2zR: FWHM <= sqrt2 x waist FWHM)",
        f"Beam length    {'>= ' if res['meas_length_at_edge'] else ''}{res['meas_length_um']:.0f} um   "
        "(measured: FWHM <= sqrt2 x min FWHM)",
        "",
        "Fit values assume a Gaussian beam; with aberrations (e.g. spherical)",
        "trust the measured values. All assume the detection is focused on the beam.",
        "Waist and length include detection blur and pixel size (upper bounds);",
        "the NA does not depend on them.",
    ]
    if res["meas_length_at_edge"]:
        warnings = list(warnings) + ["Measured length reaches the end of the image: it is a lower bound."]
    if not res["waist_in_image"]:
        warnings = list(warnings) + ["Waist outside the analysed range: values are extrapolated."]
    elif not res["length_in_image"]:
        warnings = list(warnings) + ["Beam length extends past the image: length is extrapolated."]
    if res["power_cv"] > 0.2:
        warnings = list(warnings) + [f"Light per column varies {100 * res['power_cv']:.0f}% along the beam "
                                     "(expected constant)."]
    if len(res["outlier_x_um"]):
        warnings = list(warnings) + [f"{len(res['outlier_x_um'])} column bins excluded as outliers "
                                     "(FWHM inconsistent with neighbours: dust, hot pixel?)."]
    if res["n_dropped"]:
        warnings = list(warnings) + [f"{res['n_dropped']} column bins skipped: beam wider than 1/4 of the crop."]
    if warnings:
        lines += ["", "WARNINGS:"] + [f"- {w}" for w in warnings]
    return "\n".join(lines)


class BeamProfileWindow(QtWidgets.QMainWindow):
    def __init__(self, pixel_pitch_um=4.25, mag=5.0, start_dir="", laser=""):
        super().__init__()
        self.setWindowTitle("Beam profile analysis")
        self.setAcceptDrops(True)
        self.start_dir = start_dir
        self.img = self.raw_max = self.file_px = None
        self.path = None
        self.n_frames = 0

        self.pitch = QtWidgets.QDoubleSpinBox(decimals=3, minimum=0.1, maximum=100, value=pixel_pitch_um)
        self.pitch.setToolTip("Camera pixel pitch, um")
        self.mag = QtWidgets.QDoubleSpinBox(decimals=3, minimum=0.01, maximum=1000, value=mag)
        self.mag.setToolTip("Detection magnification; sample pixel = camera pixel / magnification")
        self.n = QtWidgets.QDoubleSpinBox(decimals=3, minimum=1.0, maximum=2.0, singleStep=0.01, value=1.56)
        self.n.setToolTip("Refractive index of the immersion medium (for the NA)")
        self.laser = QtWidgets.QLineEdit(laser)
        self.laser.setMaximumWidth(80)
        self.laser.setToolTip("Excitation wavelength, shown in the plot title and report. "
                              "Taken from the file's mesoSPIM metadata (_meta.txt) when present.")
        self.laser.editingFinished.connect(self.run)
        self.crop0 = QtWidgets.QSpinBox(minimum=0, maximum=0)
        self.crop1 = QtWidgets.QSpinBox(minimum=0, maximum=0)
        for w in (self.crop0, self.crop1):
            w.setToolTip("Rows to analyse (px). Or drag vertically on the image. "
                         "Keep some background above and below the beam: the background is taken from the crop edges.")
            w.editingFinished.connect(self.run)
        open_btn = QtWidgets.QPushButton("Open TIF...")
        run_btn = QtWidgets.QPushButton("Analyse")
        save_btn = QtWidgets.QPushButton("Save PNG...")
        open_btn.clicked.connect(self.open_tif)
        run_btn.clicked.connect(self.run)
        save_btn.clicked.connect(self.save_png)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(open_btn)
        for label, w in (("Camera pixel (um)", self.pitch), ("Magnification", self.mag), ("n", self.n),
                         ("Laser", self.laser), ("Rows from", self.crop0), ("to", self.crop1)):
            bar.addWidget(QtWidgets.QLabel(label))
            bar.addWidget(w)
        bar.addWidget(run_btn)
        bar.addWidget(save_btn)
        bar.addStretch()

        self.fig = Figure(figsize=(10, 7))
        self.canvas = FigureCanvas(self.fig)
        self.text = QtWidgets.QPlainTextEdit(readOnly=True)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.text.setStyleSheet("font-family: Consolas, monospace;")
        self.text.setPlainText("Open a TIF, or drag and drop one here.")
        split = QtWidgets.QSplitter()
        split.addWidget(self.canvas)
        split.addWidget(self.text)
        split.setSizes([950, 450])

        lay = QtWidgets.QVBoxLayout()
        lay.addLayout(bar)
        lay.addWidget(split)
        central = QtWidgets.QWidget()
        central.setLayout(lay)
        self.setCentralWidget(central)
        self.resize(1400, 800)

    def px(self):
        return self.pitch.value() / self.mag.value()

    def open_tif(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open beam image", self.start_dir, "TIFF (*.tif *.tiff)")
        if path:
            self.load(path)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(url.toLocalFile().lower().endswith((".tif", ".tiff")) for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith((".tif", ".tiff")):
                self.load(path)
                return

    def load(self, path):
        try:
            self.img, self.raw_max, self.n_frames, self.file_px = read_image(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Beam profile", f"Failed to open file:\n{e}")
            return
        self.path = path
        laser = read_sidecar_laser(path)
        if laser:
            self.laser.setText(laser)
        H = self.img.shape[0]
        for w, v in ((self.crop0, 0), (self.crop1, H)):
            w.blockSignals(True)
            w.setMaximum(H)
            w.setValue(v)
            w.blockSignals(False)
        self.setWindowTitle(f"Beam profile analysis - {os.path.basename(path)}")
        self.run()

    def _on_span(self, y_min_um, y_max_um):
        for w, v in ((self.crop0, y_min_um / self.px()), (self.crop1, y_max_um / self.px())):
            w.blockSignals(True)
            w.setValue(int(round(v)))
            w.blockSignals(False)
        self.run()

    def run(self):
        if self.img is None:
            return
        a, b = sorted((self.crop0.value(), self.crop1.value()))
        if b - a < 10:
            self.text.setPlainText("Crop too narrow: select at least 10 rows.")
            return
        warnings = []
        sat, vmax, nmax = saturation(self.raw_max[a:b])
        if sat:
            warnings.append(f"SATURATED: {nmax} pixels at {vmax}. Results unreliable: "
                            "lower the laser power or exposure.")
        if self.file_px and abs(self.file_px / self.px() - 1) > 0.05:
            warnings.append(f"The TIF stores {self.file_px:.3f} um/px; using {self.px():.3f} um/px "
                            "(camera pixel / magnification).")
        try:
            res = analyse_beam(self.img[a:b], self.px(), self.n.value())
        except Exception as e:
            self.text.setPlainText(f"Analysis failed: {e}")
            return
        laser = self.laser.text().strip()
        self.text.setPlainText(
            (f"Laser          {laser}\n" if laser else "") +
            report(res, warnings) + "\n\n" +
            f"Pixel {self.px():.3f} um ({self.pitch.value():g} um / {self.mag.value():g}x), "
            f"rows {a}-{b}, {self.n_frames} frame(s) averaged")
        self.plot(res, a, b)

    def plot(self, res, a, b):
        self.fig.clear()
        ax = self.fig.subplots(2, 1, sharex=True)
        px = res["px_um"]
        H, W = self.img.shape
        ax[0].imshow(self.img, cmap="gray", aspect="auto", extent=(0, W * px, H * px, 0),
                     vmin=np.percentile(self.img, 1), vmax=np.percentile(self.img, 99.9))
        ax[0].axhspan(0, a * px, color="k", alpha=0.6)
        ax[0].axhspan(b * px, H * px, color="k", alpha=0.6)
        ax[0].set_ylim(H * px, 0)
        ax[0].set_ylabel("y (um)")
        laser = self.laser.text().strip()
        ax[0].set_title(f"{os.path.basename(self.path or '')}" + (f", laser {laser}" if laser else "")
                        + "  (drag vertically to crop)")
        self._span = SpanSelector(ax[0], self._on_span, "vertical", useblit=True, minspan=10 * px,
                                  props=dict(facecolor="tab:orange", alpha=0.3))
        ax[1].plot(res["x_um"], res["fwhm_um"], ".", ms=3, label="FWHM across the beam")
        xx = np.linspace(0, W, 1000)
        ax[1].plot(xx * px, _observed_fwhm(xx, *res["fit_params_px"]) * px, "-",
                   label=f"fit: NA {res['na_eff']:.3f}, waist FWHM {res['waist_fwhm_um']:.2f} um, "
                         f"length {res['two_zR_um']:.0f} um")
        if len(res["outlier_x_um"]):
            ax[1].plot(res["outlier_x_um"], res["outlier_fwhm_um"], "x", color="gray", ms=5,
                       label=f"outlier bins, excluded ({len(res['outlier_x_um'])})")
        ax[1].plot(res["min_x_um"], res["min_fwhm_um"], "v", color="tab:red", ms=7,
                   label=f"min measured FWHM {res['min_fwhm_um']:.2f} um")
        ax[1].axhline(np.sqrt(2) * res["min_fwhm_um"], color="tab:red", ls=":", lw=1)
        ax[1].axvspan(res["meas_x0_um"], res["meas_x1_um"], facecolor="none", edgecolor="tab:red",
                      hatch="//", alpha=0.5,
                      label=f"measured length {'>= ' if res['meas_length_at_edge'] else ''}"
                            f"{res['meas_length_um']:.0f} um")
        ax[1].axhline(np.sqrt(2) * res["waist_fwhm_um"], color="gray", ls=":", lw=1)
        ax[1].axvspan(res["waist_x_um"] - res["two_zR_um"] / 2, res["waist_x_um"] + res["two_zR_um"] / 2,
                      color="tab:green", alpha=0.15)
        ax[1].set_ylabel("FWHM (um)")
        ax[1].set_xlabel("x along the beam (um)")
        ax[1].set_ylim(0, None)
        ax[1].legend(fontsize=8)
        self.fig.tight_layout()
        self.canvas.draw()

    def save_png(self):
        if self.img is None:
            return
        default = os.path.splitext(self.path)[0] + "_beam_profile.png" if self.path else ""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save figure", default, "PNG (*.png)")
        if path:
            self.fig.savefig(path, dpi=120)
            with open(os.path.splitext(path)[0] + ".txt", "w", encoding="utf-8") as f:
                f.write(f"{self.path}\n\n{self.text.toPlainText()}\n")


def main():
    """Standalone entry point; mesoSPIM_control launches it as a separate process."""
    import argparse
    parser = argparse.ArgumentParser(description="Beam profile analysis from an image of a static beam")
    parser.add_argument("tiff_path", nargs="?", default=None, help="TIF to preload")
    parser.add_argument("--pixel-pitch", type=float, default=4.25, dest="pixel_pitch",
                        help="Camera pixel pitch in um")
    parser.add_argument("--mag", type=float, default=5.0, help="Detection magnification")
    parser.add_argument("--dir", default="", help="Start folder of the file dialog")
    parser.add_argument("--laser", default="", help="Excitation laser, e.g. '488 nm' (a file's _meta.txt overrides it)")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = BeamProfileWindow(args.pixel_pitch, args.mag, args.dir, args.laser)
    win.show()
    if args.tiff_path:
        win.load(args.tiff_path)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
