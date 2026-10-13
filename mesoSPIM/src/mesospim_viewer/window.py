"""The Data viewer window.

    python -m mesoSPIM.src.mesospim_viewer.window /path/to/data
    python -m mesoSPIM.src.mesospim_viewer.window /path/to/Sample.ome.zarr

One window for looking at data, whether it is being acquired or was acquired
last year. Its panel lists acquisitions; what the window is given decides what
is on the list:

- a **data folder** the microscope writes into is watched: its acquisitions are
  listed, the newest is shown, and one that starts later is shown in its place,
  growing on screen as it is acquired;
- a **dataset** (a tile, an acquisition, or a folder of acquisitions) is opened
  beside whatever is there, through the panel's Open button, by dropping its
  folder onto the window, or from the command line.

Inside mesoSPIM-control the window is also fed the camera's frames
(:meth:`begin_stack`, :meth:`add_plane`, :meth:`end_stack`), so the stack being
acquired is on screen plane by plane, long before it is on disk.

What is shown is decided by :class:`~mesoSPIM.src.mesospim_viewer.watch.Library`;
this file gives it a window, a timer and the two things only Qt can do: ask for a
folder, and take one that is dropped.

Written against the Qt binding mesoSPIM-control uses (PyQt5), through the same
small helper the plain widget uses, so PyQt6 and PySide work as well.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time
from pathlib import Path

from .live import Stack, thin
from .omezarr import NotAStore
from .viewer import Viewer, _qt
from .watch import PLANES_PER_S, Library

logger = logging.getLogger(__name__)

POLL_MS = 1000
# Frames are passed over while this many wait to be taken in.
WAITING_PLANES = 8


def make_window_class():
    """The window class, built once Qt is known to be importable."""
    qt = _qt()
    QtCore, QtWidgets = qt.QtCore, qt.QtWidgets
    events = getattr(QtCore.QEvent, "Type", QtCore.QEvent)
    DRAGGING = (events.DragEnter, events.DragMove, events.DragLeave, events.Drop)
    Signal = getattr(QtCore, "pyqtSignal", None) or QtCore.Signal

    class DataViewerWindow(QtWidgets.QWidget):
        """The viewer, over a data folder that is watched and any datasets opened beside it."""

        # The page asks from one of the server's threads; Qt answers in its own.
        open_requested = Signal()

        def __init__(self, folder: str | Path | None = None, parent=None, *, viewer: Viewer | None = None) -> None:
            super().__init__(parent)
            self._viewer = viewer or Viewer(ui="simple")
            self.library = Library(self._viewer)
            self.setWindowTitle("Data viewer")
            self.setAcceptDrops(True)

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            self.web = self.viewer.qt_widget(self)
            layout.addWidget(self.web, 1)
            # In Qt, files dragged onto a web page reach the page without their
            # paths, so drops are taken here, from the web view: its drawing
            # surface passes every drag up to it.
            self.web.installEventFilter(self)

            self.open_requested.connect(self.ask_and_open)
            self.viewer.on_open(self.open_requested.emit)

            # Everything that touches the disk runs off the GUI thread: the look
            # at the watched folder once a second, and whatever the microscope
            # feeds in. Neither may ever hold up the window, or the acquisition.
            self._closing = False
            self._polling: threading.Thread | None = None
            # Unbounded, so that handing something over never waits: the start and
            # the end of a stack are few, and frames are passed over when the
            # viewer falls behind (see add_plane).
            self._feed: queue.Queue = queue.Queue()
            self._feeder = threading.Thread(target=self._feed_on, name="mesospim-view-feed", daemon=True)
            self._feeder.start()
            self._plane_at = 0.0
            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(POLL_MS)
            if folder is not None:
                self.watch(folder)
            else:
                self.poll()

        @property
        def viewer(self) -> Viewer:
            return self._viewer

        # -- what is shown ---------------------------------------------------------

        def watch(self, folder: str | Path | None) -> None:
            """Follow the folder the microscope writes into (see :meth:`Library.watch`)."""
            self._later(lambda: self.library.watch(folder))

        def open(self, path: str | Path) -> None:
            """Show a dataset from disk beside what is shown.

            One that cannot be shown is said so on the picture, in a sentence.
            """
            self.drop([Path(path)])

        def drop(self, paths: list[Path]) -> None:
            """Show each folder beside what is shown; a folder that cannot be shown does
            not stop the others, and the picture says why it was not opened."""

            def opening() -> None:
                refused = []
                for path in paths:
                    try:
                        self.library.open(path)
                    except (NotAStore, OSError) as why:
                        refused.append(refusal(path, why))
                self.viewer.say("\n".join(refused))

            self._later(opening)

        def ask_and_open(self) -> None:
            """Ask for a dataset on disk, as the panel's Open button does."""
            start = str(self.library.root) if self.library.root is not None else ""
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Open a dataset (a .ome.zarr folder, or a folder of acquisitions)", start
            )
            if path:
                self.open(path)

        # -- the microscope's feed ---------------------------------------------------

        def begin_stack(self, stack: Stack) -> None:
            """The microscope is about to acquire a stack (see :meth:`Library.begin_stack`)."""
            self._plane_at = 0.0
            self._enqueue(("begin", stack))

        def add_plane(self, index: int, frame) -> None:
            """A camera frame of the running stack, as it is written.

            Returns at once: the frame is thinned out here (a copy of every few
            pixels) and everything else happens off the GUI thread. Frames
            arriving faster than the preview takes them are passed over.
            """
            now = time.monotonic()
            if now - self._plane_at < 1.0 / PLANES_PER_S or self._feed.qsize() > WAITING_PLANES:
                return
            self._plane_at = now
            self._enqueue(("plane", index, thin(frame)))

        def end_stack(self) -> None:
            self._enqueue(("end",))

        def end_run(self) -> None:
            """The whole run is over (see :meth:`Library.end_run`)."""
            self._later(self.library.end_run)

        def _enqueue(self, item: tuple) -> None:
            self._feed.put_nowait(item)

        def _later(self, work) -> None:
            self._enqueue(("call", work))

        def _feed_on(self) -> None:
            while True:
                item = self._feed.get()
                if item[0] == "stop":
                    return
                try:
                    if item[0] == "plane":
                        self.library.add_plane(item[1], item[2])
                    elif item[0] == "begin":
                        self.library.begin_stack(item[1])
                    elif item[0] == "end":
                        self.library.end_stack()
                    elif item[0] == "call":
                        item[1]()
                except Exception:  # noqa: BLE001 -- the viewer must never take the acquisition down
                    logger.exception("the Data viewer could not take in %s", item[0])

        # -- the look at the disk ------------------------------------------------------

        def poll(self) -> None:
            """One look at the disk, in the background; a look still going on is left to finish."""
            if self._closing:
                return
            if self._polling is not None and self._polling.is_alive():
                return
            self._polling = threading.Thread(target=self._poll_now, name="mesospim-view-poll", daemon=True)
            self._polling.start()

        def _poll_now(self) -> None:
            try:
                if not self._closing:
                    self.library.poll()
            except Exception:  # noqa: BLE001 -- the next look may well succeed
                logger.exception("looking at the data folder failed")

        # -- Qt's own ---------------------------------------------------------------------

        def eventFilter(self, watched, event) -> bool:  # noqa: N802 -- Qt's name
            """Take folders dragged onto the picture, and keep every drag from the page:
            the page could do nothing with a folder without its path."""
            if watched is not self.web or event.type() not in DRAGGING:
                return super().eventFilter(watched, event)
            if event.type() == events.DragLeave:
                return True
            paths = _local_paths(event.mimeData())
            if not paths:
                event.ignore()
                return True
            event.acceptProposedAction()
            if event.type() == events.Drop:
                self.drop(paths)
            return True

        def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
            self._closing = True
            self.timer.stop()
            # Nothing is waited for long: a look at a slow disk that is still
            # going on finds the library closed and does nothing more.
            self.library.close()
            self._feed.put_nowait(("stop",))
            self._feeder.join(timeout=1.0)
            if self._polling is not None:
                self._polling.join(timeout=1.0)
            self.viewer.stop()
            super().closeEvent(event)

    return DataViewerWindow


def refusal(path: Path, error: Exception) -> str:
    """One short sentence saying why a folder was not shown, naming only the folder.

    A store the viewer recognises but cannot show says why in a few words; for
    anything else it is enough to know that the folder is not one the viewer opens.
    """
    reason = getattr(error, "reason", None)
    if reason:
        return f"{path.name} can't be shown: {reason}."
    return f"{path.name} isn't an OME-Zarr folder the viewer can open."


def _local_paths(mime) -> list[Path]:
    """The files and folders a drag carries from the file manager."""
    if mime is None or not mime.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]


def is_data_folder(path: Path) -> bool:
    """Whether a folder is one acquisitions are written into, rather than a dataset itself."""
    return path.is_dir() and not path.name.endswith(".ome.zarr") and not (
        (path / "zarr.json").is_file() or (path / ".zgroup").is_file() or (path / ".zattrs").is_file()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The Data viewer window: over a data folder that is being acquired into, "
        "or over datasets from disk."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="a folder the microscope writes acquisitions into (it is watched), "
        "or datasets to open: .ome.zarr folders",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the first folder as a dataset even if it looks like a data folder: "
        "its acquisitions are listed, and none that starts later is followed",
    )
    args = parser.parse_args(argv)
    qt = _qt()
    app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication(sys.argv)
    paths = [Path(path).expanduser() for path in args.paths]
    watched = paths[0] if paths and not args.open and is_data_folder(paths[0]) else None
    window = make_window_class()(watched)
    for path in paths:
        if path != watched:
            window.open(path)
    window.resize(1280, 820)
    window.show()
    return app.exec() if hasattr(app, "exec") else app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
