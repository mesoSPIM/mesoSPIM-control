"""Fixtures for the mesoSPIM viewer tests.

``viewers`` makes viewers and stops them; ``library`` is a :class:`Library` on a
clock the test moves. ``browser`` is one headless Chromium for the session,
through Playwright; ``pages`` opens the built page in it, waits for a picture
and counts what the page asks the server for. The tile fixtures are pretend
mesoSPIM tiles written with numpy alone.

The picture tests skip, saying why, when Playwright or a Chromium is missing:
``pip install playwright`` and ``playwright install chromium``, or name a
Chromium already on the machine in ``MESOSPIM_VIEWER_CHROMIUM``.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from mesoSPIM.src.mesospim_viewer import PAGE_DIR, Library, Viewer
from mesoSPIM.src.mesospim_viewer.demo import write_tile, write_tiles

from .tools import Clock


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers", "qt: drives the Data viewer window in Qt; runs only with MESOSPIM_VIEWER_QT_TESTS=1"
    )


@pytest.fixture(scope="session")
def tiles(tmp_path_factory) -> list[Path]:
    """Four two-channel tiles in a two-by-two grid, one time point each."""
    return write_tiles(tmp_path_factory.mktemp("tiles"))


@pytest.fixture(scope="session")
def stacks(tmp_path_factory) -> list[Path]:
    """Two tiles side by side with three time points each, for the sliders."""
    folder = tmp_path_factory.mktemp("stacks")
    return [
        write_tile(folder / f"tile_{i}.ome.zarr", origin_um=(0, 0, i * 144), seed=i, timepoints=3)
        for i in range(2)
    ]


@pytest.fixture
def viewers():
    """Makes viewers, and stops each of them when the test is over."""
    made: list[Viewer] = []

    def make(**options) -> Viewer:
        made.append(Viewer(**options))
        return made[-1]

    yield make
    # Stopping waits for the server's loop to come round (half a second): done
    # aside, so a hundred tests do not wait a minute for it.
    for view in made:
        threading.Thread(target=view.stop, daemon=True).start()


@pytest.fixture
def library(viewers) -> Library:
    """A library over a viewer of its own, going by a clock the test moves
    (``library.clock.tick()``); nothing in it waits for real time to pass."""
    return Library(viewers(), clock=Clock())


# What the engine holds: every layer's sources and errors, and how many of the
# chunks the picture needs have arrived.
DESCRIBE = """() => {
  const v = window.viewer; if (!v?.layerManager) return null;
  let needed = 0, available = 0;
  const layers = v.layerManager.managedLayers.map((m) => {
    for (const rl of m.layer?.renderLayers ?? []) {
      const p = rl.layerChunkProgressInfo;
      if (p) { needed += p.numVisibleChunksNeeded; available += p.numVisibleChunksAvailable; }
    }
    return {
      name: m.name,
      loaded: (m.layer?.dataSources ?? []).every((s) => s.loadState !== undefined),
      errors: (m.layer?.dataSources ?? []).map((s) => s.loadState?.error?.message).filter(Boolean),
      channelRank: m.layer?.channelCoordinateSpace?.value?.rank ?? null,
      sources: (m.layer?.dataSources ?? []).length,
    };
  });
  const space = v.navigationState.position.coordinateSpace.value;
  return { layers, needed, available, names: Array.from(space?.names ?? []),
           shown: Array.from(v.navigationState.pose.displayDimensionRenderInfo.value.displayDimensionIndices) };
}"""

# Every engine layer object the page has ever made is given a number, the first
# time it is seen: when the list of layers changes, and when a test asks. A layer
# that was rebuilt is a new object and so a new number.
WATCH_LAYERS = """() => {
  if (window.__layers) return;
  const known = new Map();
  const look = () => window.viewer.layerManager.managedLayers.map((m) => {
    if (m.layer && !known.has(m.layer)) known.set(m.layer, known.size);
    return [m.name, known.get(m.layer)];
  });
  window.__layers = { look, made: () => known.size };
  window.viewer.layerManager.layersChanged.add(look);
  look();
}"""

LAYER_OBJECTS = "() => ({ now: Object.fromEntries(window.__layers.look()), made: window.__layers.made() })"

# Where the view is, by axis name: in voxels of the picture's space, and in micrometres.
WHERE = """() => {
  const n = window.viewer.navigationState, space = n.position.coordinateSpace.value;
  const voxels = {}, um = {};
  Array.from(space?.names ?? []).forEach((name, i) => {
    voxels[name] = n.position.value[i];
    um[name] = n.position.value[i] * space.scales[i] * (space.units[i] === 'm' ? 1e6 : 1);
  });
  return { voxels, um, zoom: n.zoomFactor.value };
}"""

# Each layer's contrast as the engine holds it now, and whether the page sets it itself.
CONTRAST = """() => Object.fromEntries(window.viewer.layerManager.managedLayers.map((m) => {
  const value = m.layer.shaderControlState.state.get('contrast')?.trackable.value;
  return [m.name, { auto: window.mesospim.isAuto(m.name),
                    range: value ? Array.from(value.range, Number) : null,
                    window: value ? Array.from(value.window, Number) : null }];
}))"""

# The picture itself -- the part of the canvas the image is drawn in, without the
# panel beside it -- as counts of its pixels: `lit` are plainly brighter than
# black, `clear` are see-through.
PICTURE = """() => {
  const display = window.viewer.display; display.draw();
  const gl = display.gl, canvas = display.canvas;
  const panel = document.querySelector('.neuroglancer-rendered-data-panel');
  if (!panel) return { pixels: 0, lit: 0, clear: 0 };
  const box = panel.getBoundingClientRect(), whole = canvas.getBoundingClientRect();
  const sx = canvas.width / whole.width, sy = canvas.height / whole.height;
  const x = Math.round((box.left - whole.left) * sx), w = Math.round(box.width * sx);
  const h = Math.round(box.height * sy), y = canvas.height - Math.round((box.top - whole.top) * sy) - h;
  const pixels = new Uint8Array(w * h * 4);
  gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  let lit = 0, clear = 0;
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i + 3] === 0) clear++;
    else if (Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) > 48) lit++;
  }
  return { pixels: w * h, lit, clear };
}"""


METADATA = ("zarr.json", ".zarray", ".zattrs", ".zgroup", ".zmetadata")


class Pages:
    """The built page, opened in the session's browser."""

    def __init__(self, browser) -> None:
        self.browser = browser
        self.opened = []
        self._asked: dict[object, list[str]] = {}
        self._answered: dict[object, list[tuple[str, int]]] = {}

    def open(self, url: str, *, width: int = 900, height: int = 700):
        """The page at ``url`` and the list its script errors are collected in.

        Returns once the page has built its viewer."""
        page = self.browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        asked = self._asked[page] = []

        def note(request) -> None:
            path = urlsplit(request.url).path
            if path.startswith(("/data/", "/live/")):
                asked.append(path.lstrip("/"))

        answered = self._answered[page] = []

        def answer(response) -> None:
            path = urlsplit(response.url).path
            if path.startswith(("/data/", "/live/")):
                answered.append((path.lstrip("/"), response.status))

        page.on("request", note)
        page.on("response", answer)
        page.goto(url)
        self.opened.append(page)
        page.wait_for_function("() => window.viewer?.layerManager && window.mesospim", timeout=30_000)
        page.evaluate(WATCH_LAYERS)
        return page, errors

    @staticmethod
    def _hear(page) -> None:
        # Playwright hands over what the page did only while it is being talked to.
        if not page.is_closed():
            page.evaluate("() => 0")

    def asked(self, page) -> list[str]:
        """Every file of a store or a preview the page has asked the server for, in
        order, as its path below the server: ``data/0/0/0.0.5.0.0``. The server has
        the page check each file again, so nothing is answered from a cache unseen."""
        self._hear(page)
        return self._asked[page]

    def chunks_asked(self, page, since: int = 0) -> list[str]:
        """Of those, the chunk files: not the descriptions of groups and arrays."""
        return [path for path in self.asked(page)[since:] if not path.endswith(METADATA)]

    def chunks_read(self, page) -> set[str]:
        """The chunk files the page was given (rather than told there is none yet)."""
        self._hear(page)
        return {
            path for path, status in self._answered[page] if status in (200, 206) and not path.endswith(METADATA)
        }

    @staticmethod
    def describe(page) -> dict | None:
        return page.evaluate(DESCRIBE)

    @staticmethod
    def layer_objects(page) -> dict:
        """``now``: the number of the engine layer object behind each layer's name;
        ``made``: how many such objects the page has made since it opened."""
        return page.evaluate(LAYER_OBJECTS)

    def drawn(self, page, *, layers: int, sources: int | None = None, timeout_s: float = 40.0) -> dict:
        """Wait until ``layers`` engine layers have loaded (each with ``sources``
        sources, when given) and every visible chunk is in."""
        deadline = time.time() + timeout_s
        seen = None
        while time.time() < deadline:
            seen = self.describe(page)
            if (
                seen
                and len(seen["layers"]) == layers
                and all(layer["loaded"] for layer in seen["layers"])
                and (sources is None or all(layer["sources"] == sources for layer in seen["layers"]))
                and seen["needed"] > 0
                and seen["available"] == seen["needed"]
            ):
                return seen
            time.sleep(0.25)
        raise AssertionError(f"the picture never settled: {seen}")

    def close(self) -> None:
        for page in self.opened:
            if not page.is_closed():
                page.close()


# Drawn on the graphics card where there is one, in software where there is not.
_ON_THE_CARD = ["--ignore-gpu-blocklist", "--enable-gpu"]
_IN_SOFTWARE = ["--use-gl=angle", "--use-angle=swiftshader", "--ignore-gpu-blocklist"]


@pytest.fixture(scope="session")
def browser():
    """One headless Chromium for the session, or a skip that says why not."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("Playwright is not installed: pip install playwright && playwright install chromium")
    named = os.environ.get("MESOSPIM_VIEWER_CHROMIUM", "").strip() or None
    try:
        manager = sync_playwright().start()
    except Exception as why:  # noqa: BLE001 -- Playwright's own driver is missing
        pytest.skip(f"Playwright could not start ({str(why).splitlines()[0]})")
    playwright = manager
    try:
        launched = None
        for args in (_ON_THE_CARD, _IN_SOFTWARE):
            try:
                launched = playwright.chromium.launch(executable_path=named, args=args)
                break
            except Exception as why:  # noqa: BLE001 -- the next way, then a skip
                reason = str(why).splitlines()[0]
        if launched is None:
            pytest.skip(f"no Chromium could be started ({reason}); set MESOSPIM_VIEWER_CHROMIUM")
        yield launched
        launched.close()
    finally:
        manager.stop()


@pytest.fixture
def pages(browser) -> Pages:
    if not (PAGE_DIR / "index.html").is_file():
        pytest.skip("the mesoSPIM page is not built: npm ci && npm run build in mesoSPIM/src/mesospim_viewer/source")
    held = Pages(browser)
    yield held
    held.close()
