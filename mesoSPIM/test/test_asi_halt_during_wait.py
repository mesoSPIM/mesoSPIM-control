"""A blocking ASI move must stay stoppable (#114): a fake Tiger port stays busy until HALT.
Run from the ``mesoSPIM`` folder."""
import threading
import time

import pytest
from PyQt5 import QtCore

import src.devices.stages.asi.asicontrol as asicontrol
from src.mesoSPIM_Stages import mesoSPIM_ASI_Stages, StageMotionHalted
from src.mesoSPIM_Core import mesoSPIM_Core

HALT = b'\\\r'


class FakeTigerPort:
    """Answers '/' with 'B' for ``busy_polls`` polls after a move (forever when None), then 'N'."""

    def __init__(self):
        self.busy_polls = 3
        self.remaining = 0
        self.sent = []
        self.in_waiting = 0

    def write(self, command):
        self.sent.append(command)
        if command[:1] in (b'M', b'R'):
            self.remaining = self.busy_polls
        elif command == HALT:
            self.remaining = 0

    def readline(self):
        if self.sent[-1] == b'/\r':
            if self.remaining is None:
                return b'B\r\n'
            if self.remaining > 0:
                self.remaining -= 1
                return b'B\r\n'
            return b'N\r\n'
        if self.sent[-1][:1] == b'W':
            return b':A 0 0 0\r\n'
        return b':A\r\n'

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        pass

    def halts(self):
        return self.sent.count(HALT)


class FakeSerialWorker(QtCore.QObject):
    sig_stop_movement = QtCore.pyqtSignal()
    sig_zero_axes = QtCore.pyqtSignal(list)
    sig_unzero_axes = QtCore.pyqtSignal(list)
    sig_load_sample = QtCore.pyqtSignal()
    sig_unload_sample = QtCore.pyqtSignal()
    sig_center_sample = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.state = {}
        self.cfg = type('Cfg', (), {})()
        self.cfg.asi_parameters = {
            'COMport': 'COM99', 'baudrate': 115200, 'ttl_cards': None, 'ttl_motion_enabled': False,
            'stage_assignment': {'x': 'X', 'z': 'Z', 'theta': 'T'},
            'encoder_conversion': {'X': 10, 'Z': 10, 'T': 1000},
            'speed': {'X': 3.0, 'Z': 3.0, 'T': 30.0}, 'move_timeout_s': 0.4,
        }
        self.cfg.stage_parameters = {f'{axis}_{end}': limit for axis in 'xyzf' for end, limit in
                                     (('min', -100000), ('max', 100000))} | {'theta_min': -720, 'theta_max': 720}


@pytest.fixture
def port(monkeypatch):
    fake = FakeTigerPort()
    monkeypatch.setattr(asicontrol.serial, 'Serial', lambda *a, **k: fake)
    return fake


@pytest.fixture
def stage(port):
    QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    stage = mesoSPIM_ASI_Stages(FakeSerialWorker())
    stage.pos_timer.stop()
    return stage


def test_a_completed_move_returns_without_a_halt(stage, port):
    stage.move_absolute({'theta_abs': 0}, wait_until_done=True)
    assert port.halts() == 0
    assert port.sent.count(b'/\r') >= 5, "done needs two N answers after the B answers"


def test_stop_from_another_thread_ends_a_blocking_move(stage, port):
    port.busy_polls = None
    outcome = []

    def core_thread():
        try:
            stage.move_absolute({'theta_abs': 0}, wait_until_done=True)
        except StageMotionHalted:
            outcome.append('halted')

    worker = threading.Thread(target=core_thread, daemon=True)
    worker.start()
    time.sleep(0.15)
    assert worker.is_alive(), "the wait should still be blocking on the busy port"
    assert stage._serial_lock.acquire(timeout=1), "the port is never free while the wait runs"
    stage._serial_lock.release()
    stage.stop()
    worker.join(timeout=2)
    assert outcome == ['halted']
    assert port.halts() == 1


def test_a_move_that_times_out_halts_and_raises(stage, port):
    port.busy_polls = None
    t0 = time.monotonic()
    with pytest.raises(StageMotionHalted):
        stage.move_absolute({'theta_abs': 0}, wait_until_done=True)
    assert port.halts() == 1
    assert 0.4 <= time.monotonic() - t0 < 1.5


class CoreStub:
    """The bits of mesoSPIM_Core that run_acquisition_list touches."""

    def __init__(self, halt_on_prepare):
        self.stopflag = False
        self.halt_on_prepare = halt_on_prepare
        self.calls = []

    def prepare_acquisition(self, acq, acq_list):
        self.calls.append(('prepare', acq))
        if self.halt_on_prepare:
            raise StageMotionHalted('theta')

    def run_acquisition(self, acq, acq_list):
        self.calls.append(('run', acq))

    def close_acquisition(self, acq, acq_list):
        self.calls.append(('close', acq))

    def stop(self):
        self.calls.append(('stop', None))
        self.stopflag = True


def test_core_stops_the_list_when_a_move_is_halted():
    core = CoreStub(halt_on_prepare=True)
    mesoSPIM_Core.run_acquisition_list(core, ['acq0', 'acq1'])
    assert core.calls == [('prepare', 'acq0'), ('stop', None)]


def test_core_runs_the_list_when_moves_complete():
    core = CoreStub(halt_on_prepare=False)
    mesoSPIM_Core.run_acquisition_list(core, ['acq0'])
    assert core.calls == [('prepare', 'acq0'), ('run', 'acq0'), ('close', 'acq0')]
