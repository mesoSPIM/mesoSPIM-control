# mesoSPIM-control
Image acquisition software for [mesoSPIM](http://mesospim.org/) light-sheet microscopes. A mesoSPIM (mesoscale selective plane illumination microscope) is optimized for fast imaging of large (many cm³) cleared tissue samples at near-isotropic resolution. Currently, more than 10 mesoSPIM setups are operational [around the world](http://mesospim.org/setups/).

Parts lists, drawings, and instructions for building a mesoSPIM can be found in the [mesoSPIM wiki](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation).

## Overview
The mesoSPIM is a versatile light-sheet microscope for imaging
cleared tissue samples. It is compatible with all major clearing approaches - including CLARITY - and optimized for quickly creating large-field-of-view overview datasets of whole mouse brains.

## Installation

### :warning: Warning
If you are updating `mesoSPIM-control` from a previous version: Please have a close look at the [Changelog](CHANGELOG.md) to avoid overwriting your configuration files.

### Prerequisites
* Windows 7 or Windows 10
* Python >=3.6

#### Device drivers
* [Hamamatsu DCAM API](https://dcam-api.com/) when using Hamamatsu Orca Flash 4.0 V2 or V3 sCMOS cameras. To test camera functionality, [HCImage](https://dcam-api.com/hamamatsu-software/) can be used.
* [PVCAM and PVCAM-SDK](https://www.photometrics.com/support/software/) when using Photometrics cameras (under development). In addition, the `PyVCAM` Python package is necessary ([Link](https://github.com/Photometrics/PyVCAM)).
* [Software for Physik Instrumente stages](https://www.physikinstrumente.com/en/products/motion-control-software/) if a PI stage is used. To test the stages, PI MicroMove can be used. 
* [Software for Steinmeyer Mechatronics / Feinmess stages using Galil drivers](http://www.galilmc.com/downloads/api) if such a stage is used. To test the stages, GalilTools can be used.
* [Robotis DynamixelSDK](https://github.com/ROBOTIS-GIT/DynamixelSDK/releases) for Dynamixel Zoom servos. Make sure you download version 3.5.4 of the SDK.

#### Python
mesoSPIM-control is usually running with [Anaconda](https://www.anaconda.com/download/) using a >=3.6 Python. 
##### Anaconda 
(optional) Create and activate a Python 3.6 environment from Anaconda prompt:
```
conda create -n py36 python=3.6
conda activate py36
```
The step above is optional because the latest Python 3.8 is backward compatible with Python 3.6 code.

Many libraries are already included in Anaconda. 
Install mesoSPIM-specific libraries: 
```
pip install requirements-anaconda.txt
```

##### Clean python 
For a clean (non-Anaconda) python interpreter, install all required libraries: 
```
pip install requirements-clean-python.txt
```

##### Additional libraries
Camera libraries are not hosted on PyPi and need to be installed manually:
* [PyVCAM when using a Photometrics camera](https://github.com/Photometrics/PyVCAM)
* pco (`python -m pip install pco`) when using a PCO camera ([Link](https://pypi.org/project/pco/)). A Version ≥0.1.3 is recommended.

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
The software will now start. If you have multiple configuration files you will be prompted to choose one. 

For testing, you can use demo mode:
```
python mesoSPIM_Control.py -D
```

Or select a "demo" file using the UI selector, should you have more than in your configuration directory. 

You may also run the software with an interactive iPython console for de-bugging:
```
python mesoSPIM_Control.py -C
```
For example, executing `mSpim.state.__dict__` in this console will show the current mesoSPIM state. 

##### Troubleshooting
If there are problems with PyQt5 such as `ModuleNotFoundError: No module named 'PyQt5.QtWinExtras` after starting 
`mesoSPIM-control`, try reinstalling PyQt5 by: `python -m pip install --user -I PyQt5` and `python -m pip install --user -I PyQt5-sip`)

#### Documentation for users
For instructions on how to use mesoSPIM-control, please check out the documentation [here](https://github.com/mesoSPIM/mesoSPIM-powerpoint-documentation).
