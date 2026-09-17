"""AI Assistant worker logic, from source, under the Qt-free shim in conftest.

Covers the completion wrapper (dispatch_and_wait), the tool builder, and the worker's turn,
retry, tool-surfacing, and interrupt behaviour with a fake agent — no live model, no hardware.
Real-thread ordering is left to the real-PyQt smoke test, matching the Remote Control split.
"""
import json
import threading
import time

import pytest

from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src.mesoSPIM_AiAssistent import (
    AssistantWorker, Endpoint, dispatch_and_wait, start_assistant_for_core, stop_assistant_for_core)
from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import READ, WAIT, COMPLETED
from mesoSPIM.test.remote_control.support.fakes import RecordingCore


# --- dispatch_and_wait: the completion wrapper ---

class FakeAcceptor:
    """Scripts dispatch() with the REAL nesting: status/id live under "operation". A WAIT op
    reports 'processing' then 'completed' after `flip_after` get_progress polls."""

    def __init__(self, flip_after=2):
        self.calls = []
        self._polls = 0
        self._flip_after = flip_after

    def dispatch(self, name, args):
        self.calls.append((name, args))
        if name == "get_progress":
            self._polls += 1
            status = COMPLETED if self._polls >= self._flip_after else "processing"
            return {"operation": {"status": status, "id": "op-000001"}}
        return {"accepted": True, "operation": {"id": "op-000001", "status": "processing"}}


class _Cfg:
    POLL_INTERVAL_S = 0.0
    WAIT_CAP_S = 5


def test_read_returns_immediately():
    acc = FakeAcceptor()
    dispatch_and_wait(acc, "get_state", {}, READ, threading.Event(), _Cfg)
    assert acc.calls == [("get_state", {})]                       # no polling for a READ


def test_wait_blocks_until_completed():
    acc = FakeAcceptor(flip_after=3)
    out = dispatch_and_wait(acc, "move_absolute", {"targets": {"x": 12000}}, WAIT, threading.Event(), _Cfg)
    assert out["status"] == COMPLETED
    assert [c[0] for c in acc.calls].count("get_progress") == 3


def test_cancel_before_dispatch_actuates_nothing():
    acc = FakeAcceptor()
    cancel = threading.Event()
    cancel.set()
    out = dispatch_and_wait(acc, "move_absolute", {"targets": {"x": 1}}, WAIT, cancel, _Cfg)
    assert out["status"] == "cancelled"
    assert acc.calls == []                                         # gated before any dispatch


def test_wait_returns_still_running_past_cap():
    acc = FakeAcceptor(flip_after=10**9)                          # genuinely never completes

    class Cfg:
        POLL_INTERVAL_S = 0.0
        WAIT_CAP_S = 0.05

    out = dispatch_and_wait(acc, "run_acquisition_list", {}, WAIT, threading.Event(), Cfg)
    assert out["status"] == "still_running"


def test_build_tools_covers_commands_except_prompt_only():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools, _PROMPT_ONLY
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS
    tools = build_tools(FakeAcceptor(), threading.Event())
    names = {t.name for t in tools}
    assert len(tools) == len(COMMANDS) - len(_PROMPT_ONLY)
    assert "get_manual" not in names                            # in the system prompt, not a tool
    assert "move_absolute" in names


# --- the worker: turn, retry, tool-surfacing, interrupt (fake agent) ---

class FakeResult:
    def __init__(self, output):
        self.output = output

    def all_messages(self):
        return ["history"]


class FakeAgent:
    def __init__(self, results=None, errors=None):
        self._results = list(results or [])
        self._errors = list(errors or [])
        self.runs = 0

    def run_sync(self, text, message_history=None):
        self.runs += 1
        self.last_prompt = text
        if self._errors:
            error = self._errors.pop(0)
            if error is not None:
                raise error
        return self._results.pop(0) if self._results else FakeResult("ok")


def _collect(signal):
    got = []
    signal.connect(lambda *a: got.append(a[0] if len(a) == 1 else a))
    return got


def test_run_turn_emits_reply(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent([FakeResult("moved")]))
    replies = _collect(worker.sig_reply)
    dones = _collect(worker.sig_done)
    worker.run_turn("go")
    assert replies == ["moved"]
    assert len(dones) == 1


def test_tool_fn_streams_call_before_dispatch():
    acc = FakeAcceptor()
    seen = []
    tool = ai._tool_fn(acc, "get_state", READ, threading.Event(), on_call=lambda n, a: seen.append((n, a)))
    out = tool(foo=1)                                           # keywords ARE the wire args
    assert seen == [("get_state", json.dumps({"foo": 1}))]      # surfaced live, at the tool boundary
    assert ("get_state", {"foo": 1}) in acc.calls               # then dispatched
    assert "accepted" in out


def test_validation_error_carries_the_configured_vocabulary():
    """A type-only refusal ("'zoom' must be a string") tells the model nothing about which zooms
    exist, so it asks the operator instead of retrying. The vocabulary rides along on every
    validation failure; other failures stay lean."""
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import ValidationError

    class Refusing:
        def __init__(self, error):
            self.error = error
            self.calls = []

        def dispatch(self, name, args):
            self.calls.append((name, args))
            if name == "get_config":
                return {"zooms": ["1x", "2x"]}
            raise self.error

    acc = Refusing(ValidationError("'zoom' must be a string"))
    out = json.loads(ai._tool_fn(acc, "set_zoom", READ, threading.Event())(zoom=2))
    assert out["error"]["configured_options"] == {"zooms": ["1x", "2x"]}
    assert ("get_config", {}) in acc.calls

    busy = Refusing(RuntimeError("boom"))
    lean = json.loads(ai._tool_fn(busy, "set_zoom", READ, threading.Event())(zoom=2))
    assert "configured_options" not in lean["error"]
    assert ("get_config", {}) not in busy.calls               # only a value refusal pays for the read


def test_run_turn_error_emits_sig_error(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent(errors=[RuntimeError("boom")]))
    errors = _collect(worker.sig_error)
    dones = _collect(worker.sig_done)
    worker.run_turn("go")
    assert errors and "boom" in errors[0]
    assert len(dones) == 1                                        # sig_done fires even on failure


def test_error_message_names_the_type_even_when_blank():
    """An httpx read timeout stringifies to "", which rendered as a bare "error —" in the tab and
    told the operator nothing. The type always leads."""
    class Blank(Exception):
        def __str__(self):
            return "   "

    assert ai.describe_error(Blank()) == "Blank"
    assert ai.describe_error(ValueError("bad axis")) == "ValueError: bad axis"


def test_run_turn_reports_a_blank_error_with_its_type(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    monkeypatch.setattr(ai, "build_agent",
                        lambda a, c, **k: FakeAgent(errors=[TimeoutError()]))
    errors = _collect(worker.sig_error)
    worker.run_turn("go")
    assert errors == ["TimeoutError"]


def test_interrupt_sets_cancel_and_stops():
    acc = FakeAcceptor()
    worker = AssistantWorker(acc)
    stopper = worker.interrupt()
    assert worker.cancel.is_set()
    stopper.join(5)
    assert not stopper.is_alive()
    assert ("stop", {}) in acc.calls


def test_interrupt_returns_without_waiting_for_a_busy_core():
    """The Interrupt button runs on the GUI thread. A dispatch waits up to DISPATCH_TIMEOUT_SEC
    for Core, so the stop must be issued from another thread or the GUI freezes on the one
    control meant for emergencies."""
    release = threading.Event()
    reached = threading.Event()

    class BusyAcceptor(FakeAcceptor):
        def dispatch(self, name, args):
            reached.set()
            assert release.wait(5), "the stop dispatch was never released"
            return super().dispatch(name, args)

    acc = BusyAcceptor()
    worker = AssistantWorker(acc)
    started = time.monotonic()
    stopper = worker.interrupt()
    assert time.monotonic() - started < 1.0           # returned while Core is still "busy"
    assert worker.cancel.is_set()                      # further tool calls are gated at once
    assert reached.wait(5)                             # the stop was still issued, elsewhere
    assert stopper.is_alive() and ("stop", {}) not in acc.calls
    release.set()
    stopper.join(5)
    assert ("stop", {}) in acc.calls


# --- Acceptor lifecycle for Core (start/stop_assistant_for_core) ---

def test_start_assistant_builds_and_reuses_one_acceptor():
    core = RecordingCore()
    core._remote_control = None
    acceptor = start_assistant_for_core(core)                 # passes self_test, builds an Acceptor
    assert acceptor is not None
    assert core._assistant_acceptor is acceptor
    assert start_assistant_for_core(core) is acceptor         # idempotent: one Acceptor per session


def test_start_assistant_refused_while_transport_runs():
    core = RecordingCore()
    core._remote_control = object()                           # a transport holds the session
    assert start_assistant_for_core(core) is None
    assert core._assistant_acceptor is None


def test_stop_assistant_releases_the_acceptor():
    core = RecordingCore()
    core._remote_control = None
    start_assistant_for_core(core)
    stop_assistant_for_core(core)
    assert core._assistant_acceptor is None


# --- the endpoint chosen in the tab ---

def test_endpoint_prefers_the_typed_key_over_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    typed = Endpoint.from_preset("Gemini", api_key="  typed  ")
    assert (typed.kind, typed.api_key, typed.model) == ("google", "typed", "gemini-3.5-flash-lite")
    assert typed.fallback_model == "gemini-3.1-flash-lite"
    assert Endpoint.from_preset("Gemini").api_key == "from-env"


def test_endpoint_without_any_key_is_detectable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    endpoint = Endpoint.from_preset("Anthropic", model="claude-opus-5")
    assert endpoint.needs_key and endpoint.api_key == ""
    assert endpoint.model == "claude-opus-5"                       # a typed model wins over the preset


def test_local_endpoint_needs_a_base_url_not_a_key():
    endpoint = Endpoint.from_preset("OpenAI-compatible server", base_url="http://box:8000/v1")
    assert not endpoint.needs_key
    assert endpoint.base_url == "http://box:8000/v1"


def test_configure_rebuilds_the_agent_on_the_next_turn_and_keeps_history(monkeypatch):
    built = []

    def fake_build(a, c, **k):
        built.append(k["endpoint"])
        return FakeAgent([FakeResult("one"), FakeResult("two")])

    monkeypatch.setattr(ai, "build_agent", fake_build)
    worker = AssistantWorker(FakeAcceptor())
    worker.configure(Endpoint.from_preset("OpenAI", api_key="k1"))
    worker.run_turn("first")
    other = Endpoint.from_preset("Anthropic", api_key="k2")
    worker.configure(other)
    worker.run_turn("second")
    assert [e.provider for e in built] == ["OpenAI", "Anthropic"]
    assert worker._history                                          # the transcript survived the switch


# --- the state block, and looking through a side call ---

def test_endpoint_vision_comes_from_the_preset():
    assert Endpoint.from_preset("Gemini", api_key="k").vision is True
    assert Endpoint.from_preset("OpenAI-compatible server").vision is False
    assert Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u").vision is False


def test_with_state_appends_the_snapshot_or_nothing():
    class _Acc:
        def dispatch(self, name, args):
            assert name == "get_snapshot"
            return {"state": "idle", "position": {"x": 1.0}}

    text = ai.with_state(_Acc(), "move x by 5")
    assert text.startswith("move x by 5\n\n<microscope_state>\n")
    assert '"position": {"x": 1.0}' in text and text.endswith("</microscope_state>")

    class _Broken:
        def dispatch(self, name, args):
            raise RuntimeError("no")

    assert ai.with_state(_Broken(), "hello") == "hello"


def test_run_turn_sends_the_state_block(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    agent = FakeAgent([FakeResult("ok")])
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: agent)
    worker.run_turn("where is the stage?")
    assert agent.last_prompt.startswith("where is the stage?\n\n<microscope_state>")


def _real_acceptor():
    from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor
    core = RecordingCore()
    return Acceptor(core), core


def test_look_gives_a_text_only_model_the_numbers_and_no_image():
    acceptor, core = _real_acceptor()
    shown = []
    endpoint = Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u")
    result = ai.look(acceptor, endpoint, "is it in focus?", True, threading.Event(), on_frame=shown.append)
    assert result["available"] and "answer" not in result and "cannot see" in result["note"]
    assert result["stats"]["shape"] == [64, 96] and result["stats"]["bright_fraction"] > 0
    assert shown == []                                              # nothing was rendered for nobody
    assert [c[0] for c in core.calls() if c[0] == "snap"] == ["snap"]


def test_look_asks_the_vision_model_in_a_side_call(monkeypatch):
    acceptor, _ = _real_acceptor()
    asked, shown = [], []
    monkeypatch.setattr(ai, "vision_answer", lambda endpoint, image, question, stats: asked.append((question, image["format"])) or "sample centred")
    endpoint = Endpoint.from_preset("Gemini", api_key="k")
    result = ai.look(acceptor, endpoint, "is the sample centred?", True, threading.Event(), on_frame=shown.append)
    assert result["answer"] == "sample centred"
    assert asked == [("is the sample centred?", "png")]
    assert len(shown) == 1 and shown[0]                             # the operator sees the same frame


def test_look_reuses_the_last_frame_when_asked(monkeypatch):
    acceptor, core = _real_acceptor()
    endpoint = Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u")
    assert ai.look(acceptor, endpoint, "q", False, threading.Event())["available"] is False
    ai.look(acceptor, endpoint, "q", True, threading.Event())
    ai.look(acceptor, endpoint, "q", False, threading.Event())
    assert [c[0] for c in core.calls() if c[0] == "snap"] == ["snap"]   # one snap for two looks


def test_vision_error_does_not_lose_the_numbers(monkeypatch):
    acceptor, _ = _real_acceptor()
    monkeypatch.setattr(ai, "vision_answer", lambda *a: (_ for _ in ()).throw(TimeoutError()))
    result = ai.look(acceptor, Endpoint.from_preset("Gemini", api_key="k"), "q", True, threading.Event())
    assert result["vision_error"] == "TimeoutError" and result["stats"]


def test_vision_answer_is_one_stateless_call_with_the_image(monkeypatch):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.messages import BinaryContent, ModelResponse, TextPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    seen = {}

    def model_function(messages, info):
        seen["messages"] = len(messages)
        prompt = next(p for p in messages[-1].parts if isinstance(p, UserPromptPart))
        seen["text"] = prompt.content[0]
        seen["image"] = any(isinstance(c, BinaryContent) and c.media_type == "image/png" for c in prompt.content)
        return ModelResponse(parts=[TextPart("looks fine")])

    monkeypatch.setattr(ai, "build_model", lambda endpoint: FunctionModel(model_function))
    import base64
    image = {"format": "png", "base64": base64.b64encode(b"\x89PNG fake").decode()}
    answer = ai.vision_answer(Endpoint.from_preset("Gemini", api_key="k"), image, "in focus?", {"focus_measure": 0.5})
    assert answer == "looks fine"
    assert seen["messages"] == 1 and seen["image"] is True         # no history, the frame attached
    assert seen["text"].startswith("in focus?") and "focus_measure" in seen["text"]


def test_build_tools_adds_look_only_with_an_endpoint():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    without = {t.name for t in build_tools(FakeAcceptor(), threading.Event())}
    with_endpoint = {t.name for t in build_tools(FakeAcceptor(), threading.Event(), endpoint=Endpoint.from_preset("Gemini", api_key="k"))}
    assert "look" not in without and "look" in with_endpoint
    assert with_endpoint - without == {"look"}


# --- the confirmation gate ---

def test_gate_waits_for_the_operator_and_returns_the_answer():
    asked = []
    gate = ai.ConfirmationGate(on_ask=lambda name, args: asked.append((name, args)), timeout=5)
    results = []
    thread = threading.Thread(target=lambda: results.append(gate.ask("load_sample", {})))
    thread.start()
    deadline = time.monotonic() + 5
    while not asked and time.monotonic() < deadline:
        time.sleep(0.01)
    assert asked == [("load_sample", "{}")]
    assert not results                                              # still waiting
    gate.answer(True)
    thread.join(5)
    assert results == [True]


def test_gate_times_out_as_cancel():
    gate = ai.ConfirmationGate(on_ask=lambda name, args: None, timeout=0.05)
    assert gate.ask("run_acquisition_list", {}) is False


def test_confirm_first_tool_is_refused_without_the_operator():
    acc = FakeAcceptor()
    gate = ai.ConfirmationGate(on_ask=lambda name, args: None, timeout=0.01)
    fn = ai._tool_fn(acc, "run_acquisition_list", WAIT, threading.Event(), gate=gate)
    out = json.loads(fn())
    assert out["error"]["code"] == "refused" and "run_acquisition_list" in out["error"]["message"]
    assert acc.calls == []                                          # never dispatched


def test_confirm_first_tool_runs_after_run(monkeypatch):
    acc = FakeAcceptor(flip_after=1)
    gate = ai.ConfirmationGate(on_ask=lambda name, args: gate.answer(True), timeout=1)
    fn = ai._tool_fn(acc, "load_sample", WAIT, threading.Event(), gate=gate)
    out = json.loads(fn())
    assert out["status"] == COMPLETED and acc.calls[0] == ("load_sample", {})


def test_ordinary_tools_do_not_ask():
    acc = FakeAcceptor()
    gate = ai.ConfirmationGate(on_ask=lambda name, args: pytest.fail("asked for a read"), timeout=1)
    ai._tool_fn(acc, "get_state", READ, threading.Event(), gate=gate)()
    assert acc.calls == [("get_state", {})]


def test_interrupt_cancels_an_open_question():
    worker = AssistantWorker(FakeAcceptor())
    results = []
    thread = threading.Thread(target=lambda: results.append(worker.gate.ask("unload_sample", {})))
    thread.start()
    time.sleep(0.05)
    stopper = worker.interrupt()
    thread.join(5)
    stopper.join(5)
    assert results == [False]
