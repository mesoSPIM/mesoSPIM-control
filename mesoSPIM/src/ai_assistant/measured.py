"""Measured values through the turn guard (roadmap E1), behind a setting that is off by default.

A value the operator did not give waits for their Run. With this setting on, one that follows from
code's own measurement passes without it, within bounds, when the measurement is fresh: the
newest frame was taken after the last move or setting, and code could measure from it.

- A move on x and y within MEASURED_TOLERANCE of the frame's centre_move_um and at most one field
  of view, and each next measured offset smaller than the last, in neither image direction larger
  (beyond MEASURED_SLACK_UM): a move that makes it worse on any axis (a wrong calibration sign)
  stops the next one, even while the other axis converges.
- A focus move to the map's best focus, or a search step of at most MEASURED_FOCUS_STEP_UM within
  MEASURED_FOCUS_RANGE_UM of where the request started.
- An intensity or exposure within a factor of MEASURED_LIGHT_FACTOR of the frame's.
- At most MEASURED_MOVES_MAX measured moves per request.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import math

from . import config
from .frames import flag, sample_map


class MeasuredValues:
    """What one request has done on measured values, and whether the next one follows from a
    fresh measurement. The turn guard asks it about a value the operator did not give."""

    def __init__(self, history):
        self.history = history
        self.reset(None)
        self.changed_at = float("-inf")   # the last move or setting, on the history's clock

    def reset(self, start_f):
        """A new request, which started at focus `start_f`."""
        self.start_f = start_f
        self.moves = 0
        self.last_offset = None

    def changed(self):
        self.changed_at = self.history.clock()

    def allows(self, name, args):
        """Whether this call's values follow from a fresh measurement within the bounds."""
        frame = self.history.frames[-1] if self.history.frames else None
        if frame is None or frame["t"] <= self.changed_at or flag(frame):
            return False
        if name in config.MOVE_ARGS:
            return self._move(name, (args or {}).get(config.MOVE_ARGS[name]) or {}, frame)
        if name == "set_intensity":
            return _within_factor((args or {}).get("intensity"), frame["settings"]["intensity"])
        if name == "set_camera":
            values = {k: v for k, v in (args or {}).items() if k not in config.NOT_VALUES}
            return set(values) == {"camera_exposure_time"} and _within_factor(
                values["camera_exposure_time"], frame["settings"]["exposure_s"])
        return False

    def took(self, name, frame):
        """Note a measured move that went through."""
        if name in config.MOVE_ARGS:
            self.moves += 1
            offset = frame["measures"].get("offset_um")
            if offset:
                self.last_offset = (abs(offset["right"]), abs(offset["up"]))

    def _move(self, name, values, frame):
        if self.moves >= config.MEASURED_MOVES_MAX or not set(values) <= {"x", "y", "f"} or not values:
            return False
        position = frame["position"]
        deltas = {axis: float(v) - position[axis] if name == "move_absolute" else float(v) for axis, v in values.items()}
        if ("x" in deltas or "y" in deltas) and not self._centring(deltas.get("x", 0.0), deltas.get("y", 0.0), frame):
            return False
        return "f" not in deltas or self._focusing(position["f"] + deltas["f"], deltas["f"])

    def _centring(self, dx, dy, frame):
        move, offset, field = (frame["measures"].get("centre_move_um"), frame["measures"].get("offset_um"),
                               frame.get("field_um"))
        if not move or not offset or not field:
            return False
        size = math.hypot(move["x"], move["y"])
        if math.hypot(dx - move["x"], dy - move["y"]) > config.MEASURED_TOLERANCE * size + 1.0:
            return False
        if math.hypot(dx, dy) > field[0]:
            return False
        if self.last_offset is None:
            return True
        now = (abs(offset["right"]), abs(offset["up"]))                    # each next offset smaller,
        return (math.hypot(*now) < math.hypot(*self.last_offset)           # and no direction worse
                and all(a <= b + config.MEASURED_SLACK_UM for a, b in zip(now, self.last_offset)))

    def _focusing(self, target, step):
        groups = (sample_map(self.history) or {}).get("groups") or []
        best = groups[0].get("best_focus") if groups else None
        if best and "edge" not in best and abs(target - best["f"]) <= best["plus_minus"] + 5.0:
            return True
        start = self.start_f if self.start_f is not None else target - step
        return abs(step) <= config.MEASURED_FOCUS_STEP_UM and abs(target - start) <= config.MEASURED_FOCUS_RANGE_UM


def _within_factor(value, current):
    try:
        value, current = float(value), float(current)
    except (TypeError, ValueError):
        return False
    return current > 0 and 1 / config.MEASURED_LIGHT_FACTOR <= value / current <= config.MEASURED_LIGHT_FACTOR
