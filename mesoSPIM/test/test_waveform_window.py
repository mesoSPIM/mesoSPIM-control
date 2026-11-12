"""
Waveform viewer (Waveforms tab, "Show waveforms"): the traces of one sweep on a common time axis.
No hardware; the waveforms come from the real waveform functions.
"""
import os
import types

import numpy as np
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtWidgets

from mesoSPIM.src.mesoSPIM_WaveformWindow import waveform_traces, mesoSPIM_WaveformWindow, TTL_VOLTS
from mesoSPIM.src.utils.waveforms import sawtooth, tunable_lens_ramp, single_pulse

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

STATE = {'samplerate': 100000, 'sweeptime': 0.2, 'laser': '488 nm', 'camera_delay_%': 10, 'camera_pulse_%': 1,
         'shutterconfig': 'Right', 'intensity': 10}


def make_waveformer(samplerate=100000, sweeptime=0.2):
    kw = dict(samplerate=samplerate, sweeptime=sweeptime)
    return types.SimpleNamespace(
        galvo_l_waveform=sawtooth(frequency=99.9, amplitude=2.5, offset=0, dutycycle=50, phase=np.pi / 2, **kw),
        galvo_r_waveform=sawtooth(frequency=99.9, amplitude=2.5, offset=0, dutycycle=50, phase=np.pi / 2, **kw),
        etl_l_waveform=tunable_lens_ramp(delay=7.5, rise=85, fall=2.5, amplitude=0.5, offset=2.4, **kw),
        etl_r_waveform=tunable_lens_ramp(delay=2.5, rise=5, fall=85, amplitude=0.4, offset=2.5, **kw),
        laser_template_waveform=single_pulse(delay=10, pulsewidth=87, amplitude=0.5, offset=0, **kw))


def cfg(stage_type='DemoStage', asi=None):
    c = types.SimpleNamespace(stage_parameters={'stage_type': stage_type})
    if asi is not None:
        c.asi_parameters = asi
    return c


def test_common_time_axis_one_sweep():
    t_ms, rows = waveform_traces(make_waveformer(), STATE, cfg())
    assert t_ms[0] == 0 and len(t_ms) == 20000
    assert t_ms[-1] == pytest.approx(200.0, abs=0.011)  # one sweep, in ms
    assert [title for title, _, _ in rows] == ['Galvos', 'ETLs', 'Laser', 'Camera trigger']
    for _, _, traces in rows:
        for _, _, y in traces:
            assert len(y) == len(t_ms)


def test_camera_trigger_from_delay_and_pulse():
    t_ms, rows = waveform_traces(make_waveformer(), STATE, cfg())
    (_, _, y), = rows[3][2]
    high = t_ms[y > 0]
    assert y.max() == TTL_VOLTS
    assert high[0] == pytest.approx(20.0, abs=0.02)        # 10 % of 200 ms
    assert high[-1] - high[0] == pytest.approx(2.0, abs=0.02)  # 1 % of 200 ms


def test_stage_trigger_only_for_asi_stages():
    asi = {'stage_trigger_delay_%': 92.5, 'stage_trigger_pulse_%': 1}
    _, rows = waveform_traces(make_waveformer(), STATE, cfg('ASI', asi))
    assert rows[-1][0] == 'Stage trigger'
    _, rows = waveform_traces(make_waveformer(), STATE, cfg('PI_1controllerNstages', asi))
    assert rows[-1][0] == 'Camera trigger'


def test_traces_padded_to_galvo_length():
    wf = make_waveformer()
    wf.etl_l_waveform = wf.etl_l_waveform[:-5]  # e.g. being recreated with another sweep time
    t_ms, rows = waveform_traces(wf, STATE, cfg())
    assert all(len(y) == len(t_ms) for _, _, traces in rows for _, _, y in traces)


def test_window_draws_and_follows_laser_change():
    parent = types.SimpleNamespace(state=dict(STATE), cfg=cfg(), core=types.SimpleNamespace(waveformer=make_waveformer()))
    window = mesoSPIM_WaveformWindow(parent)
    assert len(window.plots) == 4
    parent.state['laser'] = '561 nm'
    window.refresh()
    assert window.plots[2].legend.items[0][1].text == 'Laser 561 nm'
    window.close()
