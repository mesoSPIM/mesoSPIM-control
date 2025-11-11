[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6109315.svg)](https://doi.org/10.5281/zenodo.6109315)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Static Badge](https://img.shields.io/badge/user_forum-image.sc-blue)](https://forum.image.sc/tag/mesospim)


# mesoSPIM-control
Image acquisition software for [mesoSPIM](http://mesospim.org/) light-sheet microscopes. Compatible with all official versions of mesoSPIM hardware (Benchtop, v4, v5), and multple alternative configurations.

## Overview
The mesoSPIM (mesoscale selective plane illumination microscope) is a family of versatile open-source microscopes optimized for fast imaging of large (many cm³) cleared tissue samples at near-isotropic resolution. 
Currently, more than 30 mesoSPIM setups are operational [around the world](http://mesospim.org/setups/).
Parts lists, drawings, and instructions for building a mesoSPIM can be found in the wiki pages:
- [Benchtop mesoSPIM](https://github.com/mesoSPIM/benchtop-hardware)
- [mesoSPIM v4-5](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation)

The `mesoSPIM-control` is python-based acquisition software with user-friendly GUI, based on PyQt5 framework.

## Installation

### Prerequisites
* Windows >=7, 64-bit
* Python >=3.12, we recommend [Miniforge](https://github.com/conda-forge/miniforge) and `mamba` package manager that comes with it. The Anaconda distribution is not recommended since the change of its terms of service in 2020. If you have existing Anaconda installation, you can still use `conda` instead of `mamba` in the instructsions below.

### Device drivers
#### National Instruments DAQ devices
Download and install the latest [NI DAQmx drivers](https://www.ni.com/en/support/downloads/drivers/download.ni-daq-mx.html) with default parameters.
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

### Installation steps 
1. Clone this repository either by via GitHub Desktop (recommended) or by downloading and unpacking the ZIP file into folder `C:/Users/Public/mesoSPIM-control`

![image](https://user-images.githubusercontent.com/10835134/198991579-df1e5acc-d246-425b-a345-03ba93a1f0bb.png)

2. Open Miniforge prompt, create and activate a new environment `mesoSPIM-py312`:
```
mamba create -p C:/Users/Public/mamba/envs/mesoSPIM-py312 python=3.12
mamba activate C:/Users/Public/mamba/envs/mesoSPIM-py312
```
3. Install mesoSPIM-specific libraries: 
```
cd C:/Users/Public/mesoSPIM-control
pip install -r requirements-conda-mamba.txt
```

## Launching

### Miniforge prompt
1. `cd C:/Users/Public/mesoSPIM-control/mesoSPIM`
2. `python mesoSPIM_Control.py` (with argument `-D` for demo mode)

### Desktop shortcut (fast launch)
From Miniforge prompt, type `where mamba`, and enter the result (e.g. `C:\Users\Nikita\miniforge3\Scripts\activate.bat`) into line 10 of `mesoSPIM.bat` file:
```
"%windir%\System32\cmd.exe" /k ""C:\Users\Nikita\miniforge3\Scripts\activate.bat" "C:\Users\Public\conda\envs\mesoSPIM-py312" && python "mesoSPIM_Control.py""
```
Save changes and double-click the `mesoSPIM.bat` file - this should launch the control software. If this does ot happen, check the Anaconda path. Once this works, create a shortcut and place it on your desktop for quick launching.  

## Prepare a configuration file and wire the hardware
The config files are stored in the `mesoSPIM/config` directory. 
The newly installed software will launch with the `demo_config.py`, 
which has all external hardware replaced with `Demo` simulated devices, to make sure installation is successful in "dry run".

If you have multiple config files you will be prompted to choose one that corresponds to your hardware. 

Once your hardware is connected and turned on, change the `Demo` devices to hardware-specific names, set their parameters, and test each device.
See [Wiki](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation/wiki/mesoSPIM_configuration_file) for details.

## Updating existing installation
To ensure safe transition to a new version, we recommend fresh installation of each new version into a separate folder (e.g. `mesoSPIM-control-Jan2025`) using the steps above. In order to unlock all new features, please review and add new sections from the [demo config file](/mesoSPIM/config/demo_config.py) to your old configuration file.

## Troubleshooting
Some errors during software startup and acquisition can be displayed in the mamba/conda terminal, while a highly detailed log will be recorded in the time-stamped file in `mesoSPIM/log` folder. This log file is individual for each session, named by date and time of software start-up, eg `mesoSPIM/log/20241210-154845.log`.

## Further resources
For instructions on how to use mesoSPIM-control, please check out the documentation:
* ZMB (Univerity of Zurich) guides on [mesoSPIM start-up, setting up, and acquisition](https://zmb.dozuki.com/c/Lightsheet_microscopy#Section_MesoSPIM)
* [PPT](https://github.com/mesoSPIM/mesoSPIM-powerpoint-documentation) (outdated version), 
* youtube [channel](https://www.youtube.com/c/mesoSPIM), 
* subscribe to our [mailing list](http://eepurl.com/hPBRhj).
* join the discussion at the [image.cs user forum](https://forum.image.sc/tag/mesospim) (since August 2025)


## How to cite this software
Fabian F. Voigt, Nikita Vladimirov, Christian Schulze, Rob Campbell, & Fritjof Helmchen. (2022). MesoSPIM control: An open-source acquisition software for light-sheet microscopy written in Python and Qt. Zenodo. https://doi.org/10.5281/zenodo.6109315

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6109315.svg)](https://doi.org/10.5281/zenodo.6109315)
