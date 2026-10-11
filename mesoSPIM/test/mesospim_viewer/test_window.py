"""The Data viewer window: the library, a timer and the page, in Qt.

QtWebEngine aborts the whole process when it cannot create an OpenGL context
(a container without Mesa, say), which no skip can catch. So the window is only
exercised when asked for: ``MESOSPIM_VIEWER_QT_TESTS=1`` on a machine with a
display stack (``-k qt`` or ``-m qt`` picks these tests). What the window shows is decided by :class:`Library` and tested
without Qt in ``test_library.py`` and ``test_feed.py``; this only checks the
binding to Qt: the web view holds the page, the timer looks at the disk, folders
that are dropped are opened, and the microscope's feed reaches the library --
all of it off the GUI thread, so every check waits for its effect.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pytest

from mesoSPIM.src.mesospim_viewer import PAGE_DIR, Stack
from mesoSPIM.src.mesospim_viewer.demo import write_tile
from mesoSPIM.src.mesospim_viewer.window import is_data_folder, refusal

from .stores import an_acquisition
from .tools import follow, landed, offered

TILE = "Mag1_Tile{}_Sh0_Rot0.ome.zarr"


def a_run(root: Path, name: str, *, seed: int = 1, x: float = 0.0) -> Path:
    time.sleep(0.05)
    acquisition = an_acquisition(root, name)
    write_tile(acquisition / TILE.format(0), origin_um=(0, 0, x), seed=seed)
    return acquisition


# -- without Qt ---------------------------------------------------------------------


def test_a_folder_of_acquisitions_is_told_from_a_dataset(tmp_path):
    run = a_run(tmp_path / "data", "run_a")
    assert is_data_folder(tmp_path / "data") is True, "watched: acquisitions are written into it"
    assert is_data_folder(run) is False and is_data_folder(run / TILE.format(0)) is False
    assert is_data_folder(tmp_path / "missing") is False
    (tmp_path / "empty.ome.zarr").mkdir()
    assert is_data_folder(tmp_path / "empty.ome.zarr") is False


def test_a_refusal_names_only_the_folder(tmp_path):
    from mesoSPIM.src.mesospim_viewer import NotAStore

    assert refusal(tmp_path / "notes", NotAStore("a long sentence with the whole path")) == (
        "notes isn't an OME-Zarr folder the viewer can open."
    )
    assert refusal(tmp_path / "x.ome.zarr", NotAStore("...", reason="its metadata could not be read")) == (
        "x.ome.zarr can't be shown: its metadata could not be read."
    )


# -- the Qt window ---------------------------------------------------------------------


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


@pytest.fixture
def windows(qt_app):
    """Makes Data viewer windows, shown at a fixed size, and closes them after the test."""
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    made = []

    def make(folder=None):
        window = make_window_class()(folder)
        window.resize(1200, 800)
        window.show()
        made.append(window)
        return window

    yield make
    for window in made:
        window.close()


def _spin(qt, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qt.QtWidgets.QApplication.processEvents()
        time.sleep(0.02)


def _until(qt, look, wanted=lambda seen: bool(seen), timeout_s: float = 20.0):
    """Keep Qt going until ``wanted`` holds for what ``look`` returns; return the last answer."""
    deadline = time.monotonic() + timeout_s
    seen = look()
    while not wanted(seen) and time.monotonic() < deadline:
        _spin(qt, 0.1)
        seen = look()
    return seen


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


# What the window's page shows: the panel's list, the channel groups, the message
# on the picture, whether Fit is offered, and where the camera looks.
PAGE = """(() => {
  const v = window.viewer; if (!v?.layerManager) return null;
  const n = v.navigationState, space = n.position.coordinateSpace.value;
  const at = (axis) => { const i = (space?.names ?? []).indexOf(axis); return i < 0 ? null : n.position.value[i] * space.scales[i] * 1e6; };
  const notice = document.querySelector('#notice'), fit = document.querySelector('#fit'), empty = document.querySelector('#empty');
  return JSON.stringify({
    chrome: document.documentElement.dataset.chrome,
    listed: [...document.querySelectorAll('.card.acquisitions .acquisition')].map(r => [r.dataset.name, r.classList.contains('shown')]),
    removable: [...document.querySelectorAll('.card.acquisitions .acquisition .remove')].map(b => b.closest('.acquisition').dataset.name),
    groups: [...document.querySelectorAll('.group')].map(g => g.dataset.group),
    notice: notice && !notice.hidden ? notice.querySelector('.text').textContent : null,
    empty: empty && !empty.hidden ? empty.querySelector('.title').textContent : null,
    open: !document.querySelector('.card.load .open').hidden,
    fit: !!fit && !fit.hidden,
    x: at('x'), zoom: n.zoomFactor.value,
    loaded: v.layerManager.managedLayers.every(m => (m.layer?.dataSources ?? []).every(s => s.loadState !== undefined)),
  });
})()"""


def _page_until(qt, view, wanted, timeout_s: float = 60.0) -> dict:
    """The page's state once ``wanted`` holds and nothing has moved for a second
    (or the last state seen, for the assert to show)."""

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


@pytest.mark.qt
def test_the_window_shows_the_page_and_follows_its_folder_on_its_timer(tmp_path, qt_app, windows):
    app, qt = qt_app
    a_run(tmp_path, "run_a")
    window = windows(tmp_path)
    # The web view holds the viewer's page, with our panel over the engine.
    assert window.web is window.findChild(qt.QWebEngineView)
    library = window.library
    assert _until(qt, lambda: library.shown) == ["run_a"], "the folder is looked at off the GUI thread"
    assert window.web.url().toString() == window.viewer.url
    assert window.web.url().toString().startswith("http://127.0.0.1:")
    shown = _page_until(qt, window.web, lambda s: s["groups"] == ["run_a"])
    assert shown["chrome"] == "simple"
    assert shown["listed"] == [["run_a", True]] and shown["removable"] == ["run_a"]
    assert shown["open"] is True, "the window can ask for a folder, so the panel offers Open"
    assert shown["empty"] is None and shown["x"] == pytest.approx(80, abs=2)
    # A newer acquisition is shown in its place on the window's own timer.
    a_run(tmp_path, "run_b", seed=2)
    assert _until(qt, lambda: library.shown, lambda seen: seen == ["run_b"]) == ["run_b"]
    assert library.names == ["run_b", "run_a"]
    after = _page_until(qt, window.web, lambda s: s["groups"] == ["run_b"])
    assert after["listed"] == [["run_b", True], ["run_a", False]]


@pytest.mark.qt
def test_a_window_over_nothing_says_what_it_waits_for(qt_app, windows):
    app, qt = qt_app
    window = windows()
    seen = _page_until(qt, window.web, lambda s: s["empty"] is not None)
    assert seen["empty"] == "No acquisition yet" and seen["listed"] == [] and seen["open"] is True
    assert window.library.root is None


# Where each part of the time slider sits, once the slider is shown.
SLIDER_PARTS = """(() => {
  const box = document.querySelector('#slider-t');
  if (!box || box.hidden) return null;
  const at = (part) => { const r = box.querySelector(part).getBoundingClientRect(); return [r.left, r.right]; };
  return { name: at('.name'), input: at('input'), reading: at('.reading') };
})()"""


@pytest.mark.qt
def test_the_window_draws_the_time_slider_clear_of_its_label(tmp_path, qt_app, windows):
    """The window's old browser (Chromium 83) has no gaps in flex rows: the slider
    must keep its label and its reading apart some other way."""
    app, qt = qt_app
    window = windows()
    window.open(write_tile(tmp_path / "timelapse.ome.zarr", origin_um=(0, 0, 0), seed=1, timepoints=3))
    assert _until(qt, lambda: window.library.shown) == ["timelapse"]
    parts = _evaluate(qt, window.web, SLIDER_PARTS)
    assert parts is not None, "the time slider never appeared"
    assert parts["input"][0] - parts["name"][1] >= 6, parts
    assert parts["reading"][0] - parts["input"][1] >= 6, parts


@pytest.mark.qt
def test_folders_given_to_drop_are_listed_and_what_cannot_be_opened_is_said(tmp_path, qt_app, windows):
    app, qt = qt_app
    a_run(tmp_path / "data", "run_a")
    second = a_run(tmp_path / "day2", "run_b", seed=2, x=1000)
    third = write_tile(tmp_path / "day3" / "single.ome.zarr", origin_um=(0, 0, 2000), seed=3)
    (tmp_path / "notes").mkdir()
    window = windows(tmp_path / "data")
    library = window.library
    alone = _page_until(qt, window.web, lambda s: s["groups"] == ["run_a"])
    assert alone["x"] == pytest.approx(80, abs=2) and alone["fit"] is False

    # Two folders at once, one of them not a dataset: the other still opens,
    # beside what is shown, and the window says in a sentence why one did not.
    window.drop([second, tmp_path / "notes"])
    assert _until(qt, lambda: library.shown, lambda seen: len(seen) == 2) == ["run_a", "run_b"]
    both = _page_until(qt, window.web, lambda s: s["groups"] == ["run_a", "run_b"] and s["x"] > 500)
    assert both["listed"] == [["run_a", True], ["run_b", True]]
    assert both["removable"] == ["run_a", "run_b"], "any acquisition but the run being acquired can be taken off"
    assert both["notice"] == "notes isn't an OME-Zarr folder the viewer can open."
    # The view zoomed out to frame both acquisitions.
    assert both["x"] == pytest.approx((0 + 1160) / 2, abs=2)
    assert both["zoom"] > alone["zoom"] * 3

    # A drop that fully opens clears the old message.
    window.open(third)
    three = _page_until(qt, window.web, lambda s: len(s["groups"]) == 3)
    assert three["groups"] == ["run_a", "run_b", "single"] and three["notice"] is None
    assert library.names == ["run_a", "run_b", "single"]

    # The remove button on a row takes that dataset off the list.
    _evaluate(qt, window.web, """(() => { document.querySelector('.acquisition[data-name="run_b"] .remove').click(); return 1; })()""")
    left = _page_until(qt, window.web, lambda s: s["groups"] == ["run_a", "single"])
    assert left["listed"] == [["run_a", True], ["single", True]]
    assert library.names == ["run_a", "single"] and window.viewer.layers == ["run_a", "single"]


def _drag(qt, window, paths: list[Path]) -> tuple[bool, bool]:
    """Drag ``paths`` onto the window's picture and let go, as the file manager does.

    The events go to the widget Qt hands a drag to, the web view's own drawing
    surface; return whether the drag was let in and whether the drop was taken.
    """
    QtCore, QtGui = qt.QtCore, qt.QtGui
    target = window.web.focusProxy() or window.web
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


@pytest.mark.qt
def test_a_folder_dragged_onto_the_picture_is_opened_and_the_page_is_not_replaced(tmp_path, qt_app, windows):
    app, qt = qt_app
    a_run(tmp_path / "data", "run_a")
    other = a_run(tmp_path / "elsewhere", "run_b", seed=2, x=1000)
    window = windows(tmp_path / "data")
    _page_until(qt, window.web, lambda s: s["groups"] == ["run_a"])
    address = window.web.url().toString()
    assert _drag(qt, window, [other]) == (True, True)
    assert _until(qt, lambda: window.library.shown, lambda seen: len(seen) == 2) == ["run_a", "run_b"]
    _spin(qt, 1.0)
    assert window.web.url().toString() == address, "the page was not replaced by the dropped folder"
    # A drag that carries no folder is not taken.
    mime = qt.QtCore.QMimeData()
    mime.setText("just words")
    enter = qt.QtGui.QDragEnterEvent(
        qt.QtCore.QPoint(200, 200), qt.QtCore.Qt.CopyAction, mime, qt.QtCore.Qt.LeftButton, qt.QtCore.Qt.NoModifier
    )
    qt.QtWidgets.QApplication.sendEvent(window.web.focusProxy() or window.web, enter)
    assert not enter.isAccepted()


@pytest.mark.qt
def test_the_microscopes_feed_reaches_the_library_through_the_window(tmp_path, qt_app, windows):
    app, qt = qt_app
    window = windows(tmp_path)
    library, view = window.library, window.viewer
    stack = Stack(
        acquisition="run", channel="488", channels=("488", "561"), planes=16, frame=(2048, 2048),
        voxel_um=(5.0, 1.0, 1.0), origin_um=(0.0, 0.0, 0.0), tile="Tile 1", tiles=1,
    )
    frame = np.full((2048, 2048), 700, np.uint16)
    frame[:512, :512] = 3000
    began = time.perf_counter()
    window.begin_stack(stack)
    window.add_plane(0, frame)
    assert time.perf_counter() - began < 1.0, "handing a frame over returns at once"
    assert _until(qt, lambda: library.shown) == ["run"]
    assert _until(qt, lambda: landed(view, "live/")), "the first plane was announced"
    held = library.dataset("run").previews[0]
    assert held.preview.shape == (16, 512, 512), "thinned out before it was handed on"
    assert offered(view)["run"]["live"] is True and offered(view)["run"]["note"] == "Tile 1 of 1 · 488"
    for plane in range(1, 16):
        _spin(qt, 0.3)  # frames closer together than the preview takes them are passed over
        window.add_plane(plane, frame)
    assert _until(qt, lambda: held.preview.top, lambda top: top == 15) == 15
    assert follow(view)["z"] == pytest.approx(75.0)
    window.end_stack()
    assert _until(qt, lambda: library.dataset("run").running is None)
    shown = _page_until(qt, window.web, lambda s: s["groups"] == ["run"])
    assert shown["listed"] == [["run", True]] and shown["empty"] is None
    window.end_run()
    assert _until(qt, lambda: offered(view)["run"]["live"] is False, timeout_s=10)


@pytest.mark.qt
def test_closing_the_window_stops_its_viewer(tmp_path, qt_app):
    app, qt = qt_app
    from mesoSPIM.src.mesospim_viewer.window import make_window_class

    from .tools import get

    a_run(tmp_path, "run_a")
    window = make_window_class()(tmp_path)
    window.show()
    url = window.viewer.url
    assert _until(qt, lambda: window.library.shown) == ["run_a"]
    assert get(url + "api/state")[0] == 200
    window.close()
    assert not window.timer.isActive()
    with pytest.raises(OSError):
        get(url + "api/state")
