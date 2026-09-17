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

# Each command's args go on the wire as-is; the hint documents the shape and accept() enforces it.
_ARGS_SCHEMA = {"type": "object", "additionalProperties": True}


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
        return {"status": "cancelled"}                              # gate every call after Interrupt
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


def _tool_fn(acceptor, name, kind, cancel, on_call=None):
    """One passthrough tool body, closing over the command it dispatches. The keyword arguments
    ARE the command's wire args, so `move_absolute(targets={"x": 5000})` dispatches verbatim.
    `on_call` (if given) is invoked the moment the command fires, so the GUI can stream the
    activity live. Dispatch errors (out-of-range, busy) are returned to the model as data so it
    can self-correct, not raised."""
    def _call(**args) -> str:
        """See the tool description (the command's hint)."""
        if on_call is not None:
            try:
                on_call(name, json.dumps(args or {}))
            except Exception:
                pass
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


def build_tools(acceptor, cancel, on_call=None):
    """One passthrough tool per command, minus the prompt-only ones (get_manual is already in the
    system prompt). The tool list otherwise IS COMMANDS — never hand-maintained. Per-arg
    correctness comes from each command's accept() validator, the same one every transport uses.

    The schema is an OPEN object rather than one inferred from the wrapper's signature. Inferring
    it wrapped every command in an `args` envelope and set additionalProperties=false, so a model
    emitting the correct wire call — move_absolute {"targets": {"x": 5000}} — was rejected by the
    tool layer as `extra_forbidden` and never reached the dispatcher at all: every nested command
    was unreachable. from_schema also skips pydantic's own validation, which keeps accept() the
    single place a call can be refused instead of splitting rejection across two layers with two
    different error vocabularies."""
    from pydantic_ai import Tool
    return [
        Tool.from_schema(_tool_fn(acceptor, name, cmd.kind, cancel, on_call),
                         name=name, description=cmd.hint or name, json_schema=_ARGS_SCHEMA)
        for name, cmd in COMMANDS.items() if name not in _PROMPT_ONLY
    ]


def build_system_prompt(acceptor):
    """System prompt = the auto-generated get_manual reference (always in sync with COMMANDS,
    incl. the poll-get_progress contract) + a thin hand-written preamble (units, frames,
    safety tone)."""
    manual = acceptor.dispatch("get_manual", {})
    manual_text = manual if isinstance(manual, str) else json.dumps(manual, indent=2)
    preamble = (Path(__file__).parent / "assistant_manual.md").read_text(encoding="utf-8")
    return preamble + "\n\n# Microscope command reference\n\n" + manual_text


@dataclass(frozen=True)
class Endpoint:
    """One model endpoint as chosen in the tab. The key is held in memory only."""

    provider: str
    kind: str
    model: str
    api_key: str = ""
    base_url: str = ""
    fallback_model: str = ""

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
        )

    @property
    def needs_key(self):
        return self.kind != "openai-compatible"

    def describe(self):
        where = f" at {self.base_url}" if self.base_url else ""
        return f"{self.provider}, {self.model}{where}"


def _build_one(endpoint, model_id):
    if endpoint.kind == "google":
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(model_id, provider=GoogleProvider(api_key=endpoint.api_key))
    if endpoint.kind == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        return AnthropicModel(model_id, provider=AnthropicProvider(api_key=endpoint.api_key))
    # "openai" and any OpenAI-compatible server; a local server needs no key.
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


def build_agent(acceptor, cancel, on_call=None, model=None, endpoint=None):
    """`endpoint` is what the tab chose (the default preset when None). `model` overrides it — the
    GUI never passes it; the offline eval harness uses it to drive the very same agent against a
    scripted model."""
    from pydantic_ai import Agent
    if model is None:
        model = build_model(endpoint or Endpoint.from_preset(config.DEFAULT_PROVIDER))
    # instructions (not system_prompt): applied fresh each run, not accumulated into the
    # message history we carry across turns.
    return Agent(model, instructions=build_system_prompt(acceptor),
                 tools=build_tools(acceptor, cancel, on_call))


# --- In-process Acceptor lifecycle (called by Core's start_ai_assistant / stop_ai_assistant slots) ---
# Kept in this new module so the five Remote Control modules stay byte-identical to their shipped
# patch; the assistant is purely additive and reuses the shared Acceptor/dispatcher.
def start_assistant_for_core(core):
    """Build the in-process Acceptor the AI Assistant dispatches through, on the Core thread, and
    store it on ``core._assistant_acceptor``. Called from Core's start_ai_assistant slot, so the
    QObject takes its thread affinity from the Core thread. Fail-closed like a transport (same limit
    self-test) and refuses while a TCP/MCP transport is running, so the assistant does not start a
    second controller behind the operator's back. Returns the acceptor, or None on refusal /
    self-test failure (the tab reads the attribute and reports it)."""
    if getattr(core, "_remote_control", None) is not None:
        core._assistant_acceptor = None
        return None
    if getattr(core, "_assistant_acceptor", None) is None:
        ok, report = self_test(core)
        if not ok:
            logger.error("AI Assistant self-test failed: %s", "; ".join(report))
            core._assistant_acceptor = None
            return None
        core._assistant_acceptor = Acceptor(core)
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
    sig_error = QtCore.pyqtSignal(str)
    sig_done = QtCore.pyqtSignal()

    def __init__(self, acceptor, endpoint=None):
        super().__init__()
        self._acceptor = acceptor
        self._endpoint = endpoint
        self._agent = None
        self._history = []
        self.cancel = threading.Event()

    def configure(self, endpoint):
        """Use another endpoint from the next turn on; the transcript history is kept. Called from
        the GUI thread only between turns (the tab disables setup while a turn runs)."""
        self._endpoint = endpoint
        self._agent = None

    @QtCore.pyqtSlot(str)
    def run_turn(self, text):
        try:
            self.cancel.clear()
            if self._agent is None:
                self._agent = build_agent(self._acceptor, self.cancel, on_call=self._emit_tool,
                                          endpoint=self._endpoint)
            # No whole-turn retry: FallbackModel already rolls a rate-limited/unavailable primary
            # over to the fallback within one run, and retrying the turn would re-stream (and re-run)
            # every tool call the first attempt already made.
            result = self._agent.run_sync(text, message_history=self._history)
            self._history = result.all_messages()
            self.sig_reply.emit(result.output)
        except Exception as error:
            logger.exception("AI Assistant turn failed")
            self.sig_error.emit(describe_error(error))
        finally:
            self.sig_done.emit()

    def _emit_tool(self, name, args):
        """Called at the tool boundary (worker thread) as each command fires; the queued signal
        delivers it to the GUI so tool calls stream in live rather than all at the end of the turn."""
        self.sig_tool.emit(name, args)

    def interrupt(self):
        """Stop a runaway turn: gate further dispatches (dispatch_and_wait checks cancel) and
        halt the hardware now.

        The stop is dispatched from a helper thread, not from the caller's. The GUI calls this
        from its Interrupt button, and a dispatch waits up to DISPATCH_TIMEOUT_SEC for the Core
        thread to answer: issuing it on the GUI thread would freeze the whole application on the
        one button meant for emergencies. Returns the helper thread so a caller that needs the
        stop to have been issued (tests, shutdown) can join it.
        """
        self.cancel.set()

        def issue_stop():
            try:
                self._acceptor.dispatch("stop", {})
            except Exception:
                pass

        stopper = threading.Thread(target=issue_stop, name="ai-assistant-interrupt", daemon=True)
        stopper.start()
        return stopper
