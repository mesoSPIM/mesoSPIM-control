"""
Continuous-regeneration DAQ task setup, against a fake nidaqmx (no NI hardware or driver needed).

The property that matters: the camera and stage counter pulse trains must repeat with
exactly the AO waveform's period, otherwise the light sheet slides against the rolling
shutter a little more on every plane.
"""
import types
import numpy as np
import pytest
from PyQt5 import QtCore

import mesoSPIM.src.mesoSPIM_WaveFormGenerator as W
from mesoSPIM.src.utils.waveforms import samples_per_sweep, single_pulse, tunable_lens_ramp, sawtooth, square


# ---------------------------------------------------------------- fake nidaqmx
class FakeDaqError(Exception):
    pass


class FakeChannel:
    def __init__(self, kind, **kw):
        self.kind, self.kw = kind, kw
        self.co_pulse_freq = kw.get('freq')


class FakeCollection:
    def __init__(self, task):
        self.task = task

    def add_ao_voltage_chan(self, lines, **kw):
        self.task.channels.append(FakeChannel('ao', lines=lines, **kw))

    def add_do_chan(self, lines, **kw):
        self.task.channels.append(FakeChannel('do', lines=lines, **kw))

    def add_co_pulse_chan_ticks(self, line, **kw):
        if FakeNI.refuse_tick_source:
            raise FakeDaqError(f"route {kw['source_terminal']} -> {line} not supported")
        ch = FakeChannel('ticks', line=line, **kw)
        self.task.channels.append(ch)
        return ch

    def add_co_pulse_chan_freq(self, line, **kw):
        ch = FakeChannel('freq', line=line, **kw)
        ch.co_pulse_freq = FakeNI.coerce_freq(kw['freq'])
        self.task.channels.append(ch)
        return ch


class FakeTiming:
    def __init__(self, task):
        self.task, self.samp_clk_rate, self._term, self.cfg = task, None, None, {}

    @property
    def samp_clk_term(self):
        if FakeNI.refuse_clock_term:
            raise FakeDaqError('Specified property is not supported by the device (-200452)')
        return self._term

    def cfg_samp_clk_timing(self, rate, **kw):
        self.cfg = dict(rate=rate, **kw)
        self.samp_clk_rate = FakeNI.coerce_rate(rate)
        self._term = '/Dev1/ao/SampleClock'

    def cfg_implicit_timing(self, **kw):
        self.cfg = kw


class FakeTask:
    def __init__(self):
        self.channels, self.closed, self.started, self.trigger, self.written = [], False, False, None, None
        self.ao_channels = self.do_channels = self.co_channels = FakeCollection(self)
        self.timing = FakeTiming(self)
        self.out_stream = types.SimpleNamespace(regen_mode=None)
        self.triggers = types.SimpleNamespace(start_trigger=types.SimpleNamespace(
            cfg_dig_edge_start_trig=lambda src: setattr(self, 'trigger', src)))
        FakeNI.tasks.append(self)

    def control(self, mode):
        pass

    def write(self, data, auto_start=False):
        self.written = data

    def start(self):
        self.started = True

    def stop(self):
        pass

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeNI:
    tasks = []
    refuse_tick_source = False
    refuse_clock_term = False  # PXI-6733: DAQmx_SampClk_Term not readable
    coerce_rate = staticmethod(lambda r: r)
    coerce_freq = staticmethod(lambda f: f)
    Task = FakeTask


@pytest.fixture
def ni(monkeypatch):
    FakeNI.tasks = []
    FakeNI.refuse_tick_source = False
    FakeNI.refuse_clock_term = False
    FakeNI.coerce_rate = staticmethod(lambda r: r)
    FakeNI.coerce_freq = staticmethod(lambda f: f)
    monkeypatch.setattr(W, 'nidaqmx', FakeNI)
    monkeypatch.setattr(W, 'DaqError', FakeDaqError)
    for name in ('AcquisitionType', 'TaskMode', 'LineGrouping', 'RegenerationMode', 'Level'):
        if getattr(W, name) is None:
            monkeypatch.setattr(W, name, types.SimpleNamespace(
                FINITE='FINITE', CONTINUOUS='CONTINUOUS', TASK_RESERVE='RESERVE',
                CHAN_FOR_ALL_LINES='ALL', ALLOW_REGENERATION='REGEN', LOW='LOW'))
    return FakeNI


# ---------------------------------------------------------------- waveformer under test
class State(dict):
    def get_parameter_list(self, keys):
        return [self[k] for k in keys]


PXI_6733 = dict(waveformgeneration='NI', hw={
    'master_trigger_out_line': 'PXI1Slot4/port0/line0', 'camera_trigger_source': '/PXI1Slot4/PFI0',
    'camera_trigger_out_line': '/PXI1Slot4/ctr0', 'galvo_etl_task_line': 'PXI1Slot4/ao0:3',
    'galvo_etl_task_trigger_source': '/PXI1Slot4/PFI0', 'laser_task_line': 'PXI1Slot4/ao4:7',
    'laser_task_trigger_source': '/PXI1Slot4/PFI0'},
    asi={'stage_trigger_source': '/PXI1Slot4/PFI0', 'stage_trigger_out_line': '/PXI1Slot4/ctr1',
         'stage_trigger_delay_%': 92.5, 'stage_trigger_pulse_%': 1})

CDAQ = dict(waveformgeneration='cDAQ', hw={
    'master_trigger_out_line': 'cDAQ1Mod1/port0/line0', 'camera_trigger_source': '/cDAQ1Mod1/PFI4',
    'camera_trigger_out_line': '/cDAQ1Mod1/ctr0', 'galvo_etl_task_line': 'cDAQ1Mod3/ao0:3',
    'galvo_etl_task_trigger_source': '/cDAQ1Mod1/PFI4', 'laser_task_line': 'cDAQ1Mod3/ao4:7',
    'laser_task_trigger_source': '/cDAQ1Mod1/PFI4'},
    asi={'stage_trigger_source': '/cDAQ1Mod1/PFI4', 'stage_trigger_out_line': '/cDAQ1Mod1/ctr2',
         'stage_trigger_delay_%': 92.5, 'stage_trigger_pulse_%': 1})


def make_waveformer(rig, samplerate, sweeptime, camera_delay=10, camera_pulse=1):
    wf = W.mesoSPIM_WaveFormGenerator.__new__(W.mesoSPIM_WaveFormGenerator)
    QtCore.QObject.__init__(wf)  # skip __init__: it needs a full Core parent and the NI driver
    wf.MAX_GALVO_ETL_VOLT = 5
    wf.cfg = types.SimpleNamespace(acquisition_hardware=rig['hw'], waveformgeneration=rig['waveformgeneration'],
                                   stage_parameters={'stage_type': 'TigerASI'}, asi_parameters=rig['asi'])
    wf.parent = types.SimpleNamespace(read_config_parameter=lambda key, d: d[key])
    wf.state = State(samplerate=samplerate, sweeptime=sweeptime, max_laser_voltage=5.0,
                     **{'camera_delay_%': camera_delay, 'camera_pulse_%': camera_pulse})
    wf.calculate_samples()
    n = wf.samples
    wf.galvo_and_etl_waveforms = np.vstack([np.linspace(-1, 1, n)] * 4)
    wf.laser_waveforms = np.vstack([single_pulse(samplerate, sweeptime, 10, 87, 5.0)] * 4)
    return wf


def counters(ni):
    return [ch for t in ni.tasks for ch in t.channels if ch.kind in ('ticks', 'freq')]


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize('samplerate,sweeptime,expected', [
    (25000, 0.073, 1825),      # 25000*0.073 == 1824.9999999999998: truncating gave 1824 -> 40 us/plane drift
    (100000, 0.08333, 8333),   # 12 FPS on the PXI-6733 config
    (100000, 0.26734, 26734),
])
def test_every_waveform_has_the_same_rounded_length(samplerate, sweeptime, expected):
    assert samples_per_sweep(samplerate, sweeptime) == expected
    assert len(single_pulse(samplerate, sweeptime, 10, 87, 5)) == expected
    assert len(tunable_lens_ramp(samplerate, sweeptime, 5, 90, 5, 0.7, 2.3)) == expected
    assert len(sawtooth(samplerate, sweeptime, 99.9, 0.8, -0.38, 50, 0.4)) == expected
    assert len(square(samplerate, sweeptime, 99.9, 0.8, -0.38, 50, 0.4)) == expected


@pytest.mark.parametrize('rig', [PXI_6733, CDAQ], ids=['PXI-6733', 'cDAQ-9264'])
@pytest.mark.parametrize('samplerate,sweeptime', [(100000, 0.08333), (25000, 0.073)])
def test_counters_count_ao_sample_clock_ticks(ni, rig, samplerate, sweeptime):
    wf = make_waveformer(rig, samplerate, sweeptime)
    wf.create_tasks_continuous(1001)
    assert wf.continuous_timing_mode == 'ao_sample_clock_ticks'
    ao = wf.galvo_etl_laser_task
    assert ao.timing.cfg['sample_mode'] == W.AcquisitionType.CONTINUOUS
    assert ao.out_stream.regen_mode == W.RegenerationMode.ALLOW_REGENERATION
    cam, stage = counters(ni)
    for ch in (cam, stage):
        assert ch.kind == 'ticks' and ch.kw['source_terminal'] == ao.timing.samp_clk_term
        assert ch.kw['low_ticks'] + ch.kw['high_ticks'] == wf.samples  # period == AO buffer, exactly
    cam_task, stage_task = wf.camera_trigger_task, wf.stage_trigger_task
    assert cam_task.timing.cfg['samps_per_chan'] == 1001 and stage_task.timing.cfg['samps_per_chan'] == 1000
    assert cam_task.trigger is None and stage_task.trigger is None  # started by the AO clock itself
    assert cam.kw['initial_delay'] == round(wf.samples * 0.10)
    assert stage.kw['initial_delay'] == round(wf.samples * 0.925)
    assert wf.continuous_plane_period == pytest.approx(wf.samples / samplerate)


def test_names_the_ao_clock_when_the_device_cannot_report_it(ni):
    ni.refuse_clock_term = True
    wf = make_waveformer(PXI_6733, 100000, 0.08333)
    wf.create_tasks_continuous(601)
    assert wf.continuous_timing_mode == 'ao_sample_clock_ticks'
    assert {ch.kw['source_terminal'] for ch in counters(ni)} == {'/PXI1Slot4/ao/SampleClock'}


def test_falls_back_to_time_matched_counters(ni):
    ni.refuse_tick_source = True
    wf = make_waveformer(PXI_6733, 100000, 0.08333)
    wf.create_tasks_continuous(1001)
    assert wf.continuous_timing_mode == 'time_matched'
    cam, stage = counters(ni)
    assert cam.kind == stage.kind == 'freq'
    assert 1.0 / cam.kw['freq'] == pytest.approx(8333 / 100000)  # the AO's period, not 1/sweeptime
    assert wf.camera_trigger_task.trigger == '/PXI1Slot4/PFI0'
    assert not any(t.closed for t in (wf.camera_trigger_task, wf.stage_trigger_task, wf.galvo_etl_laser_task))


def test_fallback_uses_the_coerced_ao_rate(ni):
    ni.refuse_tick_source = True
    ni.coerce_rate = staticmethod(lambda r: 99999.0)  # driver could not hit 100 kS/s exactly
    wf = make_waveformer(PXI_6733, 100000, 0.08333)
    wf.create_tasks_continuous(1001)
    cam = counters(ni)[0]
    assert 1.0 / cam.kw['freq'] == pytest.approx(8333 / 99999.0)


def test_fallback_refuses_a_drifting_counter_and_releases_every_task(ni):
    ni.refuse_tick_source = True
    ni.coerce_freq = staticmethod(lambda f: f * (1 + 1e-5))  # counter timebase cannot hit the period
    wf = make_waveformer(CDAQ, 25000, 0.073)
    with pytest.raises(RuntimeError, match='drift'):
        wf.create_tasks_continuous(1001)
    assert ni.tasks and all(t.closed for t in ni.tasks)
    assert wf.camera_trigger_task is None and wf.galvo_etl_laser_task is None


def test_rejects_waveforms_that_do_not_match_the_period(ni):
    wf = make_waveformer(PXI_6733, 25000, 0.073)
    wf.laser_waveforms = wf.laser_waveforms[:, :-1]  # e.g. a truncated waveform builder
    with pytest.raises(RuntimeError, match='samples per sweep'):
        wf.create_tasks_continuous(10)
    assert all(t.closed for t in ni.tasks)


def test_park_holds_the_last_sample_lasers_off(ni):
    wf = make_waveformer(PXI_6733, 100000, 0.08333)
    wf.create_tasks_continuous(5)
    wf.close_tasks()
    wf.park_ao_outputs()
    park = ni.tasks[-1]
    assert park.channels[0].kw['lines'] == 'PXI1Slot4/ao0:3,PXI1Slot4/ao4:7'
    assert park.written[:4] == pytest.approx([1.0] * 4)   # galvo/ETL at the sweep end
    assert park.written[4:] == pytest.approx([0.0] * 4)   # lasers off
    assert park.closed
