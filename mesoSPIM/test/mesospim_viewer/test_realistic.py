"""A run written by the microscope's own writer, watched in the page as it lands.

Everything real but the specimen: the stacks go through ``Live3DPyramidWriterTCZYX``
as the ``MP_OME_Zarr_TCZYX_Writer`` plugin drives it (zarr v3, zstd, slabs of 64
planes, a pyramid behind them; see ``realistic.py``), a :class:`Library` watches
the folder once a second as the window's timer does, and the built page shows it
in a headless Chromium. Once from disk alone, and once with the camera's frames
fed in as mesoSPIM-control feeds them.

Small frames and two tiles, so the whole run takes about half a minute; the
picture is sampled a few times a second meanwhile.
"""

from __future__ import annotations

import threading
import time

import pytest

from mesoSPIM.src.mesospim_viewer import Library

from . import realistic
from .conftest import PICTURE, WHERE
from .tools import landed

TILES, CHANNELS, PLANES, SIZE, FPS = 2, ("488", "561"), 128, 256, 24.0
A_FEW_SECONDS = 8.0

SOURCES = "() => window.viewer.layerManager.managedLayers.map(m => m.layer.dataSources.length)"
LIVE = "() => ({ following: window.mesospim.following.value, acquiring: window.mesospim.acquiring.value })"


def _previews(view) -> list[str]:
    return sorted({name for layer in view.scene["layers"] for name in layer["_sources"] if name.startswith("live-")})


@pytest.mark.parametrize("mode", ["disk", "feed"])
def test_a_run_by_the_real_writer_is_followed_as_it_lands(pages, viewers, tmp_path, mode):
    unavailable = realistic.writer_available()
    if unavailable:
        pytest.skip(unavailable)
    view = viewers(ui="simple")
    library = Library(view)
    library.watch(tmp_path)
    page, errors = pages.open(view.start(), width=1100, height=700)
    mishaps: list[str] = []
    over = threading.Event()

    def look_once_a_second() -> None:  # the window's timer
        while not over.is_set():
            try:
                library.poll()
            except Exception as mishap:  # noqa: BLE001 -- told to the test below
                mishaps.append(f"poll: {mishap!r}")
            over.wait(1.0)

    first_frame: list[float] = []

    def camera(what: str, *said) -> None:  # mesoSPIM_DataViewer.Feed, without Qt
        try:
            if what == "begin":
                library.begin_stack(said[0])
            elif what == "plane":
                first_frame.append(time.time()) if not first_frame else None
                library.add_plane(*said)
            elif what == "end":
                library.end_stack()
            elif what == "finished":
                library.end_run()
        except Exception as mishap:  # noqa: BLE001
            mishaps.append(f"{what}: {mishap!r}")

    def acquire() -> None:
        try:
            realistic.acquire(
                tmp_path, tiles=TILES, channels=CHANNELS, planes=PLANES, size=SIZE, fps=FPS,
                camera=camera if mode == "feed" else None,
            )
        except Exception as mishap:  # noqa: BLE001
            mishaps.append(f"writer: {mishap!r}")

    threading.Thread(target=look_once_a_second, daemon=True).start()
    writer = threading.Thread(target=acquire, daemon=True)
    began = time.time()
    writer.start()

    # While it runs: when the first data existed, when the picture lit up, where the view was.
    first_slab = tmp_path / "run.ome.zarr" / "Mag1_Tile0_Sh0_Rot0.ome.zarr" / "0" / "c" / "0" / "0" / "0" / "0" / "0"
    first_data = lit_at = named_at = None
    planes, following, sources_seen = [], [], []
    try:
        while writer.is_alive() and time.time() - began < 180:
            now = time.time()
            if first_data is None:
                if mode == "feed" and first_frame:
                    first_data = first_frame[0]
                elif mode == "disk" and first_slab.exists():
                    first_data = now
            if named_at is None and landed(view, "data/" if mode == "disk" else "live/"):
                named_at = now
            if lit_at is None and page.evaluate(PICTURE)["lit"] > 3000:
                lit_at = now
            live = page.evaluate(LIVE)
            if live["acquiring"]:
                following.append(live["following"])
                planes.append(round(page.evaluate(WHERE)["voxels"].get("z", -1)))
            sources_seen.append(page.evaluate(SOURCES))
            time.sleep(0.3)
        assert not writer.is_alive(), "the writer did not finish"
        acquired = time.time()

        # Afterwards: every tile from disk, and nothing from memory any more.
        def settled() -> bool:
            return page.evaluate(SOURCES) == [TILES] * len(CHANNELS) and not _previews(view)

        deadline = time.time() + 60
        while not settled() and time.time() < deadline:
            if lit_at is None and page.evaluate(PICTURE)["lit"] > 3000:
                lit_at = time.time()
            time.sleep(0.5)
        assert settled(), f"sources {page.evaluate(SOURCES)}, previews left {_previews(view)}"
        pages.drawn(page, layers=len(CHANNELS), sources=TILES, timeout_s=60)
    finally:
        over.set()

    assert not mishaps, mishaps
    assert not errors, errors
    assert first_data is not None

    # The layers the page made when the run appeared are the ones it still has.
    assert pages.layer_objects(page)["made"] == len(CHANNELS), "a layer was rebuilt during the run"
    assert all(count <= TILES + 1 for seen in sources_seen for count in seen), "at most one preview beside the tiles"

    # The view followed the acquisition.
    assert following and all(following), "the view stopped following on its own"
    if mode == "feed":
        # The preview takes a few frames a second: the last one it took is near the end.
        assert max(planes) >= PLANES * 0.8, f"the view never reached the newest planes: {sorted(set(planes))}"
        assert len(set(planes)) >= 8, f"plane by plane, as the camera delivered them: {sorted(set(planes))}"
    else:
        assert max(planes) == PLANES - 1, f"the view never reached the newest slab: {sorted(set(planes))}"

    # In the end the tiles are drawn from disk.
    for layer in view.scene["layers"]:
        assert layer["_sources"] == ["store-0", "store-1"] and layer["_retiring"] == []
    assert all(not dataset.previews for dataset in library.datasets), "a preview's memory was not let go"
    read = pages.chunks_read(page)
    assert any(path.startswith("data/0/") for path in read) and any(path.startswith("data/1/") for path in read)
    assert library.names == ["run"] and library.shown == ["run"]
    assert view._server.scene.acquisitions[0]["tiles"] == TILES

    # And the operator saw something almost at once.
    what = "the first plane was delivered" if mode == "feed" else "the first slab was on disk"
    late = []
    if named_at is None or named_at - first_data > A_FEW_SECONDS:
        after = "never" if named_at is None else f"{named_at - first_data:.1f} s"
        late.append(f"the page was told of the first data {after} after {what}")
    if lit_at is None or lit_at - first_data > A_FEW_SECONDS:
        after = "never" if lit_at is None else f"{lit_at - first_data:.1f} s"
        late.append(f"the picture lit up {after} after {what}")
    if page.evaluate(PICTURE)["lit"] <= 3000:
        late.append("the picture is black at the end, with every tile drawn")
    assert not late, f"{late} (the run took {acquired - began:.0f} s)"
