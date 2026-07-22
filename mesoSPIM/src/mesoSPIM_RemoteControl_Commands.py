"""Define the complete, validated Remote Control command vocabulary.

This module contains all remotely callable commands and the rules that protect their inputs. It
resolves effective hardware limits, builds read-only status documents, validates acquisition data,
and maps accepted mutations to the existing mesoSPIM Core API. Importing the module registers all
53 commands with the transport-independent dispatcher.

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

import math
import os

from . import mesoSPIM_RemoteControl_Config as config
from .mesoSPIM_RemoteControl_Dispatcher import (
    command,
    complete,
    fail,
    request_stop,
    operation_snapshot,
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
)


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
    """
    from PyQt5 import QtCore

    operation_id = schedule_current(core)

    def body():
        if not claim_scheduled(core, operation_id):
            return
        try:
            action()
        except Exception as error:
            fail(core, milestone, error)
            return
        if verify_idle:
            here = state(core, "state")
            if here == "idle":
                complete(core, milestone)
            else:
                fail(core, milestone, RuntimeError(f"did not return to idle (state={here!r})"))

    QtCore.QTimer.singleShot(0, body)


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


def check_absolute(limits, axis, value):
    bound = limits.get(axis)
    if bound is not None and not (bound[0] <= value <= bound[1]):
        raise ValidationError(
            f"{axis}={value} is outside the allowed range [{bound[0]}, {bound[1]}] "
            f"(units: um for x/y/z/f, deg for theta; see get_limits)"
        )


def check_relative(limits, axis, current, delta):
    bound = limits.get(axis)
    if bound is None:
        return
    current = _finite(current, f"current {axis} position")
    target = current + delta
    if not (bound[0] <= target <= bound[1]):
        raise ValidationError(
            f"{axis} would reach {target}, outside the allowed range "
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
    from .utils.acquisitions import Acquisition, AcquisitionList

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
    for field, axis in config.ACQUISITION_AXIS_FIELDS.items():
        if field in acquisition:
            check_absolute(limits, axis, _finite(acquisition[field], f"{label}.{field}"))
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


def revalidate_installed_limits(core, indices=None):
    """Re-check the ALREADY-installed acquisition rows' stage fields against the effective limits,
    right before a remote command starts them. The installed list may have been set from the GUI
    (never through our accept) or may predate a tightened MESOSPIM_RS_LIMITS, so the install-time
    check is not sufficient on its own. Only the axis fields are re-checked — the safety-relevant
    part — so a GUI row carrying extra keys is not spuriously rejected. `indices` limits the check to
    specific rows (run_selected_acquisition runs only one)."""
    installed = state(core, "acq_list", []) or []
    limits = effective_limits(core)
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
            if bound is not None and not (bound[0] <= value <= bound[1]):
                raise ValidationError(
                    f"installed acquisitions[{i}].{field}={value} is outside the allowed range "
                    f"[{bound[0]}, {bound[1]}]; re-install the list within the current limits"
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
        "warnings": [],
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
            "parameters": _param_constraints(core),
        },
    }


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
    accept=_accept_get_state_all,
    hint="in: {keys?: [str]}. out: state map",
)


def _run_get_config(core, args):
    return _config_document(core)


command(
    "get_config", READ, _run_get_config, accept=no_args, hint="in: none. out: lasers/filters/zooms/camera"
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
        "modes": list(config.MODES),
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
    "status 'completed' or 'failed'. For movement, completion means "
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
        "emergency": "An immediate safety command allowed while another mutation is processing: "
        "stop, stop_activity, close_shutters, or time_lapse_stop. It does not "
        "create a new operation.",
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
            "poll get_progress for the returned operation id until status is completed or failed",
            "verify get_position reports the intended position",
        ],
    },
    {"goal": "Live mode", "steps": ["start_live {}", "... observe ...", "stop_activity {}"]},
    {
        "goal": "Run one supplied acquisition",
        "steps": [
            "acquire_start {acquisition: {...}}",
            "poll get_progress until 'completed'",
            "acquire_finish {}",
        ],
    },
    {
        "goal": "Run the installed acquisition list",
        "steps": [
            "set_acquisition_list {acquisitions: [...], selected_row: 0}",
            "poll get_progress until the list operation is completed",
            "run_acquisition_list {}",
            "poll get_progress until 'completed'",
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
    accept=_accept_acq_check,
    hint="in: {acquisitions?}. out: {free_bytes, required_bytes}",
)


def _run_check_motion_limits(core, args):
    return {"outside_limits": list(core.check_motion_limits(_acqs_to_check(core, args)))}


command(
    "check_motion_limits",
    READ,
    _run_check_motion_limits,
    accept=_accept_acq_check,
    hint="in: {acquisitions?}. out: {outside_limits}",
)


# --- Stage movement ---
def _accept_move_absolute(core, args):
    only(args, ("targets",))
    targets = axis_map(args, "targets")
    limits = effective_limits(core)
    for axis, value in targets.items():
        check_absolute(limits, axis, value)
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
    accept=_accept_move_absolute,
    milestone=config.MILESTONE_POSITION,
    hint="in: {targets:{axis: um/deg}}. out: {target}. poll get_progress",
)


def _accept_move_relative(core, args):
    only(args, ("deltas",))
    deltas = axis_map(args, "deltas")
    limits = effective_limits(core)
    here = position(core)
    targets = {}
    for axis, delta in deltas.items():
        check_relative(limits, axis, here.get(axis), delta)
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
    accept=_accept_move_relative,
    milestone=config.MILESTONE_POSITION,
    hint="in: {deltas:{axis: um/deg}}. out: {target}. poll get_progress",
)


def _accept_axes(core, args):
    only(args, ("axes",))
    return {"axes": axes_list(args, "axes")}


def _run_zero(core, args):
    core.zero_axes(args["axes"])
    return {}


command("zero", ACTION, _run_zero, accept=_accept_axes, hint="in: {axes?}. out: {}")


def _run_unzero(core, args):
    core.unzero_axes(args["axes"])
    return {}


command("unzero", ACTION, _run_unzero, accept=_accept_axes, hint="in: {axes?}. out: {}")


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
    core.state_request_handler(args["settings"])
    return {}


command(
    "set_state",
    ACTION,
    _run_state_settings,
    accept=_accept_set_state,
    hint="in: {settings:{settable keys, see get_capabilities}}. out: {}",
)


def _accept_set_filter(core, args):
    only(args, ("filter", "wait"))
    return {"filter": option(core, args, "filter"), "wait": flag(args, "wait", False)}


def _run_set_filter(core, args):
    core.set_filter(args["filter"], wait_until_done=args["wait"])
    return {}


command("set_filter", ACTION, _run_set_filter, accept=_accept_set_filter, hint="in: {filter, wait?}. out: {}")


def _accept_set_zoom(core, args):
    only(args, ("zoom", "wait", "update_etl"))
    return {
        "zoom": option(core, args, "zoom"),
        "wait": flag(args, "wait", True),
        "update_etl": flag(args, "update_etl", True),
    }


def _run_set_zoom(core, args):
    core.set_zoom(args["zoom"], wait_until_done=args["wait"], update_etl=args["update_etl"])
    return {}


command(
    "set_zoom", ACTION, _run_set_zoom, accept=_accept_set_zoom, hint="in: {zoom, wait?, update_etl?}. out: {}"
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
    return {}


command(
    "set_laser",
    ACTION,
    _run_set_laser,
    accept=_accept_set_laser,
    hint="in: {laser, wait?, update_etl?}. out: {}",
)


def _accept_set_shutterconfig(core, args):
    only(args, ("shutterconfig",))
    return {"shutterconfig": option(core, args, "shutterconfig")}


def _run_set_shutterconfig(core, args):
    core.set_shutterconfig(args["shutterconfig"])
    return {}


command(
    "set_shutterconfig",
    ACTION,
    _run_set_shutterconfig,
    accept=_accept_set_shutterconfig,
    hint="in: {shutterconfig}. out: {}",
)


def _accept_set_intensity(core, args):
    only(args, ("intensity", "wait"))
    return {"intensity": number(args, "intensity", config.PERCENT_RANGE), "wait": flag(args, "wait", False)}


def _run_set_intensity(core, args):
    core.set_intensity(args["intensity"], wait_until_done=args["wait"])
    return {}


command(
    "set_intensity",
    ACTION,
    _run_set_intensity,
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
    accept=_accept_set_camera,
    hint="in: one or more set_camera keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_etl(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_etl"])}


command(
    "set_etl",
    ACTION,
    _run_state_settings,
    accept=_accept_set_etl,
    hint="in: one or more set_etl keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_galvo(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_galvo"])}


command(
    "set_galvo",
    ACTION,
    _run_state_settings,
    accept=_accept_set_galvo,
    hint="in: one or more set_galvo keys (see get_capabilities.setting_groups). out: {}",
)


def _accept_set_laser_timing(core, args):
    return {"settings": settings(core, args, config.SETTING_GROUPS["set_laser_timing"])}


command(
    "set_laser_timing",
    ACTION,
    _run_state_settings,
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
    accept=_accept_reload_etl_config,
    hint="in: {path?, wait?}. out: ETL readback",
)
command(
    "update_etl_from_laser",
    ACTION,
    _run_etl,
    accept=_accept_update_etl_from_laser,
    hint="in: {laser?, wait?}. out: ETL readback",
)
command(
    "update_etl_from_zoom",
    ACTION,
    _run_etl,
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
    hint="in: none. out: {target}. poll get_progress",
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
    hint="in: none. out: {target}. poll get_progress",
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
    hint="in: none. out: {target}. poll get_progress",
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
    # RemoteControlGUI supplies a blocking Core->GUI bridge; headless/unit cores intentionally do not.
    bridge = getattr(core, "_remote_control_acquisition_list_signal", None)
    if bridge is not None:
        bridge.emit(acquisitions, args.get("selected_row"))
    return {"count": len(acquisitions)}


command(
    "set_acquisition_list",
    ACTION,
    _run_set_acquisition_list,
    accept=_accept_set_acquisition_list,
    hint="in: {acquisitions:[...], selected_row?}. out: {count}",
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
            fail(
                core,
                config.MILESTONE_FINISHED,
                RuntimeError("Core rejected the acquisition during preflight"),
            )


def _accept_run_acquisition_list(core, args):
    only(args, ())
    if _acq_count(core) == 0:
        raise ValidationError("the installed acquisition list is empty")
    # The installed list must still be within the current limits when execution begins.
    revalidate_installed_limits(core)
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
    return {"timepoints": timepoints, "interval_sec": interval}


def _run_time_lapse_start(core, args):
    core.run_time_lapse(tpoints=args["timepoints"], time_interval_sec=args["interval_sec"])
    return {"started": True}


command(
    "time_lapse_start",
    WAIT,
    _run_time_lapse_start,
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
        self.state = {"state": "idle", "position": {f"{a}_pos": 0.0 for a in config.AXES}}
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
            self.state["position"][key.replace("_abs", "_pos")] = float(value)

    def set_intensity(self, value, wait_until_done=False, **_):
        if wait_until_done:
            raise AssertionError("SimCore setting checks must not block")
        self.state["intensity"] = value


def self_test(source):
    """Smoke-check that the loaded config's limits are actually enforced, over the same run() both
    transports use. Takes a core-like object (reads its cfg). Returns (ok, report_lines)."""
    from .mesoSPIM_RemoteControl_Dispatcher import run

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
    note(not accepts("set_intensity", {"intensity": 250}), "over-range intensity refused")
    note(not accepts("move_absolute", {"targets": {"nope": 0}}), "unknown axis refused")
    note(not accepts("__import__", {}), "unknown command refused")
    note(len(sim.moves) == expected, f"only the {expected} in-range move(s) reached the mock stage")
    return ok, report
