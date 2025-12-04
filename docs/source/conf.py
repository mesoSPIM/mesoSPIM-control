# -*- coding: utf-8 -*-
import os
import sys

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
    "ctypes",
    "distutils",
    "pyzwoefw",
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
