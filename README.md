# mesoSPIM-control
Code and documentation for the mesoSPIM light-sheet microscope software.
The documentation of the microscope hardware information can be found [here](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation).

## Overview
The Swiss mesoSPIM is a versatile light-sheet microscope for imaging
cleared tissue samples. It is compatible with all major clearing approaches - including CLARITY - and optimized for quickly creating large-field-of-view overview datasets of whole mouse brains.

## Installation

### Prerequisites
* Windows 7 or Windows 10
* Python >3.6

#### Device drivers
* [Hamamatsu DCAM API](https://dcam-api.com/) when using Hamamatsu Orca Flash 4.0 V2 or V3 sCMOS cameras. To test camera functionality, [HCImage](https://dcam-api.com/hamamatsu-software/) can be used.
* [Software for Physik Instrumente stages](https://www.physikinstrumente.com/en/products/motion-control-software/) if a PI stage is used. To test the stages, PI MicroMove can be used.
* [Software for Steinmeyer Mechatronics / Feinmess stages using Galil drivers](http://www.galilmc.com/downloads/api) if such a stage is used. To test the stages, GalilTools can be used.
* [Robotis DynamixelSDK](https://github.com/ROBOTIS-GIT/DynamixelSDK/releases) for Dynamixel Zoom servos. Make sure you download version 3.5.4 of the SDK.

#### Python
mesoSPIM-control is usually running with [Anaconda](https://www.anaconda.com/download/) using a >3.6 Python. For a clean python install, the following packages are necessary (part of Anaconda):

* csv
* traceback
* pprint
* numpy
* scipy
* ctypes
* importlib
* PyQt5

In addition (for Anaconda), the following packages need to be installed:
* nidaqmx (`python -m pip install nidaqmx`)
* indexed (`python -m pip install indexed.py`)
* serial (`python -m pip install pyserial`)
* pyqtgraph  (`python -m pip install pyqtgraph`)
* pywinusb  (`python -m pip install pywinusb`)
* PIPython (part of the Physik Instrumente software collection. Unzip it, `cd` to the directory with the Anaconda terminal as an admin user, then install with `python setup.py install`. Test install with  test installation with `import pipython`)

#### Preparing python bindings for device drivers
* For PI stages, copy `C:\ProgramData\PI\GCSTranslator\PI_GCS2_DLL_x64.dll` in the main mesoSPIM folder: `PI_GCS2_DLL_x64.dll`
* For Galil stages, copy `gclib.py` into `mesoSPIM/src/devices/stages/galil/gclib/gclib.py`
* For zoom control via dynamixel servos, copy the dynamixel Python file `dynamixel_functions.py` into `mesoSPIM/src/devices/zoom/dynamixel/` You will also need to edit this file to point to the correct Dynamixel dll. You could copy these files into the `zoom/dynamixel` folder to keep things neatly in one place.

#### Prepare a configuration file and wire the NI DAQ
The configuration files are in the `config` directory.
The "demo" files have some devices replaced with dummy devices for testing purposes.
You can start with one of those if you wish or proceed directly to a non-demo config file.
Choose one of the ZMB config files as appropriate and work through each section, filling it out for your hardware:

* You can rename your DAQ devices in NI MAX to match the names in the config file (PXI6259 and PXI6733).
* The `master_trigger_out_line` should be connected to the line which serves as the trigger source for the camera and the galvo/etl task.
At time of writing that means the master trigger out (`PXI6259/port0/line1`) should be connected to `PXI6259/PFI0`.
* On Toptica lasers, analog line 1 is the longest wavelength and line 4 is the shortest wavelength.
Use BNC T connectors to split each analog output line to both lasers.
* You will need to set the ThorLabs shutter controllers to run on TTL input mode.

#### Run the software.
```
python mesoSPIM_Control.py
```
After launch, it will prompt you for a configuration file. Please choose a file
with demo devices (e.g. `DemoStage`) for testing.

#### Documentation for users
For instructions on how to use mesoSPIM-control, please check out the documentation [here](https://github.com/mesoSPIM/mesoSPIM-powerpoint-documentation).
