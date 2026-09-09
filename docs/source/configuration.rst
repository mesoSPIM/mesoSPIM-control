Configuration
=============

The **configuration file** is a Python (``.py``) file that tells
mesoSPIM-control which hardware is connected and how it is wired.
Every setting — from NI DAQ channel names to stage serial ports — lives here.

Location and selection
----------------------

Config files are stored in ``mesoSPIM/config/``.  On startup, if more than
one ``*.py`` file is present you will be prompted to select one.

The shipped ``demo_config.py`` replaces every hardware device with a software
simulator — use it to verify a fresh installation, or as the starting point
for your own config file.

.. tip::

   Make a copy of ``demo_config.py``, rename it to something like
   ``my_scope_config.py``, and edit that copy.  Never commit credentials or
   personal paths to the main file.

Two-level config files
----------------------

A config file can either define everything itself (the legacy single-file form,
still fully supported) or be split in two levels:

* **shared hardware files** in ``mesoSPIM/config/hardware/``, organised by
  device category — ``cameras/``, ``DAQ/``, ``stages/``, ``lasers/``,
  ``filterwheels/``, ``objectives/`` (zoom, named so for historical reasons),
  ``galvos/``, ``ETLs/`` — plus plugin settings in
  ``mesoSPIM/config/plugins/writers/`` and interface defaults in
  ``mesoSPIM/config/UI/``.  These are shared and meant to be kept up to date
  for everyone;
* **your user file** in ``mesoSPIM/config/``, which picks the hardware of your
  microscope with ``include()`` and overrides whatever is personal to you.

.. code-block:: python

   config_format = 2   # 2 = two-level config; absent or 1 = legacy single file

   include('hardware/cameras/hamamatsu_orca_flash4.py',
           'hardware/DAQ/NI_PXI6259_PXI6733.py',
           'hardware/stages/PI_C884_xyzft.py',
           'hardware/lasers/demo_lasers.py',
           'hardware/filterwheels/demo_filterwheel.py',
           'hardware/objectives/demo_zoom.py',
           'hardware/galvos/demo_galvos.py',
           'hardware/ETLs/demo_etl.py',
           'plugins/writers/demo_writers.py',
           'UI/default_ui.py')

   # everything below wins over the included files
   camera_parameters['x_pixels'] = 2048
   ui_options['dark_mode'] = False
   startup.update({'folder': 'D:/my_data/', 'zoom': '1x'})

Rules:

* ``include()`` needs no import — it is provided by the config loader.  Paths are
  relative to ``mesoSPIM/config/`` (absolute paths also work).
* Anything assigned **after** the ``include()`` call wins; this is ordinary
  Python assignment, no magic.
* Dicts of the same name are **merged key-by-key**, later ``include()`` first,
  so several hardware files each contribute their part of the ``startup`` dict.
  Use ``startup.update({...})`` in your file to override single keys, or
  ``startup = {...}`` to replace the dict entirely.
* Only the user file may include.  An included file that calls ``include()``
  raises a ``ValueError``, so a config is never more than two levels deep and you
  never have to follow a chain of files to see what a setting is.  Two similar
  hardware files repeat their content instead of chaining.
* Files under ``hardware/``, ``plugins/`` and ``UI/`` never show up in the startup file
  dialog — only ``mesoSPIM/config/*.py`` does.

Your editor will flag ``include`` and ``startup`` as undefined in a two-level
file; that is expected, both are supplied at load time.

``mesoSPIM/config/demo_config.py`` is the reference two-level file and is what
demo mode (``-D``) loads.  ``mesoSPIM/config/demo_config_format1(legacy).py`` is the very
same demo microscope written as one legacy file, so the two formats can be
compared side by side; both load into exactly the same settings.

Converting an old config file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Old single-file configs keep working, so there is no need to convert. If you do
want the short form, run from the repository root::

   python -m mesoSPIM.src.utils.convert_config mesoSPIM/config/my_old_config.py -o mesoSPIM/config/my_config.py

The converter picks, for each hardware category, the file under
``config/hardware/`` that fits your config best, and writes the remaining
settings as overrides.  It then loads the old and the new file and compares them
setting by setting; a conversion that would lose a setting is reported as
``FAILED``.  Its report also lists

* settings **dropped** because the software no longer reads them
  (``camera_sensor_mode``, ``camera_parameters['binning']``, ...);
* settings **dropped** because the configured driver ignores them, such as the
  COM port and baud rate of a USB ``'ZWO'`` filter wheel or the servo id of a
  ``'Demo'`` zoom - old configs often keep the port of the device they replaced;
* settings **added** by the shared files, which are newer than your config;
* dicts of operator choices (``filterdict``, ``laserdict``, ``zoomdict``, ...)
  that were kept as a whole, so that filters or lasers you do not have cannot
  appear in the interface.

Use ``--check`` to see all of that without writing anything.  Comments of the old
file are not carried over, so read the result before taking it to the instrument.

Config file structure
---------------------

A config file is plain Python, so you can use arithmetic, imports, and
comments freely.  The sections below describe every top-level variable,
whether it is defined in a single file or in a shared hardware file.

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
       'readout_speed': 1,
       'trigger_active': 1,
       'trigger_mode': 1,
       'trigger_polarity': 2,     # positive pulse
       'trigger_source': 2,       # external
   }

   binning_dict = {'1x1': (1, 1), '2x2': (2, 2), '4x4': (4, 4)}

.. note::

   The binning in use is ``startup['camera_binning']``, not a
   ``camera_parameters['binning']`` key. Older config files carry both; the
   ``camera_parameters`` one is ignored and can be deleted.

For Photometrics camera parameter examples, see
``mesoSPIM/config/hardware/cameras/``.

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
refer to the commented example files in ``mesoSPIM/config/hardware/stages/``,
``objectives/`` and ``ETLs/``, and to the
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

Check the files in ``mesoSPIM/config/hardware/`` and
``mesoSPIM/config/plugins/writers/`` for the latest required keys.

Switching between config files
------------------------------

If you have several setups or configurations, place each ``*.py`` file in
``mesoSPIM/config/`` and mesoSPIM-control will display a selection dialog on
startup.

Further reading
---------------

* `mesoSPIM hardware wiki — configuration file <https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file>`_
* ``mesoSPIM/config/demo_config.py`` — reference two-level config
* ``mesoSPIM/config/hardware/`` — shared, commented hardware definitions
* ``mesoSPIM/config/`` — additional real-world examples
* ``mesoSPIM/config/examples/format1(legacy)/`` — single-file configs of real
  instruments, kept for reference and as converter input
