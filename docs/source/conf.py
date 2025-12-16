# -*- coding: utf-8 -*-
import os
import sys
import importlib
import types
import ctypes
import platform

# --- Path setup -------------------------------------------------------------

DOCS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(DOCS_DIR, "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

# --- Project information -----------------------------------------------------

project = "mesoSPIM Control"
author = "mesoSPIM team"
copyright = "mesoSPIM team"
version = ""
release = "1.11.1"

# --- Docs-only hacks ---------------------------------------------------------
# 1) Fake GetCurrentProcessorNumber on non-Windows platforms to avoid crashes in psutil
if not hasattr(ctypes, "windll") or platform.system() != "Windows":
    dummy_kernel32 = types.SimpleNamespace(
        GetCurrentProcessorNumber=lambda: 0
    )
    ctypes.windll = types.SimpleNamespace(kernel32=dummy_kernel32)


# 2) Fake ZWO EFW bindings module so mesoSPIM_Control import doesn't crash
MODULE_NAME = "mesoSPIM.src.devices.filter_wheels.ZWO_EFW.pyzwoefw"
try:
    importlib.import_module(MODULE_NAME)
except Exception:
    # Create a simple dummy module and insert it into sys.modules
    dummy_efw = types.ModuleType(MODULE_NAME)
    # Provide minimal attributes that your code might touch
    # For now we just define a no-op function placeholder
    def _dummy_init():
        return 0
    dummy_efw.EFWInit = _dummy_init
    dummy_efw.EFWClose = lambda *args, **kwargs: None
    sys.modules[MODULE_NAME] = dummy_efw

# 3) Patch Dynamixel dxl_x64_c.dll load so it doesn't crash on Linux in docs build
try:
    # Try importing the real module; on Linux this will usually fail with invalid ELF header
    import mesoSPIM.src.devices.servos.dynamixel.dynamixel_functions as _dxl_funcs  # noqa: F401
except Exception:
    # Emulate what dynamixel_functions expects, but without loading the DLL
    try:
        dxl_mod_name = "mesoSPIM.src.devices.servos.dynamixel.dynamixel_functions"
        dxl_mod = importlib.import_module(dxl_mod_name)
    except Exception:
        dxl_mod = types.ModuleType(dxl_mod_name)
        sys.modules[dxl_mod_name] = dxl_mod
    # Provide a fake dxl_lib object with dummy methods
    class _DummyDxlLib:
        def __getattr__(self, name):
            # Any DLL function call becomes a no-op that returns 0
            def _dummy(*args, **kwargs):
                return 0
            return _dummy
    dxl_mod.dxl_lib = _DummyDxlLib()

# --- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.napoleon",
    "myst_parser",
]

autodoc_mock_imports = [
    "scipy",
    "PyQt5",
    "PyQt5_sip",
    "nidaqmx",
    "indexed",
    "pipython",
    "serial",       # this is the package name for pyserial
    "pyqtgraph",
    "pywinusb",
    "tifffile",
    "qdarkstyle",
    "npy2bdv",
    "future",
    "matplotlib",
    "psutil",
    "distutils",
]


# Optional but useful
myst_enable_extensions = [
    "colon_fence",
]

templates_path = ["_templates"]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
master_doc = "index"
language = "en"
exclude_patterns = []
pygments_style = "sphinx"

# --- HTML output -------------------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
htmlhelp_basename = "mesoSPIMControldoc"

# --- Extension settings ------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

todo_include_todos = True
