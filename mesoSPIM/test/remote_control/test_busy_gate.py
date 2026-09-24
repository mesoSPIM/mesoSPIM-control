"""Cross-transport busy-gate semantics against ONE Core-owned session shared by both adapters.

This is the offline home of the cross-transport busy check: a live app hosts only one transport, so
it cannot stage a cross-lane race. Here we prove cross-lane serialization semantics. The Dispatcher
suite proves atomicity under real thread contention, and the opt-in DemoStage suite races concurrent
clients over the operator-selected live transport.
"""

from __future__ import annotations

import pytest

from mesoSPIM.test.remote_control.support.fakes import RecordingCore
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


class _Sig:
    """A synchronous stand-in for a Core signal."""

    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot):
        self._slots.remove(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)


class _SignallingCore(RecordingCore):
    """RecordingCore with the signals the Acceptor listens to, and Core's own stop_time_lapse
    behaviour: it emits sig_time_lapse_cancelled synchronously."""

    def __init__(self):
        super().__init__()
        self.sig_finished = _Sig()
        self.sig_warning = _Sig()
        self.sig_time_lapse_cancelled = _Sig()
        self.sig_time_lapse_finished = _Sig()

    def stop_time_lapse(self, *args, **kwargs):
        was_active = self.timelapse_active
        super().stop_time_lapse(*args, **kwargs)
        if was_active:
            self.sig_time_lapse_cancelled.emit()


@pytest.fixture
def hs():
    harness = Harness(core=_SignallingCore())
    try:
        yield harness
    finally:
        harness.stop()


CORE_ACQUIRING_STATES = ["snap", "run_selected_acquisition", "run_acquisition_list", "preview_acquisition",
                         "running_script"]   # the strings mesoSPIM_Core.set_state and friends store
CORE_LIVE_STATES = ["live", "visual_mode", "lightsheet_alignment_mode"]


def test_the_config_names_the_states_core_stores():
    assert set(CORE_ACQUIRING_STATES) == set(config.ACQUIRING_STATES)
    assert set(CORE_LIVE_STATES) == set(config.LIVE_STATES)


@pytest.mark.parametrize("busy_state", CORE_ACQUIRING_STATES)
def test_a_gui_acquisition_or_snap_refuses_every_mutation_but_not_stop_or_reads(h, busy_state):
    """Core's own state machine is busy with no remote operation open: the operator pressed Snap
    or Run in the GUI. A mutation landing now would execute inside that loop."""
    h.core.state["state"] = busy_state
    for lane in ("mcp", "tcp"):
        for name, args in (("move_absolute", {"targets": {"x": 10}}), ("snap", {}), ("set_intensity", {"intensity": 20})):
            ok, refused = h.invoke(lane, name, args)
            assert not ok and refused["code"] == "busy" and busy_state in refused["error"], (lane, name)
        ok, state = h.invoke(lane, "get_state", {})            # reads never wait
        assert ok and state["state"] == busy_state
    assert all(name not in ("move_absolute", "snap", "set_intensity") for name, *_ in h.core.calls())
    ok, _ = h.invoke("tcp", "stop", {})                          # the emergency stops never wait
    assert ok
    ok, after = h.invoke("tcp", "stop_activity", {})
    assert ok and after["state"] == "idle"                       # and this one resets a left-over state
    ok, accepted = h.invoke("tcp", "set_intensity", {"intensity": 20})
    assert ok and accepted["accepted"] is True


@pytest.mark.parametrize("live_state", CORE_LIVE_STATES)
def test_a_gui_live_mode_refuses_only_what_would_take_over(h, live_state):
    """Live from the GUI keeps moves and settings usable, as the GUI itself does; a snap, another
    mode, an acquisition or a time lapse would take the loop over and is refused."""
    h.core.state["state"] = live_state
    for name in config.TAKES_OVER:
        assert name in dispatcher.COMMANDS, name
    for name, args in (("snap", {}), ("start_live", {}), ("run_acquisition_list", {}), ("time_lapse_start", {})):
        ok, refused = h.invoke("mcp", name, args)
        assert not ok and refused["code"] == "busy", (name, refused)
        assert "operator" in refused["error"] and "stop_activity" not in refused["error"]   # no invitation to end it
    ok, done = h.invoke("mcp", "set_intensity", {"intensity": 20})   # an ACTION: done at once
    assert ok and done["accepted"] is True
    ok, accepted = h.invoke("tcp", "move_absolute", {"targets": {"x": 10}})
    assert ok and accepted["accepted"] is True


def test_a_stale_gui_state_is_reset_when_its_sig_finished_arrives(hs):
    """Core leaves 'snap' after a GUI snap and the run state after a refused GUI run. The
    sig_finished that ends each resets the state, so remote work is not refused forever."""
    core = hs.core
    core.state["state"] = "snap"                                  # a GUI snap ran: state left behind
    core.sig_finished.emit()
    assert core.state["state"] == "idle"
    core.state["state"] = "run_acquisition_list"                  # a GUI run refused in preflight
    core.sig_warning.emit("The following folders do not exist - stopping! /nowhere")
    core.sig_finished.emit()
    assert core.state["state"] == "idle"
    ok, accepted = hs.invoke("tcp", "move_absolute", {"targets": {"x": 10}})
    assert ok and accepted["accepted"] is True


def test_a_stale_snap_left_before_the_transport_started_is_cleared_at_start():
    core = _SignallingCore()
    core.state["state"] = "snap"
    harness = Harness(core=core)
    try:
        assert core.state["state"] == "idle"
        ok, accepted = harness.invoke("mcp", "set_intensity", {"intensity": 20})
        assert ok and accepted["accepted"] is True
    finally:
        harness.stop()


def test_a_refused_time_point_ends_the_time_lapse_in_the_production_order(hs):
    """Upstream sets the run state, then start() refuses in preflight: sig_warning, sig_finished,
    the state still set. The operation must fail (not complete, although stop_time_lapse emits the
    cancel signal) and the time lapse must stop instead of idling through every interval."""
    core = hs.core
    operation = dispatcher._begin(core, "time_lapse_start", config.MILESTONE_TIMELAPSE)
    core.timelapse_active = True
    core.state["state"] = "run_acquisition_list"                  # MainWindow.run_timepoint did this
    core.sig_warning.emit("The following folders do not exist - stopping! /nowhere")
    latest = dispatcher.operation_snapshot(core)
    assert latest["status"] == "processing"                       # nothing decided on the warning alone
    core.sig_finished.emit()
    latest = dispatcher.operation_snapshot(core)
    assert latest["id"] == operation["id"] and latest["status"] == "failed", latest
    assert "refused a time point" in latest["error"] and "/nowhere" in latest["error"]
    assert core.timelapse_active is False and core.state["state"] == "idle"
    assert ("stop_time_lapse", (), {}) in core.calls()


def test_a_time_point_that_completes_after_a_warning_keeps_the_time_lapse(hs):
    core = hs.core
    operation = dispatcher._begin(core, "time_lapse_start", config.MILESTONE_TIMELAPSE)
    core.timelapse_active = True
    core.state["state"] = "run_acquisition_list"
    core.sig_warning.emit("Please wait until the zoom change is complete")
    core.state["state"] = "idle"                                  # close_acquisition_list did this
    core.sig_finished.emit()
    latest = dispatcher.operation_snapshot(core)
    assert latest["id"] == operation["id"] and latest["status"] == "processing"
    assert core.timelapse_active is True
    assert all(name != "stop_time_lapse" for name, *_ in core.calls())


def test_a_gui_time_lapse_is_busy_between_its_points(h):
    """Between points Core is idle and no remote operation exists, yet the next point is on its
    way: a remote live started now would have the point fired into its loop."""
    h.core.timelapse_active = True
    for name, args in (("start_live", {}), ("move_absolute", {"targets": {"x": 10}}), ("set_intensity", {"intensity": 20})):
        ok, refused = h.invoke("mcp", name, args)
        assert not ok and refused["code"] == "busy" and "time_lapse_stop" in refused["error"], name
    ok, after = h.invoke("mcp", "stop_activity", {})             # ends the time lapse too
    assert ok and h.core.timelapse_active is False
    ok, accepted = h.invoke("mcp", "set_intensity", {"intensity": 20})
    assert ok and accepted["accepted"] is True


def test_a_refused_time_point_is_detected_while_the_operation_is_stopping(hs):
    core = hs.core
    operation = dispatcher._begin(core, "time_lapse_start", config.MILESTONE_TIMELAPSE)
    core.timelapse_active = True
    operation["status"] = dispatcher.STOPPING                    # a client's stop landed mid-run
    assert dispatcher.operation_snapshot(core)["status"] == "stopping"
    core.state["state"] = "run_acquisition_list"
    core.sig_warning.emit("The following files already exist - stopping! a.raw")
    core.sig_finished.emit()
    latest = dispatcher.operation_snapshot(core)
    assert latest["status"] == "failed" and core.timelapse_active is False and core.state["state"] == "idle"


def test_a_stopped_run_ends_stopped_and_frees_the_gate(h):
    """A run a stop cut short used to end "completed" with stop_requested beside it, so a client that
    read only the status thought all its planes were taken. It ends "stopped" now; stop_requested
    stays for a client that reads it."""
    ok, opened = h.invoke("tcp", "run_acquisition_list", {})
    assert ok and opened["operation"]["status"] == "processing"
    h.invoke("tcp", "stop_activity", {})
    dispatcher.complete(h.core, config.MILESTONE_FINISHED)
    operation = dispatcher.operation_snapshot(h.core)
    assert operation["status"] == "stopped" and operation["stop_requested"] is True
    ok, next_one = h.invoke("tcp", "set_intensity", {"intensity": 20})      # the gate is free again
    assert ok and next_one["operation"]["status"] == "completed"


def test_a_run_nobody_stopped_still_ends_completed(h):
    h.invoke("tcp", "run_acquisition_list", {})
    dispatcher.complete(h.core, config.MILESTONE_FINISHED)
    operation = dispatcher.operation_snapshot(h.core)
    assert operation["status"] == "completed" and not operation.get("stop_requested")
