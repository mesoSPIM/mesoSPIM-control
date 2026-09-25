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
from .ImageProcessorApi import ImageProcessor
from .FilterWheelApi import FilterWheelPlugin, API_VERSION as FILTER_WHEEL_API_VERSION

# Default directories for built-in plugins
PLUGINS_DIR = Path(__file__).resolve().parent
DEFAULT_DIRS: list[Path] = [
    PLUGINS_DIR / "ImageWriters",
    PLUGINS_DIR / "ImageProcessors",
    PLUGINS_DIR / "FilterWheels",
]

MESOSPIM_PLUGIN_MODULE_PREFIX = 'mesospim_plugin'
RESERVED_FILTER_WHEEL_NAMES = frozenset({'Demo', 'Dynamixel', 'Ludl', 'Sutter', 'ZWO'})
_active_registry = None

class PluginRegistry:
    def __init__(self, cfg) -> None:
        # self.parent = parent # mesoSPIM_MainWindow instance
        self.cfg = cfg

        # Register paths where plugins are stored
        self.plugins_dirs = list(DEFAULT_DIRS)
        if hasattr(self.cfg, "plugins"):
            # Add paths defined in the mesospim config
            paths = self.cfg.plugins.get('path_list', [])
            self.plugins_dirs += [Path(x) for x in paths]

        self._writers: Dict[str, Type[ImageWriter]] = {}
        self._processors: Dict[str, Type[ImageProcessor]] = {}
        self._filter_wheels: Dict[str, Type[FilterWheelPlugin]] = {}
        self.load_from_dirs()
        global _active_registry
        _active_registry = self

    def register(self, cls: Type[ImageWriter]) -> None:
        if not isinstance(cls, type):
            return
        if not hasattr(cls, "api_version") or not hasattr(cls, "name"):
            return
        if cls.api_version().split(".")[0] != API_VERSION.split(".")[0]:
            return
        self._writers[cls.name()] = cls

    def register_processor(self, cls: Type[ImageProcessor]) -> None:
        """Register an ImageProcessor plugin."""
        if not isinstance(cls, type):
            return
        if not hasattr(cls, "api_version") or not hasattr(cls, "name"):
            return
        if cls.api_version().split(".")[0] != API_VERSION.split(".")[0]:
            return
        self._processors[cls.name()] = cls

    def register_filter_wheel(self, cls: Type[FilterWheelPlugin]) -> bool:
        """Register a FilterWheelPlugin class."""
        if not isinstance(cls, type):
            return False
        if cls is FilterWheelPlugin:
            return False
        required_methods = (
            "api_version",
            "name",
            "description",
            "required_parameters",
            "create",
        )
        if not all(hasattr(cls, method) for method in required_methods):
            return False
        try:
            if not issubclass(cls, FilterWheelPlugin):
                return False
        except TypeError:
            return False
        try:
            compatible = (
                cls.api_version().split(".")[0]
                == FILTER_WHEEL_API_VERSION.split(".")[0]
            )
            name = cls.name()
            description = cls.description()
            required_parameters = cls.required_parameters()
        except (AttributeError, TypeError):
            return False
        valid_metadata = (
            compatible
            and isinstance(name, str)
            and bool(name)
            and isinstance(description, str)
            and isinstance(required_parameters, tuple)
            and all(isinstance(parameter, str) for parameter in required_parameters)
        )
        if not valid_metadata:
            return False
        if name in RESERVED_FILTER_WHEEL_NAMES:
            logger.error(
                f"Filter wheel plugin name {name!r} is reserved for a built-in driver"
            )
            return False
        existing = self._filter_wheels.get(name)
        if existing is not None:
            if existing is cls:
                return True
            logger.error(
                f"Filter wheel plugin name {name!r} is already registered by "
                f"{existing.__module__}.{existing.__name__}; ignoring "
                f"{cls.__module__}.{cls.__name__}"
            )
            return False
        self._filter_wheels[name] = cls
        return True

    @property
    def processors(self) -> Dict[str, Type[ImageProcessor]]:
        """Return registered processors."""
        return self._processors

    @property
    def filter_wheels(self) -> Dict[str, Type[FilterWheelPlugin]]:
        """Return registered filter-wheel plugin classes."""
        return self._filter_wheels

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
                        # 2) auto-scan for classes that match a plugin interface
                        for obj in mod.__dict__.values():
                            try:
                                is_filter_wheel_plugin = (
                                    isinstance(obj, type)
                                    and issubclass(obj, FilterWheelPlugin)
                                )
                            except TypeError:
                                is_filter_wheel_plugin = False
                            if is_filter_wheel_plugin:
                                self.register_filter_wheel(obj)
                                continue
                            self.register(obj)  # harmless if not a Writer
                            self.register_processor(obj)  # harmless if not a Processor
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


def get_registered_filter_wheel_plugins():
    """Return active registry entries, or None before registry initialization."""
    if _active_registry is None:
        return None
    return dict(_active_registry.filter_wheels)
