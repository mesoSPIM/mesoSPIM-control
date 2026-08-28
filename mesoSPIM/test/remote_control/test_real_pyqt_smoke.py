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
    sig_finished = QtCore.pyqtSignal()
    sig_time_lapse_finished = QtCore.pyqtSignal()
    sig_time_lapse_cancelled = QtCore.pyqtSignal()
    sig_publish_acquisition_list = QtCore.pyqtSignal(object, object)

    def __init__(self):
        super().__init__()
        self.state = {"state": "idle"}
        self.cfg = SimpleNamespace(version="pyqt-smoke")
        self._remote_session = {"operation": None, "counter": 0}
        self.timelapse_active = False
        self.started = []
        self.stopped = 0
        self.calls = []
        self.sig_publish_acquisition_list.connect(self.publish_acquisition_list)

    @QtCore.pyqtSlot(str, str, int, str)
    def start_remote_control(self, *args):
        self.started.append(args)  # fake slot: deliberately cannot bind a transport

    @QtCore.pyqtSlot()
    def stop_remote_control(self):
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
    def __init__(self):
        super().__init__()
        self.core = Core()
        self.core_thread = QtCore.QThread(self)
        self.core.moveToThread(self.core_thread)
        self.core_thread.start()
        self.TabWidget = QtWidgets.QTabWidget(self)
        self.TimelapseTabWidget = QtWidgets.QWidget(self.TabWidget)
        self.TabWidget.addTab(self.TimelapseTabWidget, "Timelapse")
        self.setCentralWidget(self.TabWidget)
        self.acquisition_manager_window = AcquisitionManager()


def process_until(app, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert predicate(), "timed out while processing the Qt event queue"


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window()
    tab = RemoteControlGUI(window)
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
    tab.stop()
    assert window.core.stopped == 1 and not tab.running

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

    # The uncancelled timer executes and resolves only after the fake Core leaves its run state.
    normal_core = Core()
    run(normal_core, "start_live", {})
    process_until(app, lambda: bool(normal_core.calls))
    assert normal_core.calls == [("set_state", "live")]
    run(normal_core, "stop_activity", {})
    complete(normal_core, config.MILESTONE_FINISHED)
    assert operation_snapshot(normal_core)["status"] == "completed"

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
    print(
        f"REAL PYQT SMOKE PASS: Qt {QtCore.QT_VERSION_STR}, "
        f"PyQt {QtCore.PYQT_VERSION_STR}, commands={len(COMMANDS)}, no transport bound"
    )


if __name__ == "__main__":
    main()
