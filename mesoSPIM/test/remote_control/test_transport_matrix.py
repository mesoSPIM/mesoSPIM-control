"""Verify every command's reply kind and expected Core call over both transports."""

from __future__ import annotations

import pytest

from mesoSPIM.test.remote_control.support.harness import Harness
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.test.remote_control.support.contracts import (
    VALID_CASES,
    EXPECTED_CORE_CALL,
    READ_ONLY_WITHOUT_CORE_CALL,
)

READ, ACTION, WAIT, EMERGENCY = dispatcher.READ, dispatcher.ACTION, dispatcher.WAIT, dispatcher.EMERGENCY
_SPECIAL = {"set_acquisition_list", "acquire_finish"}  # neither contract table; ordinary ACTIONs
_INLINE_FAKE_TIMER = {
    "move_absolute",
    "move_relative",
    "load_sample",
    "unload_sample",
    "center_sample",
}

# The RecordingCore records these three as calls (EXPECTED_CORE_CALL needs the record) but they are
# non-actuating READS. Every other recorded call moves hardware, so filtering them out lets the
# matrix assert the expected call is the ONLY actuation — catching a handler that also fires a stray,
# safety-relevant Core call on the happy path.
_NON_MUTATING_RECORDED = {"get_free_disk_space", "get_required_disk_space", "check_motion_limits"}

_harness = Harness()


def teardown_module(_module=None):
    _harness.stop()


def _expected_status(name):
    """The envelope classifies by cmd.kind, NOT by contract-table membership. TRAP: stop_activity
    is in READ_ONLY_WITHOUT_CORE_CALL yet is EMERGENCY, so it returns a WRAPPED idle envelope."""
    kind = dispatcher.COMMANDS[name].kind
    if kind == ACTION:
        # The offline Qt shim executes the scheduled action inline. Real Qt always returns the
        # processing acknowledgement first; the dedicated ordering and real-PyQt tests prove it.
        return "completed"
    if kind == EMERGENCY:
        return "idle"  # _active is None -> _public(None) == idle
    if kind == WAIT:
        # The offline Qt shim executes timer callbacks inline. Real Qt returns these stage calls as
        # processing before it runs the zero-delay move callback; the real-PyQt smoke covers that
        # ordering. Here the fake move and its readback poll have already completed.
        return "completed" if name == "preview_acquisition" or name in _INLINE_FAKE_TIMER else "processing"
    return None  # READ -> bare payload, no operation wrapper


@pytest.mark.parametrize("transport", ["mcp", "tcp"])
@pytest.mark.parametrize("name", sorted(VALID_CASES))
def test_command_over_both_lanes(transport, name):
    _harness.reset()

    ok, payload = _harness.invoke(transport, name, VALID_CASES[name])
    assert ok, (transport, name, payload)
    assert isinstance(payload, dict), (transport, name, payload)

    expected = _expected_status(name)
    if expected is None:  # a READ is bare: no envelope wrapper. Some
        assert "accepted" not in payload, payload  # read docs embed an "operation" field as
    else:  # data, so only "accepted" marks the wrapper.
        assert payload["accepted"] is True, payload
        assert payload["operation"]["status"] == expected, (name, payload["operation"])

    call_names = [c[0] for c in _harness.core.calls()]
    mutating = [c for c in call_names if c not in _NON_MUTATING_RECORDED]
    if name in EXPECTED_CORE_CALL:
        expected_call = EXPECTED_CORE_CALL[name]
        assert expected_call in call_names, (transport, name, call_names)
        # the expected call must be the ONLY actuation — a stray hardware call must not slip through
        assert mutating == ([] if expected_call in _NON_MUTATING_RECORDED else [expected_call]), (
            transport,
            name,
            call_names,
        )
    else:  # READ_ONLY or _SPECIAL: no actuation
        assert mutating == [], (transport, name, call_names)


def test_contract_tables_partition_the_vocabulary():
    """Completeness guard: the three buckets exactly cover the 53 commands, once each."""
    classified = set(EXPECTED_CORE_CALL) | READ_ONLY_WITHOUT_CORE_CALL | _SPECIAL
    assert classified == set(VALID_CASES)
    assert set(VALID_CASES) == set(dispatcher.COMMANDS)
    assert len(VALID_CASES) == 53
