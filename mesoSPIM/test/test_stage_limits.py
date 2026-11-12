"""Soft stage limits for every stage type (utils/stage_limits.py, mesoSPIM_Serial, Core pre-flight).

Run: python -m pytest mesoSPIM/test/test_stage_limits.py
"""
import logging
from types import SimpleNamespace

import pytest

from mesoSPIM.src.utils.stage_limits import (
    StageLimitGuard, limits_from_cfg, limit_guard_um, limit_status,
    acquisition_limit_violations, format_violations, DEFAULT_LIMIT_GUARD_UM)

STAGE = {'x_min': -1000, 'x_max': 1000, 'y_min': -2000, 'y_max': 2000, 'z_min': 0, 'z_max': 5000,
         'f_min': 0, 'f_max': 10000, 'theta_min': -90, 'theta_max': 90}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def make_guard(guard_um=10.0):
    clock = Clock()
    return StageLimitGuard(limits_from_cfg(STAGE), guard_um, hold_s=1.0, clock=clock), clock


# --- config ---------------------------------------------------------------------------------------

def test_limits_from_cfg_skips_incomplete_axes():
    limits = limits_from_cfg({'x_min': -1, 'x_max': 1, 'z_min': 0})
    assert limits == {'x': (-1.0, 1.0)}


def test_limit_guard_um_default_and_bad_values():
    assert limit_guard_um({}) == DEFAULT_LIMIT_GUARD_UM
    assert limit_guard_um({'limit_guard_um': 25}) == 25.0
    assert limit_guard_um({'limit_guard_um': -5}) == 0.0
    assert limit_guard_um({'limit_guard_um': 'x'}) == DEFAULT_LIMIT_GUARD_UM


# --- relative moves -------------------------------------------------------------------------------

def test_move_inside_limits_is_unchanged():
    guard, _ = make_guard()
    assert guard.check_relative('x', 100, 0) == (100, 100, None)


def test_programmatic_move_across_a_limit_is_refused_not_shortened():
    guard, _ = make_guard()
    step, target, message = guard.check_relative('z', 100, 4950)
    assert step is None and target is None
    assert 'refused' in message and 'z_max = 5000' in message


def test_button_move_is_shortened_to_stop_inside_the_limit():
    guard, _ = make_guard(guard_um=10)
    step, target, message = guard.check_relative('x', 500, 800, clamp=True)
    assert step == pytest.approx(190) and target == pytest.approx(990)
    assert 'stopped at the soft limit' in message
    step, target, _ = guard.check_relative('x', -500, -800, clamp=True)
    assert step == pytest.approx(-190) and target == pytest.approx(-990)


def test_button_at_the_limit_does_not_move_toward_it_but_can_move_away():
    guard, _ = make_guard(guard_um=10)
    step, target, message = guard.check_relative('x', 100, 995, clamp=True)
    assert step is None and 'at the soft limit' in message
    assert guard.check_relative('x', -100, 995, clamp=True)[0] == -100


def test_the_old_three_step_margin_is_gone():
    # 600 from the limit with a 250 step: the old check (pos + 3 * step) refused this.
    guard, _ = make_guard()
    assert guard.check_relative('y', 250, 1400)[0] == 250


def test_fast_clicks_are_checked_against_where_the_axis_is_heading():
    guard, clock = make_guard(guard_um=0)
    reported = 0.0  # position not updated yet: all clicks within the 100 ms poll
    for expected in (300, 300, 300):
        step, target, _ = guard.check_relative('x', 300, reported, clamp=True)
        assert step == expected
        guard.accept('x', target)
        clock.t += 0.05
    step, target, message = guard.check_relative('x', 300, reported, clamp=True)
    assert step == pytest.approx(100) and target == pytest.approx(1000)  # 900 + 100, not 0 + 300
    guard.accept('x', target)
    assert guard.check_relative('x', 300, reported, clamp=True)[0] is None


def test_remembered_target_expires_and_the_reported_position_is_used():
    guard, clock = make_guard()
    guard.accept('x', 900)
    assert guard.heading('x', 0) == 900
    clock.t += 1.5
    assert guard.heading('x', 0) == 0
    guard.accept('x', 900)
    guard.forget()
    assert guard.heading('x', 0) == 0


def test_check_does_not_remember_until_accepted():
    guard, _ = make_guard()
    guard.check_relative('x', 500, 0)
    assert guard.heading('x', 0) == 0


def test_moving_back_toward_the_range_from_outside_is_allowed():
    guard, _ = make_guard()
    assert guard.check_relative('z', 50, -200)[0] == 50     # still outside, but closer
    assert guard.check_relative('z', -50, -200)[0] is None  # further out


def test_theta_has_no_guard_gap_and_degree_units():
    guard, _ = make_guard(guard_um=10)
    step, target, message = guard.check_relative('theta', 20, 80, clamp=True)
    assert step == pytest.approx(10) and target == pytest.approx(90)
    assert '°' in message


def test_axis_without_limits_is_not_checked():
    guard = StageLimitGuard({'x': (-1, 1)}, 0)
    assert guard.check_relative('z', 1e6, 0) == (1e6, None, None)
    assert guard.check_absolute('z', 1e6) is None


# --- absolute moves -------------------------------------------------------------------------------

def test_absolute_move_checks_the_target():
    guard, _ = make_guard()
    assert guard.check_absolute('f', 5000) is None
    message = guard.check_absolute('f', 12000)
    assert 'refused' in message and '(0, 10000)' in message


# --- GUI cue --------------------------------------------------------------------------------------

def test_limit_status():
    assert limit_status(0, -1000, 1000, 100) == (False, False, False)
    assert limit_status(950, -1000, 1000, 100) == (False, False, True)
    assert limit_status(995, -1000, 1000, 100, guard=10) == (False, True, True)
    assert limit_status(-1000, -1000, 1000, 100) == (True, False, True)


# --- acquisition list pre-flight ------------------------------------------------------------------

def acq(**values):
    row = dict(x_pos=0, y_pos=0, z_start=100, z_end=200, f_start=5000, f_end=5000, rot=0)
    row.update(values)
    return row


def test_acquisition_list_checks_all_axes_including_f_and_rotation():
    limits = limits_from_cfg(STAGE)
    rows = [acq(), acq(f_end=12000), acq(rot=120), acq(z_end=5100), acq(x_pos=-1500)]
    violations = acquisition_limit_violations(rows, limits, {})
    assert [(row, key) for row, key, *_ in violations] == [(1, 'f_end'), (2, 'rot'), (3, 'z_end'), (4, 'x_pos')]
    text = format_violations(violations)
    assert 'row 2: f_end = 12000 > f_max = 10000' in text
    assert 'row 5: x_pos = -1500 < x_min = -1000' in text


def test_acquisition_list_uses_physical_coordinates_after_zero():
    limits = limits_from_cfg(STAGE)
    # Z zeroed at physical 4900: int offset -4900; GUI z_end 150 is physical 5050 > z_max.
    violations = acquisition_limit_violations([acq(z_start=0, z_end=150)], limits, {'z': -4900})
    assert [(key, physical) for _r, key, _v, physical, *_ in violations] == [('z_end', 5050)]
    assert 'physical 5050' in format_violations(violations)


def test_format_violations_truncates():
    violations = [(i, 'x_pos', 2000, 2000, 'x_max', 1000) for i in range(15)]
    assert format_violations(violations).endswith('... and 5 more')


# --- mesoSPIM_Serial -----------------------------------------------------------------------------

class FakeStage:
    def __init__(self):
        for axis in ('x', 'y', 'z', 'f', 'theta'):
            setattr(self, f'{axis}_pos', 0.0)
            setattr(self, f'int_{axis}_pos_offset', 0.0)
        self.relative, self.absolute = [], []

    def move_relative(self, sdict, wait_until_done=False):
        self.relative.append(dict(sdict))

    def move_absolute(self, sdict, wait_until_done=False, use_internal_position=True):
        self.absolute.append(dict(sdict))


def make_serial():
    from mesoSPIM.src.mesoSPIM_Serial import mesoSPIM_Serial
    guard, clock = make_guard(guard_um=10)
    messages, refused = [], []
    fake = SimpleNamespace(stage=FakeStage(), limit_guard=guard, stage_limits_warning=False,
                           send_status_message=messages.append,
                           sig_move_refused=SimpleNamespace(emit=refused.append))
    fake._limit_message = lambda message, refused_programmatic=False: \
        mesoSPIM_Serial._limit_message(fake, message, refused_programmatic)
    fake._clear_limit_message = lambda: mesoSPIM_Serial._clear_limit_message(fake)
    return mesoSPIM_Serial, fake, messages, refused, clock


def test_serial_button_move_is_shortened_and_warned(caplog):
    Serial, fake, messages, refused, _ = make_serial()
    fake.stage.x_pos = 900.0
    with caplog.at_level(logging.WARNING):
        assert Serial.move_relative(fake, {'x_rel': 500.0}, clamp=True)
    assert fake.stage.relative == [{'x_rel': pytest.approx(90.0)}]
    assert 'stopped at the soft limit' in messages[-1] and not refused
    assert any(r.levelno == logging.WARNING and 'x_max = 1000' in r.getMessage() for r in caplog.records)
    # next click: at the limit, nothing sent
    assert not Serial.move_relative(fake, {'x_rel': 500.0}, clamp=True)
    assert len(fake.stage.relative) == 1
    # a fine move clears the status message
    assert Serial.move_relative(fake, {'x_rel': -100.0}, clamp=True)
    assert messages[-1] == ''


def test_serial_programmatic_move_is_refused_whole_and_signalled():
    Serial, fake, messages, refused, _ = make_serial()
    fake.stage.z_pos = 4990.0
    assert not Serial.move_relative(fake, {'z_rel': 20.0, 'f_rel': 5.0})
    assert fake.stage.relative == [] and len(refused) == 1 and 'z_max' in refused[0]
    assert fake.limit_guard.heading('f', 0) == 0  # the allowed axis was not remembered either


def test_serial_absolute_move_uses_zero_offsets():
    Serial, fake, messages, refused, _ = make_serial()
    fake.stage.int_f_pos_offset = -9000.0  # F zeroed at physical 9000
    assert not Serial.move_absolute(fake, {'f_abs': 2000.0})  # physical 11000 > f_max
    assert fake.stage.absolute == [] and '11000.0' in refused[0] and '(0, 10000)' in refused[0]
    assert Serial.move_absolute(fake, {'f_abs': 500.0})  # physical 9500
    assert fake.stage.absolute == [{'f_abs': 500.0}]
    assert Serial.move_absolute(fake, {'f_abs': 11000.0}, use_internal_position=False) is False


def test_serial_fast_clicks_cannot_pass_the_limit():
    Serial, fake, messages, refused, clock = make_serial()
    fake.stage.y_pos = 1500.0  # reported position stays stale between polls
    sent = 0.0
    for _ in range(10):
        Serial.move_relative(fake, {'y_rel': 200.0}, clamp=True)
        clock.t += 0.02
    sent = sum(move['y_rel'] for move in fake.stage.relative)
    assert 1500.0 + sent == pytest.approx(1990.0)
