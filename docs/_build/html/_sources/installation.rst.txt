Installation
============

This page covers the complete installation of **mesoSPIM-control**, including
device drivers for cameras, stages, and data acquisition hardware.

For a simpler "first-run" guide without hardware see :doc:`getting_started`.

System requirements
-------------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Requirement
     - Details
   * - Operating system
     - Windows 7 or later, 64-bit (Windows 10/11 recommended)
   * - Python
     - 3.12 (via `Miniforge <https://github.com/conda-forge/miniforge>`_)
   * - RAM
     - ≥64 GB recommended
   * - Storage
     - Fast NVMe SSD strongly recommended for acquisition write speed

Device drivers
--------------

Install the required drivers **before** connecting hardware and before running
the software.

Data acquisition (NI DAQ)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Download and install the latest
`NI DAQmx drivers <https://www.ni.com/en/support/downloads/drivers/download.ni-daq-mx.html>`_
with default parameters.  Both PCI and cDAQ (USB/Ethernet) devices are
supported.

Cameras
~~~~~~~

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - Camera
     - Driver / SDK
   * - Hamamatsu Orca Flash 4.0 V2/V3
     - `Hamamatsu DCAM API <https://dcam-api.com/>`_.
       Use `HCImage <https://hcimage.com/download/>`_ to test camera connectivity.
   * - Photometrics (PVCAM)
     - `PVCAM and PVCAM-SDK <https://www.teledynevisionsolutions.com/products/pvcam-sdk-amp-driver/?model=PVCAM-SDK>`_
       plus the `PyVCAM <https://github.com/Photometrics/PyVCAM>`_ Python package (requires MS Visual C++ 14.0+).
   * - PCO cameras
     - ``pip install pco`` (version ≥ 0.1.3 recommended).

Stages
~~~~~~

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - Stage controller
     - Driver
   * - Physik Instrumente (PI)
     - `PI software suite <https://www.physikinstrumente.com/en/products/motion-control-software/>`_.
       Test with PI MicroMove.
   * - Steinmeyer / Feinmess (Galil)
     - `Galil API <http://www.galilmc.com/downloads/api>`_.
       Test with GalilTools.
   * - ASI Tiger / MS2000
     - `ASI Tiger drivers <https://www.asiimaging.com/support/download/tiger-controller-console/>`_.
       For USB: follow
       `ASI USB support instructions <https://www.asiimaging.com/support/download/usb-support-on-ms-2000-wk-controllers/>`_.

Software installation
---------------------

1. **Clone the repository**

   Using GitHub Desktop (recommended) or download the ZIP archive::

      # Example target path
      C:/Users/Public/mesoSPIM-control

2. **Create a Conda/Mamba environment**

   Open a Miniforge prompt::

      mamba create -p C:/Users/Public/mamba/envs/mesoSPIM-py312 python=3.12
      mamba activate C:/Users/Public/mamba/envs/mesoSPIM-py312

3. **Install Python dependencies**

   ::

      cd C:/Users/Public/mesoSPIM-control
      pip install -r requirements-conda-mamba.txt

4. **Verify the installation**

   Run in demo mode to check that all Python packages load correctly::

      cd mesoSPIM
      python mesoSPIM_Control.py -D

   The GUI should open with all devices shown as ``Demo`` simulators.

Launching
---------

Miniforge prompt
~~~~~~~~~~~~~~~~

::

   cd C:/Users/Public/mesoSPIM-control/mesoSPIM
   python mesoSPIM_Control.py          # normal mode (requires config + hardware)
   python mesoSPIM_Control.py -D       # demo mode (no hardware required)

Desktop shortcut (recommended for daily use)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. From the Miniforge prompt, run ``where mamba`` and note the path, e.g.
   ``C:\Users\Nikita\miniforge3\Scripts\activate.bat``.

2. Open ``mesoSPIM/mesoSPIM.bat`` in a text editor and paste that path into
   line 10, for example:

   .. code-block:: bat

      "%windir%\System32\cmd.exe" /k ""C:\Users\Nikita\miniforge3\Scripts\activate.bat" "C:\Users\Public\conda\envs\mesoSPIM-py312" && python "mesoSPIM_Control.py""

3. Save the file, double-click it to verify the GUI opens, then create a
   desktop shortcut for quick access.

Updating
--------

We recommend installing each new version into a **fresh folder** (e.g.
``mesoSPIM-control-Jan2025``) using the steps above.

After updating, review the :doc:`changelog` and compare your existing config
file against the latest ``demo_config.py`` to add any new required sections.

Troubleshooting
---------------

* **Error messages at startup** — check the Miniforge/conda terminal window.
* **Detailed logs** — every session writes a timestamped log file in
  ``mesoSPIM/log/``, e.g. ``20241210-154845.log``.
* **Forum** — post questions at the
  `image.sc forum <https://forum.image.sc/tag/mesospim>`_.
