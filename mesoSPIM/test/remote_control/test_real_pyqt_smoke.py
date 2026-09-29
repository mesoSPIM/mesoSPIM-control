"""Real-PyQt smoke test. Constructs Qt objects but never starts or binds a transport."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtNetwork, QtWidgets
except ModuleNotFoundError as error:
    raise SystemExit("real_pyqt_smoke.py requires PyQt5") from error

from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src.mesoSPIM_RemoteControl_Commands import COMMANDS
from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import complete, operation_snapshot, run
from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI


class Core(QtCore.QObject):
    sig_remote_control_started = QtCore.pyqtSignal(bool, str)
    sig_warning = QtCore.pyqtSignal(str)
    sig_finished = QtCore.pyqtSignal()
    sig_time_lapse_finished = QtCore.pyqtSignal()
    sig_time_lapse_cancelled = QtCore.pyqtSignal()
    sig_publish_acquisition_list = QtCore.pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.state = {"state": "idle"}
        self.cfg = SimpleNamespace(version="pyqt-smoke")
        self._remote_session = {"operation": None, "counter": 0}
        self._remote_control = None                       # Core's controller handles
        self._assistant_acceptor = None
        self.timelapse_active = False
        self.started = []
        self.stopped = 0
        self.stop_time_list = [{"filename": "installed-during-stop.raw"}]
        self.calls = []
        self.sig_publish_acquisition_list.connect(self.publish_acquisition_list)

    @QtCore.pyqtSlot(str, str, int, str)
    def start_remote_control(self, *args):
        self.started.append(args)  # fake slot: deliberately cannot bind a transport

    @QtCore.pyqtSlot()
    def stop_remote_control(self):
        # Runs on the Core thread while the GUI thread is BLOCKED in tab.stop() (a
        # BlockingQueuedConnection). A remote set_acquisition_list landing at this moment emits the
        # Core -> GUI bridge from here. With a blocking bridge both threads wait on each other
        # forever; the bridge must therefore be queued. main() guards this with a watchdog.
        bridge = getattr(self, "_remote_control_acquisition_list_signal", None)
        if bridge is not None:
            bridge.emit(self.stop_time_list, 0)
        self.stopped += 1

    @QtCore.pyqtSlot(object, object)
    def publish_acquisition_list(self, acquisitions, selected_row):
        self._remote_control_acquisition_list_signal.emit(acquisitions, selected_row)

    def set_state(self, mode):
        self.calls.append(("set_state", mode))
        self.state["state"] = mode

    def stop(self):
        self.calls.append(("stop",))
        self.state["state"] = "idle"


class AcquisitionModel:
    def __init__(self):
        self.table = ["old"]

    def setTable(self, table):
        self.table = table


class AcquisitionManager:
    def __init__(self):
        self.model = AcquisitionModel()
        self.selected_row = 0
        self.predictions_updated = 0

    def get_first_selected_row(self):
        return self.selected_row

    def set_selected_row(self, row):
        self.selected_row = row

    def update_acquisition_time_prediction(self):
        self.predictions_updated += 1

    def update_acquisition_size_prediction(self):
        self.predictions_updated += 1


class Window(QtWidgets.QMainWindow):
    # MainWindow's two stop signals, which the Remote Control tab listens to.
    sig_state_request = QtCore.pyqtSignal(dict)
    sig_stop_time_lapse = QtCore.pyqtSignal()

    def __init__(self, core=None):
        super().__init__()
        self.core = core or Core()
        self.core_thread = QtCore.QThread(self)
        self.core.moveToThread(self.core_thread)
        self.core_thread.start()
        self.TabWidget = QtWidgets.QTabWidget(self)
        self.TimelapseTabWidget = QtWidgets.QWidget(self.TabWidget)
        self.TabWidget.addTab(self.TimelapseTabWidget, "Timelapse")
        self.setCentralWidget(self.TabWidget)
        self.acquisition_manager_window = AcquisitionManager()
        self.shown = []                                   # (text, thread) of every warning window

    def display_warning(self, text):
        self.shown.append((text, threading.get_ident()))

    # What the tab calls on MainWindow when a remote run starts or ends (its STOP bridge).
    ControlGroupBox = property(lambda self: self.TabWidget)

    def enable_stop_button(self, enabled):
        self.stop_enabled = enabled

    def enable_mode_control_buttons(self, enabled):
        pass

    def set_progressbars_to_busy(self):
        pass

    def finished(self):
        self.stop_enabled = False


class WarningCore(Core):
    """The smoke Core with the slots a warning test drives on its own thread."""

    @QtCore.pyqtSlot()
    def connect_assistant(self):                          # as start_assistant_for_core, minus the self-test
        self._assistant_acceptor = Acceptor(self)
        self.done.set()

    @QtCore.pyqtSlot()
    def disconnect_assistant(self):                       # as stop_assistant_for_core
        self._assistant_acceptor.stop()
        self._assistant_acceptor = None
        self.done.set()

    @QtCore.pyqtSlot()
    def open_live(self):
        run(self, "start_live", {})
        self.done.set()

    @QtCore.pyqtSlot(str)
    def warn(self, text):
        self.sig_warning.emit(text)
        self.done.set()


class Driver(QtCore.QObject):
    """Queues calls onto the Core thread."""
    connect_assistant = QtCore.pyqtSignal()
    disconnect_assistant = QtCore.pyqtSignal()
    open_live = QtCore.pyqtSignal()
    warn = QtCore.pyqtSignal(str)


def build_tab(window):
    """In mesoSPIM's order: MainWindow builds the tab (:167 -> :617), connects Core's warnings to
    its window (:184), and mesoSPIM_Control.py:162 shows the window, where the tab takes over."""
    tab = RemoteControlGUI(window)
    window.core.sig_warning.connect(window.display_warning)
    window.show()
    return tab


def exercise_warning_routing(app):
    """A warning a connected remote controller's command caused opens no window and is on its
    operation; once the controller is gone, a warning opens exactly one window, on the GUI thread.
    Core runs on its own thread, as in mesoSPIM; every step waits on an Event, never on a sleep."""
    core = WarningCore()
    core.done = threading.Event()
    window = Window(core)                                 # Core on its own thread
    tab = build_tab(window)
    driver = Driver()
    for name in ("connect_assistant", "disconnect_assistant", "open_live", "warn"):
        getattr(driver, name).connect(getattr(window.core, name), QtCore.Qt.QueuedConnection)

    def on_core(signal, *args):
        window.core.done.clear()
        signal.emit(*args)
        assert window.core.done.wait(5), "the Core thread did not run the step"
        app.processEvents()                               # deliver anything queued to the GUI thread

    gui = threading.get_ident()
    on_core(driver.connect_assistant)
    on_core(driver.open_live)
    on_core(driver.warn, "remote")
    app.processEvents()
    assert window.shown == [], window.shown
    assert operation_snapshot(window.core)["warning"] == "remote"

    on_core(driver.disconnect_assistant)
    on_core(driver.warn, "operator")
    app.processEvents()
    assert window.shown == [("operator", gui)], window.shown   # exactly one, on the GUI thread

    window.core_thread.quit()
    window.core_thread.wait()
    tab.deleteLater()
    window.deleteLater()
    app.processEvents()
    print("REAL PYQT WARNING ROUTING PASS: a remote command's warning on its operation, no window; "
          "after disconnect one window on the GUI thread")


def process_until(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert predicate(), "timed out while processing the Qt event queue"


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window()
    tab = build_tab(window)
    app.processEvents()

    assert not tab.running and window.core.started == []
    assert tab.RemoteControlStatusLabel.text() == "stopped"
    assert tab.RemoteControlTokenLineEdit.echoMode() == QtWidgets.QLineEdit.Password

    # The bridge is published on Core but executes the table replacement through the tab's signal.
    remote_list = [{"filename": "smoke.raw"}]
    window.core.sig_publish_acquisition_list.emit(remote_list, 0)
    process_until(app, lambda: window.acquisition_manager_window.model.table is remote_list)
    assert window.acquisition_manager_window.predictions_updated == 2

    # Prove the manual request is queued. The fake Core records it but cannot open a socket.
    tab.RemoteControlTokenLineEdit.setText("smoke-secret")
    tab.start()
    assert window.core.started == []
    process_until(app, lambda: bool(window.core.started))
    assert window.core.started == [("TCP", "127.0.0.1", 42000, "smoke-secret")]
    window.core.sig_remote_control_started.emit(True, "127.0.0.1:42000")
    assert tab.running and all(not widget.isEnabled() for widget in tab._inputs())

    # Deadlock regression: Stop blocks the GUI thread on Core, and Core emits the acquisition-list
    # bridge back at the GUI thread while it is blocked. A blocking bridge never returns; the
    # watchdog turns that hang into a failed run instead of a silent one.
    watchdog = threading.Timer(15, lambda: os._exit(3))
    watchdog.daemon = True
    watchdog.start()
    tab.stop()
    watchdog.cancel()
    assert window.core.stopped == 1 and not tab.running
    process_until(app, lambda: window.acquisition_manager_window.model.table is window.core.stop_time_list)

    # Marshal a read from a real Python worker through a real queued Qt signal.
    acceptor_core = Core()
    acceptor = Acceptor(acceptor_core)
    answer = {}

    def dispatch_ping():
        answer["thread"] = threading.get_ident()
        answer["reply"] = acceptor.dispatch("ping", {})

    worker = threading.Thread(target=dispatch_ping)
    worker.start()
    process_until(app, lambda: not worker.is_alive())
    worker.join()
    assert answer["thread"] != threading.get_ident()
    assert answer["reply"]["pong"] is True
    acceptor.close()
    acceptor.stop()

    # Cancel a real zero-delay QTimer callback before it can actuate the fake Core.
    timer_core = Core()
    assert run(timer_core, "start_live", {})["operation"]["status"] == "processing"
    run(timer_core, "stop_activity", {})
    app.processEvents()
    assert timer_core.calls == []
    assert operation_snapshot(timer_core)["stop_requested"] is True
    assert operation_snapshot(timer_core)["status"] == "stopped"     # a stop before it started ends it stopped

    # The uncancelled timer executes and resolves only after the fake Core leaves its run state.
    normal_core = Core()
    run(normal_core, "start_live", {})
    process_until(app, lambda: bool(normal_core.calls))
    assert normal_core.calls == [("set_state", "live")]
    run(normal_core, "stop_activity", {})
    complete(normal_core, config.MILESTONE_FINISHED)
    assert operation_snapshot(normal_core)["status"] == "stopped"         # stop_activity ended it

    server = QtNetwork.QTcpServer()  # construct the real class; never call listen()
    assert not server.isListening()
    server.close()
    server.deleteLater()

    # Application shutdown always asks Core to stop, even when the GUI already says stopped. This
    # also closes a transport whose queued start completed before its queued started signal arrived.
    tab.shutdown()
    assert window.core.stopped == 2

    window.core_thread.quit()
    window.core_thread.wait()
    tab.deleteLater()
    window.close()
    window.deleteLater()
    app.processEvents()
    exercise_warning_routing(app)
    print(
        f"REAL PYQT SMOKE PASS: Qt {QtCore.QT_VERSION_STR}, "
        f"PyQt {QtCore.PYQT_VERSION_STR}, commands={len(COMMANDS)}, no transport bound"
    )


if __name__ == "__main__":
    main()
