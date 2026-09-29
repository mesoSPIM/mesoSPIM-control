"""Real-PyQt MCP/TCP smoke for asynchronous mutation admission and polling.

Uses a fake Core and an ephemeral loopback port. It never starts mesoSPIM or touches hardware.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from PyQt5 import QtCore, QtNetwork, sip
except ModuleNotFoundError as error:
    raise SystemExit("real_pyqt_transport_smoke.py requires PyQt5") from error

from mesoSPIM.src import mesoSPIM_RemoteControl_Config as config
from mesoSPIM.src.mesoSPIM_RemoteControl_Commands import self_test
from mesoSPIM.src.mesoSPIM_RemoteControl_Servers import (
    Acceptor,
    FrameReader,
    McpAdapter,
    TcpAdapter,
    frame,
)


TOKEN = "pyqt-mcp-smoke"


class Core(QtCore.QObject):
    sig_finished = QtCore.pyqtSignal()
    sig_time_lapse_finished = QtCore.pyqtSignal()
    sig_time_lapse_cancelled = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        position = {
            "x_pos": 0.0,
            "y_pos": 0.0,
            "z_pos": 0.0,
            "f_pos": 2500.0,
            "theta_pos": 0.0,
        }
        self.state = {
            "state": "idle",
            "position": dict(position),
            "position_absolute": dict(position),
            "current_framenumber": 0,
        }
        self.cfg = SimpleNamespace(
            stage_parameters={
                "x_min": -25000,
                "x_max": 25000,
                "y_min": -50000,
                "y_max": 50000,
                "z_min": -25000,
                "z_max": 25000,
                "f_min": 0,
                "f_max": 98000,
                "theta_min": -999,
                "theta_max": 999,
                "stage_type": "DemoStage",
            }
        )
        self._remote_session = {"operation": None, "counter": 0}
        self.timelapse_active = False
        self.moves = []
        self.actions = []
        self.response_received = threading.Event()

    def move_absolute(self, targets, wait_until_done=False, **_kwargs):
        assert wait_until_done is False
        self.moves.append(dict(targets))

        def finish_move():
            for key, value in targets.items():
                position_key = key.replace("_abs", "_pos")
                self.state["position"][position_key] = float(value)
                self.state["position_absolute"][position_key] = float(value)

        # Long enough to prove that the HTTP reply and a second request arrive before completion.
        QtCore.QTimer.singleShot(300, finish_move)

    def zero_axes(self, axes):
        assert self.response_received.wait(1.0), "action ran before its acceptance reply arrived"
        self.actions.append(("zero_axes", list(axes)))


def process_until(app, predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert predicate(), "timed out while processing the Qt event queue"


def mcp_call(app, port, name, arguments=None, response_event=None):
    result = {}

    def request():
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Origin": "http://127.0.0.1",
            },
        )
        with urllib.request.urlopen(req, timeout=2.0) as response:
            rpc = json.loads(response.read().decode("utf-8"))
        tool = rpc["result"]
        assert tool["isError"] is False, tool
        result["value"] = json.loads(tool["content"][0]["text"])
        if response_event is not None:
            response_event.set()

    worker = threading.Thread(target=request)
    worker.start()
    process_until(app, lambda: not worker.is_alive())
    worker.join()
    return result["value"]


def tcp_call(app, port, name, arguments=None, response_event=None):
    result = {}

    def request():
        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            reader = FrameReader(sock)
            sock.sendall(frame(TOKEN))
            assert reader.read() == "OK"
            sock.sendall(frame(json.dumps({name: arguments or {}})))
            reply = reader.read()
        assert reply.startswith(config.OK_MARKER), reply
        result["value"] = json.loads(reply[len(config.OK_MARKER) :])
        if response_event is not None:
            response_event.set()

    worker = threading.Thread(target=request)
    worker.start()
    process_until(app, lambda: not worker.is_alive())
    worker.join()
    return result["value"]


def exercise_async_move(app, call):
    started = time.monotonic()
    accepted = call("move_absolute", {"targets": {"x": 100}})
    assert time.monotonic() - started < 1.0
    operation_id = accepted["operation"]["id"]
    assert accepted["operation"]["status"] == "processing"
    assert "target" not in accepted["operation"]

    # This is a new connection while the move is still active. It must not wait for or poison the
    # first request.
    progress = call("get_progress")
    assert progress["operation"]["id"] == operation_id
    assert progress["operation"]["status"] == "processing"

    deadline = time.monotonic() + 2.0
    while progress["operation"]["status"] == "processing" and time.monotonic() < deadline:
        progress = call("get_progress")
    assert progress["operation"] == {
        "id": operation_id,
        "command": "move_absolute",
        "status": "completed",
        "target": {"x": 100.0},
        "observed": {"x": 100.0},
        "result": {"target": {"x": 100.0}},
    }


def exercise_async_action(call, core):
    core.response_received.clear()
    accepted = call("zero", {"axes": ["x"]})
    operation_id = accepted["operation"]["id"]
    assert accepted["operation"] == {
        "id": operation_id,
        "command": "zero",
        "status": "processing",
    }

    progress = call("get_progress")
    assert progress["operation"] == {
        "id": operation_id,
        "command": "zero",
        "status": "completed",
        "result": {},
    }


def exercise_bind_rules(app):
    """What a LAN peer sees: "localhost" binds loopback only, an empty token or a hostname never
    binds, and a socket that sends no token is dropped after the auth timeout."""
    core = Core()
    acceptor = Acceptor(core)
    adapter = TcpAdapter()
    adapter.start(acceptor, "localhost", 0, TOKEN)
    try:
        bound = adapter._server.serverAddress()
        assert bound.isLoopback(), bound.toString()
    finally:
        adapter.stop()
        acceptor.stop()
    for host, token, error in (("127.0.0.1", "", ValueError), ("not-an-address", TOKEN, RuntimeError)):
        acceptor = Acceptor(Core())
        try:
            TcpAdapter().start(acceptor, host, 0, token)
        except error:
            pass
        else:
            raise AssertionError(f"bound with host={host!r} token={token!r}")
        finally:
            acceptor.stop()
    config.TCP_AUTH_TIMEOUT_MS = 200
    core = Core()
    acceptor = Acceptor(core)
    adapter = TcpAdapter()
    port = adapter.start(acceptor, "127.0.0.1", 0, TOKEN)
    try:
        silent = QtNetwork.QTcpSocket()
        silent.connectToHost("127.0.0.1", port)
        process_until(app, lambda: silent.state() == QtNetwork.QAbstractSocket.ConnectedState)
        process_until(app, lambda: len(adapter._clients) == 1)
        process_until(app, lambda: silent.state() == QtNetwork.QAbstractSocket.UnconnectedState, timeout=3.0)
        assert adapter._clients == {}, "the silent client was not dropped"
    finally:
        adapter.stop()
        acceptor.stop()
    print("REAL PYQT TCP BIND RULES PASS: localhost is loopback, no token or hostname refused, silent client dropped")


class CoreThreadServer(QtCore.QObject):
    """The TCP server on a QThread of its own, as mesoSPIM runs it on Core's."""

    listening = QtCore.pyqtSignal(int)

    @QtCore.pyqtSlot()
    def start(self):
        self.acceptor = Acceptor(Core())
        self.adapter = TcpAdapter()
        self.listening.emit(self.adapter.start(self.acceptor, "127.0.0.1", 0, TOKEN))

    @QtCore.pyqtSlot()
    def stop(self):
        self.adapter.stop()
        self.acceptor.stop()


def exercise_tcp_sockets_are_created_by_pyqt(app):
    """Every client socket the TCP server hands out is one PyQt created, so PyQt learns the moment
    it is deleted: the invariant behind exercise_tcp_reconnect_per_call, checked without timing."""
    acceptor = Acceptor(Core())
    adapter = TcpAdapter()
    port = adapter.start(acceptor, "127.0.0.1", 0, TOKEN)
    clients = [socket.create_connection(("127.0.0.1", port), timeout=2.0) for _ in range(3)]
    try:
        process_until(app, lambda: len(adapter._clients) == 3)
        assert all(sip.ispycreated(conn) for conn in adapter._clients), "a client socket was created in C++"
    finally:
        for client in clients:
            client.close()
        adapter.stop()
        acceptor.stop()
    print("REAL PYQT TCP SOCKETS PASS: every client socket is created by PyQt, which tracks its deletion")


def exercise_tcp_reconnect_per_call(app, calls=1000):
    """A client that opens a connection for every call is answered every time, with Core's server on
    its own thread and the GUI thread busy. Qt's own QTcpServer creates each socket in C++, and PyQt
    learns of such a socket's deletion only later: a socket accepted in between at the same address
    could be handed the deleted one's wrapper, which PyQt then invalidated, and that call was never
    answered (about 5 in 1000 here). Runs a real event loop, the only place Qt deletes sockets."""
    core_thread = QtCore.QThread()
    server = CoreThreadServer()
    server.moveToThread(core_thread)
    ports = []
    server.listening.connect(ports.append, QtCore.Qt.DirectConnection)
    core_thread.started.connect(server.start)
    core_thread.start()
    deadline = time.monotonic() + 5
    while not ports and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ports, "the TCP server on the Core thread did not start"
    unanswered = []

    def client():
        for index in range(calls):
            try:
                with socket.create_connection(("127.0.0.1", ports[0]), timeout=2.0) as sock:
                    reader = FrameReader(sock)
                    sock.sendall(frame(TOKEN))
                    assert reader.read().strip() == "OK"
                    sock.sendall(frame(json.dumps({"ping": {}})))
                    assert reader.read().startswith(config.OK_MARKER)
            except (OSError, AssertionError):
                unanswered.append(index)
                return

    worker = threading.Thread(target=client)
    busy_gui = QtCore.QTimer()
    busy_gui.timeout.connect(lambda: time.sleep(0.02))
    finished = QtCore.QTimer()
    finished.timeout.connect(lambda: worker.is_alive() or app.quit())
    busy_gui.start(5)
    finished.start(20)
    worker.start()
    app.exec_()
    busy_gui.stop()
    finished.stop()
    QtCore.QMetaObject.invokeMethod(server, "stop", QtCore.Qt.BlockingQueuedConnection)
    core_thread.quit()
    core_thread.wait()
    assert unanswered == [], f"call {unanswered[0]} of {calls} was never answered"
    print(f"REAL PYQT TCP RECONNECT PER CALL PASS: {calls} connections from one client, every call answered")


def main():
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    startup_ok, startup_report = self_test(Core())
    assert startup_ok, startup_report
    exercise_bind_rules(app)
    for label, adapter_type, caller in (
        ("MCP", McpAdapter, mcp_call),
        ("TCP", TcpAdapter, tcp_call),
    ):
        core = Core()
        acceptor = Acceptor(core)
        adapter = adapter_type()
        port = adapter.start(acceptor, "127.0.0.1", 0, TOKEN)
        try:
            exercise_async_move(
                app,
                lambda name, arguments=None: caller(app, port, name, arguments, core.response_received),
            )
            exercise_async_action(
                lambda name, arguments=None: caller(app, port, name, arguments, core.response_received),
                core,
            )
            assert core.moves == [{"x_abs": 100.0}]
            assert core.actions == [("zero_axes", ["x"])]
            print(f"REAL PYQT {label} ASYNC MUTATION PASS")
        finally:
            acceptor.close()
            adapter.stop()
            acceptor.stop()

    print(
        "REAL PYQT TRANSPORT POLLING PASS: actions accepted first, polling responsive, "
        "movement target confirmed"
    )
    exercise_tcp_sockets_are_created_by_pyqt(app)
    exercise_tcp_reconnect_per_call(app)


if __name__ == "__main__":
    main()
