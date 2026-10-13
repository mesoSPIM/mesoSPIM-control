"""Small things several test files share: talking to the viewer's server as the
page does, a clock a test moves by hand, and waiting for something to come true."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


def get(url: str, headers: dict | None = None):
    """A GET as (status, headers, body); an HTTP error is an answer, not an exception."""
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, dict(answer.headers), answer.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def status(url: str) -> int:
    return get(url)[0]


def get_json(url: str) -> dict:
    return json.loads(get(url)[2])


def post(url: str, payload=None, headers: dict | None = None) -> int:
    """A POST of JSON, as the page sends its reports; ``headers`` are sent beside it."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            answer.read()
            return answer.status
    except urllib.error.HTTPError as error:
        return error.code


class Clock:
    """The time a Library goes by, moved by the test."""

    def __init__(self, now: float = 5000.0) -> None:
        # Far from zero, like a machine that has been up for a while: nothing
        # counts as recent only because the clock has just started.
        self.now = now

    def __call__(self) -> float:
        return self.now

    def tick(self, seconds: float = 1.0) -> float:
        self.now += seconds
        return self.now


def until(look, wanted=lambda seen: bool(seen), timeout_s: float = 10.0, every_s: float = 0.1):
    """Call ``look`` until ``wanted`` holds for what it returns; return the last answer."""
    deadline = time.time() + timeout_s
    seen = look()
    while not wanted(seen) and time.time() < deadline:
        time.sleep(every_s)
        seen = look()
    return seen


# -- what a viewer has told its page ------------------------------------------------


def events(view) -> list[dict]:
    """Everything the page was told happened, oldest first."""
    return [event for _, event in view._server.scene._events]


def landed(view, store: str = "data/") -> list[tuple[str, list[str] | None]]:
    """The files named to the page as landed, as (store, files), oldest first:
    of the stores on disk, or with ``store="live/"`` of the stacks in memory."""
    return [
        (event["store"], event.get("files"))
        for event in events(view)
        if event["type"] == "landed" and event["store"].startswith(store)
    ]


def offered(view) -> dict[str, dict]:
    """The panel's list of acquisitions, by name, in the order it is listed."""
    return {entry["name"]: entry for entry in view._server.scene.acquisitions}


def follow(view) -> dict:
    """Where a live view is told to look, without the count of how often that moved."""
    return {key: value for key, value in view._server.scene.follow.items() if key != "count"}


def sources(view, acquisition: str) -> dict[str, str]:
    """The sources of an acquisition's first channel: lasting name -> address below the server."""
    layer = next(spec for spec in view.scene["layers"] if spec["_acquisition"] == acquisition)
    return {
        name: source["url"].split("|")[0].replace(view.url, "")
        for name, source in zip(layer["_sources"], layer["source"])
    }
