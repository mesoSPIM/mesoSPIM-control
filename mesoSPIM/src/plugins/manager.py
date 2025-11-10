# mesospim/plugins/manager.py
"""
Manage MesoSPIM plugins through automatic import, validation and registration
"""
from __future__ import annotations
import importlib.util, sys, types, traceback, os
import logging
logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Dict, Type, Iterable
from .ImageWriterApi import ImageWriter, API_VERSION

# Default DIRS for builtin image writers
DEFAULT_DIRS: list[Path] = [
    Path.cwd() / "src/plugins/ImageWriters",
]

MESOSPIM_PLUGIN_MODULE_PREFIX = 'mesospim_plugin'

class PluginRegistry:
    def __init__(self, cfg) -> None:
        # self.parent = parent # mesoSPIM_MainWindow instance
        self.cfg = cfg

        # Register paths where plugins are stored
        self.plugins_dirs = DEFAULT_DIRS
        if hasattr(self.cfg, "plugins"):
            # Add paths defined in the mesospim config
            self.plugins_dirs += [Path(x) for x in self.cfg.plugins["paths_list"]]

        self._writers: Dict[str, Type[ImageWriter]] = {}
        self.load_from_dirs()

    def register(self, cls: Type[ImageWriter]) -> None:
        if not isinstance(cls, type):
            return
        if not hasattr(cls, "api_version") or not hasattr(cls, "name"):
            return
        if cls.api_version().split(".")[0] != API_VERSION.split(".")[0]:
            return
        self._writers[cls.name()] = cls

    def load_from_dirs(self) -> None:
        for d in self.plugins_dirs:
            if d.exists():
                for path in list(d.glob("*.py")) + [p for p in d.iterdir() if p.is_dir() and (p / "__init__.py").exists()]:
                    if "__init__.py" in str(path): continue # Skip imports of __init__.py
                    try:
                        mod = _import_path(path)
                        # Two ways to register:
                        # 1) explicit hook
                        hook = getattr(mod, "register_mesospim_plugins", None)
                        if callable(hook):
                            hook(self)
                        # 2) auto-scan for classes that look like Writers
                        for obj in mod.__dict__.values():
                            self.register(obj)  # harmless if not a Writer
                        logger.info(f'Loaded plugin module: {path}')
                    except Exception:
                        logger.error(f'Failed to load plugin module: {d}')
                        traceback.print_exc()
            else:
                logger.info(f'Plugin Path does not exist: {d}')

def _import_path(path: Path) -> types.ModuleType:
    '''Import all modules in the paths'''
    modname = f"{MESOSPIM_PLUGIN_MODULE_PREFIX}_{path.stem}" # module name prefixed with mesospim_plugin_
    spec = importlib.util.spec_from_file_location(
        modname, path if path.suffix == ".py" else (path / "__init__.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod
