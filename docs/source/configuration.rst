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

Config file structure
---------------------

A config file is plain Python, so you can use arithmetic, imports, and
comments freely.  The sections below describe every top-level variable.

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

``path_list`` adds extra directories that are scanned for both image-writer
and image-processor plugins. Built-in plugins are always loaded from the
repository's plugin directories.

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

These dictionaries are read by the selected writer at acquisition time.

Image processors are handled differently: they are configured in the
processor-chain dialog and persisted to ``processor_chain.json`` next to the
active microscope config file rather than through top-level config variables.

See :doc:`plugins` for the full developer-facing plugin guide.

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

Switching between config files
------------------------------

If you have several setups or configurations, place each ``*.py`` file in
``mesoSPIM/config/`` and mesoSPIM-control will display a selection dialog on
startup.

Further reading
---------------

* `mesoSPIM hardware wiki — configuration file <https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file>`_
* ``mesoSPIM/config/demo_config.py`` — heavily commented reference config
* ``mesoSPIM/config/`` — additional real-world examples
