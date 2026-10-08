"""Following a folder the microscope writes into: the watcher, and the window over it."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from mesoSPIM.src.mesospim_viewer import PAGE_DIR, Acquisitions, Viewer, Watcher
from mesoSPIM.src.mesospim_viewer.demo import write_tile


def an_acquisition(root: Path, name: str) -> Path:
    """An acquisition group the way the tczyx writer lays it out: a zarr group of tile stores."""
    group = root / f"{name}.ome.zarr"
    group.mkdir(parents=True)
    (group / ".zgroup").write_text('{"zarr_format": 2}')
    return group


def test_acquisitions_are_listed_newest_first_and_tiles_are_not_mistaken_for_them(tmp_path):
    older = an_acquisition(tmp_path, "run_a")
    write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    time.sleep(0.05)
    newer = an_acquisition(tmp_path, "run_b")
    # a bare tile store beside them is not an acquisition
    write_tile(tmp_path / "loose_tile.ome.zarr", origin_um=(0, 0, 0), seed=2)
    (tmp_path / "notes.txt").write_text("x")
    listed = Acquisitions(tmp_path).list()
    assert [a.path for a in listed] == [newer, older]
    assert [a.name for a in listed] == ["run_b", "run_a"]
    assert Acquisitions(tmp_path).newest().path == newer
    assert Acquisitions(tmp_path / "missing").list() == []


def test_the_watcher_adds_tiles_as_they_land_and_rereads_a_grown_one(tmp_path):
    acquisition = an_acquisition(tmp_path, "run")
    view = Viewer()
    watcher = Watcher(view, acquisition)
    try:
        assert watcher.poll() == []
        assert view.layers == []

        first = write_tile(
            acquisition / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1
        )
        assert watcher.poll() == [first]
        assert view.layers == ["run"]
        assert [s.path for s in view.stores("run")] == [first]
        assert watcher.poll() == [], "nothing changed, nothing done"

        second = write_tile(
            acquisition / "Mag1_Tile1_Sh0_Rot0.ome.zarr", origin_um=(0, 144, 0), seed=2
        )
        # a folder still being created is looked at again later, not shown half-made
        (acquisition / "Mag1_Tile2_Sh0_Rot0.ome.zarr").mkdir()
        assert watcher.poll() == [second]
        assert [s.path for s in view.stores("run")] == [first, second]
        revision_before = view.state["layers"][0]["_revision"]

        # a time point appended to the first tile: shown again, others untouched
        write_tile(first, origin_um=(0, 0, 0), seed=1, timepoints=2)
        assert watcher.poll() == [first]
        assert view.state["layers"][0]["_revision"] == revision_before + 1
        assert [s.shape[0] for s in view.stores("run")] == [2, 1]

        watcher.forget()
        assert view.layers == []
    finally:
        view.stop()


def test_a_tile_being_written_is_read_again_while_it_grows_and_once_it_has_settled(tmp_path):
    """The writer creates a tile's arrays when the stack starts and lands the chunks
    over the minutes after: the watcher shows the tile at once, reads it again
    while chunks keep coming, and once more after the last one. A quiet spell
    does not end the watching: the first chunk comes only after the camera's
    first few dozen frames, and at a slow frame rate the chunks come a long
    way apart."""
    acquisition = an_acquisition(tmp_path, "run")
    view = Viewer()
    watcher = Watcher(view, acquisition, settle_s=0.3, refresh_s=0.15, forget_s=1.2)
    try:
        tile = write_tile(acquisition / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
        # The arrays exist, the chunks are still to come.
        landing = [tile / "0" / "0.0.0.0.0", tile / "0" / "0.1.0.0.0"]
        held_back = {chunk: chunk.read_bytes() for chunk in landing}
        for chunk in landing:
            chunk.unlink()
        assert watcher.poll() == [tile], "shown the moment it can be read"
        revision = view.state["layers"][0]["_revision"]

        # nothing lands for longer than the settle: still watched
        time.sleep(0.35)
        assert watcher.poll() == []
        assert list(watcher.writing) == [tile]
        assert view.state["layers"][0]["_revision"] == revision

        # the first chunk, well after the settle: read again
        landing[0].write_bytes(held_back[landing[0]])
        assert watcher.poll() == [tile]
        assert view.state["layers"][0]["_revision"] == revision + 1
        revision += 1

        # chunks landing: read again every refresh_s while they keep coming...
        landing[1].write_bytes(held_back[landing[1]])
        assert watcher.poll() == [], "too soon after the last read"
        time.sleep(0.2)
        assert watcher.poll() == [tile], "chunks came, and the last read is refresh_s ago"
        assert view.state["layers"][0]["_revision"] == revision + 1
        landing[1].unlink()
        landing[1].write_bytes(held_back[landing[1]])
        time.sleep(0.05)
        assert watcher.poll() == []

        # ... and once more when none has come for settle_s
        time.sleep(0.35)
        assert watcher.poll() == [tile]
        assert view.state["layers"][0]["_revision"] == revision + 2
        assert list(watcher.writing) == [tile], "settled, and still watched"

        # a time point starting: the arrays grow first, the chunks land after
        write_tile(tile, origin_um=(0, 0, 0), seed=1, timepoints=2)
        assert watcher.poll() == [tile], "a grown shape is shown at once"
        assert [s.shape[0] for s in view.stores("run")] == [2]

        # only a long quiet ends the watching
        time.sleep(1.3)
        assert watcher.poll() == []
        assert watcher.writing == {}, "forgotten: not walked any more"
    finally:
        view.stop()


def test_the_follower_stays_on_the_newest_acquisition_until_an_older_one_is_chosen(tmp_path):
    from mesoSPIM.src.mesospim_viewer import Follower

    older = an_acquisition(tmp_path, "run_a")
    write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    view = Viewer()
    follower = Follower(view, tmp_path)
    try:
        assert follower.poll() is True and follower.names == ["run_a"]
        assert follower.shown == older and follower.shown_index == 0
        assert view.layers == ["run_a"]
        assert follower.poll() is False

        time.sleep(0.05)
        newer = an_acquisition(tmp_path, "run_b")
        write_tile(newer / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=2)
        assert follower.poll() is True
        assert follower.shown == newer, "a new acquisition is followed on its own"
        assert follower.names == ["run_b", "run_a"] and follower.shown_index == 0
        assert view.layers == ["run_b"]

        follower.choose(1)
        assert follower.shown == older and follower.following is False
        write_tile(newer / "Mag1_Tile1_Sh0_Rot0.ome.zarr", origin_um=(0, 144, 0), seed=3)
        follower.poll()
        assert follower.shown == older, "a chosen acquisition stays while the newest grows"

        follower.follow_latest()
        assert follower.shown == newer and follower.following is True
        assert len(view.stores("run_b")) == 2, "and the tile that landed meanwhile is there"
        follower.choose(0)
        assert follower.following is True

        # The panel's dropdown is fed by the follower and drives it back.
        assert view._server.scene.choices == {"names": ["run_b", "run_a"], "current": 0, "live": True}
        view._server.choice_reported({"index": 1})
        assert follower.shown == older and follower.following is False
        assert view._server.scene.choices == {"names": ["run_b", "run_a"], "current": 1, "live": True}
    finally:
        view.stop()



def test_an_acquired_dataset_is_shown_as_it_is_and_nothing_new_is_followed(tmp_path):
    from mesoSPIM.src.mesospim_viewer import NotAStore, Opened

    older = an_acquisition(tmp_path, "run_a")
    tile = write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    write_tile(older / "Mag1_Tile1_Sh0_Rot0.ome.zarr", origin_um=(0, 144, 0), seed=2)
    time.sleep(0.05)
    newer = an_acquisition(tmp_path, "run_b")
    write_tile(newer / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=3)

    # One acquisition: all its tiles, in one layer named after it, and no dropdown.
    view = Viewer()
    try:
        opened = Opened(view, older)
        assert view.layers == ["run_a"] and len(view.stores("run_a")) == 2
        assert opened.follower is None
        assert view._server.scene.choices["names"] == [], "no dropdown for a single acquisition"
    finally:
        view.stop()

    # One tile store on its own.
    view = Viewer()
    try:
        Opened(view, tile)
        assert view.layers == ["Mag1_Tile0_Sh0_Rot0"] and len(view.stores("Mag1_Tile0_Sh0_Rot0")) == 1
    finally:
        view.stop()

    # A data folder: the newest is shown, the dropdown offers the rest, and a newer
    # acquisition appearing later is not switched to.
    view = Viewer()
    try:
        opened = Opened(view, tmp_path)
        assert opened.follower.shown == newer and opened.follower.following is False
        # Nothing is being acquired here: the newest is not called the current one.
        assert view._server.scene.choices == {"names": ["run_b", "run_a"], "current": 0, "live": False}
        view._server.choice_reported({"index": 1})
        assert opened.follower.shown == older
        time.sleep(0.05)
        newest = an_acquisition(tmp_path, "run_c")
        write_tile(newest / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=4)
        assert opened.follower.shown == older
    finally:
        view.stop()

    # A folder with nothing the viewer can show says so.
    (tmp_path / "empty").mkdir()
    view = Viewer()
    try:
        with pytest.raises(NotAStore, match="not a dataset the viewer can open"):
            Opened(view, tmp_path / "empty")
    finally:
        view.stop()


def _sources(view: Viewer, layer: str) -> list[dict]:
    """The sources the page is asked to show for one acquisition's first channel."""
    first = next(spec for spec in view.state["layers"] if spec["name"].startswith(layer + " · "))
    return first["source"]


def test_dropped_folders_are_added_beside_what_is_shown(tmp_path):
    from mesoSPIM.src.mesospim_viewer import NotAStore, Opened

    first = an_acquisition(tmp_path / "day1", "run_a")
    write_tile(first / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    second = an_acquisition(tmp_path / "day2", "run_b")
    write_tile(second / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 1000), seed=2)
    write_tile(second / "Mag1_Tile1_Sh0_Rot0.ome.zarr", origin_um=(0, 144, 1000), seed=3)
    loose = write_tile(tmp_path / "loose" / "single.ome.zarr", origin_um=(0, 500, 0), seed=4, timepoints=3)
    # The same acquisition name on another day: a second block, never merged into the first.
    again = an_acquisition(tmp_path / "day3", "run_a")
    write_tile(again / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 2000), seed=5)

    view = Viewer()
    try:
        opened = Opened(view, first)
        assert opened.add(second) == ["run_b"]
        assert opened.add(loose) == ["single"]
        assert opened.add(again) == ["run_a (2)"]
        assert view.layers == ["run_a", "run_b", "single", "run_a (2)"]
        assert [s.path.name for s in view.stores("run_b")] == ["Mag1_Tile0_Sh0_Rot0.ome.zarr", "Mag1_Tile1_Sh0_Rot0.ome.zarr"]
        # Each placed by its own metadata: the viewer shifts none of them.
        assert [s.translation[-3:] for s in view.stores("run_b")] == [(0, 0, 1000), (0, 144, 1000)]
        assert all("transform" not in source for source in _sources(view, "run_b"))
        assert view.stores("run_a (2)")[0].translation[-3:] == (0, 0, 2000)
        # Channels share one contrast row per name within each acquisition, as before.
        assert [spec["name"] for spec in view.state["layers"]][:4] == [
            "run_a · 488", "run_a · 561", "run_b · 488", "run_b · 561"
        ]
        assert view.stores("single")[0].shape[0] == 3, "its time points reach the time slider"

        # The same folder dropped twice is the same block, read again.
        assert opened.add(second) == ["run_b"]
        assert view.layers == ["run_a", "run_b", "single", "run_a (2)"]

        # A folder that holds acquisitions adds each of them, oldest first.
        both = tmp_path / "session"
        older = an_acquisition(both, "run_c")
        write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 3000), seed=6)
        time.sleep(0.05)
        newer = an_acquisition(both, "run_d")
        write_tile(newer / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 4000), seed=7)
        assert opened.add(both) == ["run_c", "run_d"]

        # What cannot be shown says why, in one short sentence naming only the
        # folder, and leaves what is shown alone.
        from mesoSPIM.src.mesospim_viewer.window import refusal

        def refused(path):
            with pytest.raises(NotAStore) as caught:
                opened.add(path)
            return refusal(path, caught.value)

        (tmp_path / "notes").mkdir()
        assert refused(tmp_path / "notes") == "notes isn't an OME-Zarr folder the viewer can open."
        broken = tmp_path / "broken.ome.zarr"
        broken.mkdir()
        (broken / ".zattrs").write_text("{not json")
        assert refused(broken) == "broken.ome.zarr can't be shown: its metadata could not be read."
        newer_format = write_tile(tmp_path / "newer.ome.zarr", origin_um=(0, 0, 0), seed=8)
        attrs = json.loads((newer_format / ".zattrs").read_text())
        attrs["multiscales"][0]["version"] = "0.6"
        (newer_format / ".zattrs").write_text(json.dumps(attrs))
        assert refused(newer_format) == (
            "newer.ome.zarr can't be shown: it is OME-NGFF 0.6, which the viewer does not read yet."
        )
        # An acquisition whose tiles cannot be read says why its tiles could not.
        odd = an_acquisition(tmp_path / "odd", "run_x")
        attrs["multiscales"][0]["version"] = "0.4"
        attrs["multiscales"][0]["axes"][1]["type"] = "space"
        tile = write_tile(odd / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=9)
        (tile / ".zattrs").write_text(json.dumps(attrs))
        assert refused(odd) == "run_x.ome.zarr can't be shown: its axis c is not of type channel."
        assert refusal(tmp_path / "gone", OSError("no such folder")) == (
            "gone isn't an OME-Zarr folder the viewer can open."
        )
        assert view.layers == ["run_a", "run_b", "single", "run_a (2)", "run_c", "run_d"]
    finally:
        view.stop()


def test_the_remove_button_takes_one_acquisition_off_the_view(tmp_path):
    from mesoSPIM.src.mesospim_viewer import Opened

    first = an_acquisition(tmp_path / "day1", "run_a")
    write_tile(first / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    second = an_acquisition(tmp_path / "day2", "run_b")
    write_tile(second / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 1000), seed=2)

    view = Viewer()
    try:
        opened = Opened(view, first)
        opened.add(second)
        # The page offers a remove button only where something listens for it.
        assert view._server.scene.ui.get("removable") is True
        view._server.remove_reported({"name": "run_a"})
        assert view.layers == ["run_b"]
        assert [spec["name"] for spec in view.state["layers"]] == ["run_b · 488", "run_b · 561"]
        # Dropped again after removal, it comes back under its own name.
        assert opened.add(first) == ["run_a"]
        assert opened.remove("nothing such") is False
    finally:
        view.stop()

    # In a folder of acquisitions, removing the one picked in the dropdown takes it
    # out of the dropdown and shows the next one down, or the one above when it
    # was the last; the dropdown empties only when none remain.
    session = tmp_path / "session"
    for seed, name in enumerate(["run_c", "run_d", "run_e"]):
        write_tile(an_acquisition(session, name) / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=seed)
        time.sleep(0.05)
    view = Viewer()
    try:
        opened = Opened(view, session)
        choices = lambda: view._server.scene.choices
        assert view.layers == ["run_e"]
        assert opened.remove("run_e") is True
        assert view.layers == ["run_d"]
        assert choices() == {"names": ["run_d", "run_c"], "current": 0, "live": False}
        view._server.choice_reported({"index": 1})
        assert view.layers == ["run_c"]
        assert opened.remove("run_c") is True
        assert view.layers == ["run_d"]
        assert choices() == {"names": ["run_d"], "current": 0, "live": False}
        assert opened.remove("run_d") is True
        assert view.layers == []
        assert choices() == {"names": [], "current": -1, "live": False}
    finally:
        view.stop()

    # The live window offers no remove button.
    view = Viewer()
    try:
        from mesoSPIM.src.mesospim_viewer import Follower

        Follower(view, tmp_path / "session").poll()
        assert view._server.scene.ui.get("removable") is None
    finally:
        view.stop()


def test_the_dropdown_numbers_an_acquisition_whose_name_a_drop_already_shows(tmp_path):
    from mesoSPIM.src.mesospim_viewer import Opened

    session = tmp_path / "session"
    older = an_acquisition(session, "run_a")
    write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    time.sleep(0.05)
    newer = an_acquisition(session, "run_b")
    write_tile(newer / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 500), seed=2)
    dropped = an_acquisition(tmp_path / "day1", "run_a")
    write_tile(dropped / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 1000), seed=3)

    view = Viewer()
    try:
        opened = Opened(view, session)
        assert opened.add(dropped) == ["run_a"]
        # The dropdown's run_a is a different acquisition: it gets a block of its own.
        view._server.choice_reported({"index": 1})
        assert view.layers == ["run_a", "run_a (2)"]
        assert view.stores("run_a")[0].path.parent == dropped
        assert view.stores("run_a (2)")[0].path.parent == older
        # Its remove button is the dropdown's: the next one down is shown instead.
        assert opened.remove("run_a (2)") is True
        assert view.layers == ["run_a", "run_b"]
        assert view._server.scene.choices["names"] == ["run_b"]
    finally:
        view.stop()


# -- the Qt window ---------------------------------------------------------------
#
# QtWebEngine aborts the whole process when it cannot create an OpenGL context
# (a container without Mesa, say), which no skip can catch. So the window is only
# exercised when asked for: MESOSPIM_VIEWER_QT_TESTS=1 on a machine with a display
# stack. What it does is tested above through Follower; this only checks the
# binding to Qt.


# One QApplication for the session: Qt WebEngine cannot start again in a process
# whose first QApplication has gone, and crashes the process when asked to.
@pytest.fixture(scope="session")
def qt_app():
    if not os.environ.get("MESOSPIM_VIEWER_QT_TESTS"):
        pytest.skip("set MESOSPIM_VIEWER_QT_TESTS=1 to drive the Qt window (needs OpenGL)")
    if not (PAGE_DIR / "index.html").is_file():
        pytest.skip("the mesoSPIM page is not built")
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")
    try:
        from mesoSPIM.src.mesospim_viewer.viewer import _qt

        qt = _qt()
    except ImportError as error:
        pytest.skip(f"no Qt WebEngine binding: {error}")
    app = qt.QtWidgets.QApplication.instance() or qt.QtWidgets.QApplication([])
    yield app, qt


def _spin(qt, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qt.QtWidgets.QApplication.processEvents()
        time.sleep(0.02)


def test_the_window_shows_the_page_and_follows_on_its_timer(tmp_path, qt_app):
    app, qt = qt_app
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    older = an_acquisition(tmp_path, "run_a")
    write_tile(older / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    window = make_window_class()(tmp_path)
    try:
        # The web view holds the viewer's page.
        view = window.findChild(qt.QWebEngineView)
        assert view is not None
        _spin(qt, 1.0)
        assert view.url().toString().startswith("http://127.0.0.1:")
        assert window.follower.shown == older
        assert window.follower.names == ["run_a"]
        # A newer acquisition is followed on the window's own timer.
        time.sleep(0.05)
        newer = an_acquisition(tmp_path, "run_b")
        write_tile(newer / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=2)
        _spin(qt, 1.5)
        assert window.follower.shown == newer and window.follower.names == ["run_b", "run_a"]
        # The page's dropdown answers through the viewer: an older entry is shown
        # and stays shown, the first entry follows the newest again.
        window.follower.choose(1)
        _spin(qt, 1.5)
        assert window.follower.shown == older and not window.follower.following
        window.follower.choose(0)
        assert window.follower.shown == newer and window.follower.following
    finally:
        window.close()


def _evaluate(qt, view, script: str, timeout_s: float = 20.0):
    """Run ``script`` in the window's page and return its result."""
    answer = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        view.page().runJavaScript(script, answer.append)
        _spin(qt, 0.3)
        if answer and answer[-1] is not None:
            return answer[-1]
        answer.clear()
    return None


# Where each part of the time slider sits, once the slider is shown.
SLIDER_PARTS = """(() => {
  const box = document.querySelector('#slider-t');
  if (!box || box.hidden) return null;
  const at = (part) => { const r = box.querySelector(part).getBoundingClientRect(); return [r.left, r.right]; };
  return { name: at('.name'), input: at('input'), reading: at('.reading') };
})()"""


def test_the_window_draws_the_time_slider_clear_of_its_label(tmp_path, qt_app):
    """The window's old browser (Chromium 83) has no gaps in flex rows: the slider
    must keep its label and its reading apart some other way."""
    app, qt = qt_app
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    write_tile(tmp_path / "timelapse.ome.zarr", origin_um=(0, 0, 0), seed=1, timepoints=3)
    window = make_window_class()(tmp_path / "timelapse.ome.zarr", live=False)
    try:
        window.resize(1200, 800)
        window.show()
        view = window.findChild(qt.QWebEngineView)
        parts = _evaluate(qt, view, SLIDER_PARTS)
        assert parts is not None, "the time slider never appeared"
        assert parts["input"][0] - parts["name"][1] >= 6, parts
        assert parts["reading"][0] - parts["input"][1] >= 6, parts
    finally:
        window.close()


def _drag(qt, window, paths: list[Path]) -> tuple[bool, bool]:
    """Drag ``paths`` onto the window's picture and let go, as the file manager does.

    The events go to the widget Qt hands a drag to, the web view's own drawing
    surface; return whether the drag was let in and whether the drop was taken.
    """
    QtCore, QtGui = qt.QtCore, qt.QtGui
    view = window.findChild(qt.QWebEngineView)
    target = view.focusProxy() or view
    mime = QtCore.QMimeData()
    mime.setUrls([QtCore.QUrl.fromLocalFile(str(path)) for path in paths])
    at = QtCore.QPoint(200, 200)
    enter = QtGui.QDragEnterEvent(at, QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    qt.QtWidgets.QApplication.sendEvent(target, enter)
    if not enter.isAccepted():
        return False, False
    drop = QtGui.QDropEvent(QtCore.QPointF(at), QtCore.Qt.CopyAction, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    qt.QtWidgets.QApplication.sendEvent(target, drop)
    return True, drop.isAccepted()


# What the window's page shows: the panel's acquisition blocks, the message on
# the picture, whether Show all is offered, and where the camera looks.
PAGE = """(() => {
  const v = window.viewer; if (!v?.layerManager) return null;
  const n = v.navigationState, space = n.position.coordinateSpace.value;
  if (!space?.rank) return null;
  const at = (axis) => { const i = space.names.indexOf(axis); return n.position.value[i] * space.scales[i] * 1e6; };
  const notice = document.querySelector('#notice'), showAll = document.querySelector('#show-all');
  return JSON.stringify({
    groups: [...document.querySelectorAll('.group')].map(g => g.dataset.group),
    removable: document.querySelectorAll('.group .remove').length,
    notice: notice && !notice.hidden ? notice.querySelector('.text').textContent : null,
    showAll: !!showAll && !showAll.hidden,
    x: at('x'), zoom: n.zoomFactor.value,
    loaded: v.layerManager.managedLayers.every(m => (m.layer?.dataSources ?? []).every(s => s.loadState !== undefined)),
  });
})()"""


def _page_until(qt, view, wanted, timeout_s: float = 60.0) -> dict:
    """The page's state once ``wanted`` holds and nothing has moved for a second
    (or the last state seen, for the assert to show)."""
    import json

    def look():
        raw = _evaluate(qt, view, PAGE)
        return json.loads(raw) if raw else None

    deadline = time.monotonic() + timeout_s
    seen = None
    while time.monotonic() < deadline:
        seen = look()
        if seen and seen["loaded"] and wanted(seen):
            _spin(qt, 1.0)
            if look() == seen:
                return seen
        _spin(qt, 0.2)
    return seen


def test_folders_dropped_on_the_window_are_added_and_can_be_removed(tmp_path, qt_app):
    app, qt = qt_app
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    first = an_acquisition(tmp_path / "day1", "run_a")
    write_tile(first / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    second = an_acquisition(tmp_path / "day2", "run_b")
    write_tile(second / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 1000), seed=2)
    third = write_tile(tmp_path / "day3" / "single.ome.zarr", origin_um=(0, 0, 2000), seed=3)
    (tmp_path / "notes").mkdir()

    window = make_window_class()(first, live=False)
    try:
        window.resize(1200, 800)
        window.show()
        view = window.findChild(qt.QWebEngineView)
        alone = _page_until(qt, view, lambda s: s["groups"] == ["run_a"])
        assert alone["x"] == pytest.approx(80, abs=2) and alone["showAll"] is False

        # Two folders at once, one of them not a dataset: the other still opens,
        # beside the first, and the window says in a sentence why one did not.
        assert _drag(qt, window, [second, tmp_path / "notes"]) == (True, True)
        both = _page_until(qt, view, lambda s: s["groups"] == ["run_a", "run_b"] and s["x"] > 500)
        assert window.viewer.layers == ["run_a", "run_b"]
        assert both["notice"] == "notes isn't an OME-Zarr folder the viewer can open."
        # Overview mode: the view zoomed out to frame both acquisitions.
        assert both["x"] == pytest.approx((0 + 1160) / 2, abs=2)
        assert both["zoom"] > alone["zoom"] * 3
        assert both["removable"] == 2

        # The operator zooms in: from then on the view stays, and Show all is offered.
        _evaluate(qt, view, "(() => { window.viewer.navigationState.zoomFactor.value /= 4; return 1; })()")
        theirs = _page_until(qt, view, lambda s: s["showAll"])
        assert theirs["showAll"] is True
        assert _drag(qt, window, [third]) == (True, True)
        three = _page_until(qt, view, lambda s: len(s["groups"]) == 3)
        assert three["groups"] == ["run_a", "run_b", "single"]
        assert (three["x"], three["zoom"]) == (pytest.approx(theirs["x"]), pytest.approx(theirs["zoom"]))
        assert three["notice"] is None, "a drop that fully opened clears the old message"

        # Show all frames everything again.
        _evaluate(qt, view, "(() => { document.querySelector('#show-all').click(); return 1; })()")
        everything = _page_until(qt, view, lambda s: not s["showAll"])
        assert everything["x"] == pytest.approx((0 + 2160) / 2, abs=2)

        # The remove button on a block takes that acquisition off the view.
        _evaluate(qt, view, """(() => { document.querySelector('.group[data-group="run_b"] .remove').click(); return 1; })()""")
        _page_until(qt, view, lambda s: s["groups"] == ["run_a", "single"])
        assert window.viewer.layers == ["run_a", "single"]
    finally:
        window.close()


def test_the_live_window_refuses_a_drop_and_offers_no_remove_button(tmp_path, qt_app):
    app, qt = qt_app
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    run = an_acquisition(tmp_path / "data", "run_a")
    write_tile(run / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
    other = an_acquisition(tmp_path / "elsewhere", "run_b")
    write_tile(other / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 1000), seed=2)

    window = make_window_class()(tmp_path / "data")
    try:
        window.resize(1200, 800)
        window.show()
        view = window.findChild(qt.QWebEngineView)
        page = view.url().toString()
        shown = _page_until(qt, view, lambda s: s["groups"] == ["run_a"])
        assert shown["removable"] == 0
        assert _drag(qt, window, [other]) == (False, False)
        _spin(qt, 1.5)
        assert window.viewer.layers == ["run_a"]
        assert view.url().toString() == page, "the page was not replaced by the dropped folder"
    finally:
        window.close()
