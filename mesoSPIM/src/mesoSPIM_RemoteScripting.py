"""
mesoSPIM remote scripting server.
=================================
Exposes mesoSPIM's Script Window over a localhost TCP socket: an external process
sends a Python script, it runs in the live ``mesoSPIM_Core`` context exactly as
the Script Window runs it (via the existing ``Core.execute_script``), and the
captured console output (stdout + stderr) is sent back. That is the whole
feature -- text in, console text out. No command vocabulary, no data format: a
client scripts the microscope with the full mesoSPIM Python API and prints
whatever it wants to get back.

    SECURITY. A script runs as ARBITRARY PYTHON on the acquisition PC (it can
    touch the filesystem, not only the scope). So the server is OFF by default,
    started by an operator from the GUI (Tools -> Remote Scripting...), binds to
    ``127.0.0.1`` unless changed, and can require a shared ``token`` (the client
    must present it before any script runs). The token is compared in constant
    time. NOTE: this is plain TCP -- the token is sent in clear text, so it is a
    gate against casual access on a trusted LAN, not protection against a network
    sniffer. For untrusted networks, tunnel it (SSH/VPN).

    BLOCKING. A script runs synchronously on the Core's thread via
    ``Core.execute_script``, exactly as the Script Window does -- so the GUI is
    unresponsive while a script runs. Keep injected scripts short (start work and
    return; poll for completion in separate calls) rather than sleeping inside
    one long-running script.

Wire protocol (line-length-framed, UTF-8):

    request  =  b"<decimal-byte-count>\\n" + <payload bytes>
    reply    =  same framing

If a token is configured, the FIRST frame a client sends must be the token; the
server replies with a one-frame ``"OK"`` or ``"AUTH-FAILED"`` (and closes on
failure). Every frame after that (or every frame, if no token) is a script; the
reply frame is the captured console output.

The framing and auth logic (:func:`frame`, :class:`FrameDecoder`,
:class:`AuthGate`) is kept socket-free so it unit-tests without a running Qt
event loop; ``QtNetwork`` is imported lazily by the server itself.

Author: Thom de Hoog (ZMB, University of Zurich). License: GPL-3.0 (part of
mesoSPIM-control; it uses the GPL Core API).
"""

import hmac
import io
import logging
import sys
import threading
import traceback

logger = logging.getLogger(__name__)

ENCODING = "utf-8"
MAX_FRAME_BYTES = 16 * 1024 * 1024  # guard against a client that never frames


class FramingError(ValueError):
    """A frame's length prefix was not a decimal byte count."""


def frame(payload):
    """Length-prefix a payload for the wire: ``b"<len>\\n" + payload``."""
    if isinstance(payload, str):
        payload = payload.encode(ENCODING)
    return str(len(payload)).encode("ascii") + b"\n" + payload


class FrameDecoder:
    """Incremental parser for length-prefixed frames (socket-free, so testable).

    Feed it received bytes with :meth:`feed`, then iterate :meth:`frames` for the
    complete payloads buffered so far. Raises :class:`FramingError` on a
    non-integer length line. :attr:`buffered` is the unconsumed byte count, so
    the caller can cap it against a client that never frames.
    """

    def __init__(self):
        self._buf = b""

    def feed(self, data):
        self._buf += bytes(data)

    @property
    def buffered(self):
        return len(self._buf)

    def frames(self):
        """Yield each complete payload (bytes) buffered so far, consuming it."""
        while b"\n" in self._buf:
            head, _, rest = self._buf.partition(b"\n")
            try:
                length = int(head)
            except ValueError as exc:
                raise FramingError("expected '<byte-count>\\n<payload>'") from exc
            if len(rest) < length:
                return  # payload not fully arrived yet
            self._buf = rest[length:]
            yield rest[:length]


class AuthGate:
    """Constant-time shared-token gate for the first frame.

    :attr:`passed` is True from the start when no token is configured. :meth:`check`
    compares the supplied first frame against the token in constant time, over
    UTF-8 bytes so a non-ASCII token works (``hmac.compare_digest`` refuses to
    compare a ``str`` containing non-ASCII).
    """

    def __init__(self, token=None):
        self._token = token or None
        self.passed = self._token is None

    @property
    def required(self):
        return self._token is not None

    def check(self, supplied):
        """True if *supplied* matches the token; sets :attr:`passed` on success."""
        if isinstance(supplied, str):
            supplied = supplied.encode(ENCODING)
        ok = hmac.compare_digest(supplied, str(self._token).encode(ENCODING))
        if ok:
            self.passed = True
        return ok


class _ThreadTee:
    """A stdout/stderr stand-in that always writes through to the real stream and,
    additionally, to a per-thread capture buffer when one is registered for the
    calling thread.

    This lets the server capture a script's own console output for the reply
    *without* hijacking the process-wide stream: a script runs alone on the Core
    thread, so only that thread has a buffer registered, and every other thread's
    output still reaches the real console untouched.
    """

    def __init__(self, real):
        self._real = real
        self._buffers = {}

    def register(self, buf):
        self._buffers[threading.get_ident()] = buf

    def unregister(self):
        self._buffers.pop(threading.get_ident(), None)

    def write(self, text):
        buf = self._buffers.get(threading.get_ident())
        if buf is not None:
            buf.write(text)
        return self._real.write(text)

    def flush(self):
        self._real.flush()

    def __getattr__(self, name):  # delegate isatty/encoding/... to the real stream
        return getattr(self._real, name)


class RemoteScriptingServer:
    """A localhost TCP server that runs received scripts in the Core context.

    Signal-driven (QTcpServer + readyRead), so it lives on the Core's event loop
    without blocking it while idle. One client at a time -- a new connection
    preempts a stale one, so a crashed client's half-open socket can never hold
    the server hostage. Parented to the Core so Qt owns its lifetime.

    Raises ``RuntimeError`` if the socket cannot bind (e.g. the port is in use);
    the caller reports that to the operator rather than showing a false "running".
    """

    def __init__(self, core, host="127.0.0.1", port=42000, token=None):
        from PyQt5 import QtNetwork

        self.core = core
        self._token = token or None
        # QHostAddress does not resolve hostnames; map the common alias.
        bind_host = "127.0.0.1" if host in ("localhost", "") else host
        self._server = QtNetwork.QTcpServer(core)
        if not self._server.listen(QtNetwork.QHostAddress(bind_host), int(port)):
            raise RuntimeError(
                f"cannot listen on {host}:{port}: {self._server.errorString()}"
            )
        self._host, self._port = bind_host, int(port)
        self._server.newConnection.connect(self._on_new_connection)
        self._conn = None
        self._decoder = FrameDecoder()
        self._auth = AuthGate(self._token)
        # Tee sys.stdout/stderr so a script's own output can be captured per-thread
        # (see _ThreadTee / _run_script) without swapping the process-wide stream
        # out from under the other threads. Restored in stop().
        self._real_stdout, self._real_stderr = sys.stdout, sys.stderr
        self._out_tee = _ThreadTee(sys.stdout)
        self._err_tee = _ThreadTee(sys.stderr)
        sys.stdout, sys.stderr = self._out_tee, self._err_tee
        logger.info(
            "Remote scripting listening on %s:%d (token %s)",
            self._host,
            self._port,
            "required" if self._token else "off",
        )

    # -- connection lifecycle ------------------------------------------------

    def _on_new_connection(self):
        conn = self._server.nextPendingConnection()
        if self._conn is not None:
            self._drop_client(self._conn)
        self._conn = conn
        self._decoder = FrameDecoder()
        self._auth = AuthGate(self._token)
        conn.readyRead.connect(self._on_ready_read)
        conn.disconnected.connect(lambda c=conn: self._on_disconnected(c))

    def _on_disconnected(self, conn):
        if conn is self._conn:
            self._conn = None
        # Qt may already have reclaimed the C++ socket by the time the queued
        # ``disconnected`` fires; calling deleteLater() on it then raises
        # RuntimeError. A client dropping MUST NOT crash mesoSPIM, so guard it.
        try:
            conn.deleteLater()
        except RuntimeError:
            pass

    def _drop_client(self, conn):
        if conn is self._conn:
            self._conn = None
        try:
            conn.disconnected.disconnect()
        except (TypeError, RuntimeError):
            pass  # no slots were connected, or the socket is already gone
        try:
            conn.disconnectFromHost()
            conn.deleteLater()
        except RuntimeError:
            pass  # already reclaimed by Qt

    # -- framing / dispatch --------------------------------------------------

    def _on_ready_read(self):
        if self._conn is None:
            return
        self._decoder.feed(self._conn.readAll())
        if self._decoder.buffered > MAX_FRAME_BYTES:
            self._close("frame too large")
            return
        try:
            for payload in self._decoder.frames():
                self._handle(payload.decode(ENCODING, "replace"))
                if self._conn is None:
                    return  # a rejected/closed client: stop processing its frames
        except FramingError as exc:
            self._send(f"framing error: {exc}")
            self._close("framing error")

    def _send(self, text):
        if self._conn is None:
            return
        self._conn.write(frame(text))
        self._conn.flush()

    def _close(self, _reason=""):
        if self._conn is not None:
            self._conn.disconnectFromHost()
            self._conn = None  # _on_disconnected still deleteLater()s it

    def _handle(self, message):
        # First frame is the token when one is configured.
        if not self._auth.passed:
            if self._auth.check(message):
                self._send("OK")
            else:
                self._send("AUTH-FAILED")
                self._close("auth failed")
            return
        self._send(self._run_script(message))

    def _run_script(self, script):
        """Run ``script`` via the existing Core.execute_script, capturing its own
        console output for the reply.

        execute_script runs exec() in the Core context (self == Core) and prints
        any traceback. A script runs alone on the Core thread (execute_script blocks
        it), so we register a capture buffer for THIS thread on the tees installed
        in __init__ -- capturing the script's stdout/stderr while other threads'
        output keeps flowing only to the real console. We never swap the
        process-wide stream out from under them.
        """
        buf = io.StringIO()
        self._out_tee.register(buf)
        self._err_tee.register(buf)
        try:
            self.core.execute_script(script)
        except Exception:  # execute_script catches script errors; belt-and-suspenders
            buf.write(traceback.format_exc())
        finally:
            self._out_tee.unregister()
            self._err_tee.unregister()
        return buf.getvalue()

    def stop(self):
        if self._conn is not None:
            self._drop_client(self._conn)
        self._server.close()
        # Restore the real stdout/stderr we teed in __init__.
        if getattr(self, "_real_stdout", None) is not None:
            sys.stdout, sys.stderr = self._real_stdout, self._real_stderr
        logger.info("Remote scripting stopped")
