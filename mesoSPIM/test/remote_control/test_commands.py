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


def test_default_password_is_refused_outside_loopback():
    with pytest.raises(ValueError):
        servers.start(object(), "MCP", "0.0.0.0", 0, config.DEFAULT_TOKEN)
