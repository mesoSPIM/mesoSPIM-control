Data viewer
===========

**View → Open Data Viewer** opens a separate window that shows the acquisition
being written, as it is written: every tile and every time point is on screen
within a second of landing on disk. It follows the newest acquisition in the
folder the acquisition list saves into, and a dropdown at the top of its panel
switches to an earlier acquisition of the session (pick the one marked
*current* to follow the newest again).

The window is a neuroglancer page driven from Python, from the separate
`mesospim_view <https://github.com/thomdehoog/ZMART-viewer/tree/main/mesospim_view>`_
package. It reads the layout the ``MP_OME_Zarr_TCZYX_Writer`` produces: one
``.ome.zarr`` group per acquisition holding one ``(t, c, z, y, x)`` store per
tile (see :doc:`file_formats`). Stores from the other writers are not shown.

What is on screen
-----------------

* **2D / 3D** switch, top left of the picture. 3D draws a maximum projection;
  the mouse turns it.
* **Depth (Z) slider** upright at the right edge and **time (T) slider** along
  the bottom, each only when the axis has more than one step.
* **Panel** on the right, foldable: the acquisition dropdown; in 3D a card
  with the projection (max, accumulate, min), the detail (ray steps), the gain,
  where to look from and whether to draw the slice planes; and one row per
  channel with an eye, a colour swatch and the window control with its
  histogram and auto-range buttons (Min-Max, 1-99%, 5-95%).

Installing
----------

In the mesoSPIM Python environment:

.. code-block:: bash

   pip install "git+https://github.com/thomdehoog/ZMART-viewer"
   pip install PyQtWebEngine

The first brings the package with its page built in (no Node needed); the
second is the web view for PyQt5, which PyQt5 itself does not include.
mesoSPIM imports it at start-up when present, so restart mesoSPIM after
installing. Without either, the menu entry shows a message saying what is
missing and nothing else changes.

Testing it
----------

Before the first real acquisition, from a Python prompt in that environment:

.. code-block:: python

   import mesospim_view, PyQt5.QtWebEngineWidgets   # both must import
   mesospim_view.Viewer().page_built                # must be True

Then, without the microscope, a pretend run in the Data viewer window:

.. code-block:: bash

   python -m mesospim_view.demo --live --window

It writes four two-channel tiles and then appends time points to them, one
stack every two seconds. What to look for:

1. The window opens with the panel on the right and a black picture; the
   first tile appears within a couple of seconds of ``wrote run_00 tile 0``
   in the console, the others follow, placed beside one another.
2. The T slider appears at the bottom once the second time point lands, and
   its range grows to 3.
3. Changing a window with its slider, or hiding a channel with its eye, stays
   as it is when the next tile lands.
4. 3D shows the tiles as a volume; **Top / Front / Side** turn it.
5. A second run of the same command starts ``run_01`` in the same folder: the
   window switches to it on its own, and the dropdown lists ``run_00`` too.

Then with the microscope: select ``MP_OME_Zarr_TCZYX_Writer`` in the
file-naming wizard, open the Data viewer, and run a short acquisition list of
two tiles and two lasers. Each tile should appear as it finishes, with both
channels in one row group; a time lapse of a few time points should extend the
T slider without any tile being redrawn from scratch.

If something is wrong
---------------------

* **The window stays black** while the console shows tiles being written:
  usually WebGL in the Qt web view. Set
  ``QTWEBENGINE_CHROMIUM_FLAGS=--ignore-gpu-blocklist`` in the environment
  before starting, and try ``--disable-gpu-driver-bug-workarounds`` after
  that. ``python -m mesospim_view.demo --live`` (without ``--window``) shows
  the same run in the system browser: if the browser draws and Qt does not,
  it is Qt's GPU path and not the viewer.
* **The menu entry says the package is missing** although it is installed:
  it was installed into a different Python environment than the one mesoSPIM
  runs in. ``python -c "import mesospim_view; print(mesospim_view.__file__)"``
  from the mesoSPIM environment tells.
* **"QtWebEngineWidgets must be imported before a QCoreApplication instance is
  created"**: PyQtWebEngine was installed after mesoSPIM was started, or the
  ``mesoSPIM_DataViewer.prepare_qt()`` call at the top of ``mesoSPIM_Control.py``
  was removed. Restart mesoSPIM.
* **Nothing appears for an acquisition** written with another writer: only
  the tczyx layout is read. Check the acquisition folder holds
  ``<Sample>.ome.zarr/Mag…_Tile…_Sh…_Rot….ome.zarr`` stores.
* **The data viewer's own tests** live in the ZMART-viewer repository:
  ``python -m pytest tests/mesospim``
  there, with a Chromium for the picture tests.
