Data viewer
===========

The Data viewer is one window for looking at data: the acquisition that is
running, shown as the camera delivers it, and datasets that are already on
disk. It is in the **View** menu.

**View → Open Data Viewer** opens the window, or brings it to the front. It
watches the folder the acquisition list saves into. The newest acquisition in
that folder is shown, and when an acquisition starts it is shown in its place
and grows on screen plane by plane.

**View → Open Dataset in Data Viewer...** asks for a dataset that is already on
disk and shows it in the same window, beside whatever is there. The folder
button at the top of the window's panel does the same, and so does dropping a
folder from the file manager onto the window. You can pick:

* one acquisition, the ``<Sample>.ome.zarr`` folder holding its tiles, to see
  all the tiles together;
* one tile, a ``Mag…_Tile…_Sh…_Rot….ome.zarr`` store, to see it on its own;
* a data folder holding several acquisitions: every one is listed, and the
  newest is shown.

The window is a neuroglancer page driven from Python, the ``mesospim_viewer``
package in ``mesoSPIM/src/mesospim_viewer/``.

A running acquisition
---------------------

While the microscope acquires, the stack that is being acquired is drawn from
the camera's frames, the same frames the camera window shows. So the first
plane is on screen as soon as the camera has delivered it, and this works
whatever format the run is saved in. The picture of a running stack is a
thinned-out copy held in memory; once the stack is complete on disk, the tile
on disk takes its place. This needs an OME-Zarr writer: with another format the
thinned-out copy is all the viewer can show, and the run cannot be opened in
the viewer afterwards.

* The **Live** button at the top left is lit while the view follows the
  acquisition, which means it shows the newest plane. If you step through the
  planes or time points yourself, the view stays where you put it and the
  button reads **Back to live**; press it to follow again.
* The view zooms out to show every tile as tiles arrive, until you pan or zoom.
  After that a **Fit** button appears; press it to see everything again.
  Zooming into the tile that is being acquired does not stop the planes from
  coming.
* The contrast of each channel sets itself from what is on screen while the
  run is going on (**Auto** in the channel's row is lit). Moving a channel's
  contrast yourself switches Auto off for that channel; press **Auto** to
  switch it on again.

The viewer does not slow the acquisition down: it takes a small copy of a
frame a few times a second and does everything else in its own threads.

What is on screen
-----------------

* **2D / 3D** switch, top left of the picture. 3D draws a maximum projection;
  the mouse turns it.
* **Depth (Z) slider** and **time (T) slider** along the bottom, each only
  when there is more than one plane or time point. The Z slider shows the
  depth in micrometres and the plane number.
* **Under the pointer**: the position in micrometres and the value of each
  channel, bottom right.
* **Panel** on the right, foldable:

  * *1 Load data*: **Open from folder…** adds a saved acquisition, and the
    square **Live** switch decides whether what the microscope acquires comes
    in. With Live on, a run that starts appears at the top of the list, marked
    **Live**, and turns **Saved** when it ends. With Live off, nothing new comes
    in, and a run being shown is marked **Paused** until Live is on again.
  * *2 Acquisitions*: those of the watched folder, newest first, and the
    datasets you opened, each a bar with an eye, its name, one line about it
    and Live, Saved or Paused. The eye shows or hides it, so several can be
    shown together. A click on the bar selects it, folds out its positions (one
    acquisition's at a time; the arrow folds them away) and takes the view to
    all of it; a click on a position takes the view to that tile. The × takes a
    saved acquisition off the list; its files stay on disk.
  * *3 Channels*: the selected acquisition's channels, one row each, with an
    eye, a colour swatch, **Auto**, and the contrast with its histogram.
  * *3D view*, in 3D only: the projection (max, blend, min), the detail, the
    gain, where to look from, and whether to draw the plane the Z slider moves.
    **Detail** sets how sharply the volume is drawn for what is on screen, from
    fast to as fine as the screen; beside it, the size of a voxel of the copy of
    the image drawn now. Zooming in draws from finer copies by itself, down to
    the finest the data has, so to look at a detail, zoom in on it. While you
    turn, zoom or pan it, the volume is drawn coarser so that it keeps up, and
    at the detail chosen again as soon as you stop. The volume
    turns about the middle of the stack; while an acquisition runs, Live in 3D
    follows its time points.

* The picture is never silently black: with nothing to draw it says what it is
  waiting for, and a thin bar along the top shows while data is still loading.

Moving around
~~~~~~~~~~~~~

.. list-table::
   :widths: 40 60

   * - Drag
     - move the picture
   * - Scroll
     - zoom in and out
   * - Shift + scroll, or ``,`` and ``.``
     - step through the planes
   * - ``[`` and ``]``
     - step through the time points
   * - Drag, in 3D
     - turn the specimen (Shift + drag moves it)

The **?** button at the top right of the picture shows this list.

Channels are mixed so that a structure that is lit in two channels shows in
both colours. Tiles are placed by their stage positions and are not stitched:
where two tiles overlap, the brighter of the two is seen.

Which data it can show
----------------------

From disk the viewer reads OME-Zarr in version 0.4 or 0.5, with the axes
``t, c, z, y, x`` or some of them in that order, as long as ``z, y, x`` are
there. So ``(z, y, x)``, ``(c, z, y, x)`` and ``(t, z, y, x)`` open too. An
axis that is missing simply counts as one step long. OME-Zarr 0.6 is not read
yet; the viewer says so if you pick one.

That covers what the ``MP_OME_Zarr_TCZYX_Writer`` saves (one
``(t, c, z, y, x)`` store per tile, see :doc:`file_formats`) and what the
``OME_Zarr_Writer`` and ``MP_OME_Zarr_Writer`` save (one store per tile and
channel).

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

Then, without the microscope, a rehearsal of a run in the Data viewer window:

.. code-block:: bash

   python -m mesoSPIM.src.mesospim_viewer.demo --live --window

It acquires four two-channel tiles with the microscope's own OME-Zarr writer,
frame by frame at a camera's pace, and feeds the window the frames the way
mesoSPIM-control does. What to look for:

1. The window opens saying *No acquisition yet*. Within a second or two the
   first tile appears and fills in plane by plane; **Live** is lit, and the Z
   slider moves on its own.
2. Each further tile appears beside the others as it starts, and the view
   zooms out to show them all.
3. Drag the Z slider back: the view stays there and the button reads
   **Back to live**. Press it: the view follows the newest plane again.
4. Hiding a channel with its eye, or changing its colour, stays as it is when
   the next tile starts.
5. 3D shows the tiles as a volume; **Top / Front / Side** turn it.
6. A second run of the same command starts ``run_01`` in the same folder: the
   window shows it in place of ``run_00``, which stays in the list.

Then with the microscope: select ``MP_OME_Zarr_TCZYX_Writer`` in the
file-naming wizard, open the Data viewer, and run a short acquisition list of
two tiles and two lasers. Each stack should fill in as it is acquired, and a
time lapse of a few time points should extend the T slider. In the panel,
while it runs and after:

1. The run comes in at the top, marked **Live**, opened, with its positions:
   the tile being acquired says *acquiring*, the others *next*. With the list
   going laser by laser, a tile with one laser done says *1 of 2 channels*.
2. At the end it turns **Saved**, its line says how many positions and which
   channels, and it has a ×.
3. A click on an earlier acquisition selects it: its positions fold out, the
   other's fold away, the channels below become its own, and the view goes to
   it. A click on one of its positions goes to that tile; **Fit** goes back.
4. **Live** off, and a short run: it does not appear. **Live** on again: it
   appears, **Saved**. **Live** off during a run: it reads **Paused**; on again,
   it goes on.
5. **Open from folder…** adds a saved acquisition; the × takes one off the list
   (its files stay on disk). File > Exit closes the Data viewer with mesoSPIM.

If something is wrong
---------------------

* **The window stays black and says nothing**: usually WebGL in the Qt web
  view. Set ``QTWEBENGINE_CHROMIUM_FLAGS=--ignore-gpu-blocklist`` in the
  environment before starting, and try ``--disable-gpu-driver-bug-workarounds``
  after that. ``python -m mesoSPIM.src.mesospim_viewer.demo --live`` (without
  ``--window``) shows the same rehearsal in the system browser: if the browser
  draws and Qt does not, it is Qt's GPU path and not the viewer.
* **The picture is there but dark**: press **Auto** in the channel's row.
* **The menu entry says PyQtWebEngine is missing** although it is installed:
  it was installed into a different Python environment than the one mesoSPIM
  runs in. ``python -c "import PyQt5.QtWebEngineWidgets"`` from the mesoSPIM
  environment tells.
* **"QtWebEngineWidgets must be imported before a QCoreApplication instance is
  created"**: PyQtWebEngine was installed after mesoSPIM was started, or the
  ``mesoSPIM_DataViewer.prepare_qt()`` call at the top of ``mesoSPIM_Control.py``
  was removed. Restart mesoSPIM.
* **A tile fills in only in large steps, or late**: the window is not getting
  the camera's frames and is following the files on disk instead, which arrive
  64 planes at a time. This is the case when the window was started on its own
  (``python -m mesoSPIM.src.mesospim_viewer.window <folder>``) rather than from
  the View menu.
* **A finished run stays coarse, and is gone when the window is closed**: it
  was saved in a format the viewer cannot read from disk (TIFF, HDF5, raw), so
  the thinned-out copy made from the camera's frames is all there is to show.
  Only OME-Zarr can be opened again.
* **All channels look the same in a dataset from disk**: the dataset holds one
  store per channel, and the stores do not say which channel they hold (they
  have no ``omero`` block). The viewer then cannot tell them apart. This is the
  case for data from the ``OME_Zarr_Writer`` and ``MP_OME_Zarr_Writer`` written
  before they started saving the channel in each store; data written since
  shows each channel as its own row.
* **The data viewer's own tests**: ``python -m pytest mesoSPIM/test/mesospim_viewer``,
  with Playwright and a Chromium for the picture tests (they skip, saying so,
  without them). Changing the page itself needs Node: see
  ``mesoSPIM/src/mesospim_viewer/README.md``.
