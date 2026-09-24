"""Real-PyQt smoke test for the AI Assistant tab's layout: builds the tab offscreen, never a
worker, a model or a server. Checks what the fake-Qt unit tests cannot: that the setup grid
re-places the key without duplicating it, shows the right fields per type and preset in both
model boxes, lines the boxes up, stays within the main window's width, and that Enter sends
while Shift+Enter starts a new line."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtTest, QtWidgets
except ModuleNotFoundError as error:
    raise SystemExit("test_real_pyqt_assistant_smoke.py requires PyQt5") from error

from mesoSPIM.src.mesoSPIM_AiAssistent_GUI import CLOUD_MODE, LOCAL_MODE, SAME_AS_LANGUAGE, AiAssistentGUI
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI

MAIN_WINDOW_WIDTH = 964  # the designed width of mesoSPIM_MainWindow.ui
SLACK = 80               # the boxes may run a little past it; the window is wider in practice


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
    language, vision = tab.language, tab.vision
    grid = language.grid

    # Cloud, a key-only provider: the key spans the second line, no base URL.
    language.mode.setCurrentText(CLOUD_MODE)
    language.provider.setCurrentText("Anthropic")
    app.processEvents()
    assert language.key.isVisible() and not language.base_url.isVisible() and not language.local_model.isVisible()
    assert cell_of(grid, language.key) == (1, 3, 6), cell_of(grid, language.key)
    assert items_for(grid, language.key) == 1 and items_for(grid, language.key_label) == 1
    width_cloud = tab.minimumSizeHint().width()

    # OpenAI-style: the base URL takes the start of the line and the key moves after it, once.
    language.provider.setCurrentText("OpenAI-style")
    app.processEvents()
    assert language.base_url.isVisible() and language.key.isVisible()
    assert cell_of(grid, language.base_url) == (1, 3, 3) and cell_of(grid, language.key) == (1, 7, 2)
    assert items_for(grid, language.key) == 1 and items_for(grid, language.key_label) == 1
    assert language.key.placeholderText() == "optional"
    width_server = tab.minimumSizeHint().width()

    # Back and forth leaves exactly one key item and the same width as before.
    language.provider.setCurrentText("Gemini")
    language.provider.setCurrentText("OpenAI-style")
    language.provider.setCurrentText("Anthropic")
    app.processEvents()
    assert items_for(grid, language.key) == 1 and cell_of(grid, language.key) == (1, 3, 6)
    assert tab.minimumSizeHint().width() == width_cloud

    # Local: the file dropdown and the folder button, the cloud fields gone.
    language.mode.setCurrentText(LOCAL_MODE)
    app.processEvents()
    assert language.local_model.isVisible() and language.folder_button.isVisible()
    assert not any(w.isVisible() for w in (language.provider, language.model, language.key, language.base_url))
    width_local = tab.minimumSizeHint().width()

    # The vision box defers to the language model until told otherwise, then offers the same.
    assert vision.same and vision.mode.currentText() == SAME_AS_LANGUAGE
    assert not any(w.isVisible() for w in (vision.provider, vision.model, vision.key, vision.local_model))
    same_height = vision.sizeHint().height()
    vision.mode.setCurrentText(CLOUD_MODE)
    app.processEvents()
    assert vision.provider.isVisible() and vision.key.isVisible() and vision.sizeHint().height() > same_height
    vision.mode.setCurrentText(LOCAL_MODE)
    app.processEvents()
    assert vision.local_model.isVisible() and not vision.provider.isVisible()

    # The boxes line up: same first columns.
    for column in range(5):
        assert language.grid.cellRect(0, column).width() == vision.grid.cellRect(0, column).width()
    assert language.mapToParent(language.grid.cellRect(0, 1).topLeft()).x() == \
        vision.mapToParent(vision.grid.cellRect(0, 1).topLeft()).x()
    # Send right of the input, on its line; under them every other button on one line, in this order.
    assert tab.send_button.mapTo(tab, tab.send_button.rect().topLeft()).y() == tab.input.mapTo(tab, tab.input.rect().topLeft()).y()
    assert tab.send_button.mapTo(tab, tab.send_button.rect().topLeft()).x() > tab.input.mapTo(tab, tab.input.rect().topRight()).x()
    row = (tab.interrupt, tab.clear_button, tab.connect_button, tab.disconnect_button, tab.stop_button)
    tops = {tab.mapTo(tab, b.mapTo(tab, b.rect().topLeft())).y() for b in row}
    assert len(tops) == 1 and tops.pop() > tab.input.mapTo(tab, tab.input.rect().bottomLeft()).y()
    lefts = [b.mapTo(tab, b.rect().topLeft()).x() for b in row]
    assert lefts == sorted(lefts)
    assert tab.disconnect_button.text() == "Disconnect"
    assert tab.connect_button.isEnabled() and not tab.disconnect_button.isEnabled()

    for name, width in (("cloud", width_cloud), ("local", width_local)):
        assert width <= MAIN_WINDOW_WIDTH + SLACK, f"{name} setup needs {width} px"
    assert width_server <= MAIN_WINDOW_WIDTH + 2 * SLACK, f"OpenAI-style setup needs {width_server} px"

    # The input box: Enter sends, Shift+Enter starts a new line, as editors do. Only the key
    # handling is under test, so the tab's own submit slot is detached first.
    sent = []
    tab.input.returnPressed.disconnect(tab.on_submit)
    tab.input.returnPressed.connect(lambda: sent.append(tab.input.text()))
    tab.input.setFocus()
    QtTest.QTest.keyClicks(tab.input, "centre the sample")
    QtTest.QTest.keyClick(tab.input, QtCore.Qt.Key_Return, QtCore.Qt.ShiftModifier)
    QtTest.QTest.keyClicks(tab.input, "then snap")
    assert sent == [] and tab.input.text() == "centre the sample\nthen snap"
    QtTest.QTest.keyClick(tab.input, QtCore.Qt.Key_Return)
    assert sent == ["centre the sample\nthen snap"]
    tab.input.setText("")

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
