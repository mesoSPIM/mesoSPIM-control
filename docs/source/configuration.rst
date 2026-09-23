Configuration
=============

The **configuration file** is a Python (``.py``) file that tells
mesoSPIM-control which hardware is connected and how it is wired.
Every setting — from NI DAQ channel names to stage serial ports — lives here.

Since version 1.26 a configuration is split over **two files**:

``mesoSPIM/config/hardware/<rig>_hw.py``
   The *hardware file*: the ground truth for one instrument. Camera model,
   filter wheel and filters, objectives, galvo offsets and amplitudes, stages,
   DAQ lines, writer defaults. It changes when the instrument changes.

``mesoSPIM/config/<rig>.py``
   The *user file*: one ``include()`` line that pulls in the hardware file,
   plus the handful of settings that differ for your session — where the data
   goes, how files are named, which state the software starts in.

Single-file configurations from earlier versions still load unchanged.

Location and selection
----------------------

User config files are stored in ``mesoSPIM/config/``.  On startup, if more than
one ``*.py`` file is present you will be prompted to select one.  Hardware files
live one level down in ``mesoSPIM/config/hardware/`` and never appear in that
dialog, so they cannot be picked by mistake.

The shipped ``demo_config.py`` replaces every hardware device with a software
simulator — use it to verify a fresh installation, or as the starting point
for your own config file.  Its hardware file is
``mesoSPIM/config/hardware/demo_config_hw.py``.

.. tip::

   Copy *both* files, rename them to something like ``my_scope.py`` and
   ``hardware/my_scope_hw.py``, point the ``include()`` line at your copy, and
   edit those.  Never commit credentials or personal paths to the main file.

Config file structure
---------------------

Both files are plain Python, so you can use arithmetic, imports, and comments
freely.  The variables documented in the sections below all belong in the
**hardware file** — that is where the old single-file config went.

The user file only needs three things:

.. code-block:: python

   config_format = 2

   include('hardware/my_scope_hw.py')

   startup.update({
       'state': 'init',
       'folder': 'D:/data/',
       'snap_folder': 'D:/data/',
       'file_prefix': '',
       'file_suffix': '000001',
   })

``include()`` copies every variable from the hardware file into the user file.
The path is relative to the user file, so a config and its copy in a different
folder use the same line.  Anything written *after* ``include()`` wins, because
it is simply later Python:

.. code-block:: python

   include('hardware/my_scope_hw.py')

   startup['camera_exposure_time'] = 0.05   # override one value
   filterdict['Empty-Alignment'] = 0        # add one entry

Only the user file may call ``include()``.  A hardware file that calls it raises
``NameError``, so a configuration is never more than two files deep and you never
have to follow a chain of includes to find out what a setting is.

Converting an existing config
-----------------------------

A single-file config is converted with:

.. code-block:: bash

   python -m mesoSPIM.src.utils.convert_config path/to/my_config.py

This writes ``my_config.py`` (the user file) and ``hardware/my_config_hw.py``
next to it.  The hardware file is the original, byte for byte, minus the five
session settings that move to the user file.  Before the files are written, the
converter loads the new pair and compares it against the original; if anything
differs it raises and writes nothing.  Pass ``-o OUTDIR`` to convert into a
different directory instead of in place.

.. warning::

   The converter proves that the *values* are unchanged.  It cannot test the
   instrument.  Check trigger lines, COM ports and travel limits before running
   a converted config on a microscope.

plugins
~~~~~~~

Controls where mesoSPIM looks for plugins and which image writer appears first
in the file-naming wizard.

.. code-block:: python

   plugins = {
       'path_list': [
            "../src/plugins",                # relative paths work
            "C:/a/different/plugin/location",
        ],
       'first_image_writer': 'OME_Zarr_Writer',
        # other options: 'H5_BDV_Writer', 'MP_OME_Zarr_Writer',
        #                'Tiff_Writer', 'Big_Tiff_Writer', 'RAW_Writer'
    }

``path_list`` adds extra directories that are scanned for image-writer,
image-processor, and filter-wheel plugins. Built-in plugins are always loaded
from the repository's plugin directories.

``first_image_writer`` only affects the ordering in the file-naming wizard. It
does not force a writer for all acquisitions.

Writer-specific settings are provided through additional top-level dictionaries
named after the writer itself, for example:

.. code-block:: python

   OME_Zarr_Writer = {
       'ome_version': '0.5',
       'generate_multiscales': True,
       'compression': 'zstd',
       'compression_level': 5,
   }

These dictionaries are read by the selected writer at acquisition time. See
:doc:`file_formats` for every writer's available options and what they do.

Image processors are handled differently: they are configured in the
processor-chain dialog and persisted to ``processor_chain.json`` next to the
active microscope config file rather than through top-level config variables.

Filter-wheel plugins are selected by setting a plugin's ``name()`` as
``filterwheel_parameters['filterwheel_type']``. For example, the built-in
``LudlPlugin`` requires explicit connection and wait settings:

.. code-block:: python

   filterwheel_parameters = {
       'filterwheel_type': 'LudlPlugin',
       'COMport': 'COM3',
       'baudrate': 9600,
       'wait_until_done_delay': 0.2,
   }

The plugin-based Sutter Lambda 10 driver also requires wheel speed:

.. code-block:: python

   filterwheel_parameters = {
       'filterwheel_type': 'SutterPlugin',
       'COMport': 'COM3',
       'baudrate': 9600,
       'wheel_speed': 3,
       'wait_until_done_delay': 0.5,
   }

The baud rate must match the controller's serial-interface configuration;
Sutter Lambda 10 controllers typically use 9600.

FLI High Speed Filter Wheels use the configured position numbers directly:

.. code-block:: python

   filterwheel_parameters = {
       'filterwheel_type': 'FLI',
       'COMport': 'COM3',
       'baudrate': 9600,
       'wait_until_done_delay': 0.2,
   }

Set ``filterdict`` to the position numbering verified on the specific HS-625,
HS-1025, or HS-1032 wheel. Those mappings define the available positions. The
plugin sends zero-based positions 0 through 9 directly without an indexing
offset.

The established ``Demo``, ``Ludl``, ``Dynamixel``, ``Sutter``, and ``ZWO``
names continue to select their existing built-in drivers. See
:doc:`plugins` for the filter-wheel factory and runtime interfaces.

ui_options
~~~~~~~~~~

UI appearance and button visibility.

.. code-block:: python

   ui_options = {
       'dark_mode': True,
       'enable_x_buttons': True,
       'enable_y_buttons': True,
       'enable_z_buttons': True,
       'enable_f_buttons': True,
       'enable_f_zero_button': True,   # False for revolving objectives
       'enable_rotation_buttons': True,
       'enable_loading_buttons': True,
       'flip_XYZFT_button_polarity': (True, False, False, False, False),
       'button_sleep_ms_xyzft': (250, 0, 250, 0, 0),
       'window_pos': (0, 0),           # top-left corner of the main window
       'usb_webcam_ID': 0,             # None to disable
       'flip_auto_LR_illumination': False,
   }

logging_level
~~~~~~~~~~~~~

.. code-block:: python

   logging_level = 'INFO'   # 'DEBUG' for verbose; 'INFO' for production

acquisition_hardware
~~~~~~~~~~~~~~~~~~~~~

NI DAQ card line assignments.  Names must match exactly what NI MAX shows.

.. code-block:: python

   acquisition_hardware = {
       'master_trigger_out_line':      'PXI6259/port0/line1',
       'camera_trigger_source':        '/PXI6259/PFI0',
       'camera_trigger_out_line':      '/PXI6259/ctr0',
       'galvo_etl_task_line':          'PXI6259/ao0:3',  # Galvo-L, Galvo-R, ETL-L, ETL-R
       'galvo_etl_task_trigger_source':'/PXI6259/PFI0',
       'laser_task_line':              'PXI6733/ao0:3',  # lasers in wavelength order
       'laser_task_trigger_source':    '/PXI6259/PFI0',
   }

waveformgeneration
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   waveformgeneration = 'NI'   # 'DemoWaveFormGeneration' for simulated mode

laser / laserdict
~~~~~~~~~~~~~~~~~

.. code-block:: python

   laser = 'NI'   # 'Demo' or 'NI'

   # Keys shown in the GUI; values are digital enable lines.
   # Must be in increasing wavelength order.
   laserdict = {
       '405 nm': 'PXI1Slot4/port0/line2',
       '488 nm': 'PXI1Slot4/port0/line3',
       '561 nm': 'PXI1Slot4/port0/line4',
       '638 nm': 'PXI1Slot4/port0/line5',
   }

   laser_blanking = 'images'   # 'images' or 'stacks'

shutter
~~~~~~~

.. code-block:: python

   shutter = 'NI'            # 'Demo' or 'NI'
   shutterswitch = False     # True: left = general shutter, right = L/R switch
   shutteroptions = ('Left', 'Right')
   shutterdict = {
       'shutter_left':  'PXI6259/port0/line0',
       'shutter_right': 'PXI6259/port2/line0',
   }

camera
~~~~~~

.. code-block:: python

   camera = 'HamamatsuOrca'   # 'DemoCamera', 'HamamatsuOrca', or 'Photometrics'

   # Example — Hamamatsu Orca Flash 4.0 V2/V3
   camera_parameters = {
       'x_pixels': 2048,
       'y_pixels': 2048,
       'x_pixel_size_in_microns': 6.5,
       'y_pixel_size_in_microns': 6.5,
       'subsampling': [1, 2, 4],
       'camera_id': 0,
       'sensor_mode': 12,         # 12 = progressive
       'defect_correct_mode': 2,
       'binning': '1x1',
       'readout_speed': 1,
       'trigger_active': 1,
       'trigger_mode': 1,
       'trigger_polarity': 2,     # positive pulse
       'trigger_source': 2,       # external
   }

   binning_dict = {'1x1': (1, 1), '2x2': (2, 2), '4x4': (4, 4)}

For Photometrics camera parameter examples, see ``demo_config.py``.

microscope_parameters
~~~~~~~~~~~~~~~~~~~~~

Optional microscope-specific metadata that is copied into acquisition and snap
metadata sidecar files. These fields are descriptive only and do not change
instrument behavior.

.. code-block:: python

   microscope_parameters = {
       'name': 'Atlas mesoSPIM',
       'location': 'Imaging room 2.14',
       'instrument_id': 'MSPIM-01',
       'notes': 'Dual-sided setup with custom sample chamber',
       'objective': {
           'name': 'Olympus XLPLN10XSVMP',
           'model_number': '1-U2B933',
           'magnification': '10x',
           'numerical_aperture': 0.6,
           'working_distance_mm': 8.0,
           'immersion_medium': 'silicone oil',
           'design_refractive_index': 1.406,
           'coverglass_thickness_mm': 0.17,
       },
       'users': {
           'authorized': ['Doe, John', 'Doe, Jane', 'Chewbacca'],
           'owner': 'Leia Organa',
       },
    }

Top-level non-dictionary entries are written into a ``MICROSCOPE PARAMETERS``
block. Top-level dictionary entries are expanded one level deep into separate
blocks named after the key, for example ``objective`` -> ``OBJECTIVE`` and
``users`` -> ``USERS``.

Lists, tuples, and deeper nested dictionaries inside those blocks are written as
JSON-formatted values on a single line.

For backward compatibility, the legacy top-level ``objective_parameters``
dictionary is still supported. If ``microscope_parameters['objective']`` is not
present, mesoSPIM writes ``objective_parameters`` into an ``OBJECTIVE`` block.

stages / zoom / ETL
~~~~~~~~~~~~~~~~~~~~

For stage, zoom motor, and ETL (electrically tunable lens) configuration
refer to the extensive comments and examples directly in ``demo_config.py``
and the
`mesoSPIM hardware wiki <https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file>`_.

Mandatory dictionaries (v1.20+)
-------------------------------

Since release 1.20.0 the following empty dictionaries **must** be present even
if the corresponding feature is not used:

.. code-block:: python

   plugins = {}
   H5_BDV_Writer = {}
   OME_Zarr_Writer = {}
   MP_OME_Zarr_Writer = {}

Check the ``demo_config.py`` for the latest required keys.

The zoom tables are checked at startup and mesoSPIM-control refuses to start if
they cannot work, because ``pixelsize[zoom]`` is read while an acquisition is
running, where a missing key costs the whole run:

* ``zoomdict`` and ``pixelsize`` must have exactly the same keys;
* ``startup['zoom']`` must be one of those keys.

Switching between config files
------------------------------

If you have several setups or configurations, place each user file in
``mesoSPIM/config/`` and mesoSPIM-control will display a selection dialog on
startup.  Several user files may include the same hardware file — that is the
tidy way to keep, say, a 20 ms and a 200 ms exposure variant of one microscope
without duplicating its wiring.

Further reading
---------------

* `mesoSPIM hardware wiki — configuration file <https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file>`_
* ``mesoSPIM/config/hardware/demo_config_hw.py`` — heavily commented reference hardware file
* ``mesoSPIM/config/demo_config.py`` — the matching user file
* ``mesoSPIM/config/examples/demo_config_legacy.py`` — the same config in the old single-file format
* ``mesoSPIM/config/examples/`` — additional real-world examples
