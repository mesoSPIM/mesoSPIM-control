"""Check the public Remote Control vocabulary and its fail-closed entry points."""

import os
import re
from pathlib import Path

from types import SimpleNamespace

import pytest

from mesoSPIM.src import mesoSPIM_RemoteControl_Commands as commands
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as servers
from mesoSPIM.test.remote_control.support.contracts import EXPECTED_CORE_CALL, VALID_CASES
from mesoSPIM.test.remote_control.support.fakes import RecordingCore


def test_registry_is_the_documented_56_calls():
    assert len(dispatcher.COMMANDS) == 56
    assert set(dispatcher.COMMANDS) == set(VALID_CASES)
    assert "execute_stage_program" not in dispatcher.COMMANDS
    assert "procedure" not in dispatcher.COMMANDS
    assert "set_mode" not in dispatcher.COMMANDS


def test_published_call_list_matches_the_registry():
    repository = Path(__file__).resolve().parents[3]
    text = (repository / "docs" / "source" / "remote_control" / "calls.md").read_text()
    documented = re.findall(r"^\| `([a-z_]+)` \|", text, re.MULTILINE)

    assert len(documented) == len(set(documented)) == 56
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
    # A POST-only JSON-RPC endpoint is the Streamable HTTP shape, first defined in 2025-03-26.
    assert config.MCP_PROTOCOL_VERSION == "2025-03-26"
    assert config.MCP_PROTOCOL_VERSION in config.MCP_SUPPORTED_PROTOCOL_VERSIONS
    assert "2024-11-05" not in config.MCP_SUPPORTED_PROTOCOL_VERSIONS  # that revision is HTTP+SSE
    assert config.MCP_SERVER_NAME
    assert config.MCP_SERVER_VERSION


def test_every_command_publishes_a_schema_that_matches_its_validator():
    """The schema is what an MCP client shows its model; accept() is what runs. They must agree on
    the argument names, and the reviewed valid example of every command must fit its schema."""
    for name, cmd in dispatcher.COMMANDS.items():
        schema = cmd.schema
        assert schema["type"] == "object" and schema["additionalProperties"] is False, name
        properties = schema["properties"]
        example = VALID_CASES[name]
        if not properties:
            assert example == {}, f"{name} takes arguments but publishes none"
        assert set(example) <= set(properties), (name, set(example) - set(properties))
        assert set(schema.get("required", ())) <= set(example), (name, schema.get("required"))
        for key, value in example.items():
            expected = properties[key]["type"]
            actual = {bool: "boolean", int: "integer", float: "number", str: "string", list: "array", dict: "object"}[type(value)]
            assert actual == expected or (expected == "number" and actual == "integer"), (name, key, expected, actual)


def test_schemas_reject_what_accept_rejects():
    """Every command's universal negative case (an unexpected field) is outside its schema too."""
    from mesoSPIM.test.remote_control.support.contracts import UNEXPECTED_ARGUMENT_CASES

    for name, bad in UNEXPECTED_ARGUMENT_CASES.items():
        assert not set(bad) & set(dispatcher.COMMANDS[name].schema["properties"]), name


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


# --- snap: one saved frame, without the GUI prefix dialog ---


def test_snap_saves_one_frame_and_reports_its_path(tmp_path):
    core = RecordingCore()
    reply = dispatcher.run(core, "snap", {"folder": str(tmp_path), "prefix": "remote"})
    assert reply["accepted"] is True
    operation = dispatcher.operation_snapshot(core)
    assert operation["status"] == "completed", operation
    path = operation["result"]["path"]
    assert os.path.isfile(path) and os.path.dirname(path) == str(tmp_path)
    assert os.path.basename(path).startswith("remote_")
    # Captured through Core's own snap, with the GUI save path (prefix dialog) switched off.
    ((_, _, kwargs),) = [c for c in core.calls() if c[0] == "snap"]
    assert kwargs == {"write_flag": False}
    assert core.state["state"] == "idle"
    assert core.state["snap_folder"] == str(tmp_path)


def test_a_second_snap_within_the_same_second_still_counts(tmp_path):
    """The writer names a snap by the second, so two snaps in one second land on one file name; the
    second must be reported as saved, not as "saved nothing". The fake writer's fixed name is that
    collision every time."""
    core = RecordingCore()
    for _ in range(2):
        dispatcher.run(core, "snap", {"folder": str(tmp_path), "prefix": "remote"})
        operation = dispatcher.operation_snapshot(core)
        assert operation["status"] == "completed", operation
        assert os.path.isfile(operation["result"]["path"])
    assert len(os.listdir(tmp_path)) == 1                              # one name, written twice


def test_snap_defaults_to_the_configured_snap_folder():
    core = RecordingCore()
    dispatcher.run(core, "snap", {})
    path = dispatcher.operation_snapshot(core)["result"]["path"]
    assert os.path.dirname(path) == core.state["snap_folder"]


def test_snap_refuses_a_missing_folder_or_a_path_like_prefix(tmp_path):
    core = RecordingCore()
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.run(core, "snap", {"folder": str(tmp_path / "missing")})
    with pytest.raises(dispatcher.ValidationError):
        dispatcher.run(core, "snap", {"prefix": "../escape"})
    assert core.calls() == []


def test_snap_fails_when_no_frame_arrives(monkeypatch):
    monkeypatch.setattr(config, "SNAP_TIMEOUT_SEC", 0.0)
    core = RecordingCore()
    core.snap = lambda write_flag=True: core._record("snap", write_flag=write_flag)  # camera silent
    dispatcher.run(core, "snap", {})
    operation = dispatcher.operation_snapshot(core)
    assert operation["status"] == "failed" and "no frame" in operation["error"]
    assert core.state["state"] == "idle"


# --- Core warnings reach the client ---


class _RefusingCore(RecordingCore):
    """Core.start refusing in preflight: it warns, emits sig_finished, and keeps the run state."""

    def start(self, *args, **kwargs):
        self._record("start", *args, **kwargs)
        self.sig_warning.emit("The following files already exist - stopping! x.raw")
        self.sig_finished.emit()


def test_acceptor_records_core_warnings_for_get_info():
    core = RecordingCore()
    acceptor = servers.Acceptor(core)
    try:
        core.sig_warning.emit("Snap folder not found")
    finally:
        acceptor.stop()
    warnings = dispatcher.run(core, "get_info", {})["warnings"]
    assert warnings == [{"operation": None, "message": "Snap folder not found"}]


def test_preflight_refusal_reports_the_reason():
    core = _RefusingCore()
    acceptor = servers.Acceptor(core)
    try:
        dispatcher.run(core, "run_acquisition_list", {})
    finally:
        acceptor.stop()
    operation = dispatcher.operation_snapshot(core)
    assert operation["status"] == "failed"
    assert operation["warning"] == "The following files already exist - stopping! x.raw"
    assert "files already exist" in operation["error"]
    assert dispatcher.run(core, "get_info", {})["warnings"][-1]["operation"] == operation["id"]


def test_warning_history_is_bounded():
    core = RecordingCore()
    for i in range(dispatcher.MAX_WARNINGS + 5):
        dispatcher.record_warning(core, f"w{i}")
    history = dispatcher.recent_warnings(core)
    assert len(history) == dispatcher.MAX_WARNINGS
    assert history[-1]["message"] == f"w{dispatcher.MAX_WARNINGS + 4}"


REMOTE_RUNS = ("start_live", "start_visual_mode", "start_lightsheet_alignment_mode",
               "run_acquisition_list", "run_selected_acquisition", "acquire_start")


class _WindowBridge:
    """Stands in for the Remote Control tab's run signal and notes how far Core had got."""

    def __init__(self, core):
        self.core = core
        self.emitted = []

    def emit(self, running):
        self.emitted.append((running, len(self.core.calls())))


@pytest.mark.parametrize("name", REMOTE_RUNS)
def test_a_remote_run_puts_the_window_into_run_state_before_core_starts(name):
    """The main window's STOP is enabled only by its own Run handlers, so a run started remotely
    must tell the window, before Core starts, or the operator has no STOP for it."""
    core = RecordingCore()
    bridge = core._remote_control_run_signal = _WindowBridge(core)
    dispatcher.run(core, name, VALID_CASES[name])
    started = [i for i, call in enumerate(core.calls()) if call[0] == EXPECTED_CORE_CALL[name]]
    assert bridge.emitted and bridge.emitted[0][0] is True
    assert bridge.emitted == [(True, bridge.emitted[0][1])]
    assert started and bridge.emitted[0][1] <= started[-1]


class _CoreThatCannotStartLive(RecordingCore):
    def set_state(self, *args, **kwargs):
        raise RuntimeError("camera not ready")


def test_a_remote_run_that_cannot_start_gives_the_window_back():
    """No sig_finished follows a start that raised, so the window must be released here."""
    core = _CoreThatCannotStartLive()
    bridge = core._remote_control_run_signal = _WindowBridge(core)
    dispatcher.run(core, "start_live", {})
    assert [running for running, _ in bridge.emitted] == [True, False]
    assert dispatcher.operation_snapshot(core)["status"] == "failed"


def test_a_preview_leaves_the_window_alone():
    """Preview ends without sig_finished, so upstream's finished() would never release a window
    put into run state for it: only runs that end with sig_finished may lock the window."""
    core = RecordingCore()
    bridge = core._remote_control_run_signal = _WindowBridge(core)
    dispatcher.run(core, "preview_acquisition", VALID_CASES["preview_acquisition"])
    assert bridge.emitted == []


def test_a_core_without_the_tab_runs_without_a_window_bridge():
    core = RecordingCore()
    dispatcher.run(core, "start_live", {})
    assert [call[0] for call in core.calls()].count("set_state") == 1


def test_a_snap_into_a_missing_snap_folder_is_refused_with_the_reason(tmp_path):
    """mesoSPIM's writer swallows the error and only logs it, so a snap into a missing folder saved
    nothing and said nothing: on the Windows demo the assistant could only say "the image writer did
    not save the file". The default folder is checked like an explicit one, before Core runs."""
    core = RecordingCore()
    missing = str(tmp_path / "gone")
    core.state["snap_folder"] = missing
    with pytest.raises(dispatcher.ValidationError, match="snap folder .*gone.* does not exist"):
        dispatcher.run(core, "snap", {})
    assert [call[0] for call in core.calls()] == []


def test_a_snap_the_writer_could_not_save_fails_with_the_writers_reason(tmp_path):
    """mesoSPIM's write_snap_image catches its error and only logs it. The snap is judged by that
    error, not by file times: on Windows two writes within one clock tick share a modification
    time, so a timestamp comparison called a real second snap "saved nothing"."""
    import logging

    class _LoggingWriter:
        def write_snap_image(self, image, prefix=""):
            logging.getLogger("mesoSPIM.src.mesoSPIM_ImageWriter").error("[Errno 28] No space left on device")

    core = RecordingCore()
    core.image_writer = _LoggingWriter()
    dispatcher.run(core, "snap", {"folder": str(tmp_path), "prefix": "remote"})
    operation = dispatcher.operation_snapshot(core)
    assert operation["status"] == "failed"
    assert "No space left on device" in operation["error"]


def test_a_snap_into_a_named_missing_folder_says_how_to_go_on(tmp_path):
    """The refusal said only that the folder did not exist, and on the demo the AI Assistant, asked
    to propose a fix, had none to give (1 of 5). It now names the ways forward, as the refusal for
    a missing snap folder does."""
    core = RecordingCore()
    with pytest.raises(dispatcher.ValidationError) as refused:
        dispatcher.run(core, "snap", {"folder": str(tmp_path / "nowhere")})
    message = str(refused.value)
    assert "nowhere" in message and "does not exist" in message
    assert "pass an existing folder" in message and repr(core.state["snap_folder"]) in message
