"""Following a folder the microscope writes into: the watcher, and the window over it."""

from __future__ import annotations

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
    while chunks keep coming, and once more after the last one."""
    acquisition = an_acquisition(tmp_path, "run")
    view = Viewer()
    watcher = Watcher(view, acquisition, settle_s=0.3, refresh_s=0.15)
    try:
        tile = write_tile(acquisition / "Mag1_Tile0_Sh0_Rot0.ome.zarr", origin_um=(0, 0, 0), seed=1)
        assert watcher.poll() == [tile], "shown the moment it can be read"
        revision = view.state["layers"][0]["_revision"]

        # nothing lands: not read again, and after a quiet spell no longer watched
        time.sleep(0.35)
        assert watcher.poll() == []
        assert watcher.writing == {}
        assert view.state["layers"][0]["_revision"] == revision

        # a time point starting: the arrays grow first, the chunks land after
        write_tile(tile, origin_um=(0, 0, 0), seed=1, timepoints=2)
        landing = [tile / "0" / "1.1.0.0.0", tile / "0" / "1.1.1.0.0"]
        held_back = {chunk: chunk.read_bytes() for chunk in landing}
        for chunk in landing:
            chunk.unlink()
        assert watcher.poll() == [tile], "a grown shape is shown at once"
        revision = view.state["layers"][0]["_revision"]

        # chunks landing: read again every refresh_s while they keep coming...
        landing[0].write_bytes(held_back[landing[0]])
        assert watcher.poll() == [], "too soon after the last read"
        time.sleep(0.2)
        assert watcher.poll() == [tile], "chunks came, and the last read is refresh_s ago"
        assert view.state["layers"][0]["_revision"] == revision + 1
        landing[1].write_bytes(held_back[landing[1]])
        time.sleep(0.05)
        assert watcher.poll() == []

        # ... and once more when none has come for settle_s
        time.sleep(0.35)
        assert watcher.poll() == [tile]
        assert view.state["layers"][0]["_revision"] == revision + 2
        assert watcher.writing == {}, "settled: not walked any more"
        time.sleep(0.35)
        assert watcher.poll() == []
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
        assert view._server.scene.choices == {"names": ["run_b", "run_a"], "current": 0}
        view._server.choice_reported({"index": 1})
        assert follower.shown == older and follower.following is False
        assert view._server.scene.choices == {"names": ["run_b", "run_a"], "current": 1}
    finally:
        view.stop()


# -- the Qt window ---------------------------------------------------------------
#
# QtWebEngine aborts the whole process when it cannot create an OpenGL context
# (a container without Mesa, say), which no skip can catch. So the window is only
# exercised when asked for: MESOSPIM_VIEWER_QT_TESTS=1 on a machine with a display
# stack. What it does is tested above through Follower; this only checks the
# binding to Qt.


@pytest.fixture
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
