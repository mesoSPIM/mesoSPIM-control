#!/usr/bin/env python3
"""
Single-file PyQt5 GUI application for field curvature / chromatic focal shift analysis.

Ported from the `ContrastMapsChromatic-*.ipynb` notebooks of the `lens-testing` repo.

- Open one TIF z-stack of a Ronchi grating (monochromatic), or several stacks acquired
  through different bandpass filters (polychromatic), each with a user-defined label
  and (optionally) a wavelength.
- Divide each frame into a grid of ROIs, compute Michelson-style contrast per ROI and
  per Z-plane -> a (Z, N_ROIs_Y, N_ROIs_X) contrast table per channel.
- Tab 1: 4-panel contrast map of the selected channel.
- Tab 2: field curvature across X and Y for all channels, axial chromatic shift vs
  wavelength (polychromatic only), and a text summary (DOF, sag).
- Save the current tab as a single 300 DPI PNG.

AXIS CONVENTION
---------------
Y is stack array axis 1 (TIFF rows, ImageLength) and X is array axis 2 (TIFF columns,
ImageWidth) - the standard image convention, so Y is the vertical axis in Fiji and in
these figures. On mesoSPIM stacks Y is also the long axis of the frame (e.g. 5056 x 2960
px), even though the acquisition metadata calls that dimension `x_pixels`; the stored
array is what counts here. Same convention as the source notebooks, whose `N_ROIs_H`
indexes axis 1 and is called Y.

Y rows are reversed for display, so the panels look like the stack does in ImageJ (row 0
on top) while FOV_Y still runs upward from 0 at the bottom edge of the frame. FOV_Y = 0
is therefore the LAST array row, and FOV_Y = max is array row 0.

www.mesoSPIM.org, GPL-3 License.
"""
# Default parameters
MAG = 5.0                     # effective magnification of the system
PIXEL_PITCH_MICRON = 4.25     # camera pixel pitch
Z_STEP_MICRON = 10.0          # distance between planes of the z-stack
N_ROIS_Y = 16                 # number of ROIs along Y, frame axis 1 (rows)
N_ROIS_X = 16                 # number of ROIs along X, frame axis 2 (columns)
CONTRAST_MIN = 0.25           # lower limit of the contrast map color scale
CONTRAST_MAX = 0.95           # upper limit of the contrast map color scale
CMAP = 'plasma'
COLORMAPS = ['plasma', 'viridis', 'magma', 'inferno', 'gray', 'jet']
MARKERS = ['o', '*', '^', 'D', '>', '<', 'x', 's', 'v', 'P']

import os
import sys
import numpy as np

from PyQt5 import QtCore, QtWidgets

from scipy.ndimage import zoom

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from tifffile import TiffFile

try:
    from . import optimization as opt
except ImportError:  # launched as a standalone script
    import optimization as opt


# =============================
#  ANALYSIS FUNCTIONS
# =============================

def wavelength_to_rgb(wavelength_nm):
    """A crude mapping of nm to RGB space, for plotting purposes."""
    min_wavelength, max_wavelength = 400, 720
    normalized = (wavelength_nm - min_wavelength) / (max_wavelength - min_wavelength)
    return plt.get_cmap('turbo')(np.clip(normalized, 0, 1))


def contrast(roi):
    """Contrast value (max-min)/(max+min) of an image ROI, using the 1/99 percentiles."""
    mini = np.percentile(roi, 1)
    maxi = np.percentile(roi, 99)
    return (maxi - mini) / (maxi + mini)


def contrast_table_from_stack(path, n_rois_y=N_ROIS_Y, n_rois_x=N_ROIS_X, progress_cb=None):
    """
    Compute the per-ROI contrast table of a TIF z-stack.

    The stack is read plane by plane rather than as a whole: these files are routinely
    several GB, and the polychromatic case loads a handful of them, so only the small
    contrast table is ever held in memory.

    Parameters
    ----------
    path : str
        TIF z-stack of a Ronchi grating (or similar periodic target).
    n_rois_y, n_rois_x : int
        Number of ROIs along frame axis 1 (Y, rows) and axis 2 (X, columns).
    progress_cb : callable(plane_index, n_planes) -> bool, optional
        Called after each plane. Return False to abort; the function then raises
        KeyboardInterrupt.

    Returns
    -------
    (table, n_saturated_planes) : (np.ndarray, int)
        `table` has shape (Z, n_rois_y, n_rois_x), dtype float64.
        `n_saturated_planes` counts planes containing at least one pixel at the dtype
        maximum - such a stack is clipped and its contrast underestimated.
    """
    with TiffFile(path) as tif_file:
        pages = tif_file.pages
        n_z = len(pages)
        if n_z < 3:
            raise ValueError(f"Expected a z-stack, got {n_z} plane(s) in {os.path.basename(path)}")

        table = np.empty((n_z, n_rois_y, n_rois_x))
        n_saturated_planes = 0
        roi_y = roi_x = None

        for iz, page in enumerate(pages):
            plane = page.asarray()
            if plane.ndim != 2:
                raise ValueError(f"Expected 2D planes, got shape {plane.shape}")
            if roi_y is None:
                roi_y, roi_x = plane.shape[0] // n_rois_y, plane.shape[1] // n_rois_x
                if roi_y < 2 or roi_x < 2:
                    raise ValueError(
                        f"ROI grid {n_rois_y}x{n_rois_x} is too fine for frames of "
                        f"shape {plane.shape}"
                    )
            if np.issubdtype(plane.dtype, np.integer) and plane.max() >= np.iinfo(plane.dtype).max:
                n_saturated_planes += 1

            # Same ROIs as a nested per-ROI loop, but vectorised over the whole plane.
            blocks = plane[:n_rois_y * roi_y, :n_rois_x * roi_x].reshape(
                n_rois_y, roi_y, n_rois_x, roi_x)
            # Both percentiles in one call: same values, but roughly half the time of
            # two separate calls, which each re-partition the whole plane.
            mini, maxi = np.percentile(blocks, [1, 99], axis=(1, 3))
            table[iz] = (maxi - mini) / (maxi + mini)

            if progress_cb is not None and not progress_cb(iz, n_z):
                raise KeyboardInterrupt(f"Analysis of {os.path.basename(path)} cancelled")

    return table, n_saturated_planes


def z_profile_from_table(table, z_step_um, upsampling_factor=None):
    """
    Axial position of maximum contrast for every ROI, in microns.

    The contrast table is first upsampled along Z by cubic interpolation, so the peak
    position is not quantised to the (coarse) z-step of the acquisition.

    Returns
    -------
    np.ndarray of shape (n_rois_y, n_rois_x), in microns from the first plane.
    """
    if upsampling_factor is None:
        upsampling_factor = max(1, int(round(z_step_um)))
    upsampled = zoom(table, zoom=(upsampling_factor, 1, 1), order=3)
    return np.argmax(upsampled, axis=0) * (z_step_um / upsampling_factor)


def summary_metrics(table, z_step_um, fov_x_mm, fov_y_mm):
    """
    Depth of field and field curvature sag, from gaussian fits of the axial contrast
    profile at the center and at the four edge midpoints of the ROI grid.

    Returns a dict with `dof_um`, `sag_x_um`, `sag_y_um`, `ave_sag_um`, `z_best_um`,
    `max_contrast` and `mean_contrast_best_plane`.
    """
    n_z, n_y, n_x = table.shape
    z_range = np.linspace(0, z_step_um * (n_z - 1), n_z)
    cy, cx = n_y // 2, n_x // 2

    fit_center, fit_sigma, _, _ = opt.fit_gaussian_1d(table[:, cy, cx], z_range)
    # Sag across FOV_Y: peak contrast position at the two ends of axis 1 (rows).
    center_y_low, _, _, _ = opt.fit_gaussian_1d(table[:, 0, cx], z_range)
    center_y_high, _, _, _ = opt.fit_gaussian_1d(table[:, -1, cx], z_range)
    # Sag across FOV_X: same along axis 2 (columns).
    center_x_low, _, _, _ = opt.fit_gaussian_1d(table[:, cy, 0], z_range)
    center_x_high, _, _, _ = opt.fit_gaussian_1d(table[:, cy, -1], z_range)

    sag_x = abs(fit_center - 0.5 * (center_x_low + center_x_high))
    sag_y = abs(fit_center - 0.5 * (center_y_low + center_y_high))
    z_best_index = int(np.argmax(table[:, cy, cx]))

    return {
        'dof_um': opt.sigma2fwhm(fit_sigma),
        'sag_x_um': sag_x,
        'sag_y_um': sag_y,
        'ave_sag_um': (sag_x * fov_x_mm + sag_y * fov_y_mm) / (fov_x_mm + fov_y_mm),
        'z_best_um': fit_center,
        'z_best_index': z_best_index,
        'max_contrast': float(table.max()),
        'mean_contrast_best_plane': float(table[z_best_index].mean()),
    }


def linear_trend(profile):
    """Linear trend (slope * index) of a 1D profile, for subtracting sample/slide tilt."""
    index = np.arange(len(profile))
    slope = np.polyfit(index, profile, 1)[0]
    return index * slope


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
        w, h = max(self.width(), 1), max(self.height(), 1)
        dpi = self.fig.get_dpi()
        self.fig.set_size_inches(w / dpi, h / dpi, forward=False)
        if self.fig.get_layout_engine() is None:
            # A figure that sets its own layout engine (e.g. the shared-colorbar contrast
            # maps) rescales itself; tight_layout would fight it and warn.
            try:
                self.fig.tight_layout(pad=1.0, w_pad=0.7, h_pad=0.7)
            except Exception:
                pass
        self.draw_idle()


# =============================
#  MAIN WINDOW (PyQt5)
# =============================

COL_FILE, COL_LABEL, COL_WAVELENGTH = 0, 1, 2


class FieldCurvatureMainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, mag=None, pixel_pitch_micron=None, z_step_micron=None,
                 filenames=None, labels=None, wavelengths=None):
        """
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget, so the window can be launched embedded in another Qt app
            (e.g. mesoSPIM_control) instead of only as a standalone application.
        mag : float, optional
            Effective system magnification. Defaults to MAG.
        pixel_pitch_micron : float, optional
            Camera pixel pitch in microns. Defaults to PIXEL_PITCH_MICRON.
        z_step_micron : float, optional
            Distance between z-planes in microns. Defaults to Z_STEP_MICRON.
        filenames : list of str, optional
            TIF z-stacks to add to the channel table on startup.
        labels : list of str, optional
            Channel labels for *filenames*, in order. Defaults to the file basenames.
        wavelengths : list of float, optional
            Wavelength in nm for *filenames*, in order. Only needed for the axial
            chromatic shift plot.
        """
        super().__init__(parent)

        self.setWindowTitle("Field curvature & chromatic shift (www.mesoSPIM.org). GPL-3 License.")
        self.resize(1400, 900)

        # Analysis results, keyed by channel label
        self.tables = {}
        self.z_profiles = {}
        self.metrics = {}
        self.fov_x_mm = self.fov_y_mm = None
        self.load_folder = None

        self.mag = mag if mag is not None else MAG
        self.pixel_pitch_micron = pixel_pitch_micron if pixel_pitch_micron is not None else PIXEL_PITCH_MICRON
        self.z_step_micron = z_step_micron if z_step_micron is not None else Z_STEP_MICRON

        self._init_ui()
        self.setAcceptDrops(True)

        if filenames:
            self.add_files(filenames, labels, wavelengths)

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
        self.z_step_edit = QtWidgets.QDoubleSpinBox()
        self.z_step_edit.setRange(0.01, 500.0)
        self.z_step_edit.setValue(self.z_step_micron)
        self.z_step_edit.setDecimals(2)
        self.z_step_edit.setSingleStep(1.0)
        self.z_step_edit.valueChanged.connect(self.update_system_parameters)
        params_layout.addWidget(self.z_step_edit)

        params_layout.addSpacing(10)
        params_layout.addWidget(QtWidgets.QLabel("N ROIs (X):"))
        self.n_rois_x_edit = QtWidgets.QSpinBox()
        self.n_rois_x_edit.setRange(3, 128)
        self.n_rois_x_edit.setValue(N_ROIS_X)
        self.n_rois_x_edit.setToolTip("Number of ROIs along X - frame array axis 2, the TIFF columns.")
        params_layout.addWidget(self.n_rois_x_edit)

        params_layout.addSpacing(10)
        params_layout.addWidget(QtWidgets.QLabel("N ROIs (Y):"))
        self.n_rois_y_edit = QtWidgets.QSpinBox()
        self.n_rois_y_edit.setRange(3, 128)
        self.n_rois_y_edit.setValue(N_ROIS_Y)
        self.n_rois_y_edit.setToolTip("Number of ROIs along Y - frame array axis 1, the TIFF rows, vertical in Fiji.")
        params_layout.addWidget(self.n_rois_y_edit)

        params_layout.addStretch(1)

        # Channel table
        channels_group = QtWidgets.QGroupBox("Channels (one row per TIF z-stack)")
        channels_layout = QtWidgets.QHBoxLayout()
        channels_group.setLayout(channels_layout)
        vbox.addWidget(channels_group)

        self.channel_table = QtWidgets.QTableWidget(0, 3)
        self.channel_table.setHorizontalHeaderLabels(["File", "Label", "Wavelength (nm)"])
        self.channel_table.horizontalHeader().setSectionResizeMode(COL_FILE, QtWidgets.QHeaderView.Stretch)
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setMaximumHeight(160)
        self.channel_table.setToolTip(
            "Label and Wavelength are editable, before or after a run. Renaming a dataset "
            "only relabels the figures - it never triggers a recomputation - so labels can "
            "be polished for export. Wavelength is only needed for the axial chromatic "
            "shift plot; leave it blank for a single-channel measurement."
        )
        self.channel_table.itemChanged.connect(self.on_channel_table_edited)
        channels_layout.addWidget(self.channel_table)

        buttons_layout = QtWidgets.QVBoxLayout()
        channels_layout.addLayout(buttons_layout)

        add_button = QtWidgets.QPushButton("Add files...")
        add_button.clicked.connect(self.open_files)
        buttons_layout.addWidget(add_button)

        remove_button = QtWidgets.QPushButton("Remove selected")
        remove_button.clicked.connect(self.remove_selected_channels)
        buttons_layout.addWidget(remove_button)

        buttons_layout.addStretch(1)

        # Analysis controls
        controls = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls)

        self.run_button = QtWidgets.QPushButton("Run analysis")
        self.run_button.clicked.connect(self.run_analysis)
        controls.addWidget(self.run_button)

        controls.addSpacing(20)
        self.detrend_checkbox = QtWidgets.QCheckBox("Subtract tilt, reference channel:")
        self.detrend_checkbox.setToolTip(
            "Fit a linear trend to the central X and Y profiles of the reference channel "
            "and subtract it from every channel. Removes the tilt of the test slide, which "
            "is common to all channels of one acquisition session."
        )
        self.detrend_checkbox.stateChanged.connect(self.update_plots)
        controls.addWidget(self.detrend_checkbox)

        self.reference_combo = QtWidgets.QComboBox()
        self.reference_combo.setMinimumWidth(160)
        self.reference_combo.currentIndexChanged.connect(self.update_plots)
        controls.addWidget(self.reference_combo)

        controls.addSpacing(20)
        self.info_label = QtWidgets.QLabel("No files added")
        controls.addWidget(self.info_label)

        controls.addStretch(1)

        # Display controls (redraw only, no re-analysis)
        controls2 = QtWidgets.QHBoxLayout()
        vbox.addLayout(controls2)

        controls2.addWidget(QtWidgets.QLabel("Show channel:"))
        self.channel_combo = QtWidgets.QComboBox()
        self.channel_combo.setMinimumWidth(160)
        self.channel_combo.currentIndexChanged.connect(self.update_plots)
        controls2.addWidget(self.channel_combo)

        controls2.addSpacing(10)
        controls2.addWidget(QtWidgets.QLabel("Contrast min:"))
        self.contrast_min_edit = QtWidgets.QDoubleSpinBox()
        self.contrast_min_edit.setRange(0.0, 1.0)
        self.contrast_min_edit.setValue(CONTRAST_MIN)
        self.contrast_min_edit.setDecimals(2)
        self.contrast_min_edit.setSingleStep(0.05)
        self.contrast_min_edit.valueChanged.connect(self.update_plots)
        controls2.addWidget(self.contrast_min_edit)

        controls2.addSpacing(10)
        controls2.addWidget(QtWidgets.QLabel("Contrast max:"))
        self.contrast_max_edit = QtWidgets.QDoubleSpinBox()
        self.contrast_max_edit.setRange(0.0, 1.0)
        self.contrast_max_edit.setValue(CONTRAST_MAX)
        self.contrast_max_edit.setDecimals(2)
        self.contrast_max_edit.setSingleStep(0.05)
        self.contrast_max_edit.valueChanged.connect(self.update_plots)
        controls2.addWidget(self.contrast_max_edit)

        controls2.addSpacing(10)
        controls2.addWidget(QtWidgets.QLabel("Colormap:"))
        self.cmap_combo = QtWidgets.QComboBox()
        self.cmap_combo.addItems(COLORMAPS)
        self.cmap_combo.setCurrentText(CMAP)
        self.cmap_combo.currentIndexChanged.connect(self.update_plots)
        controls2.addWidget(self.cmap_combo)

        controls2.addStretch(1)

        # Figure tabs
        self.tabs = QtWidgets.QTabWidget()
        self.maps_canvas = MplCanvas(self, dpi=100)
        self.summary_canvas = MplCanvas(self, dpi=100)
        self.tabs.addTab(self.maps_canvas, "Contrast maps")
        self.tabs.addTab(self.summary_canvas, "Field curvature summary")
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                            QtWidgets.QSizePolicy.Expanding)
        self.tabs.setSizePolicy(size_policy)
        vbox.addWidget(self.tabs)

        self._init_menus()

    def _init_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QtWidgets.QAction("Add TIF files...", self)
        open_action.triggered.connect(self.open_files)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_png_action = QtWidgets.QAction("Save current tab as PNG (300 DPI)...", self)
        save_png_action.triggered.connect(self.save_png_figure)
        file_menu.addAction(save_png_action)

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # ---------- Parameter updates ----------

    def update_system_parameters(self):
        """Update system parameters and redraw. Changing the ROI grid instead requires
        re-running the analysis, so it is deliberately not connected here."""
        self.mag = float(self.mag_edit.value())
        self.pixel_pitch_micron = float(self.pixel_pitch_edit.value())
        self.z_step_micron = float(self.z_step_edit.value())
        if self.tables:
            self.update_plots()

    # ---------- Channel table ----------

    def open_files(self):
        fnames, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Add TIF z-stacks", self.load_folder or "",
            "TIF files (*.tif *.tiff);;All files (*)"
        )
        if fnames:
            self.add_files(fnames)

    def add_files(self, filenames, labels=None, wavelengths=None):
        """Append one channel row per file, with the label prefilled from the basename
        unless *labels* / *wavelengths* supply them (one entry per file, in order)."""
        if labels is not None and len(labels) != len(filenames):
            print(f"Ignoring --labels: got {len(labels)} for {len(filenames)} file(s)")
            labels = None
        if wavelengths is not None and len(wavelengths) != len(filenames):
            print(f"Ignoring --wavelengths: got {len(wavelengths)} for {len(filenames)} file(s)")
            wavelengths = None

        self.channel_table.blockSignals(True)
        for i_file, path in enumerate(filenames):
            row = self.channel_table.rowCount()
            self.channel_table.insertRow(row)

            file_item = QtWidgets.QTableWidgetItem(path)
            file_item.setFlags(file_item.flags() & ~QtCore.Qt.ItemIsEditable)
            file_item.setToolTip(path)
            self.channel_table.setItem(row, COL_FILE, file_item)

            label = (labels[i_file] if labels is not None
                     else os.path.splitext(os.path.basename(path))[0])
            wavelength = f"{wavelengths[i_file]:g}" if wavelengths is not None else ""
            self.channel_table.setItem(row, COL_LABEL, QtWidgets.QTableWidgetItem(label))
            self.channel_table.setItem(row, COL_WAVELENGTH, QtWidgets.QTableWidgetItem(wavelength))

            self.load_folder = os.path.dirname(os.path.abspath(path))
        self.channel_table.blockSignals(False)

        self.info_label.setText(f"{self.channel_table.rowCount()} channel(s) added, not analyzed yet")
        self.update_reference_combo()

    def remove_selected_channels(self):
        for row in sorted({index.row() for index in self.channel_table.selectedIndexes()}, reverse=True):
            self.channel_table.removeRow(row)
        self.update_reference_combo()

    def channel_rows(self):
        """Current channel table contents as a list of (path, label, wavelength_nm) tuples.
        `wavelength_nm` is None when the cell is empty or not a number."""
        rows = []
        for row in range(self.channel_table.rowCount()):
            path = self.channel_table.item(row, COL_FILE).text()
            label_item = self.channel_table.item(row, COL_LABEL)
            label = label_item.text().strip() if label_item else ""
            if not label:
                label = os.path.splitext(os.path.basename(path))[0]
            wl_item = self.channel_table.item(row, COL_WAVELENGTH)
            try:
                wavelength = float(wl_item.text()) if wl_item and wl_item.text().strip() else None
            except ValueError:
                wavelength = None
            rows.append((path, label, wavelength))
        return rows

    def update_reference_combo(self):
        """Keep the reference/display channel combos in sync with the channel table.
        Each entry shows the current label but carries the file path as its data, so a
        renamed channel keeps both its selection and its already-computed results."""
        rows = self.channel_rows()
        for combo in (self.reference_combo, self.channel_combo):
            previous_path = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for path, label, _ in rows:
                combo.addItem(label, path)
            index = combo.findData(previous_path)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def on_channel_table_edited(self, item):
        """A Label or Wavelength edit only changes how results are presented, so refresh
        the combos and redraw - never re-run the analysis."""
        self.update_reference_combo()
        if self.tables:
            self.update_plots()

    def label_for(self, path):
        """Current display label of a channel, as typed in the table."""
        for row_path, label, _ in self.channel_rows():
            if row_path == path:
                return label
        return os.path.splitext(os.path.basename(path))[0]

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(url.toLocalFile().lower().endswith((".tif", ".tiff")) for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.toLocalFile().lower().endswith((".tif", ".tiff"))]
        if paths:
            self.add_files(paths)

    # ---------- Analysis ----------

    def run_analysis(self):
        rows = self.channel_rows()
        if not rows:
            QtWidgets.QMessageBox.warning(self, "Warning", "Add at least one TIF z-stack first.")
            return

        n_rois_x, n_rois_y = int(self.n_rois_x_edit.value()), int(self.n_rois_y_edit.value())
        self.tables, self.z_profiles, self.metrics = {}, {}, {}
        saturated = []

        # The analysis runs on the GUI thread, as in psf_gui_qt.py: this tool runs in its
        # own process, so a long run cannot block mesoSPIM_control itself.
        progress = QtWidgets.QProgressDialog("Computing contrast tables...", "Cancel", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setMinimumDuration(0)

        try:
            for i_channel, (path, _, _) in enumerate(rows):
                progress.setLabelText(f"[{i_channel + 1}/{len(rows)}] {os.path.basename(path)}")

                def report(iz, n_z, i_channel=i_channel):
                    overall = 100.0 * (i_channel + (iz + 1) / n_z) / len(rows)
                    progress.setValue(int(overall))
                    QtWidgets.QApplication.processEvents()
                    return not progress.wasCanceled()

                table, n_saturated = contrast_table_from_stack(path, n_rois_y, n_rois_x, report)
                if n_saturated:
                    saturated.append(f"{os.path.basename(path)}: {n_saturated} plane(s)")

                # Keyed by path, not label, so the Label column stays editable after a run.
                self.tables[path] = table
                self.z_profiles[path] = z_profile_from_table(table, self.z_step_micron)
                self.fov_x_mm, self.fov_y_mm = self._fov_mm(path)
                self.metrics[path] = summary_metrics(table, self.z_step_micron,
                                                     self.fov_x_mm, self.fov_y_mm)
        except KeyboardInterrupt:
            self.tables, self.z_profiles, self.metrics = {}, {}, {}
            self.info_label.setText("Analysis cancelled")
            self.clear_plots()
            return
        except Exception as e:
            self.tables, self.z_profiles, self.metrics = {}, {}, {}
            progress.close()
            QtWidgets.QMessageBox.critical(self, "Error", f"Analysis failed:\n{e}")
            self.clear_plots()
            return
        finally:
            progress.close()

        if saturated:
            QtWidgets.QMessageBox.warning(
                self, "Saturation warning",
                "Saturated pixels found - the contrast of these planes is underestimated:\n"
                + "\n".join(saturated)
            )

        self.info_label.setText(
            f"{len(self.tables)} channel(s) analyzed, "
            f"FOV(X) x FOV(Y) = {self.fov_x_mm:.2f} x {self.fov_y_mm:.2f} mm"
        )
        if self.fov_x_mm > self.fov_y_mm:
            # Y (rows) is the long axis on the usual mesoSPIM frame. A landscape stack is
            # not an error - it just means these plots have the short axis vertical - but
            # it is worth saying so, since a rotated save looks exactly like this.
            self.info_label.setText(
                self.info_label.text() + "  [landscape frame: X is the long axis]")
        self.update_plots()

    def _fov_mm(self, path):
        """Field of view (X, Y) in mm, from the frame shape of *path*, the magnification
        and the camera pixel pitch. Y is array axis 1 (rows), X is array axis 2 (columns)."""
        with TiffFile(path) as tif_file:
            self.frame_shape = tif_file.pages[0].shape
        pixel_size_mm = self.pixel_pitch_micron / self.mag / 1000.0
        return self.frame_shape[1] * pixel_size_mm, self.frame_shape[0] * pixel_size_mm

    def _detrended_profiles(self, path):
        """Central X and Y sections of a channel's z-profile, in microns, with the tilt of
        the reference channel subtracted when 'Subtract tilt' is on."""
        z_profile = self.z_profiles[path]
        n_y, n_x = z_profile.shape
        profile_y = z_profile[:, n_x // 2]   # varies along axis 1 = Y
        profile_x = z_profile[n_y // 2, :]   # varies along axis 2 = X

        if self.detrend_checkbox.isChecked():
            reference = self.reference_combo.currentData()
            if reference in self.z_profiles:
                reference_profile = self.z_profiles[reference]
                profile_y = profile_y - linear_trend(reference_profile[:, n_x // 2])
                profile_x = profile_x - linear_trend(reference_profile[n_y // 2, :])
        return profile_x, profile_y

    # ---------- Plotting ----------

    def clear_plots(self):
        for canvas in (self.maps_canvas, self.summary_canvas):
            canvas.fig.clear()
            canvas.draw()

    def update_plots(self):
        if not self.tables:
            return
        path = self.channel_combo.currentData()
        if path not in self.tables:
            return

        self.maps_canvas.fig.clear()
        self._populate_maps_figure(self.maps_canvas.fig, path)
        self.maps_canvas.draw()

        self.summary_canvas.fig.clear()
        self._populate_summary_figure(self.summary_canvas.fig, path)
        self.summary_canvas.draw()

    def _populate_maps_figure(self, fig, path, fontsize=14):
        """4-panel contrast map of one channel: max contrast along Z, the highest-contrast
        plane, and the two axial sections through the center of the FOV."""
        table = self.tables[path]
        n_z = table.shape[0]
        fov_x, fov_y = self.fov_x_mm, self.fov_y_mm
        z_max_um = self.z_step_micron * (n_z - 1)
        cmin, cmax = float(self.contrast_min_edit.value()), float(self.contrast_max_edit.value())
        cmap = self.cmap_combo.currentText()
        z_best = self.metrics[path]['z_best_index']
        n_y, n_x = table.shape[1], table.shape[2]

        # Constrained layout, because the colorbar is shared by all four panels and
        # tight_layout cannot handle that.
        fig.set_layout_engine('constrained')
        fig.suptitle(f"Contrast maps: {self.label_for(path)}", fontsize=fontsize + 2)
        imshow_kw = dict(vmin=cmin, vmax=cmax, cmap=cmap, interpolation='bicubic', origin='lower')

        # Table rows are Y and columns are X. Rows are drawn reversed so the picture
        # matches ImageJ (array row 0 on top) while FOV_Y still increases upward from the
        # bottom edge of the frame.
        ax0 = fig.add_subplot(1, 4, 1)
        ax0.imshow(table.max(axis=0)[::-1], extent=[0, fov_x, 0, fov_y], aspect='equal', **imshow_kw)
        ax0.set_title("Max. contrast along Z", fontsize=fontsize)

        ax1 = fig.add_subplot(1, 4, 2)
        ax1.imshow(table[z_best][::-1], extent=[0, fov_x, 0, fov_y], aspect='equal', **imshow_kw)
        ax1.set_title("Highest-contrast plane", fontsize=fontsize)
        ax1.axhline(fov_y / 2, c="gray", linewidth=1)
        ax1.axvline(fov_x / 2, c="gray", linewidth=1)

        for ax in (ax0, ax1):
            ax.set_xlabel("FOV(X), mm", fontsize=fontsize)
            ax.set_ylabel("FOV(Y), mm", fontsize=fontsize)

        ax2 = fig.add_subplot(1, 4, 3)
        image = ax2.imshow(table[:, ::-1, n_x // 2].T, extent=[0, z_max_um, 0, fov_y],
                           aspect='auto', **imshow_kw)
        ax2.set_title("Contrast across FOV(Y)", fontsize=fontsize)
        ax2.set_xlabel("Z position, µm", fontsize=fontsize)
        ax2.set_ylabel("FOV(Y), mm", fontsize=fontsize)
        ax2.grid(True)

        ax3 = fig.add_subplot(1, 4, 4)
        ax3.imshow(table[:, n_y // 2, :], extent=[0, fov_x, 0, z_max_um],
                   aspect='auto', **imshow_kw)
        ax3.set_title("Contrast across FOV(X)", fontsize=fontsize)
        ax3.set_xlabel("FOV(X), mm", fontsize=fontsize)
        ax3.set_ylabel("Z position, µm", fontsize=fontsize)
        ax3.grid(True)

        fig.colorbar(image, ax=[ax0, ax1, ax2, ax3], orientation='horizontal',
                     fraction=0.05, pad=0.12, label="Contrast")

    def _populate_summary_figure(self, fig, selected_path, fontsize=13):
        """Field curvature across X and Y for all channels, the axial chromatic shift vs
        wavelength (skipped for a single channel or when no wavelengths are given), and a
        text summary of the selected channel."""
        rows = self.channel_rows()
        wavelengths = {path: wl for path, _, wl in rows if wl is not None and path in self.tables}
        show_chromatic = len(self.tables) > 1 and len(wavelengths) > 1
        n_panels = 4 if show_chromatic else 3

        fov_x, fov_y = self.fov_x_mm, self.fov_y_mm
        any_path = next(iter(self.tables))
        n_y, n_x = self.z_profiles[any_path].shape
        x_range = np.linspace(0, fov_x, n_x)
        y_range = np.linspace(0, fov_y, n_y)

        detrended = " (tilt subtracted)" if self.detrend_checkbox.isChecked() else ""
        fig.set_layout_engine('constrained')
        fig.suptitle(f"Field curvature{detrended}", fontsize=fontsize + 3)

        ax0 = fig.add_subplot(1, n_panels, 1)
        ax1 = fig.add_subplot(1, n_panels, 2)
        ax2 = fig.add_subplot(1, n_panels, 3) if show_chromatic else None

        axial_positions = {}
        for i_channel, (path, label, wavelength) in enumerate(rows):
            if path not in self.z_profiles:
                continue
            color = wavelength_to_rgb(wavelength) if wavelength is not None else f"C{i_channel}"
            marker = MARKERS[i_channel % len(MARKERS)]
            profile_x, profile_y = self._detrended_profiles(path)
            plot_kw = dict(label=label, color=color, lw=2, marker=marker, ms=6)

            ax0.plot(profile_y[::-1], y_range, **plot_kw)  # row 0 at the top, as in ImageJ
            ax1.plot(x_range, profile_x, **plot_kw)
            axial_positions[path] = profile_x[len(profile_x) // 2]

        ax0.set_ylim([0, fov_y])
        ax0.set_ylabel('FOV(Y), mm', fontsize=fontsize)
        ax0.set_xlabel('Field curvature, µm', fontsize=fontsize)
        ax0.set_title("Curvature across FOV(Y)", fontsize=fontsize)

        ax1.set_xlim([0, fov_x])
        ax1.set_xlabel('FOV(X), mm', fontsize=fontsize)
        ax1.set_ylabel('Field curvature, µm', fontsize=fontsize)
        ax1.set_title("Curvature across FOV(X)", fontsize=fontsize)

        for ax in (ax0, ax1):
            ax.tick_params(axis='both', which='major', labelsize=fontsize - 2)
            ax.legend(loc='best', fontsize=fontsize - 3)
            ax.grid(True)

        if show_chromatic:
            # Chromatic shift is relative to the shortest-wavelength channel.
            reference_path = min(wavelengths, key=wavelengths.get)
            offset = axial_positions[reference_path]
            for i_channel, (path, label, wavelength) in enumerate(rows):
                if path not in wavelengths:
                    continue
                ax2.plot(wavelength, axial_positions[path] - offset, label=label,
                         color=wavelength_to_rgb(wavelength), lw=2,
                         marker=MARKERS[i_channel % len(MARKERS)], ms=8, ls='none')
            ax2.tick_params(axis='both', which='major', labelsize=fontsize - 2)
            ax2.set_xlabel('Wavelength, nm', fontsize=fontsize)
            ax2.set_ylabel('Chromatic shift (axial), µm', fontsize=fontsize)
            ax2.set_title(f"Axial shift vs {self.label_for(reference_path)}", fontsize=fontsize)
            ax2.legend(loc='best', fontsize=fontsize - 3)
            ax2.grid(True)

        ax_text = fig.add_subplot(1, n_panels, n_panels)
        ax_text.axis('off')
        ax_text.set_title(f"Summary: {self.label_for(selected_path)}", fontsize=fontsize)
        metrics = self.metrics[selected_path]
        lines = [
            f"Frame: {self.frame_shape[1]} (X, axis 2) x {self.frame_shape[0]} (Y, axis 1) px",
            f"FOV(X), FOV(Y): {fov_x:.2f}, {fov_y:.2f} mm",
            f"ROI grid (X, Y): {n_x} x {n_y}",
            f"Z-step: {self.z_step_micron:g} µm",
            "",
            f"DOF (FWHM): {metrics['dof_um']:.0f} µm",
            f"Sag across FOV, average: {metrics['ave_sag_um']:.0f} µm",
            f"Sag across FOV(X): {metrics['sag_x_um']:.0f} µm",
            f"Sag across FOV(Y): {metrics['sag_y_um']:.0f} µm",
            "",
            f"Max contrast: {metrics['max_contrast']:.2f}",
            f"Mean contrast, best plane: {metrics['mean_contrast_best_plane']:.2f}",
        ]
        for i_line, line in enumerate(lines):
            ax_text.text(0.0, 0.92 - 0.07 * i_line, line, fontsize=fontsize - 1,
                         transform=ax_text.transAxes)

    def save_png_figure(self):
        """Save the figure of the currently visible tab as a single PNG at 300 DPI."""
        if not self.tables:
            QtWidgets.QMessageBox.warning(self, "Warning", "No plots to save yet.")
            return

        path = self.channel_combo.currentData()
        label = self.label_for(path)
        is_maps_tab = self.tabs.currentIndex() == 0
        default_name = (f"contrast-maps({label}).png" if is_maps_tab
                        else f"field-curvature-summary({label}).png")
        default_path = os.path.join(self.load_folder, default_name) if self.load_folder else default_name

        fname, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save current tab as PNG (300 DPI)", default_path, "PNG images (*.png)")
        if not fname:
            return
        if not fname.lower().endswith(".png"):
            fname += ".png"

        EXPORT_W_IN, EXPORT_H_IN = 20.0, 6.0  # fixed export dimensions (inches @ 300 DPI)
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            export_fig = plt.Figure(figsize=(EXPORT_W_IN, EXPORT_H_IN), dpi=300)
            FigureCanvasAgg(export_fig)  # attach non-interactive Agg backend for rendering
            if is_maps_tab:
                self._populate_maps_figure(export_fig, path, fontsize=18)
            else:
                self._populate_summary_figure(export_fig, path, fontsize=16)
            export_fig.savefig(fname, dpi=300, format="png")
            plt.close(export_fig)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save PNG:\n{e}")


def main():
    """Standalone entry point. Also used by mesoSPIM_control, which launches this script
    as a separate process (via subprocess.Popen) rather than embedding it in its own
    process, so a long-running analysis can't block the main GUI."""
    import argparse

    parser = argparse.ArgumentParser(description="Field curvature & chromatic shift analysis tool")
    parser.add_argument("tiff_paths", nargs="*", default=None,
                        help="TIF z-stack(s) to add to the channel table on startup")
    parser.add_argument("--mag", type=float, default=None, help="System magnification")
    parser.add_argument("--pixel-pitch", type=float, default=None, dest="pixel_pitch",
                        help="Camera pixel pitch in microns")
    parser.add_argument("--z-step", type=float, default=None, dest="z_step",
                        help="Distance between z-planes in microns")
    parser.add_argument("--labels", nargs="*", default=None,
                        help="Channel label per TIFF, in the same order")
    parser.add_argument("--wavelengths", nargs="*", type=float, default=None,
                        help="Wavelength in nm per TIFF, in the same order")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = FieldCurvatureMainWindow(mag=args.mag, pixel_pitch_micron=args.pixel_pitch,
                                  z_step_micron=args.z_step, filenames=args.tiff_paths,
                                  labels=args.labels, wavelengths=args.wavelengths)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
