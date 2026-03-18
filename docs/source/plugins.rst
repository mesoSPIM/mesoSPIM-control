Plugin System
=============

This page is the main developer guide for the mesoSPIM plugin system.
It explains what plugin types exist today, how they are discovered, and
how to build working plugins for image writing and image processing.

If you only use mesoSPIM as an operator, the short sections in
:doc:`user_guide` are usually enough. If you want to extend the software,
start here.

Overview
--------

mesoSPIM currently supports two plugin families:

* **Image writer plugins** create output files during acquisition.
* **Image processor plugins** transform frames before they are displayed or
  written to disk.

These plugin families live under ``mesoSPIM/src/plugins/``:

* ``mesoSPIM/src/plugins/ImageWriters/``
* ``mesoSPIM/src/plugins/ImageProcessors/``

Although some comments in the source mention possible future plugin types
such as camera or stage plugins, those are not part of the current plugin
system.

How Plugins Are Discovered
--------------------------

Plugin discovery happens very early during application startup in
``mesoSPIM/mesoSPIM_Control.py``. After the microscope configuration file is
loaded, :class:`mesoSPIM.src.plugins.manager.PluginRegistry` scans plugin
locations and imports matching modules.

Discovery rules
~~~~~~~~~~~~~~~

* Built-in plugin directories are defined in
  ``mesoSPIM/src/plugins/manager.py``.
* Additional plugin directories can be provided through
  ``plugins['path_list']`` in the microscope config file.
* The loader imports top-level ``*.py`` files and package directories that
  contain ``__init__.py``.
* A module can register plugins explicitly through a
  ``register_mesospim_plugins(registry)`` function.
* If no explicit hook is provided, mesoSPIM scans the imported module for
  classes that look like image writers or image processors.

In practice, registration is permissive. A class may be imported and
registered successfully even if it is still missing methods that the UI or
runtime will call later. For that reason, a plugin being discovered does not
automatically mean it is fully usable.

Plugin Locations
----------------

Built-in plugins live in the repository:

* ``mesoSPIM/src/plugins/ImageWriters/``
* ``mesoSPIM/src/plugins/ImageProcessors/``

External plugins can live anywhere on disk as long as their parent directory
is listed in the active config file:

.. code-block:: python

   plugins = {
       'path_list': [
           'C:/mesospim_plugins',
       ],
       'first_image_writer': 'OME_Zarr_Writer',
   }

Keep these points in mind when authoring external plugins:

* Paths are resolved by the running process, so test them from the same launch
  location you use for mesoSPIM.
* The loader scans one directory level for modules and Python packages.
* Import-time side effects happen immediately when the module is loaded. Avoid
  expensive work at import time whenever possible.
* Some built-in plugins currently install optional dependencies during import.
  That works, but it is better for third-party plugins to fail clearly with a
  good error message than to surprise users during startup.

Image Writer Plugins
--------------------

Image writer plugins are responsible for taking acquired frames and saving
them in a particular format. Writers run in the image-writer thread and are
selected per acquisition entry through the file-naming wizard.

Where Writers Fit in the Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

During acquisition, ``mesoSPIM_ImageWriter`` creates the selected writer,
passes it a :class:`~mesoSPIM.src.plugins.ImageWriterApi.WriteRequest`, then
calls ``write_frame()`` for each frame and ``finalize()`` at the end of the
acquisition.

Core writer lifecycle:

1. ``open(req)``
2. ``write_frame(data)`` repeated for each image
3. ``finalize(finalize_image)``
4. ``abort()`` if acquisition is interrupted

Required Writer Interface in Practice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The formal protocol is documented in
``mesoSPIM/src/plugins/ImageWriterApi.py``, but the runtime expects a little
more than the protocol currently declares.

In practice, a working writer should provide:

* classmethods:

  * ``api_version()``
  * ``name()``
  * ``capabilities()``
  * ``file_extensions()``
  * ``file_names()``

* instance methods:

  * ``open(req)``
  * ``write_frame(data)``
  * ``finalize(finalize_image)``
  * ``abort()``

The ``file_names()`` method is especially important to call out: it is used by
the filename wizard and is effectively required even though it is not declared
in the ``ImageWriter`` protocol.

Data Passed to Writers
~~~~~~~~~~~~~~~~~~~~~~

The following helper dataclasses are defined in
``mesoSPIM/src/plugins/ImageWriterApi.py``:

* ``WriteRequest``: static information for the acquisition being opened,
  including destination path, array shape, axes, voxel size, acquisition
  metadata, and any writer-specific config values.
* ``WriteImage``: one frame plus its current z index and acquisition context.
* ``FinalizeImage``: acquisition metadata passed when finishing the writer.

Current runtime behavior worth knowing:

* ``shape`` is currently passed as ``(z, y, x)``.
* ``dtype`` is currently ``'uint16'`` for the normal acquisition path.
* ``uri`` is currently passed as a path-like string.
* Writer-specific config comes from a top-level config dictionary with the same
  name as the writer, for example ``OME_Zarr_Writer = {...}``.

Metadata and Side Effects
~~~~~~~~~~~~~~~~~~~~~~~~~

Writers are also expected to expose metadata-related attributes used by the
rest of the application:

* ``self.metadata_file``
* ``self.metadata_file_describes_this_path``
* ``self.MIP_path``

The helper ``metadata_file_info()`` in ``ImageWriterApi.py`` sets reasonable
defaults for simple one-file-per-tile writers. More advanced writers often
override it.

Minimal Writer Example
~~~~~~~~~~~~~~~~~~~~~~

Use ``mesoSPIM/src/plugins/ImageWriters/TiffWriter.py`` as the best minimal
example. It shows the standard writer pattern:

* declare metadata such as name, extensions, and capabilities
* open resources in ``open()``
* write one frame at a time in ``write_frame()``
* close resources in ``finalize()``

For debugging and for understanding the data flow, see
``mesoSPIM/src/plugins/ImageWriters/ShamWriter.py``. It prints the
``WriteRequest`` and each frame received by the writer without doing real I/O.

Writer Configuration from the Config File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Writer-specific options are read from the active microscope config file by
looking for a top-level dictionary named exactly after the selected writer.

Example:

.. code-block:: python

   OME_Zarr_Writer = {
       'ome_version': '0.5',
       'generate_multiscales': True,
       'compression': 'zstd',
       'compression_level': 5,
   }

This mechanism is how built-in advanced writers such as
``OME_Zarr_Writer`` and ``MP_OME_Zarr_Writer`` receive chunking,
compression, and multiscale settings.

Writer Authoring Checklist
~~~~~~~~~~~~~~~~~~~~~~~~~~

Before considering a writer complete, verify that it:

* registers and appears in the file-naming wizard
* accepts the chosen file extension
* opens and writes a full acquisition in demo mode
* finalizes cleanly on success
* aborts cleanly when the user presses Stop
* produces metadata paths compatible with mesoSPIM metadata export

Image Processor Plugins
-----------------------

Image processor plugins transform camera frames before display and before the
same processed frames are passed onward for writing. In other words,
processors affect both live viewing and saved output.

Where Processors Fit in the Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Processors are applied inside the camera worker through the processor chain.
The processor chain is configured in the processor-chain dialog and persisted
to ``processor_chain.json`` next to the active config file.

This means processor plugins are not selected through the microscope config
file the way writers are. They are managed interactively in the GUI.

Required Processor Interface in Practice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The protocol lives in ``mesoSPIM/src/plugins/ImageProcessorApi.py``.
A minimal working processor should provide:

* classmethods:

  * ``api_version()``
  * ``name()``
  * ``description()``
  * ``capabilities()``

* instance methods:

  * ``process_frame(image)``

Optional but strongly recommended methods:

* ``configure(params)``
* ``get_config()``
* ``reset()``
* ``parameter_descriptions()``

The processor chain currently always calls ``process_frame()``. Capability
fields such as input dtype, output dtype, dimensionality, and in-place support
are useful documentation, but they are not strictly enforced by the current
runtime.

Parameter Editor Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your processor exposes configuration values, implement both
``get_config()`` and ``configure(params)``.

For a good GUI editing experience, also implement
``parameter_descriptions()``. The processor-chain window uses that metadata to
choose the right widget and constraints for each parameter.

Supported metadata keys include:

* ``type``: ``int``, ``float``, ``bool``, or ``str``
* ``default``
* ``min`` and ``max`` for numeric values
* ``step`` for numeric widgets
* ``decimals`` for floating-point widgets
* ``choices`` for drop-down selections
* ``description`` for user-facing help text

If ``parameter_descriptions()`` is omitted, mesoSPIM falls back to a more
basic editor inferred from ``get_config()``. That fallback is useful for
compatibility, but explicit metadata is preferred.

Minimal Processor Example
~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``mesoSPIM/src/plugins/ImageProcessors/IdentityProcessor.py`` as the best
minimal processor example. It shows the smallest practical processor:

* declares a name and description
* advertises capabilities
* implements ``process_frame()``

Configurable Processor Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``mesoSPIM/src/plugins/ImageProcessors/GaussianBlurProcessor.py`` as the
main template for configurable processors. It demonstrates:

* internal state set in ``__init__``
* ``configure(params)`` for applying changes
* ``get_config()`` for persistence and UI reflection
* ``parameter_descriptions()`` for a strong editor experience

For a more stateful example, see
``mesoSPIM/src/plugins/ImageProcessors/BackgroundSubtractionProcessor.py``.
For a heavier dependency and model-loading example, see
``mesoSPIM/src/plugins/ImageProcessors/NeuralDenoiseProcessor.py``.

Processor Authoring Checklist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before considering a processor complete, verify that it:

* appears in the processor-chain dialog
* can be added, enabled, disabled, reordered, and removed
* works correctly in live view
* behaves acceptably during acquisition, not just in demo tests
* persists and restores its settings through ``processor_chain.json``
* handles repeated reconfiguration cleanly

Short User Guide
----------------

Most users do not need to know the plugin internals, but these behaviors are
useful to understand:

* **Image writers** are chosen in the file-naming wizard for each acquisition
  entry.
* **Image processors** are configured in the processor-chain window, available
  from the main window menu and toolbar.
* Processor settings are saved only when the user clicks **Apply** in the
  processor-chain window.
* When auto-apply is enabled in that window, parameter edits can affect the
  live processor chain immediately, but **Apply** is still required to save the
  configuration to disk.
* Processors affect both live display and acquired image data.

Testing Plugins
---------------

Recommended validation workflow:

1. Start in demo mode so discovery, UI integration, and basic runtime behavior
   can be tested without hardware.
2. For writers, run a short acquisition and verify output, metadata files, and
   abort behavior.
3. For processors, test both live view and saved acquisitions.
4. After demo validation, test on real hardware because timing and throughput
   issues often only appear there.

Common Gotchas
--------------

These implementation details are worth documenting explicitly for plugin
authors:

* ``file_names()`` is required in practice for image writers even though it is
  not declared in the current writer protocol.
* ``metadata_file_info`` is described as a property in the API helper, but it
  is used like a method by the runtime and by several built-in writers.
* Plugin registration is permissive; discovery success is not the same as full
  runtime compatibility.
* Writer and processor modules should avoid surprising import-time work.
* Processor capability flags are informative today, not enforced.
* The current processor-chain UI is oriented around one entry per processor
  type, so test carefully if your workflow assumes duplicates.

Reference Files
---------------

Good source files to study while building plugins:

* ``mesoSPIM/src/plugins/manager.py``
* ``mesoSPIM/src/plugins/ImageWriterApi.py``
* ``mesoSPIM/src/plugins/ImageProcessorApi.py``
* ``mesoSPIM/src/plugins/ImageWriters/TiffWriter.py``
* ``mesoSPIM/src/plugins/ImageWriters/ShamWriter.py``
* ``mesoSPIM/src/plugins/ImageProcessors/IdentityProcessor.py``
* ``mesoSPIM/src/plugins/ImageProcessors/GaussianBlurProcessor.py``
