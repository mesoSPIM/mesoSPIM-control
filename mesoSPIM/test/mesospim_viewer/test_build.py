"""The built page: what is committed is what the build makes, every time.

The page in ``mesospim_viewer/page`` is built from ``page_source`` and committed,
so a mesoSPIM installation needs no Node.js. That only holds if building the
same sources twice gives the same files, and if building leaves the installed
engine (``node_modules``) exactly as npm put it there: otherwise a second build,
or a build on another machine, quietly makes a different page.

The first test reads only the committed page and always runs. The second builds
the page twice and needs Node.js and ``npm ci`` in ``page_source``; it skips,
saying so, without them.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mesoSPIM.src.mesospim_viewer import PAGE_DIR

SOURCE_DIR = PAGE_DIR.parent / "page_source"
ENGINE_LIB = SOURCE_DIR / "node_modules" / "neuroglancer" / "lib"

# esbuild names each module it bundles in a comment; the shims for the Qt window's
# old Chromium (src/legacy_browser.js) must come exactly once into each worker.
SHIMS = "// src/legacy_browser.js"


def _workers(page: Path) -> dict[str, Path]:
    found = {path.name: path for path in page.rglob("*.js") if "bundle" in path.name}
    return {
        "chunk": next(path for name, path in found.items() if name.startswith("chunk_worker")),
        "async": next(path for name, path in found.items() if name.startswith("async_computation")),
    }


def _digest(folder: Path) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def test_each_worker_of_the_committed_page_carries_the_old_browser_shims_once():
    for kind, path in _workers(PAGE_DIR).items():
        text = path.read_text(encoding="utf-8")
        assert text.count(SHIMS) == 1, f"{kind} worker {path.name}: shims {text.count(SHIMS)} times"
        # The uncompiled stub is a list of `import "#src/..."` lines a browser cannot resolve.
        assert 'import "#src/' not in text and len(text) > 500_000, (
            f"{kind} worker {path.name} is not a compiled bundle"
        )


def _npm() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


@pytest.mark.skipif(
    _npm() is None or not (SOURCE_DIR / "node_modules" / "vite").is_dir(),
    reason="needs Node.js and `npm ci` in mesoSPIM/src/mesospim_viewer/page_source",
)
def test_building_twice_gives_the_committed_page_and_leaves_the_engine_untouched(tmp_path):
    engine_before = _digest(ENGINE_LIB)
    built = []
    for attempt in ("first", "second"):
        out = tmp_path / attempt
        subprocess.run(
            f'"{_npm()}" run build -- --outDir "{out}" --emptyOutDir',
            cwd=SOURCE_DIR,
            shell=True,
            check=True,
            capture_output=True,
            env={**os.environ, "NO_COLOR": "1"},
        )
        built.append(_digest(out))
    assert _digest(ENGINE_LIB) == engine_before, "the build changed files in node_modules"
    assert built[0] == built[1], "two builds of the same sources differ"
    assert built[0] == _digest(PAGE_DIR), "the committed page is not what the build makes"
