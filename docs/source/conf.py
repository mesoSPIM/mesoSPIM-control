# -*- coding: utf-8 -*-
import os
import sys
import importlib
import types
import ctypes

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
# 1) Fake ctypes.windll on non-Windows so utility_functions.GetCurrentProcessorNumber doesn't crash
if not hasattr(ctypes, "windll") or platform.system() != "Windows":
    # Minimal dummy with a kernel32.GetCurrentProcessorNumber function
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
    "numpy",
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

html_theme = "sphinx_rtd_theme"   # optional but recommended
html_static_path = ["_static"]
htmlhelp_basename = "mesoSPIMControldoc"

# --- Extension settings ------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

todo_include_todos = True
