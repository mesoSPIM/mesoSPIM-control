"""One local HTTP address that serves the page, the stores' bytes and the scene.

Four kinds of request, kept deliberately plain:

- ``/`` and the page's own files, from the built ``dist`` folder;
- ``/data/<key>/...`` -- the files of a registered store, with byte ranges
  (sharded zarr v3 needs them) and revalidation by ETag;
- ``/live/<name>/...`` -- a stack being acquired, served from memory as a
  small zarr store (``live.py``);
- ``/api/...`` -- the scene as JSON and the events since, long-polled by the
  page, and the short reports the page posts back: where the camera is, what
  was clicked, which acquisition was ticked on or off in the panel's list or
  taken off the view, and a press of the panel's Open button.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlsplit

LONGEST_WAIT_S = 25.0
# How many events are kept for a page to catch up on; one that falls further
# behind reads everything it found missing again.
EVENT_LOG = 512


class Scene:
    """What the page should show, and what has happened since it last asked.

    Two things reach the page, both through one waiting request:

    - the **scene**, which is state: the layers, the acquisitions on offer, the
      message on the picture. It has a version, and the page is sent it again
      only when that has moved;
    - **events**, which are not state: files that landed in a store, to be read
      once by the page that is open. They are numbered and kept in a short log,
      and a page that asks from a number the log no longer reaches is told to
      catch up on its own (``resync``).

    Where the live view should be looking (``follow``) is state too, but it
    moves with every plane, so it travels beside the scene rather than in it:
    a new plane then costs a few bytes, not the whole scene again.
    """

    def __init__(self) -> None:
        self._changed = threading.Condition()
        self.version = 0
        self.camera_version = 0
        self.state: dict = {"layers": [], "layout": "xy"}
        self.camera: dict = {}
        self.ui: dict = {}
        # The acquisitions the panel lists, shown or not.
        self.acquisitions: list[dict] = []
        # A message for the operator, shown on the picture until the next one or
        # until they close it. The count tells the page that a message is new,
        # so the same sentence said twice is shown twice.
        self.notice: dict = {"text": "", "count": 0}
        # Where a live view should be looking, and how often that has moved.
        self.follow: dict = {"count": 0}
        self.sequence = 0
        self._events: deque[tuple[int, dict]] = deque(maxlen=EVENT_LOG)

    def _moved(self) -> int:
        self.version += 1
        self._changed.notify_all()
        return self.version

    def publish(self, state: dict) -> int:
        with self._changed:
            if state == self.state:
                return self.version
            self.state = state
            return self._moved()

    def offer(self, acquisitions: list[dict]) -> int:
        with self._changed:
            if acquisitions == self.acquisitions:
                return self.version
            self.acquisitions = acquisitions
            return self._moved()

    def dress(self, **ui) -> int:
        """Change how the page dresses itself while it is open."""
        with self._changed:
            if all(self.ui.get(key) == value for key, value in ui.items()):
                return self.version
            self.ui = {**self.ui, **ui}
            return self._moved()

    def say(self, text: str) -> int:
        with self._changed:
            self.notice = {"text": text, "count": self.notice["count"] + 1}
            return self._moved()

    def move_camera(self, camera: dict) -> int:
        with self._changed:
            self.camera_version += 1
            self.camera = camera
            return self._moved()

    def look_at_newest(self, position: dict | None) -> None:
        """Where the newest data is, by axis name, or None when nothing is being written.

        ``await`` may name the chunk that holds it (``{"store": ..., "chunk": [...]}``):
        the page then steps there once that chunk is loaded."""
        with self._changed:
            held = {key: value for key, value in self.follow.items() if key != "count"}
            wanted = dict(position or {})
            if held == wanted:
                return
            self.follow = {**wanted, "count": self.follow["count"] + 1}
            self._changed.notify_all()

    def emit(self, event: dict) -> int:
        """Tell the page something that happened, once."""
        with self._changed:
            self.sequence += 1
            self._events.append((self.sequence, event))
            self._changed.notify_all()
            return self.sequence

    def wait_past(self, version: int, timeout: float, sequence: int = -1, follow: int = -1) -> dict:
        """What is new for a page that holds ``version``, has heard events up to
        ``sequence`` and has followed up to ``follow``; waits until something is."""
        with self._changed:
            self._changed.wait_for(
                lambda: self.version != version
                or (sequence >= 0 and self.sequence != sequence)
                or (follow >= 0 and self.follow["count"] != follow),
                timeout=timeout,
            )
            answer: dict = {
                "version": self.version,
                "sequence": self.sequence,
                "follow": self.follow,
            }
            if self.version != version:
                answer.update(
                    cameraVersion=self.camera_version,
                    state=self.state,
                    camera=self.camera,
                    ui=self.ui,
                    acquisitions=self.acquisitions,
                    notice=self.notice,
                )
            if 0 <= sequence < self.sequence:
                oldest = self._events[0][0] if self._events else self.sequence + 1
                if sequence + 1 < oldest:
                    answer["resync"] = True
                answer["events"] = [event for number, event in self._events if number > sequence]
            return answer


class Stores:
    """The folders the page may read, each behind a short key.

    A store can be given a *guard*: a function that says, for a file of the
    store, whether the page may not have it yet. The live view uses it to keep
    a stack that is being written off the picture until all of it is on disk,
    while the stack's preview is shown in its place (``live.py``).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._roots: dict[str, Path] = {}
        self._guards: dict[str, Callable[[str], bool]] = {}
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

    def key_of(self, root: Path) -> str | None:
        root = root.resolve()
        with self._lock:
            return next((key for key, held in self._roots.items() if held == root), None)

    def guard(self, root: Path, held_back: Callable[[str], bool] | None) -> None:
        """Hold files of a store back from the page (``held_back(path below the root)``),
        or with None let all of it through again."""
        key = self.register(root)
        with self._lock:
            if held_back is None:
                self._guards.pop(key, None)
            else:
                self._guards[key] = held_back

    def resolve(self, key: str, relative: str) -> Path | None:
        """The file ``relative`` of the store registered under ``key``.

        ``<key>.<revision>`` names the same store: a store whose shape has changed
        on disk is given to the page under a new address (see ``Viewer._url_for``),
        so that the engine reads its description afresh.
        """
        key = key.partition(".")[0]
        with self._lock:
            root = self._roots.get(key)
            guard = self._guards.get(key)
        if root is None:
            return None
        if guard is not None and relative and guard(relative):
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
        # Only the viewer's own page may report: another page open in a browser
        # on this computer must not be able to tick acquisitions or ask for a
        # file dialog. A browser names the page a request comes from.
        origin = self.headers.get("Origin")
        if origin is not None and origin.rstrip("/") != self.server.url.rstrip("/"):
            self._send_empty(HTTPStatus.FORBIDDEN)
            return
        if route == "/api/view":
            self.server.scene_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/pick":
            self.server.pick_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/remove":
            self.server.remove_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/show":
            self.server.show_reported(payload)
            self._send_json({"ok": True})
        elif route == "/api/open":
            self.server.open_reported()
            self._send_json({"ok": True})
        elif route == "/api/collect":
            self.server.collect_reported(payload)
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
        if route.startswith("/live/"):
            pieces = route[len("/live/") :].split("/", 1)
            source = self.server.live.get(pieces[0])
            body = source.read(pieces[1] if len(pieces) > 1 else "") if source is not None else None
            if body is None:
                self._send_empty(HTTPStatus.NOT_FOUND)
            else:
                self._send_bytes(body, head=head)
            return
        if route == "/api/state":
            query = parse_qs(parts.query)

            def number(name: str) -> int:
                try:
                    return int(query.get(name, ["-1"])[0])
                except ValueError:
                    return -1

            wait = min(float(query.get("wait", ["0"])[0]), LONGEST_WAIT_S)
            self._send_json(
                self.server.scene.wait_past(
                    number("since"), wait, sequence=number("events"), follow=number("follow")
                )
            )
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

    def _send_bytes(self, body: bytes, *, head: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head:
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
        self.remove_listeners: list[Callable[[str], None]] = []
        self.show_listeners: list[Callable[[str, bool, bool], None]] = []
        self.open_listeners: list[Callable[[], None]] = []
        self.collect_listeners: list[Callable[[bool], None]] = []
        # Stacks shown from memory while they are acquired, by the name in their address.
        self.live: dict[str, object] = {}
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

    def show_reported(self, payload: object) -> None:
        """The operator ticked an acquisition in the panel's list on or off, or
        asked for it alone (``only``)."""
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
            return
        for listener in list(self.show_listeners):
            listener(payload["name"], bool(payload.get("visible", True)), bool(payload.get("only", False)))

    def open_reported(self) -> None:
        """The operator pressed Open in the panel: the window asks for a folder."""
        for listener in list(self.open_listeners):
            listener()

    def collect_reported(self, payload: object) -> None:
        """The operator switched Live on or off: whether runs the microscope acquires are collected."""
        if not isinstance(payload, dict) or not isinstance(payload.get("on"), bool):
            return
        for listener in list(self.collect_listeners):
            listener(payload["on"])

    def remove_reported(self, payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
            return
        for listener in list(self.remove_listeners):
            listener(payload["name"])

    def pick_reported(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        for listener in list(self.pick_listeners):
            listener(payload)
