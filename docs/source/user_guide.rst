User Guide
==========

This guide walks you through the mesoSPIM-control GUI and its core workflows —
from moving a sample to running a fully automated tiled acquisition.

Overview of the interface
--------------------------

.. figure:: ../../docs/screenshots/all-windows-v1.9.0.png
   :alt: mesoSPIM-control main windows
   :width: 100%

   **mesoSPIM-control v1.9** — Main window (left), Camera live view (centre),
   and Acquisition Manager (right).

The application has five main windows:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Window
     - Purpose
   * - **Main window**
     - Stage position read-out, manual motion controls, laser/shutter
       selection, and single-image snap.
   * - **Camera window**
     - Live camera preview with auto-range intensity scaling.
   * - **Acquisition Manager**
     - Build, edit, and run multi-position / multi-channel acquisition lists.
   * - **Script window**
     - Run Python scripts against the live mesoSPIM state.
   * - **Webcam window**
     - Optional USB webcam feed for sample monitoring (configurable in
       ``ui_options``).

Main window
-----------

Stage controls
~~~~~~~~~~~~~~

The ``X / Y / Z / F / θ`` buttons move the corresponding axis by the step
size shown in the adjacent spin box.  Button polarity and step-motion delays
are configurable in the :doc:`configuration` file (``flip_XYZFT_button_polarity``,
``button_sleep_ms_xyzft``).

.. note::

   The **F axis** controls the focus/objective position.  If your setup uses a
   revolving objective turret, set ``enable_f_zero_button: False`` in the
   config to prevent accidental mechanical conflicts.

Shutter and laser selection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Use the **shutter drop-down** to choose Left, Right, or Both illumination
  arms.
* Select the active **laser** from the wavelength drop-down.  Only lasers
  listed in ``laserdict`` will appear.

Single-image acquisition (Snap)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set the exposure time (ms), choose a filename, and click **Snap** to capture
a single image without creating an acquisition entry.

Camera window
-------------

The live view updates continuously when a laser and shutter are open.
Right-click the histogram to set intensity levels; the **Auto** button fits
the display to the current frame.

.. tip::

   Excessive ``autorange`` calls can cause GUI stuttering during acquisition.
   Use a fixed display range in production runs.

Acquisition Manager
-------------------

Building an acquisition list
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each row in the Acquisition Manager table represents one
**acquisition entry** — a combination of position (X, Y, Z, F, θ),
illumination (laser, filter, shutter), and file settings.

Common workflow:

1. Move the sample to the desired start position using the Main window.
2. Click **Add current position** to create a new entry.
3. Set the **Z start / Z end / Z step** values for a Z-stack.
4. Choose the **laser**, **filter**, and **shutter** arm.
5. Enter the **exposure time** and **filename**.
6. Repeat for additional positions or channels.

Acquisition modes
~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Mode
     - Description
   * - **Single plane**
     - One image per entry.
   * - **Z-stack**
     - Sweeps the Z axis from *Z start* to *Z end* in *Z step* increments.
   * - **Tiled**
     - Combines multiple XY positions into a seamless mosaic (uses the
       Tile View window to plan overlap).
   * - **Multiview / dual-illumination**
     - Alternates Left / Right illumination between planes.
   * - **Time-lapse**
     - Repeats the entire acquisition list at defined time intervals.

.. figure:: ../../docs/screenshots/timelapse-launch.png
   :alt: Time-lapse launch dialog
   :width: 60%

   Time-lapse configuration dialog.

Output file formats
~~~~~~~~~~~~~~~~~~~~

Select the image writer in the file-naming wizard:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Writer
     - Description
   * - ``OME_Zarr_Writer``
     - OME-ZARR 0.4 (zarr v2) with automatic multi-scale pyramid.
       Recommended for new acquisitions.
   * - ``MP_OME_Zarr_Writer``
     - Multi-process OME-ZARR writer — faster on systems with fast SSDs.
   * - ``H5_BDV_Writer``
     - HDF5/BigDataViewer format compatible with BigStitcher.
   * - ``Tiff_Writer``
     - Single TIFF per plane — simple and universal.
   * - ``Big_Tiff_Writer``
     - BigTIFF for stacks larger than 4 GB.
   * - ``RAW_Writer``
     - Raw 16-bit binary dump.

Running an acquisition
~~~~~~~~~~~~~~~~~~~~~~

Click **Run** in the Acquisition Manager toolbar to start.  Progress is shown
in the status bar and log.  To stop mid-acquisition click **Stop**.

Script window
-------------

The script window exposes the full mesoSPIM Python API.  Scripts run in the
same process and can read/write the instrument state, move stages, snap
images, and iterate over acquisition lists.

A selection of example scripts is in ``mesoSPIM/scripts/``.

Keyboard shortcuts
------------------

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Key
     - Action
   * - ``Space``
     - Stop current acquisition
   * - ``F5``
     - Refresh GUI from hardware state
   * - ``Ctrl+S``
     - Save acquisition list

Logging and troubleshooting
----------------------------

* All session output is logged to a timestamped file in ``mesoSPIM/log/``,
  e.g. ``20241210-154845.log``.
* Set ``logging_level = 'DEBUG'`` in your config for ultra-verbose output.
* For live status, watch the terminal where you launched the software.

Further resources
-----------------

* `ZMB Dozuki guides <https://zmb.dozuki.com/c/Lightsheet_microscopy#Section_MesoSPIM>`_
  — start-up, setup, and acquisition walkthroughs.
* `mesoSPIM YouTube channel <https://www.youtube.com/c/mesoSPIM>`_
* `image.sc user forum <https://forum.image.sc/tag/mesospim>`_
