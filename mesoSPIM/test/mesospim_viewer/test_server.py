"""The one local address: the stores' bytes, stacks from memory, the scene and its events.

The page long-polls ``/api/state`` and is answered with whatever is new to it:
the scene when its version has moved, the events since the last one it heard,
and where a live view should look. It reads store files from ``/data/<key>/``
and a stack being acquired from ``/live/<name>/``, and posts what the operator
did. Python only: the requests are made here as the page makes them.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import Channel, PreviewStack, Stack
from mesoSPIM.src.mesospim_viewer.server import EVENT_LOG, Scene, Stores

from .tools import get, get_json, post, status

# -- the bytes of a store ----------------------------------------------------------


def test_the_server_serves_store_bytes_with_ranges_and_revalidation(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    url = view.start()
    source = view.scene["layers"][0]["source"][0]["url"].split("|")[0]
    assert source == f"{url}data/0/"
    code, headers, body = get(source + ".zattrs")
    assert code == 200 and b"multiscales" in body
    code, headers, whole = get(source + "0/0.0.0.0.0")
    assert code == 200 and headers["Accept-Ranges"] == "bytes" and headers["Cache-Control"] == "no-cache"
    assert len(whole) == 64 * 64 * 2
    code, headers, part = get(source + "0/0.0.0.0.0", {"Range": "bytes=10-19"})
    assert code == 206 and part == whole[10:20]
    assert headers["Content-Range"] == f"bytes 10-19/{len(whole)}"
    code, _, tail = get(source + "0/0.0.0.0.0", {"Range": "bytes=-16"})
    assert code == 206 and tail == whole[-16:], "the last bytes: where a shard keeps its index"
    code, _, rest = get(source + "0/0.0.0.0.0", {"Range": f"bytes={len(whole) - 4}-"})
    assert code == 206 and rest == whole[-4:]
    code, headers, _ = get(source + "0/0.0.0.0.0", {"Range": f"bytes={len(whole)}-"})
    assert code == 416 and headers["Content-Range"] == f"bytes */{len(whole)}"
    etag = get(source + ".zattrs")[1]["ETag"]
    assert get(source + ".zattrs", {"If-None-Match": etag})[0] == 304
    assert get(source + ".zattrs", {"If-None-Match": '"stale"'})[0] == 200


def test_the_server_serves_nothing_outside_the_stores_it_was_given(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    url = view.start()
    assert status(f"{url}data/0/../../etc/passwd") == 404
    assert status(f"{url}data/0/%2e%2e/tile_01.ome.zarr/.zattrs") == 404
    assert status(f"{url}data/99/.zattrs") == 404
    assert status(f"{url}data/0/0/9.9.9.9.9") == 404, "a chunk that is not written yet"
    assert status(f"{url}data/0/0") == 404, "a folder is not a file"
    assert status(f"{url}api/nothing") == 404
    assert post(f"{url}api/nothing", {}) == 404


def test_the_page_itself_is_served_from_the_build(viewers):
    view = viewers()
    url = view.start()
    if not view.page_built:
        pytest.skip("the mesoSPIM page is not built")
    code, headers, body = get(url)
    assert code == 200 and headers["Content-Type"].startswith("text/html") and b"<html" in body.lower()
    assert status(url + "chunk_worker.bundle.js") == 200
    assert get(url + "chunk_worker.bundle.js")[1]["Content-Type"] == "text/javascript"
    assert status(url + "no_such_file.js") == 404
    assert status(url + "../viewer.py") == 404


def test_without_a_built_page_only_the_page_is_missing(viewers, tmp_path, tiles):
    view = viewers(page_dir=tmp_path)
    view.add(tiles[0], layer="overview")
    assert view.page_built is False
    assert status(view.url) == 503
    assert status(view.url + "api/state") == 200 and status(view.url + "data/0/.zattrs") == 200


# -- a store's files held back ---------------------------------------------------------


def test_a_guard_keeps_files_of_a_store_from_the_page_until_it_is_lifted(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    view.add(tiles[1], layer="overview")
    url = view.start()
    asked = []

    def second_channel(file: str) -> bool:
        asked.append(file)
        return file.startswith("0/0.1.")

    view.guard(tiles[0], second_channel)
    assert status(f"{url}data/0/0/0.1.3.0.0") == 404
    assert status(f"{url}data/0/0/0.0.3.0.0") == 200
    assert status(f"{url}data/0/.zattrs") == 200 and status(f"{url}data/0/0/.zarray") == 200
    assert asked == ["0/0.1.3.0.0", "0/0.0.3.0.0", ".zattrs", "0/.zarray"], "asked by the path below the store"
    assert status(f"{url}data/1/0/0.1.3.0.0") == 200, "another store is not held back"
    view.guard(tiles[0], None)
    assert status(f"{url}data/0/0/0.1.3.0.0") == 200


def test_a_guard_holds_whatever_address_the_store_is_read_at(tmp_path):
    (tmp_path / "held").write_text("x")
    (tmp_path / "free").write_text("x")
    stores = Stores()
    key = stores.register(tmp_path)
    assert key == "0" and stores.key_of(tmp_path) == key
    assert stores.register(tmp_path) == key, "registered once"
    assert stores.resolve(key, "held") == (tmp_path / "held").resolve()
    assert stores.resolve(f"{key}.3", "held") == (tmp_path / "held").resolve(), "the same store, read again"
    stores.guard(tmp_path, lambda file: file == "held")
    assert stores.resolve(key, "held") is None and stores.resolve(f"{key}.3", "held") is None
    assert stores.resolve(key, "free") is not None
    stores.guard(tmp_path, None)
    assert stores.resolve(key, "held") is not None
    assert stores.resolve("5", "held") is None and stores.key_of(tmp_path / "elsewhere") is None
    assert stores.resolve(key, "../outside") is None


# -- a stack served from memory ------------------------------------------------------------


def test_a_preview_is_read_at_live_as_a_small_zarr_store(viewers):
    view = viewers()
    stack = Stack(
        acquisition="run", channel="561", channels=("488", "561"), planes=4, frame=(8, 8),
        voxel_um=(5.0, 1.0, 1.0), origin_um=(0.0, 0.0, 0.0),
    )
    preview = PreviewStack(stack)
    name = view.add_preview("run", preview, Channel("561"))
    url = f"{view.url}live/{name}/"
    assert get_json(url + ".zgroup") == {"zarr_format": 2}
    assert get_json(url + "0/.zarray")["shape"] == [1, 2, 4, 8, 8]
    assert "multiscales" in get_json(url + ".zattrs")
    assert status(url + "0/0/1/0/0/0") == 404, "the plane has not arrived"
    frame = np.arange(64, dtype=np.uint16).reshape(8, 8)
    preview.add(0, frame)
    code, headers, body = get(url + "0/0/1/0/0/0")
    assert code == 200 and body == frame.astype("<u2").tobytes()
    assert headers["Cache-Control"] == "no-store", "a plane may be filled in again"
    assert status(url + "0/0/1/1/0/0") == 404
    assert status(url + "0/0/0/0/0/0") == 404, "the other channel is not this stack's"
    assert status(f"{view.url}live/live-9/.zattrs") == 404
    view.remove_preview(name)
    assert status(url + ".zattrs") == 404


# -- the scene, and what has happened since --------------------------------------------------


def test_a_page_is_sent_the_scene_only_when_its_version_has_moved():
    scene = Scene()
    first = scene.wait_past(-1, 0)
    assert first["version"] == 0 and first["state"] == {"layers": [], "layout": "xy"}
    assert {"camera", "ui", "acquisitions", "notice", "cameraVersion"} <= set(first)
    started = time.monotonic()
    same = scene.wait_past(0, 0.2)
    assert 0.15 < time.monotonic() - started < 2
    assert same == {"version": 0, "sequence": 0, "follow": {"count": 0}}, "nothing new, nothing sent"

    state = {"layers": [{"name": "a"}], "layout": "xy"}
    assert scene.publish(state) == 1
    assert scene.publish(dict(state)) == 1, "the same scene again is not a new version"
    answer = scene.wait_past(0, 5)
    assert answer["version"] == 1 and answer["state"] == state


def test_a_waiting_page_is_woken_by_a_change():
    scene = Scene()
    answers = []
    waiting = threading.Thread(target=lambda: answers.append(scene.wait_past(0, 10)))
    started = time.monotonic()
    waiting.start()
    time.sleep(0.1)
    scene.say("hello")
    waiting.join(5)
    assert time.monotonic() - started < 3
    assert answers[0]["version"] == 1 and answers[0]["notice"] == {"text": "hello", "count": 1}


def test_what_the_panel_lists_and_wears_is_part_of_the_scene():
    scene = Scene()
    assert scene.offer([{"name": "run", "shown": True}]) == 1
    assert scene.offer([{"name": "run", "shown": True}]) == 1, "the same list again"
    assert scene.offer([{"name": "run", "shown": False}]) == 2
    assert scene.dress(removable=True) == 3
    assert scene.dress(removable=True) == 3
    assert scene.say("") == 4 and scene.say("") == 5, "the same sentence said twice is shown twice"
    assert scene.move_camera({"fit": True}) == 6
    answer = scene.wait_past(0, 0)
    assert answer["acquisitions"] == [{"name": "run", "shown": False}]
    assert answer["ui"] == {"removable": True}
    assert answer["notice"] == {"text": "", "count": 2}
    assert answer["camera"] == {"fit": True} and answer["cameraVersion"] == 1


def test_events_reach_a_page_once_after_the_last_one_it_heard():
    scene = Scene()
    version = scene.version
    assert scene.emit({"type": "landed", "store": "data/0", "files": ["a"]}) == 1
    assert scene.emit({"type": "landed", "store": "data/0", "files": ["b"]}) == 2
    assert scene.version == version, "an event is not a new scene"
    # A page that has only just opened asks without a number: it has read nothing
    # yet, so nothing can have landed behind its back.
    assert "events" not in scene.wait_past(version, 0)
    answer = scene.wait_past(version, 5, sequence=0)
    assert answer["sequence"] == 2 and "state" not in answer and "resync" not in answer
    assert [event["files"] for event in answer["events"]] == [["a"], ["b"]]
    assert [event["files"] for event in scene.wait_past(version, 5, sequence=1)["events"]] == [["b"]]
    started = time.monotonic()
    quiet = scene.wait_past(version, 0.2, sequence=2)
    assert time.monotonic() - started > 0.15 and "events" not in quiet


def test_a_waiting_page_is_woken_by_an_event():
    scene = Scene()
    answers = []
    waiting = threading.Thread(target=lambda: answers.append(scene.wait_past(0, 10, sequence=0)))
    waiting.start()
    time.sleep(0.1)
    scene.emit({"type": "landed", "store": "data/0", "files": ["a"]})
    waiting.join(5)
    assert answers and answers[0]["events"] == [{"type": "landed", "store": "data/0", "files": ["a"]}]


def test_a_page_the_log_has_overrun_is_told_to_catch_up_on_its_own():
    scene = Scene()
    for number in range(EVENT_LOG + 10):
        scene.emit({"type": "landed", "store": "data/0", "files": [str(number)]})
    behind = scene.wait_past(0, 0, sequence=3)
    assert behind["resync"] is True
    assert len(behind["events"]) == EVENT_LOG and behind["events"][-1]["files"] == [str(EVENT_LOG + 9)]
    # The oldest event still kept is number 11: a page that heard up to 10 has missed nothing.
    assert "resync" not in scene.wait_past(0, 0, sequence=10)
    assert scene.wait_past(0, 0, sequence=9)["resync"] is True
    near = scene.wait_past(0, 0, sequence=EVENT_LOG + 8)
    assert "resync" not in near and len(near["events"]) == 2


def test_where_a_live_view_looks_travels_beside_the_scene():
    scene = Scene()
    version = scene.version
    scene.look_at_newest({"z": 35.0, "t": 0.0})
    assert scene.version == version, "a new plane does not cost the whole scene again"
    answer = scene.wait_past(version, 5, follow=0)
    assert answer == {"version": version, "sequence": 0, "follow": {"z": 35.0, "t": 0.0, "count": 1}}
    scene.look_at_newest({"z": 35.0, "t": 0.0})
    assert scene.follow["count"] == 1, "the same place again is no move"
    scene.look_at_newest({"z": 40.0, "t": 0.0, "await": {"store": "live/live-1", "chunk": [0, 0, 8, 0, 0]}})
    assert scene.follow["count"] == 2 and scene.follow["await"]["chunk"] == [0, 0, 8, 0, 0]
    scene.look_at_newest(None)
    assert scene.follow == {"count": 3}, "nothing is running any more"
    scene.look_at_newest(None)
    assert scene.follow == {"count": 3}
    started = time.monotonic()
    scene.wait_past(version, 0.2, follow=3)
    assert time.monotonic() - started > 0.15
    # A page that does not say how far it has followed is not woken by it.
    started = time.monotonic()
    scene.wait_past(version, 0.2)
    assert time.monotonic() - started > 0.15


def test_the_state_request_takes_all_three_numbers(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    url = view.start()
    answer = get_json(f"{url}api/state?since=-1")
    assert answer["version"] >= 1
    assert answer["state"]["layers"][0]["name"] == "overview · 488"
    assert answer["state"]["layers"][0]["_sources"] == ["store-0"], "the page is sent the scene, additions and all"
    assert answer["ui"] == {"transparent": False, "chrome": "full"}
    assert answer["notice"] == {"text": "", "count": 0} and answer["acquisitions"] == []
    assert answer["follow"] == {"count": 0} and answer["sequence"] == 0

    version = answer["version"]
    view.landed(tiles[0], ["0/0.0.1.0.0"])
    view.look_at_newest(z=5.0, t=0.0)
    answer = get_json(f"{url}api/state?since={version}&events=0&follow=0&wait=5")
    assert "state" not in answer and answer["version"] == version
    assert answer["events"] == [{"type": "landed", "store": "data/0", "files": ["0/0.0.1.0.0"]}]
    assert answer["follow"] == {"z": 5.0, "t": 0.0, "count": 1}

    # A change of the scene is versioned, and a waiting page is woken by it.
    started = time.monotonic()
    threading.Timer(0.2, lambda: view.look_at(x=5.0)).start()
    answer = get_json(f"{url}api/state?since={version}&events=1&follow=1&wait=5")
    assert 0.1 < time.monotonic() - started < 4
    assert answer["version"] > version and answer["camera"] == {"position": {"x": 5.0}}
    assert "events" not in answer
    assert get_json(f"{url}api/state?since=nonsense&wait=0")["version"] == answer["version"]


def test_look_at_newest_names_the_chunk_to_wait_for(viewers):
    view = viewers()
    follow = lambda: view._server.scene.follow
    view.look_at_newest(z=10.0, t=1.0, preview="live-2", chunk=[0, 0, 2, 1, 0])
    assert follow() == {"z": 10.0, "t": 1.0, "await": {"store": "live/live-2", "chunk": [0, 0, 2, 1, 0]}, "count": 1}
    view.look_at_newest(z=15.0)
    assert follow() == {"z": 15.0, "count": 2}
    view.look_at_newest()
    assert follow() == {"count": 3}


# -- what the page reports back ----------------------------------------------------------------


def test_ticking_removing_and_opening_in_the_panel_reach_python(viewers):
    view = viewers()
    url = view.start()
    shown, removed, opened = [], [], []
    assert "removable" not in get_json(f"{url}api/state")["ui"]
    view.on_show(lambda name, visible, only: shown.append((name, visible, only)))
    view.on_remove(removed.append)
    view.on_open(lambda: opened.append(True))
    ui = get_json(f"{url}api/state")["ui"]
    assert ui["removable"] is True and ui["openable"] is True, "the panel offers what something listens for"

    assert post(f"{url}api/show", {"name": "run_a", "visible": False}) == 200
    assert post(f"{url}api/show", {"name": "run_b", "visible": True, "only": True}) == 200
    assert post(f"{url}api/show", {"name": "run_c"}) == 200
    assert shown == [("run_a", False, False), ("run_b", True, True), ("run_c", True, False)]
    assert post(f"{url}api/remove", {"name": "run_a"}) == 200
    assert removed == ["run_a"]
    assert post(f"{url}api/open", {}) == 200 and post(f"{url}api/open", None) == 200
    assert opened == [True, True]
    # What is not a report is answered and passed over.
    for payload in (None, [], {"name": 3}, {}):
        assert post(f"{url}api/show", payload) == 200 and post(f"{url}api/remove", payload) == 200
    assert len(shown) == 3 and removed == ["run_a"]


def test_only_the_viewers_own_page_may_report(viewers):
    """A browser names the page a request comes from: another page open on this
    computer must not be able to tick acquisitions or ask for a file dialog."""
    view = viewers()
    url = view.start()
    shown, removed, opened, seen, picked = [], [], [], [], []
    view.on_show(lambda name, visible, only: shown.append(name))
    view.on_remove(removed.append)
    view.on_open(lambda: opened.append(True))
    view.on_view(seen.append)
    view.on_pick(picked.append)
    report = {"names": ["x"], "scales": [1e-6], "units": ["m"], "position": [5]}
    reports = {"show": {"name": "run_a"}, "remove": {"name": "run_a"}, "open": {}, "view": report, "pick": report}
    host, port = view._server.server_address[:2]
    strangers = [
        "http://evil.example",
        "https://evil.example:8443",
        f"http://{host}:{port + 1}",  # another program on this computer
        f"https://{host}:{port}",
        f"http://localhost:{port}",
        f"{url}elsewhere",
        "null",  # a page opened from a file
        "",
    ]
    for origin in strangers:
        for route, payload in reports.items():
            assert post(f"{url}api/{route}", payload, {"Origin": origin}) == 403, (origin, route)
    assert (shown, removed, opened, seen, picked) == ([], [], [], [], []), "and nothing was heard"
    assert view.position is None
    assert post(f"{url}api/nothing", {}, {"Origin": "http://evil.example"}) == 403

    # The viewer's own page, as a browser names it (without the last slash) or with it...
    for origin in (url.rstrip("/"), url):
        for route, payload in reports.items():
            assert post(f"{url}api/{route}", payload, {"Origin": origin}) == 200, (origin, route)
    assert shown == ["run_a"] * 2 and removed == ["run_a"] * 2 and opened == [True] * 2
    assert len(seen) == 2 and len(picked) == 2
    assert post(f"{url}api/nothing", {}, {"Origin": url.rstrip("/")}) == 404
    # ...and whatever does not say where it comes from: a script, or a page of the same origin.
    for route, payload in reports.items():
        assert post(f"{url}api/{route}", payload) == 200
    assert len(shown) == 3 and len(opened) == 3


def test_a_refused_report_leaves_the_connection_usable(viewers):
    """The page keeps its connections open: a refusal must take the report's body
    off the line, or the next request on it would be read from the middle of it."""
    import http.client
    import json

    view = viewers()
    url = view.start()
    shown = []
    view.on_show(lambda name, visible, only: shown.append(name))
    host, port = view._server.server_address[:2]
    line = http.client.HTTPConnection(host, port, timeout=10)
    try:
        body = json.dumps({"name": "run_a", "visible": True}).encode()
        line.request("POST", "/api/show", body, {"Content-Type": "application/json", "Origin": "http://evil.example"})
        answer = line.getresponse()
        assert answer.status == 403 and answer.read() == b""
        line.request("POST", "/api/show", body, {"Content-Type": "application/json", "Origin": url.rstrip("/")})
        answer = line.getresponse()
        assert answer.status == 200 and json.loads(answer.read()) == {"ok": True}
        line.request("GET", "/api/state")
        answer = line.getresponse()
        assert answer.status == 200 and "version" in json.loads(answer.read())
    finally:
        line.close()
    assert shown == ["run_a"]


def test_reading_is_open_to_any_page(viewers, tiles):
    # Only reports are kept to the viewer's own page: what is read changes nothing.
    view = viewers()
    view.add(tiles[0], layer="overview")
    url = view.start()
    stranger = {"Origin": "http://evil.example"}
    assert get(f"{url}api/state", stranger)[0] == 200
    assert get(f"{url}data/0/.zattrs", stranger)[0] == 200


def test_a_message_and_the_offered_list_reach_the_page(viewers):
    view = viewers()
    url = view.start()
    version = get_json(f"{url}api/state")["version"]
    view.say("tile_9.ome.zarr isn't an OME-Zarr folder the viewer can open.")
    offered = [{"name": "run_b", "shown": True, "live": True, "tiles": 2}, {"name": "run_a", "shown": False}]
    view.offer(offered)
    answer = get_json(f"{url}api/state?since={version}&wait=5")
    assert answer["notice"] == {
        "text": "tile_9.ome.zarr isn't an OME-Zarr folder the viewer can open.",
        "count": 1,
    }
    assert answer["acquisitions"] == offered
    version = answer["version"]
    view.offer(offered)
    assert get_json(f"{url}api/state")["version"] == version


def test_reports_from_the_page_come_back_in_micrometres(viewers, tiles):
    view = viewers()
    view.add(tiles[0], layer="overview")
    url = view.start()
    picked, seen = [], []
    view.on_pick(picked.append)
    view.on_view(seen.append)
    assert view.position is None
    report = {
        "names": ["t", "z", "y", "x"],
        "scales": [1, 5e-6, 1e-6, 1e-6],
        "units": ["s", "m", "m", "m"],
        "position": [0, 4, 30, 200],
    }
    assert post(f"{url}api/pick", report) == 200 and post(f"{url}api/view", report) == 200
    where = {"t": 0.0, "z": pytest.approx(20.0), "y": pytest.approx(30.0), "x": pytest.approx(200.0)}
    assert picked == [where] and seen == [where]
    assert view.position == where


# -- the end of a viewer ------------------------------------------------------------------------


def test_a_stopped_viewer_is_not_started_again(tiles):
    from mesoSPIM.src.mesospim_viewer import Viewer

    view = Viewer()
    view.add(tiles[0], layer="overview")
    url = view.start()
    assert view.start() == url and view.url == url, "started once, however often it is asked"
    assert status(url + "api/state") == 200
    view.stop()
    with pytest.raises(RuntimeError, match="stopped"):
        view.start()
    with pytest.raises(RuntimeError):
        view.url
    assert view._server is None and view._thread is not None and not _alive(view._thread)
    with pytest.raises(OSError):
        get(url + "api/state")  # nothing answers at the address any more
    # Whatever would have started the server again says the same, and starts nothing.
    for ask in (
        lambda: view.add(tiles[1], layer="overview"),
        lambda: view.guard(tiles[0], None),
        lambda: view.offer([]),
        lambda: view.say("hello"),
        lambda: view.fit(),
        lambda: view.look_at_newest(z=1.0),
        lambda: view.on_show(lambda name, visible, only: None),
    ):
        with pytest.raises(RuntimeError):
            ask()
    assert view._server is None
    # What only reads, or tells a page that is no longer there, passes quietly.
    view.landed(tiles[0], ["0/0.0.0.0.0"])
    view.preview_landed("live-1", ["0/0/0/0/0/0"])
    assert view.remove_preview("live-1") is False and view.position is None
    assert view.layers == ["overview"] and len(view.stores("overview")) == 1
    view.stop()  # stopping twice is nothing


def test_a_viewer_stopped_before_it_was_started_never_starts():
    from mesoSPIM.src.mesospim_viewer import Viewer

    view = Viewer()
    view.stop()
    with pytest.raises(RuntimeError):
        view.start()
    assert view._server is None and view._thread is None


def _alive(thread: threading.Thread) -> bool:
    thread.join(5)
    return thread.is_alive()
