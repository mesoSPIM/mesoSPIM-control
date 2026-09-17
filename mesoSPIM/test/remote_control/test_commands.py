"""Check the public Remote Control vocabulary and its fail-closed entry points."""

import re
from pathlib import Path

from types import SimpleNamespace

import pytest

from mesoSPIM.src import mesoSPIM_RemoteControl_Commands as commands
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as servers
from mesoSPIM.test.remote_control.support.contracts import VALID_CASES
from mesoSPIM.test.remote_control.support.fakes import RecordingCore


def test_registry_is_the_documented_53_calls():
    assert len(dispatcher.COMMANDS) == 53
    assert set(dispatcher.COMMANDS) == set(VALID_CASES)
    assert "execute_stage_program" not in dispatcher.COMMANDS
    assert "procedure" not in dispatcher.COMMANDS
    assert "set_mode" not in dispatcher.COMMANDS
    assert "snap" not in dispatcher.COMMANDS


def test_published_call_list_matches_the_registry():
    repository = Path(__file__).resolve().parents[3]
    text = (repository / "docs" / "source" / "remote_control" / "calls.md").read_text()
    documented = re.findall(r"^\| `([a-z_]+)` \|", text, re.MULTILINE)

    assert len(documented) == len(set(documented)) == 53
    assert set(documented) == set(dispatcher.COMMANDS)


def test_every_call_has_a_kind_and_readable_hint():
    allowed = {dispatcher.READ, dispatcher.ACTION, dispatcher.WAIT, dispatcher.EMERGENCY}
    for specification in dispatcher.COMMANDS.values():
        assert specification.kind in allowed
        assert specification.hint.strip()


def test_error_codes_are_stable_and_typed():
    assert dispatcher.error_info(dispatcher.ValidationError("x"))[0] == "validation"
    assert dispatcher.error_info(dispatcher.BusyError("x"))[0] == "busy"
    assert dispatcher.error_info(dispatcher.UnknownCommand("x"))[0] == "unknown_command"
    assert dispatcher.error_info(KeyError("x"))[0] == "execution"


def test_json_and_single_call_envelope_are_strict():
    name, arguments = dispatcher.parse_call('{"move_absolute":{"targets":{"x":1}}}')
    assert name == "move_absolute"
    assert arguments == {"targets": {"x": 1}}

    with pytest.raises(dispatcher.ValidationError):
        dispatcher.strict_json_loads('{"x":NaN}')
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.parse_call('{"a":{},"b":{}}')
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.parse_call("[]")


def test_built_in_manual_matches_the_registry_and_async_contract():
    manual = dispatcher.run(RecordingCore(), "get_manual", {})

    assert {entry["name"] for entry in manual["commands"]} == set(dispatcher.COMMANDS)
    assert "ordinary mutation" in manual["interaction"]["accepted_or_rejected"]
    assert "poll get_progress" in manual["interaction"]["kinds"]["wait"]
    assert "does not create a new operation" in manual["interaction"]["kinds"]["emergency"]


def test_mcp_identity_is_complete():
    assert config.MCP_PROTOCOL_VERSION == "2024-11-05"
    assert config.MCP_SERVER_NAME
    assert config.MCP_SERVER_VERSION


def test_startup_self_test_accepts_a_complete_demo_configuration():
    ok, report = commands.self_test(RecordingCore())
    assert ok is True, report


def test_unknown_transport_is_rejected_before_binding():
    with pytest.raises(ValueError):
        servers.start(object(), "SMTP", "127.0.0.1", 0, "secret")


def test_mcp_requires_a_password():
    with pytest.raises(ValueError):
        servers.start(object(), "MCP", "127.0.0.1", 0, "")


def test_missing_limits_fail_closed_before_binding():
    core = SimpleNamespace(cfg=SimpleNamespace())
    with pytest.raises(RuntimeError):
        servers.start(core, "MCP", "127.0.0.1", 0, "secret")


def test_transport_is_refused_while_the_ai_assistant_holds_the_session():
    """The mirror of test_start_assistant_refused_while_transport_runs: one controller per session."""
    core = RecordingCore()
    core._remote_control = None
    core._assistant_acceptor = object()
    servers.start_for_core(core, "TCP", "127.0.0.1", 0, "secret")
    assert core._remote_control is None
    reports = [args for name, args, _ in core.calls() if name == "sig_remote_control_started"]
    assert len(reports) == 1
    ok, message = reports[0]
    assert ok is False and "AI Assistant" in message


def test_default_password_is_refused_outside_loopback():
    with pytest.raises(ValueError):
        servers.start(object(), "MCP", "0.0.0.0", 0, config.DEFAULT_TOKEN)


# --- movement limits are enforced in the physical stage frame, whatever the zeroed readback says ---


def _zeroed_core(axis="x", user=0.0, physical=24999.0):
    """A core whose `axis` was zeroed: the operator sees `user`, the stage sits at `physical`.
    FakeCfg bounds x to [-25000, 25000], so +1 in the user frame is the last legal step and +2
    would leave the envelope."""
    core = RecordingCore()
    core.state["position"][f"{axis}_pos"] = user
    core.state["position_absolute"][f"{axis}_pos"] = physical
    return core


def test_axis_offsets_are_user_minus_physical_and_zero_when_unzeroed():
    core = _zeroed_core()
    offsets = commands.axis_offsets(core)
    assert offsets["x"] == -24999.0
    assert all(offsets[axis] == 0.0 for axis in ("y", "z", "f", "theta"))

    unzeroed = RecordingCore()
    assert all(value == 0.0 for value in commands.axis_offsets(unzeroed).values())


def test_axis_offsets_are_zero_without_an_absolute_readback():
    core = RecordingCore()
    core.state["position_absolute"] = {}
    assert commands.axis_offsets(core) == {axis: 0.0 for axis in config.AXES}


def test_move_absolute_is_checked_in_the_stage_frame_after_zeroing():
    core = _zeroed_core()
    # The reading says 2, the stage would be driven to 25001: refused before Core is touched.
    with pytest.raises(dispatcher.ValidationError, match="stage position 25001"):
        dispatcher.run(core, "move_absolute", {"targets": {"x": 2}})
    assert [name for name, *_ in core.calls() if name == "move_absolute"] == []

    # The last legal user-frame step is accepted and reaches Core untranslated: the stage driver
    # applies the offset itself, exactly as it does for the GUI.
    reply = dispatcher.run(core, "move_absolute", {"targets": {"x": 1}})
    assert reply["accepted"] is True
    ((_, args, _kw),) = [c for c in core.calls() if c[0] == "move_absolute"]
    assert args[0] == {"x_abs": 1.0}


def test_move_relative_is_checked_in_the_stage_frame_after_zeroing():
    core = _zeroed_core()
    with pytest.raises(dispatcher.ValidationError, match="stage position 25001"):
        dispatcher.run(core, "move_relative", {"deltas": {"x": 2}})
    assert [name for name, *_ in core.calls() if name == "move_relative"] == []

    reply = dispatcher.run(core, "move_relative", {"deltas": {"x": 1}})
    assert reply["accepted"] is True


def test_unzeroed_axes_keep_their_plain_limits():
    core = _zeroed_core()
    # y carries no offset: its envelope applies to the reading as before.
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.run(core, "move_absolute", {"targets": {"y": 50001}})
    assert dispatcher.run(core, "move_absolute", {"targets": {"y": 50000}})["accepted"] is True


def test_acquisition_rows_are_checked_in_the_stage_frame_after_zeroing():
    core = _zeroed_core()
    row = {"x_pos": 2, "y_pos": 0, "z_start": 0, "z_end": 10, "z_step": 1, "planes": 11}
    with pytest.raises(dispatcher.ValidationError, match="stage position 25001"):
        dispatcher.run(core, "set_acquisition_list", {"acquisitions": [row]})

    row["x_pos"] = 1
    assert dispatcher.run(core, "set_acquisition_list", {"acquisitions": [row]})["accepted"] is True


def test_installed_rows_are_revalidated_in_the_stage_frame_before_running():
    # A list installed while unzeroed becomes unsafe once the axis is zeroed further along.
    core = RecordingCore()
    row = {"x_pos": 1, "y_pos": 0, "z_start": 0, "z_end": 10, "z_step": 1, "planes": 11}
    dispatcher.run(core, "set_acquisition_list", {"acquisitions": [row]})
    core.state["position"]["x_pos"] = 0.0
    core.state["position_absolute"]["x_pos"] = 25000.0  # x_pos=1 now means physical 25001
    with pytest.raises(dispatcher.ValidationError, match="re-install the list"):
        dispatcher.run(core, "run_acquisition_list", {})
    assert [name for name, *_ in core.calls() if name == "start"] == []


def test_zeroing_cannot_bypass_a_tightened_environment_envelope(monkeypatch):
    monkeypatch.setenv(config.LIMITS_ENV_VAR, '{"x": [-100, 100]}')
    core = _zeroed_core(user=0.0, physical=24999.0)
    # The reading (0) is inside the tightened envelope; the stage (24999) is not.
    with pytest.raises(dispatcher.ValidationError, match="stage position 24999"):
        dispatcher.run(core, "move_absolute", {"targets": {"x": 0}})
    # Going back toward the envelope is allowed once the physical target is inside it.
    assert dispatcher.run(core, "move_absolute", {"targets": {"x": -24950}})["accepted"] is True


def test_preset_positions_stay_in_the_stage_frame():
    # load_sample targets a configured PHYSICAL y; a zeroed y must not shift it.
    core = _zeroed_core(axis="y", user=0.0, physical=40000.0)
    reply = dispatcher.run(core, "load_sample", {})
    assert reply["operation"]["target"] == {"y": 1000.0}


def test_get_limits_reports_the_frame_and_the_active_offsets():
    core = _zeroed_core()
    enforced = dispatcher.run(core, "get_limits", {})["enforced"]
    assert enforced["axes_frame"] == "stage"
    assert enforced["axis_offsets"]["x"] == -24999.0
    assert enforced["axis_offsets"]["y"] == 0.0


def test_startup_self_test_covers_the_zeroed_frame():
    ok, report = commands.self_test(RecordingCore())
    assert ok is True, report
    assert any("zeroed-frame over-max" in line and line.startswith("PASS") for line in report)
    assert any("zeroed-frame relative over-max" in line and line.startswith("PASS") for line in report)


def test_startup_self_test_fails_if_the_zeroed_frame_is_ignored(monkeypatch):
    # Regress the check to the reading-only comparison and the self-test must refuse to go live.
    monkeypatch.setattr(commands, "axis_offsets", lambda core: {axis: 0.0 for axis in config.AXES})
    ok, report = commands.self_test(RecordingCore())
    assert ok is False
    assert any(line.startswith("FAIL") and "zeroed-frame" in line for line in report)
