"""
Channel settings files (former ETL config files with optional absolute F positions): parsing and saving,
backwards compatibility with old ETL files, the missing / >500 um / stage-limit checks, the F-loading
on/off switch, and that F only moves after explicit approval. No hardware, no main window.
"""
import os
import types

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5 import QtWidgets

from mesoSPIM.src.utils import channel_settings as cs
from mesoSPIM.src.mesoSPIM_Core import mesoSPIM_Core
from mesoSPIM.src.mesoSPIM_WaveFormGenerator import mesoSPIM_WaveFormGenerator
from mesoSPIM.src.mesoSPIM_MainWindow import mesoSPIM_MainWindow

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

OLD_ETL = ("Objective;Wavelength;Zoom;ETL-Left-Offset;ETL-Left-Amp;ETL-Right-Offset;ETL-Right-Amp\n"
           "1x;488 nm;1x;2.0;1.0;2.1;0.9\n"
           "1x;561 nm;2x;2.5;0.5;2.6;0.4\n")
NEW = ("Objective;Wavelength;Zoom;ETL-Left-Offset;ETL-Left-Amp;ETL-Right-Offset;ETL-Right-Amp;F-Absolute-um\n"
       "1x;488 nm;1x;2.0;1.0;2.1;0.9;5100.5\n"
       "1x;561 nm;2x;2.5;0.5;2.6;0.4;\n"
       "1x;640 nm;2x;2.5;0.5;2.6;0.4;not-a-number\n")
ETL = {'etl_l_offset': 2.2, 'etl_l_amplitude': 0.8, 'etl_r_offset': 2.3, 'etl_r_amplitude': 0.7}


def write(tmp_path, text, name='ch.csv'):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def rows(path):
    import csv
    with open(path, newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


# ---------- parsing ----------
def test_old_etl_file_loads_without_f(tmp_path):
    s = cs.read_channel_settings(write(tmp_path, OLD_ETL), '561 nm', '2x')
    assert s == {'etl_l_offset': 2.5, 'etl_l_amplitude': 0.5, 'etl_r_offset': 2.6, 'etl_r_amplitude': 0.4,
                 'f_abs': None}


def test_new_file_f_present_empty_and_invalid(tmp_path):
    path = write(tmp_path, NEW)
    assert cs.read_channel_settings(path, '488 nm', '1x')['f_abs'] == 5100.5
    assert cs.read_channel_settings(path, '561 nm', '2x')['f_abs'] is None
    assert cs.read_channel_settings(path, '640 nm', '2x')['f_abs'] is None


def test_zoom_with_description_matches_clean_zoom_and_missing_row(tmp_path):
    path = write(tmp_path, NEW)
    assert cs.read_channel_settings(path, '488 nm', '1x Mitutoyo')['f_abs'] == 5100.5
    assert cs.read_channel_settings(path, '488 nm', '4x') is None


@pytest.mark.parametrize('value', ['nan', 'inf', ' ', None])
def test_parse_f_rejects_non_finite(value):
    assert cs.parse_f(value) is None


# ---------- saving ----------
def test_save_upgrades_old_file_and_keeps_other_rows(tmp_path):
    path = write(tmp_path, OLD_ETL)
    assert cs.write_channel_settings(path, '488 nm', '1x', ETL, 4999.987) is True
    r = rows(path)
    assert list(r[0].keys())[-1] == cs.F_COLUMN
    assert r[0]['F-Absolute-um'] == '4999.99' and r[0]['ETL-Left-Offset'] == '2.2'
    assert r[1]['F-Absolute-um'] == '' and r[1]['ETL-Left-Offset'] == '2.5'  # untouched row, F absent
    assert cs.read_channel_settings(path, '488 nm', '1x')['f_abs'] == 4999.99
    assert not os.path.exists(path + '_tmp')


def test_save_appends_new_channel_and_keeps_extra_columns(tmp_path):
    path = write(tmp_path, "Objective;Wavelength;Zoom;ETL-Left-Offset;ETL-Left-Amp;ETL-Right-Offset;ETL-Right-Amp;Note\n"
                           "1x;488 nm;1x;2.0;1.0;2.1;0.9;keep me\n")
    assert cs.write_channel_settings(path, '561 nm', '2x', ETL, None) is False
    r = rows(path)
    assert r[0]['Note'] == 'keep me' and r[1]['Wavelength'] == '561 nm' and r[1]['F-Absolute-um'] == ''
    cs.write_channel_settings(path, '488 nm', '1x', ETL, 100)
    assert rows(path)[0]['Note'] == 'keep me' and rows(path)[0]['F-Absolute-um'] == '100.0'


# ---------- checks ----------
@pytest.mark.parametrize('target, current, enabled, limits, expected', [
    (5000, 5000, False, None, cs.F_DISABLED),       # switch off: ignored, even when it would be fine
    (9999, 0, False, None, cs.F_DISABLED),
    (None, 5000, True, None, cs.F_MISSING),
    (5500.1, 5000, True, None, cs.F_TOO_FAR),
    (4499.9, 5000, True, None, cs.F_TOO_FAR),
    (5500, 5000, True, None, cs.F_OFFER),           # exactly 500 um is allowed
    (4600, 5000, True, (0, 98000), cs.F_OFFER),
    (5000.2, 5000, True, None, cs.F_IN_PLACE),
    (-10, 100, True, (0, 98000), cs.F_OUT_OF_LIMITS),
])
def test_evaluate_f_target(target, current, enabled, limits, expected):
    outcome, message = cs.evaluate_f_target(target, current, enabled, limits)
    assert outcome == expected
    assert bool(message) == (expected not in (cs.F_DISABLED, cs.F_IN_PLACE))


# ---------- Core: safety gate and approved move ----------
class Signal:
    def __init__(self):
        self.calls = []

    def emit(self, *a):
        self.calls.append(a)


def make_core(f_current=5000.0, enabled=True, state='idle'):
    core = types.SimpleNamespace()
    core.state = {'load_f_from_channel_file': enabled, 'state': state, 'laser': '488 nm', 'zoom': '1x',
                  'ETL_cfg_file': 'ch.csv', 'position_absolute': {'f_pos': f_current}}
    core.cfg = types.SimpleNamespace(stage_parameters={'f_min': 0, 'f_max': 98000})
    core.sig_warning, core.sig_offer_channel_f_position = Signal(), Signal()
    core.moves = []
    core.move_absolute = lambda sdict, wait_until_done=False, use_internal_position=True: \
        core.moves.append((sdict, wait_until_done, use_internal_position))
    core.send_status_message_to_gui = lambda s: None
    core._channel_f_check = lambda f: mesoSPIM_Core._channel_f_check(core, f)
    return core


def report(f_abs):
    return {'f_abs': f_abs, 'laser': '488 nm', 'zoom': '1x', 'file': 'ch.csv'}


def test_gate_offers_but_never_moves():
    core = make_core()
    mesoSPIM_Core.handle_channel_f_position(core, report(5200.0))
    assert core.moves == [] and core.sig_warning.calls == []
    (proposal,), = core.sig_offer_channel_f_position.calls
    assert proposal['f_abs'] == 5200.0 and proposal['f_current'] == 5000.0


@pytest.mark.parametrize('f_abs', [None, 5600.0, -5.0])
def test_gate_flags_missing_far_and_out_of_limits(f_abs):
    core = make_core(f_current=100.0 if f_abs == -5.0 else 5000.0)
    mesoSPIM_Core.handle_channel_f_position(core, report(f_abs))
    assert core.moves == [] and core.sig_offer_channel_f_position.calls == []
    assert len(core.sig_warning.calls) == 1


@pytest.mark.parametrize('f_abs', [None, 5600.0, 5200.0])
def test_switch_off_ignores_f_silently(f_abs):
    core = make_core(enabled=False)
    mesoSPIM_Core.handle_channel_f_position(core, report(f_abs))
    assert core.moves == [] and core.sig_offer_channel_f_position.calls == [] and core.sig_warning.calls == []


@pytest.mark.parametrize('state', ['run_acquisition_list', 'run_selected_acquisition', 'preview_acquisition',
                                   'running_script', 'snap', 'init'])
def test_no_offer_during_acquisitions(state):
    core = make_core(state=state)
    mesoSPIM_Core.handle_channel_f_position(core, report(5200.0))
    assert core.moves == [] and core.sig_offer_channel_f_position.calls == []


def test_approved_move_uses_physical_coordinates():
    core = make_core()
    assert mesoSPIM_Core.apply_channel_f_position(core, dict(report(5200.0), f_current=5000.0)) is True
    assert core.moves == [({'f_abs': 5200.0}, True, False)]


@pytest.mark.parametrize('change', [
    {'load_f_from_channel_file': False},
    {'state': 'run_acquisition_list'},
    {'laser': '561 nm'},
    {'zoom': '2x'},
    {'ETL_cfg_file': 'other.csv'},
    {'position_absolute': {'f_pos': 4600.0}},  # F moved since the offer: target now 600 um away
    {'position_absolute': {'f_pos': 5050.0}},  # F moved 50 um since the offer: approval is stale
])
def test_approval_rechecked_before_moving(change):
    core = make_core()
    core.state.update(change)
    assert mesoSPIM_Core.apply_channel_f_position(core, dict(report(5200.0), f_current=5000.0)) is False
    assert core.moves == []
    assert len(core.sig_warning.calls) == 1


# ---------- WaveFormGenerator: load reports F, save writes F ----------
class DictState(dict):
    def set_parameters(self, d):
        self.update(d)

    def get_parameter_list(self, keys):
        return [self[k] for k in keys]

    def get_parameter_dict(self, keys):
        return {k: self[k] for k in keys}


def make_waveformer(tmp_path, text):
    path = write(tmp_path, text)
    wf = types.SimpleNamespace()
    wf.parent = types.SimpleNamespace(package_directory=str(tmp_path), sig_warning=Signal())
    wf.state = DictState({'ETL_cfg_file': 'ch.csv', 'laser': '488 nm', 'zoom': '1x',
                          'position_absolute': {'f_pos': 4321.0}, **ETL})
    wf.sig_channel_f_position, wf.sig_update_gui_from_state = Signal(), Signal()
    wf.create_waveforms = lambda: None
    wf.save_etl_parameters_to_csv = lambda: mesoSPIM_WaveFormGenerator.save_etl_parameters_to_csv(wf)
    return wf, path


def test_waveformer_loads_old_file_and_reports_missing_f(tmp_path):
    wf, path = make_waveformer(tmp_path, OLD_ETL)
    mesoSPIM_WaveFormGenerator.update_etl_parameters_from_csv(wf, 'ch.csv', '561 nm', '2x')
    assert wf.state['etl_l_offset'] == 2.5
    (rep,), = wf.sig_channel_f_position.calls
    assert rep == {'f_abs': None, 'laser': '561 nm', 'zoom': '2x', 'file': 'ch.csv'}


def test_waveformer_missing_channel_saves_it_without_offering_f(tmp_path):
    wf, path = make_waveformer(tmp_path, OLD_ETL)
    mesoSPIM_WaveFormGenerator.update_etl_parameters_from_csv(wf, 'ch.csv', '488 nm', '4x')
    assert wf.sig_channel_f_position.calls == [] and len(wf.parent.sig_warning.calls) == 1


def test_waveformer_save_writes_absolute_f(tmp_path):
    wf, path = make_waveformer(tmp_path, OLD_ETL)
    mesoSPIM_WaveFormGenerator.save_etl_parameters_to_csv(wf)
    assert cs.read_channel_settings(path, '488 nm', '1x')['f_abs'] == 4321.0


# ---------- MainWindow: GUI switch and confirmation dialog ----------
def test_gui_switch_sets_state():
    win = types.SimpleNamespace(state={'load_f_from_channel_file': False})
    mesoSPIM_MainWindow.set_load_f_from_channel_file(win, True)
    assert win.state['load_f_from_channel_file'] is True
    mesoSPIM_MainWindow.set_load_f_from_channel_file(win, False)
    assert win.state['load_f_from_channel_file'] is False


def fake_box(monkeypatch, answers, shown):
    class FakeBox:
        Question, Yes, No = QtWidgets.QMessageBox.Question, QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No

        def __init__(self, *a):
            shown.append(a)

        def setDefaultButton(self, button):
            assert button == QtWidgets.QMessageBox.No  # "No" is the default

        def exec_(self):
            return answers.pop(0)

    monkeypatch.setattr(QtWidgets, 'QMessageBox', FakeBox)


def make_win(enabled=True):
    return types.SimpleNamespace(state={'load_f_from_channel_file': enabled}, _pending_channel_f=None,
                                 _channel_f_dialog_open=False, _channel_f_shown_key=None,
                                 _channel_f_last_key=None, sig_apply_channel_f_position=Signal())


@pytest.mark.parametrize('answer, enabled, applied', [
    (QtWidgets.QMessageBox.Yes, True, 1),
    (QtWidgets.QMessageBox.No, True, 0),
    (QtWidgets.QMessageBox.Yes, False, 0),  # switched off while the offer was queued: no dialog, no move
])
def test_dialog_requires_explicit_yes(monkeypatch, answer, enabled, applied):
    shown = []
    fake_box(monkeypatch, [answer], shown)
    win = make_win(enabled)
    mesoSPIM_MainWindow.offer_channel_f_position(win, dict(report(5200.0), f_current=5000.0))
    assert len(win.sig_apply_channel_f_position.calls) == applied
    assert len(shown) == (1 if enabled else 0)
    assert win._channel_f_dialog_open is False and win._channel_f_shown_key is None


def test_identical_offer_not_asked_twice(monkeypatch):
    # startup: zoom and laser initialization both reload the channel settings -> the same offer twice
    shown = []
    fake_box(monkeypatch, [QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No], shown)
    win = make_win()
    offer = dict(report(5200.0), f_current=5000.0)
    mesoSPIM_MainWindow.offer_channel_f_position(win, offer)
    mesoSPIM_MainWindow.offer_channel_f_position(win, dict(offer))
    assert len(shown) == 1
    # a different channel, or F moved meanwhile, is asked
    mesoSPIM_MainWindow.offer_channel_f_position(win, dict(offer, f_current=5100.0))
    assert len(shown) == 2
    # toggling the checkbox forgets the last answer: the same offer is asked again
    mesoSPIM_MainWindow.set_load_f_from_channel_file(win, True)
    mesoSPIM_MainWindow.offer_channel_f_position(win, dict(offer, f_current=5100.0))
    assert len(shown) == 3


def test_identical_offer_while_dialog_open_is_skipped():
    win = make_win()
    offer = dict(report(5200.0), f_current=5000.0)
    win._channel_f_dialog_open = True
    win._channel_f_shown_key = cs.channel_f_offer_key(offer)
    mesoSPIM_MainWindow.offer_channel_f_position(win, dict(offer))
    assert win._pending_channel_f is None
