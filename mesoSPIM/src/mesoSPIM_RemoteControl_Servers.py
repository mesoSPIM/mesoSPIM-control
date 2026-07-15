"""Provide the TCP and MCP servers for mesoSPIM Remote Control.

This module owns authentication, request framing, JSON-RPC handling, and safe routing from network
threads to the mesoSPIM Core thread. TCP and MCP share one ``Acceptor`` and therefore use the same
dispatcher, validation rules, operation gate, and command results. A session binds exactly one
transport; starting or stopping it remains an explicit operator action in the GUI.

The server layer understands wire formats but not microscope command semantics. Commands and
hardware limits remain in ``mesoSPIM_RemoteControl_Commands``. Shutdown closes the acceptor before
the listener so a late or stalled request cannot actuate the microscope after the operator stops
remote control.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PyQt5 import QtCore, QtNetwork

from . import mesoSPIM_RemoteControl_Config as config

# Importing Commands fills the dispatcher registry before either server accepts requests.
from . import mesoSPIM_RemoteControl_Commands  # noqa: F401
from .mesoSPIM_RemoteControl_Dispatcher import (
    run,
    complete,
    precheck,
    operation_snapshot,
    COMMANDS,
    strict_json_loads,
    parse_call,
    error_info,
)
from .mesoSPIM_RemoteControl_Commands import self_test


logger = logging.getLogger(__name__)


# --- Shared TCP framing ---
class FramingError(ValueError):
    """The TCP byte stream does not contain a valid bounded length-prefixed frame."""


def frame(payload):
    data = payload.encode(config.ENCODING) if isinstance(payload, str) else payload
    if len(data) > config.MAX_FRAME_BYTES:
        raise FramingError(f"payload exceeds {config.MAX_FRAME_BYTES} bytes")
    return str(len(data)).encode("ascii") + b"\n" + data


def frame_length(head):
    """The payload length a header promises, refusing anything non-canonical. One copy, so the
    blocking and incremental readers cannot enforce different rules."""
    if not head or len(head) > config.MAX_FRAME_HEADER_BYTES or not head.isdigit():
        raise FramingError("expected canonical byte-count header")
    length = int(head)
    if length > config.MAX_FRAME_BYTES:
        raise FramingError(f"frame exceeds {config.MAX_FRAME_BYTES} bytes")
    return length


class FrameReader:
    """Blocking length-framed reader for the client and one-shot callers."""

    def __init__(self, sock):
        self._sock = sock
        self._buf = b""

    def read(self):
        while b"\n" not in self._buf:
            if len(self._buf) > config.MAX_FRAME_HEADER_BYTES:
                raise FramingError("frame header is too long")
            self._buf += self._recv()
        head, _, rest = self._buf.partition(b"\n")
        length = frame_length(head)
        while len(rest) < length:
            rest += self._recv()
        self._buf = rest[length:]
        return rest[:length].decode(config.ENCODING, "replace")

    def _recv(self):
        chunk = self._sock.recv(config.RECV_CHUNK_BYTES)
        if not chunk:
            raise ConnectionError("TCP server closed the connection")
        return chunk


class FrameDecoder:
    """Incremental decoder for the Qt TCP server: Qt hands us whatever arrived; yield complete
    frames, return quietly when more is needed (never blocks the Core event loop)."""

    def __init__(self):
        self._buf = b""

    def feed(self, data):
        self._buf += bytes(data)

    def frames(self):
        while True:
            if b"\n" not in self._buf:
                if len(self._buf) > config.MAX_FRAME_HEADER_BYTES:
                    raise FramingError("frame header is too long")
                return
            head, _, rest = self._buf.partition(b"\n")
            length = frame_length(head)
            if len(rest) < length:
                return
            self._buf = rest[length:]
            yield rest[:length]


# --- Core-thread command dispatch ---
class _Call:
    """A request in flight across threads. `done` is set when the Core thread answers."""

    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.result = None
        self.error = None
        self.cancelled = False
        self.done = threading.Event()


class Acceptor(QtCore.QObject):
    """dispatch(name, args) -> result, always executed on the Core thread. Construct it ON the
    Core thread (thread affinity comes from where a QObject is created)."""

    _incoming = QtCore.pyqtSignal(object)

    def __init__(self, core):
        super().__init__(core)
        self._core = core
        self._closed = False
        self._incoming.connect(self._execute, QtCore.Qt.QueuedConnection)
        self._connections = []
        self._connect_completion_signals()

    def close(self):
        """Refuse any further dispatch. Called FIRST at shutdown so a request that arrives (or a
        stalled body that finishes reading) after Stop cannot actuate the microscope."""
        self._closed = True

    def dispatch(self, name, args):
        if self._closed:
            raise RuntimeError("remote control is shutting down")

        # Reject an unknown name on the transport thread instead of parking it behind Core work.
        precheck(name)
        call = _Call(name, args)

        # Argument shape, hardware limits, and the busy gate are always decided in run().
        if QtCore.QThread.currentThread() is self.thread():
            self._execute(call)
        else:
            self._incoming.emit(call)

            if not call.done.wait(config.DISPATCH_TIMEOUT_SEC):
                call.cancelled = True

                # The call may still be executing on the Core thread. Hand back the current operation
                # so the client can reconcile via polling instead of retrying blindly.
                op = operation_snapshot(self._core)
                logger.warning(
                    "Remote command %r did not return from Core within %.1f s; operation=%s",
                    name,
                    config.DISPATCH_TIMEOUT_SEC,
                    op,
                )
                raise TimeoutError(
                    f"Core did not answer within {config.DISPATCH_TIMEOUT_SEC}s; the "
                    f"call may still be running — poll get_progress. operation={op}"
                )

        if call.error is not None:
            raise call.error

        return call.result

    def _execute(self, call):
        # ALWAYS set call.done (in finally), even when we drop a cancelled/closed call — otherwise a
        # queued caller would block until DISPATCH_TIMEOUT_SEC waiting for an answer that never comes.
        try:
            # A call queued before close() must never actuate afterward.
            if call.cancelled or self._closed:
                call.error = RuntimeError("remote control is shutting down")
                return

            call.result = run(self._core, call.name, call.args)
        except Exception as error:
            call.error = error
        finally:
            call.done.set()

    def _connect(self, signal, slot):
        if signal is not None:
            signal.connect(slot)
            self._connections.append((signal, slot))

    def _connect_completion_signals(self):
        core = self._core
        self._connect(getattr(core, "sig_finished", None), lambda: complete(core, config.MILESTONE_FINISHED))
        self._connect(getattr(core, "sig_time_lapse_finished", None), self._complete_time_lapse)
        self._connect(getattr(core, "sig_time_lapse_cancelled", None), self._complete_time_lapse)

    def _complete_time_lapse(self):
        if getattr(self._core, "timelapse_active", None) is not False:
            # Ignore a duplicate/late signal from an older time lapse while the current generation
            # is independently known to be active (including its idle interval between points).
            return
        try:
            # Core may otherwise leave the state at run_acquisition_list.
            self._core.state["state"] = "idle"
        except (AttributeError, KeyError, TypeError):
            pass

        complete(self._core, config.MILESTONE_TIMELAPSE)

    def stop(self):
        """Disconnect the completion signals; leave the Core-owned session alone."""
        # Remain fail-closed even if a caller omitted close().
        self._closed = True

        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

        self._connections = []


# --- In-process MCP server ---
def _make_handler(acceptor, token):
    class Handler(BaseHTTPRequestHandler):
        server_version = config.MCP_SERVER_BANNER

        # Bound stalled request bodies so one client cannot retain a handler thread indefinitely.
        timeout = config.CLIENT_TIMEOUT_SEC

        def _json(self, status, payload):
            body = json.dumps(payload, allow_nan=False).encode(config.ENCODING)
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                # Windows reports a timed-out client as ConnectionAbortedError (WinError 10053),
                # while other platforms commonly use BrokenPipeError or ConnectionResetError.
                # In every case the response is simply no longer deliverable.
                pass

        def log_message(self, *_):
            pass

        def do_POST(self):
            if self.path != "/mcp":
                return self._json(404, {"error": "not found"})
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1 or (origins and origins[0] not in config.ALLOWED_ORIGINS):
                return self._json(403, {"error": "origin not allowed"})
            auths = self.headers.get_all("Authorization", [])
            prefix = "Bearer "
            header = auths[0] if len(auths) == 1 else ""
            supplied = header[len(prefix) :] if header.lower().startswith(prefix.lower()) else ""
            if not hmac.compare_digest(supplied, token):
                return self._json(401, {"error": "unauthorized"})
            if self.headers.get_all("Transfer-Encoding", []):
                return self._json(400, {"error": "Transfer-Encoding unsupported"})
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not lengths[0].isdigit():
                return self._json(400, {"error": "invalid Content-Length"})
            length = int(lengths[0])
            if length > config.MAX_MCP_BODY_BYTES:
                return self._json(413, {"error": "body too large"})
            body = self.rfile.read(length)
            if len(body) != length:
                return self._json(400, {"error": "truncated body"})
            try:
                msg = strict_json_loads(body.decode(config.ENCODING))
            except (UnicodeError, ValueError):
                return self._json(400, {"error": "invalid JSON"})
            reply = _mcp_reply(acceptor, msg)
            if reply is None:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._json(200, reply)

    return Handler


def _mcp_reply(acceptor, msg):
    def rpc_error(rid, code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    if not isinstance(msg, dict):
        return rpc_error(None, -32600, "invalid request: expected an object")
    rid = msg.get("id")
    if msg.get("jsonrpc") != "2.0":
        return rpc_error(
            rid if isinstance(rid, (str, int)) and not isinstance(rid, bool) else None,
            -32600,
            "invalid request: jsonrpc must be '2.0'",
        )
    # MCP notifications never actuate hardware because no result can confirm admission.
    if "id" not in msg:
        return None
    if not isinstance(rid, (str, int)) or isinstance(rid, bool):
        return rpc_error(None, -32600, "invalid request: id must be a string or integer")
    method = msg.get("method")
    if not isinstance(method, str):
        return rpc_error(rid, -32600, "invalid request: method must be a string")
    if "params" in msg and not isinstance(msg["params"], dict):
        return rpc_error(rid, -32602, "invalid params: expected an object")
    if method == "initialize":
        result = {
            "protocolVersion": config.MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": config.MCP_SERVER_NAME, "version": config.MCP_SERVER_VERSION},
            "instructions": config.MCP_INSTRUCTIONS,
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {"name": c.name, "description": c.hint or c.name, "inputSchema": {"type": "object"}}
                for c in COMMANDS.values()
            ]
        }
    elif method == "tools/call":
        params = msg.get("params", {})
        try:
            # pass `arguments` through as-is: run() defaults a missing/None to {} and rejects a
            # non-object ([], "", …), so MCP no longer silently accepts what TCP's parse_call refuses
            data = acceptor.dispatch(params.get("name"), params.get("arguments"))
            text, is_error = json.dumps(data, allow_nan=False), False
        except Exception as error:
            code, message = error_info(error)
            text, is_error = json.dumps({"error": {"code": code, "message": message}}, allow_nan=False), True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return rpc_error(rid, -32601, f"method not found: {method}")
    return {"jsonrpc": "2.0", "id": rid, "result": result}


class McpAdapter:
    name = "mcp"

    def start(self, acceptor, host, port, token):
        class Server(ThreadingHTTPServer):
            # Stop must not wait for a client that declared a body and then stalled. RemoteControl
            # closes the Acceptor first, so a detached handler that later finishes cannot actuate.
            daemon_threads = True
            block_on_close = False

        self._server = Server((host, int(port)), _make_handler(acceptor, token))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._server.server_address[1]

    def stop(self):
        self._server.shutdown()

        # Close the listening socket instead of only pausing request handling.
        self._server.server_close()
        self._thread.join(timeout=5)


# --- Length-framed TCP server ---
class TcpAdapter:
    name = "tcp"

    def start(self, acceptor, host, port, token):
        self._acceptor = acceptor
        self._token = token or None
        self._server = QtNetwork.QTcpServer(acceptor)
        if not self._server.listen(QtNetwork.QHostAddress(host), int(port)):
            raise RuntimeError(f"cannot listen on {host}:{port}: {self._server.errorString()}")
        self._port = int(self._server.serverPort())
        self._clients = {}
        self._server.newConnection.connect(self._on_new_connection)
        return self._port

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            conn = self._server.nextPendingConnection()
            self._clients[conn] = {"decoder": FrameDecoder(), "authed": not self._token}
            conn.readyRead.connect(lambda c=conn: self._on_ready(c))
            conn.disconnected.connect(lambda c=conn: self._drop(c))
            if conn.bytesAvailable():
                self._on_ready(conn)

    def _on_ready(self, conn):
        client = self._clients.get(conn)
        if client is None:
            return
        try:
            while conn in self._clients and conn.bytesAvailable():
                client["decoder"].feed(bytes(conn.readAll()))
                for payload in client["decoder"].frames():
                    self._handle(conn, payload.decode(config.ENCODING, "replace"))
                    if conn not in self._clients:
                        return
        except FramingError as error:
            self._send(conn, f"framing error: {error}")
            self._drop(conn)
        except RuntimeError:
            # Qt can deliver a queued readyRead after the peer timed out and the underlying
            # QTcpSocket was deleted. Forget that stale Python wrapper without letting an expected
            # disconnect escape from the Qt slot and interrupt later connections.
            self._drop(conn)

    def _handle(self, conn, message):
        client = self._clients.get(conn)
        if client is None:
            return
        if not client["authed"]:
            token_bytes = str(self._token).encode(config.ENCODING)
            if hmac.compare_digest(message.encode(config.ENCODING), token_bytes):
                client["authed"] = True
                self._send(conn, "OK")
            else:
                self._send(conn, "AUTH-FAILED")
                self._drop(conn)
            return
        try:
            name, args = parse_call(message)
            reply = config.OK_MARKER + json.dumps(self._acceptor.dispatch(name, args), allow_nan=False)
        except Exception as error:
            code, text = error_info(error)
            reply = f"error: [{code}] {text}"
        self._send(conn, reply)

    def _send(self, conn, text):
        if conn not in self._clients:
            return
        try:
            conn.write(frame(text))
            conn.flush()
        except RuntimeError:
            # The C++ socket may disappear between the membership check and write().
            self._drop(conn)

    def _drop(self, conn):
        self._clients.pop(conn, None)
        try:
            conn.disconnectFromHost()
            conn.deleteLater()
        except RuntimeError:
            pass

    def stop(self):
        for conn in list(self._clients):
            self._drop(conn)
        self._server.close()


_ADAPTERS = {"TCP": TcpAdapter, "MCP": McpAdapter}


# --- Public transport lifecycle used by Core ---
class RemoteControl:
    """The running transport for one session: the acceptor plus the single adapter. Build via
    start(); stop() tears both down. The Core-owned session is deliberately NOT touched here."""

    def __init__(self, acceptor, adapter, port):
        self.acceptor = acceptor
        self.adapter = adapter
        self.port = port

    def stop(self):
        # Refuse new dispatch first so a request completing during shutdown cannot actuate.
        self.acceptor.close()
        self.adapter.stop()

        # Disconnect completion signals without changing the Core-owned operation history.
        self.acceptor.stop()


def start(core, mode, host, port, token):
    """Fail-closed: run the config self-test, then bind exactly ONE transport for `mode`. Returns a
    RemoteControl handle (`.port`, `.stop()`). Raises BEFORE binding on an unknown mode or a failed
    self-test, so a caller that catches the raise never reports 'running'. Build this on the Core
    thread: the Acceptor takes its thread affinity from where it is constructed."""
    if mode not in _ADAPTERS:
        raise ValueError(f"unknown transport mode {mode!r}; expected one of {sorted(_ADAPTERS)}")
    if not token:
        raise ValueError("a token is required; the remote control refuses to bind without one")
    if token == config.DEFAULT_TOKEN and host not in config.LOOPBACK_HOSTS:
        raise ValueError(
            f"the default password is public (in the repository); set your own before "
            f"binding a non-loopback host ({host!r})"
        )
    ok, report = self_test(core)
    if not ok:
        raise RuntimeError("remote-control self-test failed: " + "; ".join(report))
    acceptor = Acceptor(core)
    adapter = _ADAPTERS[mode]()
    try:
        bound_port = adapter.start(acceptor, host, port, token)
    except Exception:
        # Never leak a wired acceptor when the socket cannot bind.
        acceptor.stop()
        raise

    return RemoteControl(acceptor, adapter, bound_port)


def stop_for_core(core):
    """Stop Core's single transport handle. Kept here so Core needs only a tiny delegate slot."""
    handle = getattr(core, "_remote_control", None)
    if handle is not None:
        handle.stop()
        core._remote_control = None


def start_for_core(core, mode, host, port, token):
    """Replace Core's single transport and report the result through its existing Qt signal."""
    # A session owns TCP or MCP, never both.
    stop_for_core(core)

    try:
        core._remote_control = start(core, mode, host, int(port), token or None)
    except Exception as error:
        logger.exception("Remote control failed to start")
        core.sig_remote_control_started.emit(False, str(error))
        return
    logger.info("Remote control (%s) on %s:%s", mode, host, core._remote_control.port)
    core.sig_remote_control_started.emit(True, f"{host}:{core._remote_control.port}")
