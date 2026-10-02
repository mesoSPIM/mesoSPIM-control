"""The Data viewer window, in its two forms.

    python -m mesoSPIM.src.mesospim_viewer.window /path/to/data            # live
    python -m mesoSPIM.src.mesospim_viewer.window --acquired /path/to/dataset

**The live data viewer** shows the acquisition being written. It is given the
data folder, and follows the newest acquisition in it automatically -- a new one
appearing while the window is open is switched to, and every tile or time point
that lands in it is shown within a second -- unless an older one was picked from
the dropdown at the top of the viewer's own panel, which stays until the current
one is picked again. The following itself is
:class:`~mesoSPIM.src.mesospim_viewer.watch.Follower`; this file only gives it a
window and a timer.

**An acquired dataset** is shown as it is on disk, with no timer and nothing
followed: see :class:`~mesoSPIM.src.mesospim_viewer.watch.Opened` for what can
be opened. More datasets can be dragged onto this window from the file manager,
one or several folders at once: each is shown beside what is there, and each
acquisition's block in the panel has a button that takes it off the view again.
The live window takes no drops, so what it shows is always the microscope's.

The window title says which of the two a window is, so the two are never confused.

Written against the Qt binding mesoSPIM-control uses (PyQt5), through the same
small helper the plain widget uses, so PyQt6 and PySide work as well.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .omezarr import NotAStore
from .viewer import Viewer, _qt
from .watch import Follower, Opened

POLL_MS = 1000


def make_window_class():
    """The window class, built once Qt is known to be importable."""
    qt = _qt()
    QtCore, QtWidgets = qt.QtCore, qt.QtWidgets
    events = getattr(QtCore.QEvent, "Type", QtCore.QEvent)
    DRAGGING = (events.DragEnter, events.DragMove, events.DragLeave, events.Drop)

    class DataViewerWindow(QtWidgets.QWidget):
        """The viewer over a data folder (live) or over one dataset from disk (acquired).

        With ``live=False``, a folder that cannot be shown raises
        :class:`~mesoSPIM.src.mesospim_viewer.omezarr.NotAStore` before any window appears.
        """

        def __init__(
            self,
            root: str | Path,
            parent=None,
            *,
            viewer: Viewer | None = None,
            live: bool = True,
        ) -> None:
            # The data is looked at before the window exists, so a folder that cannot be
            # shown leaves nothing half-built behind.
            viewer = viewer or Viewer(ui="simple")
            opened: Opened | None = None
            if live:
                follower: Follower | None = Follower(viewer, root)
            else:
                try:
                    opened = Opened(viewer, root)
                except Exception:
                    viewer.stop()
                    raise
                follower = opened.follower
            super().__init__(parent)
            self.live = live
            self._viewer = viewer
            self.follower = follower
            self.opened = opened
            path = Path(root).expanduser()
            if live:
                self.setWindowTitle(f"Live data viewer \u2014 {path}")
                self.setToolTip(f"Following the newest acquisition in {path}")
            else:
                self.setWindowTitle(f"Acquired dataset \u2014 {path.name}")
                self.setToolTip(f"Showing {path} as it is on disk; nothing new is followed")

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            self.web = self.viewer.qt_widget(self)
            layout.addWidget(self.web, 1)
            # In Qt, files dragged onto a web page reach the page without their
            # paths, so drops are taken here, from the web view: its drawing
            # surface passes every drag up to it.
            self.web.installEventFilter(self)

            # Only the live window looks at the disk again; an acquired dataset is read once.
            self.timer = QtCore.QTimer(self)
            if live:
                self.timer.timeout.connect(self.poll)
                self.timer.start(POLL_MS)
                self.poll()

        @property
        def viewer(self) -> Viewer:
            return self._viewer

        def poll(self) -> None:
            if self.live and self.follower is not None:
                self.follower.poll()

        def eventFilter(self, watched, event) -> bool:  # noqa: N802 -- Qt's name
            """Take folders dragged onto the picture, and keep every drag from the page.

            The page never sees a drag: it could do nothing with a folder
            without its path. The live window refuses every drop.
            """
            if watched is not self.web or event.type() not in DRAGGING:
                return super().eventFilter(watched, event)
            if event.type() == events.DragLeave:
                return True
            paths = _local_paths(event.mimeData())
            if self.opened is None or not paths:
                event.ignore()
                return True
            event.acceptProposedAction()
            if event.type() == events.Drop:
                self.drop(paths)
            return True

        def drop(self, paths: list[Path]) -> None:
            """Show each dropped folder beside what is shown.

            A folder that cannot be shown does not stop the others: the picture
            says in a sentence why it was not opened, until the next drop.
            """
            refused = []
            for path in paths:
                try:
                    self.opened.add(path)
                except (NotAStore, OSError) as why:
                    refused.append(refusal(path, why))
            self.viewer.say("\n".join(refused))

        def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
            self.timer.stop()
            self.viewer.stop()
            super().closeEvent(event)

    return DataViewerWindow


def refusal(path: Path, error: Exception) -> str:
    """One short sentence saying why a dropped folder was not shown, naming only the folder.

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The Data viewer window: live over a data folder, or over an acquired dataset."
    )
    parser.add_argument(
        "folder",
        help="the folder the microscope writes acquisitions into, or with --acquired the dataset",
    )
    parser.add_argument(
        "--acquired",
        action="store_true",
        help="show the folder as it is on disk, without following new acquisitions",
    )
    args = parser.parse_args(argv)
    qt = _qt()
    app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication(sys.argv)
    window = make_window_class()(args.folder, live=not args.acquired)
    window.resize(1200, 800)
    window.show()
    return app.exec() if hasattr(app, "exec") else app.exec_()

if __name__ == "__main__":
    raise SystemExit(main())
