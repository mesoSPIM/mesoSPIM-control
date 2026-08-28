"""AI Assistant worker logic, from source, under the Qt-free shim in conftest.

Covers the completion wrapper (dispatch_and_wait), the tool builder, and the worker's turn,
retry, tool-surfacing, and interrupt behaviour with a fake agent — no live model, no hardware.
Real-thread ordering is left to the real-PyQt smoke test, matching the Remote Control split.
"""
import json
import threading

import pytest

from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src.mesoSPIM_AiAssistent import (
    AssistantWorker, dispatch_and_wait, start_assistant_for_core, stop_assistant_for_core)
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
    monkeypatch.setattr(ai, "build_agent", lambda a, c, on_call=None: FakeAgent([FakeResult("moved")]))
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
    monkeypatch.setattr(ai, "build_agent", lambda a, c, on_call=None: FakeAgent(errors=[RuntimeError("boom")]))
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
                        lambda a, c, on_call=None, model=None: FakeAgent(errors=[TimeoutError()]))
    errors = _collect(worker.sig_error)
    worker.run_turn("go")
    assert errors == ["TimeoutError"]


def test_interrupt_sets_cancel_and_stops():
    acc = FakeAcceptor()
    worker = AssistantWorker(acc)
    worker.interrupt()
    assert worker.cancel.is_set()
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
