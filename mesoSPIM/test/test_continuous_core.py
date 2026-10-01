"""
Core-side continuous-mode control flow, with a stub Core, waveformer and camera (no hardware, no GUI).
"""
import os
import types
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtWidgets

from mesoSPIM.src.mesoSPIM_Core import mesoSPIM_Core

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Calls(list):
    def rec(self, name, result=None):
        def f(*a, **k):
            self.append(name)
            return result
        return f


class Signal:
    def __init__(self, fn=None):
        self.fn, self.count = fn, 0

    def emit(self, *a):
        self.count += 1
        if self.fn:
            self.fn(*a)


def make_core(steps=20, deliver=None, stop_at=None, period=0.001):
    calls = Calls()
    core = types.SimpleNamespace()
    core.calls = calls
    core.acq = types.SimpleNamespace(get_image_count=lambda: steps)
    core.stopflag = False
    core.image_count = 0
    core.start_time = 0.0
    core.total_image_count = steps
    core.acquisition_count = 0
    core.total_acquisition_count = 1
    core.state = {'sweeptime': period, 'laser': '488 nm'}
    core.continuous_acq_mode = True
    core.camera_worker = types.SimpleNamespace(cur_image=0, drain_requests_done=0, camera=types.SimpleNamespace())
    deliver = steps if deliver is None else deliver

    def drain(*a):  # the camera thread: one frame per drain request, until it stops getting triggers
        assert core.camera_worker.drain_requests_done == core.sig_add_images_to_image_series.count - 1,             'a drain request was sent while the previous one was still outstanding'
        if core.camera_worker.cur_image < deliver:
            core.camera_worker.cur_image += 1
        if stop_at is not None and core.camera_worker.cur_image >= stop_at:
            core.stopflag = True
        core.camera_worker.drain_requests_done += 1

    core.sig_add_images_to_image_series = Signal(drain)
    core.sig_end_image_series = Signal()
    core.sig_status_message = Signal()
    core.waveformer = types.SimpleNamespace(continuous_plane_period=period,
                                            launch_continuous=calls.rec('launch'),
                                            stop_tasks=calls.rec('stop_tasks'),
                                            close_tasks=calls.rec('close_tasks'),
                                            park_ao_outputs=calls.rec('park'))
    core.laserenabler = types.SimpleNamespace(enable=calls.rec('laser_on'), disable_all=calls.rec('laser_off'))
    core.open_shutters = calls.rec('open_shutters')
    core.close_shutters = calls.rec('close_shutters')
    core.send_progress = lambda *a: None
    core._wait_for_end_image_series = calls.rec('wait_end')
    for name in ('close_image_series', '_abort_image_series', '_run_acquisition_continuous', 'run_acquisition'):
        setattr(core, name, getattr(mesoSPIM_Core, name).__get__(core))
    return core


def test_full_stack_launches_once_and_tears_down():
    core = make_core(steps=20)
    core._run_acquisition_continuous(core.acq, None)
    assert core.camera_worker.cur_image == 20 and core.image_count == 20
    assert core.calls.count('launch') == 1
    assert core.calls.index('laser_on') < core.calls.index('launch') < core.calls.index('stop_tasks') < core.calls.index('laser_off')
    assert 'close_shutters' in core.calls and 'close_tasks' not in core.calls  # closed later by close_acquisition()


def test_missed_triggers_end_the_stack_and_are_reported(caplog):
    core = make_core(steps=20, deliver=17, period=0.0005)
    core.waveformer.continuous_plane_period = -0.5  # deadline already passed once frames stop: keep the test fast
    with caplog.at_level('ERROR'):
        core._run_acquisition_continuous(core.acq, None)
    assert core.camera_worker.cur_image <= 17
    assert 'most likely missed triggers' in caplog.text  # camera reported nothing more
    assert 'stop_tasks' in core.calls and 'laser_off' in core.calls


def test_frames_lost_in_the_camera_buffer_are_reported_as_such(caplog):
    core = make_core(steps=20, deliver=17)
    core.waveformer.continuous_plane_period = -0.5
    core.camera_worker.camera = types.SimpleNamespace(max_frame_count=20)  # PVCAM captured all 20
    with caplog.at_level('ERROR'):
        core._run_acquisition_continuous(core.acq, None)
    assert 'overwritten' in caplog.text and 'series_buffer_frames' in caplog.text


def test_stop_mid_stack_releases_tasks_and_closes_the_series():
    core = make_core(steps=50, stop_at=10)
    core._run_acquisition_continuous(core.acq, None)
    assert core.camera_worker.cur_image == 10
    # stop in the finally, then the abort path: stop again, close, park, end the image series
    assert core.calls[-5:] == ['stop_tasks', 'close_tasks', 'park', 'wait_end'][-5:] or \
        core.calls[core.calls.index('close_tasks') - 1] == 'stop_tasks'
    assert core.calls.index('close_tasks') < core.calls.index('park') < core.calls.index('wait_end')
    assert core.sig_end_image_series.count == 1


def test_stop_before_launch_never_fires_the_stack():
    core = make_core(steps=50)
    core.stopflag = True
    core.run_acquisition(core.acq, None)
    assert 'launch' not in core.calls and 'laser_on' not in core.calls
    assert core.calls.index('close_tasks') < core.calls.index('park')
    assert core.sig_end_image_series.count == 1
    assert core.image_acq_end_time == core.image_acq_start_time  # close_acquisition() must not divide by it


def test_stepped_mode_close_does_not_park():
    core = make_core()
    core.continuous_acq_mode = False
    core.close_image_series()
    assert core.calls == ['close_tasks']
