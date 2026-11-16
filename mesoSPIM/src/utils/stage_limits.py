'''
Software soft limits for the stages, the same for every stage type.

All moves pass mesoSPIM_Serial, which asks a StageLimitGuard before it calls the stage driver.
Limits are cfg.stage_parameters['<axis>_min'/'<axis>_max'] in physical stage coordinates
(not affected by ZERO).

Relative moves are checked against where the axis is heading, not only against the last
reported position: the position is polled every 100 ms, so fast button clicks would otherwise
each be checked against the same stale position and could add up past the limit. The guard
remembers the target of each accepted move; once no move has been commanded on that axis for
TARGET_HOLD_S, the reported position is used again.

Button moves (clamp=True) that would cross a limit are shortened to stop limit_guard_um inside
it. Programmatic moves (acquisition steps, scripts) are never shortened, only refused.
'''
import time

AXES = ('x', 'y', 'z', 'f', 'theta')
DEFAULT_LIMIT_GUARD_UM = 10.0
TARGET_HOLD_S = 1.0
_EPS = 1e-6


def limits_from_cfg(stage_parameters):
    '''{axis: (min, max)} for the axes that have both keys in stage_parameters.'''
    limits = {}
    for axis in AXES:
        low, high = stage_parameters.get(f'{axis}_min'), stage_parameters.get(f'{axis}_max')
        if low is not None and high is not None:
            limits[axis] = (float(low), float(high))
    return limits


def limit_guard_um(stage_parameters):
    '''Gap kept to the limit when a button move is shortened (µm; not used for theta).'''
    try:
        return max(0.0, float(stage_parameters.get('limit_guard_um', DEFAULT_LIMIT_GUARD_UM)))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT_GUARD_UM


def _unit(axis):
    return '°' if axis == 'theta' else ' µm'


def _violation(value, low, high):
    '''How far value is outside [low, high]; 0 inside.'''
    return max(low - value, value - high, 0.0)


def limit_status(position, low, high, step, guard=0.0):
    '''Where an axis is relative to its limits, for the GUI.

    Args:
        position: physical position.
        low, high: limits.
        step: current button step size (> 0).
        guard: gap kept to the limit by shortened button moves.

    Returns:
        (at_low, at_high, near): at_low/at_high when a button move toward that limit can't
        move any more; near when within one step (+ guard) of a limit.
    '''
    step = abs(step)
    at_low = position <= low + guard + _EPS
    at_high = position >= high - guard - _EPS
    near = at_low or at_high or position - low <= step + guard or high - position <= step + guard
    return at_low, at_high, near


class StageLimitGuard:
    '''Checks moves against the soft limits and remembers where each axis is heading.'''

    def __init__(self, limits, guard_um=DEFAULT_LIMIT_GUARD_UM, hold_s=TARGET_HOLD_S, clock=time.monotonic):
        self.limits = dict(limits)
        self.guard_um = guard_um
        self.hold_s = hold_s
        self.clock = clock
        self._targets = {}  # axis -> (physical target, time of command)

    def _guard(self, axis):
        return 0.0 if axis == 'theta' else self.guard_um

    def heading(self, axis, reported):
        '''Where the axis is going: the last commanded target while it is recent, else the reported position.'''
        target = self._targets.get(axis)
        if target is not None and self.clock() - target[1] < self.hold_s:
            return target[0]
        return reported

    def forget(self, axes=None):
        '''Drop remembered targets (after Stop, or a move that bypassed the guard).'''
        if axes is None:
            self._targets.clear()
        else:
            for axis in axes:
                self._targets.pop(axis, None)

    def accept(self, axis, target):
        '''Remember that axis was commanded to the physical target (call after executing a checked move).'''
        if axis in self.limits:
            self._targets[axis] = (target, self.clock())

    def check_relative(self, axis, step, reported, clamp=False):
        '''Check a relative move of one axis.

        Args:
            axis: 'x', 'y', 'z', 'f' or 'theta'.
            step: requested step (physical units; µm or °).
            reported: last reported physical position of the axis.
            clamp: shorten a move that would cross a limit (button moves) instead of refusing it.

        Returns:
            (step, target, message): step to execute (the requested one, a shortened one, or
            None when refused), the physical position it ends at (None when refused), and a
            message (None when the requested step is fine and, for button moves, does not end at
            the limit). Nothing is remembered: call
            accept(axis, target) once the move was sent.
        '''
        if axis not in self.limits or step == 0:
            return step, None, None
        low, high = self.limits[axis]
        base = self.heading(axis, reported)
        new = base + step
        limit_name, limit = (f'{axis}_max', high) if step > 0 else (f'{axis}_min', low)
        unit = _unit(axis)
        # Inside the limits, or moving back toward them from outside: fine.
        if _violation(new, low, high) <= _EPS or _violation(new, low, high) < _violation(base, low, high):
            # A button step ending where limit_status() greys out its arrow: say so, or the operator
            # only sees a dead button.
            guard = self._guard(axis)
            if clamp and (new >= high - guard - _EPS if step > 0 else new <= low + guard + _EPS):
                return step, new, f'{axis.upper()} reached the soft limit ({limit_name} = {limit:g}{unit}).'
            return step, new, None
        if clamp:
            stop_at = high - self._guard(axis) if step > 0 else low + self._guard(axis)
            allowed = stop_at - base
            if allowed * step > 0 and abs(allowed) > 1e-3:
                return allowed, stop_at, (f'{axis.upper()} stopped at the soft limit: moved {allowed:.1f}{unit} '
                                 f'instead of {step:.1f}{unit} ({limit_name} = {limit:g}{unit}).')
            return None, None, (f'{axis.upper()} is at the soft limit ({limit_name} = {limit:g}{unit}): '
                          f'no move toward it.')
        return None, None, (f'{axis.upper()} move of {step:.1f}{unit} refused: it would end at {new:.1f}{unit}, '
                      f'beyond {limit_name} = {limit:g}{unit} (from {base:.1f}{unit}; physical coordinates).')

    def check_absolute(self, axis, target):
        '''Check an absolute move to a physical target. Returns None if fine, else a message.
        Nothing is remembered: call accept(axis, target) once the move was sent.'''
        if axis not in self.limits:
            return None
        low, high = self.limits[axis]
        if low <= target <= high:
            return None
        unit = _unit(axis)
        return (f'{axis.upper()} move to {target:.1f}{unit} refused: outside the soft limits '
                f'({low:g}, {high:g}){unit} (physical coordinates).')


def acquisition_limit_violations(acq_list, limits, offsets):
    '''Positions of an acquisition list outside the soft limits.

    Args:
        acq_list: acquisitions (dict-like: x_pos, y_pos, z_start, z_end, f_start, f_end, rot),
            in GUI coordinates (with the ZERO offsets).
        limits: {axis: (min, max)}, physical coordinates.
        offsets: {axis: int_<axis>_pos_offset}; physical = GUI value - offset.

    Returns:
        list of (row, key, gui_value, physical_value, limit_name, limit) for every violation.
    '''
    keys = (('x', 'x_pos'), ('y', 'y_pos'), ('z', 'z_start'), ('z', 'z_end'),
            ('f', 'f_start'), ('f', 'f_end'), ('theta', 'rot'))
    violations = []
    for row, acq in enumerate(acq_list):
        for axis, key in keys:
            if axis not in limits:
                continue
            try:
                value = float(acq[key])
            except (KeyError, TypeError, ValueError):
                continue
            physical = value - offsets.get(axis, 0.0)
            low, high = limits[axis]
            if physical < low:
                violations.append((row, key, value, physical, f'{axis}_min', low))
            elif physical > high:
                violations.append((row, key, value, physical, f'{axis}_max', high))
    return violations


def format_violations(violations, max_lines=10):
    '''Human-readable text for acquisition_limit_violations(); rows are 1-based as in the table.'''
    lines = []
    for row, key, value, physical, limit_name, limit in violations[:max_lines]:
        shown = f'{value:g}' if value == physical else f'{value:g} (physical {physical:g})'
        relation = '<' if limit_name.endswith('_min') else '>'
        lines.append(f'row {row + 1}: {key} = {shown} {relation} {limit_name} = {limit:g}')
    if len(violations) > max_lines:
        lines.append(f'... and {len(violations) - max_lines} more')
    return '\n'.join(lines)
