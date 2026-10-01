"""Fixtures for the mesoSPIM viewer tests.

``browser`` is one headless Chromium for the session, through Playwright;
``pages`` opens the built page in it and waits for a picture. The tile
fixtures are pretend mesoSPIM tiles written with numpy alone.

The picture tests skip, saying why, when Playwright or a Chromium is missing:
``pip install playwright`` and ``playwright install chromium``, or name a
Chromium already on the machine in ``MESOSPIM_VIEWER_CHROMIUM``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from mesoSPIM.src.mesospim_viewer import PAGE_DIR
from mesoSPIM.src.mesospim_viewer.demo import write_tile, write_tiles


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


class Pages:
    """The built page, opened in the session's browser."""

    def __init__(self, browser) -> None:
        self.browser = browser
        self.opened = []

    def open(self, url: str, *, width: int = 900, height: int = 700):
        """The page at ``url`` and the list its script errors are collected in."""
        page = self.browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        self.opened.append(page)
        return page, errors

    @staticmethod
    def describe(page) -> dict | None:
        return page.evaluate(DESCRIBE)

    def drawn(self, page, *, layers: int, timeout_s: float = 40.0) -> dict:
        """Wait until ``layers`` engine layers have loaded and every visible chunk is in."""
        deadline = time.time() + timeout_s
        seen = None
        while time.time() < deadline:
            seen = self.describe(page)
            if (
                seen
                and len(seen["layers"]) == layers
                and all(layer["loaded"] for layer in seen["layers"])
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
        pytest.skip("the mesoSPIM page is not built: npm ci && npm run build in mesoSPIM/src/mesospim_viewer/page_source")
    held = Pages(browser)
    yield held
    held.close()
