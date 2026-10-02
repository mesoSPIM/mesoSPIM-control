Data viewer
===========

The Data viewer comes in two forms, both in the **View** menu.

**View → Open Live Data Viewer** opens a separate window that shows the
acquisition being written, as it is written: every tile and every time point is
on screen within a second of landing on disk. It follows the newest acquisition
in the folder the acquisition list saves into, and a dropdown at the top of its
panel switches to an earlier acquisition of the session (pick the one marked
*current* to follow the newest again).

**View → Open Acquired Dataset...** asks for a dataset that is already on disk
and shows it as it is, in a window of its own. Nothing is followed: if more
data arrives in that folder later, this window does not change. You can pick:

* one acquisition, the ``<Sample>.ome.zarr`` folder holding its tiles, to see
  all the tiles together;
* one tile, a ``Mag…_Tile…_Sh…_Rot….ome.zarr`` store, to see it on its own;
* a data folder holding several acquisitions, to see the newest, with the
  dropdown to switch between them.

Several acquired datasets can be open at once, each in its own window. The
window title always says which form a window is: *Live data viewer* or
*Acquired dataset*.

The window is a neuroglancer page driven from Python, the ``mesospim_viewer``
package in ``mesoSPIM/src/mesospim_viewer/``.

Which data it can show
----------------------

The **live data viewer** reads the layout the ``MP_OME_Zarr_TCZYX_Writer``
produces: one ``.ome.zarr`` group per acquisition holding one
``(t, c, z, y, x)`` store per tile (see :doc:`file_formats`).

An **acquired dataset** can be any OME-Zarr image in version 0.4 or 0.5, with
the axes ``t, c, z, y, x`` or some of them in that order, as long as ``z, y, x``
are there. So ``(z, y, x)``, ``(c, z, y, x)`` and ``(t, z, y, x)`` open too. An
axis that is missing simply counts as one step long. OME-Zarr 0.6 is not read
yet; the viewer says so if you pick one.

When a dataset holds one store per tile *and* per channel, the viewer needs to
know which channel each store holds. It reads this from the ``omero`` block
inside the store, never from the file name. Stores without that information
cannot be told apart, so their channels are then shown on top of each other as
one channel.

.. note::

   **For a quick viewer, keep one store per position.** What makes the viewer
   slow is the number of stores, not which axes they have, because every store
   is set up on its own when it is shown. One store per position, with all its
   channels and time points inside it (``t, c, z, y, x``), stays quick even with
   hundreds of positions. A dataset split into one store per channel or per time
   point opens too, but takes longer the more stores it has.

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

Nothing extra is needed. The viewer comes with mesoSPIM-control, its page
already built (no Node needed), and the web view for PyQt5 that it draws in,
PyQtWebEngine, is installed together with mesoSPIM-control, both by
``pip install -e .`` and by ``pip install -r requirements-conda-mamba.txt``.

An environment set up before the viewer existed does not have it yet. In
that case, install it into the mesoSPIM Python environment and restart
mesoSPIM, because mesoSPIM loads the web view only at start-up:

.. code-block:: bash

   pip install PyQtWebEngine==5.15.7

If it is missing, the menu entry shows a message saying so, and nothing else
changes.

Testing it
----------

Before the first real acquisition, from a Python prompt in that environment:

.. code-block:: python

   from mesoSPIM.src import mesospim_viewer; import PyQt5.QtWebEngineWidgets   # both must import
   mesospim_viewer.Viewer().page_built                                         # must be True

Then, without the microscope, a pretend run in the Data viewer window:

.. code-block:: bash

   python -m mesoSPIM.src.mesospim_viewer.demo --live --window

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
  that. ``python -m mesoSPIM.src.mesospim_viewer.demo --live`` (without ``--window``) shows
  the same run in the system browser: if the browser draws and Qt does not,
  it is Qt's GPU path and not the viewer.
* **The menu entry says PyQtWebEngine is missing** although it is installed:
  it was installed into a different Python environment than the one mesoSPIM
  runs in. ``python -c "import PyQt5.QtWebEngineWidgets"`` from the mesoSPIM
  environment tells.
* **"QtWebEngineWidgets must be imported before a QCoreApplication instance is
  created"**: PyQtWebEngine was installed after mesoSPIM was started, or the
  ``mesoSPIM_DataViewer.prepare_qt()`` call at the top of ``mesoSPIM_Control.py``
  was removed. Restart mesoSPIM.
* **Nothing appears in the live data viewer** for an acquisition written with
  another writer: the live viewer reads only the tczyx layout. Check the
  acquisition folder holds ``<Sample>.ome.zarr/Mag…_Tile…_Sh…_Rot….ome.zarr``
  stores, or open the data with **Open Acquired Dataset...** instead.
* **All channels look the same in an acquired dataset**: the dataset holds one
  store per channel, and the stores do not say which channel they hold (they
  have no ``omero`` block). The viewer then cannot tell them apart.
* **The data viewer's own tests**: ``python -m pytest mesoSPIM/test/mesospim_viewer``,
  with Playwright and a Chromium for the picture tests (they skip, saying so,
  without them). Changing the page itself needs Node: see
  ``mesoSPIM/src/mesospim_viewer/README.md``.
