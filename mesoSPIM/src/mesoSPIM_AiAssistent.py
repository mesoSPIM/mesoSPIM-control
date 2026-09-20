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

from .mesoSPIM_RemoteControl_Dispatcher import COMMANDS, WAIT, COMPLETED, FAILED, error_info
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
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


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


def _tool_fn(acceptor, name, kind, cancel, on_call=None, gate=None):
    """One passthrough tool body, closing over the command it dispatches. The keyword arguments
    ARE the command's wire args, so `move_absolute(targets={"x": 5000})` dispatches verbatim.
    `on_call` (if given) is invoked the moment the command fires, so the GUI can stream the
    activity live. Dispatch errors (out-of-range, busy) are returned to the model as data so it
    can self-correct, not raised. A confirm-first command first asks the operator through `gate`."""
    def _call(**args) -> str:
        """See the tool description (the command's hint)."""
        if on_call is not None:
            try:
                on_call(name, json.dumps(args or {}))
            except Exception:
                pass
        if cancel.is_set():
            return json.dumps({"status": "cancelled"})                   # never ask after Cancel
        if gate is not None and name in config.CONFIRM_FIRST and not gate.ask(name, args):
            return json.dumps({"error": {"code": "refused", "message": f"the operator did not confirm {name}"}})
        try:
            return json.dumps(dispatch_and_wait(acceptor, name, args, kind, cancel))
        except Exception as error:
            code, message = error_info(error)
            failure = {"error": {"code": code, "message": message}}
            if code == "validation":
                options = _configured_options(acceptor)
                if options is not None:
                    failure["error"]["configured_options"] = options
            return json.dumps(failure)
    return _call


def look(acceptor, endpoint, question, snap, cancel, on_frame=None, image_size=None):
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
    if image is not None and on_frame is not None:
        on_frame(image["base64"])
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
        instructions="You are looking at one frame from a light-sheet microscope camera, contrast-stretched "
                     "to 8 bit for display. Answer the operator's question about it in a few sentences. "
                     "The display cannot show exposure: it is stretched to the frame's own range, so a dim "
                     "frame looks as bright as a good one. Judge saturation and underexposure from the "
                     "numbers only: saturated_fraction above a few percent is saturated; a max below about "
                     "a tenth of full_scale is underexposed. Judge shapes, positions, focus and artefacts "
                     "from the picture.",
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


def build_tools(acceptor, cancel, on_call=None, endpoint=None, on_frame=None, gate=None, vision_endpoint=None,
                image_size=None, profile=None):
    """One passthrough tool per offered command (see offered_commands). The tool list is derived
    from COMMANDS and the profile — never hand-maintained.

    Each tool publishes the command's own JSON schema (the one MCP tools/list serves), so the model
    sees the argument names, types and ranges. from_schema skips pydantic's validation of the call,
    which keeps accept() the single place a call can be refused, with one error vocabulary. In the
    Regular profile a straddling command is offered with a narrowed schema and refuses the rest."""
    from pydantic_ai import Tool
    regular = (profile or config.DEFAULT_TOOL_PROFILE) == "Regular"
    narrow = config.REGULAR_ARGS if regular else {}
    tools = []
    for cmd in offered_commands(profile):
        fn = _tool_fn(acceptor, cmd.name, cmd.kind, cancel, on_call, gate)
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
        tools.append(Tool.from_schema(fn, name=cmd.name, description=cmd.hint or cmd.name, json_schema=schema))
    if endpoint is not None:
        eyes = vision_endpoint or endpoint  # a dedicated reader, or the main model when it can see

        def _look(question="", snap=True) -> str:
            if on_call is not None:
                on_call("look", json.dumps({"question": question, "snap": snap}))
            size = image_size() if callable(image_size) else image_size  # a callable reads a live setting
            try:
                return json.dumps(look(acceptor, eyes, question, snap, cancel, on_frame, size))
            except Exception as error:  # busy, shutting down: data for the model, like every tool
                code, message = error_info(error)
                return json.dumps({"error": {"code": code, "message": message}})

        tools.append(Tool.from_schema(
            _look, name="look", json_schema=_LOOK_SCHEMA,
            description="Take a snap (or reuse the last frame with snap=false) and describe it: numbers about "
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


def with_state(acceptor, text):
    """The current microscope readout, then the operator's message: data the model can rely on
    instead of calling reads first, with the operator's words last, where a model weighs text
    most, so that a note in a folder name inside the readout does not read as the request. Sent
    without the block if the readout fails."""
    try:
        snapshot = acceptor.dispatch("get_snapshot", {})
    except Exception:
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
    starts = [
        index for index, message in enumerate(messages)
        if type(getattr(message, "parts", [None])[0]).__name__ == "UserPromptPart"
    ]
    if len(starts) <= max_turns:
        return list(messages)
    return list(messages[starts[-max_turns]:])


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


def build_agent(acceptor, cancel, on_call=None, model=None, endpoint=None, on_frame=None, gate=None,
                vision_endpoint=None, image_size=None, profile=None):
    """`endpoint` is what the tab chose (the default preset when None). `model` overrides it — the
    GUI never passes it; the offline eval harness uses it to drive the very same agent against a
    scripted model."""
    from pydantic_ai import Agent
    if model is None:
        model = build_model(endpoint or Endpoint.from_preset(config.DEFAULT_PROVIDER))
    # instructions (not system_prompt): applied fresh each run, not accumulated into the
    # message history we carry across turns.
    return Agent(model, instructions=build_system_prompt(profile=profile),
                 tools=build_tools(acceptor, cancel, on_call, endpoint=endpoint, on_frame=on_frame, gate=gate,
                                   vision_endpoint=vision_endpoint, image_size=image_size, profile=profile))


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
    sig_frame = QtCore.pyqtSignal(str)       # base64 PNG the `look` tool showed the vision model
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

    @QtCore.pyqtSlot(str)
    def run_turn(self, text):
        started = time.monotonic()
        try:
            self.cancel.clear()
            if self._agent is None:
                self._agent = build_agent(self._acceptor, self.cancel, on_call=self._emit_tool,
                                          endpoint=self._endpoint, on_frame=self.sig_frame.emit, gate=self.gate,
                                          vision_endpoint=self._vision_endpoint,
                                          image_size=lambda: self.look_image_size, profile=self._profile)
            # No whole-turn retry: FallbackModel already rolls a rate-limited/unavailable primary
            # over to the fallback within one run, and retrying the turn would re-stream (and re-run)
            # every tool call the first attempt already made.
            result = self._agent.run_sync(with_state(self._acceptor, text), message_history=self._history)
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

