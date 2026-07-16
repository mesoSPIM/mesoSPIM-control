"""Opt-in bounded adversarial tests for the real mesoSPIM DemoStage, over the SINGLE bound
transport (MESOSPIM_LIVE_ADVERSARIAL_TRANSPORT in {mcp, tcp}; a live session hosts one transport).

This is the only place the real Acceptor cross-thread marshalling under concurrency is exercised:
the concurrent burst runs entirely on the bound transport (multiple concurrent clients of that one
transport). The cross-transport busy race is impossible live and is proven offline instead.
"""

from __future__ import annotations

import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mesoSPIM.test.remote_control.support.clients import RemoteControl
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as srv
from mesoSPIM.test.remote_control.support.live_session import bounded_delta as _bounded_delta
from mesoSPIM.test.remote_control.support.live_session import demo_acquisition as _demo_acquisition
from mesoSPIM.test.remote_control.support.live_session import live_config as _live_config
from mesoSPIM.test.remote_control.support.live_session import must as _must
from mesoSPIM.test.remote_control.support.live_session import raw_mcp_tool as _raw_tool
from mesoSPIM.test.remote_control.support.live_session import raw_tcp_tool as _raw_tcp_tool
from mesoSPIM.test.remote_control.support.live_session import wait_for_operation as _wait_for_operation
from mesoSPIM.test.remote_control.support.live_session import wait_for_result as _wait_for_result
from mesoSPIM.test.remote_control.support.live_session import wait_until as _wait_until


pytestmark = pytest.mark.live_adversarial

MUTATION_ATTEMPTS = 16
READ_ATTEMPTS = 8
ADMISSION_ATTEMPTS = 10
MAX_WORKERS = 8
REJECTED_REQUEST_TIMEOUT = 2.0


def _selected_transport():
    transport = os.environ.get("MESOSPIM_LIVE_ADVERSARIAL_TRANSPORT", "mcp").lower()
    if transport not in {"mcp", "tcp"}:
        raise ValueError("MESOSPIM_LIVE_ADVERSARIAL_TRANSPORT must be 'mcp' or 'tcp'")
    return transport


def _busy_message(reply):
    return str(reply.get("error", reply)) if isinstance(reply, dict) else str(reply)


def _rejected_tcp_raw(host, port, token, payload):
    """Send a deliberately malformed payload and assert the server refuses it."""
    sock = socket.create_connection((host, int(port)), timeout=REJECTED_REQUEST_TIMEOUT)
    try:
        sock.sendall(srv.frame(token))
        reader = srv.FrameReader(sock)
        assert reader.read().strip() == "OK"
        sock.sendall(srv.frame(payload))
        assert "__MESOSPIM_OK__" not in reader.read()
    finally:
        sock.close()


def _rejected_mcp_raw(host, port, token, body):
    headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://{host}:{port}/mcp", data=body.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REJECTED_REQUEST_TIMEOUT) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == 400


def _make_tool(transport, host, port, token, request_timeout):
    if transport == "mcp":
        if not token:
            pytest.skip("set MESOSPIM_LIVE_MCP_TOKEN for the live MCP server")
        return lambda name, arguments=None: _raw_tool(
            host, port, token, request_timeout, name, arguments
        ), None
    tcp_host = os.environ.get("MESOSPIM_LIVE_TCP_HOST", "127.0.0.1")
    tcp_port = os.environ.get("MESOSPIM_LIVE_TCP_PORT")
    tcp_token = os.environ.get("MESOSPIM_LIVE_TCP_TOKEN")
    if tcp_host not in {"127.0.0.1", "localhost"} or not tcp_port or not tcp_token:
        pytest.skip("set loopback MESOSPIM_LIVE_TCP_PORT and MESOSPIM_LIVE_TCP_TOKEN")

    def tool(name, arguments=None):
        # Normal authenticated calls use the configured live-operation timeout. The two-second
        # hostile-input bound belongs only to deliberately rejected raw frames above; applying it
        # here made a fresh TCP authentication race a finishing acquisition and masked cleanup.
        client = RemoteControl(tcp_host, int(tcp_port), tcp_token, timeout=request_timeout)
        try:
            return _raw_tcp_tool(client, name, arguments)
        finally:
            client.close()

    return tool, (tcp_host, tcp_port, tcp_token)


def _wait_for_failed_operation(tool, started, label):
    operation_id = started["operation"]["id"]

    def terminal():
        operation = _must(tool, "get_progress")["operation"]
        if operation.get("id") != operation_id:
            raise AssertionError(f"{label} operation changed from {operation_id} to {operation.get('id')}")
        return operation if operation.get("status") in {"completed", "failed"} else None

    operation = _wait_until(terminal, f"{label} terminal operation")
    assert operation["status"] == "failed", operation
    assert "preflight" in operation.get("error", "").lower(), operation
    return operation


def test_real_demo_rejects_hostile_api_corpus_and_recovers():
    """Try to break the bound live API, proving refusals leave DemoStage unchanged."""
    host, port, token, _hold, request_timeout, _root, _etl, _pid = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()
    tool, tcp = _make_tool(transport, host, port, token, request_timeout)

    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live adversarial attacks outside DemoStage")
    state_keys = [
        "state",
        "position",
        "intensity",
        "filter",
        "zoom",
        "laser",
        "shutterconfig",
        "shutterstate",
        "camera_exposure_time",
        "etl_l_delay_%",
        "galvo_l_duty_cycle",
        "laser_l_delay_%",
    ]
    original = _must(tool, "get_state_all", {"keys": state_keys})
    assert original["state"] == "idle"

    attacks = [(name, {}) for name in ("__class__", "__globals__", "eval", "os.system")]
    command_names = _must(tool, "get_capabilities")["commands"]
    # The valid live sweep supplies a reviewed good payload for every command. Pair it here with a
    # universal bad payload: every exact command must reject an extra/misspelled field as validation
    # before any handler or hardware call runs.
    attacks.extend((name, {"__unexpected__": True}) for name in command_names)
    position = original["position"]
    for axis, bounds in limits["enforced"]["axes"].items():
        if bounds:
            attacks.append(("move_absolute", {"targets": {axis: bounds[1] + 1}}))
            attacks.append(("move_absolute", {"targets": {axis: bounds[0] - 1}}))
            attacks.append(("move_relative", {"deltas": {axis: bounds[1] - position[axis + "_pos"] + 1}}))
            attacks.append(("move_relative", {"deltas": {axis: bounds[0] - position[axis + "_pos"] - 1}}))
    # Every BOUNDED hardware parameter (voltages, frequency, phase, camera/scan timings, percents)
    # must refuse a value one step past its enforced range, exercising every reported parameter
    # bounds on real hardware, derived from what get_limits actually reports (not hardcoded). Both the
    # grouped path (set_state) and the dedicated setter are hit.
    _setter_for = {"camera_exposure_time": "set_camera", "sweeptime": "set_state"}
    for key, spec in limits["enforced"]["parameters"].items():
        rng = spec.get("range")
        if not rng or spec.get("type") != "number":
            continue
        setter = _setter_for.get(
            key,
            "set_etl"
            if key.startswith("etl_")
            else "set_galvo"
            if key.startswith("galvo_")
            else "set_laser_timing"
            if key.startswith("laser_")
            else "set_intensity"
            if key == "intensity"
            else "set_state",
        )
        for bad in (rng[1] + 1, rng[0] - 1):
            payload = {"intensity": bad} if key == "intensity" else {key: bad}
            attacks.append((setter, payload if setter != "set_state" else {"settings": {key: bad}}))
            if setter != "set_state":
                attacks.append(("set_state", {"settings": {key: bad}}))  # same generic-setter bound

    # The guarded recovery command must be a safe no-op while the microscope is idle (it may only free
    # the gate when the core is INDEPENDENTLY idle, and there is no wedged op here). It is NOT hostile,
    # so it is verified separately below rather than in the "must be rejected" corpus.
    x_too_high = limits["enforced"]["axes"]["x"][1] + 1
    attacks.extend(
        [
            ("move_absolute", {"targets": {"not_an_axis": 1}}),
            ("move_absolute", {"targets": {}}),
            ("set_intensity", {"intensity": True}),
            ("set_intensity", {"intensity": 101}),
            ("set_filter", {"filter": "__missing_filter__"}),
            ("set_state", {"settings": {"x_max": 999999999}}),
            ("set_state", {"settings": {"state": "__invalid_remote_state__"}}),
            ("set_camera", {"camera_exposure_time": "instant"}),
            ("set_camera", {"camera_delay_%": -1}),
            ("set_etl", {"etl_l_delay_%": -1}),
            ("set_galvo", {"galvo_l_duty_cycle": 101}),
            ("set_laser_timing", {"laser_l_delay_%": -1}),
            ("set_acquisition_list", {"acquisitions": "not-a-list"}),
            ("set_acquisition_list", {"acquisitions": [{"intensity": 101}], "selected_row": 0}),
            ("set_acquisition_list", {"acquisitions": [{"x_pos": x_too_high}], "selected_row": 0}),
            ("set_acquisition_list", {"acquisitions": [{}], "selected_row": -1}),
            ("acquire_start", {"acquisition": []}),
            ("acquire_start", {"acquisition": {"intensity": 101}}),
            ("acquire_start", {"acquisition": {"x_pos": x_too_high}}),
            ("run_selected_acquisition", {"row": -1}),
            ("preview_acquisition", {"row": -1}),
            ("time_lapse_start", {"timepoints": 0, "interval_sec": 0}),
            ("time_lapse_start", {"timepoints": 1, "interval_sec": -1}),
            ("set_state", {"settings": {"state": "live"}}),  # 'state' is not a settable key
        ]
    )
    assert len(attacks) <= 256

    try:
        for name, arguments in attacks:
            ok, reply = tool(name, arguments)
            assert not ok, f"{transport} accepted hostile {name}: {arguments!r} -> {reply!r}"
            if arguments == {"__unexpected__": True}:
                assert "validation" in str(reply).lower(), (name, reply)

        raw_count = 0
        if transport == "tcp":
            _, tcp_port, tcp_token = tcp
            for payload in (
                '{"ping":{},"get_state":{}}',
                '{"set_intensity":{"intensity":1},"set_intensity":{"intensity":2}}',
                '{"set_intensity":{"intensity":NaN}}',
                "[]",
            ):
                _rejected_tcp_raw("127.0.0.1", tcp_port, tcp_token, payload)
                raw_count += 1
        else:
            for body in (
                "{",
                '{"jsonrpc":"2.0","id":1,"method":"tools/list","method":"tools/call"}',
                '{"jsonrpc":"2.0","id":NaN,"method":"tools/list"}',
            ):
                _rejected_mcp_raw(host, port, token, body)
                raw_count += 1

        after = _must(tool, "get_state_all", {"keys": state_keys})
        assert after == original

        # Guarded recovery is a safe no-op while idle; it must not free a gate that
        # nothing holds, and it must not touch hardware.
        recovered = _must(tool, "clear_stuck_operation")
        assert recovered["cleared"] is False, recovered
        assert _must(tool, "get_state_all", {"keys": state_keys}) == original

        ok, hello = tool("hello", {})
        assert ok and hello["app"] == "mesoSPIM-control"
        print(
            f"LIVE HOSTILE API CORPUS VERIFIED: {len(attacks) + raw_count} rejected attacks; "
            f"hardware-parameter bounds enforced; guarded recovery idle-safe; "
            f"state unchanged; {transport} healthy",
            flush=True,
        )
    finally:
        for name, arguments in (
            ("stop_activity", {}),
            (
                "move_absolute",
                {
                    "targets": {
                        axis: original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f", "theta")
                    }
                },
            ),
            ("set_filter", {"filter": original["filter"], "wait": True}),
            ("set_zoom", {"zoom": original["zoom"], "wait": True, "update_etl": False}),
            ("set_laser", {"laser": original["laser"], "wait": True, "update_etl": False}),
            ("set_intensity", {"intensity": original["intensity"], "wait": True}),
            ("set_shutterconfig", {"shutterconfig": original["shutterconfig"]}),
        ):
            try:
                cleanup = _must(tool, name, arguments)
                _wait_for_operation(tool, cleanup, f"hostile corpus cleanup {name}")
            except Exception:
                pass


def test_real_demo_busy_gate_survives_bounded_single_transport_concurrency():
    """Race a free gate, then stress one active operation with mixed reads and mutations."""
    host, port, token, _hold, request_timeout, _root, _etl, process_id = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()

    # The burst needs many concurrent clients of the ONE bound transport, so build a per-call tool.
    if transport == "mcp":
        if not token:
            pytest.skip("set MESOSPIM_LIVE_MCP_TOKEN for the live MCP server")
        burst_call = lambda name, arguments=None: _raw_tool(
            host, port, token, request_timeout, name, arguments
        )
    else:
        tcp_host = os.environ.get("MESOSPIM_LIVE_TCP_HOST", "127.0.0.1")
        tcp_port = os.environ.get("MESOSPIM_LIVE_TCP_PORT")
        tcp_token = os.environ.get("MESOSPIM_LIVE_TCP_TOKEN")
        if tcp_host not in {"127.0.0.1", "localhost"} or not tcp_port or not tcp_token:
            pytest.skip("set loopback MESOSPIM_LIVE_TCP_PORT and MESOSPIM_LIVE_TCP_TOKEN")

        def burst_call(name, arguments=None):
            client = RemoteControl(tcp_host, int(tcp_port), tcp_token, timeout=request_timeout)
            try:
                return _raw_tcp_tool(client, name, arguments)
            finally:
                client.close()

    tool = burst_call
    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live adversarial stress outside DemoStage")

    sentinel = Path(tempfile.gettempdir()) / (f".mesospim_demo_busy_stress_{process_id}_{transport}.done")
    if sentinel.exists():
        pytest.skip(f"live busy stress already ran for PID {process_id}, transport={transport}")
    sentinel.write_text("bounded live busy stress started\n", encoding="utf-8")

    state_keys = [
        "state",
        "position",
        "laser",
        "intensity",
        "filter",
        "zoom",
        "shutterconfig",
        "etl_l_offset",
        "etl_l_amplitude",
        "etl_r_offset",
        "etl_r_amplitude",
    ]
    original = _must(tool, "get_state_all", {"keys": state_keys})
    assert original["state"] == "idle"
    original_acquisitions = _must(tool, "get_acquisition_list")["acquisitions"]
    alternate_intensity = _bounded_delta(original["intensity"], 0, 100, 1)
    temp_folder = Path(tempfile.mkdtemp(prefix="mesospim_demo_busy_stress_"))
    acquisition = _demo_acquisition(temp_folder, "busy-stress.raw", original)
    z_start = float(acquisition["z_start"])
    z_limit = limits["enforced"]["axes"]["z"]
    if not z_limit:
        pytest.fail("demo Z axis has no enforced range")
    z_end = z_start + 4 if z_start + 4 <= z_limit[1] else z_start - 4
    if z_end < z_limit[0]:
        pytest.fail("demo Z range is too small for the five-plane busy stress acquisition")
    acquisition.update({"z_end": z_end, "planes": 5})
    accepted = None

    try:
        # Race ten valid mutations against a free gate. start_live holds the winning operation open
        # until an emergency stop, so no later socket event can win merely because a short action
        # completed first. Exactly one call must reserve the operation; every other call sees busy.
        admission_release = threading.Event()

        def attempt_admission():
            admission_release.wait()
            return burst_call("start_live", {})

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            admission_futures = [executor.submit(attempt_admission) for _ in range(ADMISSION_ATTEMPTS)]
            admission_release.set()
            admission_results = [future.result() for future in admission_futures]

        winners = [reply for ok, reply in admission_results if ok]
        refusals = [reply for ok, reply in admission_results if not ok]
        assert len(winners) == 1, admission_results
        assert len(refusals) == ADMISSION_ATTEMPTS - 1, admission_results

        winning_operation = winners[0]["operation"]
        assert winning_operation["command"] == "start_live"
        assert winning_operation["status"] == "processing"
        for refusal in refusals:
            error = _busy_message(refusal)
            assert "busy" in error
            assert winning_operation["id"] in error

        progress = _must(tool, "get_progress")["operation"]
        assert progress["id"] == winning_operation["id"]
        stopped = _must(tool, "stop_activity")
        _wait_for_operation(tool, stopped, "free-gate admission-race stop")
        _wait_until(
            lambda: _must(tool, "get_state")["state"] == "idle",
            "idle state after free-gate admission race",
        )
        print(
            f"LIVE ADMISSION RACE VERIFIED: 1 mutation accepted, "
            f"{ADMISSION_ATTEMPTS - 1} rejected busy; transport={transport}",
            flush=True,
        )

        installed = _must(tool, "set_acquisition_list", {"acquisitions": [acquisition], "selected_row": 0})
        _wait_for_operation(tool, installed, "busy stress list install")
        accepted = _must(tool, "run_acquisition_list")
        operation = accepted["operation"]
        assert operation["status"] == "processing"

        attempts = []
        for index in range(MUTATION_ATTEMPTS):
            attempts.append("mutation")
            if index < READ_ATTEMPTS:
                attempts.append("read")
        release = threading.Event()

        def attempt(kind):
            release.wait()
            started = time.perf_counter()
            name = "set_intensity" if kind == "mutation" else "get_progress"
            arguments = {"intensity": alternate_intensity, "wait": True} if kind == "mutation" else {}
            ok, reply = burst_call(name, arguments)
            return kind, ok, reply, time.perf_counter() - started

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(attempt, item) for item in attempts]
            release.set()
            results = [future.result() for future in futures]

        for kind, ok, reply, _latency in results:
            if kind == "mutation":
                assert not ok, reply
                error = _busy_message(reply)
                assert "busy" in error  # new wire text: 'busy: <cmd> (<id>) ...'
                assert operation["command"] in error  # names the running command
                assert operation["id"] in error  # names the running op id
            else:
                assert ok, reply
                assert reply["operation"]["id"] == operation["id"]
                assert reply["operation"]["status"] == "processing"

        unchanged = _must(tool, "get_state_all", {"keys": ["intensity"]})
        assert unchanged["intensity"] == original["intensity"]
        _wait_for_operation(tool, accepted, "busy stress acquisition")

        ok, reopened = burst_call("set_intensity", {"intensity": alternate_intensity, "wait": True})
        assert ok, reopened
        _wait_for_operation(tool, reopened, "busy stress post-gate intensity")
        restored = _must(tool, "set_intensity", {"intensity": original["intensity"], "wait": True})
        _wait_for_operation(tool, restored, "busy stress intensity restoration")
        print(
            f"LIVE BUSY STRESS VERIFIED: {MUTATION_ATTEMPTS} mutations rejected, "
            f"{READ_ATTEMPTS} reads served, transport={transport}",
            flush=True,
        )
    finally:
        if accepted is not None:
            try:
                _wait_for_operation(tool, accepted, "busy stress cleanup")
            except Exception:
                pass
        for name, arguments in (
            ("stop_activity", {}),
            ("set_intensity", {"intensity": original["intensity"], "wait": True}),
            (
                "move_absolute",
                {
                    "targets": {
                        axis: original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f", "theta")
                    }
                },
            ),
            ("set_acquisition_list", {"acquisitions": original_acquisitions, "selected_row": 0}),
        ):
            try:
                cleanup = _must(tool, name, arguments)
                _wait_for_operation(tool, cleanup, f"busy stress cleanup {name}")
            except Exception:
                pass
        shutil.rmtree(temp_folder, ignore_errors=True)

    final = _must(tool, "get_state_all", {"keys": ["intensity", "position"]})
    assert final["intensity"] == original["intensity"]
    assert final["position"] == original["position"]


def test_real_demo_acquisition_completes_and_recovery_is_guarded():
    """A remote acquisition must complete without wedging, and guarded recovery must refuse to
    clear genuinely running work. ``acquire_start`` restores the operator's list through
    ``acquire_finish``. This is the live validation of the operation-completion model."""
    host, port, token, _hold, request_timeout, root, _etl, process_id = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()
    tool, _tcp = _make_tool(transport, host, port, token, request_timeout)

    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live acquisition test outside DemoStage")

    keys = [
        "state",
        "position",
        "laser",
        "intensity",
        "filter",
        "zoom",
        "shutterconfig",
        "etl_l_offset",
        "etl_l_amplitude",
        "etl_r_offset",
        "etl_r_amplitude",
    ]
    state = _must(tool, "get_state_all", {"keys": keys})
    assert state["state"] == "idle"
    folder = Path(tempfile.mkdtemp(prefix=f"mesospim_acquire_{process_id}_", dir=root))
    acquisition = _demo_acquisition(folder, "remote_control_probe.raw", state)
    started = None

    try:
        started = _must(tool, "acquire_start", {"acquisition": acquisition})
        assert started["operation"]["status"] == "processing"

        # If we catch it running, Core must report a run state because the remote command is no
        # longer idle mid-acquisition. Guarded recovery must refuse to clear genuinely active work.
        # This observation is best-effort because a one-plane demo may finish before the first poll;
        # the hard guarantee is that the operation reaches a terminal state.
        if _must(tool, "get_progress")["operation"].get("status") == "processing":
            assert _must(tool, "get_state")["state"] in ("run_acquisition_list", "run_selected_acquisition")
            assert _must(tool, "clear_stuck_operation")["cleared"] is False  # never abort a live run

        _wait_for_operation(tool, started, "remote acquire_start")  # HARD: it completes, never wedges
    finally:
        # A polling/client failure must not make acquire_finish race the still-running WAIT and then
        # mask the original error with BusyError. Wait for terminal state before restoring the list.
        if started is not None:
            _wait_for_operation(tool, started, "remote acquire_start cleanup")
        finished = _must(tool, "acquire_finish")  # restore the operator's list
        _wait_for_operation(tool, finished, "acquire_finish restoration")
        shutil.rmtree(folder, ignore_errors=True)

    assert not folder.exists()
    assert _must(tool, "get_state")["state"] == "idle"
    assert _must(tool, "clear_stuck_operation")["cleared"] is False  # a safe no-op once idle
    print(
        f"LIVE ACQUISITION LIFECYCLE VERIFIED: acquire_start completed on {transport}; "
        f"run-state reported; recovery guarded; operator list restored",
        flush=True,
    )


def test_real_demo_preflight_refusals_are_failed_terminal_and_recoverable(request):
    """Exercise upstream's early sig_finished refusal branches without allowing a gate wedge."""
    host, port, token, _hold, request_timeout, root, _etl, process_id = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()
    tool, tcp = _make_tool(transport, host, port, token, request_timeout)
    persistent_client = None
    connection_mode = os.environ.get("MESOSPIM_LIVE_TCP_PERSISTENT_CLIENT", "0")
    if connection_mode not in {"0", "1"}:
        raise ValueError("MESOSPIM_LIVE_TCP_PERSISTENT_CLIENT must be 0 or 1")
    if transport == "tcp" and connection_mode == "1":
        tcp_host, tcp_port, tcp_token = tcp
        persistent_client = RemoteControl(tcp_host, int(tcp_port), tcp_token, timeout=request_timeout)
        request.addfinalizer(persistent_client.close)

        def tool(name, arguments=None):
            return _raw_tcp_tool(persistent_client, name, arguments)

    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live preflight tests outside DemoStage")

    keys = [
        "state",
        "position",
        "laser",
        "intensity",
        "filter",
        "zoom",
        "shutterconfig",
        "etl_l_offset",
        "etl_l_amplitude",
        "etl_r_offset",
        "etl_r_amplitude",
    ]
    original_state = _must(tool, "get_state_all", {"keys": keys})
    original_list = _must(tool, "get_acquisition_list")["acquisitions"]
    folder = Path(tempfile.mkdtemp(prefix=f"mesospim_preflight_{process_id}_", dir=root))
    existing = folder / "already-exists.raw"
    existing.write_bytes(b"do not overwrite")
    cases = []
    for case, target_folder, filename in (
        ("missing folder", folder / "missing", "missing.raw"),
        ("existing file", folder, existing.name),
        ("missing extension", folder, "no-extension"),
    ):
        acquisition = _demo_acquisition(target_folder, filename, original_state)
        cases.append((case, acquisition))
    verified = 0

    try:
        for case, acquisition in cases:
            started = _must(tool, "acquire_start", {"acquisition": acquisition})
            assert started["operation"]["status"] == "processing"
            _wait_for_failed_operation(tool, started, case)
            assert _must(tool, "get_state")["state"] == "idle"
            finished = _must(tool, "acquire_finish")
            _wait_for_operation(tool, finished, f"{case} acquire_finish")
            assert _must(tool, "get_acquisition_list")["acquisitions"] == original_list
            assert _must(tool, "clear_stuck_operation")["cleared"] is False
            verified += 1

        duplicate = _demo_acquisition(folder, "duplicate.raw", original_state)
        installed = _must(
            tool, "set_acquisition_list", {"acquisitions": [duplicate, dict(duplicate)], "selected_row": 0}
        )
        _wait_for_operation(tool, installed, "duplicate-list install")
        started = _must(tool, "run_acquisition_list")
        _wait_for_failed_operation(tool, started, "duplicate filenames")
        assert _must(tool, "get_state")["state"] == "idle"
        verified += 1

        # Exercise the disk-space preflight only when the reported free/required values prove that
        # upstream will refuse it. The million-plane ceiling keeps this bounded and no image is taken.
        z_low, z_high = limits["enforced"]["axes"]["z"]
        z_start = float(original_state["position"]["z_pos"])
        z_end = z_high if z_start != z_high else z_low
        if z_end != z_start:
            planes = 1_000_000
            disk_pressure = _demo_acquisition(folder, "disk-pressure.raw", original_state)
            disk_pressure.update(
                {
                    "z_end": z_end,
                    "z_step": abs(z_end - z_start) / (planes - 1),
                    "planes": planes,
                }
            )
            disk = _must(tool, "get_disk_space", {"acquisitions": [disk_pressure]})
            if disk["free_bytes"] < disk["required_bytes"] * 1.1:
                installed = _must(
                    tool, "set_acquisition_list", {"acquisitions": [disk_pressure], "selected_row": 0}
                )
                _wait_for_operation(tool, installed, "disk-pressure list install")
                started = _must(tool, "run_acquisition_list")
                _wait_for_failed_operation(tool, started, "insufficient disk space")
                assert _must(tool, "get_state")["state"] == "idle"
                verified += 1
    finally:
        try:
            finished = _must(tool, "acquire_finish")
            _wait_for_operation(tool, finished, "preflight cleanup acquire_finish")
        except Exception:
            pass
        try:
            restored = _must(tool, "set_acquisition_list", {"acquisitions": original_list, "selected_row": 0})
            _wait_for_operation(tool, restored, "preflight cleanup list restoration")
        except Exception:
            pass
        shutil.rmtree(folder, ignore_errors=True)

    assert existing.exists() is False  # temp tree removed; user data was never touched
    assert _must(tool, "get_state")["state"] == "idle"
    mode = "persistent" if persistent_client is not None else "reconnect-per-call"
    print(
        f"LIVE PREFLIGHT RECOVERY VERIFIED: {verified} upstream refusals became failed terminal "
        f"operations; list restored; transport={transport}; connection_mode={mode}",
        flush=True,
    )


def test_real_demo_native_acquisition_list_round_trips_exactly():
    """Reinstall mesoSPIM's own rows verbatim, including its planes/geometry metadata mismatch."""
    host, port, token, _hold, request_timeout, _root, _etl, _process_id = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()
    tool, _tcp = _make_tool(transport, host, port, token, request_timeout)
    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live acquisition-list test outside DemoStage")
    assert _must(tool, "get_state")["state"] == "idle"

    original = _must(tool, "get_acquisition_list")["acquisitions"]
    if not original:
        pytest.skip("the live acquisition list is empty; no native row is available to round-trip")

    try:
        installed = _must(tool, "set_acquisition_list", {"acquisitions": original})
        result = _wait_for_result(tool, installed, "native list install")
        assert result["count"] == len(original)
        assert _must(tool, "get_acquisition_list")["acquisitions"] == original
    finally:
        # Omitting selected_row preserves the operator's current table selection.
        restored = _must(tool, "set_acquisition_list", {"acquisitions": original})
        _wait_for_operation(tool, restored, "native list restoration")

    print(f"LIVE NATIVE LIST ROUND TRIP VERIFIED: {len(original)} row(s); transport={transport}", flush=True)


def test_real_demo_time_lapse_idle_gap_cannot_be_mistaken_for_a_wedge():
    """After point 0, Core is idle while the time lapse is still active; recovery must refuse."""
    host, port, token, _hold, request_timeout, root, _etl, process_id = _live_config(
        "MESOSPIM_RUN_LIVE_ADVERSARIAL"
    )
    transport = _selected_transport()
    tool, _tcp = _make_tool(transport, host, port, token, request_timeout)
    limits = _must(tool, "get_limits")
    if (limits.get("stage") or {}).get("stage_type") != "DemoStage":
        pytest.fail("refusing live time-lapse test outside DemoStage")

    keys = [
        "state",
        "position",
        "laser",
        "intensity",
        "filter",
        "zoom",
        "shutterconfig",
        "etl_l_offset",
        "etl_l_amplitude",
        "etl_r_offset",
        "etl_r_amplitude",
    ]
    original_state = _must(tool, "get_state_all", {"keys": keys})
    original_list = _must(tool, "get_acquisition_list")["acquisitions"]
    folder = Path(tempfile.mkdtemp(prefix=f"mesospim_timelapse_{process_id}_", dir=root))
    acquisition = _demo_acquisition(folder, "idle-gap.raw", original_state)
    started = None

    try:
        installed = _must(tool, "set_acquisition_list", {"acquisitions": [acquisition], "selected_row": 0})
        _wait_for_operation(tool, installed, "time-lapse list install")
        started = _must(tool, "time_lapse_start", {"timepoints": 2, "interval_sec": 10})
        operation_id = started["operation"]["id"]
        observation = {}

        def first_point_finished_and_waiting():
            operation = _must(tool, "get_progress")["operation"]
            state = _must(tool, "get_state")["state"]
            outputs = sorted(path.name for path in folder.iterdir())
            observation.update(state=state, operation=operation, outputs=outputs)
            first_output_exists = any("_Time000" in name for name in outputs)
            return (
                first_output_exists
                and state == "idle"
                and operation.get("id") == operation_id
                and operation.get("status") == "processing"
            )

        try:
            _wait_until(first_point_finished_and_waiting, "time lapse idle interval after point 0")
        except AssertionError as exc:
            raise AssertionError(f"{exc}; last observation={observation!r}") from exc
        recovery = _must(tool, "clear_stuck_operation")
        assert recovery["cleared"] is False
        assert "time lapse is still active" in recovery["reason"]
        _must(tool, "time_lapse_stop")

        def terminal_operation():
            operation = _must(tool, "get_progress")["operation"]
            return operation if operation.get("status") in {"completed", "failed"} else None

        terminal = _wait_until(terminal_operation, "time lapse cancellation")
        assert terminal["id"] == operation_id and terminal.get("stop_requested") is True
    finally:
        try:
            _must(tool, "time_lapse_stop")
        except Exception:
            pass
        if started is not None:
            try:
                _must(tool, "stop_activity")
            except Exception:
                pass
        try:
            restored = _must(tool, "set_acquisition_list", {"acquisitions": original_list, "selected_row": 0})
            _wait_for_operation(tool, restored, "time-lapse list restoration")
        except Exception:
            pass
        shutil.rmtree(folder, ignore_errors=True)

    assert _must(tool, "get_state")["state"] == "idle"
    print(
        f"LIVE TIME-LAPSE GAP VERIFIED: recovery refused between points; explicit stop completed; "
        f"transport={transport}",
        flush=True,
    )
