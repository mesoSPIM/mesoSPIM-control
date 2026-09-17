"""Cross-transport busy-gate semantics against ONE Core-owned session shared by both adapters.

This is the offline home of the cross-transport busy check: a live app hosts only one transport, so
it cannot stage a cross-lane race. Here we prove cross-lane serialization semantics. The Dispatcher
suite proves atomicity under real thread contention, and the opt-in DemoStage suite races concurrent
clients over the operator-selected live transport.
"""

from __future__ import annotations

import pytest

from mesoSPIM.test.remote_control.support.harness import Harness
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher


@pytest.fixture
def h():
    harness = Harness()
    try:
        yield harness
    finally:
        harness.stop()


@pytest.mark.parametrize("first,second", [("mcp", "tcp"), ("tcp", "mcp")])
def test_busy_gate_serializes_across_lanes(h, first, second):
    ok, opened = h.invoke(first, "start_live", {})  # WAIT op; no signal fired -> holds the gate
    assert ok and opened["accepted"] is True
    operation = opened["operation"]
    assert operation["status"] == "processing"
    assert operation["command"] == "start_live"
    op_id = operation["id"]

    before = h.core.calls()
    ok, refused = h.invoke(second, "set_intensity", {"intensity": 20})  # mutation on the other lane
    assert not ok
    assert refused["code"] == "busy"
    assert "start_live" in refused["error"] and op_id in refused["error"]
    assert h.core.calls() == before  # the blocked mutation never reached Core
    assert dispatcher.operation_snapshot(h.core)["command"] == "start_live"  # running op untouched

    ok, progress = h.invoke(second, "get_progress", {})  # a READ is served while busy
    assert ok
    assert progress["operation"]["id"] == op_id
    assert progress["operation"]["status"] == "processing"

    ok, stopping = h.invoke(second, "stop_activity", {})  # an EMERGENCY is allowed while busy
    assert ok
    assert stopping["operation"]["status"] == "stopping"

    dispatcher.complete(h.core, config.MILESTONE_FINISHED)  # the milestone fires -> gate releases
    ok, done = h.invoke(first, "set_intensity", {"intensity": 20})
    assert ok
    assert done["operation"]["status"] == "completed"


@pytest.mark.parametrize("lane", ["mcp", "tcp"])
def test_action_is_acknowledged_before_execution_and_polled_over_each_lane(h, lane):
    pending = []
    h.core._remote_control_single_shot = lambda _delay, callback: pending.append(callback)

    ok, accepted = h.invoke(lane, "set_intensity", {"intensity": 20})

    assert ok
    assert accepted["operation"] == {
        "id": "op-000001",
        "command": "set_intensity",
        "status": "processing",
    }
    assert h.core.calls() == []
    assert len(pending) == 1

    pending.pop()()
    ok, progress = h.invoke(lane, "get_progress", {})

    assert ok
    assert progress["operation"] == {
        "id": "op-000001",
        "command": "set_intensity",
        "status": "completed",
        "result": {},
    }


def test_stop_start_does_not_clear_the_core_session(h):
    """Acceptor.stop() leaves the Core-owned session alone, so a
    WAIT op that never signalled still holds the gate after the transport is torn down."""
    ok, opened = h.invoke("mcp", "start_live", {})
    assert ok and opened["operation"]["status"] == "processing"

    h.acceptor.stop()  # tear the transport's signal wiring down
    assert dispatcher.operation_snapshot(h.core)["status"] == "processing"  # the gate survived
    with pytest.raises(dispatcher.BusyError):  # a fresh transport would still be blocked
        dispatcher.run(h.core, "set_intensity", {"intensity": 20})


def test_wrong_milestone_does_not_resolve_a_finished_op(h):
    """Completion routes on milestone, so a time_lapse milestone
    must not resolve a start_live (finished) op."""
    ok, opened = h.invoke("tcp", "start_live", {})
    assert ok and opened["operation"]["status"] == "processing"

    dispatcher.complete(h.core, config.MILESTONE_TIMELAPSE)
    assert dispatcher.operation_snapshot(h.core)["status"] == "processing"
    h.core.state["state"] = "idle"
    dispatcher.complete(h.core, config.MILESTONE_FINISHED)
    assert dispatcher.operation_snapshot(h.core)["status"] == "completed"


@pytest.mark.parametrize("busy_state", ["live", "snap", "run_acquisition_list"])
def test_a_mode_started_from_the_gui_refuses_mutations_but_not_stop_or_reads(h, busy_state):
    """Core's own state machine can be busy with no remote operation open: the operator pressed
    Live or Run in the GUI. A remote mutation landing then would execute inside that loop."""
    h.core.state["state"] = busy_state
    for lane in ("mcp", "tcp"):
        ok, refused = h.invoke(lane, "move_absolute", {"targets": {"x": 10}})
        assert not ok and refused["code"] == "busy" and busy_state in refused["error"]
        ok, refused = h.invoke(lane, "snap", {})
        assert not ok and refused["code"] == "busy"
        ok, state = h.invoke(lane, "get_state", {})            # reads never wait
        assert ok and state["state"] == busy_state
    assert all(name not in ("move_absolute", "snap") for name, *_ in h.core.calls())
    ok, _ = h.invoke("tcp", "stop", {})                          # the emergency stop never waits
    assert ok
    h.core.state["state"] = "idle"
    ok, accepted = h.invoke("tcp", "move_absolute", {"targets": {"x": 10}})
    assert ok and accepted["accepted"] is True


def test_a_refused_time_point_ends_the_time_lapse(h):
    """Core refuses a time point in preflight with a warning and never starts it; the operation
    would otherwise stay open for every remaining interval. The Acceptor stops the time lapse."""
    operation = dispatcher._begin(h.core, "time_lapse_start", config.MILESTONE_TIMELAPSE)
    h.core.timelapse_active = True
    h.acceptor._on_warning("The following folders do not exist - stopping! /nowhere")
    latest = dispatcher.operation_snapshot(h.core)
    assert latest["id"] == operation["id"] and latest["status"] == "failed"
    assert "refused a time point" in latest["error"] and "/nowhere" in latest["error"]
    assert ("stop_time_lapse", (), {}) in h.core.calls() and h.core.timelapse_active is False


def test_a_warning_while_a_time_point_runs_is_only_recorded(h):
    operation = dispatcher._begin(h.core, "time_lapse_start", config.MILESTONE_TIMELAPSE)
    h.core.state["state"] = "run_acquisition_list"               # a point is under way
    h.acceptor._on_warning("Please wait until the zoom change is complete")
    latest = dispatcher.operation_snapshot(h.core)
    assert latest["id"] == operation["id"] and latest["status"] == "processing"
    assert latest["warning"].startswith("Please wait")
    assert all(name != "stop_time_lapse" for name, *_ in h.core.calls())
