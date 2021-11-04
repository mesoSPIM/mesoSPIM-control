# mesoSPIM-control
Image acquisition software for [mesoSPIM](http://mesospim.org/) light-sheet microscopes. A mesoSPIM (mesoscale selective plane illumination microscope) is optimized for fast imaging of large (many cm³) cleared tissue samples at near-isotropic resolution. Currently, more than 10 mesoSPIM setups are operational [around the world](http://mesospim.org/setups/).

Parts lists, drawings, and instructions for building a mesoSPIM can be found in the [mesoSPIM wiki](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation).

## Overview
The mesoSPIM is a versatile light-sheet microscope for imaging
cleared tissue samples. It is compatible with all major clearing approaches - including CLARITY - and optimized for quickly creating large-field-of-view overview datasets of whole mouse brains.

## Installation

### :warning: Warning
If you are updating `mesoSPIM-control` from a previous version: 
please add new sections from the [demo config file](/mesoSPIM/config/demo_config.py) 
to your old configuration file in order to unlock all new features.

### Prerequisites
* Windows 7 or Windows 10, 64-bit
* Python >=3.7 (3.7 is preferred, but the code is compatible with 3.6)

#### Device drivers
* [Hamamatsu DCAM API](https://dcam-api.com/) when using Hamamatsu Orca Flash 4.0 V2 or V3 sCMOS cameras. To test camera functionality, [HCImage](https://dcam-api.com/hamamatsu-software/) can be used.
* [PVCAM and PVCAM-SDK](https://www.photometrics.com/support/software/) when using Photometrics cameras (under development). In addition, the `PyVCAM` Python package is necessary ([Link](https://github.com/Photometrics/PyVCAM)).
* [Software for Physik Instrumente stages](https://www.physikinstrumente.com/en/products/motion-control-software/) if a PI stage is used. To test the stages, PI MicroMove can be used. 
* [Software for Steinmeyer Mechatronics / Feinmess stages using Galil drivers](http://www.galilmc.com/downloads/api) if such a stage is used. To test the stages, GalilTools can be used.
* [Robotis DynamixelSDK](https://github.com/ROBOTIS-GIT/DynamixelSDK/releases) for Dynamixel Zoom servos. Make sure you download version 3.5.4 of the SDK.

#### Python
mesoSPIM-control is usually running with [Anaconda](https://www.anaconda.com/download/) using a >=3.7 Python. 
##### Anaconda 
(optional) Create and activate a Python 3.7 environment from Anaconda prompt (you can use any name instead of `py37`):
```
conda create -n py37 python=3.7
conda activate py37
```
The step above is optional but recommended, to avoid conflicts if some libraries already exist or will be changed in the default environment.
This helps keep your mesoSPIM-dedicated python environment clean and stable.

Many libraries are already included in Anaconda. 
Install mesoSPIM-specific libraries: 
```
pip install -r requirements-anaconda.txt
```

##### Clean python 
For a clean (non-Anaconda) python interpreter, install all required libraries: 
```
pip install -r requirements-clean-python.txt
```

##### Additional libraries
Camera libraries are not hosted on PyPi and need to be installed manually:
* [PyVCAM when using a Photometrics camera](https://github.com/Photometrics/PyVCAM)
* pco (`python -m pip install pco`) when using a PCO camera ([Link](https://pypi.org/project/pco/)). A Version ≥0.1.3 is recommended.

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

## Launching
#### From Anaconda prompt
```
conda activate py37
python mesoSPIM_Control.py
```
The software will now start. If you have multiple configuration files you will be prompted to choose one. 

#### From start_mesoSPIM.bat file
Open the `start_mesoSPIM.bat` file in text editor and configure Anaconda and `py37` path to your own. 
Once done, launch mesoSPIM by double-clicking the file. 
Optionally, create a Windows shortcut (via right-click menu) and place it e.g. on your desktop. 
Using shortcut saves a lot of time for users.

#### Starting in demo mode
```
python mesoSPIM_Control.py -D
```

## Troubleshooting
If there are problems with PyQt5 such as `ModuleNotFoundError: No module named 'PyQt5.QtWinExtras` after starting 
`mesoSPIM-control`, try reinstalling PyQt5 by: `python -m pip install --user -I PyQt5` and `python -m pip install --user -I PyQt5-sip`)

## Documentation for users
For instructions on how to use mesoSPIM-control, please check out the documentation:
* [PPT](https://github.com/mesoSPIM/mesoSPIM-powerpoint-documentation), 
* youtube [channel](https://www.youtube.com/channel/UCeZqIhsh8j9wUhtbLJ73wbQ), 
* subscribe to our mailing [list](mailto:mesospim-jedi+subscribe@googlegroups.com).

If you have questions, contact the current core developer [Nikita Vladimirov](mailto:vladimirov@hifo.uzh.ch).


