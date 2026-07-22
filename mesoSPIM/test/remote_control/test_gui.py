"""RemoteControlGUI logic, from source, using the QtWidgets stub in conftest."""

import pytest

from PyQt5.QtWidgets import QMessageBox
from mesoSPIM.src.mesoSPIM_RemoteControl_GUI import RemoteControlGUI
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config


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
