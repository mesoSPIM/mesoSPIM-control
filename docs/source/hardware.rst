Supported Hardware
==================

This page lists all hardware devices that mesoSPIM-control can drive, together
with the configuration key used to enable each one.  Every category also
includes a ``Demo`` simulator for software-only testing.

Cameras
-------

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - Camera model
     - Config key
     - Notes
   * - **Demo (simulated)**
     - ``'DemoCamera'``
     - Software simulator; no driver required.
   * - **Hamamatsu Orca Flash 4.0 V3**
     - ``'HamamatsuOrca'``
     - 2048 × 2048, 6.5 µm pixel. Supported and recommended. Requires `DCAM API <https://dcam-api.com/>`_. Use PCIe frame grabber (not USB3).
   * - **Hamamatsu Orca Fusion**
     - ``'HamamatsuOrca'``
     - 2304 × 2304, 6.5 µm pixel. Tested, stable. Use CoaXPress frame grabber (not USB3). Requires DCAM API.
   * - **Teledyne Photometrics Kinetix**
     - ``'Photometrics'``
     - 3200 × 3200, 6.5 µm pixel. Tested, stable. High resolution across entire FOV only with large-FOV detection objectives. Requires PVCAM + PVCAM-SDK + PyVCAM.
   * - **Teledyne Photometrics Prime BSI / Prime BSI Express**
     - ``'Photometrics'``
     - 2048 × 2048, 6.5 µm pixel. Tested, stable. Requires PVCAM + PVCAM-SDK + PyVCAM.
   * - **Teledyne Photometrics Iris 15**
     - ``'Photometrics'``
     - 5056 × 2960, 4.25 µm pixel. Supported and recommended for mesoSPIM-2.0 (Benchtop). Requires PVCAM + PVCAM-SDK + PyVCAM.
   * - **PCO cameras**
     - ``'PCO'``
     - Requires the ``pco`` Python package (≥ 0.1.3).

Camera parameters — pixel size, binning, trigger mode, etc. — are set in
the ``camera_parameters`` dict.  See :doc:`configuration` for examples.

Stages
------

mesoSPIM-control supports a variety of stage combinations.  The ``stage``
config key selects the stage *class*; individual axis assignments are set in
the ``stage_parameters`` dict.

.. list-table::
   :widths: 35 35 30
   :header-rows: 1

   * - Stage class
     - Config key
     - Typical use
   * - **Demo stage**
     - ``'DemoStage'``
     - Simulation; no hardware.
   * - **PI (1 controller → N axes)**
     - ``'mesoSPIM_PI_1toN'``
     - Single PI controller (e.g. C-884, serves up to 6 axes incl. rotation) for all axes. Default for mesoSPIM v4–v5.
   * - **PI (N controllers → N axes)**
     - ``'mesoSPIM_PI_NtoN'``
     - One PI controller per axis (e.g. C-663, one stage per controller). mesoSPIM v5 option.
   * - **PI (rot+Z) + Galil (X,Y,F)**
     - ``'mesoSPIM_PI_rotz_and_Galil_xyf_Stages'``
     - Mixed PI / Galil setup (mesoSPIM v4–v5). Galil support is deprecated.
   * - **ASI Tiger / MS2000**
     - ``'mesoSPIM_ASI_Stages'``
     - ASI Tiger TG8-BASIC: 4 motor slots + 5 free slots. Benchtop mesoSPIM default controller; supports TTL trigger.

PI stages require the `PI software suite <https://www.physikinstrumente.com/en/products/motion-control-software/>`_.
Galil stages require the `Galil API <http://www.galilmc.com/downloads/api>`_.
ASI stages require `ASI Tiger drivers <https://www.asiimaging.com/support/download/tiger-controller-console/>`_.

Filter wheels
-------------

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - Filter wheel
     - Config key
     - Notes
   * - **Demo**
     - ``'DemoFilterWheel'``
     - Simulation.
   * - **Ludl 96A350**
     - ``'LudlFilterWheel'``
     - 32 mm, 10 positions. Large filter wheel with separate MAC6000 controller, serial cable. mesoSPIM v4–v5.
   * - **Sutter Lambda 10**
     - ``'SutterFilterWheel'``
     - 25 mm, 10 positions. Serial communication; configurable baud rate and wheel speed. Deprecated (used in early versions).
   * - **ZWO EFW-MINI**
     - ``'ZWO_EFW'``
     - 31 mm, 5 positions. Compact, low-cost astronomy filter wheel with integrated USB controller. mesoSPIM Benchtop. Requires ``pyzwoefw`` bindings.

Zoom / magnification
--------------------

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - Zoom actuator
     - Config key
     - Notes
   * - **Demo zoom**
     - ``'Demo'``
     - Simulation.
   * - **Dynamixel servo**
     - ``'Dynamixel'``
     - Robotis Dynamixel servo for motorised zoom body.
   * - **Mitutoyo turret**
     - ``'Mitu'``
     - Mitutoyo motorized turret.

Lasers / laser enable
---------------------

Laser power is modulated via **analogue output** on the NI DAQ card.
Individual laser lines are enabled / blanked via **digital output** lines.

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - Laser control
     - Config key
     - Notes
   * - **Demo**
     - ``'Demo'``
     - Simulation.
   * - **NI DAQ digital enable**
     - ``'NI'``
     - One DO line per laser (see ``laserdict`` in :doc:`configuration`).

Shutters
--------

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - Shutter type
     - Config key
     - Notes
   * - **Demo**
     - ``'Demo'``
     - Simulation.
   * - **NI DAQ**
     - ``'NI'``
     - Digital output shutter control (see ``shutterdict``).

Data acquisition (DAQ)
-----------------------

Galvo scan waveforms, ETL (electrically tunable lens) ramps, laser
modulation, and camera triggers are generated by National Instruments cards.

.. list-table::
   :widths: 30 25 45
   :header-rows: 1

   * - DAQ backend
     - Config key
     - Notes
   * - **Demo waveform generator**
     - ``'DemoWaveFormGeneration'``
     - Simulation.
   * - **NI PXI/PCIe (AO)**
     - ``'NI'``
     - PXI6259 (galvo/ETL) + PXI6733 (lasers), or equivalent.
   * - **NI cDAQ**
     - ``'NI_cDAQ'``
     - USB/Ethernet cDAQ chassis; see ``config_benchtop-cDAQ.py`` example.

Adding custom hardware
-----------------------

mesoSPIM-control uses a plugin architecture for image writers and a class
hierarchy for hardware devices.  To add a new device type:

1. Create a new ``.py`` file in the appropriate sub-folder of
   ``mesoSPIM/src/devices/``.
2. Subclass the relevant base class (e.g. ``mesoSPIM_Stage``,
   ``mesoSPIM_GenericCamera``).
3. Register the new class name in your config file.

See :doc:`contributing` and the :doc:`api/index` for details.
