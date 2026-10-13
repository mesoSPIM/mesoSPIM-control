"""
The Data viewer: one window for looking at data, in the View menu.

* **Open Data Viewer** opens the window, or brings it to the front. It watches the
  folder the acquisition list saves into: the newest acquisition is shown, and one
  that starts is shown in its place, plane by plane as the camera delivers it.
* **Open Dataset in Data Viewer...** asks for a dataset on disk and shows it in the
  same window, beside whatever is there.

The window itself is the ``mesospim_viewer`` package beside this module, a
neuroglancer page driven from Python. From disk it reads OME-Zarr, as the
``MP_OME_Zarr_TCZYX_Writer`` (one (t, c, z, y, x) store per tile) and the other
OME-Zarr writers save it. The stack that is being acquired is shown from the
camera's frames, whatever format the run is saved in.

This module is all mesoSPIM-control holds of it: two lines in mesoSPIM_Control.py
call ``prepare_qt`` before the QApplication exists, the two menu actions call
``open_window`` and ``open_acquired_dataset``, and ``Feed`` listens to four signals
the Core and the camera already emit. Nothing in the acquisition waits for the
viewer: a frame is handed over as a thinned-out copy and the rest happens in the
viewer's own threads. PyQtWebEngine is installed with mesoSPIM-control; if it is
missing all the same, the menu entries say how to get it instead of failing.
"""
import logging
import os
import re
from pathlib import Path

from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)

INSTALL_HINT = (
    "The Data viewer needs PyQtWebEngine, the web view for PyQt5. Install it into the\n"
    "mesoSPIM Python environment and restart mesoSPIM:\n"
    "    pip install PyQtWebEngine==5.15.7"
)

# The time index mesoSPIM writes into file names while running a time lapse
# (see mesoSPIM_AcquisitionManagerWindow.append_time_index_to_filenames).
_TIME_SUFFIX = re.compile(r'_Time(\d+)')


def prepare_qt() -> None:
    """Import Qt WebEngine before the first QApplication exists.

    Qt allows the module only then, and wants the shared-OpenGL-context attribute set
    first. Nothing happens, and nothing complains, when PyQtWebEngine is not installed:
    the viewer is optional.
    """
    try:
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)
        from PyQt5 import QtWebEngineWidgets  # noqa: F401
    except ImportError:
        logger.debug("PyQtWebEngine is not installed; the Data viewer will not be available")


def acquisition_folder(main_window) -> str | None:
    """The folder the acquisition list saves into, or None if there is no list yet."""
    try:
        acq_list = main_window.state['acq_list']
        if len(acq_list) > 0 and acq_list[0]['folder']:
            return acq_list[0]['folder']
    except Exception:
        pass
    return None


def _window_class(main_window):
    """The viewer's window class, or None after telling the operator what is missing."""
    # The web view is looked for only when the window class is built, so both steps sit
    # inside the same guard: a missing PyQtWebEngine then shows the hint, not a traceback.
    try:
        from mesoSPIM.src.mesospim_viewer.window import make_window_class
        return make_window_class()
    except ImportError as error:
        main_window.display_warning(f"{INSTALL_HINT}\n\n({error})")
        return None


def open_window(main_window):
    """Open the Data viewer, or bring the one already open to the front."""
    window = getattr(main_window, 'data_viewer_window', None)
    if window is not None and window.isVisible():
        window.watch(acquisition_folder(main_window))  # the list may save somewhere else by now
        window.raise_()
        window.activateWindow()
        return window
    # A closed window has stopped its viewer, so a fresh one is made instead of reusing it.
    window_class = _window_class(main_window)
    if window_class is None:
        return None
    window = window_class(acquisition_folder(main_window))
    window.resize(1280, 820)
    window.show()
    main_window.data_viewer_window = window
    feed = getattr(main_window, 'data_viewer_feed', None)
    if feed is None:
        try:
            main_window.data_viewer_feed = Feed(main_window)
        except Exception:
            # Without the feed the window still follows the acquisition from disk.
            logger.exception('The Data viewer could not be connected to the camera')
    return window


def close_window(main_window):
    """Close the Data viewer with mesoSPIM: a window of its own, left open it would keep
    the program running after File > Exit has closed every other window."""
    window = getattr(main_window, 'data_viewer_window', None)
    if window is not None:
        window.close()


def open_acquired_dataset(main_window, path: str | None = None):
    """Ask for a dataset on disk and show it in the Data viewer, beside what it shows.

    The dataset can be one ``.ome.zarr`` tile, one ``.ome.zarr`` acquisition holding
    tiles, or a data folder holding acquisitions (each is listed, the newest is shown).
    If the folder holds none of these, the viewer says so on its picture. Returns the
    window, or None.
    """
    if path is None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            main_window, 'Open a dataset (a .ome.zarr folder)', acquisition_folder(main_window) or ''
        )
        if not path:
            return None
    window = open_window(main_window)
    if window is not None:
        window.open(path)
    return window


def time_point_of(filename: str) -> int:
    """The time point a file name of a time lapse names ('Sample.ome_Time003.zarr' -> 3), else 0."""
    found = _TIME_SUFFIX.findall(Path(filename).name)
    return int(found[-1]) if found else 0


def plain_name(filename: str) -> str:
    """A file name without its time index and its ending: 'Sample.ome_Time003.zarr' -> 'Sample'."""
    name = _TIME_SUFFIX.sub('', Path(filename).name)
    for suffix in ('.ome.zarr', '.zarr', '.ome.tif', '.ome.tiff', '.tiff', '.tif', '.btf', '.h5', '.raw'):
        if name.endswith(suffix):
            return name[:-len(suffix)]
    return name


def describe_stack(core, acq, acq_list, frame_shape):
    """What the viewer needs to know about the stack that is starting, from what
    mesoSPIM-control knows about it: a ``mesospim_viewer.Stack``.

    Sizes and positions are the ones the image writers save (the pixel size of the
    zoom, the z step, the stage position), so the preview sits exactly where the tile
    on disk will.
    """
    from mesoSPIM.src.mesospim_viewer import Stack

    def label(laser: str) -> str:
        return laser[:-3] if laser.endswith(' nm') else laser

    lasers = [label(laser) for laser in acq_list.get_unique_attr_list('laser')]
    pixel = float(core.cfg.pixelsize[acq['zoom']])
    writer = getattr(getattr(core, 'image_writer', None), 'writer', None)
    # Where the stack is saved, when that is an OME-Zarr store the viewer reads: the
    # OME-Zarr writers name the tile's store, and the one-store-per-tile writer the
    # acquisition's folder as well (without the time index of a time lapse).
    store = getattr(writer, 'current_acquire_file_path', None)
    store = Path(store) if store and str(store).endswith('.ome.zarr') else None
    # A writer that keeps every time point of a tile in one store says where the run
    # as a whole is saved; with the others each time point is a dataset of its own.
    shared = getattr(writer, 'acquisition_path', None) if store is not None else None
    folder = Path(shared) if shared else (store.parent if store is not None else None)
    if store is not None:
        name = plain_name(acq['filename'])
    else:
        # A format with one file per stack: the run is named by what its files'
        # names have in common, so its stacks are shown together as one acquisition.
        names = [plain_name(row['filename']) for row in acq_list]
        name = os.path.commonprefix(names)
        if any(len(other) > len(name) and other[len(name)] not in ' _-.' for other in names):
            # Cut in the middle of a word ("brain_Mag2x_Tile" of "..._Tile0"): the
            # words the names share in full are the name.
            name = name[: max(name.rfind(mark) for mark in ' _-.') + 1]
        name = name.rstrip(' _-.')
        if len(name) < 3:
            name = Path(str(acq['folder']).rstrip('/\\')).name or 'Acquisition'
    tile = acq_list.get_tile_index(acq)
    return Stack(
        acquisition=name,
        channel=label(acq['laser']),
        channels=tuple(lasers),
        planes=int(acq.get_image_count()),
        frame=(int(frame_shape[0]), int(frame_shape[1])),
        voxel_um=(float(acq['z_step']), pixel, pixel),
        origin_um=(float(acq['z_start']), float(acq['y_pos']), float(acq['x_pos'])),
        time_point=time_point_of(acq['filename']) if (shared or store is None) else 0,
        tile=f'Tile {tile + 1}',
        tiles=int(acq_list.get_n_tiles()),
        folder=folder,
        store=store,
    )


class Feed(QtCore.QObject):
    """Hands the camera's frames to the Data viewer while a stack is acquired.

    Four signals mesoSPIM-control already has are listened to, all in the GUI thread:

    * ``Core.sig_prepare_image_series``: a stack is about to start;
    * ``Camera.sig_camera_frame``: a frame is ready for display. It is the same frame
      the camera window shows (``frame_queue_display``), in the orientation the
      writers save;
    * ``Core.sig_end_image_series``: the stack is acquired;
    * ``Core.sig_finished``: the whole run is over (in a time lapse, a time point).

    With no Data viewer window open, each of them returns at once.
    """

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.core = main_window.core
        self.pending = None  # (acq, acq_list) of a stack that was announced; described at its first frame
        self.running = False
        self.core.sig_prepare_image_series.connect(self.on_prepare, type=QtCore.Qt.QueuedConnection)
        self.core.camera_worker.sig_camera_frame.connect(self.on_frame, type=QtCore.Qt.QueuedConnection)
        self.core.sig_end_image_series.connect(self.on_end, type=QtCore.Qt.QueuedConnection)
        self.core.sig_finished.connect(self.on_finished, type=QtCore.Qt.QueuedConnection)
        # Heard in the order the Core says them: a time point, then its end.
        self.time_point = None
        self.core.sig_run_timepoint.connect(self.on_time_point, type=QtCore.Qt.QueuedConnection)

    def window(self):
        window = getattr(self.main_window, 'data_viewer_window', None)
        return window if window is not None and window.isVisible() else None

    def on_prepare(self, acq, acq_list) -> None:
        self.pending = (acq, acq_list)
        self.running = False

    def on_frame(self) -> None:
        if self.pending is None and not self.running:
            return  # live mode or a snap: not a stack
        window = self.window()
        frames = self.core.frame_queue_display
        if window is None or not frames:
            return
        try:
            frame = frames[0]
            if self.pending is not None:
                # Described now, at the first frame: by then the writer has opened its
                # file, and the frame says what size the stack is saved in.
                acq, acq_list = self.pending
                self.pending = None
                window.watch(acq['folder'])
                window.begin_stack(describe_stack(self.core, acq, acq_list, frame.shape))
                self.running = True
            # The camera counts on while the frame waits to be shown, so the plane is
            # the newest one the camera has, give or take a frame: near enough for a
            # preview, and the tile on disk takes its place once it is whole.
            index = max(0, int(getattr(self.core.camera_worker, 'cur_image', 1)) - 1)
            window.add_plane(index, frame)
        except Exception:
            # The viewer must never take the acquisition down with it.
            logger.exception('The Data viewer could not take in a frame')
            self.pending = None
            self.running = False

    def on_end(self, acq, acq_list) -> None:
        self.pending = None
        if not self.running:
            return
        self.running = False
        window = self.window()
        if window is not None:
            window.end_stack()

    def on_time_point(self, time_point: int) -> None:
        self.time_point = int(time_point)

    def on_finished(self) -> None:
        self.pending = None
        self.running = False
        window = self.window()
        if window is None:
            return
        # In a time lapse the Core says "finished" after every time point; the run
        # is over only after the last. Which one has just finished is what the Core
        # last announced (on_time_point): its own counter may have moved on already
        # by the time this is heard, when the time points follow without a pause.
        core = self.core
        at, self.time_point = self.time_point, None
        more = (
            at is not None
            and getattr(core, 'timelapse_active', False)
            and at + 1 < getattr(core, 'timelapse_tpoints', 0)
        )
        if more:
            window.end_stack()
        else:
            window.end_run()
