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

### Device drivers
#### Cameras
* Hamamatsu Orca Flash 4.0 V2/V3 camera: [Hamamatsu DCAM API](https://dcam-api.com/). To test camera functionality, [HCImage](https://dcam-api.com/hamamatsu-software/) can be used.
* Photometrics camera: [PVCAM and PVCAM-SDK](https://www.photometrics.com/support/software/). 
In addition, the `PyVCAM` Python package is required ([github](https://github.com/Photometrics/PyVCAM)), 
which depends on ¨[MS Visual C++ 14.0 or higher](https://visualstudio.microsoft.com/visual-cpp-build-tools/). 
When installing the MS Visual C++ tools, make sure to check [C++ build tools](https://docs.microsoft.com/en-us/answers/questions/136595/error-microsoft-visual-c-140-or-greater-is-require.html)
* PCO camera: `pco` python library (`python -m pip install pco`). A Version ≥0.1.3 is recommended.

#### Stages
* PI stages: [Software for Physik Instrumente stages](https://www.physikinstrumente.com/en/products/motion-control-software/). To test the stages, PI MicroMove can be used. 
* Steinmeyer Mechatronics / Feinmess stages: [Software for using Galil drivers](http://www.galilmc.com/downloads/api) if such a stage is used. To test the stages, GalilTools can be used.
* ASI stages: [ASI Tiger drivers](http://www.asiimaging.com/support/downloads/tiger-controller-console/). 
If using USB connection, check ASI instructions on [USB support](http://www.asiimaging.com/support/downloads/usb-support-on-ms-2000-wk-controllers/)
#### Zoom servo
* Dynamixel servos: [Robotis DynamixelSDK](https://github.com/ROBOTIS-GIT/DynamixelSDK/releases). Make sure you download version 3.5.4 of the SDK.

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


#### Prepare a configuration file and wire the NI DAQ
The configuration files are in the `config` directory.
The "demo" files have some devices replaced with `Demo` devices for testing purposes.
Start with demo config file to make sure installation went successfully.
Then change the `Demo` devices to your hardware, set their parameters, and test each device.
See [Wiki](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file) for details.

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


