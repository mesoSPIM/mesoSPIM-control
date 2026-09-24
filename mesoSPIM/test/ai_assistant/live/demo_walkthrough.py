"""The AI Assistant driving a running mesoSPIM, to watch its tool calls reach the instrument.

The offline tests and the evaluation run the assistant against a simulated Core. This runs the
same agent, tools, TurnGuard, gate and failure advice against a real one: a mesoSPIM started with
-D (DemoStage) whose Remote Control tab has TCP running. The assistant's acceptor is swapped for
one that sends each command over that connection, so every tool call is a real command to the
running Core, and the stage, the filter wheel, the snap folder and the acquisition table change
on screen as it goes. After each step the instrument's own state is read back and checked.

    python -m mesoSPIM.test.ai_assistant.live.demo_walkthrough                      # scripted calls
    python -m mesoSPIM.test.ai_assistant.live.demo_walkthrough --provider Gemini    # the model decides

--scripted (the default) replays fixed tool calls, so it proves the tool plumbing end to end with
no language model and no API key. --provider hands the same prompts to a model, which chooses the
calls itself. The starting position, intensity, filter and acquisition list are put back at the
end. It refuses to run unless get_limits reports DemoStage.
"""
from __future__ import annotations

import argparse
import json
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
    """Put back what the walk changed, each command waited out as the assistant waits for its
    own: the next one would otherwise meet the gate still held by the last (busy)."""
    from mesoSPIM.src.mesoSPIM_RemoteControl_Dispatcher import COMMANDS
    undo = [("move_absolute", {"targets": {"x": start["x"]}}), ("set_intensity", {"intensity": start["intensity"]}),
            ("set_filter", {"filter": start["filter"]})]
    if start["acquisitions"]:
        undo.append(("set_acquisition_list", {"acquisitions": start["acquisitions"], "selected_row": 0}))
    for name, args in undo:
        done = ai.dispatch_and_wait(acceptor, name, args, COMMANDS[name].kind, threading.Event())
        print(f"    {name}: {done.get('status', 'done') if isinstance(done, dict) else done}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--provider", default="", help="a model preset (Gemini, OpenAI, Anthropic); scripted calls when omitted")
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

    start = {"x": position("x"), "intensity": value("intensity"), "filter": value("filter"),
             "acquisitions": read("get_acquisition_list", {}).get("acquisitions") or []}
    first_row = start["acquisitions"][0] if start["acquisitions"] else None
    x_target = 5000.0 if abs((start["x"] or 0) - 5000.0) > 1 else 6000.0
    snap_count = {"before": None}

    def newest_snap():
        folder = value("snap_folder")
        files = [f for f in os.listdir(folder) if f.endswith(".tif")] if folder and os.path.isdir(folder) else []
        return len(files)

    steps = [
        (f"Move the stage to X = {x_target:.0f} um.",
         [("move_absolute", {"targets": {"x": x_target}})],
         "X", lambda: _wait_until(lambda: position("x"), x_target), x_target),
        ("Set the laser intensity to 20 %.",
         [("set_intensity", {"intensity": 20})],
         "intensity", lambda: _wait_until(lambda: value("intensity"), 20), 20),
        ("Switch the filter to 515LP.",
         [("set_filter", {"filter": "515LP"})],
         "filter", lambda: _wait_until(lambda: value("filter"), "515LP"), "515LP"),
        ("Take a snap.",
         [("snap", {})],
         "a new file in the snap folder", lambda: newest_snap() > snap_count["before"], True),
    ]
    if first_row is not None:
        steps.append(("Rename the first acquisition to walkthrough.tif.",
                      [("update_acquisition_row", {"row": 0, "changes": {"filename": "walkthrough.tif"}})],
                      "row 0 renamed, zoom and z range kept",
                      lambda: _wait_until(lambda: (lambda row: (row.get("filename"), row.get("zoom"), row.get("z_end")))(
                          (read("get_acquisition_list", {}).get("acquisitions") or [{}])[0]),
                          ("walkthrough.tif", first_row.get("zoom"), first_row.get("z_end"))),
                      ("walkthrough.tif", first_row.get("zoom"), first_row.get("z_end"))))

    endpoint = ai.Endpoint.from_preset(arguments.provider) if arguments.provider else None
    gate = ai.ConfirmationGate(on_ask=lambda name, args: (print(f"      Run / Cancel asked for {name}: Run"),
                                                           gate.answer(True)))
    mode = f"model {endpoint.model}" if endpoint else "scripted tool calls"
    print(f"AI Assistant -> mesoSPIM DemoStage at {arguments.host}:{arguments.port}, {mode}\n")

    passed = 0
    try:
        for prompt, calls, what, check, expected in steps:
            if what.startswith("a new file"):
                snap_count["before"] = newest_snap()
            print(f"> {prompt}")
            agent = ai.build_agent(acceptor, threading.Event(), gate=gate, profile="Regular",
                                   on_call=lambda name, args: print(f"    tool: {name}({args})"),
                                   model=None if endpoint else _scripted(calls), endpoint=endpoint)
            reply = agent.run_sync(ai.with_state(acceptor, prompt)).output
            print(f"    reply: {ai.without_state_block(reply).strip()}")
            got = check()
            ok = got == expected
            passed += ok
            print(f"    {'PASS' if ok else 'FAIL'}: {what} is {got!r}{'' if ok else f', expected {expected!r}'}\n")
            time.sleep(arguments.pause)
    finally:
        print("Putting the instrument back ...")
        _restore(acceptor, start)
        acceptor.close()
    print(f"{passed} of {len(steps)} steps passed")
    raise SystemExit(0 if passed == len(steps) else 1)


if __name__ == "__main__":
    main()
