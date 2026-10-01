"""The Data viewer window: the running acquisition on screen as it is written.

    python -m mesoSPIM.src.mesospim_viewer.window /path/to/data

The viewer over a data folder. The newest acquisition is followed
automatically -- a new one appearing while the window is open is switched to,
and every tile or time point that lands in it is shown within a second --
unless an older one was picked from the dropdown at the top of the viewer's
own panel, which stays until the current one is picked again. The following
itself is :class:`~mesoSPIM.src.mesospim_viewer.watch.Follower`; this file only gives it a
window and a timer.

Written against the Qt binding mesoSPIM-control uses (PyQt5), through the same
small helper the plain widget uses, so PyQt6 and PySide work as well.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .viewer import Viewer, _qt
from .watch import Follower

POLL_MS = 1000


def make_window_class():
    """The window class, built once Qt is known to be importable."""
    qt = _qt()
    QtCore, QtWidgets = qt.QtCore, qt.QtWidgets

    class DataViewerWindow(QtWidgets.QWidget):
        """The viewer, following the newest acquisition of a folder."""

        def __init__(self, root: str | Path, parent=None, *, viewer: Viewer | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Data viewer")
            self.follower = Follower(viewer or Viewer(ui="simple"), root)
            self.setToolTip(f"Watching {self.follower.root}")

            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.viewer.qt_widget(self), 1)

            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(POLL_MS)
            self.poll()

        @property
        def viewer(self) -> Viewer:
            return self.follower.viewer

        def poll(self) -> None:
            self.follower.poll()

        def closeEvent(self, event) -> None:  # noqa: N802 -- Qt's name
            self.timer.stop()
            self.viewer.stop()
            super().closeEvent(event)

    return DataViewerWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Data viewer window over a data folder.")
    parser.add_argument("folder", help="the folder the microscope writes acquisitions into")
    args = parser.parse_args(argv)
    qt = _qt()
    app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication(sys.argv)
    window = make_window_class()(args.folder)
    window.resize(1200, 800)
    window.show()
    return app.exec() if hasattr(app, "exec") else app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
