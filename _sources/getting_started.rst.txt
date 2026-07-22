Getting Started
===============

This page gets you from zero to a running mesoSPIM-control session in demo
mode — no physical hardware required.

Prerequisites
-------------

* **OS**: Windows 7 or later, 64-bit
* **Python**: 3.12 (we recommend `Miniforge <https://github.com/conda-forge/miniforge>`_
  and its ``mamba`` package manager)

.. note::

   The Anaconda distribution is not recommended due to its changed terms of
   service.  If you already have Anaconda, replace ``mamba`` with ``conda``
   in every command below.

Step 1 — Clone the repository
------------------------------

Clone (or download) this repository into a convenient location, for example::

   C:/Users/Public/mesoSPIM-control

Using **GitHub Desktop** is the easiest option.  Alternatively, download and
unpack the ZIP archive from the GitHub releases page.

.. image:: https://user-images.githubusercontent.com/10835134/198991579-df1e5acc-d246-425b-a345-03ba93a1f0bb.png
   :alt: GitHub Desktop clone dialog
   :width: 60%

Step 2 — Create a Python environment
--------------------------------------

Open a **Miniforge prompt** and run::

   mamba create -p C:/Users/Public/mamba/envs/mesoSPIM-py312 python=3.12
   mamba activate C:/Users/Public/mamba/envs/mesoSPIM-py312

Step 3 — Install dependencies
-------------------------------

::

   cd C:/Users/Public/mesoSPIM-control
   pip install -r requirements-conda-mamba.txt

Step 4 — Launch in demo mode
------------------------------

From the Miniforge prompt::

   cd C:/Users/Public/mesoSPIM-control/mesoSPIM
   python mesoSPIM_Control.py -D

The ``-D`` flag enables **demo mode**, replacing every hardware device with a
software simulator so you can explore the full GUI without any connected
equipment.

What's next?
------------

.. list-table::
   :widths: 30 70
   :header-rows: 0

   * - :doc:`installation`
     - Install device drivers and set up a real hardware system.
   * - :doc:`configuration`
     - Write a config file that maps to your specific hardware.
   * - :doc:`user_guide`
     - Learn the GUI, acquisition modes, and scripting interface.
   * - :doc:`hardware`
     - See all supported cameras, stages, filter wheels, and lasers.