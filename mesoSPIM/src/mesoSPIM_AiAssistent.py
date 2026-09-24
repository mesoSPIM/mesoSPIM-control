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

import json
import re
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt5 import QtCore

from .mesoSPIM_RemoteControl_Dispatcher import COMMANDS, READ, WAIT, COMPLETED, FAILED, error_info
from .mesoSPIM_RemoteControl_Servers import Acceptor
from .mesoSPIM_RemoteControl_Commands import self_test
from . import mesoSPIM_AiAssistent_Config as config

logger = logging.getLogger(__name__)

_TERMINAL = {COMPLETED, FAILED}

# Commands embedded in the system prompt, so not worth exposing as tools (a call only re-fetches
# what the model already has). get_manual is the whole command reference — large and static.
_PROMPT_ONLY = {"get_manual"}


def dispatch_and_wait(acceptor, name, args, kind, cancel, cfg=config):
    """Run one command and return a finished result. For WAIT commands the return always
    carries a consistent top-level `status` ('completed' / 'failed' / 'still_running' /
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
    if kind != WAIT:
        return result
    op = (result or {}).get("operation") or {}
    op_id = op.get("id")
    if op.get("status") in _TERMINAL:
        return {"status": op["status"], "operation": op_id, "result": result}

    deadline = time.monotonic() + cfg.WAIT_CAP_S
    while time.monotonic() < deadline:
        if cancel.is_set():
            return {"status": "cancelled", "operation": op_id}      # interrupt() halts the hardware
        time.sleep(cfg.POLL_INTERVAL_S)
        snap = acceptor.dispatch("get_progress", {}) or {}          # READ: cheap, holds no gate
        status = (snap.get("operation") or {}).get("status")
        if status in _TERMINAL:
            return {"status": status, "operation": op_id, "result": snap}
    return {"status": "still_running", "operation": op_id,
            "note": "operation exceeds the wait cap; call get_progress to check on it."}


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


def _only_keys(fn, name, keys):
    """Refuse, as data, any argument outside `keys`; then call through."""
    def _call(**args) -> str:
        extra = sorted(set(args) - set(keys))
        if extra:
            return json.dumps({"error": {"code": "validation",
                                         "message": f"{name} offers only {', '.join(keys)} in the Regular tool set; "
                                                    f"{', '.join(extra)} needs the Full tool set (the operator's choice "
                                                    "in the setup box)"}})
        return fn(**args)
    return _call


class ConfirmationGate:
    """The operator's Run / Cancel for a confirm-first command, asked from the worker thread and
    answered from the GUI thread. One question at a time. The question waits as long as it takes:
    nothing is pending at the provider or on the instrument meanwhile, and Cancel and
    Stop microscope answer it too. This is a gate in code: the model cannot talk its way past it."""

    def __init__(self, on_ask):
        self._on_ask = on_ask
        self._answered = threading.Event()
        self._answer = False

    def ask(self, name, args):
        self._answered.clear()
        self._answer = False
        self._on_ask(name, json.dumps(args or {}))
        self._answered.wait()
        return self._answer

    def answer(self, allowed):
        self._answer = bool(allowed)
        self._answered.set()


class TurnGuard:
    """Three rules of the manual, kept in code for the length of one turn, because a small model
    reads them and does otherwise. After a move was refused for a movement limit, no other target
    for that axis is taken: a different number is a different instruction, and the operator gives
    those. After a command was refused because the operator is running something from the GUI, a
    stop is theirs to confirm, not the model's way to make room. And a look right after a snap
    reads that frame instead of exposing the sample a second time.

    A turn is one operator message, counted by the session store; without a store there is no turn
    to count and the guard lets everything through."""

    def __init__(self, store=None):
        self._store = store
        self._turn = None
        self._clear()

    def _clear(self):
        self.refused_axes = set()
        self.busy_from_gui = False
        self.fresh_snap = False
        self.light_changes = {}

    def _sync(self):
        if self._store is None:
            return False
        turn = len(self._store.turns)
        if turn != self._turn:
            self._turn = turn
            self._clear()
        return True

    def before(self, name, args):
        """The refusal this call gets, shaped like any tool error, or None to let it through."""
        if not self._sync() or name not in config.MOVE_ARGS:
            return None
        asked = (args or {}).get(config.MOVE_ARGS[name])
        again = sorted(self.refused_axes & set(asked)) if isinstance(asked, dict) else []
        if not again:
            return None
        return {"error": {"code": "refused",
                          "message": f"{', '.join(again)}: a move was refused for a movement limit earlier in this "
                                     "turn, and another target in its place is not what the operator asked for. "
                                     "Tell them the limit and what was refused; the next number is theirs."}}

    def stop_is_the_operators(self, name):
        """True for a stop that would end what the operator is running from the GUI."""
        return self._sync() and self.busy_from_gui and name in config.STOP_COMMANDS

    def is_one_change_too_many(self, name):
        """True when this turn has already changed this light setting as often as a turn may: asked
        to double the intensity of a dim frame once, a 12B went 20, 40, 80, 100 because the next
        frame looked no better. The light on the sample is the operator's to escalate."""
        return self._sync() and self.light_changes.get(name, 0) >= config.LIGHT_CHANGES_PER_TURN.get(name, 1 << 30)

    def take_fresh_snap(self):
        """True, once, when the last thing done to the instrument in this turn was a snap."""
        fresh = self._sync() and self.fresh_snap
        self.fresh_snap = False
        return fresh

    def after(self, name, args, outcome):
        """Note what this call's result rules out for the rest of the turn."""
        if not self._sync():
            return
        error = outcome.get("error") if isinstance(outcome, dict) else None
        message = str((error or {}).get("message", ""))
        if error and error.get("code") == "busy" and config.BUSY_FROM_GUI in message:
            self.busy_from_gui = True
        if error and error.get("code") == "validation" and config.LIMIT_REFUSAL in message and name in config.MOVE_ARGS:
            asked = (args or {}).get(config.MOVE_ARGS[name])
            self.refused_axes |= set(asked) if isinstance(asked, dict) else set()
        if name in config.LIGHT_CHANGES_PER_TURN and not error:
            self.light_changes[name] = self.light_changes.get(name, 0) + 1
        if name == "snap":
            self.fresh_snap = isinstance(outcome, dict) and outcome.get("status") == COMPLETED
        elif name == "look" or (name in COMMANDS and COMMANDS[name].kind != READ):
            self.fresh_snap = False           # the instrument changed, or the frame was read


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
            error["advice"] = _advice(name, error.get("code"), str(error.get("message", ""))) or config.FAILURE_ADVICE
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


def _tool_fn(acceptor, name, kind, cancel, on_call=None, gate=None, guard=None):
    """One passthrough tool body, closing over the command it dispatches. The keyword arguments
    ARE the command's wire args, so `move_absolute(targets={"x": 5000})` dispatches verbatim.
    `on_call` (if given) is invoked the moment the command fires, so the GUI can stream the
    activity live. Dispatch errors (out-of-range, busy) are returned to the model as data so it
    can self-correct, not raised. A confirm-first command first asks the operator through `gate`,
    and so does a stop that would end the operator's own run (see TurnGuard)."""
    guard = guard or TurnGuard()

    def _call(**args) -> str:
        """See the tool description (the command's hint)."""
        if on_call is not None:
            try:
                on_call(name, json.dumps(args or {}))
            except Exception:
                pass
        if cancel.is_set():
            return json.dumps({"status": "cancelled"})                   # never ask after Cancel
        refusal = guard.before(name, args)
        if refusal is not None:
            return json.dumps(refusal)
        refused = json.dumps({"error": {"code": "refused", "message": f"the operator did not confirm {name}"}})
        if gate is not None and name in config.CONFIRM_FIRST and not gate.ask(name, args):
            return refused
        if guard.stop_is_the_operators(name) and (gate is None or not gate.ask(name, args)):
            return refused                                               # nobody to ask is not a yes
        if guard.is_one_change_too_many(name) and (gate is None or not gate.ask(name, args)):
            return json.dumps({"error": {"code": "refused", "message": (
                f"the operator did not confirm another {name} in this turn. It has been changed "
                f"{config.LIGHT_CHANGES_PER_TURN[name]} times already; tell them what the frames showed and stop.")}})
        try:
            outcome = shorten_result(name, dispatch_and_wait(acceptor, name, args, kind, cancel))
        except Exception as error:
            code, message = error_info(error)
            outcome = {"error": {"code": code, "message": message}}
            if code == "validation":
                options = _configured_options(acceptor)
                if options is not None:
                    outcome["error"]["configured_options"] = options
        outcome = with_advice(name, outcome)
        guard.after(name, args, outcome)
        return json.dumps(outcome)
    return _call


def look(acceptor, endpoint, question, snap, cancel, image_size=None):
    """Take a frame and describe it. The numbers come from get_frame and reach the main model
    always. The picture itself goes to a vision model in a separate single-shot call with the
    question, and only that answer comes back — the main conversation never carries images, so a
    text-only main model can still look, and a frame from three turns ago cannot mislead later."""
    if snap:
        done = dispatch_and_wait(acceptor, "snap", {"prefix": "assistant"}, WAIT, cancel)
        if done.get("status") != COMPLETED:
            return {"error": {"code": "execution", "message": f"snap did not complete: {done}"}}
    frame = acceptor.dispatch("get_frame", {"include_image": endpoint.vision, "max_size": image_size or config.LOOK_IMAGE_SIZE})
    if not frame.get("available"):
        return {"available": False, "note": "no frame yet; take a snap first"}
    result = {"available": True, "stats": frame["stats"]}
    image = frame.get("image")
    if image is None:
        result["note"] = "this model cannot see images; decide from the numbers"
    elif question:
        try:
            result["answer"] = vision_answer(endpoint, image, question, frame["stats"])
        except Exception as error:
            result["vision_error"] = describe_error(error)
    return result


def vision_answer(endpoint, image, question, stats):
    """One stateless request to the vision model: the frame, the question, the numbers."""
    import base64

    from pydantic_ai import Agent, BinaryContent

    agent = Agent(
        build_model(endpoint),
        # What to take from the picture comes first and says nothing of stretching: told the frame
        # was "contrast-stretched" and "cannot show exposure", gemma4:12b answered which of three
        # spots is brightest with "all appear equally bright because the image is contrast-stretched",
        # on every scaling tried, and compared them as soon as those words were gone.
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
        "snap": {"type": "boolean", "description": "take a new frame first (default true); false reuses the last one"},
    },
    "required": ["question"],
    "additionalProperties": False,
}


def offered_commands(profile=None):
    """The commands the assistant offers under a tool profile, in registry order. A profile whose
    set is None offers everything. The prompt-only commands are never tools."""
    allowed = config.TOOL_PROFILES[profile or config.DEFAULT_TOOL_PROFILE]
    return [cmd for name, cmd in COMMANDS.items()
            if name not in _PROMPT_ONLY and (allowed is None or name in allowed)]


def hidden_commands(profile=None):
    """The command names a tool profile withholds, in registry order: what the model is told it
    does not have, so it says so instead of standing another command in for it."""
    offered = {cmd.name for cmd in offered_commands(profile)}
    return [name for name in COMMANDS if name not in offered and name not in _PROMPT_ONLY]


def _row_arguments(schema):
    """The argument names under which a command takes acquisition rows: a list or a single row."""
    properties = schema.get("properties", {})
    return [name for name in ("acquisitions", "acquisition") if name in properties]


class SessionStore:
    """Every turn of the session in full: the operator's words, the readout the model was given,
    the tool calls with their results, the reply. The memory the model carries keeps older turns
    compact; what compaction leaves out is here, and the recall and search tools hand it back on
    request. Kept in memory for the session only; Clear all empties it."""

    def __init__(self):
        self.turns = []

    def begin(self, prompt, snapshot):
        self.turns.append({"turn": len(self.turns) + 1, "time": time.strftime("%H:%M:%S"),
                           "prompt": prompt, "readout": snapshot, "tools": [], "reply": None})
        return len(self.turns)

    def finish(self, messages, reply):
        if self.turns:
            self.turns[-1]["tools"] = turn_trace(messages)
            self.turns[-1]["reply"] = reply

    def _get(self, snapshot, path):
        value = snapshot
        for key in path.split("."):
            value = value[key] if isinstance(value, dict) else None
        return value

    def recall(self, turn=None, changed=None):
        """The full readout of one turn (1 is the first, -1 the newest), or the turns in which a
        dotted readout key changed, with its value before and after."""
        if changed:
            found, previous = [], None
            for entry in self.turns:
                value = self._get(entry["readout"], changed) if entry["readout"] else None
                if previous is not None and value != previous[1]:
                    found.append({"turn": entry["turn"], "time": entry["time"], "from": previous[1], "to": value,
                                  "prompt": entry["prompt"][:120]})
                previous = (entry["turn"], value)
            return {"key": changed, "changes": found, "turns": len(self.turns)}
        if not self.turns:
            return {"error": {"code": "not_found", "message": "no turns yet"}}
        index = (turn if turn is not None else -1)
        index = index - 1 if index > 0 else index
        try:
            entry = self.turns[index]
        except IndexError:
            return {"error": {"code": "not_found", "message": f"no turn {turn}; the session has {len(self.turns)}"}}
        return {key: entry[key] for key in ("turn", "time", "prompt", "readout", "tools", "reply")}

    def search(self, query, limit=5):
        """Turns whose operator message, reply or tool results contain the words of the query,
        best matches first: a lookup by words, which needs no model and works offline."""
        words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
        hits = []
        for entry in self.turns:
            text = " ".join([entry["prompt"], entry["reply"] or "", json.dumps(entry["tools"])]).lower()
            score = sum(text.count(w) for w in words)
            if score:
                hits.append((score, {"turn": entry["turn"], "time": entry["time"], "prompt": entry["prompt"][:200],
                                     "reply": (entry["reply"] or "")[:200]}))
        hits.sort(key=lambda pair: (-pair[0], pair[1]["turn"]))
        return {"query": query, "matches": [hit for _, hit in hits[:limit]], "turns": len(self.turns)}


_RECALL_SCHEMA = {
    "type": "object",
    "properties": {
        "turn": {"type": "integer", "description": "1 is the first turn of the session, -1 the newest"},
        "changed": {"type": "string", "description": "a readout key such as optics.intensity or position.x: "
                                                     "the turns in which it changed, instead of one turn"},
    },
    "additionalProperties": False,
}
_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "words to look for"},
                   "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
    "required": ["query"],
    "additionalProperties": False,
}


def _store_tools(store, on_call):
    from pydantic_ai import Tool

    def recall_turn(turn=None, changed=None) -> str:
        if on_call is not None:
            on_call("recall_turn", json.dumps({"turn": turn, "changed": changed}))
        return json.dumps(store.recall(turn=turn, changed=changed), default=str)

    def search_history(query="", limit=5) -> str:
        if on_call is not None:
            on_call("search_history", json.dumps({"query": query, "limit": limit}))
        return json.dumps(store.search(query, limit), default=str)

    return [
        Tool.from_schema(recall_turn, name="recall_turn", json_schema=_RECALL_SCHEMA,
                         description="The full readout, tool calls and reply of an earlier turn, or the turns in "
                                     "which a readout key changed. Older turns in your memory keep only a one-line "
                                     "readout; this has the rest."),
        Tool.from_schema(search_history, name="search_history", json_schema=_SEARCH_SCHEMA,
                         description="Earlier turns of this session whose operator message, reply or tool results "
                                     "contain the given words, best matches first. For anything the operator said or "
                                     "asked earlier that is no longer in your memory."),
    ]


_ROW_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {"row": {"type": "integer", "minimum": 0},
                   "changes": {"type": "object", "description": "row key: new value"}},
    "required": ["row", "changes"],
    "additionalProperties": False,
}


def _row_update_tool(acceptor, install, on_call, hidden):
    """Change the named keys of one row and hand the whole list to set_acquisition_list, so the
    rest of the row is the instrument's, never retyped. On the Windows demo a rename through
    set_acquisition_list rewrote the zoom, the focus and the planes. `install` is the tool body
    of set_acquisition_list, so its checks, the gate and the advice all apply; `hidden` are the
    keys this tool set may not change (the ETL under Regular)."""
    from pydantic_ai import Tool
    known = set(COMMANDS["set_acquisition_list"].schema["properties"]["acquisitions"]["items"]["properties"])

    def refused(message):
        return json.dumps(with_advice("update_acquisition_row", {"error": {"code": "validation", "message": message}}))

    def update_acquisition_row(row=0, changes=None) -> str:
        if on_call is not None:
            on_call("update_acquisition_row", json.dumps({"row": row, "changes": changes}))
        rows = acceptor.dispatch("get_acquisition_list", {}).get("acquisitions") or []
        if not isinstance(changes, dict) or not changes:
            return refused("changes must name at least one row key and its new value")
        if not isinstance(row, int) or not 0 <= row < len(rows):
            return refused(f"row {row} is not in the acquisition list, which has {len(rows)} rows")
        unknown = sorted(set(changes) - known)
        if unknown:
            return refused(f"unknown row key(s): {', '.join(unknown)}; the keys are {', '.join(sorted(known))}")
        withheld = sorted(set(changes) & set(hidden))
        if withheld:
            return refused(f"{', '.join(withheld)} cannot be changed with this tool set")
        new = [dict(existing) for existing in rows]
        new[row].update(changes)
        return install(acquisitions=new, selected_row=row)

    return Tool.from_schema(update_acquisition_row, name="update_acquisition_row", json_schema=_ROW_UPDATE_SCHEMA,
                            description=config.TOOL_DESCRIPTIONS["update_acquisition_row"])


def _rows_by_reference(schema):
    """A copy of a schema whose acquisition rows are described by reference to set_acquisition_list
    instead of spelling every row key out again: the checks take the same rows, and repeating the
    row schema in each of them was a third of all tool text."""
    schema = json.loads(json.dumps(schema))
    for name in _row_arguments(schema):
        holder = schema["properties"][name]
        if "items" in holder:
            holder["items"] = {"type": "object"}
            holder["description"] = "rows exactly as set_acquisition_list takes them; omit to use the installed list"
        else:
            schema["properties"][name] = {"type": "object",
                                          "description": "one row exactly as set_acquisition_list takes it"}
    return schema


def _rows_without(schema, keys):
    """A copy of a schema whose acquisition rows (a list, or a single one) no longer offer `keys`."""
    schema = json.loads(json.dumps(schema))
    for name in _row_arguments(schema):
        holder = schema["properties"][name]
        row = holder.get("items", holder)
        for key in keys:
            row.get("properties", {}).pop(key, None)
    return schema


def _refuse_row_keys(fn, name, keys):
    """Refuse, as data, an acquisition row that carries any of `keys`; then call through."""
    def _call(**args) -> str:
        rows = list(args.get("acquisitions") or [])
        if isinstance(args.get("acquisition"), dict):
            rows.append(args["acquisition"])
        found = sorted({key for row in rows if isinstance(row, dict) for key in row if key in keys})
        if found:
            return json.dumps({"error": {"code": "validation",
                                         "message": f"{name}: {', '.join(found)} are not part of the Regular tool set; "
                                                    "a row takes the current settings for them, and the Full tool set "
                                                    "(the operator's choice in the setup box) offers them"}})
        return fn(**args)
    return _call


def _narrowed(cmd, keys):
    """A copy of the command's schema offering only `keys`, and a check for a call to it."""
    schema = dict(cmd.schema)
    schema["properties"] = {k: v for k, v in cmd.schema["properties"].items() if k in keys}
    required = [k for k in cmd.schema.get("required", []) if k in keys]
    schema.pop("required", None)
    if required:
        schema["required"] = required
    return schema


def build_tools(acceptor, cancel, on_call=None, endpoint=None, gate=None, vision_endpoint=None,
                image_size=None, profile=None, store=None):
    """One passthrough tool per offered command (see offered_commands). The tool list is derived
    from COMMANDS and the profile — never hand-maintained.

    Each tool publishes the command's own JSON schema (the one MCP tools/list serves), so the model
    sees the argument names, types and ranges. from_schema skips pydantic's validation of the call,
    which keeps accept() the single place a call can be refused, with one error vocabulary. In the
    Regular profile a straddling command is offered with a narrowed schema and refuses the rest."""
    from pydantic_ai import Tool
    regular = (profile or config.DEFAULT_TOOL_PROFILE) == "Regular"
    narrow = config.REGULAR_ARGS if regular else {}
    guard = TurnGuard(store)             # one for all the tools: what one call rules out for the next
    tools = []
    installs = {}
    for cmd in offered_commands(profile):
        fn = _tool_fn(acceptor, cmd.name, cmd.kind, cancel, on_call, gate, guard)
        installs[cmd.name] = fn
        schema = cmd.schema
        if cmd.name in narrow:
            keys = narrow[cmd.name]
            schema = _narrowed(cmd, keys)
            fn = _only_keys(fn, cmd.name, keys)
        if cmd.name in config.ROWS_BY_REFERENCE:
            schema = _rows_by_reference(schema)
        if regular and _row_arguments(schema):
            schema = _rows_without(schema, config.REGULAR_ROW_HIDDEN)
            fn = _refuse_row_keys(fn, cmd.name, config.REGULAR_ROW_HIDDEN)
        description = config.TOOL_DESCRIPTIONS.get(cmd.name, cmd.hint or cmd.name)
        tools.append(Tool.from_schema(fn, name=cmd.name, description=description, json_schema=schema))
    if "set_acquisition_list" in installs:
        tools.append(_row_update_tool(acceptor, installs["set_acquisition_list"], on_call,
                                      config.REGULAR_ROW_HIDDEN if regular else ()))
    if store is not None:
        tools += _store_tools(store, on_call)
    if endpoint is not None:
        eyes = vision_endpoint or endpoint  # a dedicated reader, or the main model when it can see

        def _look(question="", snap=True) -> str:
            if on_call is not None:
                on_call("look", json.dumps({"question": question, "snap": snap}))
            size = image_size() if callable(image_size) else image_size  # a callable reads a live setting
            reuse = bool(snap) and guard.take_fresh_snap()  # snapped a moment ago: no second exposure
            try:
                outcome = look(acceptor, eyes, question, snap and not reuse, cancel, size)
                if reuse and outcome.get("available"):
                    outcome["frame"] = ("the one snapped a moment ago in this turn, not a second exposure; look "
                                        "takes its own snap, so next time call look alone")
            except Exception as error:  # busy, shutting down: data for the model, like every tool
                code, message = error_info(error)
                outcome = {"error": {"code": code, "message": message}}
            outcome = with_advice("look", outcome)
            guard.after("look", {}, outcome)
            return json.dumps(outcome)

        tools.append(Tool.from_schema(
            _look, name="look", json_schema=_LOOK_SCHEMA,
            description="Takes a snap itself (or reuses the last frame with snap=false) and describes it: numbers about "
                        "exposure, focus and where the signal is, plus, when the model can see, an answer to "
                        "`question` about the image. Use it to check the sample, the field of view or the exposure.",
        ))
    return tools


def traces_folder(cfg):
    """Where turns are recorded: the microscope config's ``ai_assistant_traces_folder`` when
    set, else ``~/mesoSPIM/assistant_traces``."""
    configured = getattr(cfg, config.TRACES_FOLDER_CONFIG_KEY, None)
    return configured or os.path.join(os.path.expanduser("~"), "mesoSPIM", "assistant_traces")


def _brief(content):
    """A tool result for the record: text, an image's base64 replaced by its size, cut short."""
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    text = re.sub(r'"base64": ?"([^"]*)"', lambda m: f'"base64": "<{len(m.group(1))} chars>"', text)
    return text[:config.TRACE_RESULT_CHARS]


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


def served_models(messages):
    """The names of the models that answered in these messages, in order of first appearance: the
    fallback model rolls in silently on a rate limit, and a trace should say who really answered."""
    names = []
    for message in messages:
        name = getattr(message, "model_name", None)
        if getattr(message, "kind", None) == "response" and name and name not in names:
            names.append(name)
    return names


def write_trace(folder, record):
    """Append one turn to today's JSONL file in the folder."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, time.strftime("assistant-%Y-%m-%d.jsonl"))
    with open(path, "a", encoding="utf-8") as sink:
        sink.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


_STATE_BLOCK = re.compile(r"\s*<microscope_state>.*?</microscope_state>\s*", re.DOTALL)


def without_state_block(reply):
    """The reply without any <microscope_state> block a model copied from its input: the manual
    forbids quoting it, and a small model does it anyway. The evaluation scores the raw reply, so
    the habit stays visible there; the operator is spared the JSON."""
    return _STATE_BLOCK.sub("\n", reply).strip() if reply else reply


def with_state(acceptor, text, store=None):
    """The current microscope readout, then the operator's message: data the model can rely on
    instead of calling reads first, with the operator's words last, where a model weighs text
    most, so that a note in a folder name inside the readout does not read as the request. Sent
    without the block if the readout fails. With a store, the turn is opened in it."""
    try:
        snapshot = acceptor.dispatch("get_snapshot", {})
    except Exception:
        snapshot = None
    if store is not None:
        store.begin(text, snapshot)
    if snapshot is None:
        return text
    return f"<microscope_state>\n{json.dumps(snapshot)}\n</microscope_state>\n\n{text}"


_KINDS = (("read", "reads, which change nothing"),
          ("action", "actions, which return at once"),
          ("wait", "waits, which return when the instrument is done"),
          ("emergency", "emergency commands, never gated"))


def build_system_prompt(acceptor=None, profile=None):
    """The hand-written preamble (units, frames, safety) plus the offered commands grouped by
    kind. What each does and its argument shape are in its tool description and schema, which the
    model receives anyway; the prompt does not repeat them, which keeps it small enough for a local
    model's context alongside the conversation."""
    preamble = (Path(__file__).parent / "assistant_manual.md").read_text(encoding="utf-8")
    offered = offered_commands(profile)
    lines = [f"- {label}: {', '.join(cmd.name for cmd in offered if cmd.kind == kind)}"
             for kind, label in _KINDS if any(cmd.kind == kind for cmd in offered)]
    prompt = preamble + "\n\n# Commands\n\nBy kind; each tool's description says what it does.\n" + "\n".join(lines)
    hidden = hidden_commands(profile)
    if hidden:
        prompt += ("\n\n# Not in this tool set\n\nThe operator chose the "
                   f"{profile or config.DEFAULT_TOOL_PROFILE} tool set, which does not offer: {', '.join(hidden)}. "
                   "The Full tool set, chosen in the setup box, does. When a request needs one of them, say "
                   "exactly that, and stop: never call another command in its place and never report a result "
                   "you did not get.")
    return prompt


def trim_history(messages, max_turns):
    """Keep the last `max_turns` operator turns. A turn starts at a request whose first part is
    the operator's prompt, so a tool call is never separated from its result."""
    starts = _turn_starts(messages)
    if len(starts) <= max_turns:
        return list(messages)
    return list(messages[starts[-max_turns]:])


def _turn_starts(messages):
    return [index for index, message in enumerate(messages)
            if type(getattr(message, "parts", [None])[0]).__name__ == "UserPromptPart"]


def _compact_prompt(text):
    """The operator's message with its readout reduced to the few values later turns may refer to
    ("put it back to what it was"): a stale readout is noise, its optics and position are not."""
    match = re.search(r"<microscope_state>\n?(.*?)\n?</microscope_state>", text, re.DOTALL)
    if not match:
        return text
    try:
        snapshot = json.loads(match.group(1))
        kept = {key: snapshot[key] for key in config.HISTORY_READOUT_KEYS if key in snapshot}
        summary = f"<microscope_state_then>{json.dumps(kept)}</microscope_state_then>"
    except (ValueError, TypeError):
        summary = ""
    return (text[:match.start()] + summary + text[match.end():]).strip()


def _is_challenge(message):
    parts = getattr(message, "parts", None) or []
    return bool(config.CALLED_NOTHING_CHALLENGE) and any(
        type(part).__name__ == "RetryPromptPart" and part.content == config.CALLED_NOTHING_CHALLENGE for part in parts)


def _without_answered_challenges(messages):
    """The messages without the question about a reply that called nothing, and without its
    answer, where the answer called nothing either: in earlier turns only, since the turn in
    progress may still be waiting for that answer. The first reply is what the operator was
    shown, and the memory should end a turn on it rather than on the word SAME."""
    messages = list(messages)
    starts = _turn_starts(messages)
    current = starts[-1] if starts else len(messages)
    out, index = [], 0
    while index < len(messages):
        message = messages[index]
        answer = messages[index + 1] if index + 1 < len(messages) else None
        calls = any(type(part).__name__ == "ToolCallPart" for part in getattr(answer, "parts", None) or [])
        if index + 1 < current and _is_challenge(message) and answer is not None and not calls:
            index += 2
            continue
        out.append(message)
        index += 1
    return out


def compact_history(messages, full_turns=None):
    """The history with its older turns made small: the last `full_turns` operator turns stay as
    they are; before them, each operator message keeps a one-line readout instead of the whole
    state block, and a tool result longer than HISTORY_RESULT_CHARS is shortened. Tool calls, their
    pairing with results and the replies are untouched, so nothing the model said is lost."""
    from dataclasses import replace
    full_turns = config.HISTORY_FULL_TURNS if full_turns is None else full_turns
    messages = _without_answered_challenges(messages)
    starts = _turn_starts(messages)
    cutoff = starts[-full_turns] if len(starts) > full_turns else 0
    if cutoff == 0:
        return list(messages)
    out = []
    for index, message in enumerate(messages):
        if index >= cutoff or not getattr(message, "parts", None):
            out.append(message)
            continue
        parts = []
        for part in message.parts:
            kind = type(part).__name__
            if kind == "UserPromptPart" and isinstance(part.content, str):
                compact = _compact_prompt(part.content)
                part = replace(part, content=compact) if compact != part.content else part
            elif kind == "ToolReturnPart":
                content = part.content if isinstance(part.content, str) else json.dumps(part.content, default=str)
                if len(content) > config.HISTORY_RESULT_CHARS:
                    part = replace(part, content=content[:config.HISTORY_RESULT_CHARS] + " …[shortened in memory]")
            parts.append(part)
        changed = any(new is not old for new, old in zip(parts, message.parts))
        out.append(replace(message, parts=parts) if changed else message)
    return out


@dataclass(frozen=True)
class Endpoint:
    """One model endpoint as chosen in the tab. The key is held in memory only."""

    provider: str
    kind: str
    model: str
    api_key: str = ""
    base_url: str = ""
    fallback_model: str = ""
    vision: bool = False  # may be shown a camera frame (the `look` side call)

    @classmethod
    def from_preset(cls, provider, model="", api_key="", base_url=""):
        """Fill the blanks from the provider preset: an empty model or base URL takes the preset's,
        an empty key takes the preset's environment variable (which may also be unset)."""
        preset = config.PROVIDERS[provider]
        key_env = preset.get("key_env")
        key = api_key.strip() or (os.environ.get(key_env, "") if key_env else "")
        return cls(
            provider=provider,
            kind=preset["kind"],
            model=model.strip() or preset["model"],
            api_key=key,
            base_url=base_url.strip() or preset.get("base_url", ""),
            fallback_model=preset.get("fallback_model", ""),
            vision=bool(preset.get("vision", False)),
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


def build_model(endpoint):
    """The endpoint's model, wrapped with its fallback (if the preset names one) so a rate-limited
    or unavailable primary rolls over transparently."""
    primary = _build_one(endpoint, endpoint.model)
    if not endpoint.fallback_model:
        return primary
    from pydantic_ai.models.fallback import FallbackModel

    return FallbackModel(primary, _build_one(endpoint, endpoint.fallback_model))


def build_agent(acceptor, cancel, on_call=None, model=None, endpoint=None, gate=None,
                vision_endpoint=None, image_size=None, profile=None, store=None):
    """`endpoint` is what the tab chose (the default preset when None). `model` overrides it — the
    GUI never passes it; the offline eval harness uses it to drive the very same agent against a
    scripted model."""
    from pydantic_ai import Agent
    from pydantic_ai.capabilities import ProcessHistory
    if model is None:
        model = build_model(endpoint or Endpoint.from_preset(config.DEFAULT_PROVIDER))
    # instructions (not system_prompt): applied fresh each run, not accumulated into the
    # message history we carry across turns. ProcessHistory compacts the older turns before
    # every model request, mid-turn ones included, and the compacted history is what the run
    # keeps, so an old turn is compacted once and stays so.
    agent = Agent(model, instructions=build_system_prompt(profile=profile),
                  tools=build_tools(acceptor, cancel, on_call, endpoint=endpoint, gate=gate,
                                    vision_endpoint=vision_endpoint, image_size=image_size, profile=profile,
                                    store=store),
                  capabilities=[ProcessHistory(compact_history)],
                  model_settings={"temperature": config.MODEL_TEMPERATURE},   # the most likely call, not a creative one
                  retries=config.TOOL_CALL_RETRIES)                            # a malformed call goes back to the model
    if config.CALLED_NOTHING_CHALLENGE:
        agent.output_validator(_challenge_a_reply_that_called_nothing(cancel))
    return agent


def _challenge_a_reply_that_called_nothing(cancel):
    """A small model answers "stop" with "I have stopped the microscope." and no call; whether it
    does so turns on the wording of an unrelated line of the manual, so no wording cures it. The
    one thing known without reading the reply is that the turn called nothing: such a reply goes
    back to the model once, with that fact. If it then calls a tool, the turn goes on and its new
    reply reports what happened. If it does not, the operator gets the first reply, word for word:
    asked to repeat itself a small model writes something shorter and worse, so it is asked for one
    word instead, at the cost of one short request on a turn that sends no command."""
    from pydantic_ai import ModelRetry
    first = {}                                        # run id -> the reply that was challenged

    def _check(ctx, output):
        turn = ctx.messages[_turn_starts(ctx.messages)[-1]:] if _turn_starts(ctx.messages) else ctx.messages
        called = any(type(part).__name__ == "ToolCallPart" for message in turn for part in getattr(message, "parts", []))
        if called or cancel.is_set():
            first.pop(ctx.run_id, None)
            return output
        if ctx.run_id in first:
            return first.pop(ctx.run_id)              # challenged, and still nothing called: as it was
        first[ctx.run_id] = output
        raise ModelRetry(config.CALLED_NOTHING_CHALLENGE)
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
    GUI disables input during a turn. Cancellation is at the tool boundary (dispatch_and_wait
    checks `cancel` before every dispatch) plus a `stop`: the agent can only touch the
    instrument through gated tools, so gating them + stopping the hardware halts it; the
    in-flight model call finishes harmlessly."""

    sig_reply = QtCore.pyqtSignal(str)
    sig_tool = QtCore.pyqtSignal(str, str)   # tool name, args-json
    sig_confirm = QtCore.pyqtSignal(str, str)  # a confirm-first command waits for Run / Cancel
    sig_served = QtCore.pyqtSignal(str)      # another model than the chosen one answered (the fallback)
    sig_error = QtCore.pyqtSignal(str)
    sig_done = QtCore.pyqtSignal()

    def __init__(self, acceptor):
        super().__init__()
        self._acceptor = acceptor
        self._endpoint = None  # set by configure() before the first turn
        self._vision_endpoint = None
        self._profile = config.DEFAULT_TOOL_PROFILE
        self._agent = None
        self._history = []
        self.store = SessionStore()      # every turn in full, for recall_turn and search_history
        self.cancel = threading.Event()
        self.gate = ConfirmationGate(on_ask=self.sig_confirm.emit)
        self.max_history_turns = config.MAX_HISTORY_TURNS  # the tab sets these
        self.look_image_size = config.LOOK_IMAGE_SIZE
        self.trace_folder = None                           # set by the tab: every turn is recorded there

    def configure(self, endpoint, vision_endpoint=None, profile=None):
        """Use another endpoint (and reader for frames, and tool profile) from the next turn on;
        the transcript history is kept. Called from the GUI thread only between turns."""
        self._endpoint = endpoint
        self._vision_endpoint = vision_endpoint
        self._profile = profile or config.DEFAULT_TOOL_PROFILE
        self._agent = None

    def set_profile(self, profile):
        """Switch tool sets between turns; the agent is rebuilt with the next message."""
        self._profile = profile
        self._agent = None

    def reset(self):
        """Forget the conversation (Clear all). Called between turns, like configure."""
        self._history = []
        self.store = SessionStore()
        self._agent = None               # the tools close over the store

    @QtCore.pyqtSlot(str)
    def run_turn(self, text):
        started = time.monotonic()
        try:
            self.cancel.clear()
            if self._agent is None:
                self._agent = build_agent(self._acceptor, self.cancel, on_call=self._emit_tool,
                                          endpoint=self._endpoint, gate=self.gate,
                                          vision_endpoint=self._vision_endpoint,
                                          image_size=lambda: self.look_image_size, profile=self._profile,
                                          store=self.store)
            # No whole-turn retry: FallbackModel already rolls a rate-limited/unavailable primary
            # over to the fallback within one run, and retrying the turn would re-stream (and re-run)
            # every tool call the first attempt already made.
            result = self._agent.run_sync(with_state(self._acceptor, text, self.store), message_history=self._history)
            self.store.finish(result.new_messages(), result.output)
            self._history = trim_history(result.all_messages(), self.max_history_turns)
            self._record(text, result.new_messages(), started, reply=result.output)
            chosen = self._endpoint.model if self._endpoint else None
            others = [name for name in served_models(result.new_messages()) if name != chosen]
            if others:   # the operator must know: another model is not the one they evaluated
                self.sig_served.emit(f"{', '.join(others)} answered this turn, standing in for {chosen}")
            self.sig_reply.emit(without_state_block(result.output))
        except Exception as error:
            logger.exception("AI Assistant turn failed")
            self._record(text, [], started, error=describe_error(error))
            self.sig_error.emit(describe_error(error))
        finally:
            self.sig_done.emit()

    def _record(self, prompt, messages, started, reply=None, error=None):
        """One line per turn in the traces folder, so what the assistant did can be read back
        later. Recording never fails a turn."""
        if not self.trace_folder:
            return
        endpoint = self._endpoint
        record = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "provider": endpoint.provider if endpoint else None,
            "model": endpoint.model if endpoint else None,
            "profile": self._profile,
            "prompt": prompt,
            "tools": turn_trace(messages),
            "served": served_models(messages),
            "reply": reply,
            "error": error,
            "seconds": round(time.monotonic() - started, 2),
        }
        try:
            write_trace(self.trace_folder, record)
        except OSError as problem:
            logger.warning("could not record the assistant turn in %s: %s", self.trace_folder, problem)

    def _emit_tool(self, name, args):
        """Called at the tool boundary (worker thread) as each command fires; the queued signal
        delivers it to the GUI so tool calls stream in live rather than all at the end of the turn."""
        self.sig_tool.emit(name, args)

    def interrupt(self):
        """The Cancel button: stop the assistant, not the microscope. Every further tool call in
        this turn returns 'cancelled' (dispatch_and_wait checks the flag), an open Run / Cancel
        question is answered Cancel, and the turn ends when the model next replies. Whatever the assistant already
        started keeps running; stopping the instrument is stop_microscope, a separate decision."""
        self.cancel.set()
        self.gate.answer(False)

