Image Processing Plugins (beta)
==========================

mesoSPIM-control can apply a configurable chain of image-processing steps to
every camera frame, both in the live view and in the data that gets written
to disk. This page covers using the built-in processors from the GUI; if you
want to write your own processor plugin, see :doc:`plugins` instead.

.. warning::

   The image processor plugin system is still in **beta testing**. Some
   built-in processors have known performance bottlenecks that can reduce
   the achievable frame rate. Test a
   candidate chain with **Live** at your target frame rate before relying on
   it during a real acquisition.

Opening the Processor Chain window
-------------------------------------

Open **Plugins → Processor Chain** in the Main window, or press
``Ctrl+Shift+P``.

.. important::

   Processors affect **both** the live view and the frames written to disk
   for the current acquisition. Disable a processor (uncheck it in the
   Active Chain) if you only want to inspect raw data.

The window has two lists side by side:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Panel
     - Purpose
   * - **Available Processors**
     - Every processor type discovered at startup (built-in and any from
       ``plugins['path_list']`` in your config). Select one and click
       **Add →** to append it to the chain.
   * - **Active Chain**
     - Processors currently applied, in order, top to bottom. Each entry has
       a checkbox to enable/disable it without removing it. Drag rows to
       reorder them, or use **↑ Up** / **↓ Down**. **Remove** deletes the
       selected entry entirely.

Order matters: frames pass through the chain top to bottom, so e.g. a
background-subtraction step should usually come before a denoising step.

Editing parameters
---------------------

Selecting a processor in the Active Chain shows its parameters below, in
**Selected Processor Parameters**.

* By default, parameter edits are only *staged* — click **Apply** to push
  them to the live chain and save them to disk.
* Check **Auto-apply parameter changes** to have edits take effect in the
  live chain immediately as you type/adjust them. **Apply** is still
  required afterwards to persist the change for the next session.
* **Close** exits the dialog; unsaved (non-auto-applied) edits are not
  written to disk.

Configuration is saved to ``processor_chain.json`` next to the active
microscope config file, and the active chain is recorded in each
acquisition's metadata.

Built-in processors
-----------------------

.. list-table::
   :widths: 20 30 50
   :header-rows: 1

   * - Processor
     - Parameters
     - Description
   * - **Identity**
     - —
     - Pass-through, no change. Useful as a placeholder or for testing.
   * - **GaussianBlur**
     - ``sigma`` (px, default 1.0)
     - Gaussian smoothing for spatial denoising; larger ``sigma`` means more
       smoothing.
   * - **DifferenceOfGaussians**
     - ``sigma_low`` / ``sigma_high`` (px), ``device``
     - Band-pass filter (difference of two Gaussian blurs) that enhances
       features between the two length scales while suppressing very fine
       noise and very broad background. Runs on CPU or CUDA via PyTorch
       (``device: auto`` picks CUDA if available).
   * - **BackgroundSubtraction**
     - ``method`` (``rolling_ball`` / ``threshold``), ``radius``,
       ``threshold``
     - Removes uneven background. *Rolling ball* estimates a smooth
       background with a uniform filter of the given ``radius``;
       *threshold* subtracts a constant value.
   * - **Binning**
     - ``bin_factor`` (1–16), ``method`` (``mean`` / ``sum`` / ``max``)
     - Downsamples the frame by ``bin_factor`` × ``bin_factor`` blocks,
       reducing it with the chosen reduction method.
   * - **NeuralDenoise**
     - ``num_frames`` (1/3/5/7/9/11), ``device``
     - Temporal denoising with a PyTorch model that predicts a cleaned-up
       version of the most recent frame from a short sliding window of the
       last ``num_frames`` frames. Requires the matching
       ``denoise_Nframe.pth`` weights file (see below) and PyTorch, with
       optional CUDA acceleration.

.. note::

   ``NeuralDenoise`` model weights live in
   ``mesoSPIM/src/plugins/support_files/ImageProcessors/NeuralDenoise/``.
   Only some frame counts may ship by default — if you select a
   ``num_frames`` value whose ``.pth`` file isn't present, the processor
   logs an error and the frame passes through unprocessed. Ask on the
   `image.sc forum <https://forum.image.sc/tag/mesospim>`_ if you need a
   model for a frame count that isn't bundled.

GPU acceleration
-------------------

``DifferenceOfGaussians`` and ``NeuralDenoise`` both accept a ``device``
parameter (``auto`` / ``cpu`` / ``cuda``) and use PyTorch. ``auto`` selects
CUDA automatically if a compatible GPU and PyTorch+CUDA install are present,
otherwise falls back to CPU. If PyTorch (or a CUDA build of it) is missing,
these processors log a warning and pass frames through unchanged rather than
crashing the acquisition.

Troubleshooting
-------------------

* **A processor seems to do nothing** — check it's enabled (checkbox in the
  Active Chain) and that changes were applied (auto-apply, or **Apply**).
* **Live view is fine but saved data looks unprocessed, or vice versa** — the
  same chain applies to both; check you're comparing frames from the same
  acquisition and that the chain wasn't changed (and re-applied) in between.
* **NeuralDenoise / DifferenceOfGaussians raise an import or file-not-found
  error** — install PyTorch (``pip install torch``, with a CUDA build if you
  want GPU acceleration), and for NeuralDenoise confirm the
  ``denoise_Nframe.pth`` file for your chosen ``num_frames`` exists.

For plugin authoring (writing a new processor type), see :doc:`plugins`.
