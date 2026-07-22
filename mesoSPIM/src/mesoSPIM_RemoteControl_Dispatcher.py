"""Validate and dispatch Remote Control commands independently of TCP or MCP.

Both transports call :func:`run` with the same command name and arguments. This module finds the
registered command, validates its input, enforces the one-mutation-at-a-time gate, records the
operation lifecycle, and returns consistent success or error information. Accepted mutations are
scheduled on the Qt event loop so their network replies do not wait for hardware or GUI work.
Clients poll ``get_progress`` for the terminal result. This module also provides the strict JSON
parser shared by the wire protocols.

Command names, hardware calls, and microscope-specific limits belong in
``mesoSPIM_RemoteControl_Commands``. Socket handling belongs in
``mesoSPIM_RemoteControl_Servers``. Keeping those concerns out of this module makes the dispatcher
small enough to reason about and ensures TCP and MCP follow the same execution rules.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import math
import threading
from dataclasses import dataclass
from typing import Callable, Optional


# --- Public errors and command definitions ---


class ValidationError(ValueError):
    """An `accept` raises this to reject a call. It never opened the gate."""


class BusyError(RuntimeError):
    """The gate refuses a mutation because another one is already running."""


class UnknownCommand(KeyError):
    """The requested command name is not in the registry. A subclass of KeyError so an ordinary
    KeyError escaping a handler is NOT misreported as an unknown command."""


# Command kinds describe how a call interacts with the mutation gate.
READ = "read"
ACTION = "action"
WAIT = "wait"
EMERGENCY = "emergency"

# Only PROCESSING and STOPPING hold the mutation gate.
PROCESSING, STOPPING, COMPLETED, FAILED, IDLE = ("processing", "stopping", "completed", "failed", "idle")

COMMANDS = {}

# Admission must be atomic: two requests arriving together cannot both observe an empty gate and
# start. The lock is held only while operation state changes, never while a command executes.
_GATE = threading.Lock()


@dataclass(frozen=True)
class Command:
    """One allowlisted command and the functions that validate and execute it."""

    name: str
    kind: str
    execute: Callable
    hint: str = ""
    accept: Optional[Callable] = None
    milestone: Optional[str] = None

    # Core state held by this asynchronous operation while it is running.
    running_state: Optional[str] = None


def command(name, kind, execute, **rest):
    """Register one command definition when the Commands module is imported."""
    COMMANDS[name] = Command(name, kind, execute, **rest)


def jsonable(value):
    """Recursively convert Core values to data accepted by strict ``json.dumps``.

    ``json.dumps(default=str)`` cannot recurse into unknown containers or repair tuple keys, so the
    conversion is explicit. Non-finite floats become readable strings instead of invalid JSON
    tokens such as ``NaN`` or ``Infinity``.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        # a non-finite value in Core state must not become the non-standard JSON token NaN/Infinity
        # (invalid strict JSON, and it breaks a client's parse) -> emit a string instead
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "items"):
        return {str(key): jsonable(item) for key, item in value.items()}
    return str(value)


def _session(core):
    """The Core-owned session on the write path. Core, SimCore and test cores build it eagerly,
    so it exists before any mutation runs."""
    return core._remote_session


# --- Operation state and the one-mutation gate ---


def _read_session(core):
    """None-safe read of the session — safe on the camera thread and on a core still being set
    up. A read never creates the session, so both threads cannot race to build one."""
    return getattr(core, "_remote_session", None)


def _active(core):
    session = _read_session(core)
    operation = session["operation"] if session else None
    if operation is not None and operation["status"] in (PROCESSING, STOPPING):
        return operation
    return None


def operation_snapshot(core):
    """The public view of the LATEST operation, any status — for polling reads. `_active` would
    report idle once terminal, hiding the result the poller waits for."""
    session = _read_session(core)
    return _public(session["operation"] if session else None)


def _core_state(core):
    """None-safe read of the core's own state-machine state (production StateSingleton raises on a
    miss). Used to tell a WAIT op's real completion from a stray same-milestone signal."""
    try:
        return core.state["state"]
    except (KeyError, TypeError, AttributeError):
        return None


def _begin(core, name, milestone, running_state=None):
    session = _session(core)
    session["counter"] += 1
    operation = {
        "id": f"op-{session['counter']:06d}",
        "command": name,
        "status": PROCESSING,
        "milestone": milestone,
        # Admission and the queued phase are one atomic state change. An emergency request that
        # arrives immediately afterward can cancel this operation before any command body runs.
        "phase": "scheduled",
    }
    if running_state is not None:
        operation["running_state"] = running_state
    session["operation"] = operation
    return operation


def schedule_current(core):
    """Mark the current WAIT as deferred and return its id for the timer callback."""
    with _GATE:
        operation = _active(core)
        if operation is None:
            raise RuntimeError("cannot defer without an active operation")
        operation["phase"] = "scheduled"
        return operation["id"]


def claim_scheduled(core, operation_id):
    """Claim one deferred callback. A cancelled/replaced operation must never actuate later."""
    with _GATE:
        operation = _active(core)
        if (
            operation is None
            or operation["id"] != operation_id
            or operation["status"] != PROCESSING
            or operation.get("phase") != "scheduled"
        ):
            return False
        operation["phase"] = "running"
        return True


def request_stop(core):
    """The stop commands call this; close_shutters does not. `stop_requested` survives past
    terminal so a reader can tell a completed op was stopped, not finished."""
    # Serialize this operation-state transition with dispatch.
    with _GATE:
        operation = _active(core)
        if operation is not None:
            operation["stop_requested"] = True
            if operation.get("phase") == "scheduled":
                # Nothing has touched hardware yet. Make the queued callback fail its id/phase claim
                # and release the gate immediately instead of creating a permanent STOPPING op.
                operation["status"] = COMPLETED
            else:
                operation["status"] = STOPPING


def complete(core, milestone):
    # Serialize this operation-state transition with dispatch.
    with _GATE:
        operation = _active(core)
        if operation is None or operation["milestone"] != milestone:
            return
        if operation.get("phase") == "scheduled":
            # A signal left over from a prior operation must not complete (and thereby cancel) a
            # new command whose guarded Qt callback has not even started.
            return
        running = operation.get("running_state")
        if running is not None and _core_state(core) == running:
            # The op's own activity is still running (the core is still in its running state), so this
            # milestone signal cannot be THIS op's completion — it is a stray (a duplicate, or a
            # signal for a prior same-milestone op). Ignore it: the op stays processing until the
            # core actually leaves its running state. This is the operation/state association that
            # keeps a late signal from completing a newer operation early.
            return
        operation["status"] = COMPLETED


def fail(core, milestone, error):
    # Serialize this operation-state transition with dispatch.
    with _GATE:
        operation = _active(core)
        if operation is not None and operation["milestone"] == milestone:
            operation["status"] = FAILED
            operation["error"] = str(error)


def clear_if_core_idle(core):
    """Recover a WAIT only when independent Core state proves it is no longer active."""
    with _GATE:
        operation = _active(core)
        if operation is None:
            return {"cleared": False, "reason": "no operation is holding the gate"}
        if operation["milestone"] is None:
            return {
                "cleared": False,
                "operation_id": operation["id"],
                "reason": "the active operation is synchronous and cannot be recovered",
            }
        if operation.get("phase") == "scheduled":
            return {
                "cleared": False,
                "operation_id": operation["id"],
                "reason": "the deferred hardware action has not started",
            }
        if operation.get("target") and not operation.get("stop_requested"):
            return {
                "cleared": False,
                "operation_id": operation["id"],
                "reason": "the stage target has not been confirmed; call stop before recovery",
            }
        if operation["command"] == "time_lapse_start":
            active = getattr(core, "timelapse_active", None)
            if active is not False:
                return {
                    "cleared": False,
                    "operation_id": operation["id"],
                    "reason": "the time lapse is still active or its state is unavailable",
                }
        core_state = _core_state(core)
        if core_state != IDLE:
            return {
                "cleared": False,
                "operation_id": operation["id"],
                "reason": f"core is not idle (state={core_state!r}); the operation is still running",
            }
        operation["status"] = FAILED
        operation["error"] = "recovered: core returned to idle but no completion signal arrived"
        return {"cleared": True, "operation_id": operation["id"]}


_PUBLIC_OP_KEYS = (
    "id",
    "command",
    "status",
    "target",
    "observed",
    "stop_requested",
    "result",
    "error",
)


def _public(operation):
    if operation is None:
        return {"status": IDLE}
    return {key: operation[key] for key in _PUBLIC_OP_KEYS if key in operation}


def _reply(name, result, operation):
    reply = jsonable(result)
    if not isinstance(reply, dict):
        reply = {"result": reply}
    reply["accepted"] = True
    reply["accepted_command"] = name
    reply["operation"] = _public(operation)
    return reply


def _accepted_reply(name, operation):
    """Return the transport acknowledgement for an admitted mutation.

    Command-specific output deliberately does not appear here. The scheduled command stores that
    output in the operation record, where ``get_progress`` exposes it after execution. Keeping the
    acknowledgement independent of command duration prevents a completed Core or GUI mutation
    from being mistaken for a failed call merely because its network response arrived too late.
    """
    return {
        "accepted": True,
        "accepted_command": name,
        "operation": _public(operation),
    }


def _single_shot(core, delay_ms, callback):
    """Schedule work on Core's Qt event loop, with an injectable hook for deterministic tests."""
    from PyQt5 import QtCore

    schedule = getattr(core, "_remote_control_single_shot", QtCore.QTimer.singleShot)
    schedule(delay_ms, callback)


def _record_mutation_result(core, operation_id, kind, result):
    """Store one scheduled command result and finish a short action atomically."""
    with _GATE:
        session = _read_session(core)
        operation = session["operation"] if session else None
        if operation is None or operation["id"] != operation_id:
            return

        operation["result"] = jsonable(result)
        if kind == ACTION and operation["status"] == PROCESSING:
            operation["status"] = COMPLETED


def _record_mutation_failure(core, operation_id, error):
    """Make an execution failure visible to pollers without losing the accepted reply."""
    with _GATE:
        session = _read_session(core)
        operation = session["operation"] if session else None
        if operation is None or operation["id"] != operation_id:
            return

        operation["status"] = FAILED
        operation["error"] = str(error)


def _schedule_mutation(core, cmd, args, operation):
    """Queue an admitted ACTION or WAIT and return before its execution begins."""
    operation_id = operation["id"]

    def body():
        if not claim_scheduled(core, operation_id):
            return

        try:
            result = cmd.execute(core, args)
        except Exception as error:
            _record_mutation_failure(core, operation_id, error)
            return

        _record_mutation_result(core, operation_id, cmd.kind, result)

    try:
        _single_shot(core, 0, body)
    except Exception as error:
        _record_mutation_failure(core, operation_id, error)
        raise


def precheck(name):
    """Fail-fast on the CALLING (transport) thread for the ONE rejection that can be decided without
    the Core thread and is permanent: an UNKNOWN command name (a pure allowlist lookup). Raising it
    here means an unknown name comes back immediately, without being marshalled behind a Core thread
    that may be mid-move.

    Everything else — input shape, limit range, and the busy gate — is decided later in
    run()/dispatch() on the Core thread, in that order, with **busy checked LAST**. So a call that is
    wrong in a fixable way (bad shape, out of limits) gets a precise `validation` error even while
    the instrument is busy; `busy` is returned only when the call is otherwise valid but an operation
    already holds the gate. The atomic gate in dispatch() remains the authority for busy."""
    if name not in COMMANDS:
        raise UnknownCommand(f"unknown command: {name!r}")


def dispatch(core, cmd, args):
    if cmd.kind == READ:
        return jsonable(cmd.execute(core, args))

    if cmd.kind == EMERGENCY:
        # A stop handler marks the current operation through request_stop.
        result = cmd.execute(core, args)
        return _reply(cmd.name, result, _active(core))

    # The busy check and begin are ONE atomic step: if two mutations arrive together, exactly one
    # opens an operation. All ordinary mutations are then queued for the next Qt event-loop turn.
    # The transport therefore acknowledges admission before Core, hardware, or GUI work begins.
    with _GATE:
        active = _active(core)
        if active is not None:
            raise BusyError(f"busy: {active['command']} ({active['id']}) is running")
        operation = _begin(core, cmd.name, cmd.milestone, cmd.running_state)

    _schedule_mutation(core, cmd, args, operation)
    return _accepted_reply(cmd.name, operation)


def run(core, name, args=None):
    cmd = COMMANDS.get(name)
    if cmd is None:
        raise UnknownCommand(f"unknown command: {name!r}")
    if args is None:
        args = {}
    # A false but non-object value such as [], "", 0, or false is invalid, not an empty call.
    if not isinstance(args, dict):
        raise ValidationError("command arguments must be an object")
    clean = cmd.accept(core, args) if cmd.accept else args
    return dispatch(core, cmd, clean)


# --- strict JSON and the call envelope (shared by the transports and the limits reader) ---


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON member {key!r}")
        result[key] = value
    return result


def _finite_json_number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValidationError(f"non-finite JSON number {text!r}")
    return value


def _reject_constant(name):
    raise ValidationError(f"non-finite JSON constant {name!r}")


def strict_json_loads(payload):
    """Decode strict JSON: unique object keys and finite numbers only."""
    import json

    return json.loads(
        payload,
        object_pairs_hook=_unique_object,
        parse_float=_finite_json_number,
        parse_constant=_reject_constant,
    )


def parse_call(payload):
    """The canonical wire envelope: one {name: {args}} object."""
    msg = strict_json_loads(payload)
    if not isinstance(msg, dict) or len(msg) != 1:
        raise ValidationError("expected one JSON object: {'command': {args}}")
    ((name, args),) = msg.items()
    if not isinstance(name, str):
        raise ValidationError("command name must be a string")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValidationError("command arguments must be an object")
    return name, args


def error_info(error):
    """Map an exception to a machine-readable (code, message), so a client can decide whether to
    retry (busy) or not (validation/unknown) without scraping the human text."""
    if isinstance(error, ValidationError):
        code = "validation"
    elif isinstance(error, BusyError):
        code = "busy"
    elif isinstance(error, UnknownCommand):
        code = "unknown_command"
    else:
        # A plain KeyError raised inside a handler is also an execution error.
        code = "execution"
    return code, str(error)
