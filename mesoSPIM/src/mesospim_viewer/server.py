"""One local HTTP address that serves the page, the stores' bytes and the scene.

Three kinds of request, kept deliberately plain:

- ``/`` and the page's own files, from the built ``dist`` folder;
- ``/data/<key>/...`` -- the files of a registered store, with byte ranges
  (sharded zarr v3 needs them) and revalidation by ETag;
- ``/api/...`` -- the scene as JSON, long-polled by the page, and three short
  reports the page posts back: where the camera is, what was clicked, and
  which acquisition was chosen from the panel's dropdown.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlsplit

LONGEST_WAIT_S = 25.0


class Scene:
    """What the page should show, versioned so it can wait for a change."""

    def __init__(self) -> None:
        self._changed = threading.Condition()
        self.version = 0
        self.camera_version = 0
        self.state: dict = {"layers": [], "layout": "xy"}
        self.camera: dict = {}
        self.ui: dict = {}
        # The acquisitions the panel offers in its dropdown, and which is shown.
        self.choices: dict = {"names": [], "current": -1}

    def publish(self, state: dict) -> int:
        with self._changed:
            self.version += 1
            self.state = state
            self._changed.notify_all()
            return self.version

    def offer(self, names: list[str], current: int) -> int:
        with self._changed:
            self.version += 1
            self.choices = {"names": list(names), "current": current}
            self._changed.notify_all()
            return self.version

    def move_camera(self, camera: dict) -> int:
        with self._changed:
            self.camera_version += 1
            self.camera = camera
            self.version += 1
            self._changed.notify_all()
            return self.version

    def wait_past(self, version: int, timeout: float) -> dict:
        with self._changed:
            self._changed.wait_for(lambda: self.version != version, timeout=timeout)
            return {
                "version": self.version,
                "cameraVersion": self.camera_version,
                "state": self.state,
                "camera": self.camera,
                "ui": self.ui,
                "choices": self.choices,
            }


class Stores:
    """The folders the page may read, each behind a short key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._roots: dict[str, Path] = {}
        self._next = 0

    def register(self, root: Path) -> str:
        root = root.resolve()
        with self._lock:
            for key, held in self._roots.items():
                if held == root:
                    return key
            key = str(self._next)
            self._next += 1
            self._roots[key] = root
            return key

    def resolve(self, key: str, relative: str) -> Path | None:
        with self._lock:
            root = self._roots.get(key)
        if root is None:
            return None
        target = (root / relative).resolve() if relative else root
        try:
            target.relative_to(root)
        except ValueError:
            return None
        return target


def _content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if path.suffix in (".js", ".mjs"):
        return "text/javascript"
    return guessed or "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: "ViewServer"

    # -- routing ---------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        self._serve(head=False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(head=True)

    def do_POST(self) -> None:  # noqa: N802
        route = urlsplit(self.path).path
        payload = self._read_json()
        if route == "/api/view":
            self.server.scene_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/pick":
            self.server.pick_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/choose":
            self.server.choice_reported(payload)
            self._send_json({"ok": True})
        else:
            self._send_empty(HTTPStatus.NOT_FOUND)

    def _serve(self, *, head: bool) -> None:
        parts = urlsplit(self.path)
        route = unquote(parts.path)
        if route.startswith("/data/"):
            pieces = route[len("/data/") :].split("/", 1)
            key = pieces[0]
            relative = pieces[1] if len(pieces) > 1 else ""
            target = self.server.stores.resolve(key, relative)
            if target is None or not target.is_file():
                self._send_empty(HTTPStatus.NOT_FOUND)
                return
            self._send_file(target, head=head, cache="no-cache")
            return
        if route == "/api/state":
            query = parse_qs(parts.query)
            since = int(query.get("since", ["-1"])[0])
            wait = min(float(query.get("wait", ["0"])[0]), LONGEST_WAIT_S)
            self._send_json(self.server.scene.wait_past(since, wait))
            return
        if route.startswith("/api/"):
            self._send_empty(HTTPStatus.NOT_FOUND)
            return
        page = self.server.page_dir
        if page is None:
            self._send_empty(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        target = (page / route.lstrip("/")).resolve() if route != "/" else page / "index.html"
        try:
            target.relative_to(page.resolve())
        except ValueError:
            self._send_empty(HTTPStatus.NOT_FOUND)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_empty(HTTPStatus.NOT_FOUND)
            return
        self._send_file(target, head=head, cache="no-cache")

    # -- answering -------------------------------------------------------------

    def _read_json(self) -> object:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw or b"null")
        except ValueError:
            return None

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_file(self, target: Path, *, head: bool, cache: str) -> None:
        try:
            about = target.stat()
        except OSError:
            self._send_empty(HTTPStatus.NOT_FOUND)
            return
        etag = f'"{about.st_mtime_ns:x}-{about.st_size:x}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("ETag", etag)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = 0, about.st_size - 1
        wanted = self.headers.get("Range")
        partial = False
        if wanted and wanted.startswith("bytes="):
            first, _, last = wanted[len("bytes=") :].partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else end
                else:
                    start = max(0, about.st_size - int(last))
            except ValueError:
                start, end = 0, about.st_size - 1
            else:
                end = min(end, about.st_size - 1)
                if start > end:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{about.st_size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                partial = True
        length = end - start + 1 if about.st_size else 0
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("Content-Type", _content_type(target))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", cache)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{about.st_size}")
        self.end_headers()
        if head or not length:
            return
        with target.open("rb") as handle:
            handle.seek(start)
            left = length
            while left > 0:
                piece = handle.read(min(left, 1 << 20))
                if not piece:
                    break
                self.wfile.write(piece)
                left -= len(piece)

    def log_message(self, *args) -> None:  # noqa: D401 -- quiet by default
        if os.environ.get("MESOSPIM_VIEW_LOG"):
            super().log_message(*args)


class ViewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, host: str, port: int, page_dir: Path | None) -> None:
        super().__init__((host, port), Handler)
        self.page_dir = page_dir
        self.scene = Scene()
        self.stores = Stores()
        self.view_listeners: list[Callable[[dict], None]] = []
        self.pick_listeners: list[Callable[[dict], None]] = []
        self.choice_listeners: list[Callable[[int], None]] = []
        self.last_view: dict | None = None
        self.last_view_at: float = 0.0

    @property
    def url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}/"

    def handle_error(self, request, client_address) -> None:
        """A page that went away mid-request is not an error worth a traceback."""
        error = sys.exc_info()[1]
        if isinstance(error, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)

    def scene_reported(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self.last_view = payload
        self.last_view_at = time.monotonic()
        for listener in list(self.view_listeners):
            listener(payload)

    def choice_reported(self, payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("index"), int):
            return
        for listener in list(self.choice_listeners):
            listener(payload["index"])

    def pick_reported(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        for listener in list(self.pick_listeners):
            listener(payload)
