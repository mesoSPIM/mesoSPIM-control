"""
The Data viewer: the acquisition being written, shown as it lands (View > Open Data Viewer).

The window itself is the ``mesospim_viewer`` package beside this module, a neuroglancer
page driven from Python. It watches the folder
the acquisition list saves into -- the newest ``.ome.zarr`` acquisition in it by default,
with a dropdown for earlier ones -- and reads the stores the ``MP_OME_Zarr_TCZYX_Writer``
writes: one (t, c, z, y, x) store per tile.

This module is all mesoSPIM-control holds of it: two lines in mesoSPIM_Control.py call
``prepare_qt`` before the QApplication exists, and the main window's menu action calls
``open_window``. PyQtWebEngine is installed with mesoSPIM-control; if it is missing all the
same, the menu entry says how to get it instead of failing.
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


def open_window(main_window):
    """Open the Data viewer window, or bring the one already open to the front."""
    window = getattr(main_window, 'data_viewer_window', None)
    if window is not None:
        window.show()
        window.raise_()
        return window
    # The web view is looked for only when the window class is built, so both steps sit
    # inside the same guard: a missing PyQtWebEngine then shows the hint, not a traceback.
    try:
        from mesoSPIM.src.mesospim_viewer.window import make_window_class
        window_class = make_window_class()
    except ImportError as error:
        main_window.display_warning(f"{INSTALL_HINT}\n\n({error})")
        return None
    folder = acquisition_folder(main_window)
    if folder is None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(main_window, 'Folder with acquisitions')
        if not folder:
            return None
    window = window_class(folder)
    window.resize(1200, 800)
    window.show()
    main_window.data_viewer_window = window
    return window
