"""The AI Assistant driving a running mesoSPIM, to watch its tool calls reach the instrument.

The offline tests and the evaluation run the assistant against a simulated Core. This runs the
same agent, tools, TurnGuard, gate and failure advice against a real one: a mesoSPIM started with
-D (DemoStage) whose Remote Control tab has TCP running. The assistant's acceptor is swapped for
one that sends each command over that connection, so every tool call is a real command to the
running Core, and the stage, the filter wheel, the snap folder, live mode and the acquisition
table change on screen as it goes. After each step the instrument's own state is read back and checked.

    python -m mesoSPIM.test.ai_assistant.live.demo_walkthrough                      # scripted calls
    python -m mesoSPIM.test.ai_assistant.live.demo_walkthrough --provider Gemini    # the model decides

--scripted (the default) replays fixed tool calls, so it proves the tool plumbing end to end with
no language model and no API key. --provider hands the same prompts to a model, which chooses the
calls itself. The starting position, intensity, filter and acquisition list are put back at the
end. It refuses to run unless get_limits reports DemoStage.
"""
from __future__ import annotations

import argparse
import os
import threading
import time

from mesoSPIM.test.remote_control import conftest  # noqa: F401  (Qt substitute: the agent runs here, headless)
from mesoSPIM.src import mesoSPIM_AiAssistent as ai
from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import BusyError, UnknownCommand, ValidationError
from mesoSPIM.test.remote_control.support.clients import RemoteControl

_ERRORS = {"validation": ValidationError, "busy": BusyError, "unknown_command": UnknownCommand}


class TcpAcceptor:
    """The one thing the assistant asks of its acceptor, dispatch(name, args), over Remote
    Control TCP. An error reply ("error: [code] text") is raised as the exception the in-app
    Acceptor raises for that code, so the advice and TurnGuard see what they see in the tab."""

    def __init__(self, host, port, token):
        self._client = RemoteControl(host, port, token, timeout=60)
        self._lock = threading.Lock()

    def dispatch(self, name, args):
        with self._lock:
            try:
                return self._client.call(name, **(args or {}))
            except RuntimeError as error:
                text = str(error)
                if text.startswith("error: [") and "] " in text:
                    code, message = text[len("error: ["):].split("] ", 1)
                    raise _ERRORS.get(code, RuntimeError)(message) from None
                raise

    def close(self):
        self._client.close()


def _scripted(calls):
    """A model that makes these tool calls, one per request, then says it is done."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    def respond(messages, _info):
        made = sum(1 for m in messages for p in getattr(m, "parts", []) if type(p).__name__ == "ToolReturnPart")
        if made < len(calls):
            name, args = calls[made]
            return ModelResponse(parts=[ToolCallPart(name, args)])
        return ModelResponse(parts=[TextPart("Done.")])

    return FunctionModel(respond)


def _wait_until(read, expected, seconds=15.0):
    deadline = time.monotonic() + seconds
    while True:
        value = read()
        if value == expected or time.monotonic() > deadline:
            return value
        time.sleep(0.2)


def _restore(acceptor, start):
    """Put back what the walk changed, each action waited out until its operation ends: the
    assistant returns an action at acceptance, and the next command would otherwise meet the gate
    still held by the last (busy). An emergency stop has no operation of its own to wait on."""
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import ACTION, COMMANDS, WAIT
    undo = []
    if acceptor.dispatch("get_state_all", {"keys": ["state"]}).get("state") != "idle":
        undo.append(("stop_activity", {}))
    undo += [("move_absolute", {"targets": {"x": start["x"], "y": start["y"]}}),
             ("set_intensity", {"intensity": start["intensity"]}), ("set_filter", {"filter": start["filter"]}),
             ("set_laser", {"laser": start["laser"]}), ("set_zoom", {"zoom": start["zoom"]}),
             ("set_shutterconfig", {"shutterconfig": start["shutterconfig"]})]
    if start["acquisitions"]:
        undo.append(("set_acquisition_list", {"acquisitions": start["acquisitions"], "selected_row": 0}))
    for name, args in undo:
        kind = COMMANDS[name].kind
        done = ai.dispatch_and_wait(acceptor, name, args, WAIT if kind == ACTION else kind, threading.Event())
        print(f"    {name}: {done.get('status', 'done') if isinstance(done, dict) else done}")


class Step:
    """One operator request: the prompt, the calls a scripted run makes for it, and a check that
    reads the instrument (and, for a refusal, the reply) afterwards. `model_only` steps need a
    real model: look calls a vision model."""

    def __init__(self, prompt, calls, check, model_only=False):
        self.prompt, self.calls, self.check, self.model_only = prompt, calls, check, model_only


_LIMIT_WORDS = ("limit", "range", "25000", "25,000")
_FOLDER_WORDS = ("folder", "directory")
# The operator asked that a failure end with a way forward: the same words the evaluation accepts.
_PROPOSAL_WORDS = ("shall i", "should i", "would you like", "do you want", "another folder", "existing folder",
                   "set the snap folder", "choose", "create", "configur", "please")


def _steps(read, value, position, probe, stamp):
    """The walk. Each check returns (passed, what it saw); `before` holds the snap count and the
    position taken just before each step."""
    first = (read("get_acquisition_list", {}).get("acquisitions") or [None])[0]
    before = {"snaps": 0, "x": None, "y": None}

    def count_snaps():
        folder = value("snap_folder")
        return len([f for f in os.listdir(folder) if f.endswith(".tif")]) if folder and os.path.isdir(folder) else 0

    def mark():
        before.update(snaps=count_snaps(), x=position("x"), y=position("y"))

    def settled(read_value, expected):
        got = _wait_until(read_value, expected)
        return got == expected, f"{got!r} (expected {expected!r})"

    def new_snaps():
        return count_snaps() - before["snaps"]

    def first_row(*keys):
        row = read("get_acquisition_list", {})["acquisitions"][0]
        return tuple(row.get(key) for key in keys)

    def says(reply, words):
        """A scripted run answers only "Done.", so the reply is judged only with a model (None)."""
        return reply is None or any(word in reply.lower() for word in words)

    steps = [
        Step("Move the stage to X = 5000 um.", [("move_absolute", {"targets": {"x": 5000}})],
             lambda reply: settled(lambda: position("x"), 5000.0)),
        Step("Move Y by 1 mm.", [("move_relative", {"deltas": {"y": 1000}})],
             lambda reply: settled(lambda: position("y"), before["y"] + 1000.0)),
        Step("Set the laser intensity to 20 %.", [("set_intensity", {"intensity": 20})],
             lambda reply: settled(lambda: value("intensity"), 20)),
        Step("Switch the filter to 515LP.", [("set_filter", {"filter": "515LP"})],
             lambda reply: settled(lambda: value("filter"), "515LP")),
        Step("Switch to the 561 nm laser.", [("set_laser", {"laser": "561 nm"})],
             lambda reply: settled(lambda: value("laser"), "561 nm")),
        Step("Set the zoom to 1x.", [("set_zoom", {"zoom": "1x"})],
             lambda reply: settled(lambda: value("zoom"), "1x")),
        Step("Use the left light sheet.", [("set_shutterconfig", {"shutterconfig": "Left"})],
             lambda reply: settled(lambda: value("shutterconfig"), "Left")),
        Step("Take a snap.", [("snap", {})],
             lambda reply: (new_snaps() == 1, f"{new_snaps()} new file(s) (expected 1)")),
        Step("Take a snap into D:\\nowhere.", [("snap", {"folder": "D:\\nowhere"})],
             lambda reply: (new_snaps() == 0 and says(reply, _FOLDER_WORDS) and says(reply, _PROPOSAL_WORDS),
                            f"{new_snaps()} new file(s) (expected 0); the reply names the folder: {says(reply, _FOLDER_WORDS)}, "
                            f"proposes a fix: {says(reply, _PROPOSAL_WORDS)}")),
        Step("Look at the sample and tell me what you see.", [],
             lambda reply: (new_snaps() == 1 and len(reply) > 20, f"{new_snaps()} new file(s) (expected 1: one exposure)"),
             model_only=True),
        Step("Start live mode.", [("start_live", {})],
             lambda reply: settled(lambda: value("state"), "live")),
        Step("Stop the live mode.", [("stop_activity", {})],
             lambda reply: settled(lambda: value("state"), "idle")),
        Step("Move X to 30000 um.", [("move_absolute", {"targets": {"x": 30000}})],
             lambda reply: (position("x") == before["x"] and says(reply, _LIMIT_WORDS),
                            f"X {position('x')!r} (expected {before['x']!r} kept); the reply names the limit: {says(reply, _LIMIT_WORDS)}")),
    ]
    if first is not None:
        # The row's own extension: it suits the row's writer, which refuses any other.
        name = f"walk_{stamp}{os.path.splitext(first.get('filename') or '')[1] or '.tif'}"
        steps += [
            Step(f"Rename the first acquisition to {name}.",
                 [("update_acquisition_row", {"row": 0, "changes": {"filename": name}})],
                 lambda reply: settled(lambda: first_row("filename", "zoom", "f_start"),
                                       (name, first.get("zoom"), first.get("f_start")))),
            Step(f"Change the first acquisition to z from 0 to 20 um in steps of 10, saved in {probe}.",
                 [("update_acquisition_row", {"row": 0, "changes": {"z_start": 0, "z_end": 20, "z_step": 10, "folder": probe}})],
                 lambda reply: settled(lambda: first_row("z_end", "z_step", "folder", "zoom"),
                                       (20, 10, probe, first.get("zoom")))),
            Step("Run the acquisition list.", [("run_acquisition_list", {})],
                 lambda reply: (_wait_until(lambda: os.path.exists(os.path.join(probe, name)), True, 60),
                                os.path.join(probe, name))),
        ]
    return steps, mark


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--provider", default="", help="a model preset (Gemini, OpenAI, Anthropic); scripted calls when omitted")
    parser.add_argument("--repeat", type=int, default=1, help="walk this many times: a model's choice can differ per run")
    parser.add_argument("--probe", default=r"D:\mesospim-pr106-probe", help="an existing folder for the acquisition step")
    parser.add_argument("--host", default=os.environ.get("MESOSPIM_LIVE_TCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MESOSPIM_LIVE_TCP_PORT", "42000")))
    parser.add_argument("--token", default=os.environ.get("MESOSPIM_LIVE_TCP_TOKEN", "smart_mesospim"))
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between steps, to watch the instrument")
    arguments = parser.parse_args()

    acceptor = TcpAcceptor(arguments.host, arguments.port, arguments.token)
    read = acceptor.dispatch
    if (read("get_limits", {}).get("stage") or {}).get("stage_type") != "DemoStage":
        raise SystemExit("refused: get_limits does not report DemoStage; this walks a demo instrument only")

    def value(key):
        return read("get_state_all", {"keys": [key]}).get(key)

    def position(axis):
        return read("get_position", {}).get(axis)

    start = {"x": position("x"), "y": position("y"),
             **{key: value(key) for key in ("intensity", "filter", "laser", "zoom", "shutterconfig")},
             "acquisitions": read("get_acquisition_list", {}).get("acquisitions") or []}
    endpoint = ai.Endpoint.from_preset(arguments.provider) if arguments.provider else None
    gate = ai.ConfirmationGate(on_ask=lambda name, args: (print(f"      Run / Cancel asked for {name}: Run"),
                                                           gate.answer(True)))
    mode = f"model {endpoint.model}" if endpoint else "scripted tool calls"
    print(f"AI Assistant -> mesoSPIM DemoStage at {arguments.host}:{arguments.port}, {mode}\n")

    failures, total = [], 0
    try:
        for walk in range(1, arguments.repeat + 1):
            steps, mark = _steps(read, value, position, arguments.probe, time.strftime("%H%M%S"))
            for step in steps:
                if step.model_only and endpoint is None:
                    continue
                mark()
                print(f"[walk {walk}] > {step.prompt}")
                agent = ai.build_agent(acceptor, threading.Event(), gate=gate, profile="Regular",
                                       on_call=lambda name, args: print(f"    tool: {name}({args})"),
                                       model=None if endpoint else _scripted(step.calls), endpoint=endpoint)
                reply = ai.without_state_block(agent.run_sync(ai.with_state(acceptor, step.prompt)).output).strip()
                print(f"    reply: {reply}")
                ok, seen = step.check(reply if endpoint else None)
                total += 1
                print(f"    {'PASS' if ok else 'FAIL'}: {seen}\n")
                if not ok:
                    failures.append((walk, step.prompt, seen, reply))
                time.sleep(arguments.pause)
            print(f"Putting the instrument back after walk {walk} ...")
            _restore(acceptor, start)
            print()
    except BaseException:
        print("Stopped early: putting the instrument back ...")
        _restore(acceptor, start)
        raise
    finally:
        acceptor.close()
    print(f"{total - len(failures)} of {total} steps passed")
    for walk, prompt, seen, reply in failures:
        print(f"  FAIL walk {walk}: {prompt}\n       saw {seen}\n       reply: {reply}")
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
