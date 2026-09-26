"""Real-PyQt smoke test for the AI Assistant tab and window: builds them offscreen, never a
worker, a model or a server. Checks what the fake-Qt unit tests cannot: that the setup grid
re-places the key without duplicating it, shows the right fields per type and preset in both
model boxes, lines the boxes up, stays within the main window's width; that the window lays its
controls out as designed and appears only when connected; and that Enter sends while Shift+Enter
starts a new line."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtGui, QtTest, QtWidgets
except ModuleNotFoundError as error:
    raise SystemExit("test_real_pyqt_assistant_smoke.py requires PyQt5") from error

from mesoSPIM.src.mesoSPIM_AiAssistent_GUI import CLOUD_MODE, LOCAL_MODE, SAME_AS_LANGUAGE, AiAssistentGUI
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI

MAIN_WINDOW_WIDTH = 964  # the designed width of mesoSPIM_MainWindow.ui
SLACK = 80               # the boxes may run a little past it; the window is wider in practice


class Core(QtCore.QObject):
    sig_remote_control_started = QtCore.pyqtSignal(bool, str)
    sig_warning = QtCore.pyqtSignal(str)
    cfg = types.SimpleNamespace()
    _remote_control = None                                # Core's controller handles
    _assistant_acceptor = None

    @QtCore.pyqtSlot(str, str, int, str)
    def start_remote_control(self, *_args):
        pass

    @QtCore.pyqtSlot()
    def stop_remote_control(self):
        pass


class Window(QtWidgets.QMainWindow):
    # MainWindow's two stop signals, which the Remote Control tab listens to.
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_stop_time_lapse = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.core = Core()
        self.TabWidget = QtWidgets.QTabWidget(self)
        self.TimelapseTabWidget = QtWidgets.QWidget()
        self.TabWidget.addTab(self.TimelapseTabWidget, "Timelapse")
        self.setCentralWidget(self.TabWidget)
        self.remote_control = RemoteControlGUI(self)
        self.core.sig_warning.connect(self.display_warning)   # MainWindow.py:184 runs after the tab

    def display_warning(self, text):
        pass


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
    # The tab: Connect and Disconnect side by side under the setup, Connect the one that works;
    # the window a separate top-level window, closed until connected.
    chat = tab.chat_window
    assert tab.connect_button.isEnabled() and not tab.disconnect_button.isEnabled()
    assert tab.connect_button.mapTo(tab, tab.connect_button.rect().topLeft()).y() == \
        tab.disconnect_button.mapTo(tab, tab.disconnect_button.rect().topLeft()).y()
    assert chat.isWindow() and not chat.isVisible() and chat.parent() is window
    tab._set_connect_state("ready", "Gemini, gemini-3.5-flash-lite")
    app.processEvents()
    assert chat.isVisible() and chat.windowTitle() == "mesoSPIM AI Assistant — Gemini, gemini-3.5-flash-lite"
    assert not tab.connect_button.isEnabled() and tab.disconnect_button.isEnabled()
    assert not language.isEnabled()
    # In the window: the transcript on top, Stop microscope right of the input, on its line (Enter
    # sends); under them Cancel prompt, Clear context and Show tool calls on one line, in this order.
    stop, entry = chat.stop_button, chat.input
    assert chat.output.mapTo(chat, chat.output.rect().bottomLeft()).y() < entry.mapTo(chat, entry.rect().topLeft()).y()
    assert stop.mapTo(chat, stop.rect().topLeft()).y() == entry.mapTo(chat, entry.rect().topLeft()).y()
    assert stop.mapTo(chat, stop.rect().topLeft()).x() > entry.mapTo(chat, entry.rect().topRight()).x()
    row = (chat.interrupt, chat.clear_button, chat.show_tool_calls)
    middles = {b.mapTo(chat, b.rect().center()).y() for b in row}
    assert max(middles) - min(middles) <= 2 and min(middles) > entry.mapTo(chat, entry.rect().bottomLeft()).y()
    lefts = [b.mapTo(chat, b.rect().topLeft()).x() for b in row]
    assert lefts == sorted(lefts)
    tab._set_connect_state("idle")
    app.processEvents()
    assert not chat.isVisible() and language.isEnabled()

    # Widths are only real with real fonts: offscreen Qt on Windows has none, and draws every
    # letter as a wide box.
    fonts = bool(QtGui.QFontDatabase().families())
    if fonts:
        for name, width in (("cloud", width_cloud), ("local", width_local)):
            assert width <= MAIN_WINDOW_WIDTH + SLACK, f"{name} setup needs {width} px"
        assert width_server <= MAIN_WINDOW_WIDTH + 2 * SLACK, f"OpenAI-style setup needs {width_server} px"

    # The input box: Enter sends, Shift+Enter starts a new line, as editors do. Only the key
    # handling is under test, so the tab's own submit slot is detached first.
    sent = []
    entry.returnPressed.disconnect(tab.on_submit)
    entry.returnPressed.connect(lambda: sent.append(entry.text()))
    chat.show()
    entry.setFocus()
    QtTest.QTest.keyClicks(entry, "centre the sample")
    QtTest.QTest.keyClick(entry, QtCore.Qt.Key_Return, QtCore.Qt.ShiftModifier)
    QtTest.QTest.keyClicks(entry, "then snap")
    assert sent == [] and entry.text() == "centre the sample\nthen snap"
    QtTest.QTest.keyClick(entry, QtCore.Qt.Key_Return)
    assert sent == ["centre the sample\nthen snap"]
    entry.setText("")

    tab.shutdown()
    print(f"REAL PYQT ASSISTANT SMOKE PASS: Qt {QtCore.QT_VERSION_STR}, "
          + (f"setup widths cloud={width_cloud} local={width_local} openai-style={width_server}" if fonts
             else "setup widths not measured: no fonts on this platform, run with QT_QPA_PLATFORM=windows"))


if __name__ == "__main__":
    main()
