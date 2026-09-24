"""RemoteControlGUI logic, from source, using the QtWidgets stub in conftest."""

import pytest

from PyQt5.QtWidgets import QMessageBox
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.test.remote_control.support.fakes import RecordingCore
from mesoSPIM.src import mesoSPIM_RemoteControl_Commands  # noqa: F401  (fills the command registry)


class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot, *a, **k):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _FakeTabWidget:
    def indexOf(self, _widget):
        return 0

    def insertTab(self, *_a):
        pass

    def addTab(self, *_a):
        pass


class _FakeCore:
    def __init__(self):
        self.started = []
        self.stopped = []
        self.sig_remote_control_started = _Signal()

    def start_remote_control(self, *args):
        self.started.append(args)

    def stop_remote_control(self, *args):
        self.stopped.append(args)


class _FakeModel:
    def __init__(self):
        self.table = ["old"]

    def setTable(self, table):
        self.table = table


class _FakeAcquisitionManager:
    def __init__(self):
        self.model = _FakeModel()
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


class _FakeParent:
    def __init__(self, core):
        self.TabWidget = _FakeTabWidget()
        self.TimelapseTabWidget = object()
        self.core = core
        self.acquisition_manager_window = _FakeAcquisitionManager()
        self.sig_state_request = _Signal()                  # MainWindow's two stop signals
        self.sig_stop_time_lapse = _Signal()


@pytest.fixture
def tab():
    QMessageBox.warnings.clear()
    return RemoteControlGUI(_FakeParent(_FakeCore()))


def _fill(tab, host="127.0.0.1", port="42000", token="secret", mode="TCP"):
    tab.RemoteControlHostLineEdit.setText(host)
    tab.RemoteControlPortLineEdit.setText(port)
    tab.RemoteControlTokenLineEdit.setText(token)
    tab.RemoteControlModeComboBox.setCurrentText(mode)


def test_start_non_numeric_port_warns_without_emit(tab):
    _fill(tab, port="not-a-port")
    tab.start()
    assert "Remote Control" in [w[1] for w in QMessageBox.warnings]
    assert QMessageBox.warnings[-1][2] == "Port must be a number."
    assert tab.core.started == []


@pytest.mark.parametrize("port", ("-1", "0", "65536"))
def test_start_out_of_range_port_warns_without_emit(tab, port):
    _fill(tab, port=port)
    tab.start()
    assert QMessageBox.warnings[-1][2] == "Port must be between 1 and 65535."
    assert tab.core.started == []


def test_start_empty_token_warns_without_emit(tab):
    _fill(tab, token="   ")
    tab.start()
    assert QMessageBox.warnings[-1][2] == "Password is required."
    assert tab.core.started == []


def test_password_field_is_masked(tab):
    """The password is a credential and must never render in clear text."""
    from PyQt5.QtWidgets import QLineEdit

    assert tab.RemoteControlTokenLineEdit.echoMode() == QLineEdit.Password


def test_remote_control_never_starts_without_operator_action(tab):
    assert tab.running is False
    assert tab.core.started == []
    assert tab.RemoteControlStatusLabel.text() == "stopped"


def test_acquisition_list_bridge_resets_gui_model_and_selection(tab):
    manager = tab.main_window.acquisition_manager_window
    acquisitions = [{"filename": "remote.raw"}]
    assert tab.core._remote_control_acquisition_list_signal is tab.sig_install_acquisition_list

    tab.core._remote_control_acquisition_list_signal.emit(acquisitions, 0)

    assert manager.model.table is acquisitions
    assert manager.selected_row == 0
    assert manager.predictions_updated == 2

    manager.selected_row = 1
    replacement = [{"filename": "one.raw"}, {"filename": "two.raw"}]
    tab.core._remote_control_acquisition_list_signal.emit(replacement, None)
    assert manager.model.table is replacement
    assert manager.selected_row == 1


def test_start_empty_host_defaults(tab):
    _fill(tab, host="   ")
    tab.start()
    assert tab.core.started, "expected a start emit"
    assert tab.core.started[-1][1] == config.DEFAULT_HOST


def test_start_valid_emits_payload_and_order(tab):
    _fill(tab, host="localhost", port="42123", token="tok", mode="MCP")
    tab.start()
    assert QMessageBox.warnings == []
    ((mode, host, port, token),) = tab.core.started
    assert (mode, host, port, token) == ("MCP", "localhost", 42123, "tok")
    assert isinstance(mode, str) and isinstance(host, str)
    assert isinstance(port, int) and isinstance(token, str)


def test_on_started_running_vs_warn(tab):
    tab.on_started(True, "ok")
    assert tab.running is True
    assert QMessageBox.warnings == []
    tab.on_started(False, "self-test failed")
    assert tab.running is False
    assert QMessageBox.warnings, "a failed start must warn"


def test_running_session_locks_transport_selection_until_stop(tab):
    tab.on_started(True, "ok")
    assert not tab.RemoteControlStartButton.isEnabled()
    assert tab.RemoteControlStopButton.isEnabled()
    assert all(not widget.isEnabled() for widget in tab._inputs())

    tab.stop()
    assert tab.RemoteControlStartButton.isEnabled()
    assert not tab.RemoteControlStopButton.isEnabled()
    assert all(widget.isEnabled() for widget in tab._inputs())


def test_update_mode_note_swaps_only_the_default_port(tab):
    # MCP with the TCP default -> swapped to the MCP default
    tab.RemoteControlModeComboBox.setCurrentText("MCP")
    tab.RemoteControlPortLineEdit.setText(str(config.DEFAULT_TCP_PORT))
    tab.update_mode_note()
    assert tab.RemoteControlPortLineEdit.text() == str(config.DEFAULT_MCP_PORT)

    # TCP with the MCP default -> swapped back
    tab.RemoteControlModeComboBox.setCurrentText("TCP")
    tab.RemoteControlPortLineEdit.setText(str(config.DEFAULT_MCP_PORT))
    tab.update_mode_note()
    assert tab.RemoteControlPortLineEdit.text() == str(config.DEFAULT_TCP_PORT)

    # a hand-typed port is left untouched in both directions
    for mode in ("MCP", "TCP"):
        tab.RemoteControlModeComboBox.setCurrentText(mode)
        tab.RemoteControlPortLineEdit.setText("55555")
        tab.update_mode_note()
        assert tab.RemoteControlPortLineEdit.text() == "55555"


def test_shutdown_always_stops_core_including_during_an_inflight_start(tab):
    tab.running = False
    tab.shutdown()
    assert len(tab.core.stopped) == 1

    tab.running = True
    tab.shutdown()
    assert len(tab.core.stopped) == 2
    assert tab.running is False


def test_stop_always_emits(tab):
    # The Stop button and shutdown both emit unconditionally because Core owns the real handle.
    tab.running = False
    tab.stop()
    assert len(tab.core.stopped) == 1


class _ThreadedFakeCore(_FakeCore):
    """A core that reports a different thread than the tab, as production does."""

    def thread(self):
        return object()


def test_core_to_gui_bridge_is_queued_never_blocking_across_threads():
    from PyQt5.QtCore import Qt

    window = _FakeParent(_ThreadedFakeCore())
    tab = RemoteControlGUI(window)

    by_slot = {slot: kwargs for slot, kwargs in tab.sig_install_acquisition_list.connections}
    assert by_slot[tab.install_acquisition_list]["type"] == Qt.QueuedConnection
    # The GUI -> Core direction may block; the GUI thread waiting on Core is fine on its own. What
    # must never happen is Core also waiting on the GUI, which is the bridge above.
    stop_type = {slot: kwargs for slot, kwargs in tab.sig_stop_remote_control.connections}
    assert stop_type[window.core.stop_remote_control]["type"] == Qt.BlockingQueuedConnection


class _FakeButton:
    def __init__(self, enabled):
        self.enabled = enabled

    def setEnabled(self, enabled):
        self.enabled = enabled


class _FakeMainWindow(_FakeParent):
    """The four MainWindow methods a GUI Run button calls, recorded, plus its Controls box."""

    def __init__(self, core):
        super().__init__(core)
        self.ControlGroupBox = _FakeButton(True)
        self.stop_enabled = False
        self.mode_buttons_enabled = True
        self.progress = "standard"
        self.finished_calls = 0

    def enable_stop_button(self, enabled):
        self.stop_enabled = enabled

    def enable_mode_control_buttons(self, enabled):
        self.mode_buttons_enabled = enabled

    def set_progressbars_to_busy(self):
        self.progress = "busy"

    def finished(self):
        self.finished_calls += 1
        self.stop_enabled, self.mode_buttons_enabled = False, True
        self.ControlGroupBox.setEnabled(True)
        self.progress = "standard"


def test_a_remote_run_enables_stop_and_locks_the_run_buttons_like_a_gui_run():
    window = _FakeMainWindow(_FakeCore())
    tab = RemoteControlGUI(window)
    assert tab.core._remote_control_run_signal is tab.sig_remote_run

    tab.core._remote_control_run_signal.emit(True)
    assert window.stop_enabled is True
    assert window.mode_buttons_enabled is False
    assert window.ControlGroupBox.enabled is False
    assert window.progress == "busy"
    assert window.finished_calls == 0

    tab.core._remote_control_run_signal.emit(False)          # the start raised: no sig_finished
    assert window.finished_calls == 1
    assert (window.stop_enabled, window.mode_buttons_enabled, window.ControlGroupBox.enabled) == (False, True, True)


def test_the_run_bridge_is_queued_never_blocking_across_threads():
    from PyQt5.QtCore import Qt

    window = _FakeMainWindow(_ThreadedFakeCore())
    tab = RemoteControlGUI(window)
    by_slot = {slot: kwargs for slot, kwargs in tab.sig_remote_run.connections}
    assert by_slot[tab.on_remote_run]["type"] == Qt.QueuedConnection


class _SessionCore(RecordingCore):
    """The fake Core with a real remote session, plus what the tab connects to."""

    def __init__(self):
        super().__init__()
        self.sig_remote_control_started = _Signal()

    def start_remote_control(self, *args):
        pass

    def stop_remote_control(self, *args):
        pass


_WindowWithStop = _FakeMainWindow   # STOP and Stop microscope emit its sig_state_request and sig_stop_time_lapse


@pytest.mark.parametrize("stop", ["idle request", "time lapse stop"])
def test_a_remote_run_stopped_from_the_window_is_reported_as_stopped(stop):
    """On the Windows demo, Stop microscope ended a remote 1000-plane run at 25 planes and the
    client was told "completed" with no stop_requested: it could not tell. Only stop_activity
    marked the operation; a stop from the window now does too."""
    from mesoSPIM.src import mesoSPIM_RemoteControl_Config as rc_config
    from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher

    core = _SessionCore()
    window = _WindowWithStop(core)
    RemoteControlGUI(window)
    dispatcher.run(core, "run_acquisition_list", {})
    assert dispatcher.operation_snapshot(core)["status"] == "processing"

    if stop == "idle request":
        window.sig_state_request.emit({"state": "idle"})
    else:
        window.sig_stop_time_lapse.emit()
    assert dispatcher.operation_snapshot(core)["stop_requested"] is True

    dispatcher.complete(core, rc_config.MILESTONE_FINISHED)
    operation = dispatcher.operation_snapshot(core)
    assert operation["status"] == "completed" and operation["stop_requested"] is True


def test_another_state_request_from_the_window_is_not_a_stop():
    from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher

    core = _SessionCore()
    window = _WindowWithStop(core)
    RemoteControlGUI(window)
    dispatcher.run(core, "run_acquisition_list", {})
    window.sig_state_request.emit({"intensity": 20})
    assert not dispatcher.operation_snapshot(core).get("stop_requested")
