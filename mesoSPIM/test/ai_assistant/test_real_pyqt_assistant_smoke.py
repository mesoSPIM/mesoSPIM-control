"""Real-PyQt smoke test for the AI Assistant tab's layout: builds the tab offscreen, never a
worker, a model or a server. Checks what the fake-Qt unit tests cannot: that the setup grid
re-places the key without duplicating it, shows the right fields per type and preset, and stays
within the main window's width."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtWidgets
except ModuleNotFoundError as error:
    raise SystemExit("test_real_pyqt_assistant_smoke.py requires PyQt5") from error

from mesoSPIM.src.mesoSPIM_AiAssistent_GUI import CLOUD_MODE, LOCAL_MODE, AiAssistentGUI
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI

MAIN_WINDOW_WIDTH = 964  # the designed width of mesoSPIM_MainWindow.ui
SLACK = 60               # the OpenAI-style line may run a little past it


class Core(QtCore.QObject):
    sig_remote_control_started = QtCore.pyqtSignal(bool, str)
    cfg = types.SimpleNamespace()

    @QtCore.pyqtSlot(str, str, int, str)
    def start_remote_control(self, *_args):
        pass

    @QtCore.pyqtSlot()
    def stop_remote_control(self):
        pass


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = Core()
        self.TabWidget = QtWidgets.QTabWidget(self)
        self.TimelapseTabWidget = QtWidgets.QWidget()
        self.TabWidget.addTab(self.TimelapseTabWidget, "Timelapse")
        self.setCentralWidget(self.TabWidget)
        self.remote_control = RemoteControlGUI(self)


def cell_of(grid, widget):
    row, column, _rows, columns = grid.getItemPosition(grid.indexOf(widget))
    return row, column, columns


def items_for(grid, widget):
    return sum(grid.itemAt(i).widget() is widget for i in range(grid.count()))


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window()
    tab = AiAssistentGUI(window)
    window.TabWidget.setCurrentWidget(tab)
    tab.setup_toggle.setChecked(True)
    window.show()
    app.processEvents()
    grid = tab._model_grid

    # Cloud, a key-only provider: the key spans the second line, no base URL.
    tab.mode.setCurrentText(CLOUD_MODE)
    tab.provider.setCurrentText("Anthropic")
    app.processEvents()
    assert tab.key.isVisible() and not tab.base_url.isVisible() and not tab.local_model.isVisible()
    assert cell_of(grid, tab.key) == (1, 3, 5), cell_of(grid, tab.key)
    assert items_for(grid, tab.key) == 1 and items_for(grid, tab._key_label) == 1
    assert cell_of(grid, tab.connect_button)[:2] == (1, 8)
    width_cloud = tab.minimumSizeHint().width()

    # OpenAI-style: the base URL takes the start of the line and the key moves after it, once.
    tab.provider.setCurrentText("OpenAI-style")
    app.processEvents()
    assert tab.base_url.isVisible() and tab.key.isVisible()
    assert cell_of(grid, tab.base_url) == (1, 3, 3) and cell_of(grid, tab.key) == (1, 7, 1)
    assert items_for(grid, tab.key) == 1 and items_for(grid, tab._key_label) == 1
    assert tab.key.placeholderText() == "optional"
    width_server = tab.minimumSizeHint().width()

    # Back and forth leaves exactly one key item and the same width as before.
    tab.provider.setCurrentText("Gemini")
    tab.provider.setCurrentText("OpenAI-style")
    tab.provider.setCurrentText("Anthropic")
    app.processEvents()
    assert items_for(grid, tab.key) == 1 and cell_of(grid, tab.key) == (1, 3, 5)
    assert tab.minimumSizeHint().width() == width_cloud

    # Local: the file dropdown and the folder button, the cloud fields gone, Connect still last.
    tab.mode.setCurrentText(LOCAL_MODE)
    app.processEvents()
    assert tab.local_model.isVisible() and tab.folder_button.isVisible()
    assert not any(w.isVisible() for w in (tab.provider, tab.model, tab.key, tab.base_url))
    assert cell_of(grid, tab.folder_button)[:2] == (1, 7) and cell_of(grid, tab.connect_button)[:2] == (1, 8)
    width_local = tab.minimumSizeHint().width()

    for name, width in (("cloud", width_cloud), ("local", width_local)):
        assert width <= MAIN_WINDOW_WIDTH + SLACK, f"{name} setup needs {width} px"
    assert width_server <= MAIN_WINDOW_WIDTH + 2 * SLACK, f"OpenAI-style setup needs {width_server} px"

    # The Connect button never changes size between its states.
    tab._set_connect_state("idle")
    idle = tab.connect_button.sizeHint().width()
    tab._set_connect_state("ready")
    app.processEvents()
    assert tab.connect_button.minimumWidth() >= tab.connect_button.sizeHint().width() >= idle

    tab.shutdown()
    print(f"REAL PYQT ASSISTANT SMOKE PASS: Qt {QtCore.QT_VERSION_STR}, "
          f"setup widths cloud={width_cloud} local={width_local} openai-style={width_server}")


if __name__ == "__main__":
    main()
