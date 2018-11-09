# mesoSPIM
Code and documentation for the mesoSPIM light-sheet microscope

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
* For PI stages, copy `PI_GCS2_DLL_x64.dll` in the main mesoSPIM folder: `PI_GCS2_DLL_x64.dll`
* For Galil stages, copy `gclib.py` into `mesoSPIM/src/devices/stages/galil/gclib/gclib.py`
* For zoom control via dynamixel servos, copy the dynamixel Python file `dynamixel_functions.py` into `mesoSPIM/src/devices/zoom/dynamixel/`

#### Prepare a configuration file

#### Run the software.
```
python mesoSPIM_Control.py
```
After launch, it will prompt you for a configuration file. Please choose a file
with demo devices (e.g. `DemoStage`) for testing.
