"""The two-lane wire driver: one Acceptor over one RecordingCore, one real MCP loopback lane, one
``_handle``-driven TCP lane, and a uniform ``invoke(lane, name, args) -> (ok, payload)``.

The MCP lane is a real loopback ThreadingHTTPServer inside the process. The TCP lane drives the real
adapter method ``TcpAdapter._handle`` with a fake conn, because the fake Qt shim stubs
``QTcpServer = object`` so a real offline TCP socket is impossible; ``_handle`` is the real adapter
code, so the harness never re-implements server logic (no drift). Real Qt TCP is demo-only.
"""

from __future__ import annotations

import json
import socket

from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src import mesoSPIM_RemoteControl_Servers as srv
from mesoSPIM.test.remote_control.support.clients import mcp_call
from mesoSPIM.test.remote_control.support.fakes import RecordingCore

TOKEN = "harness-token-Ac"


# --- Minimal connection object used to exercise the real TCP adapter ---
class FakeConn:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(bytes(data))

    def flush(self):
        pass

    def disconnectFromHost(self):
        pass

    def deleteLater(self):
        pass


def last_frame(conn):
    """Split the last written frame on its byte-count header, as impl's _last_frame does."""
    _, _, rest = conn.written[-1].partition(b"\n")
    return rest.decode(config.ENCODING, "replace")


def _parse_tcp(reply):
    """Normalize a TCP reply string to (ok, payload). A refusal is ``error: [<code>] <text>``."""
    if reply.startswith(config.OK_MARKER):
        return True, json.loads(reply[len(config.OK_MARKER) :])
    if reply.startswith("error: [") and "] " in reply:
        code = reply[len("error: [") : reply.index("] ")]
        return False, {"code": code, "error": reply}
    return False, {"code": None, "error": reply}


def _parse_mcp(reply):
    """Normalize an MCP tools/call JSON-RPC reply to (ok, payload)."""
    result = reply["result"]
    payload = json.loads(result["content"][0]["text"])
    if result["isError"]:
        error = payload["error"]
        return False, {"code": error["code"], "error": error["message"]}
    return True, payload


class McpLane:
    """A real loopback ThreadingHTTPServer running the production MCP handler."""

    name = "mcp"

    def start(self, acceptor, token=TOKEN):
        self.adapter = srv.McpAdapter()
        self.token = token
        self.port = self.adapter.start(acceptor, "127.0.0.1", 0, token)
        return self.port

    def call(self, name, args):
        reply = mcp_call("127.0.0.1", self.port, self.token, "tools/call", name, args or {})
        return _parse_mcp(reply)

    def rpc(self, method, name=None, args=None):
        """A raw JSON-RPC call (initialize / tools/list / get_capabilities-as-tools/call)."""
        return mcp_call("127.0.0.1", self.port, self.token, method, name, args or {})

    def raw(self, headers, body=b"", *, shutdown_write=False, timeout=0.6):
        """Send a raw HTTP POST for header and oversized-request attacks. Returns
        (status, raw_bytes). ``shutdown_write`` lets the 413-before-read path answer without a body."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        sock.settimeout(timeout)
        lines = [b"POST /mcp HTTP/1.1", b"Host: 127.0.0.1", b"Connection: close"]
        lines.extend(h.encode("ascii") for h in headers)
        sock.sendall(b"\r\n".join(lines) + b"\r\n\r\n" + body)
        if shutdown_write:
            sock.shutdown(socket.SHUT_WR)
        chunks = []
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
        finally:
            sock.close()
        response = b"".join(chunks)
        status = int(response.split(b" ", 2)[1]) if response.startswith(b"HTTP/") else None
        return status, response

    def stop(self):
        self.adapter.stop()


class TcpLane:
    """The TCP lane: the real TcpAdapter._handle driven with a fake conn (no socket)."""

    name = "tcp"

    def start(self, acceptor, token=TOKEN):
        self.adapter = srv.TcpAdapter()
        self.adapter._acceptor = acceptor
        self.adapter._token = token or None
        self.adapter._clients = {}
        self.token = token
        self.conn = self.new_conn()
        if token:
            assert self.authenticate(self.conn, token) == "OK"

    def new_conn(self, authed=None):
        """A freshly-registered client conn. Pre-authed when there is no token (or when asked)."""
        conn = FakeConn()
        pre = not (self.token or None) if authed is None else authed
        self.adapter._clients[conn] = {"decoder": srv.FrameDecoder(), "authed": pre}
        return conn

    def authenticate(self, conn, token):
        self.adapter._handle(conn, token)
        return last_frame(conn)

    def call(self, name, args):
        self.adapter._handle(self.conn, json.dumps({name: args or {}}))
        return _parse_tcp(last_frame(self.conn))


class Harness:
    """One Acceptor over one RecordingCore; both lanes share the single Core-owned session."""

    def __init__(self, core=None, token=TOKEN):
        self.core = core if core is not None else RecordingCore()
        self.token = token
        self.acceptor = srv.Acceptor(self.core)
        self.mcp = McpLane()
        self.mcp.start(self.acceptor, token)
        self.tcp = TcpLane()
        self.tcp.start(self.acceptor, token)

    def lane(self, name):
        return self.mcp if name == "mcp" else self.tcp

    def invoke(self, lane, name, args=None):
        return self.lane(lane).call(name, args or {})

    def reset(self):
        self.core.reset()

    def stop(self):
        self.mcp.stop()
        self.acceptor.stop()
