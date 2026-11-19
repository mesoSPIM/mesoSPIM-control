"""
Live 'Hold laser ON' (Other tab): constant laser waveform, no per-frame blanking, AO parked at 0 V on stop.
Stub Core, waveformer and laser enabler (no hardware, no GUI).
"""
import os
import types
import numpy as np

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtWidgets

from mesoSPIM.src.mesoSPIM_Core import mesoSPIM_Core
from mesoSPIM.src.mesoSPIM_WaveFormGenerator import mesoSPIM_WaveFormGenerator

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class Signal:
    def __init__(self, fn=None):
        self.fn = fn

    def emit(self, *a):
        if self.fn:
            self.fn(*a)


class StubState(dict):
    def get_parameter_list(self, keys):
        return [self[k] for k in keys]


def make_waveformer(hold):
    wf = types.SimpleNamespace(laser_hold=hold, samples=1000,
                               cfg=types.SimpleNamespace(laserdict={'405 nm': 'a', '488 nm': 'b'}),
                               state=StubState({'samplerate': 100000, 'sweeptime': 0.01, 'laser_l_delay_%': 10,
                                                'laser_l_pulse_%': 80, 'max_laser_voltage': 5, 'intensity': 40,
                                                'laser': '488 nm'}))
    mesoSPIM_WaveFormGenerator.create_laser_waveforms(wf)
    return wf.laser_waveforms


def test_laser_waveform_pulsed_by_default_constant_when_held():
    pulsed = make_waveformer(False)
    assert pulsed[1, 0] == 0 and pulsed[1, -1] == 0 and pulsed[1].max() == 2.0
    held = make_waveformer(True)
    assert np.all(held[1] == 2.0)   # selected laser: constant at 40% of 5 V
    assert np.all(held[0] == 0)     # other laser lines stay off


def make_core(hold_schedule, lasers=None):
    """hold_schedule[i]: value of state['laser_hold_on'] seen at frame i; Live stops after the last frame."""
    calls = []
    core = types.SimpleNamespace(stopflag=False, cfg=types.SimpleNamespace(), calls=calls)
    core.state = {'laser': '488 nm', 'laser_hold_on': hold_schedule[0]}
    frame = {'i': 0}

    def snap_image(blanking):
        calls.append(('snap', blanking, core.waveformer.laser_hold))
        frame['i'] += 1
        if frame['i'] >= len(hold_schedule):
            core.stopflag = True
        else:
            core.state['laser_hold_on'] = hold_schedule[frame['i']]
            if lasers:
                core.state['laser'] = lasers[frame['i']]

    core.waveformer = types.SimpleNamespace(laser_hold=False,
                                            create_laser_waveforms=lambda: calls.append(('wf', core.waveformer.laser_hold)),
                                            park_ao_outputs=lambda: calls.append(('park',)))
    core.laserenabler = types.SimpleNamespace(enable=lambda l: calls.append(('on', l)),
                                              disable_all=lambda: calls.append(('off',)))
    core.snap_image = snap_image
    core.open_shutters = core.close_shutters = lambda: None
    for s in ('sig_prepare_live', 'sig_get_live_image', 'sig_end_live', 'sig_finished'):
        setattr(core, s, Signal())
    for name in ('live', '_update_live_laser_hold', '_release_live_laser_hold'):
        setattr(core, name, getattr(mesoSPIM_Core, name).__get__(core))
    return core


def test_live_without_hold_is_unchanged():
    core = make_core([False, False])
    core.live()
    assert [c for c in core.calls if c[0] == 'snap'] == [('snap', True, False)] * 2
    assert ('park',) not in core.calls and ('wf', True) not in core.calls


def test_live_with_hold_no_blanking_and_parked_on_stop():
    core = make_core([True, True, True])
    core.live()
    assert [c for c in core.calls if c[0] == 'snap'] == [('snap', False, True)] * 3
    assert core.calls.count(('wf', True)) == 1           # constant waveform made once
    assert core.calls[-3:] == [('wf', False), ('park',), ('off',)]  # pulsed waveform back, AO to 0 V, enable off
    assert core.waveformer.laser_hold is False


def test_hold_toggled_during_live_and_laser_change_reenables():
    core = make_core([False, True, True, False], lasers=[None, '488 nm', '405 nm', '405 nm'])
    core.live()
    snaps = [c for c in core.calls if c[0] == 'snap']
    assert snaps == [('snap', True, False), ('snap', False, True), ('snap', False, True), ('snap', True, False)]
    assert ('on', '405 nm') in core.calls                # switching laser while held re-enables the new line
    assert ('park',) not in core.calls                   # released before stop: the pulsed sweep ends at 0 V itself
