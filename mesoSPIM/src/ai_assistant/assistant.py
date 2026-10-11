"""AI Assistant connector: turns the Remote Control commands into agent tools, runs a
Pydantic AI agent in a worker thread, and blocks each mutating tool until the microscope
actually finishes — so the agent sees completed actions, not 'processing'.

Reuses the shared dispatcher unchanged: every actuation goes through Acceptor.dispatch()
→ validation, movement limits, _GATE.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import asyncio
import json
import math
import re
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from PyQt5 import QtCore

from ..remote_control.dispatcher import COMMANDS, DISPLAY, WAIT, COMPLETED, FAILED, STOPPED, error_info
from ..remote_control.servers import Acceptor
from ..remote_control.commands import self_test
from ..remote_control.frame import array_of, to_png
from . import config
from .frames import Calibration, FrameHistory, field_um, flag, nominal_scale, place_and_settings, sample_map, shift
from ..remote_control import config as rc_config

logger = logging.getLogger(__name__)

_TERMINAL = {COMPLETED, FAILED, STOPPED}

# Commands embedded in the system prompt, so not worth exposing as tools (a call only re-fetches
# what the model already has). get_manual is the whole command reference — large and static.
_PROMPT_ONLY = {"get_manual"}


def hms(seconds):
    """A time on the assistant's clock (epoch seconds) as the operator reads it, HH:MM:SS."""
    return time.strftime("%H:%M:%S", time.localtime(seconds))


def dispatch_and_wait(acceptor, name, args, kind, cancel, cfg=config, clock=time.time):
    """Run one command and return a finished result. For WAIT commands the return always
    carries a consistent top-level `status` ('completed' / 'failed' / 'stopped' / 'still_running' /
    'cancelled'); READ/ACTION commands pass their own result through unchanged.

    A WAIT command returns 'processing' immediately and completes later on a milestone; we
    poll get_progress here so one tool call == one completed action (no polling rule in the
    prompt). Past WAIT_CAP_S it returns 'still_running' so the worker frees up (an unbounded
    wait would hang on a never-signalled op — see clear_stuck_operation). Status/id live under
    the "operation" key of both the accept-reply and get_progress.
    """
    if cancel.is_set():
        return {"status": "cancelled"}                              # gate every call after Cancel
    result = acceptor.dispatch(name, args or {})
    if kind == DISPLAY:
        return _displayed(acceptor, result, cancel, cfg, clock)
    if kind != WAIT:
        return result
    op = (result or {}).get("operation") or {}
    op_id = op.get("id")
    if op.get("status") in _TERMINAL:
        return {"status": op["status"], "operation": op_id, "result": result}

    deadline = clock() + cfg.WAIT_CAP_S
    until_stopped = name in getattr(cfg, "RUNS_UNTIL_STOPPED", ())
    on_its_own = name in getattr(cfg, "RUNS_ON_ITS_OWN", ())
    runs = COMMANDS[name].running_state if until_stopped or on_its_own else None
    while clock() < deadline:
        if cancel.is_set():
            return {"status": "cancelled", "operation": op_id}      # interrupt() halts the hardware
        time.sleep(cfg.POLL_INTERVAL_S)
        snap = acceptor.dispatch("get_progress", {}) or {}          # READ: cheap, holds no gate
        status = (snap.get("operation") or {}).get("status")
        if status in _TERMINAL:
            return {"status": status, "operation": op_id, "result": snap}
        if until_stopped and snap.get("state") == runs:
            return {"status": "running", "operation": op_id,
                    "note": f"{runs} runs until stopped; stop_activity ends it, and settings and moves pass meanwhile."}
        if on_its_own and (runs is None or snap.get("state") == runs):
            return {"status": "running", "operation": op_id,
                    "note": cfg.RUNS_ON_ITS_OWN_NOTE.format(what=runs or name)}
    return {"status": "still_running", "operation": op_id,
            "note": "operation exceeds the wait cap; call get_progress to check on it."}


def _displayed(acceptor, result, cancel, cfg, clock):
    """A display change is applied on the GUI thread a moment later: wait until get_display reports
    the request's outcome, and return what the windows then show, so the model sees what it did."""
    number = (result or {}).get("request")
    if number is None:
        return result
    deadline = clock() + cfg.WAIT_CAP_S
    shown = {}
    while clock() < deadline and not cancel.is_set():
        shown = acceptor.dispatch("get_display", {"request": number}) or {}
        if (shown.get("request") or {}).get("status") not in ("queued", None):
            return shown
        time.sleep(cfg.POLL_INTERVAL_S)
    return {**shown, "note": "the window has not shown the change yet; get_display tells when it has."}


def _asked_values(name, args):
    """The state keys a setter sets, with the values asked; empty for any other command."""
    if name not in config.SETTERS:
        return {}
    values = (args or {}).get("settings") if name == "set_state" else args
    return {key: value for key, value in values.items() if key not in config.NOT_VALUES} if isinstance(values, dict) else {}


def _reads_as(value, asked):
    if isinstance(value, (int, float)) and isinstance(asked, (int, float)) and not isinstance(value, bool):
        return abs(value - asked) <= 1e-9 * max(1.0, abs(asked))
    return value == asked


def read_back(acceptor, asked, cancel, cfg=config, clock=time.time):
    """What Core holds for the keys a setter set: read until every key reads as asked, or for
    READ_BACK_S at most. None when the instrument does not know one of the keys."""
    deadline = clock() + cfg.READ_BACK_S
    while True:
        try:
            values = acceptor.dispatch("get_state_all", {"keys": list(asked)})
        except Exception:
            return None
        values = {key: values.get(key) for key in asked}
        if all(_reads_as(values[key], value) for key, value in asked.items()) or cancel.is_set() or clock() >= deadline:
            return values
        time.sleep(cfg.POLL_INTERVAL_S)


def _trail_view(snapshot):
    """The readout's TRAIL_KEYS as flat dotted keys: optics.intensity, position.x."""
    out = {}
    for key in config.TRAIL_KEYS:
        group, _, leaf = key.partition(".")
        value = (snapshot or {}).get(group)
        if leaf:
            out[key] = value.get(leaf) if isinstance(value, dict) else None
        elif isinstance(value, dict):
            out.update({f"{group}.{name}": item for name, item in value.items()})
        else:
            out[key] = value
    return out


class StateTrail:
    """The readout keys that changed since the model last saw them: the turn's readout (from the
    session store), then each result. A move's new position otherwise sits three levels deep in
    its result, and a setting's effect, or anything the operator changed meanwhile, nowhere."""

    def __init__(self, acceptor, store=None):
        self._acceptor = acceptor
        self._store = store
        self._turn = None
        self._seen = None
        self._lock = threading.Lock()      # the calls of one reply run on threads of their own

    def since_last(self):
        with self._lock:
            try:
                now = _trail_view(self._acceptor.dispatch("get_snapshot", {}))
            except Exception:
                return {}
            if self._store is not None and self._store.turns and len(self._store.turns) != self._turn:
                self._turn = len(self._store.turns)
                readout = self._store.turns[-1].get("readout")
                self._seen = _trail_view(readout) if readout else None
            seen, self._seen = self._seen, now
            return {} if seen is None else {key: value for key, value in now.items() if seen.get(key) != value}


def with_changes(outcome, trail, changed=None):
    """The result with `changed` (the setter's keys as read back) and then the other readout keys
    that changed since the last result, so that every result ends with them."""
    if not isinstance(outcome, dict):
        return outcome
    if changed is not None:
        outcome["changed"] = changed
    moved = {key: value for key, value in trail.since_last().items()
             if key.rpartition(".")[2] not in (changed or {})}
    if moved:
        outcome["state_changed"] = moved
    return outcome


def describe_error(error):
    """A turn failure the operator can act on.

    Client transport failures often carry no message at all — an httpx read timeout stringifies to
    "" — and the tab then renders a bare "error —" with nothing after it, which is
    indistinguishable from the assistant having said nothing. Lead with the exception type so the
    line always names what went wrong; run_turn logs the traceback alongside it."""
    text = str(error).strip()
    described = f"{type(error).__name__}: {text}" if text else type(error).__name__
    if any(sign in text for sign in config.CONTEXT_TOO_SMALL_SIGNS):
        described = config.CONTEXT_TOO_SMALL_HELP + " — " + described
    return described


def _configured_options(acceptor):
    """The instrument's own vocabulary, fetched only after a call was refused on its values.

    A rejection is the model's whole basis for self-correcting, and the validators are not uniform
    about it: set_filter answers "not one of ['Empty', '515LP']" and the agent recovers, while
    set_zoom answers "'zoom' must be a string" — a type check that fires before the membership
    check — and the agent dead-ends into asking the operator for a vocabulary the microscope
    already knows. Attaching get_config (a READ; it holds no gate) makes every refusal as
    instructive as the best one, without touching the shipped validators."""
    try:
        reply = acceptor.dispatch("get_config", {})
    except Exception:
        return None
    return reply if isinstance(reply, dict) else None


def _safe_keys(schema):
    """The schema with each argument name Anthropic refuses renamed, at any depth, and the
    renaming to undo: a property name must match ^[a-zA-Z0-9_.-]{1,64}$, so "camera_delay_%" is
    offered as "camera_delay_pct". The commands keep their names; only the model sees these."""
    renamed = {}

    def walk(node):
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                out[key] = {}
                for name, sub in value.items():
                    safe = name.replace("%", "pct")
                    if safe != name:
                        renamed[safe] = name
                    out[key][safe] = walk(sub)
            elif key == "required" and isinstance(value, list):
                out[key] = [name.replace("%", "pct") for name in value]
            else:
                out[key] = walk(value)
        return out
    return walk(schema), renamed


def _original_keys(fn, renamed):
    """The call with the names `_safe_keys` gave back to the command's own, at any depth."""
    def back(value):
        if isinstance(value, dict):
            return {renamed.get(key, key): back(item) for key, item in value.items()}
        if isinstance(value, list):
            return [back(item) for item in value]
        return value

    def _call(**args) -> str:
        return fn(**back(args))
    return _call


def _advice(name, code, message):
    """What to do about a refusal, said where the model reads it next: a rule in the manual is
    thousands of tokens away by the time a tool answers, and the busy message itself names the
    command that would end the operator's run."""
    if code == "busy" and config.BUSY_FROM_GUI in message:
        return "The operator is running this at the microscope. Say so and wait; do not stop it to make room."
    if code == "validation" and config.LIMIT_REFUSAL in message and name in config.MOVE_ARGS:
        return "Tell the operator the limit and stop. Do not move to another value in its place."
    return None


def with_advice(name, outcome):
    """A failure's way forward, attached where the model reads it next: the specific advice of
    _advice, else FAILURE_ADVICE. A refusal and a failed look carry it in their error; a WAIT that
    ran and failed, beside its status. A success is returned as it is."""
    error = outcome.get("error") if isinstance(outcome, dict) else None
    if isinstance(error, dict):
        if "advice" not in error:
            general = config.OPTIONS_ADVICE if "configured_options" in error else config.FAILURE_ADVICE
            error["advice"] = _advice(name, error.get("code"), str(error.get("message", ""))) or general
    elif isinstance(outcome, dict) and outcome.get("status") == FAILED:
        outcome.setdefault("advice", config.FAILURE_ADVICE)
    return outcome


def _compact_row(row):
    return {key: row[key] for key in config.ROW_SUMMARY_KEYS if key in row}


def shorten_result(name, result):
    """A tool result the turn can afford. The acquisition list keeps every row but only the keys
    an operator asks about; any other result over RESULT_CHARS keeps the top-level keys that fit
    and names the ones it left out, so the model can ask for them. A short result is returned as
    it is."""
    text = json.dumps(result)
    if len(text) <= config.RESULT_CHARS or not isinstance(result, dict):
        return result
    if name == "get_acquisition_list" and isinstance(result.get("acquisitions"), list):
        rows = [_compact_row(row) for row in result["acquisitions"] if isinstance(row, dict)]
        note = f"{len(rows)} rows, each with {', '.join(config.ROW_SUMMARY_KEYS)} only; the other row keys hold the current settings"
        if len(rows) > config.ROWS_MAX:
            note += f"; rows after the first {config.ROWS_MAX} omitted"
        return dict(result, acquisitions=rows[:config.ROWS_MAX], note=note)   # the list is what was asked for
    kept, omitted, size = {}, [], 2
    for key, value in result.items():
        piece = len(json.dumps({key: value}))
        if size + piece <= config.RESULT_CHARS:
            kept[key] = value
            size += piece
        else:
            omitted.append(f"{key} ({piece} chars)")
    kept["note"] = "result shortened; omitted: " + ", ".join(omitted)
    return kept


def _tool_fn(acceptor, name, kind, cancel, on_call=None, clock=time.time, trail=None, on_started=None):
    """One passthrough tool body, closing over the command it dispatches. The keyword arguments
    ARE the command's wire args, so `move_absolute(targets={"x": 5000})` dispatches verbatim.
    `on_call` (if given) is invoked the moment the command fires, so the GUI can stream the
    activity live. Dispatch errors (out-of-range, busy) are returned to the model as data so it
    can self-correct, not raised; the safety is Core's limits, the busy gate and Stop microscope,
    the same for every client. A call that reached the instrument returns with the readout keys
    it changed (see with_changes). `on_started` (if given) hears of a run that returned while
    under way, with its operation id, so the tab can say when it ends."""
    trail = trail or StateTrail(acceptor)

    def _call(**args) -> str:
        """See the tool description (the command's hint)."""
        if on_call is not None:
            try:
                on_call(name, json.dumps(args or {}))
            except Exception:
                pass
        if cancel.is_set():
            return json.dumps({"status": "cancelled"})
        try:
            outcome = shorten_result(name, dispatch_and_wait(acceptor, name, args, kind, cancel, clock=clock))
        except Exception as error:
            code, message = error_info(error)
            outcome = {"error": {"code": code, "message": message}}
            if code == "validation" and name in config.OPTION_COMMANDS:
                options = _configured_options(acceptor)
                if options is not None:
                    outcome["error"]["configured_options"] = options
        outcome = with_advice(name, outcome)
        if on_started is not None and name in config.RUNS_ON_ITS_OWN and isinstance(outcome, dict) \
                and outcome.get("status") == "running":
            on_started(name, outcome.get("operation"))
        if name == "stop" and isinstance(outcome, dict) and "error" not in outcome:
            running = acceptor.dispatch("get_state_all", {"keys": ["state"]}).get("state")
            if running and running != "idle":
                outcome["note"] = config.STAGE_STOP_NOTE.format(state=running)
        asked = _asked_values(name, args)
        changed = None
        if asked and isinstance(outcome, dict) and "error" not in outcome:
            changed = read_back(acceptor, asked, cancel, clock=clock)
        outcome = with_changes(outcome, trail, changed)
        return json.dumps(outcome)
    return _call


def look(acceptor, endpoint, question, snap, cancel, image_bin=None, eyes=None, clock=time.time,
         history=None, axes=None, frames=None, label=None, focus_metric=None):
    """Take a frame and describe it. The numbers come from get_frame and reach the main model
    always. The picture itself goes to a vision model in a separate call with the question, and
    only that answer comes back — the main conversation never carries images, so a text-only main
    model can still look, and a frame from three turns ago cannot mislead later. With `eyes` (a
    VisionSession) that call is a turn in the vision model's own conversation; without, it is one
    stateless call.

    With a frame `history`, the new frame is kept there with code's measures, `frames` chooses
    recorded frames to show with it ("last 3", "1,7", "3-10"), and the result compares
    them; `snap` false with nothing running shows recorded frames instead of taking one.
    `focus_metric` overrides the operator's choice for this frame."""
    saved = None
    running = _running_mode(acceptor)
    if snap and running is not None:
        snap = False                              # live shows frames already; a snap would take the loop over
    fresh_needed = snap or running is not None or history is None or not history.frames
    frame = fresh = None
    if fresh_needed:
        if snap:
            done = dispatch_and_wait(acceptor, "snap", {"prefix": "assistant"}, WAIT, cancel, clock=clock)
            if done.get("status") != COMPLETED:
                return {"error": {"code": "execution", "message": f"snap did not complete: {done}"}}
            saved = (((done.get("result") or {}).get("operation") or {}).get("result") or {}).get("path")
        request = {"include_image": endpoint.vision, "bin": image_bin or config.LOOK_BIN}
        if history is not None:
            request["array_side"] = config.FRAME_COPY_SIDE
        if focus_metric:
            request["focus_metric"] = focus_metric
        frame = acceptor.dispatch("get_frame", request)
        if not frame.get("available"):
            return {"available": False, "note": "no frame yet; take a snap first"}
        if history is not None:
            source = running or "look"
            fresh = history.add(array_of(frame), frame["stats"], source, _frame_readout(acceptor), axes or {}, label)
    try:
        shown = history.pick(_frames_wanted(frames)) if history is not None and frames is not None else []
    except ValueError as error:
        return {"error": {"code": "validation", "message": str(error)}}
    if fresh is not None and all(f is not fresh for f in shown):
        shown.append(fresh)
    if history is not None and not shown:
        shown = [history.frames[-1]]
    if label and fresh is None and shown:
        shown[-1]["label"] = str(label)
    result = {"available": True}
    if frame is not None:
        result["stats"] = frame["stats"]
    if saved:
        result["file"] = saved                    # in the turn's record: the frame this look saw can be found again
    elif running is not None:
        result["source"] = f"the latest frame of the running {running}, no snap taken"
    if len(shown) == 1 and frame is not None:
        result["kept"] = {k: v for k, v in history.brief(shown[0]).items()
                          if k not in ("time", "position", "settings", "peak", "mean", "saturated", "focus",
                                       "focus_metric")}
    elif shown:
        result["frames"] = [history.brief(f) for f in shown]
        result["changes"] = history.compare(shown)
    if not endpoint.vision:
        result["note"] = "this model cannot see images; decide from the numbers"
    elif question:
        try:
            if eyes is not None:
                pictures = [(_eyes_text(history, f), _png_of(f, frame if f is fresh else None)) for f in shown] or \
                           [(f"Frame numbers: {json.dumps(frame['stats'])}", frame["image"]["base64"])]
                result["answer"] = eyes.look(pictures, question, _frame_context(acceptor))
                result["frames_seen"] = eyes.frames
            else:
                result["answer"] = vision_answer(endpoint, frame["image"], question, frame["stats"])
        except Exception as error:
            result["vision_error"] = describe_error(error)
    return result


def calibrate(acceptor, cancel, history, axes, step_um=None, clock=time.time):
    """Measure how the image moves with the stage at this zoom: snap, move x by a small step,
    snap, move back, the same on y, and from the image shifts (phase correlation of the frames'
    copies) keep the scale for the zoom in the history's calibration, so that centring moves are
    measured rather than nominal. The moves are code's, one block."""
    readout = _frame_readout(acceptor)
    zoom, field = (readout.get("optics") or {}).get("zoom"), field_um(readout)
    if zoom is None or field is None:
        return {"error": {"code": "execution", "message": "the zoom or the camera's pixel size is not in the readout"}}
    step = float(step_um or round(config.CALIBRATE_STEP_FRACTION * field[0]))

    def snapped():
        done = dispatch_and_wait(acceptor, "snap", {"prefix": "calibrate"}, WAIT, cancel, clock=clock)
        if done.get("status") != COMPLETED:
            raise RuntimeError(f"snap did not complete: {done.get('status')}")
        document = acceptor.dispatch("get_frame", {"include_image": False, "array_side": config.FRAME_COPY_SIDE})
        return history.add(array_of(document), document["stats"], "calibrate", _frame_readout(acceptor), axes)

    def moved(axis, delta):
        done = dispatch_and_wait(acceptor, "move_relative", {"deltas": {axis: delta}}, WAIT, cancel, clock=clock)
        if done.get("status") != COMPLETED:
            raise RuntimeError(f"the {axis} move of {delta} um did not complete: {done.get('status')}")

    try:
        start = snapped()
        if flag(start):
            return {"error": {"code": "refused", "message": f"frame {start['n']}: {flag(start)}; calibrate needs a "
                                                            "visible sample that is not saturated"}}
        rows, report, used = [], {"zoom": zoom, "step_um": step}, [start["n"]]
        for axis in ("x", "y"):
            moved(axis, step)
            after = snapped()
            moved(axis, -step)
            used.append(after["n"])
            found = shift(start["image"], after["image"])
            if found is None or found["confidence"] < config.CALIBRATE_CONFIDENCE_MIN:
                return {"error": {"code": "execution", "message": (
                    f"the image shift for {axis} could not be measured (frames {start['n']} and {after['n']}); "
                    "the sample may have too little detail or have left the field")}}
            height, width = start["image"].shape
            right, up = found["right"] / width / step, -found["down"] / height / step
            rows.append([right, up])
            image_um = math.hypot(found["right"] * field[0] / width, found["down"] * field[1] / height)
            # 1 when the pixel size in the configuration is right
            report[axis] = {"sample_moves": _direction(right, up), "image_um_per_stage_um": round(image_um / step, 3)}
    except (RuntimeError, ValueError) as error:
        return {"error": {"code": "execution", "message": str(error)}}
    nominal = nominal_scale(readout, axes)
    report["matches_the_coordinate_system"] = bool(nominal) and all(
        _direction(*rows[i]) == _direction(*nominal[i]) for i in range(2))
    history.calibration.store(zoom, rows, hms(clock()), step)
    report["frames"] = used
    report["note"] = "kept for this zoom; frame measures and the map now use it"
    return report


def _direction(right, up):
    """Which way a positive move carries the sample in the image."""
    if abs(right) >= abs(up):
        return "right" if right > 0 else "left"
    return "up" if up > 0 else "down"


def _frames_wanted(frames):
    """look's `frames` as FrameHistory.pick takes it: "last 3" a count, "4" or "1,7" frame
    numbers, "3-10" a range of them."""
    if isinstance(frames, str):
        text = frames.strip().lower()
        last = re.fullmatch(r"last\s*(\d+)", text)
        if last:
            return int(last.group(1))
        if re.fullmatch(r"\d+(\s*,\s*\d+)*", text):
            return [int(n) for n in text.split(",")]
    return frames


def _eyes_text(history, entry):
    """What the eyes are told about a frame: its number, time, label, where and how it was taken,
    and code's measures."""
    brief = history.brief(entry)
    head = f"Frame {brief['n']}, {brief['time']}, {brief['source']}" + (f", labelled {brief['label']!r}" if "label" in brief else "")
    rest = {k: v for k, v in brief.items() if k not in ("n", "time", "source", "label")}
    return f"{head}. {json.dumps(rest, separators=(',', ':'))}"


def _png_of(entry, frame):
    """The frame's picture for the eyes: the full one when it was just taken, else its small copy."""
    if frame is not None and frame.get("image"):
        return frame["image"]["base64"]
    import base64
    png, _ = to_png(entry["image"], max_size=config.FRAME_COPY_SIDE)
    return base64.b64encode(png).decode("ascii")


def _frame_readout(acceptor):
    """The readout a frame was taken in: state, position, optics and camera; empty when it fails."""
    try:
        snapshot = acceptor.dispatch("get_snapshot", {}) or {}
    except Exception:
        return {}
    return {key: snapshot[key] for key in config.VISION_CONTEXT_KEYS if key in snapshot}


def _frame_context(acceptor):
    """What a picture depends on, from the readout, as compact JSON; empty when the readout fails."""
    kept = _frame_readout(acceptor)
    return json.dumps(kept, default=str, separators=(",", ":")) if kept else ""


class VisionSession:
    """The eyes: the vision model's own conversation for the session. Every look is a turn in it,
    with the frames it asks about, each with its number, time, settings and code's numbers, so the
    eyes can compare them and be asked about the session's frames without a new one. Once answered,
    a turn keeps its text and loses its images: the frames to compare are the ones a look attaches,
    and a look costs the frames it shows. Cleared with the transcript. `model` overrides the
    endpoint's, for the tests."""

    def __init__(self, endpoint, model=None, clock=time.time):
        self.endpoint = endpoint
        self.clock = clock
        self._model = model
        self._agent = None
        self._history = []
        self._loop = None                                  # the eyes' own event loop: the model's HTTP client is bound to it
        self._lock = threading.Lock()                      # one question at a time, from whichever thread asks
        self.frames = 0                                    # looks answered this session

    def look(self, pictures, question, context=""):
        """`pictures`: (what the frame is, its PNG as base64) for each frame to show, oldest first."""
        import base64
        from pydantic_ai import BinaryContent
        parts = [f"{hms(self.clock())}." + (f" Instrument now: {context}" if context else "")]
        for text, png in pictures:
            parts += [text, BinaryContent(data=base64.b64decode(png), media_type="image/png")]
        answer = self._run(parts + [f"Question: {question}"])
        self.frames += 1
        return answer

    def ask(self, question):
        """A question about the frames seen so far, with no new frame."""
        if self.frames == 0:
            return "No frame has been looked at yet in this session; look first."
        return self._run(f"No new frame. Question about the frames seen so far: {question}")

    def reset(self):
        self._history, self.frames = [], 0

    def _run(self, prompt):
        """On the eyes' own loop, whichever thread asks: look runs on a thread the turn does not
        wait on, ask_eyes on another, and a client bound to one loop refuses a second."""
        from pydantic_ai import Agent
        with self._lock:
            if self._agent is None:
                self._agent = Agent(self._model or build_model(self.endpoint),
                                    instructions=config.EYES_INSTRUCTIONS,
                                    model_settings=model_settings(self.endpoint))
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
            result = self._loop.run_until_complete(self._agent.run(prompt, message_history=self._history))
            self._history = detach_old_frames(result.all_messages(), 0)
            return result.output


def detach_old_frames(messages, kept):
    """The messages with the image removed from every frame turn but the last `kept`: the text
    of the turn (time, settings, numbers) and the answer stay. The answer's thinking goes with the
    image: Anthropic signs a thinking block for the turn it saw, and refuses the next request
    when that turn has changed ("bound to a different conversation")."""
    import dataclasses
    from pydantic_ai.messages import BinaryContent, ThinkingPart, UserPromptPart
    with_image = [i for i, m in enumerate(messages)
                  if any(isinstance(p, UserPromptPart) and isinstance(p.content, list)
                         and any(isinstance(c, BinaryContent) for c in p.content) for p in getattr(m, "parts", []))]
    to_strip = set(with_image[:-kept] if kept > 0 else with_image)
    out = []
    for i, message in enumerate(messages):
        if i in to_strip:
            parts = [dataclasses.replace(p, content=[c for c in p.content if not isinstance(c, BinaryContent)]
                                         + ["[frame no longer attached]"])
                     if isinstance(p, UserPromptPart) and isinstance(p.content, list) else p
                     for p in message.parts]
            message = dataclasses.replace(message, parts=parts)
        elif i - 1 in to_strip and any(isinstance(p, ThinkingPart) for p in message.parts):
            message = dataclasses.replace(message, parts=[p for p in message.parts if not isinstance(p, ThinkingPart)])
        out.append(message)
    return out


_CALIBRATE_SCHEMA = {
    "type": "object",
    "properties": {"step_um": {"type": "number", "minimum": 5, "maximum": 2000,
                               "description": "the test move on x and on y; a tenth of the field when omitted"}},
    "additionalProperties": False,
}
_ASK_EYES_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "what to compare or recall across the frames seen"}},
    "required": ["question"],
    "additionalProperties": False,
}


def _running_mode(acceptor):
    """The live mode the instrument is in, else None."""
    try:
        state = acceptor.dispatch("get_state_all", {"keys": ["state"]}).get("state")
    except Exception:
        return None
    return state if state in rc_config.LIVE_STATES else None


def vision_answer(endpoint, image, question, stats):
    """One stateless request to the vision model: the frame, the question, the numbers."""
    import base64

    from pydantic_ai import Agent, BinaryContent

    agent = Agent(
        build_model(endpoint),
        # What to take from the picture comes first and says nothing of stretching: a model told the
        # frame is contrast-stretched judges brightness by that word instead of by the picture.
        instructions="You are looking at one frame from a light-sheet microscope camera. Answer the "
                     "operator's question about it in a few sentences. Judge from the picture what is "
                     "in it: shapes, counts, positions, focus, artefacts, and which parts are brighter "
                     "or darker than others. Only whether the exposure is right comes from the numbers, "
                     "since the picture is scaled to the frame's own range: a saturated_fraction above a "
                     "few percent is saturated; a max below about a tenth of full_scale is underexposed.",
    )
    prompt = [f"{question}\n\nFrame numbers: {json.dumps(stats)}",
              BinaryContent(data=base64.b64decode(image["base64"]), media_type="image/png")]
    return agent.run_sync(prompt).output


_LOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string", "description": "what to check in the image"},
        "snap": {"type": "boolean", "description": "take a new frame first (default true); false shows recorded frames"},
        "frames": {"type": "string", "description": "recorded frames to show as well: 'last 3', '1,7', '3-10'"},
        "label": {"type": "string", "description": "a name for the new frame, to find it again: 'before'"},
        "focus_metric": {"type": "string", "enum": ["laplacian", "dct_shannon"],
                         "description": "only when the operator names one: the focus measure for this frame "
                                        "(dct_shannon is the Auto-Focus one); otherwise the operator's setting"},
    },
    "required": ["question"],
    "additionalProperties": False,
}


def offered_commands():
    """Every command, in registry order, but the prompt-only ones, which are never tools."""
    return [cmd for name, cmd in COMMANDS.items() if name not in _PROMPT_ONLY]


class _WithFocusMetric:
    """The acceptor, adding the operator's focus metric to every get_frame that names none: the
    look, the kept snaps, calibrate and the model's own get_frame all measure the same way."""

    def __init__(self, acceptor, metric):
        self._acceptor, self._metric = acceptor, metric

    def dispatch(self, name, args):
        if name == "get_frame":
            args = {"focus_metric": self._metric(), **(args or {})}
        return self._acceptor.dispatch(name, args)

    def __getattr__(self, name):
        return getattr(self._acceptor, name)


def _keeping_snaps(fn, acceptor, history, axes):
    """The snap tool, keeping each frame it took in the history and naming its number."""
    def _call(**args) -> str:
        outcome = json.loads(fn(**args))
        if isinstance(outcome, dict) and outcome.get("status") == COMPLETED:
            frame = acceptor.dispatch("get_frame", {"include_image": False, "array_side": config.FRAME_COPY_SIDE})
            if frame.get("available"):
                entry = history.add(array_of(frame), frame["stats"], "snap", _frame_readout(acceptor), axes)
                outcome["kept"] = {"n": entry["n"]}
        return json.dumps(outcome)
    return _call


def _row_arguments(schema):
    """The argument names under which a command takes acquisition rows: a list or a single row."""
    properties = schema.get("properties", {})
    return [name for name in ("acquisitions", "acquisition") if name in properties]


class SessionStore:
    """Every turn of the session: the operator's words, the readout the model was given, the tool
    calls with their results, the reply. The readout trail (StateTrail) reads the turn's readout
    from it, and the frames of the session are its frame history. Kept in memory for the session
    only; Clear context empties it."""

    def __init__(self, clock=time.time, calibration=None):
        self.turns = []
        self.clock = clock
        self.frames = FrameHistory(clock, calibration)

    def begin(self, prompt, snapshot):
        """Open a turn."""
        self.turns.append({"turn": len(self.turns) + 1, "time": hms(self.clock()), "prompt": prompt,
                           "readout": snapshot, "tools": [], "reply": None})
        return len(self.turns)

    def finish(self, messages, reply):
        if self.turns:
            self.turns[-1]["tools"] = turn_trace(messages)
            self.turns[-1]["reply"] = reply

def _rows_by_reference(schema):
    """A copy of a schema whose acquisition rows are described by reference to set_acquisition_list
    instead of spelling every row key out again: the checks take the same rows, and repeating the
    row schema in each of them was a third of all tool text. additionalProperties says the object
    takes any keys; without it pydantic-ai sends "properties": {} and a host that decodes against
    the schema returns the row empty."""
    schema = json.loads(json.dumps(schema))
    for name in _row_arguments(schema):
        holder = schema["properties"][name]
        if "items" in holder:
            holder["items"] = {"type": "object", "additionalProperties": True}
            holder["description"] = "rows exactly as set_acquisition_list takes them; omit to use the installed list"
        else:
            schema["properties"][name] = {"type": "object", "additionalProperties": True,
                                          "description": "one row exactly as set_acquisition_list takes it"}
    return schema


def build_tools(acceptor, cancel, on_call=None, endpoint=None, vision_endpoint=None,
                image_bin=None, store=None, vision_session=None, axes=None, focus_metric=None,
                clock=time.time, on_started=None, skills=None):
    """One passthrough tool per offered command (see offered_commands). The tool list is derived
    from COMMANDS, never hand-maintained.

    Each tool publishes the command's own JSON schema (the one MCP tools/list serves), so the model
    sees the argument names, types and ranges. from_schema skips pydantic's validation of the call,
    which keeps accept() the single place a call can be refused, with one error vocabulary. Every
    tool is sequential: a reply that calls two at once (both cloud models do) runs them one after
    the other, in order, instead of having the dispatcher refuse the second as busy.
    `focus_metric` (a callable, read live) is the focus metric of every get_frame that names none.
    `clock` is the assistant's one clock (epoch seconds): the readout clock, a turn's and a frame's
    time and the wait cap all follow it, so a simulator that passes its own decides when time passes."""
    from pydantic_ai import Tool
    if focus_metric is not None:
        acceptor = _WithFocusMetric(acceptor, focus_metric)
    trail = StateTrail(acceptor, store)  # one readout the tools report changes against
    history = store.frames if store is not None else None
    axes = axes or dict(config.DEFAULT_AXES)
    tools = []
    for cmd in offered_commands():
        fn = _tool_fn(acceptor, cmd.name, cmd.kind, cancel, on_call, clock, trail, on_started)
        if cmd.name == "snap" and history is not None:
            fn = _keeping_snaps(fn, acceptor, history, axes)
        schema = cmd.schema
        if cmd.name in config.CODE_ONLY_ARGS:
            schema = dict(schema, properties={k: v for k, v in schema["properties"].items()
                                              if k not in config.CODE_ONLY_ARGS[cmd.name]})
        if cmd.name in config.ROWS_BY_REFERENCE:
            schema = _rows_by_reference(schema)
        schema, renamed = _safe_keys(schema)
        if renamed:
            fn = _original_keys(fn, renamed)
        description = config.TOOL_DESCRIPTIONS.get(cmd.name, cmd.hint or cmd.name)
        tools.append(Tool.from_schema(fn, name=cmd.name, description=description, json_schema=schema, sequential=True))
    if endpoint is not None:
        eyes = vision_endpoint or endpoint  # a dedicated reader, or the main model when it can see

        def _look_now(question, snap, frames, label, focus_metric):
            if on_call is not None:
                on_call("look", json.dumps({k: v for k, v in (("question", question), ("snap", snap), ("frames", frames),
                                                              ("label", label), ("focus_metric", focus_metric))
                                            if v is not None}))
            size = image_bin() if callable(image_bin) else image_bin  # a callable reads a live setting
            reuse = bool(snap) and _snapped_just_now(history, acceptor)  # no second exposure
            try:
                outcome = look(acceptor, eyes, question, snap and not reuse, cancel, size, eyes=vision_session, clock=clock,
                               history=history, axes=axes, frames=frames, label=label, focus_metric=focus_metric)
                if reuse and outcome.get("available"):
                    outcome["frame"] = ("the one snapped a moment ago in this turn, not a second exposure; look "
                                        "takes its own snap, so next time call look alone")
            except Exception as error:  # busy, shutting down: data for the model, like every tool
                code, message = error_info(error)
                outcome = {"error": {"code": code, "message": message}}
            return json.dumps(with_changes(with_advice("look", outcome), trail))

        async def _look(question="", snap=True, frames=None, label=None, focus_metric=None) -> str:
            # On a thread the turn does not wait on: Cancel ends the turn at once, and a vision
            # answer that comes later is dropped.
            return await asyncio.to_thread(_look_now, question, snap, frames, label, focus_metric)

        tools.append(Tool.from_schema(
            _look, name="look", json_schema=_LOOK_SCHEMA, sequential=True,
            description="Takes a snap and describes it: exposure, focus, where the signal is and the move that would "
                        "centre it, and, when the model can see, an answer to `question`. Frames are numbered and kept; "
                        "`frames` shows recorded ones too and compares them. Judge exposure from the numbers, not the "
                        "picture, which is stretched for display. centre_move_um is nominal until calibrate has run "
                        "at this zoom.",
        ))
        if history is not None and history.calibration is not None:
            def _calibrate_now(step_um):
                if on_call is not None:
                    on_call("calibrate", json.dumps({"step_um": step_um} if step_um else {}))
                if cancel.is_set():
                    return json.dumps({"status": "cancelled"})
                outcome = calibrate(acceptor, cancel, history, axes, step_um, clock)
                return json.dumps(with_changes(with_advice("calibrate", outcome), trail))

            async def calibrate_tool(step_um=None) -> str:
                return await asyncio.to_thread(_calibrate_now, step_um)
            tools.append(Tool.from_schema(
                calibrate_tool, name="calibrate", json_schema=_CALIBRATE_SCHEMA, sequential=True,
                description="Measures how the image moves with the stage at this zoom (small x and y moves and back) "
                            "so centring moves are calibrated. Needs a visible sample.",
            ))
        if vision_session is not None and eyes.vision:
            def _ask_now(question):
                if on_call is not None:
                    on_call("ask_eyes", json.dumps({"question": question}))
                try:
                    return json.dumps({"answer": vision_session.ask(question), "frames_seen": vision_session.frames})
                except Exception as error:
                    return json.dumps({"error": {"code": "execution", "message": describe_error(error)}})

            async def ask_eyes(question="") -> str:
                return await asyncio.to_thread(_ask_now, question)     # off the turn's loop, like look
            tools.append(Tool.from_schema(
                ask_eyes, name="ask_eyes", json_schema=_ASK_EYES_SCHEMA, sequential=True,
                description="A question to the eyes about the frames already seen, with no new frame: which frame was "
                            "best, what they remember. When the operator says look, look again or check now, that "
                            "is a new frame: call look, whose answer compares with the earlier frames.",
            ))
    if skills:
        tools.append(_load_skill_tool(skills, on_call))
    return tools


def _load_skill_tool(skills, on_call):
    """The one tool that hands the model a skill's steps; offered only when the microscope has skills."""
    from pydantic_ai import Tool

    def load_skill(name):
        if on_call is not None:
            on_call("load_skill", json.dumps({"name": name}))
        skill = skills.get(name)
        if skill is None:
            return json.dumps({"error": {"code": "validation", "message": f"no skill {name!r}",
                                         "skills": sorted(skills)}})
        return json.dumps({"skill": skill.name, "instructions": skill.body})

    schema = {"type": "object", "properties": {"name": {"type": "string", "enum": sorted(skills)}},
              "required": ["name"], "additionalProperties": False}
    return Tool.from_schema(load_skill, name="load_skill", json_schema=schema, sequential=True,
                            description=config.LOAD_SKILL_DESCRIPTION)


def _snapped_just_now(history, acceptor):
    """True when the newest frame is a snap of this place and these settings from the last
    SNAP_REUSE_S: a look then reads it instead of exposing the sample a second time."""
    newest = history.frames[-1] if history is not None and history.frames else None
    if newest is None or newest["source"] != "snap" or history.clock() - newest["t"] > config.SNAP_REUSE_S:
        return False
    return (newest["position"], newest["settings"]) == place_and_settings(_frame_readout(acceptor))


def _brief(content):
    """A tool result for the session memory: text, an image's base64 replaced by its size, cut short."""
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    text = re.sub(r'"base64": ?"([^"]*)"', lambda m: f'"base64": "<{len(m.group(1))} chars>"', text)
    return text[:config.RECALL_RESULT_CHARS]


def turn_trace(messages):
    """The tool calls of one turn, in order, each with its arguments and what it returned, read
    from the messages pydantic-ai exchanged with the model."""
    calls, returns, order = {}, {}, []
    for message in messages:
        for part in getattr(message, "parts", []):
            kind = type(part).__name__
            if kind == "ToolCallPart":
                calls[part.tool_call_id] = {"tool": part.tool_name, "args": part.args_as_dict()}
                order.append(part.tool_call_id)
            elif kind == "ToolReturnPart":
                returns[part.tool_call_id] = _brief(part.content)
    return [dict(calls[call_id], result=returns.get(call_id)) for call_id in order]


def tokens_of(usage):
    """The tokens a run took, in and out; from the provider's details when pydantic-ai left the
    totals at 0 (a model its price table does not know)."""
    counted = (usage.input_tokens or 0) + (usage.output_tokens or 0)
    details = getattr(usage, "details", None) or {}
    return counted or sum(v for k, v in details.items() if k.endswith(("_prompt_tokens", "_candidates_tokens")))


def last_request_tokens(messages):
    """The input tokens of the last request the model answered: what the session costs per request
    now, with an append-only history. 0 when the provider counted nothing."""
    for message in reversed(messages):
        usage = getattr(message, "usage", None)
        if getattr(message, "kind", None) == "response" and usage is not None:
            return usage.input_tokens or tokens_of(usage)
    return 0


def served_models(messages):
    """The names of the models that answered in these messages, in order of first appearance: a
    gateway may route a request to another model, and the operator is told who really answered."""
    names = []
    for message in messages:
        name = getattr(message, "model_name", None)
        if getattr(message, "kind", None) == "response" and name and name not in names:
            names.append(name)
    return names


_STATE_BLOCK = re.compile(r"\s*<microscope_state>.*?</microscope_state>\s*", re.DOTALL)


def without_state_block(reply):
    """The reply without any <microscope_state> block a model copied from its input: the manual
    forbids quoting it, and a small model does it anyway; the operator is spared the JSON."""
    return _STATE_BLOCK.sub("\n", reply).strip() if reply else reply


def _block_json(value):
    """JSON for a <microscope_state> block: with "<" escaped, no text in the readout (a folder name)
    can close the block and read as the operator's words."""
    return json.dumps(value).replace("<", "\\u003c")


def with_state(acceptor, text, store=None, clock=time.time):
    """The current microscope readout, then the operator's message: data the model can rely on
    instead of calling reads first, with the operator's words last, where a model weighs text
    most, so that a note in a folder name inside the readout does not read as the request. Sent
    without the block if the readout fails. The readout carries the clock, the model's only one
    (a frame's age is read against it); with frames in the store, the frame history in brief and
    the map derived from it. With a store, the turn is opened in it."""
    try:
        snapshot = acceptor.dispatch("get_snapshot", {})
    except Exception:
        snapshot = None
    if snapshot is not None:
        snapshot = dict(snapshot, clock=hms(clock()))
    if snapshot is not None and store is not None and store.frames.frames:
        snapshot = dict(snapshot, frames=store.frames.listing(), map=sample_map(store.frames))
    if store is not None:
        store.begin(text, snapshot)
    if snapshot is None:
        return text
    return f"<microscope_state>\n{_block_json(snapshot)}\n</microscope_state>\n\n{text}"


_KINDS = (("read", "reads, which change nothing"),
          ("action", "actions, which return at once"),
          ("wait", "waits, which return when the instrument is done"),
          ("emergency", "emergency commands, which always run"),
          ("display", "display changes, which change what the windows show and never the instrument"))


def axes_section(axes):
    """The coordinate system as the operator sees it, for the prompt; empty without a choice."""
    if not axes:
        return ""
    chosen = {axis: axes.get(axis) or config.DEFAULT_AXES[axis] for axis in ("x", "y", "z")}
    other = {axis: next(c for c in config.AXIS_CHOICES[axis] if c != chosen[axis]) for axis in chosen}
    return (f"\n\n# Coordinate system\n\nA positive x move carries the sample toward the {chosen['x']} of the "
            f"image and a negative one toward the {other['x']}; positive y {chosen['y']}ward in the image, negative y "
            f"{other['y']}ward; positive z {chosen['z']}, negative z {other['z']}. So {chosen['x']} is +x, "
            f"{other['x']} is -x, {chosen['y']} is +y, {other['y']} is -y, {chosen['z']} (closer) is +z, "
            f"{other['z']} (further) is -z. The operator's left, right, up, down, closer and further are what they "
            "see in the image: convert them to signed moves with this, and say which axis and sign you used.")


def build_system_prompt(acceptor=None, axes=None, skills=None):
    """The hand-written preamble (units, frames, safety) plus the offered commands grouped by
    kind. What each does and its argument shape are in its tool description and schema, which the
    model receives anyway; the prompt does not repeat them. manual.md speaks to the operator as
    "you" and gives each rule its reason; a softened rule can make a model ask where it may
    correct, or clamp an out-of-range value, and the manual names both exceptions. Nothing in the
    prompt depends on the time or the session, so a provider's cache serves it on every request."""
    preamble = (Path(__file__).parent / "manual.md").read_text(encoding="utf-8")
    offered = offered_commands()
    lines = [f"- {label}: {', '.join(cmd.name for cmd in offered if cmd.kind == kind)}"
             for kind, label in _KINDS if any(cmd.kind == kind for cmd in offered)]
    prompt = preamble + "\n\n# Commands\n\nBy kind; each tool's description says what it does.\n" + "\n".join(lines)
    return prompt + axes_section(axes) + skills_section(skills)


def skills_section(skills):
    """The skills by name and description only; load_skill gives the steps. Empty without skills,
    so a microscope without a skills folder gets the general prompt unchanged."""
    if not skills:
        return ""
    return "\n\n" + config.SKILLS_SECTION + "\n".join(f"- {s.name}: {s.description}" for s in skills.values())


@dataclass(frozen=True)
class Endpoint:
    """One model endpoint as chosen in the tab. The key is held in memory only."""

    provider: str
    kind: str
    model: str
    api_key: str = field(default="", repr=False)
    base_url: str = ""
    vision: bool = False  # may be shown a camera frame (the `look` side call)
    request_interval_s: float = 0.0  # at least this long between requests; 0 is no spacing

    @classmethod
    def from_preset(cls, provider, model="", api_key="", base_url="", vision=None):
        """Fill the blanks from the provider preset: an empty model or base URL takes the preset's,
        an empty key takes the preset's environment variable (which may also be unset). Whether the
        model can see comes from the preset, unless said here: for an OpenAI-style server nothing
        but the operator can say whether the model behind it accepts images."""
        preset = config.PROVIDERS[provider]
        key_env = preset.get("key_env")
        key = api_key.strip() or (os.environ.get(key_env, "") if key_env else "")
        return cls(
            provider=provider,
            kind=preset["kind"],
            model=model.strip() or preset["model"],
            api_key=key,
            base_url=base_url.strip() or preset.get("base_url", ""),
            vision=bool(preset.get("vision", False)) if vision is None else bool(vision),
            request_interval_s=float(preset.get("request_interval_s", 0) or 0),
        )

    @property
    def needs_key(self):
        return self.kind != "openai-compatible"


def _build_one(endpoint, model_id):
    if endpoint.kind == "google":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(model_id, provider=GoogleProvider(api_key=endpoint.api_key))
    if endpoint.kind == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(model_id, provider=AnthropicProvider(api_key=endpoint.api_key))
    # "openai" and any OpenAI-compatible; a local server needs no key.
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(base_url=endpoint.base_url or None, api_key=endpoint.api_key or "not-needed")
    return OpenAIChatModel(model_id, provider=provider)


def throttled(model, interval_s):
    """The model with at least `interval_s` seconds between its requests, for a host with a tight
    per-minute limit: a free tier's input-tokens-per-minute cap can allow only two or
    three requests a minute at this prompt size, and one turn fires several. Spacing the requests
    themselves is what lets such a turn complete; a pause between turns cannot reach inside one."""
    import asyncio
    from pydantic_ai.models.wrapper import WrapperModel

    class Throttled(WrapperModel):
        _last = 0.0

        async def request(self, messages, model_settings, model_request_parameters):
            # Real time, not the assistant's clock: the host counts its limit in real seconds.
            # asyncio may wake a sleep up to one clock tick early (15.6 ms on Windows): sleep again.
            while (wait := Throttled._last + interval_s - time.monotonic()) > 0:
                await asyncio.sleep(wait)
            Throttled._last = time.monotonic()
            return await super().request(messages, model_settings, model_request_parameters)
    return Throttled(model)


def model_settings(endpoint):
    """Temperature 0 for the most likely call, unless the endpoint's model refuses it. On an
    Anthropic model the request is cached (prompt caching, through pydantic-ai's settings): the
    tool definitions and the instructions for an hour, since they never change and an operator
    may pause longer than five minutes; the growing history for five minutes, at the cheaper
    write, since its new part is written on every request and a turn's requests are seconds apart.
    Three of Anthropic's four breakpoints; the hour comes first, as the API requires. Each request
    of an append-only session then pays the full price for its new part only; the hits show in
    the usage as cache_read_tokens. Gemini caches on its own."""
    name = endpoint.model if endpoint else ""
    settings = {} if any(refusing in name for refusing in config.MODELS_WITHOUT_TEMPERATURE) \
        else {"temperature": config.MODEL_TEMPERATURE}
    if endpoint is not None and endpoint.kind == "anthropic":
        settings.update(anthropic_cache_tool_definitions="1h", anthropic_cache_instructions="1h", anthropic_cache="5m")
    return settings


def build_model(endpoint):
    """The endpoint's model, throttled when the endpoint asks for it."""
    model = _build_one(endpoint, endpoint.model)
    if endpoint.request_interval_s > 0:
        model = throttled(model, endpoint.request_interval_s)
    return model


def build_agent(acceptor, cancel, on_call=None, model=None, endpoint=None,
                vision_endpoint=None, image_bin=None, store=None, vision_session=None, axes=None,
                focus_metric=None, clock=time.time, on_started=None, skills=None):
    """`endpoint` is what the tab chose (the default preset when None). `model` overrides it: the
    GUI never passes it; the offline evaluation drives this same agent with a scripted model."""
    from pydantic_ai import Agent
    if model is None:
        model = build_model(endpoint or Endpoint.from_preset(config.DEFAULT_PROVIDER))
    # instructions (not system_prompt): applied fresh each run, not accumulated into the
    # message history we carry across turns. The history is never rewritten: a provider that
    # signs a reply's thinking refuses a request whose earlier messages changed, and an
    # append-only history is what its cache serves cheapest.
    agent = Agent(model, instructions=build_system_prompt(axes=axes, skills=skills),
                  tools=build_tools(acceptor, cancel, on_call, endpoint=endpoint,
                                    vision_endpoint=vision_endpoint, image_bin=image_bin, store=store,
                                    vision_session=vision_session, axes=axes,
                                    focus_metric=focus_metric, clock=clock, on_started=on_started,
                                    skills=skills),
                  model_settings=model_settings(endpoint),                     # the most likely call, not a creative one
                  retries=config.TOOL_CALL_RETRIES)                            # a malformed call goes back to the model
    agent.output_validator(_hand_back_an_empty_reply())
    return agent


def _hand_back_an_empty_reply():
    """A reply with no letter or digit in it goes back to the model once; a second one reaches the
    operator as a plain line rather than as, say, an underscore."""
    from pydantic_ai import ModelRetry
    asked = set()                                     # run ids already handed back

    def _check(ctx, output):
        if re.search(r"[^\W_]", output or ""):
            asked.discard(ctx.run_id)
            return output
        if ctx.run_id in asked:
            asked.discard(ctx.run_id)
            return config.EMPTY_REPLY_FALLBACK
        asked.add(ctx.run_id)
        raise ModelRetry(config.EMPTY_REPLY_CHALLENGE)
    return _check


# --- In-process Acceptor lifecycle (called by Core's start_ai_assistant / stop_ai_assistant slots) ---
def start_assistant_for_core(core):
    """Build the in-process Acceptor the AI Assistant dispatches through, on the Core thread, and
    store it on ``core._assistant_acceptor``. Called from Core's start_ai_assistant slot, so the
    QObject takes its thread affinity from the Core thread. Fail-closed like a transport (same limit
    self-test) and refuses while a TCP/MCP transport is running, so the assistant does not start a
    second controller behind the operator's back. Returns the acceptor, or None on refusal /
    self-test failure, with the reason in ``core._assistant_refusal`` for the tab to show."""
    if getattr(core, "_remote_control", None) is not None:
        core._assistant_acceptor = None
        core._assistant_refusal = "Stop the Remote Control transport to use the AI Assistant."
        return None
    if getattr(core, "_assistant_acceptor", None) is None:
        ok, report = self_test(core)
        if not ok:
            reason = "AI Assistant self-test failed: " + "; ".join(report)
            logger.error(reason)
            core._assistant_acceptor = None
            core._assistant_refusal = reason
            return None
        core._assistant_acceptor = Acceptor(core)
    core._assistant_refusal = None
    return core._assistant_acceptor


def stop_assistant_for_core(core):
    """Release the assistant's Acceptor: refuse further dispatch, unwire its completion signals, and
    drop the handle so a transport can start again. The Core-owned session is left untouched."""
    acceptor = getattr(core, "_assistant_acceptor", None)
    if acceptor is not None:
        acceptor.stop()
        core._assistant_acceptor = None


class AssistantWorker(QtCore.QObject):
    """Runs agent turns on the shared Acceptor, off the GUI/Core threads. Single-flight: the
    GUI disables input during a turn. Cancel ends the turn at once (its task is cancelled, so a
    model request in flight is abandoned) and gates the tools (dispatch_and_wait checks `cancel`
    before every dispatch): the agent can only touch the instrument through them."""

    sig_reply = QtCore.pyqtSignal(str)
    sig_tool = QtCore.pyqtSignal(str, str)   # tool name, args-json
    sig_served = QtCore.pyqtSignal(str)      # another model than the chosen one answered (a gateway's substitute)
    sig_usage = QtCore.pyqtSignal(int)       # the input tokens of the turn's last request: the session's size
    sig_error = QtCore.pyqtSignal(str)
    sig_done = QtCore.pyqtSignal()
    sig_run_ended = QtCore.pyqtSignal(str)   # a run the assistant started has ended (the done notice)

    def __init__(self, acceptor):
        super().__init__()
        self._acceptor = acceptor
        self._endpoint = None  # set by configure() before the first turn
        self._vision_endpoint = None
        self._agent = None
        self._history = []               # append-only until reset()
        self.clock = time.time           # the assistant's one clock; set before reset() to replace it
        self.store = SessionStore(self.now, Calibration())   # every turn, and the frames
        self.eyes = None                 # the vision model's own conversation, made by configure()
        self.cancel = threading.Event()
        self._loop = None                # the worker's event loop, made by the first turn and kept
        self._turn = None                # (event loop, task) of the turn in progress: what Cancel cancels
        self._started = None             # (command, operation id) of a run under way, for the done notice
        self.look_image_bin = config.LOOK_BIN   # the tab sets these
        self.focus_metric = config.FOCUS_METRIC
        self.axes = dict(config.DEFAULT_AXES)            # what a positive move does to the sample in the image
        self._agent_axes = None                          # the axes the agent was built with
        self.skills = {}                                 # the microscope's skills (skills.py); the tab sets them

    def configure(self, endpoint, vision_endpoint=None):
        """Use another endpoint (and reader for frames) from the next turn on; the transcript
        history is kept. Called from the GUI thread only between turns."""
        self._endpoint = endpoint
        self._vision_endpoint = vision_endpoint
        self._agent = None
        reader = vision_endpoint or endpoint
        self.eyes = VisionSession(reader, clock=self.now) if reader is not None and reader.vision else None

    def now(self):
        return self.clock()

    def reset(self):
        """Forget the conversation (Clear context). Called between turns, like configure."""
        self._history = []
        self.store = SessionStore(self.now, Calibration())
        if self.eyes is not None:
            self.eyes.reset()            # the eyes forget the frames with the transcript
        self._agent = None               # the tools close over the store

    @QtCore.pyqtSlot(str)
    def run_turn(self, text):
        try:
            self.cancel.clear()
            if self._agent is None or self._agent_axes != self.axes:      # the axes are in the prompt
                self._agent_axes = dict(self.axes)
                self._agent = build_agent(self._acceptor, self.cancel, on_call=self._emit_tool,
                                          endpoint=self._endpoint,
                                          vision_endpoint=self._vision_endpoint,
                                          image_bin=lambda: self.look_image_bin,
                                          focus_metric=lambda: self.focus_metric,
                                          store=self.store, vision_session=self.eyes,
                                          axes=self._agent_axes, clock=self.now, on_started=self._note_started,
                                          skills=self.skills)
            # No whole-turn retry: it would re-run every tool call the first attempt already made.
            # A rate limit or outage reaches the operator as an error they can see and retry. (The
            # SDK's own retry of a 429 or 529 is of one request on the same history: fine.)
            prompt = with_state(self._acceptor, text, self.store, self.now)
            result = self._run_cancellable(self._agent.run(prompt, message_history=self._history))
            self.store.finish(result.new_messages(), result.output)
            self._history = result.all_messages()
            self.sig_usage.emit(last_request_tokens(result.new_messages()))
            chosen = self._endpoint.model if self._endpoint else None
            others = [name for name in served_models(result.new_messages()) if name != chosen]
            if others:   # the operator must know: another model is not the one they evaluated
                self.sig_served.emit(f"{', '.join(others)} answered this turn, standing in for {chosen}")
            self.sig_reply.emit(without_state_block(result.output))
        except asyncio.CancelledError:
            pass
        except Exception as error:
            logger.exception("AI Assistant turn failed")
            self.sig_error.emit(describe_error(error))
        finally:
            self.sig_done.emit()

    def _run_cancellable(self, coro):
        """Agent.run_sync's own recipe (pydantic_ai._utils.run_until_complete: one event loop kept
        across turns, the turn as a task), with the task kept where interrupt() can cancel it: a
        model request in flight is abandoned instead of waited out."""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        loop = self._loop
        task = loop.create_task(coro)
        self._turn = (loop, task)
        if self.cancel.is_set():                 # Cancel came while the turn was being set up
            task.cancel()
        try:
            return loop.run_until_complete(task)
        finally:
            self._turn = None


    def _emit_tool(self, name, args):
        """Called at the tool boundary (worker thread) as each command fires; the queued signal
        delivers it to the GUI so tool calls stream in live rather than all at the end of the turn."""
        self.sig_tool.emit(name, args)

    def _note_started(self, name, operation):
        """A run returned while under way: the tab's check (check_run) says when it ends."""
        self._started = (name, operation)

    @QtCore.pyqtSlot()
    def check_run(self):
        """The tab's check, between turns: when the run the assistant started has ended, say so
        once. A read on the acceptor, from this thread, so the GUI never waits on Core."""
        started = self._started
        if started is None:
            return
        name, operation = started
        try:
            progress = self._acceptor.dispatch("get_progress", {}) or {}
        except (RuntimeError, TimeoutError):          # shutting down, or Core busy: the next check asks again
            return
        current = progress.get("operation") or {}
        status = current.get("status") if current.get("id") == operation else None
        if status in _TERMINAL or (status is None and progress.get("state") == "idle"):
            self._started = None
            ended = {COMPLETED: "finished", FAILED: "failed", STOPPED: "stopped"}.get(status, "ended")
            self.sig_run_ended.emit(config.DONE_NOTICE.format(what=config.RUN_LABELS.get(name, name), status=ended,
                                                              time=hms(self.now())))

    def interrupt(self):
        """The Cancel button: stop the assistant, not the microscope. The turn ends at once, a model
        request in flight abandoned; a tool call still running returns 'cancelled' (dispatch_and_wait
        checks the flag). Whatever the assistant already started keeps running; stopping the
        instrument is stop_microscope, a separate decision."""
        self.cancel.set()
        turn = self._turn
        if turn is not None:
            loop, task = turn
            loop.call_soon_threadsafe(task.cancel)
