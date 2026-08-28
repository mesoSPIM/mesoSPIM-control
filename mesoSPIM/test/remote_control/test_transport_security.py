"""Exercise transport security, protocol boundaries, and hostile inputs over TCP and MCP.

Each attack class has a named test so failures identify the broken boundary. This suite proves that
the packaged transports reject the same inputs end to end. Every corpus is bounded and network
waits are limited to 0.6 seconds.

The three MCP request helpers cover different layers. ``_h.invoke`` exercises normal tool calls,
``_jsonrpc`` checks HTTP status and JSON-RPC handling, and ``_raw`` sends wire shapes that standard
HTTP clients cannot produce, such as duplicate length headers. Keeping them separate preserves that
coverage.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from mesoSPIM.test.remote_control.live import test_adversarial as live_adversarial
from mesoSPIM.test.remote_control.support.harness import Harness, TOKEN, last_frame
from mesoSPIM.test.remote_control.support.fakes import RecordingCore
from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src import mesoSPIM_RemoteControl_Dispatcher as dispatcher
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as srv
from mesoSPIM.test.remote_control.support.contracts import UNEXPECTED_ARGUMENT_CASES, VALID_CASES
from mesoSPIM.test.remote_control.support import live_session

REQUEST_TIMEOUT = 0.6

_h = Harness()


def teardown_module(_module=None):
    _h.stop()


@pytest.fixture(autouse=True)
def _fresh_core():
    _h.reset()


def _refused(lane, name, args, code=None):
    """Invoke and assert a typed refusal that never touched the Core."""
    before = _h.core.calls()
    ok, payload = _h.invoke(lane, name, args)
    assert not ok, (lane, name, payload)
    if code is not None:
        assert payload["code"] == code, (lane, name, payload)
    assert _h.core.calls() == before, (lane, name, _h.core.calls())
    return payload


def _both(name, args, code=None):
    return {lane: _refused(lane, name, args, code) for lane in ("mcp", "tcp")}


# --- raw HTTP helpers over the live MCP loopback (custom Origin / Authorization / headers) ---


def _jsonrpc(port, obj, *, token=TOKEN):
    body = json.dumps(obj).encode("utf-8")
    headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1"}  # always a good origin
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as reply:
            return reply.status, json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, None


def _raw(body, *, auth, origin="http://127.0.0.1", extra=(), shutdown_write=False):
    headers = ["Content-Type: application/json"]
    if origin is not None:
        headers.append(f"Origin: {origin}")
    if auth is not None:
        headers.append(f"Authorization: {auth}")
    headers.extend(extra)
    status, _ = _h.mcp.raw(headers, body, shutdown_write=shutdown_write, timeout=REQUEST_TIMEOUT)
    return status


# ============================ representative attack classes ============================


def test_hostile_names_refused_both_lanes():
    for name in ("__class__", "os.system('x')", "move_absolute\x00", "A" * 4096):
        for lane in ("mcp", "tcp"):
            payload = _refused(lane, name, {})
            assert payload["code"] in ("unknown_command", "validation"), (name, payload)


@pytest.mark.parametrize("name", sorted(UNEXPECTED_ARGUMENT_CASES))
def test_every_command_rejects_unexpected_input_over_both_lanes(name):
    _both(name, UNEXPECTED_ARGUMENT_CASES[name], code="validation")


def test_malformed_envelopes_refused():
    _both("move_absolute", {"targets": 5})  # non-object args value
    for lane in ("mcp", "tcp"):
        # a multi-key / non-object / bare-scalar envelope is rejected at parse_call. Drive the raw
        # wire so the envelope itself is malformed, not just an argument.
        if lane == "tcp":
            for bad in ('{"a":{},"b":{}}', "[]", "null", '""'):
                conn = _h.tcp.new_conn(authed=True)
                _h.tcp.adapter._handle(conn, bad)
                assert not last_frame(conn).startswith(config.OK_MARKER), bad
        else:
            for bad in ('{"a":{},"b":{}}', "[]", "null", '""'):
                status, reply = _jsonrpc(
                    _h.mcp.port,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "move_absolute", "arguments": bad},
                    },
                )
                assert status == 200 and reply["result"]["isError"] is True, bad
    assert _h.core.calls() == []


def test_mcp_rejects_non_object_arguments():
    # MCP once coerced a falsy non-object (`[]`) to {} and accepted it, while TCP rejected
    # the analogous call. Both must now refuse it, and the Core must stay untouched.
    status, reply = _jsonrpc(
        _h.mcp.port,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": []}},
    )
    assert status == 200 and reply["result"]["isError"] is True, reply
    assert _h.core.calls() == []


@pytest.mark.parametrize(
    "message,code",
    [
        ([], -32600),
        ({"id": 1, "method": "tools/list"}, -32600),
        ({"jsonrpc": "1.0", "id": 1, "method": "tools/list"}, -32600),
        ({"jsonrpc": "2.0", "id": None, "method": "tools/list"}, -32600),
        ({"jsonrpc": "2.0", "id": True, "method": "tools/list"}, -32600),
        ({"jsonrpc": "2.0", "id": 1, "method": None}, -32600),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []}, -32602),
    ],
)
def test_mcp_jsonrpc_envelope_is_strict(message, code):
    status, reply = _jsonrpc(_h.mcp.port, message)
    assert status == 200
    assert reply["jsonrpc"] == "2.0"
    assert reply["error"]["code"] == code
    assert _h.core.calls() == []


def test_mcp_notification_is_accepted_without_hardware_dispatch():
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "set_intensity", "arguments": {"intensity": 50}},
        }
    ).encode()
    status = _raw(body, auth=f"Bearer {TOKEN}", extra=[f"Content-Length: {len(body)}"])
    assert status == 202
    assert _h.core.calls() == []


def test_axis_breach_refused():
    for value in (25001, -25001):
        results = _both("move_absolute", {"targets": {"x": value}}, code="validation")
        for payload in results.values():
            assert "25000" in payload["error"], payload  # the message names the limit


def test_relative_move_cannot_cross_envelope():
    # the core starts at x=24999, so +2 lands at 25001, one micron past x_max=25000.
    _both("move_relative", {"deltas": {"x": 2}}, code="validation")


def test_nonfinite_numbers_refused():
    # A non-finite number is rejected by strict_json_loads, which runs at
    # DIFFERENT layers per lane. Over TCP parse_call wraps it as a typed 'validation' error; over
    # MCP the whole request body is strict-parsed inside do_POST, so it returns HTTP 400 BEFORE
    # dispatch -- no tools/call isError envelope exists. Both refuse and neither touches the Core.
    for value in (float("nan"), float("inf"), 1e309):
        for name, args in (
            ("move_relative", {"deltas": {"x": value}}),  # bounded axis handler
            ("set_etl", {"etl_l_amplitude": value}),
        ):  # hardware numeric
            _refused("tcp", name, args, code="validation")
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": args},
                }
            ).encode()  # allow_nan default
            assert _raw(body, auth=f"Bearer {TOKEN}", extra=[f"Content-Length: {len(body)}"]) == 400, (
                name,
                value,
            )
    assert _h.core.calls() == []


def test_type_confusion_refused():
    _both("move_absolute", {"targets": {"x": True}}, code="validation")  # bool is not a number
    _both("set_intensity", {"intensity": "50"}, code="validation")  # string is not a number
    _both("move_absolute", {"targets": {}}, code="validation")  # empty targets


def test_limits_are_not_writable():
    for verb in ("set_limits", "set_stage_parameters", "set_stage_limits", "set_axis_limits"):
        assert verb not in dispatcher.COMMANDS
    results = _both("set_state", {"settings": {"x_max": 999999}}, code="validation")
    for payload in results.values():
        assert "x_max" in payload["error"], payload

    before = _h.core.calls()
    first = _h.invoke("mcp", "get_limits", {})[1]
    second = _h.invoke("mcp", "get_limits", {})[1]
    assert first == second  # a pure read, twice identical
    assert _h.core.calls() == before  # get_limits makes no Core call
    assert first["enforced"]["axes"]["x"] == [-25000.0, 25000.0]


def test_acquisition_abuse_refused():
    for entry in ("acquire_start",):
        _both(entry, {"acquisition": {"filter": "NOPE"}}, code="validation")
        _both(entry, {"acquisition": {"x_pos": 999999}}, code="validation")
    _both("set_acquisition_list", {"acquisitions": [{"filter": "NOPE"}]}, code="validation")
    _both("set_acquisition_list", {"acquisitions": [{"x_pos": 999999}]}, code="validation")
    _both("set_acquisition_list", {"acquisitions": []}, code="validation")


def test_upstream_plane_metadata_mismatch_round_trips_over_both_lanes():
    row = {
        "z_start": 0,
        "z_end": 100,
        "z_step": 10,
        "planes": 10,
        "image_writer_plugin": "RAW_Writer",
    }
    for lane in ("mcp", "tcp"):
        _h.reset()
        ok, installed = _h.invoke(lane, "set_acquisition_list", {"acquisitions": [row], "selected_row": 0})
        assert ok and installed["operation"]["result"]["count"] == 1, (lane, installed)
        ok, snapshot = _h.invoke(lane, "get_acquisition_list", {})
        assert ok and snapshot["acquisitions"][0]["planes"] == 10, (lane, snapshot)
        ok, restored = _h.invoke(
            lane, "set_acquisition_list", {"acquisitions": snapshot["acquisitions"], "selected_row": 0}
        )
        assert ok and restored["operation"]["result"]["count"] == 1, (lane, restored)


def test_live_tcp_normal_calls_use_the_configured_timeout(monkeypatch):
    seen = []

    class Client:
        def __init__(self, _host, _port, _token, timeout):
            seen.append(timeout)

        def call(self, _name, **_arguments):
            return {"pong": True}

        def close(self):
            pass

    monkeypatch.setenv("MESOSPIM_LIVE_TCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MESOSPIM_LIVE_TCP_PORT", "42000")
    monkeypatch.setenv("MESOSPIM_LIVE_TCP_TOKEN", "secret")
    monkeypatch.setattr(live_adversarial, "RemoteControl", Client)
    tool, _tcp = live_adversarial._make_tool("tcp", "127.0.0.1", 42100, "unused", request_timeout=17.0)

    assert tool("ping") == (True, {"pong": True})
    assert seen == [17.0]


def test_live_mcp_timeout_outlasts_server_dispatch(monkeypatch):
    monkeypatch.delenv("MESOSPIM_NETWORK_TIMEOUT_SECONDS", raising=False)
    assert live_session.network_timeout() > config.DISPATCH_TIMEOUT_SEC


def test_mcp_response_ignores_windows_client_abort():
    handler = srv._make_handler(None, "secret")

    class ClosedSocket:
        def write(self, _body):
            raise ConnectionAbortedError(10053, "client closed")

    class Response:
        wfile = ClosedSocket()

        def send_response(self, _status):
            pass

        def send_header(self, _name, _value):
            pass

        def end_headers(self):
            pass

    handler._json(Response(), 200, {"ok": True})


def test_mcp_hostile_tools_call_is_error_not_crash():
    for params in ({"name": "__class__", "arguments": {}}, {}, {"name": None, "arguments": {}}):
        status, reply = _jsonrpc(
            _h.mcp.port, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        )
        assert status == 200 and reply["result"]["isError"] is True, params
    assert _h.core.calls() == []
    ok, payload = _h.invoke("mcp", "get_state", {})  # the handler survives every hostile call
    assert ok and isinstance(payload, dict)


def test_viability_refused_and_never_actuates():
    """Both transports refuse a target above the reported limit without moving the stage."""
    for lane in ("mcp", "tcp"):
        limits = _h.invoke(lane, "get_limits", {})[1]["enforced"]["axes"]
        axis, bound = next((a, r) for a, r in limits.items() if r)
        _refused(lane, "move_absolute", {"targets": {axis: bound[1] + 1}}, code="validation")
    assert [c for c in _h.core.calls() if c[0] == "move_absolute"] == []


# --- the two confusable corpora (full, all-or-nothing) ---


def test_mcp_origin_corpus_403():
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "move_absolute", "arguments": {"targets": {"x": 0}}},
        }
    ).encode()
    hostile = [
        "null",
        "http://evil.example",
        "http://localhost.evil.example",
        "http://127.0.0.1.evil",
        "http://127.0.0.1:42100",
        "http://user@localhost",
        "HTTP://LOCALHOST",
        "http://localhost.",
        "https://localhost@evil.example",
        "file://localhost",
    ]
    for origin in hostile:
        status = _raw(body, auth=f"Bearer {TOKEN}", origin=origin, extra=[f"Content-Length: {len(body)}"])
        assert status == 403, (origin, status)
    assert _h.core.calls() == []


def test_mcp_auth_corpus_401():
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "move_absolute", "arguments": {"targets": {"x": 0}}},
        }
    ).encode()
    # each sent with a VALID Origin (checked before auth), so the check reaches hmac.compare_digest.
    candidates = [
        None,
        "Bearer ",
        f"Bearer {TOKEN[:5]}",
        f"Bearer {TOKEN} ",
        f"Bearer  {TOKEN}",
        f"Bearer {TOKEN.upper()}",
        f"Bearer {TOKEN}\x00",
        f"Bearer Bearer {TOKEN}",
    ]
    for auth in candidates:
        status = _raw(body, auth=auth, extra=[f"Content-Length: {len(body)}"])
        assert status == 401, (auth, status)
    assert _h.core.calls() == []


def test_mcp_boundary_smoke():
    # one 404: wrong path (checked before origin/auth)
    request = urllib.request.Request(
        f"http://127.0.0.1:{_h.mcp.port}/nope",
        data=b"{}",
        headers={"Origin": "http://127.0.0.1", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as reply:
            status = reply.status
    except urllib.error.HTTPError as error:
        status = error.code
    assert status == 404

    # one 413: Content-Length over the cap answers before the body is read (send none)
    assert (
        _raw(
            b"",
            auth=f"Bearer {TOKEN}",
            shutdown_write=True,
            extra=[f"Content-Length: {config.MAX_MCP_BODY_BYTES + 1}"],
        )
        == 413
    )

    # one 400: a duplicate Content-Length is rejected before dispatch
    assert _raw(b"{}", auth=f"Bearer {TOKEN}", extra=["Content-Length: 2", "Content-Length: 2"]) == 400
    assert _h.core.calls() == []


def test_tcp_framing_and_pipelining():
    adapter = _h.tcp.adapter
    # wrong token -> AUTH-FAILED and dropped
    conn = _h.tcp.new_conn(authed=False)
    adapter._handle(conn, "not-the-token")
    assert last_frame(conn) == "AUTH-FAILED"
    assert conn not in adapter._clients

    # a bad header and an oversized length header both raise before allocating
    for bad in (b"12x\n", str(config.MAX_FRAME_BYTES + 1).encode("ascii") + b"\n"):
        decoder = srv.FrameDecoder()
        decoder.feed(bad + b"payload")
        with pytest.raises(srv.FramingError):
            list(decoder.frames())

    # pipelined bad-utf8 + hostile + healthy: first two non-OK, third OK, only healthy reaches Core
    conn = _h.tcp.new_conn(authed=True)
    decoder = srv.FrameDecoder()
    decoder.feed(
        srv.frame(b'{"move_\xffabsolute":{"targets":{"x":0}}}')
        + srv.frame(json.dumps({"__import__": {}}).encode())
        + srv.frame(json.dumps({"set_intensity": {"intensity": 20}}).encode())
    )
    replies = []
    for payload in decoder.frames():
        adapter._handle(conn, payload.decode(config.ENCODING, "replace"))
        replies.append(last_frame(conn))
    assert not replies[0].startswith(config.OK_MARKER)
    assert not replies[1].startswith(config.OK_MARKER)
    assert replies[2].startswith(config.OK_MARKER)
    assert [c[0] for c in _h.core.calls()] == ["set_intensity"]


def test_mcp_bind_serve_stop():
    core = RecordingCore()
    handle = srv.start(core, "MCP", "127.0.0.1", 0, "tok")
    try:
        assert handle.port > 0
        status, reply = _jsonrpc(
            handle.port, {"jsonrpc": "2.0", "id": 1, "method": "initialize"}, token="tok"
        )
        assert status == 200
        assert reply["result"]["serverInfo"]["name"] == config.MCP_SERVER_NAME
    finally:
        handle.stop()  # joins the daemon thread AND closes the socket
    # stop() calls server.shutdown() then server.server_close(), so the listening socket is released:
    # a follow-up connect to the same port is REFUSED (URLError). TimeoutError is still accepted to
    # stay robust to OS timing, but the point is that the server is fully down, not merely paused.
    with pytest.raises((urllib.error.URLError, TimeoutError)):
        _jsonrpc(handle.port, {"jsonrpc": "2.0", "id": 2, "method": "initialize"}, token="tok")


# --- wire discovery over the real MCP loopback ---


def test_tools_list_over_wire():
    reply = _h.mcp.rpc("tools/list")
    tools = reply["result"]["tools"]
    assert {t["name"] for t in tools} == set(dispatcher.COMMANDS)
    assert len(tools) == 53
    for tool in tools:
        assert tool["inputSchema"] == {"type": "object"}
        assert tool["description"]
        assert tool["description"] == dispatcher.COMMANDS[tool["name"]].hint


def test_initialize_over_wire():
    result = _h.mcp.rpc("initialize")["result"]
    assert result["protocolVersion"] == config.MCP_PROTOCOL_VERSION
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"]["name"] == config.MCP_SERVER_NAME
    assert result["serverInfo"]["version"] == config.MCP_SERVER_VERSION
    assert "get_manual" in result["instructions"]
    assert "ordinary mutation" in result["instructions"]
    assert "Emergency commands" in result["instructions"]


def test_get_manual_over_wire():
    manuals = {}
    for lane in ("mcp", "tcp"):
        ok, payload = _h.invoke(lane, "get_manual", {})
        assert ok
        manuals[lane] = payload

        # The command list is generated from the registry, so it cannot drift from implementation.
        assert {command["name"] for command in payload["commands"]} == set(VALID_CASES)
        assert "poll get_progress" in payload["interaction"]["kinds"]["wait"]
        assert "either rejected" in payload["interaction"]["accepted_or_rejected"]
        assert "ordinary mutation" in payload["interaction"]["accepted_or_rejected"]
        assert "does not create a new operation" in payload["interaction"]["kinds"]["emergency"]
        assert set(payload["interaction"]["error_codes"]) == {
            "validation",
            "busy",
            "unknown_command",
            "execution",
        }

    # TCP and MCP must expose exactly the same built-in reference manual.
    assert manuals["tcp"] == manuals["mcp"]


def test_get_capabilities_over_wire():
    ok, payload = _h.invoke("mcp", "get_capabilities", {})
    assert ok
    assert set(payload["commands"]) == set(VALID_CASES)
    assert "set_mode" not in payload["commands"] and "procedure" not in payload["commands"]


def test_unknown_state_key_is_validation_over_mcp():
    """A client-supplied unknown state key is rejected during validation."""
    status, reply = _jsonrpc(
        _h.mcp.port,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "get_state_all", "arguments": {"keys": ["does_not_exist"]}},
        },
    )
    assert status == 200
    result = reply["result"]
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["error"]["code"] == "validation"


def test_corpus_is_bounded():
    assert REQUEST_TIMEOUT <= 0.6
    assert config.MAX_MCP_BODY_BYTES <= 1 << 20
