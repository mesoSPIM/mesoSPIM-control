[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6109315.svg)](https://doi.org/10.5281/zenodo.6109315)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Static Badge](https://img.shields.io/badge/user_forum-image.sc-blue)](https://forum.image.sc/tag/mesospim)

# mesoSPIM-control

Python/PyQt acquisition software for [mesoSPIM](http://mesospim.org/) light-sheet microscopes.
Compatible with all official mesoSPIM hardware generations (Benchtop, v4, v5) and many custom configurations.

> **Full documentation:** https://mesospim.github.io/mesoSPIM-control/

## Quick start

```bash
# 1. Clone the repository
#    (GitHub Desktop recommended, or download the ZIP)

# 2. Create and activate a conda/mamba environment
mamba create -p C:/Users/Public/mamba/envs/mesoSPIM-py312 python=3.12
mamba activate C:/Users/Public/mamba/envs/mesoSPIM-py312

# 3. Install dependencies
cd C:/Users/Public/mesoSPIM-control
pip install -r requirements-conda-mamba.txt

# 4. Launch in demo mode (no hardware required)
cd mesoSPIM
python mesoSPIM_Control.py -D
```

For full installation instructions, device drivers, desktop shortcut setup, and hardware configuration see the **[Installation](https://mesospim.github.io/mesoSPIM-control/installation.html)** and **[Configuration](https://mesospim.github.io/mesoSPIM-control/configuration.html)** pages.

## Documentation

| Page | Description |
|---|---|
| [Getting Started](https://mesospim.github.io/mesoSPIM-control/getting_started.html) | First-run guide — clone, install, demo mode |
| [Installation](https://mesospim.github.io/mesoSPIM-control/installation.html) | Device drivers, conda env, desktop shortcut |
| [Configuration](https://mesospim.github.io/mesoSPIM-control/configuration.html) | Config file reference for all hardware |
| [User Guide](https://mesospim.github.io/mesoSPIM-control/user_guide.html) | GUI walkthrough, acquisition modes, scripting |
| [Supported Hardware](https://mesospim.github.io/mesoSPIM-control/hardware.html) | Cameras, stages, filter wheels, DAQ cards |
| [Changelog](https://mesospim.github.io/mesoSPIM-control/changelog.html) | Release notes |

## Hardware builds

Parts lists, drawings, and assembly instructions for building a mesoSPIM:
- [Benchtop mesoSPIM](https://github.com/mesoSPIM/benchtop-hardware)
- [mesoSPIM v4/v5](https://github.com/mesoSPIM/mesoSPIM-hardware-documentation)

More than 30 setups are operational [around the world](http://mesospim.org/setups/).

## Community

- [image.sc forum](https://forum.image.sc/tag/mesospim) — questions and discussion
- [YouTube channel](https://www.youtube.com/c/mesoSPIM) — tutorials and demos
- [Mailing list](http://eepurl.com/hPBRhj) — announcements
- [ZMB Dozuki guides](https://zmb.dozuki.com/c/Lightsheet_microscopy#Section_MesoSPIM) — start-up and acquisition walkthroughs

## How to cite

Fabian F. Voigt, Nikita Vladimirov, Christian Schulze, Rob Campbell, & Fritjof Helmchen. (2022). *MesoSPIM control: An open-source acquisition software for light-sheet microscopy written in Python and Qt.* Zenodo. https://doi.org/10.5281/zenodo.6109315

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.6109315.svg)](https://doi.org/10.5281/zenodo.6109315)
