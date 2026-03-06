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
     - 2048 × 2048, 6.5 µm pixel. Supported and recommended for classic mesoSPIM v4–v5. Requires `DCAM API <https://dcam-api.com/>`_. Use PCIe frame grabber (not USB3). Config: ``sensor_mode=12``, ``readout_speed=1``.
   * - **Hamamatsu Orca Fusion**
     - ``'HamamatsuOrca'``
     - 2304 × 2304, 6.5 µm pixel. Tested, stable. Use CoaXPress frame grabber (not USB3). Requires DCAM API. Config: ``sensor_mode=12``, ``readout_speed=2``.
   * - **Hamamatsu Orca Lightning**
     - ``'HamamatsuOrca'``
     - 4608 × 2592, 5.5 µm pixel. High-speed sCMOS; used in mesoSPIM v6 (ZMB / HIFO). Requires DCAM API with Lightning firmware. Config: ``trigger_mode=1`` (NORMAL), ``high_dynamic_range_mode=2``; no ``readout_speed`` key.
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
     - ``'PI'`` or ``'PI_1controllerNstages'``
     - Single PI C-884 controller (up to 6 axes incl. rotation). Both keys are accepted. Axes: V4 stage set uses M-112K033 / L-406.40DG10 / M-116.DG / M-406.4PD; V5 uses L-509 series. Default for mesoSPIM v4–v6 (ZMB/USZ/HIFO sites).
   * - **PI (N controllers → N axes)**
     - ``'PI_NcontrollersNstages'``
     - One PI controller per axis (e.g. C-663, one stage per controller). mesoSPIM v5 option.
   * - **PI (rot+Z) + Galil (X,Y,F)**
     - ``'PI_rotz_and_Galil_xyf'``
     - PI C-884 drives rotation (M-061.PD) and Z (M-406.4PD); Galil DMC drives X/Y/F (Ethernet or serial). Used in mesoSPIM H45 geometry (HIFO), currently deprecated.
   * - **ASI Tiger / MS2000**
     - ``'TigerASI'``
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
     - ``'Demo'``
     - Simulation.
   * - **Ludl 96A350 (single)**
     - ``'Ludl'``
     - 32 mm, 10 positions (0–9; Ludl position 10 = index 0). Large filter wheel with separate MAC6000 controller, serial cable. mesoSPIM v4–v6 at ZMB/USZ/H45 sites. Supports **dual-wheel** mode: set two Ludl wheels, use tuples ``(pos_wheel1, pos_wheel2)`` as filter positions.
   * - **Sutter Lambda 10**
     - ``'Sutter'``
     - 25 mm, 10 positions. Serial communication; configurable baud rate and wheel speed. Deprecated (used in early versions).
   * - **ZWO EFW-MINI**
     - ``'ZWO'``
     - 31 mm, 5 positions (0–4). Compact, low-cost astronomy filter wheel with integrated USB controller. mesoSPIM Benchtop and v6. Requires ``pyzwoefw`` bindings.

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
     - Mitutoyo motorized objective-turret revolver. Baudrate **9600**; positions A–E map to objective magnifications (e.g. 2×/5×/7.5×/10×/20×). Used in mesoSPIM v6 (ZMB) and some Benchtop setups.

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
     - One DO line per laser (see ``laserdict`` in :doc:`configuration`). Analog modulation via AO lines on the same card.
   * - **NI cDAQ digital enable**
     - ``'cDAQ'``
     - CompactDAQ version (e.g. ``cDAQ1Mod2``). Used with the cDAQ waveform-generation backend.

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
   * - **NI cDAQ**
     - ``'cDAQ'``
     - CompactDAQ digital output shutter (e.g. ``/cDAQ1Mod1/port0/line2``). Used with the cDAQ waveform-generation backend.

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
   * - **NI PXI/PCIe (AO) — classic**
     - ``'NI'``
     - Two-card system: PXI6259 (galvo/ETL AO + shutter DO) + PXI6733 (laser AO + DO). Classic mesoSPIM v4–v5 (ZMB, USZ, H45). Single-card variants also work (e.g. PXI1Slot4 for Benchtop; PXI1Slot2 at UCL).
   * - **NI CompactDAQ chassis**
     - ``'cDAQ'``
     - USB/Ethernet cDAQ chassis with NI-9401 (digital) and NI-9264 (analog) modules; see ``config_benchtop-cDAQ.py`` example. Note: concurrent-task limits apply (≤ 1 DO, 1 AO, 4 counters).

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
