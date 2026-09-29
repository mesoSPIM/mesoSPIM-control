"""Real-PyQt smoke test for the assistant's schedules: the tab's own QTimer, in a running Qt
event loop, fires a due schedule as a turn on the real worker thread, which runs a real agent
(against a scripted model, never a network) whose tool dispatches through a real Acceptor on the
Core thread; Stop microscope clears the schedules and nothing fires after it. The fake-Qt unit
tests call the tick by hand; this is the timer itself."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("GEMINI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtWidgets
except ModuleNotFoundError as error:
    raise SystemExit("test_real_pyqt_scheduler_smoke.py requires PyQt5") from error

from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src import mesoSPIM_AiAssistent_Config as config
from mesoSPIM.src.mesoSPIM_AiAssistent_GUI import AiAssistentGUI
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI
from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor

EVERY_S = config.SCHEDULE_MIN_SECONDS          # the shortest schedule the tab allows
WATCH_S = 2.5 * EVERY_S                        # long enough for two firings


class Core(QtCore.QObject):
    """The smoke Core with the two slots the tab invokes to take and release the session."""
    sig_remote_control_started = QtCore.pyqtSignal(bool, str)
    sig_warning = QtCore.pyqtSignal(str)
    sig_finished = QtCore.pyqtSignal()
    sig_time_lapse_finished = QtCore.pyqtSignal()
    sig_time_lapse_cancelled = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.state = {"state": "idle"}
        self.cfg = SimpleNamespace(version="pyqt-smoke", ai_assistant_traces_folder=tempfile.mkdtemp(prefix="traces_"))
        self._remote_session = {"operation": None, "counter": 0}
        self._remote_control = None
        self._assistant_acceptor = None
        self.timelapse_active = False

    @QtCore.pyqtSlot()
    def start_ai_assistant(self):
        self._assistant_acceptor = Acceptor(self)

    @QtCore.pyqtSlot()
    def stop_ai_assistant(self):
        ai.stop_assistant_for_core(self)

    @QtCore.pyqtSlot(str, str, int, str)
    def start_remote_control(self, *_args):
        pass

    @QtCore.pyqtSlot()
    def stop_remote_control(self):
        pass


class Window(QtWidgets.QMainWindow):
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_stop_time_lapse = QtCore.pyqtSignal()
    sig_stop_movement = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.core = Core()
        self.TabWidget = QtWidgets.QTabWidget(self)
        self.TimelapseTabWidget = QtWidgets.QWidget()
        self.TabWidget.addTab(self.TimelapseTabWidget, "Timelapse")
        self.setCentralWidget(self.TabWidget)
        self.remote_control = RemoteControlGUI(self)
        self.core.sig_warning.connect(self.display_warning)
        self.stops = 0

    def display_warning(self, text):
        pass

    def stop_acquisition_and_timelapse(self):
        self.stops += 1


def scripted_model():
    """Asked for a schedule, sets one; a scheduled turn reads the state; after any tool, a word."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    def model_function(messages, info):
        last = messages[-1]
        if any(isinstance(part, ToolReturnPart) for part in last.parts):
            return ModelResponse(parts=[TextPart("Done.")])
        prompt = next((p for p in last.parts if isinstance(p, UserPromptPart)), None)
        text = prompt.content if isinstance(prompt.content, str) else " ".join(c for c in prompt.content if isinstance(c, str))
        if "[scheduled" in text:
            return ModelResponse(parts=[ToolCallPart(tool_name="get_state", args={})])
        if "every" in text:
            return ModelResponse(parts=[ToolCallPart(tool_name="schedule", args={
                "name": "check", "instruction": "check the state", "every_seconds": EVERY_S})])
        return ModelResponse(parts=[TextPart("Hello.")])
    return FunctionModel(model_function)


def wait_until(condition, seconds, what):
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
        time.sleep(0.02)


def fired_turns(tab):
    """The transcript's scheduled turns that ran a tool."""
    blocks = tab._blocks
    return sum(1 for earlier, later in zip(blocks, blocks[1:])
               if isinstance(earlier, str) and "[scheduled" in earlier
               and isinstance(later, dict) and any(name == "get_state" for name, _ in later["tools"]))


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ai.build_model = lambda endpoint: scripted_model()             # no network in this test
    window = Window()
    tab = AiAssistentGUI(window)
    window.TabWidget.setCurrentWidget(tab)
    window.show()
    app.processEvents()

    tab.language.key.setText("k")
    tab.on_connect()
    assert tab._state == "ready" and tab._tick.isActive(), (tab._state, tab.status_label.text())
    assert tab._worker is not None and tab._worker.scheduler is tab.scheduler

    tab._submit(f"Check the state every {EVERY_S} seconds.")
    wait_until(lambda: not tab._running, 20, "the first turn")
    listing = tab.scheduler.listing()
    assert [item["name"] for item in listing] == ["check"] and listing[0]["every_seconds"] == EVERY_S, listing

    started = time.monotonic()
    wait_until(lambda: fired_turns(tab) >= 2, WATCH_S + 10, "two scheduled firings")
    elapsed = time.monotonic() - started
    assert elapsed >= 2 * EVERY_S - 1, f"two firings came too early: {elapsed:.1f} s"
    shown = tab.chat_window.output.toPlainText()
    assert "[scheduled 'check'] check the state" in shown, shown[-300:]

    tab.on_stop_microscope()
    assert tab.scheduler.listing() == [] and window.stops == 1
    wait_until(lambda: not tab._running, 20, "the cancelled turn to end")
    count = fired_turns(tab)
    deadline = time.monotonic() + EVERY_S + 2
    while time.monotonic() < deadline:
        app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        time.sleep(0.05)
    assert fired_turns(tab) == count, "a schedule fired after Stop microscope"

    tab.on_disconnect()
    assert not tab._tick.isActive() and window.core._assistant_acceptor is None
    tab.shutdown()
    print(f"REAL PYQT SCHEDULER SMOKE PASS: Qt {QtCore.QT_VERSION_STR}, {count} scheduled turns fired by the "
          f"tab's timer every {EVERY_S} s through the worker and the Acceptor, none after Stop microscope", flush=True)


if __name__ == "__main__":
    main()
