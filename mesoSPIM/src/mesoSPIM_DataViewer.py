"""
The Data viewer, in two forms, both in the View menu.

* **Open Live Data Viewer** shows the acquisition being written, as it lands. It watches
  the folder the acquisition list saves into -- the newest ``.ome.zarr`` acquisition in
  it by default, with a dropdown for earlier ones.
* **Open Acquired Dataset...** asks for a dataset on disk and shows it as it is, without
  following anything. Several can be open at once, each in its own window.

The windows themselves are the ``mesospim_viewer`` package beside this module, a
neuroglancer page driven from Python. It reads the stores the ``MP_OME_Zarr_TCZYX_Writer``
writes: one (t, c, z, y, x) store per tile.

This module is all mesoSPIM-control holds of it: two lines in mesoSPIM_Control.py call
``prepare_qt`` before the QApplication exists, and the two menu actions call
``open_window`` and ``open_acquired_dataset``. PyQtWebEngine is installed with
mesoSPIM-control; if it is missing all the same, the menu entries say how to get it
instead of failing.
"""
import logging

from PyQt5 import QtCore, QtWidgets

logger = logging.getLogger(__name__)

INSTALL_HINT = (
    "The Data viewer needs PyQtWebEngine, the web view for PyQt5. Install it into the\n"
    "mesoSPIM Python environment and restart mesoSPIM:\n"
    "    pip install PyQtWebEngine==5.15.7"
)


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
    """Open the live data viewer, or bring the one already open to the front."""
    window = getattr(main_window, 'data_viewer_window', None)
    if window is not None and window.isVisible():
        window.raise_()
        window.activateWindow()
        return window
    # A closed window has stopped its viewer, so a fresh one is made instead of reusing it.
    window_class = _window_class(main_window)
    if window_class is None:
        return None
    folder = acquisition_folder(main_window)
    if folder is None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(main_window, 'Folder with acquisitions')
        if not folder:
            return None
    window = window_class(folder, live=True)
    window.resize(1200, 800)
    window.show()
    main_window.data_viewer_window = window
    return window


def open_acquired_dataset(main_window, path: str | None = None):
    """Ask for a dataset on disk and show it in a window of its own.

    The dataset can be one ``.ome.zarr`` tile, one ``.ome.zarr`` acquisition holding
    tiles, or a data folder holding acquisitions (a dropdown then switches between
    them). If the folder holds none of these, the operator is told so and no window
    opens. Returns the new window, or None.
    """
    window_class = _window_class(main_window)
    if window_class is None:
        return None
    if path is None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            main_window, 'Acquired dataset (a .ome.zarr folder)', acquisition_folder(main_window) or ''
        )
        if not path:
            return None
    from mesoSPIM.src.mesospim_viewer.omezarr import NotAStore
    try:
        window = window_class(path, live=False)
    except NotAStore as error:
        main_window.display_warning(str(error))
        return None
    window.resize(1200, 800)
    window.show()
    # Kept here so the windows stay open; closed ones are let go the next time.
    kept = [w for w in getattr(main_window, 'acquired_dataset_windows', []) if w.isVisible()]
    main_window.acquired_dataset_windows = kept + [window]
    return window
