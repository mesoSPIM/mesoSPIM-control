"""AI Assistant worker logic, from source, under the Qt-free shim in conftest.

Covers the completion wrapper (dispatch_and_wait), the tool builder, and the worker's turn,
retry, tool-surfacing, and interrupt behaviour with a fake agent — no live model, no hardware.
Real-thread ordering is left to the real-PyQt smoke test, matching the Remote Control split.
"""
import json
import os
import threading
import types
import time

import pytest

from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src.mesoSPIM_AiAssistent import (
    AssistantWorker, Endpoint, dispatch_and_wait, start_assistant_for_core, stop_assistant_for_core)
from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS, READ, WAIT, COMPLETED
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
    tools = build_tools(FakeAcceptor(), threading.Event(), profile="Full")
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

    def new_messages(self):
        return []


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


def test_interrupt_stops_the_assistant_not_the_microscope():
    acc = FakeAcceptor()
    worker = AssistantWorker(acc)
    worker.interrupt()
    assert worker.cancel.is_set()
    assert acc.calls == []                                         # no hardware call at all


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
    assert "Stop the Remote Control transport" in core._assistant_refusal


def test_start_assistant_names_a_failed_self_test(monkeypatch):
    from mesoSPIM.src import mesoSPIM_RemoteControl_Commands as commands
    from mesoSPIM.src import mesoSPIM_RemoteControl_Config as rc_config
    # Regress the zeroed-frame limit check, as the commands suite does, so the self-test refuses.
    monkeypatch.setattr(commands, "axis_offsets", lambda core: {axis: 0.0 for axis in rc_config.AXES})
    core = RecordingCore()
    core._remote_control = None
    assert start_assistant_for_core(core) is None
    assert core._assistant_acceptor is None
    assert core._assistant_refusal.startswith("AI Assistant self-test failed") and "zeroed-frame" in core._assistant_refusal


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
    assert typed.fallback_model == ""                              # no silent stand-in (see the preset)
    assert Endpoint.from_preset("Gemini").api_key == "from-env"


def test_endpoint_without_any_key_is_detectable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    endpoint = Endpoint.from_preset("Anthropic", model="claude-opus-5")
    assert endpoint.needs_key and endpoint.api_key == ""
    assert endpoint.model == "claude-opus-5"                       # a typed model wins over the preset


def test_local_endpoint_needs_a_base_url_not_a_key():
    endpoint = Endpoint.from_preset("OpenAI-style", base_url="http://box:8000/v1")
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
    assert Endpoint.from_preset("OpenAI-style").vision is False
    assert Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u").vision is False


def test_with_state_appends_the_snapshot_or_nothing():
    class _Acc:
        def dispatch(self, name, args):
            assert name == "get_snapshot"
            return {"state": "idle", "position": {"x": 1.0}}

    text = ai.with_state(_Acc(), "move x by 5")
    assert text.startswith("<microscope_state>\n") and text.endswith("</microscope_state>\n\nmove x by 5")
    assert '"position": {"x": 1.0}' in text                       # the operator's words come last

    class _Broken:
        def dispatch(self, name, args):
            raise RuntimeError("no")

    assert ai.with_state(_Broken(), "hello") == "hello"


def test_run_turn_sends_the_state_block(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    agent = FakeAgent([FakeResult("ok")])
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: agent)
    worker.run_turn("where is the stage?")
    assert agent.last_prompt.startswith("<microscope_state>") and agent.last_prompt.endswith("where is the stage?")


def test_a_state_block_a_model_copied_into_its_reply_is_stripped_for_the_operator(monkeypatch):
    copied = "Moved x to 20000.\n\n<microscope_state>\n{\"state\": \"idle\"}\n</microscope_state>"
    assert ai.without_state_block(copied) == "Moved x to 20000."
    assert ai.without_state_block("Plain reply.") == "Plain reply." and ai.without_state_block("") == ""
    worker = AssistantWorker(FakeAcceptor())
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent([FakeResult(copied)]))
    replies = []
    worker.sig_reply.connect(replies.append)
    worker.run_turn("move x to 20000")
    assert replies == ["Moved x to 20000."]


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
    gate = ai.ConfirmationGate(on_ask=lambda name, args: asked.append((name, args)))
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


def test_gate_waits_until_answered_not_a_clock():
    gate = ai.ConfirmationGate(on_ask=lambda name, args: None)
    results = []
    thread = threading.Thread(target=lambda: results.append(gate.ask("unload_sample", {})), daemon=True)
    thread.start()
    time.sleep(0.2)
    assert thread.is_alive() and results == []                     # still waiting, no deadline
    gate.answer(False)
    thread.join(5)
    assert results == [False]


def test_confirm_first_tool_is_refused_when_the_operator_cancels():
    acc = FakeAcceptor()
    gate = ai.ConfirmationGate(on_ask=lambda name, args: gate.answer(False))
    fn = ai._tool_fn(acc, "unload_sample", WAIT, threading.Event(), gate=gate)
    out = json.loads(fn())
    assert out["error"]["code"] == "refused" and "unload_sample" in out["error"]["message"]
    assert acc.calls == []                                          # never dispatched


def test_confirm_first_tool_is_not_asked_after_cancel():
    acc = FakeAcceptor()
    asked = []
    gate = ai.ConfirmationGate(on_ask=lambda name, args: asked.append(name))
    cancel = threading.Event()
    cancel.set()
    fn = ai._tool_fn(acc, "load_sample", WAIT, cancel, gate=gate)
    assert json.loads(fn()) == {"status": "cancelled"}
    assert asked == [] and acc.calls == []                           # no Run / Cancel bar, no dispatch


def test_confirm_first_tool_runs_after_run():
    acc = FakeAcceptor(flip_after=1)
    gate = ai.ConfirmationGate(on_ask=lambda name, args: gate.answer(True))
    fn = ai._tool_fn(acc, "load_sample", WAIT, threading.Event(), gate=gate)
    out = json.loads(fn())
    assert out["status"] == COMPLETED and acc.calls[0] == ("load_sample", {})


def test_only_the_three_stage_moves_ask():
    assert set(ai.config.CONFIRM_FIRST) == {"load_sample", "unload_sample", "preview_acquisition"}
    acc = FakeAcceptor(flip_after=1)
    gate = ai.ConfirmationGate(on_ask=lambda name, args: pytest.fail(f"asked for {name}"))
    for name, kind in (("get_state", READ), ("run_acquisition_list", WAIT), ("time_lapse_start", WAIT)):
        ai._tool_fn(acc, name, kind, threading.Event(), gate=gate)()
    assert [c[0] for c in acc.calls if c[0] != "get_progress"] == ["get_state", "run_acquisition_list", "time_lapse_start"]


def test_interrupt_cancels_an_open_question():
    worker = AssistantWorker(FakeAcceptor())
    results = []
    thread = threading.Thread(target=lambda: results.append(worker.gate.ask("unload_sample", {})))
    thread.start()
    time.sleep(0.05)
    worker.interrupt()
    thread.join(5)
    assert results == [False]


# --- schemas on the tools, the prompt, the history cap ---

def test_tools_publish_each_commands_schema():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS
    for tool in build_tools(FakeAcceptor(), threading.Event(), profile="Full"):
        if tool.name in ai.config.ROWS_BY_REFERENCE:                 # rows by reference to set_acquisition_list
            assert tool.function_schema.json_schema == ai._rows_by_reference(COMMANDS[tool.name].schema)
        else:
            assert tool.function_schema.json_schema == COMMANDS[tool.name].schema


def test_a_scripted_model_can_call_every_tool_through_its_schema(monkeypatch):
    """pydantic-ai's TestModel calls every tool once with arguments generated from the schema; a
    schema the tool layer cannot serve, or a wrapper that rejects a well-formed call, shows up as a
    retry prompt or an exception here."""
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor

    monkeypatch.setattr(ai.config, "WAIT_CAP_S", 0.01)             # the fake core never completes a WAIT
    monkeypatch.setattr(ai.config, "POLL_INTERVAL_S", 0.0)
    acceptor = Acceptor(RecordingCore())
    endpoint = Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u")
    tools = build_tools(acceptor, threading.Event(), endpoint=endpoint, profile="Full")
    result = Agent(TestModel(), tools=tools, instructions="test").run_sync("do everything")
    parts = [p for m in result.all_messages() for p in m.parts]
    called = {p.tool_name for p in parts if type(p).__name__ == "ToolCallPart"}
    assert called == {t.name for t in tools}
    assert not [p for p in parts if type(p).__name__ == "RetryPromptPart"]


def test_system_prompt_is_the_preamble_plus_the_commands_by_kind():
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS
    prompt = ai.build_system_prompt(profile="Full")          # every command
    assert prompt.startswith("You control a mesoSPIM")
    commands = prompt.split("# Commands")[1]
    by_kind = {line.split(":")[0].strip("- "): line.split(":", 1)[1] for line in commands.splitlines() if line.startswith("- ")}
    assert set(by_kind) == {"reads, which change nothing", "actions, which return at once",
                            "waits, which return when the instrument is done", "emergency commands, never gated"}
    for name, cmd in COMMANDS.items():
        if name != "get_manual":
            assert any(name in names for label, names in by_kind.items() if label.startswith(cmd.kind[:4]))
    assert "get_manual" not in commands and "in:" not in commands   # the hints live in the tool descriptions
    assert len(prompt) < 8000                                        # small enough for a local model's context


def test_the_prompt_and_the_tools_stay_small_enough_for_a_local_model():
    """A local model with an 8K context needs room for the conversation: the Regular prompt plus
    all tool schemas stay under 17,500 characters, roughly 4,700 tokens."""
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    tools = build_tools(FakeAcceptor(), threading.Event(), profile="Regular")
    schemas = sum(len(json.dumps(t.function_schema.json_schema)) + len(t.description or "") for t in tools)
    assert len(ai.build_system_prompt(profile="Regular")) + schemas < 17500
    by_name = {t.name: t.function_schema.json_schema for t in tools}
    rows = by_name["set_acquisition_list"]["properties"]["acquisitions"]["items"]["properties"]
    assert "z_start" in rows                                          # the installer spells the row out
    for name in ("get_disk_space", "check_motion_limits"):             # the checks refer to it instead
        holder = by_name[name]["properties"]["acquisitions"]
        assert holder["items"] == {"type": "object"} and "set_acquisition_list" in holder["description"]
    single = by_name["acquire_start"]["properties"]["acquisition"]       # and so does the single-row start
    assert "properties" not in single and "set_acquisition_list" in single["description"]


def _turn(kind):
    part = type(kind, (), {})()
    return type("Msg", (), {"parts": [part]})()


def test_trim_history_keeps_whole_recent_turns():
    history = [_turn("UserPromptPart"), _turn("TextPart"), _turn("UserPromptPart"), _turn("ToolReturnPart"),
               _turn("TextPart"), _turn("UserPromptPart"), _turn("TextPart")]
    kept = ai.trim_history(history, 2)
    assert kept == history[2:]                                      # starts at an operator prompt
    assert ai.trim_history(history, 3) == history
    assert ai.trim_history([], 5) == []


def test_compact_history_keeps_the_newest_turns_whole_and_shrinks_the_older_ones():
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
    state = json.dumps({"state": "idle", "position": {"x": 1.0}, "optics": {"intensity": 10}, "limits": {"x": [-9, 9]} , "disk": {"free_bytes": 5}})
    big = "x" * 900

    def turn(n):
        return [ModelRequest(parts=[UserPromptPart(content=f"turn {n}\n\n<microscope_state>\n{state}\n</microscope_state>")]),
                ModelResponse(parts=[ToolCallPart(tool_name="get_config", args={}, tool_call_id=f"c{n}")]),
                ModelRequest(parts=[ToolReturnPart(tool_name="get_config", content=big, tool_call_id=f"c{n}")]),
                ModelResponse(parts=[TextPart(f"reply {n}")])]
    history = [m for n in range(5) for m in turn(n)]
    compact = ai.compact_history(history, full_turns=2)
    assert len(compact) == len(history) and compact[12:] == history[12:]            # the last two turns untouched
    old_prompt = compact[0].parts[0].content
    assert old_prompt.startswith("turn 0") and "<microscope_state>" not in old_prompt
    assert '"intensity": 10' in old_prompt and "limits" not in old_prompt          # optics kept, limits dropped
    assert compact[2].parts[0].content.endswith("[shortened in memory]") and len(compact[2].parts[0].content) < 400
    assert compact[1] is history[1] and compact[3] is history[3]                     # calls and replies as they were
    def content(messages):
        return sum(len(str(getattr(part, "content", ""))) for m in messages for part in m.parts)
    assert content(compact[:12]) < content(history[:12]) / 2                       # the older turns, half or less
    assert ai.compact_history(history[:8], full_turns=2) == history[:8]              # nothing older than the window
    assert ai.compact_history([], 2) == []


def test_the_agent_compacts_the_history_before_each_model_request():
    """Older turns reach the model compacted whatever history was handed in, mid-turn requests
    included, while the stored history stays complete."""
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel
    seen = []

    def model_function(messages, info):
        seen.append(messages)
        return ModelResponse(parts=[TextPart("ok")])
    state = json.dumps({"state": "idle", "position": {"x": 1.0}, "optics": {"intensity": 10}, "limits": {"x": [-9, 9]}})
    history = [m for n in range(5) for m in (
        ModelRequest(parts=[UserPromptPart(content=f"turn {n}\n\n<microscope_state>\n{state}\n</microscope_state>")]),
        ModelResponse(parts=[TextPart(f"reply {n}")]))]
    agent = ai.build_agent(FakeAcceptor(), threading.Event(), model=FunctionModel(model_function))
    result = agent.run_sync("turn 5\n\n<microscope_state>\n" + state + "\n</microscope_state>", message_history=history)
    sent = seen[0]
    assert "<microscope_state_then>" in sent[0].parts[0].content and "limits" not in sent[0].parts[0].content
    assert sent[-1].parts[0].content.startswith("turn 5\n\n<microscope_state>")   # the newest turn whole
    stored = result.all_messages()                                   # pydantic-ai keeps the processed history,
    assert "<microscope_state_then>" in stored[0].parts[0].content   # so an old turn stays compact from then on
    assert stored[-2].parts[0].content.startswith("turn 5\n\n<microscope_state>")


def test_run_turn_caps_the_history(monkeypatch):
    monkeypatch.setattr(ai.config, "MAX_HISTORY_TURNS", 1)
    worker = AssistantWorker(FakeAcceptor())
    long = [_turn("UserPromptPart"), _turn("TextPart"), _turn("UserPromptPart"), _turn("TextPart")]
    result = FakeResult("ok")
    result.all_messages = lambda: long
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent([result]))
    worker.run_turn("hi")
    assert worker._history == long[2:]
    worker.reset()
    assert worker._history == []


def test_worker_uses_its_own_history_cap(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    worker.max_history_turns = 1
    long = [_turn("UserPromptPart"), _turn("TextPart"), _turn("UserPromptPart"), _turn("TextPart")]
    result = FakeResult("ok")
    result.all_messages = lambda: long
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent([result]))
    worker.run_turn("hi")
    assert worker._history == long[2:]


def test_a_dedicated_vision_model_reads_the_frame_for_a_text_only_main_model(monkeypatch):
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    used = []
    monkeypatch.setattr(ai, "vision_answer", lambda endpoint, image, question, stats: used.append(endpoint.provider) or "centred")
    local = Endpoint(provider="Local", kind="openai-compatible", model="m", base_url="u")
    tools = build_tools(Acceptor(RecordingCore()), threading.Event(), endpoint=local,
                        vision_endpoint=Endpoint.from_preset("Gemini"))
    look_tool = next(t for t in tools if t.name == "look")
    out = json.loads(look_tool.function(question="centred?"))
    assert out["answer"] == "centred" and used == ["Gemini"]


def test_look_uses_the_live_frame_size(monkeypatch):
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import Acceptor
    sizes = []
    acceptor = Acceptor(RecordingCore())
    real = acceptor.dispatch

    def spy(name, args):
        if name == "get_frame":
            sizes.append(args["max_size"])
        return real(name, args)

    acceptor.dispatch = spy
    size = {"px": 300}
    tools = build_tools(acceptor, threading.Event(), endpoint=Endpoint.from_preset("Gemini", api_key="k"),
                        image_size=lambda: size["px"])
    monkeypatch.setattr(ai, "vision_answer", lambda *a: "ok")
    look_tool = next(t for t in tools if t.name == "look")
    look_tool.function(question="q")
    size["px"] = 600
    look_tool.function(question="q", snap=False)
    assert sizes == [300, 600]


# --- tool sets: Regular for a facility user, Full for the machine ---

def test_regular_profile_offers_the_session_not_the_machine():
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS
    regular = {c.name for c in ai.offered_commands("Regular")}
    everything = {c.name for c in ai.offered_commands("Full")}
    assert everything == set(COMMANDS) - {"get_manual"}
    assert regular < everything
    assert {"move_absolute", "set_laser", "set_zoom", "snap", "run_acquisition_list", "load_sample", "stop"} <= regular
    machine = {"set_etl", "set_galvo", "set_laser_timing", "set_state", "reload_etl_config", "update_etl_from_laser",
               "update_etl_from_zoom", "save_etl_config", "start_lightsheet_alignment_mode", "start_visual_mode", "self_test"}
    assert machine <= everything - regular
    assert all(name in COMMANDS for name in ai.config.TOOL_PROFILES["Regular"])   # no stale names


def test_regular_tools_and_prompt_are_filtered_and_set_camera_is_narrowed():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    tools = {t.name: t for t in build_tools(FakeAcceptor(), threading.Event(), profile="Regular")}
    assert "set_etl" not in tools and "set_camera" in tools
    assert list(tools["set_camera"].function_schema.json_schema["properties"]) == ["camera_exposure_time"]
    acc = FakeAcceptor(flip_after=1)
    narrowed = {t.name: t for t in build_tools(acc, threading.Event(), profile="Regular")}["set_camera"]
    refused = json.loads(narrowed.function(camera_binning="2x2"))
    assert refused["error"]["code"] == "validation" and "camera_binning" in refused["error"]["message"]
    assert acc.calls == []
    json.loads(narrowed.function(camera_exposure_time=0.05))
    assert acc.calls[0] == ("set_camera", {"camera_exposure_time": 0.05})
    assert "Full tool set" in refused["error"]["message"]          # the way out is named, for the operator
    prompt = ai.build_system_prompt(profile="Regular")
    commands = prompt.split("# Commands")[1].split("# Not in this tool set")[0]
    assert "set_zoom" in commands and "set_etl" not in commands
    hidden = prompt.split("# Not in this tool set")[1]              # named, so the model says so instead of improvising
    assert "self_test" in hidden and "set_etl" in hidden and "get_manual" not in hidden
    assert ai.hidden_commands("Regular") == [n for n in COMMANDS if n not in ai.config.TOOL_PROFILES["Regular"] and n != "get_manual"]
    full = {t.name for t in build_tools(FakeAcceptor(), threading.Event(), profile="Full")}
    assert "set_etl" in full and "set_etl" in ai.build_system_prompt(profile="Full").split("# Commands")[1]
    assert ai.hidden_commands("Full") == [] and "# Not in this tool set" not in ai.build_system_prompt(profile="Full")


def test_worker_rebuilds_the_agent_for_a_new_profile(monkeypatch):
    built = []
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: built.append(k["profile"]) or FakeAgent([FakeResult("ok")]))
    worker = AssistantWorker(FakeAcceptor())
    worker.configure(Endpoint.from_preset("OpenAI", api_key="k"))
    worker.run_turn("a")
    worker.run_turn("b")                                            # same agent, no rebuild
    worker.set_profile("Full")
    worker.run_turn("c")
    assert built == ["Regular", "Full"]


# --- traces ---

def test_turn_trace_pairs_calls_with_their_results_and_hides_image_bytes():
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    call = ToolCallPart(tool_name="look", args={"question": "centred?"})
    messages = [ModelResponse(parts=[call]),
                ModelRequest(parts=[ToolReturnPart(tool_name="look", tool_call_id=call.tool_call_id,
                                                   content=json.dumps({"stats": {"mean": 3}, "image": {"base64": "A" * 5000}}))]),
                ModelResponse(parts=[TextPart("centred")])]
    (entry,) = ai.turn_trace(messages)
    assert entry["tool"] == "look" and entry["args"] == {"question": "centred?"}
    assert '"base64": "<5000 chars>"' in entry["result"] and len(entry["result"]) <= ai.config.TRACE_RESULT_CHARS


def test_worker_records_every_turn(tmp_path, monkeypatch):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    monkeypatch.setattr(ai, "build_model", lambda endpoint: FunctionModel(lambda messages, info: ModelResponse(parts=[TextPart("hello back")])))
    worker = AssistantWorker(FakeAcceptor())
    worker.configure(Endpoint.from_preset("Gemini", api_key="k"))
    worker.trace_folder = str(tmp_path)
    worker.run_turn("hello")
    (path,) = list(tmp_path.iterdir())
    (line,) = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["prompt"] == "hello" and record["reply"] == "hello back" and record["tools"] == []
    assert record["provider"] == "Gemini" and record["profile"] == "Regular" and record["error"] is None
    assert record["served"] == ["function:<lambda>:"]              # who answered
    worker.trace_folder = None                                      # off: nothing more is written
    worker.run_turn("again")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_traces_folder_follows_the_config():
    assert ai.traces_folder(None).endswith(os.path.join("mesoSPIM", "assistant_traces"))
    assert ai.traces_folder(types.SimpleNamespace(ai_assistant_traces_folder="/elsewhere")) == "/elsewhere"


def test_every_preset_builds_its_model_with_the_installed_sdks():
    """Catches an SDK that pydantic-ai can no longer drive (the anthropic 1.x client library
    switch) before an operator meets it at Connect. No request is made."""
    pytest.importorskip("pydantic_ai")
    for provider in ai.config.PROVIDERS:
        endpoint = Endpoint.from_preset(provider, "", api_key="placeholder", base_url="http://127.0.0.1:1/v1")
        assert ai.build_model(endpoint) is not None, provider


def test_regular_keeps_the_etl_out_of_acquisition_rows_too():
    """A row carries the machine's ETL settings, so without this the Regular set could set them
    through set_acquisition_list; the schema hides the keys and a row carrying one is refused."""
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    acc = FakeAcceptor()
    regular = {t.name: t for t in build_tools(acc, threading.Event(), profile="Regular")}["set_acquisition_list"]
    rows = regular.function_schema.json_schema["properties"]["acquisitions"]["items"]["properties"]
    assert not any(key.startswith("etl_") for key in rows) and "z_step" in rows
    out = json.loads(regular.function(acquisitions=[{"z_start": 0, "z_end": 0, "z_step": 1, "etl_l_amplitude": 1.5}]))
    assert out["error"]["code"] == "validation" and "etl_l_amplitude" in out["error"]["message"]
    assert acc.calls == []
    single = {t.name: t for t in build_tools(acc, threading.Event(), profile="Regular")}["acquire_start"]
    assert "properties" not in single.function_schema.json_schema["properties"]["acquisition"]   # by reference
    out = json.loads(single.function(acquisition={"etl_l_amplitude": 1.5}))
    assert out["error"]["code"] == "validation" and acc.calls == []
    full = {t.name: t for t in build_tools(acc, threading.Event(), profile="Full")}["set_acquisition_list"]
    assert "etl_l_amplitude" in full.function_schema.json_schema["properties"]["acquisitions"]["items"]["properties"]


def test_a_fallback_that_answers_is_announced(monkeypatch):
    def answered_by(name):
        result = FakeResult("done")
        result.new_messages = lambda: [types.SimpleNamespace(kind="response", model_name=name, parts=[])]
        return result
    agent = FakeAgent([answered_by("gemini-3.1-flash-lite"), answered_by("gemini-3.5-flash-lite")])
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: agent)
    worker = AssistantWorker(FakeAcceptor())
    worker.configure(Endpoint.from_preset("Gemini", api_key="k"))
    notices, replies = [], []
    worker.sig_served.connect(notices.append)
    worker.sig_reply.connect(replies.append)
    worker.run_turn("hello")
    assert replies == ["done"]
    assert notices == ["gemini-3.1-flash-lite answered this turn, standing in for gemini-3.5-flash-lite"]
    worker.run_turn("hello again")                                  # the chosen model: no notice
    assert len(notices) == 1 and replies == ["done", "done"]


# --- the session store: what compaction leaves out, on request ---

def test_the_store_recalls_a_turn_and_the_changes_of_a_key():
    store = ai.SessionStore()
    store.begin("set the intensity to 30", {"state": "idle", "optics": {"intensity": 10}, "disk": {"free_bytes": 5}})
    store.finish([], "Set to 30.")
    store.begin("where are we?", {"state": "idle", "optics": {"intensity": 30}, "disk": {"free_bytes": 5}})
    store.finish([], "Idle.")
    store.begin("zoom 2x", {"state": "idle", "optics": {"intensity": 30, "zoom": "2x"}, "disk": {"free_bytes": 4}})
    store.finish([], "Zoomed.")
    first = store.recall(turn=1)
    assert first["prompt"] == "set the intensity to 30" and first["readout"]["disk"]["free_bytes"] == 5
    assert store.recall(turn=-1)["prompt"] == "zoom 2x" and store.recall()["turn"] == 3
    assert store.recall(turn=9)["error"]["code"] == "not_found" and ai.SessionStore().recall()["error"]
    changes = store.recall(changed="optics.intensity")["changes"]
    assert [(c["turn"], c["from"], c["to"]) for c in changes] == [(2, 10, 30)]
    assert store.recall(changed="disk.free_bytes")["changes"][0]["turn"] == 3
    hits = store.search("intensity 30")["matches"]
    assert [h["turn"] for h in hits] == [1]                               # words in messages, replies, results
    assert store.search("banana")["matches"] == []


def test_with_state_opens_the_turn_in_the_store_and_the_tools_read_it():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    store = ai.SessionStore()
    text = ai.with_state(FakeAcceptor(), "hello", store)
    assert text.endswith("hello") and store.turns[-1]["prompt"] == "hello" and store.turns[-1]["readout"]
    store.finish([], "hi")
    tools = {t.name: t for t in build_tools(FakeAcceptor(), threading.Event(), store=store)}
    assert json.loads(tools["recall_turn"].function(turn=1))["reply"] == "hi"
    assert json.loads(tools["search_history"].function(query="hello"))["matches"][0]["turn"] == 1
    assert "recall_turn" not in {t.name for t in build_tools(FakeAcceptor(), threading.Event())}   # only with a store


def test_the_worker_keeps_a_store_and_clear_all_empties_it(monkeypatch):
    worker = AssistantWorker(FakeAcceptor())
    monkeypatch.setattr(ai, "build_agent", lambda a, c, **k: FakeAgent([FakeResult("ok"), FakeResult("ok")]))
    worker.run_turn("first")
    worker.run_turn("second")
    assert [t["prompt"] for t in worker.store.turns] == ["first", "second"] and worker.store.turns[0]["reply"] == "ok"
    worker.reset()
    assert worker.store.turns == [] and worker._agent is None


# --- large results are shortened at the source ---

def test_a_long_acquisition_list_keeps_its_rows_with_the_summary_keys_only():
    rows = [{key: i for key in ("x_pos", "y_pos", "z_start", "z_end", "z_step", "etl_l_amplitude", "etl_r_offset",
                                "laser", "filter", "zoom", "filename", "folder", "planes", "processing", "rot",
                                "shutterconfig", "intensity", "f_start", "f_end", "image_writer_plugin")} for i in range(40)]
    result = ai.shorten_result("get_acquisition_list", {"acquisitions": rows})
    assert len(result["acquisitions"]) == 40 and "etl_l_amplitude" not in result["acquisitions"][0]
    assert result["acquisitions"][3]["z_end"] == 3 and "40 rows" in result["note"]
    long = ai.shorten_result("get_acquisition_list", {"acquisitions": rows * 2})
    assert len(long["acquisitions"]) == ai.config.ROWS_MAX and "omitted" in long["note"]
    small = {"acquisitions": rows[:2]}
    assert ai.shorten_result("get_acquisition_list", small) is small                # short: untouched


def test_any_other_long_result_keeps_the_keys_that_fit_and_names_the_rest():
    big = {"small": 1, "huge": "x" * 5000, "medium": list(range(100))}
    result = ai.shorten_result("get_limits", big)
    assert result["small"] == 1 and "huge" not in result and "huge (" in result["note"]
    assert len(json.dumps(result)) <= ai.config.RESULT_CHARS
    assert ai.shorten_result("get_state", {"a": 1}) == {"a": 1}


# --- the fixed prefix is the same on every request, for the providers' caches ---

def test_the_instructions_and_tools_are_identical_across_agents():
    pytest.importorskip("pydantic_ai")
    from mesoSPIM.src.mesoSPIM_AiAssistent import build_tools
    import datetime
    a = ai.build_system_prompt(profile="Regular")
    b = ai.build_system_prompt(profile="Regular")
    assert a == b and str(datetime.date.today().year) not in a           # nothing time-dependent in the prefix
    schemas = lambda: [(t.name, t.description, json.dumps(t.function_schema.json_schema, sort_keys=True))
                       for t in build_tools(FakeAcceptor(), threading.Event(), profile="Regular")]
    assert schemas() == schemas()
