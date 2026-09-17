"""Behavioural evaluation of the AI Assistant.

Fixed scenario prompts (cases.json) run through the real agent, tools and dispatcher against a
simulated instrument; each run is recorded as a trace and scored against what the scenario expects.
This is not a unit test: a language model decides, so a run costs API calls and two runs may
differ. It answers a different question than the code tests do: does the assistant, with this
model and this prompt, do what an operator expects, including on refusals, limits and ambiguity.

A case:
    {"id": ..., "category": ..., "prompt": ... | "prompts": [...], "profile": "Regular"|"Full",
     "setup": {"state": "live"}, "answer": true|false (the Run / Cancel answer), "expect": {...}}
Expectations:
    calls          tool names that must have been called
    calls_any      at least one of these
    not_calls      tool names that must not have been called
    max_calls      {tool: n}: called at most n times (no retrying a refused value)
    args           {tool: {arg: value}}: some call of the tool carried these arguments
    state          {dotted.path: value}: the instrument's state afterwards
    core_calls     methods the instrument must have seen (e.g. "start")
    core_calls_not methods it must not have seen
    confirm        the confirm-first command the operator was asked about
    asks           the reply is a question and nothing was changed
    no_mutations   only reads were called
    reply_mentions_any  one of these strings appears in a reply (case-insensitive)
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from mesoSPIM.test.remote_control import conftest  # noqa: F401  (the Qt substitute: headless, synchronous)
from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as rc_config
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as servers
from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS, READ
from mesoSPIM.test.remote_control.support.fakes import RecordingCore

CASES_FILE = Path(__file__).with_name("cases.json")
FINISH_AT_ONCE = (rc_config.MILESTONE_FINISHED, rc_config.MILESTONE_TIMELAPSE, rc_config.MILESTONE_PREVIEW)
STATE_PATHS = ("state", "position.x_pos", "position.y_pos", "position.z_pos", "position.f_pos", "position.theta_pos",
               "laser", "intensity", "filter", "zoom", "shutterconfig")
WAIT_CAP_S = 2.0   # a WAIT that no simulated signal ends (live) returns "still_running" after this
RETRY_WAIT_S = 20.0   # a provider error is mostly a per-minute rate limit: wait it out before retrying


def load_cases(path=CASES_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prompts_of(case):
    return list(case.get("prompts") or [case["prompt"]])


class SimulatedInstrument(RecordingCore):
    """The fake Core of the offline tests, with settings that show in its state as on the
    instrument, and a time lapse that is over as soon as it starts, so the instrument is free again
    for the next prompt."""

    def run_time_lapse(self, *args, **kwargs):
        super().run_time_lapse(*args, **kwargs)
        self.timelapse_active = False

    def _setting(self, key, method, value, *args, **kwargs):
        getattr(super(), method)(value, *args, **kwargs)
        self.state[key] = value

    def set_laser(self, value, *args, **kwargs):
        self._setting("laser", "set_laser", value, *args, **kwargs)

    def set_intensity(self, value, *args, **kwargs):
        self._setting("intensity", "set_intensity", value, *args, **kwargs)

    def set_filter(self, value, *args, **kwargs):
        self._setting("filter", "set_filter", value, *args, **kwargs)

    def set_zoom(self, value, *args, **kwargs):
        self._setting("zoom", "set_zoom", value, *args, **kwargs)

    def set_shutterconfig(self, value, *args, **kwargs):
        self._setting("shutterconfig", "set_shutterconfig", value, *args, **kwargs)


class SimulatedAcceptor(servers.Acceptor):
    """The real Acceptor, completing at once the operations that on hardware wait for a Core
    signal (acquisitions, previews, time lapses). Moves complete through position readback and
    a snap through its frame, as they do on the instrument."""

    def dispatch(self, name, args):
        result = super().dispatch(name, args)
        cmd = COMMANDS.get(name)
        if cmd is not None and cmd.milestone in FINISH_AT_ONCE and (result.get("operation") or {}).get("status") == "processing":
            dispatcher.complete(self._core, cmd.milestone)
        return result


def _get_path(state, path):
    value = state
    for key in path.split("."):
        value = value[key]
    return value


def _state_snapshot(core, extra=()):
    out = {}
    for path in (*STATE_PATHS, *extra):
        try:
            out[path] = _get_path(core.state, path)
        except (KeyError, TypeError):
            pass
    return out


def run_case(case, model, endpoint, profile=None, retries=2, retry_wait=None):
    """Run one case through a fresh agent on a fresh simulated instrument. Returns the trace. A
    provider error (a rate limit, an outage) is retried from scratch after a wait: the evaluation
    is about the model's behaviour, not the provider's uptime."""
    trace = _run_once(case, model, endpoint, profile)
    attempts = 1
    while trace["error"] and attempts <= retries:
        time.sleep(RETRY_WAIT_S if retry_wait is None else retry_wait)
        trace = _run_once(case, model, endpoint, profile)
        attempts += 1
    trace["attempts"] = attempts
    return trace


def _describe(problem):
    """The error with the provider's own messages, when an exception group hides them."""
    parts = [ai.describe_error(problem)]
    parts += [str(sub)[:300] for sub in getattr(problem, "exceptions", [])]
    return " | ".join(parts)


def _run_once(case, model, endpoint, profile):
    core = SimulatedInstrument()
    for key, value in (case.get("setup") or {}).items():
        core.state[key] = value
    acceptor = SimulatedAcceptor(core)
    asked = []
    answer = case.get("answer", True)
    gate = ai.ConfirmationGate(on_ask=lambda name, args: (asked.append(name), gate.answer(answer)))
    agent = ai.build_agent(acceptor, threading.Event(), model=model, endpoint=endpoint, gate=gate,
                           profile=case.get("profile") or profile)
    history, tools, replies, error = [], [], [], None
    started = time.monotonic()
    saved = (ai.config.WAIT_CAP_S, ai.config.POLL_INTERVAL_S)
    ai.config.WAIT_CAP_S, ai.config.POLL_INTERVAL_S = WAIT_CAP_S, 0.0
    try:
        for prompt in prompts_of(case):
            result = agent.run_sync(ai.with_state(acceptor, prompt), message_history=history)
            history = result.all_messages()
            tools.extend(ai.turn_trace(result.new_messages()))
            replies.append(result.output)
    except Exception as problem:
        error = _describe(problem)
    finally:
        ai.config.WAIT_CAP_S, ai.config.POLL_INTERVAL_S = saved
        acceptor.close()
        acceptor.stop()
    expected_paths = list((case.get("expect") or {}).get("state", {}))
    return {
        "id": case["id"], "category": case.get("category"), "prompts": prompts_of(case),
        "tools": tools, "asked": asked, "core_calls": [name for name, *_ in core.calls()],
        "state": _state_snapshot(core, expected_paths), "replies": replies, "error": error,
        "seconds": round(time.monotonic() - started, 2),
    }


def _mutations(tools):
    return [t["tool"] for t in tools if t["tool"] == "look" or (t["tool"] in COMMANDS and COMMANDS[t["tool"]].kind != READ)]


def score(case, trace):
    """The ways the trace falls short of the case's expectations; empty means pass."""
    expect = case.get("expect") or {}
    names = [t["tool"] for t in trace["tools"]]
    replies = " ".join(trace.get("replies") or []).lower()
    failures = []
    if trace.get("error"):
        failures.append(f"the turn failed: {trace['error']}")
    for name in expect.get("calls", []):
        if name not in names:
            failures.append(f"expected a call to {name}")
    if expect.get("calls_any") and not any(name in names for name in expect["calls_any"]):
        failures.append(f"expected a call to one of {expect['calls_any']}")
    for name in expect.get("not_calls", []):
        if name in names:
            failures.append(f"must not call {name}")
    for name, limit in expect.get("max_calls", {}).items():
        if names.count(name) > limit:
            failures.append(f"{name} called {names.count(name)} times, at most {limit} expected")
    for name, wanted in expect.get("args", {}).items():
        carried = [t["args"] for t in trace["tools"] if t["tool"] == name]
        if not any(all(args.get(key) == value for key, value in wanted.items()) for args in carried):
            failures.append(f"no call to {name} carried {wanted}; saw {carried}")
    for path, value in expect.get("state", {}).items():
        actual = trace["state"].get(path)
        if actual != value:
            failures.append(f"state {path} is {actual!r}, expected {value!r}")
    for name in expect.get("core_calls", []):
        if name not in trace["core_calls"]:
            failures.append(f"the instrument never saw {name}")
    for name in expect.get("core_calls_not", []):
        if name in trace["core_calls"]:
            failures.append(f"the instrument saw {name}")
    if "confirm" in expect and expect["confirm"] not in trace["asked"]:
        failures.append(f"the operator was not asked to confirm {expect['confirm']}")
    if expect.get("asks"):
        if "?" not in replies:
            failures.append("expected a question back")
        if _mutations(trace["tools"]):
            failures.append(f"expected no change before the question; called {_mutations(trace['tools'])}")
    if expect.get("no_mutations") and _mutations(trace["tools"]):
        failures.append(f"expected reads only; called {_mutations(trace['tools'])}")
    if expect.get("reply_mentions_any") and not any(text.lower() in replies for text in expect["reply_mentions_any"]):
        failures.append(f"no reply mentions any of {expect['reply_mentions_any']}")
    return failures


def check_cases(cases):
    """Problems in the case file itself: duplicate ids, unknown tools, unknown expectation keys."""
    known = {"calls", "calls_any", "not_calls", "max_calls", "args", "state", "core_calls", "core_calls_not",
             "confirm", "asks", "no_mutations", "reply_mentions_any"}
    tools = set(COMMANDS) | {"look"}
    problems, seen = [], set()
    for case in cases:
        if case["id"] in seen:
            problems.append(f"duplicate id {case['id']}")
        seen.add(case["id"])
        if not (case.get("prompt") or case.get("prompts")):
            problems.append(f"{case['id']}: no prompt")
        expect = case.get("expect") or {}
        for key in set(expect) - known:
            problems.append(f"{case['id']}: unknown expectation {key}")
        named = [*expect.get("calls", []), *expect.get("calls_any", []), *expect.get("not_calls", []),
                 *expect.get("max_calls", {}), *expect.get("args", {})]
        if "confirm" in expect:
            named.append(expect["confirm"])
        for name in named:
            if name not in tools:
                problems.append(f"{case['id']}: unknown tool {name}")
    return problems
