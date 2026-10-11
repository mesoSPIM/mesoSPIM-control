"""Define the complete, validated Remote Control command vocabulary.

This module contains all remotely callable commands and the rules that protect their inputs. It
resolves effective hardware limits, builds read-only status documents, validates acquisition data,
and maps accepted mutations to the existing mesoSPIM Core API. Importing the module registers all
56 commands with the transport-independent dispatcher.

Every ordinary mutation is asynchronous. A call is validated and admitted first, then its accepted
operation is returned before Core, hardware, or GUI work starts. Short actions complete when their
scheduled function returns. Longer operations complete at a verified milestone. Clients use
``get_progress`` to observe the terminal result. Stage movement additionally checks mesoSPIM's
normal position readback until the requested target is confirmed.

This module does not open sockets or create GUI widgets. A hardware-free ``SimCore`` at the bottom
supports the fail-closed startup self-test without moving a real microscope.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import glob
import logging
import math
import os
import time

from . import config
from .gui_handles import GROUPINGS, NORMALIZATIONS, OVERLAYS, PICTURE_MAX, WINDOWS, colormaps, frame_size
from .dispatcher import (
    command,
    complete,
    fail,
    request_stop,
    operation_snapshot,
    recent_warnings,
    jsonable,
    strict_json_loads,
    clear_if_core_idle,
    schedule_current,
    claim_scheduled,
    _session,
    ValidationError,
    COMMANDS,
    READ,
    ACTION,
    WAIT,
    EMERGENCY,
    DISPLAY,
)

logger = logging.getLogger(__name__)


# --- State access and asynchronous scheduling ---
def state(core, key, default=None):
    """Read one state field. Production state has no .get(), so guard the lookup."""
    try:
        return core.state[key]
    except (KeyError, TypeError):
        return default


def cfg_dict(core, name):
    value = getattr(getattr(core, "cfg", None), name, None)
    return value if isinstance(value, dict) else {}


def position(core, absolute=False):
    """Read the user-visible position, or the physical position used by configured presets."""
    key = "position_absolute" if absolute else "position"
    pos = state(core, key, {}) or {}
    return {axis: pos.get(axis, pos.get(axis + "_pos")) for axis in config.AXES}


def axis_offsets(core):
    """The per-axis shift between the user-visible frame and the physical stage frame.

    The GUI "zero" buttons (and the remote ``zero`` command) make the current physical position
    read as 0 by adding an offset to every readback. ``stage_parameters`` limits, and therefore the
    stage drivers' own checks, are in the PHYSICAL frame, so a user-frame target must be shifted
    back before it is compared. Both readbacks come from one ``report_position`` call, so their
    difference is exactly the active offset: user = physical + offset. An axis whose absolute
    readback is unavailable (a core that has not reported yet, or a hardware-free fake) has no
    known offset and is checked as-is, which matches an unzeroed stage.
    """
    user = position(core)
    physical = position(core, absolute=True)
    offsets = {}
    for axis in config.AXES:
        here, there = user.get(axis), physical.get(axis)
        if (
            isinstance(here, (int, float))
            and isinstance(there, (int, float))
            and not isinstance(here, bool)
            and not isinstance(there, bool)
            and math.isfinite(here)
            and math.isfinite(there)
        ):
            offsets[axis] = float(here) - float(there)
        else:
            offsets[axis] = 0.0
    return offsets


def defer_position_move(core, targets, action, absolute=False):
    """Issue a stage move without blocking Core, then complete it from position readback.

    The command reply is produced before the zero-delay callback runs, so MCP and TCP receive the
    accepted operation promptly. Polling also runs on the Core event loop, where normal reads remain
    responsive. A stopped move fails instead of being mistaken for a successful arrival.
    """
    from PyQt5 import QtCore

    single_shot = getattr(core, "_remote_control_single_shot", QtCore.QTimer.singleShot)
    operation = _session(core)["operation"]
    operation["target"] = dict(targets)
    operation_id = schedule_current(core)

    def poll():
        current = _session(core).get("operation")
        if current is None or current.get("id") != operation_id:
            return
        if current.get("status") not in ("processing", "stopping"):
            return
        if current.get("stop_requested"):
            fail(
                core,
                config.MILESTONE_POSITION,
                RuntimeError("stage move stopped before the target was reached"),
            )
            return

        readback = position(core, absolute=absolute)
        observed = {axis: readback.get(axis) for axis in targets}
        current["observed"] = observed
        reached = True
        for axis, target in targets.items():
            value = observed[axis]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                reached = False
                break
            try:
                finite = math.isfinite(value)
            except (OverflowError, TypeError, ValueError):
                finite = False
            if not finite or abs(value - target) > config.POSITION_TOLERANCE[axis]:
                reached = False
                break
        if reached:
            complete(core, config.MILESTONE_POSITION)
        else:
            single_shot(config.POSITION_POLL_INTERVAL_MS, poll)

    def body():
        if not claim_scheduled(core, operation_id):
            return
        try:
            action()
        except Exception as error:
            fail(core, config.MILESTONE_POSITION, error)
            return
        single_shot(config.POSITION_POLL_INTERVAL_MS, poll)

    single_shot(0, body)


def defer_wait(core, milestone, action, verify_idle=False):
    """Schedule a WAIT command's Core `action` on the next event-loop turn and guard it.

    If `action` raises, the op is failed here so the gate cannot wedge on a raise. With
    `verify_idle` (preview) there is no signal: this runner completes the op once the action
    returns to idle. On a signal-less core (offline fakes) the op stays processing — the runtime
    never fabricates a completion; tests drive it. Qt is imported lazily.

    The main window enables its STOP only in its own Run handlers, so a run that ends with
    sig_finished first tells the window, through the Remote Control tab's queued bridge, to take
    the state a GUI run gives it; upstream's finished() gives it back. A start that raises is
    followed by no sig_finished, so it gives the window back here.
    """
    from PyQt5 import QtCore

    operation_id = schedule_current(core)
    window = getattr(core, "_remote_control_run_signal", None) if milestone == config.MILESTONE_FINISHED else None

    def body():
        if not claim_scheduled(core, operation_id):
            return
        if window is not None:
            window.emit(True)
        try:
            action()
        except Exception as error:
            if window is not None:
                window.emit(False)
            fail(core, milestone, error)
            return
        if verify_idle:
            here = state(core, "state")
            if here == "idle":
                complete(core, milestone)
            else:
                fail(core, milestone, RuntimeError(f"did not return to idle (state={here!r})"))

    QtCore.QTimer.singleShot(0, body)


def _reads_as(value, asked):
    if isinstance(value, (int, float)) and isinstance(asked, (int, float)) and not isinstance(value, bool):
        return abs(value - asked) <= 1e-9 * max(1.0, abs(asked))
    return value == asked


def refresh_window_after(core, expected):
    """Refresh the main window once Core's state holds the values a setter set, or after READ_BACK_S.

    Core's own setters refresh the window only after a filter, a shutter or an ETL file change; a
    zoom, laser, intensity or camera setting made over TCP, MCP or by the AI Assistant left the
    window's widgets on their old value. The camera worker applies its keys on its own thread, after
    the setter has returned, so the refresh waits for the state rather than firing at once.
    """
    from PyQt5 import QtCore

    single_shot = getattr(core, "_remote_control_single_shot", QtCore.QTimer.singleShot)
    polls = int(config.READ_BACK_S * 1000 / config.READ_BACK_POLL_INTERVAL_MS)

    def check(left):
        if left == 0 or all(_reads_as(state(core, key), value) for key, value in expected.items()):
            core.sig_update_gui_from_state.emit()
        else:
            single_shot(config.READ_BACK_POLL_INTERVAL_MS, lambda: check(left - 1))

    single_shot(0, lambda: check(polls))


# --- Reusable argument validators ---
def only(args, allowed):
    unknown = sorted(set(args) - set(allowed))
    if unknown:
        raise ValidationError(f"unknown argument(s): {', '.join(unknown)}")


def no_args(core, args):
    """Strict acceptor shared by commands whose public input is an empty object."""
    only(args, ())
    return {}


def _finite(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{where} must be a number, got {value!r}")
    try:
        ok = math.isfinite(value)
    except (OverflowError, ValueError):
        # A very large integer can overflow conversion inside math.isfinite.
        ok = False

    if not ok:
        raise ValidationError(f"{where} must be a finite number, got {value!r}")
    return float(value)


def number(args, key, bounds=None, required=True, default=None):
    if key not in args:
        if required:
            raise ValidationError(f"{key!r} is required")
        return default
    value = _finite(args[key], key)
    if bounds is not None and not (bounds[0] <= value <= bounds[1]):
        raise ValidationError(f"{key}={value} is outside the allowed range [{bounds[0]}, {bounds[1]}]")
    return value


def integer(args, key, minimum=None, maximum=None, required=True, default=None):
    """A whole integer. JSON booleans are ints, so exclude them."""
    if key not in args:
        if required:
            raise ValidationError(f"{key!r} is required")
        return default
    value = args[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{key!r} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{key}={value} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{key}={value} must be <= {maximum}")
    return value


def flag(args, key, default=False):
    if key not in args:
        return default
    if not isinstance(args[key], bool):
        raise ValidationError(f"{key!r} must be a boolean")
    return args[key]


def text(args, key, required=True, default=None):
    if key not in args:
        if required:
            raise ValidationError(f"{key!r} is required")
        return default
    if not isinstance(args[key], str):
        raise ValidationError(f"{key!r} must be a string")
    return args[key]


def option(core, args, key):
    value = text(args, key)
    allowed = _cfg_options(core)[key]
    if value not in allowed:
        raise ValidationError(f"{key}={value!r} is not one of {allowed}")
    return value


def axis_map(args, key):
    moves = args.get(key)
    if not isinstance(moves, dict) or not moves:
        raise ValidationError(f"{key!r} must be a non-empty object of axis -> number")
    clean = {}
    for axis, value in moves.items():
        if axis not in config.AXES:
            raise ValidationError(f"unknown axis {axis!r}; valid axes are {list(config.AXES)}")
        clean[axis] = _finite(value, f"{key}.{axis}")
    return clean


def axes_list(args, key):
    """An optional list of axes; omitted OR empty means all axes (matching the GUI)."""
    value = args.get(key)
    if value is None:
        return list(config.AXES)
    if not isinstance(value, list) or any(axis not in config.AXES for axis in value):
        raise ValidationError(f"{key!r} must be a list of {list(config.AXES)}")
    return value or list(config.AXES)


def row(core, args, key="row", default_key="selected_row"):
    """A real index into the current acquisition list. Empty list + row 0 is the clear case."""
    value = args.get(key, state(core, default_key, 0))
    count = _acq_count(core)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{key!r} must be a non-negative integer")
    if (count == 0 and value != 0) or (count > 0 and value >= count):
        raise ValidationError(f"{key}={value} is outside 0..{max(0, count - 1)}")
    return value


# --- Configuration options, setting rules, and movement limits ---
def _cfg_options(core):
    shutters = getattr(getattr(core, "cfg", None), "shutteroptions", None)
    camera = cfg_dict(core, "camera_parameters")

    # A configuration without shutter options rejects every remote shutter selection.
    return {
        "filter": list(cfg_dict(core, "filterdict")),
        "zoom": list(cfg_dict(core, "zoomdict")),
        "laser": list(cfg_dict(core, "laserdict")),
        "shutterconfig": list(shutters or []),
        "camera_binning": list(cfg_dict(core, "binning_dict")),
        "camera_display_live_subsampling": list(camera.get("subsampling", [])),
        "camera_display_acquisition_subsampling": list(camera.get("subsampling", [])),
    }


_PERCENT_KEYS = tuple(k for k in config.SETTABLE_STATE_KEYS if k.endswith("%")) + (
    "intensity",
    "galvo_l_duty_cycle",
    "galvo_r_duty_cycle",
)
_NUMERIC_OPTION_KEYS = ("camera_display_live_subsampling", "camera_display_acquisition_subsampling")
_BOOL_STATE_KEYS = ("galvo_amp_scale_w_zoom",)


def check_setting(core, key, value):
    """Type + range + option check for one settable parameter. A key we don't model is left to
    the caller. filter/zoom/laser/shutterconfig are cfg-driven enums."""
    options = _cfg_options(core)
    if key in options:
        if key in _NUMERIC_OPTION_KEYS:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValidationError(f"{key!r} must be an integer")
        elif not isinstance(value, str):
            raise ValidationError(f"{key!r} must be a string")
        if value not in options[key]:
            raise ValidationError(f"{key}={value!r} is not one of {options[key]}")
    elif key in _PERCENT_KEYS:
        _finite(value, key)
        if not (config.PERCENT_RANGE[0] <= value <= config.PERCENT_RANGE[1]):
            raise ValidationError(
                f"{key}={value} is outside the allowed range "
                f"[{config.PERCENT_RANGE[0]}, {config.PERCENT_RANGE[1]}] (percent)"
            )
    # These ranges cover voltages, frequency, phase, and camera or scan timing.
    elif key in config.PARAMETER_RANGES:
        low, high = config.PARAMETER_RANGES[key]
        _finite(value, key)
        if not (low <= value <= high):
            raise ValidationError(f"{key}={value} is outside the allowed range [{low}, {high}]")
    elif key in _BOOL_STATE_KEYS:
        if not isinstance(value, bool):
            raise ValidationError(f"{key!r} must be a boolean")
    elif key in config.SETTABLE_STATE_KEYS:
        # This is a modelled numeric parameter without a fixed GUI bound.
        _finite(value, key)

    # Values outside the settings model, such as acquisition paths, remain the caller's concern.


def settings(core, args, group):
    # Reject misspelled keys instead of silently dropping them.
    for key in args:
        if key not in group:
            raise ValidationError(f"unknown argument {key!r}; expected one of: {', '.join(group)}")

    chosen = {key: args[key] for key in group if key in args}
    if not chosen:
        raise ValidationError(f"expected one or more of: {', '.join(group)}")

    for key, value in chosen.items():
        check_setting(core, key, value)

    return chosen


def _param_constraints(core):
    """The type + allowed values of every settable parameter, so get_limits can report the
    same rules check_setting enforces. range is None when only the type is checked."""
    options = _cfg_options(core)
    spec = {}
    for key in config.SETTABLE_STATE_KEYS:
        if key in options:
            kind = "integer" if key in _NUMERIC_OPTION_KEYS else "string"
            spec[key] = {"type": kind, "options": options[key], "range": None}
        elif key in _PERCENT_KEYS:
            spec[key] = {"type": "number", "options": None, "range": list(config.PERCENT_RANGE)}
        elif key in config.PARAMETER_RANGES:
            spec[key] = {"type": "number", "options": None, "range": list(config.PARAMETER_RANGES[key])}
        elif key in _BOOL_STATE_KEYS:
            spec[key] = {"type": "boolean", "options": None, "range": None}
        else:
            spec[key] = {"type": "number", "options": None, "range": None}
    return spec


def _limits_from_cfg(core):
    stage = cfg_dict(core, "stage_parameters")
    out = {}
    for axis in config.AXES:
        low_key, high_key = f"{axis}_min", f"{axis}_max"
        if low_key not in stage and high_key not in stage:
            continue
        if low_key not in stage or high_key not in stage:
            raise ValidationError(f"stage_parameters must define both {low_key!r} and {high_key!r}")
        low = _finite(stage[low_key], f"stage_parameters.{low_key}")
        high = _finite(stage[high_key], f"stage_parameters.{high_key}")
        if low > high:
            raise ValidationError(f"stage_parameters for {axis!r} must have min <= max")
        out[axis] = (low, high)
    return out


def _limits_from_env():
    """Parse MESOSPIM_RS_LIMITS into {axis: (low, high)}. FAIL CLOSED on a malformed override: only an
    ABSENT variable means 'no override'. If the variable is set but unreadable, not JSON, not an
    object, names an unknown axis, or carries a malformed/non-finite/out-of-order pair, raise
    ValidationError — a typo in an operator's intended TIGHTER limit must not silently remove the soft
    boundary (and, since self_test resolves limits before binding, such an override takes the server
    offline rather than exposing the instrument)."""
    raw = os.environ.get(config.LIMITS_ENV_VAR)
    if raw is None:
        # Absence is the only condition that means no override.
        return {}

    raw = raw.strip()
    if not raw:
        raise ValidationError(f"{config.LIMITS_ENV_VAR} is set but empty")
    try:
        if os.path.isfile(raw):
            with open(raw, encoding=config.ENCODING) as handle:
                raw = handle.read()
        parsed = strict_json_loads(raw)
    except Exception as error:
        raise ValidationError(f"{config.LIMITS_ENV_VAR} is set but could not be read as JSON: {error}")
    if not isinstance(parsed, dict):
        raise ValidationError(f"{config.LIMITS_ENV_VAR} must be a JSON object of axis -> [low, high]")
    out = {}
    for axis, pair in parsed.items():
        if axis not in config.AXES:
            raise ValidationError(
                f"{config.LIMITS_ENV_VAR}: unknown axis {axis!r}; valid axes are {list(config.AXES)}"
            )
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValidationError(
                f"{config.LIMITS_ENV_VAR}[{axis!r}] must be [low, high] finite numbers, got {pair!r}"
            )
        low = _finite(pair[0], f"{config.LIMITS_ENV_VAR}[{axis!r}][0]")
        high = _finite(pair[1], f"{config.LIMITS_ENV_VAR}[{axis!r}][1]")
        if not (math.isfinite(low) and math.isfinite(high) and low <= high):
            raise ValidationError(
                f"{config.LIMITS_ENV_VAR}[{axis!r}]={[low, high]} must be finite with low <= high"
            )
        out[axis] = (low, high)
    return out


def effective_limits(core):
    """The cfg envelope, INTERSECTED with the env override (tighten-only): the override can only
    narrow a configured axis, never widen it. A non-overlapping override refuses the axis outright
    (fail-safe), and self_test then fails so the server never binds on a broken override."""
    limits = _limits_from_cfg(core)
    for axis, (low, high) in _limits_from_env().items():
        base = limits.get(axis)
        if base is None:
            # Apply a soft bound to an axis that has no configured range.
            limits[axis] = (low, high)
            continue

        # Intersect the ranges so an environment override can never widen the configured envelope.
        lo, hi = max(base[0], low), min(base[1], high)
        if lo > hi:
            raise ValidationError(
                f"{config.LIMITS_ENV_VAR}[{axis!r}]={[low, high]} does not overlap the configured "
                f"envelope {[base[0], base[1]]}"
            )

        limits[axis] = (lo, hi)

    missing = [axis for axis in config.AXES if axis not in limits]
    if missing:
        raise ValidationError(f"no effective motion limit for axis/axes: {', '.join(missing)}")
    return limits


def check_absolute(limits, axis, value, offset=0.0):
    """Refuse a user-frame target whose PHYSICAL position leaves the envelope. `offset` is the
    active zeroing shift for the axis (see axis_offsets); the limits are physical."""
    bound = limits.get(axis)
    if bound is None:
        return
    physical = value - offset
    if not (bound[0] <= physical <= bound[1]):
        frame = f" (stage position {physical} after the current zero offset {offset})" if offset else ""
        raise ValidationError(
            f"{axis}={value}{frame} is outside the allowed range [{bound[0]}, {bound[1]}] "
            f"(units: um for x/y/z/f, deg for theta; see get_limits)"
        )


def check_relative(limits, axis, current, delta, offset=0.0):
    bound = limits.get(axis)
    if bound is None:
        return
    current = _finite(current, f"current {axis} position")
    target = current + delta
    physical = target - offset
    if not (bound[0] <= physical <= bound[1]):
        frame = f" (stage position {physical} after the current zero offset {offset})" if offset else ""
        raise ValidationError(
            f"{axis} would reach {target}{frame}, outside the allowed range "
            f"[{bound[0]}, {bound[1]}] (current {current} + delta {delta}; see get_limits)"
        )


# --- acquisition helpers ---
def _camera_pixels(core):
    """The configured sensor size. No guessing: a config without one is a broken config."""
    params = cfg_dict(core, "camera_parameters")
    try:
        values = params["x_pixels"], params["y_pixels"]
    except KeyError as error:
        raise ValidationError(f"camera_parameters is missing or invalid: {error}")
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values):
        raise ValidationError("camera_parameters x_pixels/y_pixels must be positive integers")
    return values


def _make_acquisition_list(rows):
    from ..utils.acquisitions import Acquisition, AcquisitionList

    out = AcquisitionList([])
    for raw in rows:
        acq = Acquisition()
        acq.update({key: value for key, value in dict(raw).items() if value is not None})
        out.append(acq)
    return out


def _acq_count(core):
    try:
        return len(state(core, "acq_list", []) or [])
    except TypeError:
        return 0


def check_acquisition(core, acquisition, label="acquisition"):
    if not isinstance(acquisition, dict):
        raise ValidationError(f"{label} must be an object")

    only(acquisition, config.ACQUISITION_FIELDS)

    # Validate intensity ranges and filter, zoom, laser, and ETL options.
    for key, value in acquisition.items():
        check_setting(core, key, value)

    limits = effective_limits(core)
    offsets = axis_offsets(core)
    for field, axis in config.ACQUISITION_AXIS_FIELDS.items():
        if field in acquisition:
            check_absolute(limits, axis, _finite(acquisition[field], f"{label}.{field}"), offsets[axis])
    if "z_step" in acquisition:
        step = _finite(acquisition["z_step"], f"{label}.z_step")
        if step <= 0:
            raise ValidationError(f"{label}.z_step must be positive")
    if "planes" in acquisition:
        planes = acquisition["planes"]
        if not isinstance(planes, int) or isinstance(planes, bool) or planes < 1:
            raise ValidationError(f"{label}.planes must be a positive integer")
        if planes > config.MAX_ACQUISITION_PLANES:
            raise ValidationError(
                f"{label}.planes exceeds the metadata maximum of {config.MAX_ACQUISITION_PLANES}"
            )
    for field in config.ACQUISITION_STRING_FIELDS:
        if field in acquisition and not isinstance(acquisition[field], str):
            raise ValidationError(f"{label}.{field} must be a string")
    modeled = _make_acquisition_list([acquisition])[0]
    z_start = _finite(modeled["z_start"], f"{label}.z_start")
    z_end = _finite(modeled["z_end"], f"{label}.z_end")
    z_step = _finite(modeled["z_step"], f"{label}.z_step")
    if z_step <= 0:
        raise ValidationError(f"{label}.z_step must be positive")
    ratio = abs(z_end - z_start) / z_step
    if not math.isfinite(ratio) or ratio > config.MAX_ACQUISITION_PLANES:
        raise ValidationError(
            f"{label} resolves to too many planes; maximum is {config.MAX_ACQUISITION_PLANES}"
        )
    # Match the calculation in upstream Acquisition.get_image_count().
    derived_planes = abs(round(ratio)) + 1
    if derived_planes > config.MAX_ACQUISITION_PLANES:
        raise ValidationError(
            f"{label} resolves to {derived_planes} planes; maximum is {config.MAX_ACQUISITION_PLANES}"
        )
    # Upstream stores ``planes`` as UI metadata but always derives the real image count from the Z
    # geometry. Its own default row is metadata=10 and geometry=11, so requiring equality would make
    # get_acquisition_list -> set_acquisition_list impossible. Geometry remains authoritative and is
    # capped above; the metadata is only type/size checked for faithful round trips.
    return dict(acquisition)


def check_writer_suffix(row, label):
    """A row's file name must end in one of its writer's extensions. The writer checks it only once
    Core has stopped the stage-position polling, and Core does not resume the polling on that error:
    the position freezes, and a remote move then waits for it for good. A writer mesoSPIM does not
    know is left to Core."""
    from ..plugins.utils import get_image_writer_class_from_name

    if not isinstance(row, dict) or not isinstance(row.get("filename"), str):
        return
    writer = get_image_writer_class_from_name(row.get("image_writer_plugin"))
    extensions = writer.file_extensions() if writer is not None else None
    if not extensions:
        return
    extensions = ["." + e.lstrip(".") for e in ([extensions] if isinstance(extensions, str) else extensions)]
    if not any(row["filename"].endswith(e) for e in extensions):
        raise ValidationError(f"{label}: {row['filename']!r} does not suit {row['image_writer_plugin']}, which "
                              f"writes {', '.join(extensions)}; rename the file or choose another writer")


def revalidate_installed_writers(core, indices=None):
    """check_writer_suffix for the installed rows about to run (`indices`: only those)."""
    installed = state(core, "acq_list", []) or []
    for i in range(len(installed)) if indices is None else indices:
        if 0 <= i < len(installed):
            check_writer_suffix(installed[i], f"installed acquisitions[{i}]")


def revalidate_installed_limits(core, indices=None):
    """Re-check the ALREADY-installed acquisition rows' stage fields against the effective limits,
    right before a remote command starts them. The installed list may have been set from the GUI
    (never through our accept) or may predate a tightened MESOSPIM_RS_LIMITS, so the install-time
    check is not sufficient on its own. Only the axis fields are re-checked — the safety-relevant
    part — so a GUI row carrying extra keys is not spuriously rejected. `indices` limits the check to
    specific rows (run_selected_acquisition runs only one)."""
    installed = state(core, "acq_list", []) or []
    limits = effective_limits(core)
    offsets = axis_offsets(core)
    chosen = range(len(installed)) if indices is None else indices
    for i in chosen:
        if not (0 <= i < len(installed)):
            continue

        fields = dict(installed[i]) if isinstance(installed[i], dict) else {}
        for field, axis in config.ACQUISITION_AXIS_FIELDS.items():
            if field not in fields:
                continue

            # a PRESENT stage-axis field must be a finite number: a non-numeric target is malformed
            # and refused (fail closed), not skipped, so it cannot reach Core unchecked.
            value = _finite(fields[field], f"installed acquisitions[{i}].{field}")
            bound = limits.get(axis)
            physical = value - offsets[axis]
            if bound is not None and not (bound[0] <= physical <= bound[1]):
                raise ValidationError(
                    f"installed acquisitions[{i}].{field}={value} (stage position {physical}) is "
                    f"outside the allowed range [{bound[0]}, {bound[1]}]; re-install the list "
                    f"within the current limits"
                )


# --- Read-only response documents ---
def _state_snapshot(core, keys=None):
    state_obj = getattr(core, "state", None)
    if keys is None:
        # Production StateSingleton has no keys(), so enumerate its backing dictionary.
        raw = getattr(state_obj, "_state_dict", None)
        keys = list(raw.keys()) if isinstance(raw, dict) else ()

    get_parameter_dict = getattr(state_obj, "get_parameter_dict", None)
    if callable(get_parameter_dict):
        return jsonable(get_parameter_dict(list(keys)))
    return {key: jsonable(state(core, key)) for key in keys}


def _wavelength_nm(name):
    """The nm from a laser name like '488 nm', or None when it carries no digits."""
    digits = "".join(c for c in str(name) if c.isdigit())
    return int(digits) if digits else None


def _image_writers():
    """The registered image writers and their file extensions, the names the table calls take."""
    from ..plugins.utils import get_image_writer_plugins

    writers = []
    for plugin in get_image_writer_plugins():
        extensions = plugin["file_extensions"]
        writers.append({"name": plugin["name"],
                        "file_extensions": [extensions] if isinstance(extensions, str) else list(extensions)})
    return writers


def _config_document(core):
    cfg = getattr(core, "cfg", None)
    lasers = [{"name": n, "wavelength_nm": _wavelength_nm(n)} for n in cfg_dict(core, "laserdict")]
    pixelsizes = cfg_dict(core, "pixelsize")
    zooms = []
    for zoom, raw in cfg_dict(core, "zoomdict").items():
        fallback = raw if isinstance(raw, (int, float)) else None
        zooms.append({"name": zoom, "pixel_size_um": pixelsizes.get(zoom, fallback)})
    pixels_x, pixels_y = _camera_pixels(core)
    shutters = getattr(cfg, "shutteroptions", None) or config.DEFAULT_SHUTTER_OPTIONS
    return {
        "app": config.APP_NAME,
        "version": getattr(cfg, "version", None),
        "lasers": lasers,
        "filters": list(cfg_dict(core, "filterdict")),
        "zooms": zooms,
        "shutter_configs": list(shutters),
        "axes": list(config.AXES),
        "camera": {"pixels_x": pixels_x, "pixels_y": pixels_y},
        "image_writers": _image_writers(),
    }


def _info_document(core):
    cfg = getattr(core, "cfg", None)
    writer = getattr(core, "image_writer", None)
    return {
        "app": config.APP_NAME,
        "version": getattr(cfg, "version", None),
        "protocol": config.PROTOCOL_VERSION,
        "state": state(core, "state"),
        "stage_type": cfg_dict(core, "stage_parameters").get("stage_type"),
        "save_path": state(core, "folder"),
        "last_acquisition_path": getattr(writer, "path", None),
        "etl_config_path": state(core, "ETL_cfg_file"),
        "operation": operation_snapshot(core),
        "warnings": recent_warnings(core),
    }


def _limits_document(core):
    cfg = getattr(core, "cfg", None)
    axes = effective_limits(core)
    return {
        "stage": jsonable(getattr(cfg, "stage_parameters", {})),
        "camera": jsonable(getattr(cfg, "camera_parameters", {})),
        "startup": jsonable(getattr(cfg, "startup", {})),
        "enforced": {
            "axes": {ax: (list(axes[ax]) if ax in axes else None) for ax in config.AXES},
            # The axis envelope is in the physical stage frame. A move target is user-frame:
            # physical = target - axis_offsets[axis]. All offsets are 0 unless an axis is zeroed.
            "axes_frame": "stage",
            "axis_offsets": axis_offsets(core),
            "parameters": _param_constraints(core),
        },
    }


# --- Argument schemas (published by MCP tools/list; `accept` remains the authority) ---
def _schema(properties=None, required=(), **extra):
    schema = {"type": "object", "properties": dict(properties or {}), "additionalProperties": False}
    if required:
        schema["required"] = list(required)
    schema.update(extra)
    return schema


_NUMBER, _INTEGER, _STRING, _BOOLEAN = {"type": "number"}, {"type": "integer"}, {"type": "string"}, {"type": "boolean"}
_PERCENT = {"type": "number", "minimum": config.PERCENT_RANGE[0], "maximum": config.PERCENT_RANGE[1]}
_AXIS_MAP = _schema({axis: _NUMBER for axis in config.AXES}, minProperties=1)
_AXES = {"type": "array", "items": {"type": "string", "enum": list(config.AXES)}}
_WAIT = {**_BOOLEAN, "description": "the operation completes only once the hardware confirms"}


def _setting_schema(key):
    """The schema of one settable state key, from the same tables check_setting enforces."""
    if key in _NUMERIC_OPTION_KEYS:
        return {**_INTEGER, "description": "one of camera_parameters.subsampling"}
    if key in ("filter", "zoom", "laser", "shutterconfig", "camera_binning"):
        return {**_STRING, "description": f"one of the configured {key} options (see get_config)"}
    if key in _PERCENT_KEYS:
        return _PERCENT
    if key in config.PARAMETER_RANGES:
        low, high = config.PARAMETER_RANGES[key]
        return {"type": "number", "minimum": low, "maximum": high}
    if key in _BOOL_STATE_KEYS:
        return _BOOLEAN
    return _NUMBER


def _settings_schema(keys):
    return _schema({key: _setting_schema(key) for key in keys}, minProperties=1)


_ACQUISITION = _schema(
    {
        **{field: _NUMBER for field in config.ACQUISITION_AXIS_FIELDS},
        "z_step": {"type": "number", "exclusiveMinimum": 0},
        "planes": {"type": "integer", "minimum": 1, "maximum": config.MAX_ACQUISITION_PLANES},
        **{field: _STRING for field in config.ACQUISITION_STRING_FIELDS},
        **{key: _setting_schema(key) for key in ("laser", "intensity", "filter", "zoom", "shutterconfig")},
        **{key: _setting_schema(key) for key in ("etl_l_offset", "etl_l_amplitude", "etl_r_offset", "etl_r_amplitude")},
    }
)
_ACQUISITIONS = {"type": "array", "items": _ACQUISITION, "minItems": 1}
_ROW = {"type": "integer", "minimum": 0, "description": "index into the installed acquisition list"}


# --- Command definitions ---


# --- Read-only commands ---
def _run_hello(core, args):
    return {
        "app": config.APP_NAME,
        "version": getattr(getattr(core, "cfg", None), "version", None),
        "protocol": config.PROTOCOL_VERSION,
        "state": state(core, "state"),
    }


command("hello", READ, _run_hello, accept=no_args, hint="in: none. out: {app, version, protocol, state}")


def _run_ping(core, args):
    return {"pong": True, "state": state(core, "state")}


command("ping", READ, _run_ping, accept=no_args, hint="in: none. out: {pong, state}")


def _run_get_state(core, args):
    keys = (
        "laser",
        "intensity",
        "filter",
        "zoom",
        "shutterconfig",
        "etl_l_amplitude",
        "etl_l_offset",
        "etl_r_amplitude",
        "etl_r_offset",
    )
    out = {"state": state(core, "state"), "position": position(core)}
    out.update({key: state(core, key) for key in keys})
    return out


command("get_state", READ, _run_get_state, accept=no_args, hint="in: none. out: main settings")


def _run_get_position(core, args):
    return position(core)


command("get_position", READ, _run_get_position, accept=no_args, hint="in: none. out: {x,y,z,f,theta}")


def _accept_get_state_all(core, args):
    only(args, ("keys",))
    keys = args.get("keys")
    if keys is not None and not isinstance(keys, list):
        raise ValidationError("'keys' must be a list")
    if keys is not None:
        for key in keys:
            if not isinstance(key, str):
                raise ValidationError("every state key must be a string")
            try:
                core.state[key]
            except (KeyError, TypeError):
                raise ValidationError(f"unknown state key {key!r}")
    return {"keys": keys}


def _run_get_state_all(core, args):
    return _state_snapshot(core, args["keys"])


command(
    "get_state_all",
    READ,
    _run_get_state_all,
    schema=_schema({"keys": {"type": "array", "items": _STRING, "description": "state keys; omit for all"}}),
    accept=_accept_get_state_all,
    hint="in: {keys?: [str]}. out: state map",
)


def _run_get_config(core, args):
    return _config_document(core)


command(
    "get_config", READ, _run_get_config, accept=no_args, hint="in: none. out: lasers/filters/zooms/camera/image_writers"
)


def _run_get_info(core, args):
    return _info_document(core)


command("get_info", READ, _run_get_info, accept=no_args, hint="in: none. out: extensible microscope info")


def _run_get_limits(core, args):
    return _limits_document(core)


command(
    "get_limits", READ, _run_get_limits, accept=no_args, hint="in: none. out: stage/camera/enforced limits"
)


def _run_get_capabilities(core, args):
    return {
        "commands": list(COMMANDS),
        "axes": list(config.AXES),
        "position_keys": {axis: f"{axis}_pos" for axis in config.AXES},
        "core_states": list(config.MODES),  # what get_state may report; nothing sets a state directly
        "settable_state_keys": list(config.SETTABLE_STATE_KEYS),
        "setting_groups": {name: list(keys) for name, keys in config.SETTING_GROUPS.items()},
        "acquisition_fields": list(config.ACQUISITION_FIELDS),
    }


command("get_capabilities", READ, _run_get_capabilities, accept=no_args, hint="in: none. out: vocabulary")

# The built-in reference is returned by get_manual over both TCP and MCP. The command table is
# generated from the registry so its names, kinds, and short descriptions cannot drift from code.
_MANUAL_INTERACTION = {
    "request": "Send one named command with one object of arguments. TCP uses "
    '{"<command>": {args}}. MCP uses tools/call with the same command name and '
    "arguments. Both transports execute the same dispatcher and command registry.",
    "accepted_or_rejected": "Every ordinary mutation is either rejected with a typed error or "
    "accepted with {accepted: true, accepted_command, operation}. Accepted "
    "means the input passed validation and the operation was admitted; it "
    "does not by itself prove that hardware reached the requested state. "
    "Read-only commands return data directly. Emergency commands validate "
    "and execute immediately without creating a new operation.",
    "confirm_completion": "After an ordinary mutation is accepted, save operation.id and poll "
    "get_progress over TCP or MCP. Match the same operation id and wait for "
    "status 'completed', 'stopped' (a stop cut it short) or 'failed'; a stage move stopped after "
    "it was sent ends 'failed' with stop_requested. For movement, completion means "
    "mesoSPIM's position readback reached the accepted target within "
    "tolerance. If an emergency command returns an active operation, keep "
    "polling that operation. Never resend accepted work merely because it "
    "is still processing.",
    "kinds": {
        "read": "Returns current data without opening or waiting for the mutation gate.",
        "action": "A short asynchronous mutation. Admission is acknowledged first; poll "
        "get_progress for its terminal result.",
        "wait": "A longer asynchronous mutation. Admission is acknowledged first; poll "
        "get_progress for the same operation id until it becomes terminal.",
        "emergency": "An immediate command allowed while another mutation is processing: the "
        "stops (stop, stop_activity, time_lapse_stop), close_shutters, and the guarded recovery "
        "clear_stuck_operation. It does not create a new operation.",
        "display": "A change to what the windows show (levels, lookup table, view, regions of interest). "
        "It never touches the instrument, opens no operation and is never refused as busy, so it works "
        "during a run too. It returns a request number at once; get_display {request} reports when the "
        "window shows it.",
    },
    "mutation_gate": "Only one mutation may run at a time. A second valid mutation is rejected "
    "with error code 'busy' while an operation is processing or stopping. Reads, "
    "including get_progress, remain available and do not disturb that operation.",
    "before_you_start": "Call get_info and get_limits first. Use the returned configuration and "
    "never exceed a reported limit.",
    "error_codes": {
        "validation": "The argument type, option, range, or limit is invalid. Nothing was started.",
        "busy": "Another mutation owns the gate. Wait for its terminal status before retrying.",
        "unknown_command": "The command name is not in the allowlist. Correct the name.",
        "execution": "Execution raised an error. Inspect get_progress and restore a safe state.",
    },
}

_MANUAL_RECIPES = [
    {
        "goal": "Move the stage",
        "steps": [
            "get_limits (read the per-axis envelope)",
            "move_absolute {targets: {x: <um>}}   (or move_relative {deltas: {...}})",
            "poll get_progress for the returned operation id until status is completed, stopped or failed",
            "verify get_position reports the intended position",
        ],
    },
    {"goal": "Live mode", "steps": ["start_live {}", "... observe ...", "stop_activity {}"]},
    {
        "goal": "Run one supplied acquisition",
        "steps": [
            "acquire_start {acquisition: {...}}",
            "poll get_progress until 'completed', 'stopped' or 'failed'",
            "acquire_finish {}",
        ],
    },
    {
        "goal": "Run the installed acquisition list",
        "steps": [
            "set_acquisition_list {acquisitions: [...], selected_row: 0}",
            "poll get_progress until the list operation is completed",
            "run_acquisition_list {}",
            "poll get_progress until 'completed', 'stopped' or 'failed'",
        ],
    },
]


def _run_get_manual(core, args):
    return {
        "overview": "You are driving a mesoSPIM light-sheet microscope over a validated "
        "named-call API. Every call is one of the commands below; there is no "
        "free-form code, and a bad value is refused before it reaches the hardware.",
        "interaction": _MANUAL_INTERACTION,
        "recipes": _MANUAL_RECIPES,
        "commands": [{"name": c.name, "kind": c.kind, "hint": c.hint} for c in COMMANDS.values()],
        "see_also": "get_capabilities (the vocabulary), get_limits (the enforced limits), "
        "get_info (live microscope state).",
    }


command(
    "get_manual",
    READ,
    _run_get_manual,
    accept=no_args,
    hint="in: none. out: the client guide — READ FIRST. Workflows, the poll-get_progress "
    "completion contract, the error codes, and every command with its kind and hint.",
)


def _run_get_progress(core, args):
    return {
        "state": state(core, "state"),
        "current_plane": state(core, "current_framenumber"),
        "total_planes": state(core, "snap_count"),
        "current_acquisition": state(core, "current_acquisition"),
        "total_acquisitions": state(core, "total_acquisitions"),
        "operation": operation_snapshot(core),
    }


command(
    "get_progress",
    READ,
    _run_get_progress,
    accept=no_args,
    hint="in: none. out: {state, ...counts, operation}",
)


def _snapshot_document(core):
    """One compact readout of the microscope for a client (or a model) that needs to know where
    things stand before deciding: state, position in both frames, optics, camera, ETL, the
    installed acquisition list, disk, time lapse, the last operation and warnings, the frame."""
    session = _session(core)
    offsets = axis_offsets(core)
    acq_list = state(core, "acq_list", []) or []
    rows = [dict(row) for row in acq_list if isinstance(row, dict)]
    acquisition = {
        "rows": len(rows),
        "selected_row": state(core, "selected_row"),
        "folders": sorted({row["folder"] for row in rows if row.get("folder")}),
        "filenames": [row.get("filename") for row in rows],
    }
    disk = None
    if rows:
        try:
            disk = {
                "free_bytes": int(core.get_free_disk_space(acq_list)),
                "required_bytes": int(core.get_required_disk_space(acq_list)),
            }
        except Exception as error:  # a read must not fail because of one estimate
            disk = {"error": str(error)}
    frame = getattr(core, "frame_queue_display", None)
    return {
        "state": state(core, "state"),
        "operation": operation_snapshot(core),
        "warnings": recent_warnings(core)[-5:],
        "position": position(core),
        "position_stage": position(core, absolute=True),
        "zeroed_axes": [axis for axis, offset in offsets.items() if offset],
        "limits": {axis: list(bounds) for axis, bounds in effective_limits(core).items()},
        "optics": {key: state(core, key) for key in ("laser", "intensity", "filter", "zoom", "shutterconfig", "shutterstate")},
        "camera": {
            "exposure_time_s": state(core, "camera_exposure_time"),
            "binning": state(core, "camera_binning"),
            "pixels": list(_camera_pixels(core)),
            "pixel_size_um": state(core, "pixelsize"),
        },
        "etl": {key: state(core, key) for key in ("etl_l_amplitude", "etl_l_offset", "etl_r_amplitude", "etl_r_offset")},
        "acquisition_list": acquisition,
        "disk": disk,
        "time_lapse": {
            "active": getattr(core, "timelapse_active", None),
            "timepoint": getattr(core, "time_counter", None),
            "timepoints": getattr(core, "timelapse_tpoints", None),
            "interval_sec": getattr(core, "timelapse_interval_sec", None),
        },
        "snap_folder": state(core, "snap_folder"),
        "last_snap": session.get("last_snap"),
        "frame_available": bool(frame),
    }


def _run_get_snapshot(core, args):
    return _snapshot_document(core)


command(
    "get_snapshot",
    READ,
    _run_get_snapshot,
    accept=no_args,
    hint="in: none. out: one compact readout of the whole microscope: state, position (user and "
    "stage frame), optics, camera, ETL, acquisition list, disk, time lapse, warnings, frame",
)


def _accept_get_frame(core, args):
    from .frame import FOCUS_METRICS

    only(args, ("max_size", "bin", "include_image", "array_side", "focus_metric"))
    bin_factor = integer(args, "bin", minimum=1, maximum=8, required=False)
    if bin_factor is not None and bin_factor not in config.FRAME_BINS:
        raise ValidationError(f"bin must be one of {list(config.FRAME_BINS)}")
    focus_metric = text(args, "focus_metric", required=False, default="laplacian")
    if focus_metric not in FOCUS_METRICS:
        raise ValidationError(f"focus_metric must be one of {list(FOCUS_METRICS)}")
    return {
        "focus_metric": focus_metric,
        "max_size": integer(args, "max_size", minimum=64, maximum=4096, required=False, default=1024),
        "bin": bin_factor,
        "include_image": flag(args, "include_image", True),
        "array_side": integer(args, "array_side", minimum=16, maximum=1024, required=False),
    }


def _run_get_frame(core, args):
    """The last frame mesoSPIM displayed, as numbers and (optionally) a small PNG."""
    from .frame import describe_frame

    queue = getattr(core, "frame_queue_display", None)
    if not queue:
        return {"available": False}
    return describe_frame(queue[0], max_size=args["max_size"], include_image=args["include_image"],
                          bin_factor=args["bin"], array_side=args["array_side"],
                          focus_metric=args["focus_metric"])


command(
    "get_frame",
    READ,
    _run_get_frame,
    accept=_accept_get_frame,
    schema=_schema({
        "max_size": {"type": "integer", "minimum": 64, "maximum": 4096, "description": "longer side of the PNG, default 1024"},
        "bin": {"type": "integer", "enum": list(config.FRAME_BINS), "description": "bin the PNG n x n instead of max_size"},
        "include_image": {**_BOOLEAN, "description": "false for the numbers only"},
        "array_side": {"type": "integer", "minimum": 16, "maximum": 1024,
                       "description": "also the frame itself, 16-bit, binned to at most this longer side"},
        "focus_metric": {"type": "string", "enum": ["laplacian", "dct_shannon"],
                         "description": "focus_measure by Laplacian energy (default) or the Auto-Focus DCT-Shannon"},
    }),
    hint="in: {max_size?, bin?, include_image?, array_side?, focus_metric?}. out: {available, stats{shape, min, max, "
    "percentiles, background, saturated_fraction, bright_fraction, signal_centroid, focus_measure, focus_metric}, "
    "image{png base64}, array?}. "
    "the last displayed frame (after snap or live)",
)


def _run_self_test(core, args):
    ok, report = self_test(core)
    return {"ok": ok, "report": report}


command(
    "self_test",
    READ,
    _run_self_test,
    accept=no_args,
    hint="in: none. out: {ok, report}. never moves hardware",
)


def _run_get_acquisition_list(core, args):
    return {"acquisitions": jsonable(state(core, "acq_list", []))}


command(
    "get_acquisition_list",
    READ,
    _run_get_acquisition_list,
    accept=no_args,
    hint="in: none. out: {acquisitions}",
)


def _accept_stat_files(core, args):
    only(args, ("files",))
    files = args.get("files") or []

    # A string would otherwise be treated as one path per character.
    if not isinstance(files, list):
        raise ValidationError("'files' must be a list of strings")

    for path in files:
        if not isinstance(path, str):
            raise ValidationError("each entry in 'files' must be a string")

    return {"files": files}


def _run_stat_files(core, args):
    files = args["files"]
    return {
        "missing": [f for f in files if not os.path.isfile(f)],
        "sizes": {f: os.path.getsize(f) for f in files if os.path.isfile(f)},
    }


command(
    "stat_files",
    READ,
    _run_stat_files,
    schema=_schema({"files": {"type": "array", "items": _STRING}}, required=("files",)),
    accept=_accept_stat_files,
    hint="in: {files: [path]}. out: {missing, sizes}",
)


def _acqs_to_check(core, args):
    # An omitted or explicit null value means use the installed acquisition list.
    if args.get("acquisitions") is not None:
        return _make_acquisition_list(args["acquisitions"])

    return state(core, "acq_list")


def _accept_acq_check(core, args):
    only(args, ("acquisitions",))
    acquisitions = args.get("acquisitions")
    if acquisitions is not None and not isinstance(acquisitions, list):
        # Reject this during validation rather than reporting a later execution error.
        raise ValidationError("'acquisitions' must be a list")

    selected = acquisitions if acquisitions is not None else state(core, "acq_list", [])
    if not selected:
        raise ValidationError("an acquisition list is required")
    for index, acquisition in enumerate(acquisitions or []):
        check_acquisition(core, acquisition, f"acquisitions[{index}]")

    return args


def _run_get_disk_space(core, args):
    acq = _acqs_to_check(core, args)
    return {
        "free_bytes": int(core.get_free_disk_space(acq)),
        "required_bytes": int(core.get_required_disk_space(acq)),
    }


command(
    "get_disk_space",
    READ,
    _run_get_disk_space,
    schema=_schema({"acquisitions": {**_ACQUISITIONS, "description": "omit for the installed list"}}),
    accept=_accept_acq_check,
    hint="in: {acquisitions?}. out: {free_bytes, required_bytes}",
)


def _run_check_motion_limits(core, args):
    return {"outside_limits": list(core.check_motion_limits(_acqs_to_check(core, args)))}


command(
    "check_motion_limits",
    READ,
    _run_check_motion_limits,
    schema=_schema({"acquisitions": {**_ACQUISITIONS, "description": "omit for the installed list"}}),
    accept=_accept_acq_check,
    hint="in: {acquisitions?}. out: {outside_limits}",
)


# --- Stage movement ---
def _accept_move_absolute(core, args):
    only(args, ("targets",))
    targets = axis_map(args, "targets")
    limits = effective_limits(core)
    offsets = axis_offsets(core)
    for axis, value in targets.items():
        check_absolute(limits, axis, value, offsets[axis])
    return {"targets": targets}


def _run_move_absolute(core, args):
    targets = args["targets"]
    move = {f"{axis}_abs": value for axis, value in targets.items()}
    defer_position_move(core, targets, lambda: core.move_absolute(move, wait_until_done=False))
    return {"target": targets}


command(
    "move_absolute",
    WAIT,
    _run_move_absolute,
    schema=_schema({"targets": {**_AXIS_MAP, "description": "axis -> um (deg for theta)"}}, required=("targets",)),
    accept=_accept_move_absolute,
    milestone=config.MILESTONE_POSITION,
    hint="in: {targets:{axis: um/deg}}. out: {target}",
)


def _accept_move_relative(core, args):
    only(args, ("deltas",))
    deltas = axis_map(args, "deltas")
    limits = effective_limits(core)
    offsets = axis_offsets(core)
    here = position(core)
    targets = {}
    for axis, delta in deltas.items():
        check_relative(limits, axis, here.get(axis), delta, offsets[axis])
        targets[axis] = here[axis] + delta
    return {"deltas": deltas, "targets": targets}


def _run_move_relative(core, args):
    move = {f"{axis}_rel": delta for axis, delta in args["deltas"].items()}
    worker_move = getattr(getattr(core, "serial_worker", None), "move_relative", None)
    action = (
        (lambda: worker_move(move, wait_until_done=False))
        if callable(worker_move)
        else (lambda: core.move_relative(move, wait_until_done=False))
    )
    defer_position_move(core, args["targets"], action)
    return {"target": args["targets"]}


command(
    "move_relative",
    WAIT,
    _run_move_relative,
    schema=_schema({"deltas": {**_AXIS_MAP, "description": "axis -> um (deg for theta)"}}, required=("deltas",)),
    accept=_accept_move_relative,
    milestone=config.MILESTONE_POSITION,
    hint="in: {deltas:{axis: um/deg}}. out: {target}",
)


def _accept_axes(core, args):
    only(args, ("axes",))
    return {"axes": axes_list(args, "axes")}


def _run_zero(core, args):
    core.zero_axes(args["axes"])
    return {}


command("zero", ACTION, _run_zero, schema=_schema({"axes": {**_AXES, "description": "omit for all axes"}}), accept=_accept_axes, hint="in: {axes?}. out: {}")


def _run_unzero(core, args):
    core.unzero_axes(args["axes"])
    return {}


command("unzero", ACTION, _run_unzero, schema=_schema({"axes": {**_AXES, "description": "omit for all axes"}}), accept=_accept_axes, hint="in: {axes?}. out: {}")


# --- Emergency and recovery commands ---
def _run_stop(core, args):
    # `stop` REQUESTS a stop: it halts stage movement and marks a running op 'stopping', but it does
    # not itself end a mode, so the op stays 'stopping' until its milestone fires. To force a running
    # mode to end (and release the gate), use `stop_activity`, which drives core.stop() -> sig_finished.
    request_stop(core)
    core.sig_stop_movement.emit()
    return {}


command("stop", EMERGENCY, _run_stop, accept=no_args, hint="in: none. out: {}")


def _run_stop_activity(core, args):
    request_stop(core)

    # Broadcasting another abort while idle can emit the completion signal twice.
    if state(core, "state") != "idle":
        core.stop()
    if getattr(core, "timelapse_active", False) is True:   # started from the GUI or remotely: no next point
        core.stop_time_lapse()

    return {"state": state(core, "state")}


command("stop_activity", EMERGENCY, _run_stop_activity, accept=no_args, hint="in: none. out: {state}")


def _run_close_shutters(core, args):
    core.close_shutters()
    return {"shutterstate": state(core, "shutterstate")}


command(
    "close_shutters",
    EMERGENCY,
    _run_close_shutters,
    accept=no_args,
    hint="in: none. out: {shutterstate}. does not stop the op",
)


def _run_time_lapse_stop(core, args):
    request_stop(core)
    core.stop_time_lapse()
    return {"stopped": True}


command("time_lapse_stop", EMERGENCY, _run_time_lapse_stop, accept=no_args, hint="in: none. out: {stopped}")


def _run_clear_stuck_operation(core, args):
    return clear_if_core_idle(core)


command(
    "clear_stuck_operation",
    EMERGENCY,
    _run_clear_stuck_operation,
    accept=no_args,
    hint="in: none. out: {cleared, operation_id?, reason?}. GUARDED recovery for a never-signalled "
    "WAIT: fails a wedged operation and frees the gate ONLY if the microscope is independently "
    "idle. Never aborts a running operation.",
)


# --- Microscope settings ---
def _accept_set_state(core, args):
    only(args, ("settings",))
    obj = args.get("settings")
    if not isinstance(obj, dict) or not obj:
        raise ValidationError("'settings' must be a non-empty object")
    for key in obj:
        if key not in config.SETTABLE_STATE_KEYS:
            raise ValidationError(f"unknown state setting {key!r}")
    for key, value in obj.items():
        check_setting(core, key, value)
    return {"settings": obj}


def _run_state_settings(core, args):
    """The execute shared by set_state and the four grouped setters."""
    settings = args["settings"]
    if "galvo_amp_scale_w_zoom" in settings:   # Core forwards it and nobody applies it; the window writes it itself
        core.state["galvo_amp_scale_w_zoom"] = settings["galvo_amp_scale_w_zoom"]
    core.state_request_handler(settings)
    refresh_window_after(core, settings)
    return {}


command(
    "set_state",
    ACTION,
    _run_state_settings,
    schema=_schema({"settings": _settings_schema(config.SETTABLE_STATE_KEYS)}, required=("settings",)),
    accept=_accept_set_state,
    hint="in: {settings:{settable keys, see get_capabilities}}. out: {}",
)


def _accept_set_filter(core, args):
    only(args, ("filter", "wait"))
    return {"filter": option(core, args, "filter"), "wait": flag(args, "wait", False)}


def _run_set_filter(core, args):
    core.set_filter(args["filter"], wait_until_done=args["wait"])
    refresh_window_after(core, {"filter": args["filter"]})
    return {}


command("set_filter", ACTION, _run_set_filter, schema=_schema({"filter": _setting_schema("filter"), "wait": _WAIT}, required=("filter",)), accept=_accept_set_filter, hint="in: {filter, wait?}. out: {}")


def _accept_set_zoom(core, args):
    only(args, ("zoom", "wait", "update_etl"))
    return {
        "zoom": option(core, args, "zoom"),
        "wait": flag(args, "wait", True),
        "update_etl": flag(args, "update_etl", True),
    }


def _run_set_zoom(core, args):
    core.set_zoom(args["zoom"], wait_until_done=args["wait"], update_etl=args["update_etl"])
    refresh_window_after(core, {"zoom": args["zoom"]})
    return {}


command(
    "set_zoom", ACTION, _run_set_zoom, schema=_schema({"zoom": _setting_schema("zoom"), "wait": _WAIT, "update_etl": _BOOLEAN}, required=("zoom",)), accept=_accept_set_zoom, hint="in: {zoom, wait?, update_etl?}. out: {}"
)


def _accept_set_laser(core, args):
    only(args, ("laser", "wait", "update_etl"))
    return {
        "laser": option(core, args, "laser"),
        "wait": flag(args, "wait", False),
        "update_etl": flag(args, "update_etl", True),
    }


def _run_set_laser(core, args):
    core.set_laser(args["laser"], wait_until_done=args["wait"], update_etl=args["update_etl"])
    refresh_window_after(core, {"laser": args["laser"]})
    return {}


command(
    "set_laser",
    ACTION,
    _run_set_laser,
    schema=_schema({"laser": _setting_schema("laser"), "wait": _WAIT, "update_etl": _BOOLEAN}, required=("laser",)),
    accept=_accept_set_laser,
    hint="in: {laser, wait?, update_etl?}. out: {}",
)


def _accept_set_shutterconfig(core, args):
    only(args, ("shutterconfig",))
    return {"shutterconfig": option(core, args, "shutterconfig")}


def _run_set_shutterconfig(core, args):
    core.set_shutterconfig(args["shutterconfig"])
    refresh_window_after(core, {"shutterconfig": args["shutterconfig"]})
    return {}


command(
    "set_shutterconfig",
    ACTION,
    _run_set_shutterconfig,
    schema=_schema({"shutterconfig": _setting_schema("shutterconfig")}, required=("shutterconfig",)),
    accept=_accept_set_shutterconfig,
    hint="in: {shutterconfig}. out: {}",
)


def _accept_set_intensity(core, args):
    only(args, ("intensity", "wait"))
    return {"intensity": number(args, "intensity", config.PERCENT_RANGE), "wait": flag(args, "wait", False)}


def _run_set_intensity(core, args):
    core.set_intensity(args["intensity"], wait_until_done=args["wait"])
    refresh_window_after(core, {"intensity": args["intensity"]})
    return {}


command(
    "set_intensity",
    ACTION,
    _run_set_intensity,
    schema=_schema({"intensity": _PERCENT, "wait": _WAIT}, required=("intensity",)),
    accept=_accept_set_intensity,
    hint="in: {intensity 0..100, wait?}. out: {}",
)


# The four grouped setters share _run_state_settings but keep distinct named accepts.
def _accept_set_camera(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_camera"])}


command(
    "set_camera",
    ACTION,
    _run_state_settings,
    schema=_settings_schema(config.SETTING_GROUPS["set_camera"]),
    accept=_accept_set_camera,
    hint="in: one or more set_camera keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_etl(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_etl"])}


command(
    "set_etl",
    ACTION,
    _run_state_settings,
    schema=_settings_schema(config.SETTING_GROUPS["set_etl"]),
    accept=_accept_set_etl,
    hint="in: one or more set_etl keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_galvo(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_galvo"])}


command(
    "set_galvo",
    ACTION,
    _run_state_settings,
    schema=_settings_schema(config.SETTING_GROUPS["set_galvo"]),
    accept=_accept_set_galvo,
    hint="in: one or more set_galvo keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_laser_timing(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_laser_timing"])}


command(
    "set_laser_timing",
    ACTION,
    _run_state_settings,
    schema=_settings_schema(config.SETTING_GROUPS["set_laser_timing"]),
    accept=_accept_set_laser_timing,
    hint="in: one or more set_laser_timing keys (see get_capabilities.setting_groups). out: {}",
)


# --- Electrically tunable lens settings ---
def _etl_request(core, request, wait):
    if wait:
        core.sig_state_request_and_wait_until_done.emit(request)
    else:
        core.sig_state_request.emit(request)
    return _state_snapshot(core, config.ETL_READBACK_KEYS)


# `.get(key, state_fallback)` — an explicit empty arg is kept and then rejected, not silently
# replaced by the state value.
def _accept_reload_etl_config(core, args):
    only(args, ("path", "wait"))
    cfg_file = args.get("path", state(core, "ETL_cfg_file"))
    if not isinstance(cfg_file, str) or not cfg_file:
        raise ValidationError("path is required when ETL_cfg_file is not set")
    # Core stores the path before it opens the file; a wrong one would break every later ETL update.
    if not cfg_file.lower().endswith(".csv") or not os.path.isfile(os.path.join(core.package_directory, cfg_file)):
        raise ValidationError(f"no ETL config .csv file at {cfg_file!r}")
    return {"request": {"ETL_cfg_file": cfg_file}, "wait": flag(args, "wait", True)}


def _accept_update_etl_from_laser(core, args):
    only(args, ("laser", "wait"))
    laser = args.get("laser", state(core, "laser"))
    if not isinstance(laser, str) or not laser:
        raise ValidationError("laser is required when state['laser'] is not set")
    if laser not in _cfg_options(core)["laser"]:
        raise ValidationError(f"laser={laser!r} is not one of {_cfg_options(core)['laser']}")
    return {"request": {"set_etls_according_to_laser": laser}, "wait": flag(args, "wait", True)}


def _accept_update_etl_from_zoom(core, args):
    only(args, ("zoom", "wait"))
    zoom = args.get("zoom", state(core, "zoom"))
    if not isinstance(zoom, str) or not zoom:
        raise ValidationError("zoom is required when state['zoom'] is not set")
    if zoom not in _cfg_options(core)["zoom"]:
        raise ValidationError(f"zoom={zoom!r} is not one of {_cfg_options(core)['zoom']}")
    return {"request": {"set_etls_according_to_zoom": zoom}, "wait": flag(args, "wait", True)}


def _run_etl(core, args):
    return _etl_request(core, args["request"], args["wait"])


command(
    "reload_etl_config",
    ACTION,
    _run_etl,
    schema=_schema({"path": {**_STRING, "description": "ETL config file; omit for the current one"}, "wait": _WAIT}),
    accept=_accept_reload_etl_config,
    hint="in: {path?, wait?}. out: ETL readback",
)
command(
    "update_etl_from_laser",
    ACTION,
    _run_etl,
    schema=_schema({"laser": _setting_schema("laser"), "wait": _WAIT}),
    accept=_accept_update_etl_from_laser,
    hint="in: {laser?, wait?}. out: ETL readback",
)
command(
    "update_etl_from_zoom",
    ACTION,
    _run_etl,
    schema=_schema({"zoom": _setting_schema("zoom"), "wait": _WAIT}),
    accept=_accept_update_etl_from_zoom,
    hint="in: {zoom?, wait?}. out: ETL readback",
)


def _run_save_etl_config(core, args):
    core.sig_save_etl_config.emit()
    return {}


command("save_etl_config", ACTION, _run_save_etl_config, accept=no_args, hint="in: none. out: {}")


# --- shutters ---
def _run_open_shutters(core, args):
    core.open_shutters()
    return {"shutterstate": state(core, "shutterstate")}


command("open_shutters", ACTION, _run_open_shutters, accept=no_args, hint="in: none. out: {shutterstate}")


# --- Operating modes ---
def _run_start_live(core, args):
    defer_wait(core, config.MILESTONE_FINISHED, lambda: core.set_state("live"))
    return {"scheduled": True, "mode": "live"}


command(
    "start_live",
    WAIT,
    _run_start_live,
    accept=no_args,
    milestone=config.MILESTONE_FINISHED,
    running_state="live",
    hint="in: none. out: {scheduled, mode}. completes on sig_finished",
)


def _run_start_visual_mode(core, args):
    defer_wait(core, config.MILESTONE_FINISHED, lambda: core.set_state("visual_mode"))
    return {"scheduled": True, "mode": "visual_mode"}


command(
    "start_visual_mode",
    WAIT,
    _run_start_visual_mode,
    accept=no_args,
    milestone=config.MILESTONE_FINISHED,
    running_state="visual_mode",
    hint="in: none. out: {scheduled, mode}. completes on sig_finished",
)


def _run_start_lightsheet_alignment_mode(core, args):
    defer_wait(core, config.MILESTONE_FINISHED, lambda: core.set_state("lightsheet_alignment_mode"))
    return {"scheduled": True, "mode": "lightsheet_alignment_mode"}


command(
    "start_lightsheet_alignment_mode",
    WAIT,
    _run_start_lightsheet_alignment_mode,
    accept=no_args,
    milestone=config.MILESTONE_FINISHED,
    running_state="lightsheet_alignment_mode",
    hint="in: none. out: {scheduled, mode}",
)


# --- Snap ---
def _accept_snap(core, args):
    only(args, ("folder", "prefix"))
    folder = text(args, "folder", required=False)
    default = state(core, "snap_folder")
    if folder is not None and not os.path.isdir(folder):
        raise ValidationError(f"the folder {folder!r} does not exist on the microscope PC; pass an existing folder, "
                              f"or omit folder to use the snap folder {default!r}")
    # mesoSPIM's writer only logs a failed write, so an unchecked default folder saves nothing silently.
    if folder is None and not os.path.isdir(default or ""):
        raise ValidationError(f"the snap folder {default!r} does not exist on the microscope PC; "
                              "pass an existing folder, or set the snap folder in mesoSPIM")
    prefix = text(args, "prefix", required=False, default="remote")
    if not prefix or os.path.basename(prefix) != prefix:
        raise ValidationError("prefix must be a plain filename prefix without path separators")
    return {"folder": folder, "prefix": prefix}


def _run_snap(core, args):
    """Capture one frame and save it as the GUI Snap button does, minus the prefix dialog.

    ``Core.snap(write_flag=False)`` runs the exposure and puts the frame in the display queue. The
    GUI path would then open a modal prefix dialog on the microscope PC, which a remote client
    cannot answer, so this command saves the frame itself through the same image writer. The frame
    arrives from the camera thread, so the queue is cleared first and polled until it holds the
    new frame.
    """
    from PyQt5 import QtCore

    single_shot = getattr(core, "_remote_control_single_shot", QtCore.QTimer.singleShot)
    folder, prefix = args["folder"], args["prefix"]
    operation_id = schedule_current(core)
    deadline = time.monotonic() + config.SNAP_TIMEOUT_SEC

    def capture():
        if not claim_scheduled(core, operation_id):
            return
        try:
            core.frame_queue_display.clear()
            core.state["state"] = "snap"
            try:
                core.snap(write_flag=False)
            finally:
                core.state["state"] = "idle"
        except Exception as error:
            fail(core, config.MILESTONE_SNAP, error)
            return
        single_shot(config.SNAP_POLL_INTERVAL_MS, save)

    def save():
        operation = _session(core).get("operation")
        if operation is None or operation.get("id") != operation_id:
            return
        if operation.get("status") not in ("processing", "stopping"):
            return
        if not core.frame_queue_display:
            if time.monotonic() < deadline:
                single_shot(config.SNAP_POLL_INTERVAL_MS, save)
            else:
                fail(core, config.MILESTONE_SNAP, RuntimeError("no frame arrived from the camera"))
            return
        try:
            path = _write_snap(core, core.frame_queue_display[0], folder, prefix)
            operation["result"] = {"path": path}
            _session(core)["last_snap"] = path
        except Exception as error:
            fail(core, config.MILESTONE_SNAP, error)
            return
        complete(core, config.MILESTONE_SNAP)

    single_shot(0, capture)
    return {"scheduled": True, "prefix": prefix}


class _WriterErrors(logging.Handler):
    """The errors mesoSPIM's image writer logs while it runs: write_snap_image catches its own
    exception and only logs it, so its logger is where a failed write says why."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.messages = []

    def emit(self, record):
        if record.name.endswith("mesoSPIM_ImageWriter"):
            self.messages.append(record.getMessage())


def _write_snap(core, image, folder, prefix):
    """Save through mesoSPIM's own snap writer and return the file it wrote. The writer saves into
    the state's snap folder, so a named folder is set for this write only: the operator's snap
    folder stays theirs, and the GUI's Snap keeps saving where the GUI says. A failed write is
    judged by the error the writer logs, not by file times: on Windows two writes within one
    clock tick share a modification time. The writer names a snap by the second, so the newest
    matching file is the one just written, a same-second overwrite included."""
    operator_folder = state(core, "snap_folder")
    folder = folder or operator_folder
    pattern = os.path.join(folder, f"{prefix}_*.tif")
    errors = _WriterErrors()
    logging.getLogger().addHandler(errors)
    core.state["snap_folder"] = folder
    try:
        core.image_writer.write_snap_image(image, prefix=prefix)
    finally:
        core.state["snap_folder"] = operator_folder
        logging.getLogger().removeHandler(errors)
    if errors.messages:
        raise RuntimeError(f"the image writer could not save the snap: {'; '.join(errors.messages)}")
    written = glob.glob(pattern)
    if not written:
        raise RuntimeError(f"the image writer saved nothing matching {pattern!r}")
    return max(written, key=os.path.getmtime)


command(
    "snap",
    WAIT,
    _run_snap,
    schema=_schema({"folder": {**_STRING, "description": "existing directory; omit for the snap folder"}, "prefix": _STRING}),
    accept=_accept_snap,
    milestone=config.MILESTONE_SNAP,
    hint="in: {folder?, prefix?}. out: {scheduled, prefix}; get_progress result gives {path}. "
    "saves one frame as the GUI Snap does, without its prefix dialog",
)


# --- Configured sample positions ---
def _preset_targets(core, mapping, required_message):
    """Build absolute targets from cfg-defined preset positions, each checked against the effective
    limits BEFORE the gate. A preset drives the stage, so it is bounded like any other move — even
    though a remote client supplies no coordinates here (the destinations come from the loaded
    config). A configured preset that lands outside the effective envelope is refused rather than
    silently driving past a limit."""
    params = cfg_dict(core, "stage_parameters")
    limits = effective_limits(core)
    targets = {}
    for axis, key in mapping:
        if key in params:
            value = _finite(params[key], f"stage_parameters.{key}")

            # Apply the same pre-Core safety check used by move_absolute.
            check_absolute(limits, axis, value)
            targets[axis] = value

    if not targets:
        raise ValidationError(required_message)
    return targets


def _preset_move(core, targets):
    move = {f"{axis}_abs": value for axis, value in targets.items()}
    worker_move = getattr(getattr(core, "serial_worker", None), "move_absolute", None)
    action = (
        (lambda: worker_move(move, wait_until_done=False, use_internal_position=False))
        if callable(worker_move)
        else (lambda: core.move_absolute(move, wait_until_done=False, use_internal_position=False))
    )
    defer_position_move(core, targets, action, absolute=True)


def _accept_load_sample(core, args):
    only(args, ())
    return {
        "targets": _preset_targets(
            core, [("y", "y_load_position")], "stage configuration has no y_load_position"
        )
    }


def _run_load_sample(core, args):
    _preset_move(core, args["targets"])
    return {"target": args["targets"]}


command(
    "load_sample",
    WAIT,
    _run_load_sample,
    accept=_accept_load_sample,
    milestone=config.MILESTONE_POSITION,
    hint="in: none. out: {target}",
)


def _accept_unload_sample(core, args):
    only(args, ())
    return {
        "targets": _preset_targets(
            core, [("y", "y_unload_position")], "stage configuration has no y_unload_position"
        )
    }


def _run_unload_sample(core, args):
    _preset_move(core, args["targets"])
    return {"target": args["targets"]}


command(
    "unload_sample",
    WAIT,
    _run_unload_sample,
    accept=_accept_unload_sample,
    milestone=config.MILESTONE_POSITION,
    hint="in: none. out: {target}",
)


def _accept_center_sample(core, args):
    only(args, ())
    return {
        "targets": _preset_targets(
            core,
            [("x", "x_center_position"), ("z", "z_center_position")],
            "stage configuration has no x_center_position or z_center_position",
        )
    }


def _run_center_sample(core, args):
    _preset_move(core, args["targets"])
    return {"target": args["targets"]}


command(
    "center_sample",
    WAIT,
    _run_center_sample,
    accept=_accept_center_sample,
    milestone=config.MILESTONE_POSITION,
    hint="in: none. out: {target}",
)


# --- Acquisition operations ---
def _accept_set_acquisition_list(core, args):
    only(args, ("acquisitions", "selected_row"))
    acqs = args.get("acquisitions")
    if not isinstance(acqs, list):
        raise ValidationError("'acquisitions' must be a list")
    if not acqs:
        raise ValidationError("'acquisitions' must contain at least one row")
    clean = [check_acquisition(core, acq, f"acquisitions[{i}]") for i, acq in enumerate(acqs)]
    out = {"acquisitions": clean}

    # Check the selected row against the new list, not the previously installed list.
    if "selected_row" in args:
        selected = integer(args, "selected_row", minimum=0)
        if (not clean and selected != 0) or (clean and selected >= len(clean)):
            raise ValidationError(f"'selected_row'={selected} is outside 0..{max(0, len(clean) - 1)}")
        out["selected_row"] = selected
    return out


def _run_set_acquisition_list(core, args):
    acquisitions = _make_acquisition_list(args["acquisitions"])
    core.state["acq_list"] = acquisitions
    if "selected_row" in args:
        core.state["selected_row"] = args["selected_row"]
    # Upstream time lapse renames files through the GUI AcquisitionModel. Keep that model and Core's
    # state on the same AcquisitionList, or its first dataChanged signal restores the stale GUI rows.
    # RemoteControlGUI supplies a queued Core->GUI bridge (never blocking: Core must not wait on the
    # GUI thread, which may itself be waiting on Core); headless/unit cores intentionally do not.
    bridge = getattr(core, "_remote_control_acquisition_list_signal", None)
    if bridge is not None:
        bridge.emit(acquisitions, args.get("selected_row"))
    return {"count": len(acquisitions)}


command(
    "set_acquisition_list",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"acquisitions": _ACQUISITIONS, "selected_row": _ROW}, required=("acquisitions",)),
    accept=_accept_set_acquisition_list,
    hint="in: {acquisitions:[...], selected_row?}. out: {count}",
)


# --- The acquisition table, as the acquisition manager edits it ---
# Every edit builds the whole new table and hands it to set_acquisition_list's own accept and
# install: the same row checks (limits, options, plane count), the same busy gate, the same bridge
# to the manager window. No table edit has a path of its own.
def _installed(core):
    """The installed rows as plain objects, in order, every key present (as the list models them)."""
    rows = jsonable(_make_acquisition_list(jsonable(state(core, "acq_list", []) or [])))
    return [{key: value for key, value in row.items() if value is not None} for row in rows]


def _as_list(core, rows, selected=None):
    """The changed table, checked as set_acquisition_list checks it, ready for its install."""
    args = {"acquisitions": rows}
    if selected is not None:
        args["selected_row"] = selected
    return _accept_set_acquisition_list(core, args)


def _row_list(args, key, count, required=True):
    """A list of distinct row indices into a table of `count` rows; all rows when omitted."""
    if key not in args:
        if required:
            raise ValidationError(f"{key!r} is required")
        return list(range(count))
    rows = args[key]
    if not isinstance(rows, list) or not rows:
        raise ValidationError(f"{key!r} must be a non-empty list of row indices")
    for i, value in enumerate(rows):
        integer({"row": value}, "row", minimum=0, maximum=count - 1)
    if len(set(rows)) != len(rows):
        raise ValidationError(f"{key!r} names a row twice")
    return rows


def _row_index(args, key, count):
    return integer(args, key, minimum=0, maximum=count - 1)


def _accept_update_acquisition_row(core, args):
    only(args, ("row", "changes"))
    rows = _installed(core)
    row = _row_index(args, "row", len(rows))
    changes = args.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ValidationError("'changes' must name at least one row key and its new value")
    rows[row].update(changes)
    return _as_list(core, rows, row)


command(
    "update_acquisition_row",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"row": _ROW, "changes": {"type": "object", "additionalProperties": True,
                                             "description": "row key: new value; the rest of the row stays"}},
                   required=("row", "changes")),
    accept=_accept_update_acquisition_row,
    hint="in: {row, changes:{key: value}}. out: {count}",
)


def _accept_add_acquisition_rows(core, args):
    from ..utils.acquisitions import Acquisition

    only(args, ("rows", "like", "at"))
    installed = _installed(core)
    new = args.get("rows", [{}])
    if not isinstance(new, list) or not new or not all(isinstance(row, dict) for row in new):
        raise ValidationError("'rows' must be a non-empty list of row objects")
    base = installed[_row_index(args, "like", len(installed))] if "like" in args else \
        {key: value for key, value in Acquisition().items() if value is not None}
    at = integer(args, "at", minimum=0, maximum=len(installed), required=False, default=len(installed))
    rows = installed[:at] + [dict(base, **row) for row in new] + installed[at:]
    return _as_list(core, rows, at)


command(
    "add_acquisition_rows",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"rows": {"type": "array", "items": {"type": "object", "additionalProperties": True},
                             "description": "row objects; a key left out takes the value of row `like`, or the default"},
                    "like": _ROW, "at": {"type": "integer", "minimum": 0, "description": "insert before this row; the end when omitted"}}),
    accept=_accept_add_acquisition_rows,
    hint="in: {rows?:[{...}], like?, at?}: one default row at the end when empty; like copies a row. out: {count}",
)


def _accept_delete_acquisition_rows(core, args):
    only(args, ("rows",))
    installed = _installed(core)
    gone = set(_row_list(args, "rows", len(installed)))
    if len(gone) == len(installed):
        raise ValidationError("the list keeps at least one row; set_acquisition_list replaces it whole")
    return _as_list(core, [row for i, row in enumerate(installed) if i not in gone], 0)


command(
    "delete_acquisition_rows",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"rows": {"type": "array", "items": _ROW, "minItems": 1}}, required=("rows",)),
    accept=_accept_delete_acquisition_rows,
    hint="in: {rows:[...]}. out: {count}",
)


def _accept_move_acquisition_row(core, args):
    only(args, ("row", "to"))
    rows = _installed(core)
    row, to = _row_index(args, "row", len(rows)), _row_index(args, "to", len(rows))
    rows.insert(to, rows.pop(row))
    return _as_list(core, rows, to)


command(
    "move_acquisition_row",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"row": _ROW, "to": _ROW}, required=("row", "to")),
    accept=_accept_move_acquisition_row,
    hint="in: {row, to}. out: {count}",
)


def _accept_mark_acquisition_rows(core, args):
    from ..utils.acquisitions import value_from_state

    only(args, ("rows", "marks"))
    rows = _installed(core)
    chosen = _row_list(args, "rows", len(rows))
    marks = args.get("marks")
    if not isinstance(marks, list) or not marks or not all(m in (*config.ROW_MARKS, "all") for m in marks):
        raise ValidationError(f"'marks' must list some of: {', '.join(config.ROW_MARKS)}, or all")
    keys = [key for group, keys in config.ROW_MARKS.items() if group in marks or "all" in marks for key in keys]
    for row in chosen:
        rows[row].update({key: value_from_state(core.state, key) for key in keys})
    return _as_list(core, rows, chosen[0])


command(
    "mark_acquisition_rows",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"rows": {"type": "array", "items": _ROW, "minItems": 1},
                    "marks": {"type": "array", "minItems": 1, "items": {"enum": [*config.ROW_MARKS, "all"]}}},
                   required=("rows", "marks")),
    accept=_accept_mark_acquisition_rows,
    hint="in: {rows, marks:[xy|rotation|focus|etl|state|all]}: the rows take the instrument's current values. out: {count}",
)


def _csv_path(args, must_exist):
    path = text(args, "path")
    if not path.lower().endswith(".csv"):
        raise ValidationError("'path' must name a .csv file")
    if must_exist and not os.path.isfile(path):
        raise ValidationError(f"{path!r} does not exist")
    if not must_exist and not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise ValidationError(f"the folder of {path!r} does not exist")
    return path


def _accept_save_acquisition_list(core, args):
    only(args, ("path", "overwrite"))
    path = _csv_path(args, must_exist=False)
    if os.path.exists(path) and not flag(args, "overwrite", False):
        raise ValidationError(f"{path!r} exists; pass overwrite true to replace it")
    return {"path": path}


def _run_save_acquisition_list(core, args):
    _make_acquisition_list(_installed(core)).to_csv(args["path"])
    return {"path": args["path"], "count": _acq_count(core)}


command(
    "save_acquisition_list",
    ACTION,
    _run_save_acquisition_list,
    schema=_schema({"path": _STRING, "overwrite": _BOOLEAN}, required=("path",)),
    accept=_accept_save_acquisition_list,
    hint="in: {path (.csv), overwrite?}. out: {path, count}",
)


def _accept_load_acquisition_list(core, args):
    from ..utils.acquisitions import AcquisitionList

    only(args, ("path",))
    try:
        rows = [dict(row) for row in AcquisitionList.from_csv(_csv_path(args, must_exist=True))]
    except (OSError, ValueError, KeyError) as error:
        raise ValidationError(f"{args['path']!r} could not be read as an acquisition list: {error}") from None
    if not rows:
        raise ValidationError(f"{args['path']!r} holds no rows")
    return _as_list(core, [{k: v for k, v in row.items() if k in config.ACQUISITION_FIELDS} for row in rows], 0)


command(
    "load_acquisition_list",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"path": _STRING}, required=("path",)),
    accept=_accept_load_acquisition_list,
    hint="in: {path (.csv)}: replaces the list. out: {count}",
)


def _writer(core, args, rows):
    """The image writer named, or the one the first row names: (name, its naming rules, extension)."""
    from ..plugins.utils import get_image_writer_from_name

    name = text(args, "writer", required=False) or (rows[0].get("image_writer_plugin") if rows else None)
    writer = get_image_writer_from_name(name) if name else None
    if not writer:
        known = ", ".join(f"{w['name']} ({', '.join(w['file_extensions'])})" for w in _image_writers())
        raise ValidationError(f"{'unknown image writer ' + repr(name) if name else 'name a writer'}: one of {known}")
    extensions = writer.get("file_extensions")
    extension = extensions[0] if isinstance(extensions, (list, tuple)) else extensions
    return writer["name"], writer["file_names"], extension


def _named(core, args, rows):
    """The rows with the file names of the writer's rules, as the filename wizard gives them."""
    from ..utils.acquisitions import AcquisitionList

    name, file_names, extension = _writer(core, args, rows)
    filenames = AcquisitionList(_make_acquisition_list(rows)).filenames(
        file_names, extension, text(args, "description", required=False, default=""))
    return [dict(row, filename=filename, image_writer_plugin=name) for row, filename in zip(rows, filenames)]


def _accept_name_acquisition_rows(core, args):
    only(args, ("writer", "description"))
    return _as_list(core, _named(core, args, _installed(core)))


command(
    "name_acquisition_rows",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({"writer": {**_STRING, "description": "an image writer's name; the first row's when omitted"},
                    "description": {**_STRING, "description": "put first in every name"}}),
    accept=_accept_name_acquisition_rows,
    hint="in: {writer?, description?}: every row named by the writer's rules, as the filename wizard does. out: {count}",
)


def _accept_track_focus(core, args):
    from ..utils.acquisitions import focus_at

    only(args, ("z_1", "f_1", "z_2", "f_2", "rows", "laser", "filter"))
    z_1, f_1, z_2, f_2 = (number(args, key) for key in ("z_1", "f_1", "z_2", "f_2"))
    if z_1 == z_2:
        raise ValidationError("z_1 and z_2 must differ")
    rows = _installed(core)
    chosen = _row_list(args, "rows", len(rows), required=False)
    for key in ("laser", "filter"):
        if key in args:
            check_setting(core, key, args[key])
            chosen = [i for i in chosen if rows[i].get(key) == args[key]]
    if not chosen:
        raise ValidationError("no row has that laser and filter")
    for i in chosen:
        rows[i]["f_start"] = focus_at(z_1, z_2, f_1, f_2, rows[i]["z_start"])
        rows[i]["f_end"] = focus_at(z_1, z_2, f_1, f_2, rows[i]["z_end"])
    return _as_list(core, rows, chosen[0])


command(
    "track_focus",
    ACTION,
    _run_set_acquisition_list,
    schema=_schema({**{key: _NUMBER for key in ("z_1", "f_1", "z_2", "f_2")},
                    "rows": {"type": "array", "items": _ROW, "minItems": 1},
                    "laser": _setting_schema("laser"), "filter": _setting_schema("filter")},
                   required=("z_1", "f_1", "z_2", "f_2")),
    accept=_accept_track_focus,
    hint="in: {z_1, f_1, z_2, f_2, rows?, laser?, filter?}: each row's focus range on the line through the two points. out: {count}",
)


def _channel(core, channel, label):
    if not isinstance(channel, dict):
        raise ValidationError(f"{label} must be an object")
    only(channel, ("laser", "intensity", "filter", "f_start", "f_end", *config.ROW_MARKS["etl"]))
    out = {key: state(core, key) for key in config.ROW_MARKS["etl"]}
    out.update(f_start=state(core, "position")["f_pos"], f_end=state(core, "position")["f_pos"])
    for key in ("laser", "intensity", "filter"):
        if key not in channel:
            raise ValidationError(f"{label}.{key} is required")
        try:
            check_setting(core, key, channel[key])
        except ValidationError as error:
            raise ValidationError(f"{label}: {error}") from None
    out.update(channel)
    return out


def _accept_build_tiling_list(core, args):
    from ..utils.multicolor_acquisition_builder import (
        MulticolorTilingAcquisitionListBuilder,
        field_of_view_um,
        image_counts,
        tile_offsets,
    )

    only(args, ("x_start", "x_end", "y_start", "y_end", "z_start", "z_end", "z_step", "zoom", "shutterconfig",
                "both_sides", "overlap_percent", "x_offset", "y_offset", "channels", "folder", "writer", "description"))
    box = {key: number(args, key) for key in ("x_start", "x_end", "y_start", "y_end", "z_start", "z_end", "z_step")}
    if box["z_step"] <= 0:
        raise ValidationError("'z_step' must be positive")
    zoom = option(core, args, "zoom") if "zoom" in args else state(core, "zoom")
    shutterconfig = option(core, args, "shutterconfig") if "shutterconfig" in args else state(core, "shutterconfig")
    if "x_offset" in args or "y_offset" in args:
        if "overlap_percent" in args:
            raise ValidationError("give overlap_percent or x_offset and y_offset, not both")
        x_offset, y_offset = number(args, "x_offset", (1, 1e6)), number(args, "y_offset", (1, 1e6))
    else:
        overlap = number(args, "overlap_percent", (0, 90), required=False, default=10)
        camera = cfg_dict(core, "camera_parameters")
        pixelsize = cfg_dict(core, "pixelsize").get(zoom)
        if not pixelsize:
            raise ValidationError(f"no pixel size is configured for zoom {zoom!r}")
        x_offset, y_offset = tile_offsets(*field_of_view_um(camera["x_pixels"], camera["y_pixels"], pixelsize), overlap)
    x_count, y_count = image_counts(box["x_start"], box["x_end"], box["y_start"], box["y_end"], x_offset, y_offset)
    channels = args.get("channels")
    if not isinstance(channels, list) or not channels:
        raise ValidationError("'channels' must be a non-empty list of {laser, intensity, filter, ...}")
    channels = [_channel(core, channel, f"channels[{i}]") for i, channel in enumerate(channels)]
    both = flag(args, "both_sides", False)
    count = x_count * y_count * len(channels) * (2 if both else 1)
    if count > config.MAX_TILING_ROWS:
        raise ValidationError(f"{x_count} x {y_count} tiles x {len(channels)} channels make {count} rows; "
                              f"at most {config.MAX_TILING_ROWS}")
    built = MulticolorTilingAcquisitionListBuilder(dict(
        box, x_offset=x_offset, y_offset=y_offset, x_image_count=x_count, y_image_count=y_count, zoom=zoom,
        shutterconfig=shutterconfig, shutter_seq=both, folder=text(args, "folder"), channels=channels,
        theta_pos=state(core, "position")["theta_pos"])).get_acquisition_list()
    return _as_list(core, _named(core, args, [dict(row) for row in built]), 0)


def _run_build_tiling_list(core, args):
    out = _run_set_acquisition_list(core, args)
    rows = args["acquisitions"]
    out["tiles"] = len({(row["x_pos"], row["y_pos"]) for row in rows})
    out["first"] = rows[0]
    return out


command(
    "build_tiling_list",
    ACTION,
    _run_build_tiling_list,
    schema=_schema({**{key: _NUMBER for key in ("x_start", "x_end", "y_start", "y_end", "z_start", "z_end")},
                    "z_step": {"type": "number", "exclusiveMinimum": 0},
                    "zoom": _setting_schema("zoom"), "shutterconfig": _setting_schema("shutterconfig"),
                    "both_sides": {**_BOOLEAN, "description": "each tile once from the left and once from the right"},
                    "overlap_percent": {"type": "number", "minimum": 0, "maximum": 90, "description": "10 when omitted"},
                    "x_offset": _NUMBER, "y_offset": _NUMBER,
                    "channels": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
                        "laser": _setting_schema("laser"), "intensity": _PERCENT, "filter": _setting_schema("filter"),
                        "f_start": _NUMBER, "f_end": _NUMBER}, "required": ["laser", "intensity", "filter"],
                        "additionalProperties": True}},
                    "folder": _STRING, "writer": _STRING, "description": _STRING},
                   required=("x_start", "x_end", "y_start", "y_end", "z_start", "z_end", "z_step", "channels", "folder")),
    accept=_accept_build_tiling_list,
    hint="in: {x/y/z start and end, z_step, channels:[{laser, intensity, filter, f_start?, f_end?}], folder, "
         "overlap_percent? | x_offset, y_offset, zoom?, shutterconfig?, both_sides?, writer?, description?}: "
         "replaces the list with the tiling wizard's grid, named by the writer's rules. out: {count, tiles, first}",
)


def _accept_set_snap_folder(core, args):
    only(args, ("folder",))
    folder = text(args, "folder")
    if not os.path.isdir(folder):
        raise ValidationError(f"{folder!r} is not an existing folder")
    return {"folder": folder}


def _run_set_snap_folder(core, args):
    core.state["snap_folder"] = args["folder"]            # as the window's Choose button does; Core has no key for it
    refresh_window_after(core, {"snap_folder": args["folder"]})
    return {}


command(
    "set_snap_folder",
    ACTION,
    _run_set_snap_folder,
    schema=_schema({"folder": _STRING}, required=("folder",)),
    accept=_accept_set_snap_folder,
    hint="in: {folder}: where snaps are saved. out: {}",
)



# --- The windows: what the operator sees and sets there (gui_handles works the windows) ----------
# A display call changes only what a window shows, never the instrument: it is never gated
# (dispatcher.DISPLAY), returns a request number at once, and the GUI thread carries it out a moment
# later; get_display {request} says when. Positions in the camera window are in the camera frame's own
# pixels (x the column, y the row, as get_frame gives the frame), whatever subsampling it shows at.

IMAGE_VIEW_SETTINGS = ("levels", "colormap", "colormap_ticks", "colormap_mode", "histogram_range", "view",
                       "invert_x", "invert_y", "profile_roi", "normalization")
DISPLAY_SETTINGS = {
    "camera": IMAGE_VIEW_SETTINGS + ("adjust_levels", "overlay", "box_roi", "line_roi", "frame_index"),
    "contrast": IMAGE_VIEW_SETTINGS,
    "tile_overview": ("scale", "scroll"),
    "main": ("tab",),
}
TILE_SCALE = (0.005, 1.0)                      # the tile overview's own scale box
PICTURE_FORMATS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def _region(value, label, keys, frame=None):
    """A rectangle or a line in frame pixels: exactly `keys`, finite numbers, inside the frame."""
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be {{{', '.join(keys)}}} in frame pixels")
    only(value, keys)
    region = {key: number(value, key) for key in keys}
    if "width" in region and (region["width"] <= 0 or region["height"] <= 0):
        raise ValidationError(f"{label} width and height must be positive")
    if frame is not None:
        width, height = frame
        xs = [region[k] for k in ("x", "x1", "x2") if k in region]
        ys = [region[k] for k in ("y", "y1", "y2") if k in region]
        if "width" in region:
            xs.append(region["x"] + region["width"])
            ys.append(region["y"] + region["height"])
        if min(xs + ys) < 0 or max(xs) > width or max(ys) > height:
            raise ValidationError(f"{label} is outside the frame ({width} x {height} pixels)")
    return region


def _pair(args, key):
    """[low, high], two finite numbers with low < high."""
    pair = args[key]
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValidationError(f"{key} must be [low, high] with low < high")
    low, high = _finite(pair[0], f"{key}[0]"), _finite(pair[1], f"{key}[1]")
    if not low < high:
        raise ValidationError(f"{key} must be [low, high] with low < high")
    return [low, high]


def _ticks(args):
    """A lookup table as the histogram's gradient holds it: [[position 0..1, [r, g, b, a] 0..255], ...]."""
    ticks = args["colormap_ticks"]
    if not isinstance(ticks, list) or len(ticks) < 2:
        raise ValidationError("colormap_ticks must be two or more [position, [r, g, b, a]]")
    clean = []
    for i, tick in enumerate(ticks):
        if not (isinstance(tick, list) and len(tick) == 2 and isinstance(tick[1], list) and len(tick[1]) in (3, 4)):
            raise ValidationError(f"colormap_ticks[{i}] must be [position, [r, g, b, a]]")
        position = _finite(tick[0], f"colormap_ticks[{i}] position")
        if not 0 <= position <= 1:
            raise ValidationError(f"colormap_ticks[{i}] position must be between 0 and 1")
        color = list(tick[1]) + ([255] if len(tick[1]) == 3 else [])
        if any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c <= 255 for c in color):
            raise ValidationError(f"colormap_ticks[{i}] colour must be integers 0..255")
        clean.append([position, color])
    return clean


def check_display(frame, args):
    """set_display's arguments, for the window they name (the camera window when none), against the
    camera frame (width, height). Run when the call arrives, and again on the GUI thread before it is
    carried out (the frame may have changed size since)."""
    window = args.get("window", "camera")
    if window not in DISPLAY_SETTINGS:
        raise ValidationError(f"window {window!r} is not one of {list(DISPLAY_SETTINGS)}")
    only(args, ("window",) + DISPLAY_SETTINGS[window])
    camera = window == "camera"
    out = {"window": window} if "window" in args else {}
    for key in ("levels", "histogram_range"):
        if key in args:
            out[key] = _pair(args, key)
    if "colormap" in args:
        name = text(args, "colormap")
        if name not in colormaps():
            raise ValidationError(f"colormap {name!r} is not one of {colormaps()}")
        out["colormap"] = name
    if "colormap_ticks" in args:
        out["colormap_ticks"] = _ticks(args)
    if "colormap_mode" in args:
        mode = text(args, "colormap_mode")
        if mode not in ("rgb", "hsv"):
            raise ValidationError("colormap_mode is 'rgb' or 'hsv'")
        out["colormap_mode"] = mode
    for key in ("invert_x", "invert_y"):
        if key in args:
            out[key] = flag(args, key)
    if "view" in args:
        out["view"] = "fit" if args["view"] == "fit" else _region(args["view"], "view", ("x", "y", "width", "height"))
    if "profile_roi" in args:
        profile = args["profile_roi"]
        if not isinstance(profile, dict) or "shown" not in profile:
            raise ValidationError("profile_roi must be {shown, x?, y?, width?, height?}")
        only(profile, ("shown", "x", "y", "width", "height"))
        out["profile_roi"] = {"shown": flag(profile, "shown")}
        if set(profile) - {"shown"}:
            out["profile_roi"].update(_region({k: v for k, v in profile.items() if k != "shown"}, "profile_roi",
                                              ("x", "y", "width", "height"), frame if camera else None))
    if "normalization" in args:
        norm = args["normalization"]
        if not isinstance(norm, dict):
            raise ValidationError("normalization must be {mode?, roi?, frame?, time_range?}")
        only(norm, ("mode", "roi", "frame", "time_range"))
        out["normalization"] = {key: flag(norm, key) for key in ("roi", "frame", "time_range") if key in norm}
        if "mode" in norm:
            if norm["mode"] not in NORMALIZATIONS:
                raise ValidationError(f"normalization mode is one of {list(NORMALIZATIONS)}")
            out["normalization"]["mode"] = norm["mode"]
    if "adjust_levels" in args:
        adjust = args["adjust_levels"]
        if adjust is True:
            out["adjust_levels"] = True
        elif isinstance(adjust, dict):
            only(adjust, ("low_percentile", "high_percentile"))
            out["adjust_levels"] = {key: number(adjust, key, (0, 100)) for key in adjust}
        else:
            raise ValidationError("adjust_levels is true, or {low_percentile, high_percentile} between 0 and 100")
    if "overlay" in args:
        overlay = text(args, "overlay")
        if overlay not in OVERLAYS:
            raise ValidationError(f"overlay {overlay!r} is not one of {list(OVERLAYS)}")
        out["overlay"] = overlay
    if "box_roi" in args:
        out["box_roi"] = _region(args["box_roi"], "box_roi", ("x", "y", "width", "height"), frame)
    if "line_roi" in args:
        out["line_roi"] = _region(args["line_roi"], "line_roi", ("x1", "y1", "x2", "y2"), frame)
    if "frame_index" in args:
        out["frame_index"] = integer(args, "frame_index", minimum=0)
    if "scale" in args:
        out["scale"] = number(args, "scale", TILE_SCALE)
    if "scroll" in args:
        scroll = args["scroll"]
        if not isinstance(scroll, dict) or not scroll:
            raise ValidationError("scroll must be {x?, y?}, each 0..1 of the scroll bar")
        only(scroll, ("x", "y"))
        out["scroll"] = {key: number(scroll, key, (0, 1)) for key in scroll}
    if "tab" in args:
        out["tab"] = text(args, "tab")
    return out


def gui_handles(core):
    """The GUI thread's handles on the windows, published by the Remote Control tab."""
    found = getattr(core, "_remote_control_gui_handles", None)
    if found is None:
        raise ValidationError("there are no windows to change: this mesoSPIM runs without its GUI")
    return found


def _accept_set_display(core, args):
    gui_handles(core)
    return check_display(frame_size(core, core.cfg), args)


def _accept_get_display(core, args):
    only(args, ("request",))
    if "request" in args:
        integer(args, "request", minimum=1)
    gui_handles(core)
    return args


def _window_list(args, key):
    names = args.get(key, [])
    if not isinstance(names, list) or any(name not in WINDOWS for name in names):
        raise ValidationError(f"{key} must be a list of windows from {list(WINDOWS)}")
    return names


def _accept_set_windows(core, args):
    only(args, ("show", "hide", "cascade"))
    gui_handles(core)
    out = {"show": _window_list(args, "show"), "hide": _window_list(args, "hide"), "cascade": flag(args, "cascade")}
    if set(out["show"]) & set(out["hide"]):
        raise ValidationError("a window cannot be shown and hidden at once")
    if not (out["show"] or out["hide"] or out["cascade"]):
        raise ValidationError("name windows to show or hide, or cascade")
    return out


def _accept_get_picture(core, args):
    only(args, ("window", "path", "max_size"))
    gui_handles(core)
    window = text(args, "window")
    if window not in WINDOWS:
        raise ValidationError(f"window {window!r} is not one of {list(WINDOWS)}")
    out = {"window": window, "max_size": integer(args, "max_size", 64, PICTURE_MAX, required=False, default=PICTURE_MAX)}
    if "path" in args:
        path = text(args, "path")
        if os.path.splitext(path)[1].lower() not in PICTURE_FORMATS:
            raise ValidationError(f"path must end in one of {list(PICTURE_FORMATS)}")
        if not os.path.isdir(os.path.dirname(os.path.abspath(path))):
            raise ValidationError(f"the folder of {path!r} does not exist")
        out["path"] = path
    return out


def _accept_open_image_file(core, args):
    only(args, ("path",))
    gui_handles(core)
    path = text(args, "path")
    if os.path.splitext(path)[1].lower() not in (".tif", ".tiff"):
        raise ValidationError("open_image_file opens a TIFF file (.tif or .tiff), as File > Open TIFF does")
    if not os.path.isfile(path):
        raise ValidationError(f"{path!r} is not an existing file")
    return {"path": path}


def _accept_set_table_view(core, args):
    only(args, ("group", "select_rows"))
    gui_handles(core)
    out = {}
    if "select_rows" in args:
        rows = args["select_rows"]
        if not isinstance(rows, list) or any(isinstance(r, bool) or not isinstance(r, int) or r < 0 for r in rows):
            raise ValidationError("select_rows must be a list of row indices")
        out["select_rows"] = rows
    if "group" in args:
        group = text(args, "group")
        if group not in GROUPINGS:
            raise ValidationError(f"group is one of {list(GROUPINGS)}")
        out["group"] = group
    if not out:
        raise ValidationError("name a group or rows to select")
    return out


def _on_the_gui_thread(name):
    """A display call's body: hand the accepted request to the GUI thread, return its number."""
    def execute(core, args):
        return {"request": gui_handles(core).request(name, args)}
    return execute


def _run_get_display(core, args):
    return gui_handles(core).display(args.get("request"))


_FRAME_PIXELS = ("numbers in the camera frame's pixels (x the column, y the row, as get_frame gives the frame); the "
                 "frame's width and height are get_display's camera_window.frame: the window shows the frame turned, so its "
                 "width is the camera's y_pixels and its height x_pixels")
_BOX = _schema({key: _NUMBER for key in ("x", "y", "width", "height")}, required=("x", "y", "width", "height"),
               description=_FRAME_PIXELS)
_PAIR = {"type": "array", "items": _NUMBER, "minItems": 2, "maxItems": 2}
_WINDOW_LIST = {"type": "array", "items": {"type": "string", "enum": list(WINDOWS)}}

command(
    "get_display",
    READ,
    _run_get_display,
    accept=_accept_get_display,
    schema=_schema({"request": {"type": "integer", "minimum": 1}}),
    hint="in: {request?}. out: what the windows show: the camera window's levels, lookup table, overlay, view and "
         "regions of interest in frame pixels and um (with their offset from the frame's centre); the contrast map; "
         "the tile overview; the main window's tab, status message, progress bars and time-lapse estimate; the "
         "acquisition table's grouping, selection and time and size estimates; which windows are open; and a display "
         "request's outcome",
)

command(
    "set_display",
    DISPLAY,
    _on_the_gui_thread("set_display"),
    accept=_accept_set_display,
    schema=_schema({
        "window": {"type": "string", "enum": list(DISPLAY_SETTINGS), "description": "camera when omitted"},
        "levels": {**_PAIR, "description": "[low, high] counts"},
        "adjust_levels": {"description": "camera: true, or {low_percentile, high_percentile}: the Adjust levels button (25, 99.99)",
                          "anyOf": [{"type": "boolean", "const": True},
                                    _schema({"low_percentile": _NUMBER, "high_percentile": _NUMBER})]},
        "colormap": {"type": "string", "enum": colormaps(), "description": "a lookup table of the histogram"},
        "colormap_ticks": {"type": "array", "minItems": 2, "description": "a lookup table of your own: [[position 0..1, [r, g, b, a]], ...]",
                           "items": {"type": "array", "minItems": 2, "maxItems": 2}},
        "colormap_mode": {"type": "string", "enum": ["rgb", "hsv"]},
        "histogram_range": {**_PAIR, "description": "the histogram's own axis, [low, high]"},
        "view": {"description": "the region to show, kept at square pixels, or 'fit' for the whole image",
                 "anyOf": [{"type": "string", "const": "fit"}, _BOX]},
        "invert_x": _BOOLEAN, "invert_y": _BOOLEAN,
        "profile_roi": _schema({"shown": _BOOLEAN, **{k: _NUMBER for k in ("x", "y", "width", "height")}}, required=("shown",),
                               description="the image view's own ROI button and the mean-intensity profile under it"),
        "normalization": _schema({"mode": {"type": "string", "enum": list(NORMALIZATIONS)}, "roi": _BOOLEAN,
                                  "frame": _BOOLEAN, "time_range": _BOOLEAN}),
        "overlay": {"type": "string", "enum": list(OVERLAYS), "description": "camera"},
        "box_roi": _BOX,
        "line_roi": _schema({key: _NUMBER for key in ("x1", "y1", "x2", "y2")}, required=("x1", "y1", "x2", "y2"),
                            description=_FRAME_PIXELS),
        "frame_index": {"type": "integer", "minimum": 0, "description": "camera: the frame of a stack opened with open_image_file"},
        "scale": {"type": "number", "minimum": TILE_SCALE[0], "maximum": TILE_SCALE[1], "description": "tile_overview"},
        "scroll": _schema({"x": _NUMBER, "y": _NUMBER}, description="tile_overview: 0..1 of each scroll bar"),
        "tab": {"type": "string", "description": "main: a tab's name, as get_display lists them"},
    }),
    hint="in: {window?: camera|contrast|tile_overview|main, ...what that window offers}: camera and contrast: levels, "
         "colormap or colormap_ticks and colormap_mode, histogram_range, view, invert_x/y, profile_roi, normalization; "
         "camera also adjust_levels, overlay, box_roi, line_roi (a box_roi or line_roi shows that overlay), frame_index; "
         "tile_overview: scale, scroll; main: tab. out: {request}",
)

command(
    "set_windows",
    DISPLAY,
    _on_the_gui_thread("set_windows"),
    accept=_accept_set_windows,
    schema=_schema({"show": _WINDOW_LIST, "hide": _WINDOW_LIST, "cascade": _BOOLEAN}),
    hint="in: {show?, hide?, cascade?}: open and close windows as the View menu and their close buttons do, and "
         "cascade them. out: {request}",
)

command(
    "get_picture",
    DISPLAY,
    _on_the_gui_thread("get_picture"),
    accept=_accept_get_picture,
    schema=_schema({"window": {"type": "string", "enum": list(WINDOWS)}, "path": _STRING,
                    "max_size": {"type": "integer", "minimum": 64, "maximum": PICTURE_MAX}}, required=("window",)),
    hint="in: {window, path?, max_size?}: a picture of a window as it is on screen, as PNG in the request's outcome, "
         "or saved to path (.png, .jpg, .tif, .bmp). out: {request}",
)

command(
    "open_image_file",
    DISPLAY,
    _on_the_gui_thread("open_image_file"),
    accept=_accept_open_image_file,
    schema=_schema({"path": _STRING}, required=("path",)),
    hint="in: {path}: a TIFF image or stack into the camera window, as File > Open TIFF. out: {request}",
)

command(
    "set_table_view",
    DISPLAY,
    _on_the_gui_thread("set_table_view"),
    accept=_accept_set_table_view,
    schema=_schema({"group": {"type": "string", "enum": list(GROUPINGS)},
                    "select_rows": {"type": "array", "items": {"type": "integer", "minimum": 0}}}),
    hint="in: {group?: none|laser|illumination|selected, select_rows?}: the acquisition table's selection and grouping "
         "(an edit to a group's first row then goes to the whole group). out: {request}",
)


# --- The windows' own instrument features: what only a window offers (gui_handles) ---------------
# These change the instrument, so they are ordinary operations under the busy gate. The writer
# parameters, the processor chain, Save to config and auto illumination need no window to carry
# them out; the ETL and galvo toggles and the optimizer are the window's own, so the GUI thread
# carries them out and ends the operation (dispatcher.finish_operation).

OPTIMIZER_MODES = ("focus", "etl_offset", "etl_amp")         # mesoSPIM_Optimizer's modes_list
OPTIMIZER_POINTS = (5, 29)                                   # its Num of points box: 5, 7, ... 29
OPTIMIZER_RANGE = (0.001, 500.0)                             # its Search interval box
ALIGNMENT_TOGGLES = ("zero_left_etl", "zero_right_etl", "freeze_galvo")


def _writer_class(name):
    from ..plugins.utils import get_image_writer_plugins

    for plugin in get_image_writer_plugins():
        if plugin["name"] == name:
            return plugin["writer_class"]
    known = ", ".join(w["name"] for w in _image_writers())
    raise ValidationError(f"no image writer {name!r}; there are {known}")


def _writer_parameters(core, name):
    """A writer's own settings as the filename wizard's Writer parameters page shows them: its
    wizard_parameters() defaults, overridden by the config's entry for it (and this session's)."""
    writer = _writer_class(name)
    offered = writer.wizard_parameters() if hasattr(writer, "wizard_parameters") else {}
    current = getattr(core.cfg, name, {}) or {}
    return {key: {"value": current.get(key, default), "default": default, "help": help_text}
            for key, (default, help_text) in offered.items()}


def _accept_get_writer_parameters(core, args):
    only(args, ("writer",))
    name = text(args, "writer")
    _writer_class(name)
    return {"writer": name}


def _run_get_writer_parameters(core, args):
    return {"writer": args["writer"], "parameters": _writer_parameters(core, args["writer"])}


def _writer_value(key, default, value):
    """One value as the wizard's page takes it, typed by its default: a check box for a bool, a whole
    number for an int, text (or None) for a string, and a literal (a tuple as a list, or None) for
    the rest."""
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValidationError(f"{key} must be true or false")
        return value
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValidationError(f"{key} must be a whole number >= 0")
        return value
    if isinstance(default, str):
        if value is not None and not isinstance(value, str):
            raise ValidationError(f"{key} must be text, or null")
        return value
    if isinstance(value, list):
        return tuple(value)
    if value is None or isinstance(value, (int, float, str)) and not isinstance(value, bool):
        return value
    raise ValidationError(f"{key} must be a list, a number, text or null")


def _accept_set_writer_parameters(core, args):
    only(args, ("writer", "parameters"))
    name = text(args, "writer")
    offered = _writer_parameters(core, name)
    if not offered:
        raise ValidationError(f"{name} offers no parameters to set")
    parameters = args.get("parameters")
    if not isinstance(parameters, dict) or not parameters:
        raise ValidationError("parameters must name at least one of the writer's settings")
    unknown = sorted(set(parameters) - set(offered))
    if unknown:
        raise ValidationError(f"{name} has no setting {', '.join(unknown)}; it has {', '.join(offered)}")
    return {"writer": name, "parameters": {key: _writer_value(key, offered[key]["default"], value)
                                           for key, value in parameters.items()}}


def _run_set_writer_parameters(core, args):
    """As the wizard's page applies them: into the config attribute the writer reads at the start of a
    run, for this session only; the config file is not touched."""
    name = args["writer"]
    merged = dict(getattr(core.cfg, name, {}) or {})
    merged.update(args["parameters"])
    setattr(core.cfg, name, merged)
    logger.info(f"Remote Control: {name} parameters set: {args['parameters']}")
    return {"writer": name, "parameters": {k: v["value"] for k, v in _writer_parameters(core, name).items()}}


def _processor_chain(core):
    chain = getattr(getattr(core, "camera_worker", None), "processor_chain", None)
    if chain is None:
        raise ValidationError("this mesoSPIM has no processor chain")
    return chain


def _parameters_of(processor_class):
    """A processor's parameters as the chain window reads them: none when it describes none
    (IdentityProcessor has no parameter_descriptions)."""
    describe = getattr(processor_class, "parameter_descriptions", None)
    return (describe() or {}) if describe is not None else {}


def _processor_value(name, key, description, value):
    """One processor parameter against its own description (type, min, max, choices), as the chain
    window's editor holds it."""
    kind = description.get("type")
    if kind == "float":
        value = _finite(value, f"{name}.{key}")
    elif kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{name}.{key} must be a whole number")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise ValidationError(f"{name}.{key} must be true or false")
    elif kind == "str":
        if not isinstance(value, str):
            raise ValidationError(f"{name}.{key} must be text")
    if "choices" in description and value not in description["choices"]:
        raise ValidationError(f"{name}.{key}={value!r} is not one of {description['choices']}")
    if kind in ("float", "int") and not description.get("min", value) <= value <= description.get("max", value):
        raise ValidationError(f"{name}.{key}={value} is outside [{description.get('min')}, {description.get('max')}]")
    return value


def _run_get_processor_chain(core, args):
    chain = _processor_chain(core)
    available = [{"name": p["name"], "description": p["description"],
                  "parameters": _parameters_of(p["processor_class"])} for p in chain.available_processors]
    return {"available": available, "chain": chain.get_config()["processors"], "enabled": chain.is_enabled}


def _accept_set_processor_chain(core, args):
    only(args, ("processors", "save"))
    chain = _processor_chain(core)
    available = {p["name"]: _parameters_of(p["processor_class"]) for p in chain.available_processors}
    processors = args.get("processors")
    if not isinstance(processors, list):
        raise ValidationError("processors must be the chain, first to last: [{name, enabled?, config?}] ([] empties it)")
    clean = []
    for i, entry in enumerate(processors):
        if not isinstance(entry, dict):
            raise ValidationError(f"processors[{i}] must be {{name, enabled?, config?}}")
        only(entry, ("name", "enabled", "config"))
        name = text(entry, "name")
        if name not in available:
            raise ValidationError(f"processors[{i}]: no processor {name!r}; there are {', '.join(available)}")
        config_ = entry.get("config", {})
        if not isinstance(config_, dict):
            raise ValidationError(f"processors[{i}].config must be an object")
        unknown = sorted(set(config_) - set(available[name]))
        if unknown:
            raise ValidationError(f"{name} has no parameter {', '.join(unknown)}; it has {', '.join(available[name])}")
        clean.append({"name": name, "enabled": flag(entry, "enabled", True),
                      "config": {k: _processor_value(name, k, available[name][k], v) for k, v in config_.items()}})
    return {"processors": clean, "save": flag(args, "save")}


def _run_set_processor_chain(core, args):
    """The chain as the window's Apply sets it (and its Save writes it): the chain takes its own lock, so
    the camera thread processes the next frame with the new chain. An open chain window shows it."""
    chain = _processor_chain(core)
    chain.set_config({"processors": args["processors"]})
    result = {"chain": chain.get_config()["processors"], "enabled": chain.is_enabled}
    if args["save"]:
        path = getattr(getattr(core, "parent", None), "processor_chain_config_path", None)
        if not path or not chain.save_to_file(path):
            raise ValidationError(f"could not save the processor chain to {path!r}")
        result["saved_to"] = path
    handles = getattr(core, "_remote_control_gui_handles", None)
    if handles is not None:
        handles.request("refresh_processor_chain", {})
    return result


def _accept_set_alignment_toggles(core, args):
    only(args, ALIGNMENT_TOGGLES)
    gui_handles(core)
    toggles = {key: flag(args, key) for key in ALIGNMENT_TOGGLES if key in args}
    if not toggles:
        raise ValidationError(f"name one or more of {', '.join(ALIGNMENT_TOGGLES)}")
    return toggles


def _accept_optimize(core, args):
    only(args, ("mode", "range", "points", "roi"))
    gui_handles(core)
    mode = text(args, "mode")
    if mode not in OPTIMIZER_MODES:
        raise ValidationError(f"mode is one of {list(OPTIMIZER_MODES)}")
    out = {"mode": mode, "range": number(args, "range", OPTIMIZER_RANGE),
           "points": integer(args, "points", *OPTIMIZER_POINTS, required=False, default=7)}
    if out["points"] % 2 == 0:
        raise ValidationError("points must be odd, as the optimizer asks (the current value sits in the middle)")
    if mode != "focus" and state(core, "shutterconfig") not in ("Left", "Right"):
        raise ValidationError(f"{mode} needs one light sheet (shutterconfig Left or Right), as the optimizer asks")
    if "roi" in args:
        out["roi"] = _region(args["roi"], "roi", ("x", "y", "width", "height"), frame_size(core, core.cfg))
    return out


def _accept_finish_optimization(core, args):
    only(args, ("accept",))
    gui_handles(core)
    if "accept" not in args:
        raise ValidationError("'accept' is required: true applies the optimum, false keeps the old value")
    return {"accept": flag(args, "accept")}


def _on_the_gui_thread_as_operation(name):
    """A window's instrument feature: the operation stays processing (it holds the busy gate) until the
    GUI thread has carried it out and finished it with its result."""
    def execute(core, args):
        gui_handles(core).operation(core, operation_snapshot(core)["id"], name, args)
        return {"scheduled": True}
    return execute


def _accept_save_parameters_to_config(core, args):
    only(args, ("path", "overwrite"))
    config_file = getattr(core.cfg, "__file__", None)
    if config_file is None:
        raise ValidationError("the config file's path is not known (the config has no __file__)")
    path = text(args, "path", required=False, default=config_file)
    if not path.endswith(".py"):
        raise ValidationError("the config is a Python file: path must end in .py")
    if not os.path.isdir(os.path.dirname(os.path.abspath(path))):
        raise ValidationError(f"the folder of {path!r} does not exist")
    if os.path.exists(path) and not flag(args, "overwrite"):
        raise ValidationError(f"{path} exists; overwrite=true replaces it, as the window's question does")
    return {"config_file": config_file, "path": path}


def _run_save_parameters_to_config(core, args):
    from .gui_handles import CONFIG_PARAMETERS, parameters_to_config

    appended = parameters_to_config(args["config_file"], core.state, args["path"])
    return {"path": args["path"], "saved": list(CONFIG_PARAMETERS), "appended_as_startup_update": appended}


def _accept_auto_illumination(core, args):
    from .gui_handles import illumination_by_x

    only(args, ())
    rows = _installed(core)
    if not rows:
        raise ValidationError("the installed acquisition list is empty")
    options = getattr(core.cfg, "ui_options", {}) or {}
    sides = illumination_by_x([row["x_pos"] for row in rows], bool(options.get("flip_auto_LR_illumination")))
    for row, side in zip(rows, sides):
        row["shutterconfig"] = side
    return _as_list(core, rows)


command(
    "get_writer_parameters",
    READ,
    _run_get_writer_parameters,
    accept=_accept_get_writer_parameters,
    schema=_schema({"writer": _STRING}, required=("writer",)),
    hint="in: {writer}. out: the writer's own settings as the filename wizard's Writer parameters page shows them, "
         "each {value, default, help}",
)

command(
    "set_writer_parameters",
    ACTION,
    _run_set_writer_parameters,
    accept=_accept_set_writer_parameters,
    schema=_schema({"writer": _STRING, "parameters": {"type": "object", "additionalProperties": True,
                                                      "description": "settings named as get_writer_parameters lists them"}},
                   required=("writer", "parameters")),
    hint="in: {writer, parameters}: a writer's settings (OME-Zarr chunks, compression, shards, ...) for this session, "
         "as the filename wizard's Writer parameters page sets them. out: {writer, parameters}",
)

command(
    "get_processor_chain",
    READ,
    _run_get_processor_chain,
    accept=no_args,
    hint="in: none. out: the processors there are, with their parameters, and the chain applied to the live view "
         "and the saved images, first to last",
)

command(
    "set_processor_chain",
    ACTION,
    _run_set_processor_chain,
    accept=_accept_set_processor_chain,
    schema=_schema({"processors": {"type": "array", "items": _schema(
        {"name": _STRING, "enabled": _BOOLEAN, "config": {"type": "object", "additionalProperties": True}}, required=("name",))},
        "save": {**_BOOLEAN, "description": "also save it, as the window's Save does"}}, required=("processors",)),
    hint="in: {processors: [{name, enabled?, config?}], save?}: the whole chain, first to last, as the Processor "
         "Chain window's Apply sets it. out: {chain, enabled}",
)

command(
    "set_alignment_toggles",
    WAIT,
    _on_the_gui_thread_as_operation("set_alignment_toggles"),
    accept=_accept_set_alignment_toggles,
    schema=_schema({key: _BOOLEAN for key in ALIGNMENT_TOGGLES}),
    hint="in: {zero_left_etl?, zero_right_etl?, freeze_galvo?}: the ETL tab's AmpL=0, AmpR=0 and Freeze galvos, "
         "which set the amplitude to 0 and back. out: the three toggles",
)

command(
    "optimize",
    WAIT,
    _on_the_gui_thread_as_operation("optimize"),
    accept=_accept_optimize,
    schema=_schema({"mode": {"type": "string", "enum": list(OPTIMIZER_MODES)},
                    "range": {**_NUMBER, "minimum": OPTIMIZER_RANGE[0], "maximum": OPTIMIZER_RANGE[1],
                              "description": "+- around the current value: um for focus, V for the ETL"},
                    "points": {"type": "integer", "minimum": OPTIMIZER_POINTS[0], "maximum": OPTIMIZER_POINTS[1],
                               "description": "odd; 7 when omitted"},
                    "roi": _BOX}, required=("mode", "range")),
    hint="in: {mode: focus|etl_offset|etl_amp, range, points?, roi?}: the optimizer (AUTO Focus, Launch Optimizer): "
         "snaps across the range, scores each frame's sharpness within roi (the camera window's box) and fits the "
         "best. out: {old, new, points, sharpness}; nothing changes until finish_optimization",
)

command(
    "finish_optimization",
    WAIT,
    _on_the_gui_thread_as_operation("finish_optimization"),
    accept=_accept_finish_optimization,
    schema=_schema({"accept": _BOOLEAN}, required=("accept",)),
    hint="in: {accept}: the optimizer's result window: true applies the new value (Accept), false keeps the old "
         "(Discard). out: {accepted, value}",
)

command(
    "save_parameters_to_config",
    ACTION,
    _run_save_parameters_to_config,
    accept=_accept_save_parameters_to_config,
    schema=_schema({"path": {**_STRING, "description": "the config file when omitted"}, "overwrite": _BOOLEAN}),
    hint="in: {path?, overwrite?}: the Parameters tab's Save config file: sweep, camera, laser, galvo and ETL timing "
         "and binning written into the config file. out: {path, saved}",
)

command(
    "auto_illumination",
    ACTION,
    _run_set_acquisition_list,
    accept=_accept_auto_illumination,
    hint="in: none. out: {count}: the acquisition manager's Auto L/R illumination: rows left of the median X lit "
         "from the right, the others from the left",
)


# --- The Utils menu's analyses of image files (gui_handles) --------------------------------------
# mesoSPIM runs these tools as programs of their own: they read files and never touch the
# instrument, so the calls are never gated. They run in a thread of their own; get_display {request}
# carries the result, as for the display calls.

def _tif(path, label):
    if os.path.splitext(path)[1].lower() not in (".tif", ".tiff"):
        raise ValidationError(f"{label} must be a TIFF z-stack (.tif or .tiff)")
    if not os.path.isfile(path):
        raise ValidationError(f"{label} {path!r} is not an existing file")
    return path


def _optics(args, z_step_default):
    """The tools' System Parameters, with their windows' defaults."""
    return {"magnification": number(args, "magnification", (0.01, 1000), required=False, default=5.0),
            "pixel_pitch_um": number(args, "pixel_pitch_um", (0.01, 1000), required=False, default=4.25),
            "z_step_um": number(args, "z_step_um", (0.001, 10000), required=False, default=z_step_default)}


def _accept_analyse_psf(core, args):
    only(args, ("path", "magnification", "pixel_pitch_um", "z_step_um", "min_intensity", "min_bead_distance_um",
                "z_fit_window_um", "z_min", "z_max"))
    gui_handles(core)
    out = {"path": _tif(text(args, "path"), "path"), **_optics(args, 1.0),
           "min_intensity": number(args, "min_intensity", (0, 1e9), required=False, default=700.0),
           "min_bead_distance_um": number(args, "min_bead_distance_um", (0.01, 10000), required=False, default=15.0),
           "z_fit_window_um": number(args, "z_fit_window_um", (0.01, 10000), required=False, default=30.0)}
    for key in ("z_min", "z_max"):
        if key in args:
            out[key] = integer(args, key, minimum=0)
    return out


def _accept_analyse_field_curvature(core, args):
    only(args, ("channels", "magnification", "pixel_pitch_um", "z_step_um", "n_rois_x", "n_rois_y", "tilt_reference"))
    gui_handles(core)
    channels = args.get("channels")
    if not isinstance(channels, list) or not channels:
        raise ValidationError("channels must be one or more {path, label?, wavelength_nm?}, one TIFF z-stack each")
    clean = []
    for i, channel in enumerate(channels):
        if not isinstance(channel, dict):
            raise ValidationError(f"channels[{i}] must be {{path, label?, wavelength_nm?}}")
        only(channel, ("path", "label", "wavelength_nm"))
        entry = {"path": _tif(text(channel, "path"), f"channels[{i}].path"),
                 "label": text(channel, "label", required=False, default=os.path.basename(channel["path"]))}
        if "wavelength_nm" in channel:
            entry["wavelength_nm"] = number(channel, "wavelength_nm", (200, 2000))
        clean.append(entry)
    out = {"channels": clean, **_optics(args, 10.0),
           "n_rois_x": integer(args, "n_rois_x", 2, 64, required=False, default=16),
           "n_rois_y": integer(args, "n_rois_y", 2, 64, required=False, default=16)}
    if "tilt_reference" in args:
        reference = text(args, "tilt_reference")
        if reference not in [c["path"] for c in clean]:
            raise ValidationError("tilt_reference must be the path of one of the channels")
        out["tilt_reference"] = reference
    return out


command(
    "analyse_psf",
    DISPLAY,
    _on_the_gui_thread("analyse_psf"),
    accept=_accept_analyse_psf,
    schema=_schema({"path": _STRING, "magnification": _NUMBER, "pixel_pitch_um": _NUMBER,
                    "z_step_um": {**_NUMBER, "description": "the axial pixel; 1.0 when omitted"},
                    "min_intensity": _NUMBER, "min_bead_distance_um": _NUMBER, "z_fit_window_um": _NUMBER,
                    "z_min": {"type": "integer", "minimum": 0}, "z_max": {"type": "integer", "minimum": 0}},
                   required=("path",)),
    hint="in: {path, magnification?, pixel_pitch_um?, z_step_um?, min_intensity?, min_bead_distance_um?, "
         "z_fit_window_um?, z_min?, z_max?}: Utils > PSF (beads) analysis of a TIFF z-stack: each bead's lateral and "
         "axial FWHM and their median and spread. out: {request}; the result in get_display {request}",
)

command(
    "analyse_field_curvature",
    DISPLAY,
    _on_the_gui_thread("analyse_field_curvature"),
    accept=_accept_analyse_field_curvature,
    schema=_schema({"channels": {"type": "array", "minItems": 1, "items": _schema(
        {"path": _STRING, "label": _STRING, "wavelength_nm": _NUMBER}, required=("path",))},
        "magnification": _NUMBER, "pixel_pitch_um": _NUMBER,
        "z_step_um": {**_NUMBER, "description": "10.0 when omitted"},
        "n_rois_x": {"type": "integer", "minimum": 2, "maximum": 64}, "n_rois_y": {"type": "integer", "minimum": 2, "maximum": 64},
        "tilt_reference": {**_STRING, "description": "a channel's path: its tilt is subtracted from the sections"}},
        required=("channels",)),
    hint="in: {channels: [{path, label?, wavelength_nm?}], magnification?, pixel_pitch_um?, z_step_um?, n_rois_x?, "
         "n_rois_y?, tilt_reference?}: Utils > Field curvature / chromatic shift of TIFF z-stacks: per channel the depth "
         "of field, sag, best plane and best-focus map. out: {request}; the result in get_display {request}",
)


def _enter_and_start(core, run_state, row):
    """Run upstream's synchronous acquisition entry point with a truthful state transition.

    Successful acquisitions leave the run state before emitting ``sig_finished``. Upstream's
    preflight-refusal branches emit that signal but leave the run state unchanged; the completion
    guard correctly ignores that early signal. Reconcile the refusal after ``start`` returns so the
    operation cannot wedge. Exceptions also restore idle before ``defer_wait`` records the failure.
    """
    core.state["state"] = run_state
    try:
        core.start(row=row)
    except Exception:
        core.state["state"] = "idle"
        raise
    if state(core, "state") == run_state:
        core.state["state"] = "idle"
        if operation_snapshot(core).get("stop_requested"):
            complete(core, config.MILESTONE_FINISHED)
        else:
            # Core states the reason through sig_warning (a GUI dialog); the Acceptor records it
            # on this operation so the client learns why instead of a bare "rejected".
            warning = operation_snapshot(core).get("warning")
            reason = f": {warning}" if warning else ""
            fail(
                core,
                config.MILESTONE_FINISHED,
                RuntimeError(f"Core rejected the acquisition during preflight{reason}"),
            )


def _accept_run_acquisition_list(core, args):
    only(args, ())
    if _acq_count(core) == 0:
        raise ValidationError("the installed acquisition list is empty")
    # The installed list must still be within the current limits when execution begins.
    revalidate_installed_limits(core)
    revalidate_installed_writers(core)
    return {}


def _run_run_acquisition_list(core, args):
    defer_wait(core, config.MILESTONE_FINISHED, lambda: _enter_and_start(core, "run_acquisition_list", None))
    return {"scheduled": True}


# ``running_state`` ties a shared ``sig_finished`` milestone to the operation that owns the matching
# Core state. Acquisitions clear it during their normal close path; continuous modes clear it when
# ``stop_activity`` calls Core.stop(). A signal arriving while the state still matches is stale.
command(
    "run_acquisition_list",
    WAIT,
    _run_run_acquisition_list,
    accept=_accept_run_acquisition_list,
    milestone=config.MILESTONE_FINISHED,
    running_state="run_acquisition_list",
    hint="in: none. out: {scheduled}. requires an installed acquisition list",
)


def _accept_run_selected(core, args):
    only(args, ("row",))
    if _acq_count(core) == 0:
        raise ValidationError("the installed acquisition list is empty")
    selected = row(core, args)

    # Revalidate only the row that is about to run.
    revalidate_installed_limits(core, [selected])
    revalidate_installed_writers(core, [selected])
    return {"row": selected}


def _run_run_selected_acquisition(core, args):
    core.state["selected_row"] = args["row"]
    defer_wait(
        core,
        config.MILESTONE_FINISHED,
        lambda: _enter_and_start(core, "run_selected_acquisition", args["row"]),
    )
    return {"scheduled": True, "row": args["row"]}


command(
    "run_selected_acquisition",
    WAIT,
    _run_run_selected_acquisition,
    schema=_schema({"row": _ROW}),
    accept=_accept_run_selected,
    milestone=config.MILESTONE_FINISHED,
    running_state="run_selected_acquisition",
    hint="in: {row?}. out: {scheduled, row}. requires an installed acquisition list",
)


def _accept_preview(core, args):
    only(args, ("row", "z_update"))
    if _acq_count(core) == 0:
        raise ValidationError("the installed acquisition list is empty")
    return {"row": row(core, args), "z_update": flag(args, "z_update", True)}


def _run_preview(core, args):
    core.state["selected_row"] = args["row"]
    defer_wait(
        core,
        config.MILESTONE_PREVIEW,
        lambda: core.preview_acquisition(z_update=args["z_update"]),
        verify_idle=True,
    )
    return {"scheduled": True, "row": args["row"]}


command(
    "preview_acquisition",
    WAIT,
    _run_preview,
    schema=_schema({"row": _ROW, "z_update": _BOOLEAN}),
    accept=_accept_preview,
    milestone=config.MILESTONE_PREVIEW,
    hint="in: {row?, z_update?}. out: {scheduled, row}. requires an installed acquisition list",
)


def _accept_acquire_start(core, args):
    only(args, ("acquisition",))
    # a second acquire_start before acquire_finish would overwrite the ONE saved list reference
    # (prev_acq_list) with the first temporary one-row list, losing the operator's original for good
    if "prev_acq_list" in _session(core):
        raise ValidationError("a previous acquire_start is unfinished; call acquire_finish first")

    acquisition = check_acquisition(core, args.get("acquisition"))
    check_writer_suffix(_make_acquisition_list([acquisition])[0], "acquisition")   # as it will run: default writer too

    # Validate sensor dimensions before the mutation gate opens.
    _camera_pixels(core)
    return {"acquisition": acquisition}


def _run_acquire_start(core, args):
    acquisition = args["acquisition"]
    pixels = list(_camera_pixels(core))

    # Build every fallible value before modifying Core state.
    acq_list = _make_acquisition_list([acquisition])
    filename = acquisition.get("filename") or ""
    files = [os.path.join(acquisition.get("folder") or "", filename)] if filename else []
    response = {
        "started": True,
        "scheduled": True,
        "files": files,
        "planes": int(acq_list[0].get_image_count()),
        "pixels": pixels,
    }
    previous = core.state["acq_list"]
    _session(core)["prev_acq_list"] = previous
    core.state["acq_list"] = acq_list
    try:
        defer_wait(core, config.MILESTONE_FINISHED, lambda: _enter_and_start(core, "run_acquisition_list", 0))
    except Exception:
        # A scheduling failure must leave the operator's list untouched.
        core.state["acq_list"] = previous
        _session(core).pop("prev_acq_list", None)
        raise

    return response


command(
    "acquire_start",
    WAIT,
    _run_acquire_start,
    schema=_schema({"acquisition": _ACQUISITION}, required=("acquisition",)),
    accept=_accept_acquire_start,
    milestone=config.MILESTONE_FINISHED,
    running_state="run_acquisition_list",
    hint="in: {acquisition}. out: {started, files, planes, pixels}",
)


# Distinguish "acquire_start saved no list" from "it saved None".
_NOTHING_SAVED = object()


def _run_acquire_finish(core, args):
    previous = _session(core).pop("prev_acq_list", _NOTHING_SAVED)
    if previous is not _NOTHING_SAVED:
        core.state["acq_list"] = previous
    return {"state": state(core, "state")}


command("acquire_finish", ACTION, _run_acquire_finish, accept=no_args, hint="in: none. out: {state}")


# --- Time-lapse operations ---
def _accept_time_lapse_start(core, args):
    only(args, ("timepoints", "interval_sec"))
    if _acq_count(core) == 0:
        raise ValidationError("the installed acquisition list is empty")
    timepoints = integer(args, "timepoints", minimum=1, required=False, default=1)
    interval = integer(args, "interval_sec", minimum=0, required=False, default=0)

    # A time lapse runs the installed list, so recheck it against the current limits.
    revalidate_installed_limits(core)
    revalidate_installed_writers(core)
    return {"timepoints": timepoints, "interval_sec": interval}


def _run_time_lapse_start(core, args):
    core.run_time_lapse(tpoints=args["timepoints"], time_interval_sec=args["interval_sec"])
    return {"started": True}


command(
    "time_lapse_start",
    WAIT,
    _run_time_lapse_start,
    schema=_schema({"timepoints": {"type": "integer", "minimum": 1}, "interval_sec": {"type": "integer", "minimum": 0}}),
    accept=_accept_time_lapse_start,
    milestone=config.MILESTONE_TIMELAPSE,
    hint="in: {timepoints?, interval_sec?}. out: {started}. requires an installed acquisition list",
)


# --- Hardware-free startup simulation and self-test ---


class SimCore:
    """A stand-in Core carrying the REAL cfg but simulating hardware — a move only updates an
    in-memory position. The startup smoke-check drives this, never the instrument."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = {
            "state": "idle",
            "position": {f"{a}_pos": 0.0 for a in config.AXES},
            "position_absolute": {f"{a}_pos": 0.0 for a in config.AXES},
        }
        self._remote_session = {"operation": None, "counter": 0}
        # Startup calls self_test before returning to Qt's event loop. Simulated timer work must
        # therefore run inline; only this hardware-free Core provides the override.
        self._remote_control_single_shot = lambda _delay, callback: callback()
        self.moves = []

    def move_absolute(self, targets, wait_until_done=False, **_):
        if wait_until_done:
            raise AssertionError("SimCore stage moves must remain asynchronous")
        self.moves.append(targets)
        for key, value in targets.items():
            axis = key.replace("_abs", "")
            offset = self.state["position"][f"{axis}_pos"] - self.state["position_absolute"][f"{axis}_pos"]
            # Like the stage drivers: the user-frame target lands at physical = target - offset.
            self.state["position"][f"{axis}_pos"] = float(value)
            self.state["position_absolute"][f"{axis}_pos"] = float(value) - offset

    def set_intensity(self, value, wait_until_done=False, **_):
        if wait_until_done:
            raise AssertionError("SimCore setting checks must not block")
        self.state["intensity"] = value


def self_test(source):
    """Smoke-check that the loaded config's limits are actually enforced, over the same run() both
    transports use. Takes a core-like object (reads its cfg). Returns (ok, report_lines)."""
    from .dispatcher import run

    sim = SimCore(getattr(source, "cfg", None))
    report, ok = [], True

    def note(good, line):
        nonlocal ok
        ok = ok and good
        report.append(("PASS " if good else "FAIL ") + line)

    def accepts(name, call_args):
        try:
            run(sim, name, call_args)
            return True
        except Exception:
            return False

    note(accepts("get_limits", {}), "get_limits responds")
    try:
        limits = effective_limits(sim)
    except ValidationError as error:
        # A malformed limit override fails closed, so the server never binds.
        note(False, f"limits could not be resolved (check {config.LIMITS_ENV_VAR}): {error}")
        return ok, report

    if not limits:
        note(False, "no axis has a limit; refusing to go live")
        return ok, report
    sim.moves.clear()
    expected = 0
    for axis, (low, high) in limits.items():
        note(accepts("move_absolute", {"targets": {axis: high}}), f"in-range {axis}={high} accepted")
        expected += 1
        note(not accepts("move_absolute", {"targets": {axis: high + 1}}), f"over-max {axis} refused")
        note(not accepts("move_absolute", {"targets": {axis: low - 1}}), f"under-min {axis} refused")
    # A zeroed axis reads 0 while the stage sits at its physical maximum. A user-frame target of
    # +1 would then drive past the limit; the check must see the physical position, not the reading.
    axis, (low, high) = next(iter(limits.items()))
    sim.state["position"][f"{axis}_pos"] = 0.0
    sim.state["position_absolute"][f"{axis}_pos"] = high
    note(accepts("move_absolute", {"targets": {axis: 0}}), f"zeroed-frame {axis}=0 (stage {high}) accepted")
    expected += 1
    note(not accepts("move_absolute", {"targets": {axis: 1}}), f"zeroed-frame over-max {axis} refused")
    note(
        not accepts("move_relative", {"deltas": {axis: 1}}),
        f"zeroed-frame relative over-max {axis} refused",
    )
    sim.state["position"][f"{axis}_pos"] = 0.0
    sim.state["position_absolute"][f"{axis}_pos"] = 0.0
    note(not accepts("set_intensity", {"intensity": 250}), "over-range intensity refused")
    note(not accepts("move_absolute", {"targets": {"nope": 0}}), "unknown axis refused")
    note(not accepts("__import__", {}), "unknown command refused")
    note(len(sim.moves) == expected, f"only the {expected} in-range move(s) reached the mock stage")
    return ok, report

