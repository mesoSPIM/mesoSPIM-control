Overview of the mesoSPIM code
=============================

Basic overview
--------------

* the main entry point into the program is ``mesoSPIM_control.py``, it prompts for a
  configuration file upon startup and initializes the ``mesoSPIM_MainWindow``
* ``mesoSPIM_MainWindow`` spawns the following threads:

  * ``mesoSPIM_Core``, the main thread

    * in turn, the core spawns the following threads:

      * ``mesoSPIM_Camera``
      * ``mesoSPIM_Serial``

    * Scripts are executed in the context of the core

  * ``mesoSPIM_AcquisitionPlanner`` which is a window with an
    editable table allowing the creation of multidimensional acquisitions
  * ``mesoSPIM_CameraGUI``, the camera window (using `pyqtgraph <http://pyqtgraph.org/>`_)

Multithreading and signal exchange
----------------------------------
