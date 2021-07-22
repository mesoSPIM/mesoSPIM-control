# Latest changes
:bug: Image processing option generates MAX projections as TIFF files when output file format is either `.raw` or `.tiff`, #60.

:sparkles: File name wizard auto-starts after Tiling Wizard.

:gem: Image sharpness metric of user-defined ROI (by DCTS algorithm) is added to the Camera Window for easier adjustment of focus and ETL values.

:gem: TIFF files can be opened for preview: `Ctrl + O`.

:gem: Button `Freeze galvos` is added to ETL tab for quick adjustment of ETL parameters outside of sample, see [video tutorial](https://www.youtube.com/watch?v=dcJ9a7VALi8).

:warning: Upgrade Python to 3.7 because some libraries have limited support for 3.6 (e.g. `tifffile`).

:gem: writing to ImageJ TIFF files, including > 4 GB in size. Voxel dimension saved in TIFF.
This feature requires upgrade to Python 3.7 due to dependence from `tifffile` library.

## Release July 2021 [0.1.6]
:gem: Simplified installation and upgrading via `pip install -r requirements-anaconda.txt`. See [installation instructions](https://github.com/mesoSPIM/mesoSPIM-control#python).

:gem: Easy launching via double-clicking `start_mesoSPIM.bat` file (needs to be configured by the user).

:gem: Support of multiple PI single-axis controllers, thanks to #52 by @drchrisch. 
Note the changes in config file: single multi-axis controller (C-884) is initialized by `'PI_1controllerNstages'`, 
while multiple single-axis controllers (C-663) by `'PI_NcontrollersNstages'`.

:bug: Incorrect tiling count (off by -1 in some cases) is fixed.

### [0.1.5] 
* :gem: Improved Tiling Wizard: 
    * buttons `x-start, x-end, y-start, y-end` added for easier navigation: 
    no need to search for corners of imaginary box around the sample. 
    * `left, then right` illuminations can be created automatically for each tile: no need for manual duplication 
    and changing the illumination directions in the Acquisition Manager.
    
* :gem: Improved saving options in Fiji/BigStitcher H5 format:
     * `laser`, `illumination`, `angle` attributes are saved in the BigStitcher XML file.
     * (optional) downsampling and compression are supported.
* :gem: Image window got `Adjust levels` button for automatic intensity adjustment.
* :gem: Image window got optional `Box overlay` to help measure sample dimensions.
* :mag: Tests for tiling and serial communication are created.
* :bug: **Bugfix:** long-standing `permission denied` issues with serial communication 
to filter wheel and zoom servo are fixed.
The fix opens serial ports once and keeps them open during the session.
The root cause was due to laser control software polling serial ports regularly, thus blocking access to them.

### [0.1.4] 
* :warning: **Config files need to be updated** Please note: Updating to this version requires updating your microscope configuration file. Please copy the new configuration options from the `demo_config.py` file into your config files.
* :warning: :gem: **New handling of config files** - If there is a single config file (without a 'demo' prefix in the filename and apart from the `demo_config.py`-file) in the config folder, the software will automatically load this file. Otherwise, the config selection GUI is opened. This is especially helpful when operating a mesoSPIM with multiple users. Thanks to @raacampbell for this feature! 
* :gem: **New: Writing HDF5** - If all rows in the acquistion manager contain the same file name (ending in `.h5`), the entire acquisition list will be saved in a single hdf5 file and a XML created automatically. Both can then be loaded into [Bigstitcher](https://imagej.net/BigStitcher) for stitching & multiview fusion. This file format is also readable by Imaris. For this, the `npy2bdv` package by @nvladimus needs to be installed via pip.
* :gem: **New: Dark mode** - If the `dark_mode` option in the config file is set to `True`, the user interface appears in a dark mode. For this, the `qdarkstyle` package needs to be installed via `python -m pip install qdarkstyle`.
* :gem: **New: Camera and Acquisition Manager Windows can be reopened** - A new menu allows the camera and acquisition manager windows to be reopened in case they get closed. The same menu bar allows exiting the program as well.
* :gem: **New: Disabling arrow buttons** - To allow mesoSPIM configurations with less than 5 motorized stages, the arrow buttons in the main window can now be disabled in the configuration file. Typical examples are a mesoSPIM without a rotation stage or a mesoSPIM using only a single motorized z-stage. This feature can also be useful if the serial connection to the stages is too slow and pressing the arrow buttons leads to incorrect movements. 
* :gem: **Interactive IPython console** - If the software is launched via `python mesoSPIM-control.py -C`, an interactive IPython console is launched for debugging. Feature by @raacampbell.
* :gem: **Command-line demo mode option** - If the software is launched via `python mesoSPIM-control.py -D`, it launches automatically into demo mode. Feature by @raacampbell.
* :gem: **New: Support for PCO cameras** - PCO cameras with lightsheet mode are now supported. For this the `pco` Python package needs to be installed via `python -m pip install pco`. Currently, the only tested camera is the PCO panda 4.2 bi with lightsheet firmware.
* :gem: **New: Support for Sutter Lambda 10B Filter Controller** Thanks to Kevin Dean @AdvancedImagingUTSW, Sutter filter wheels are now supported.
* :gem: **New: Support for Physik Instrumente stepper motor stages in a XYZ configuration** Thanks to @drchrisch, a mesoSPIM configuration ('PI_xyz') using stepper motor stages for sample movement is now supported. Please note that this is currently not supporting focus movements or sample rotations.
* :gem: **New: Support for Physik Instrumente C-863 controller in a single-stage config** To allow setting up a simplified mesoSPIM using only a single motorized z-stage (all other stages need to be manually operated), the combination of the C-863 motor controller and L-509 stage is now supported ('PI_z')
* :sparkles: **Improvement:** **Disabling movement buttons in the GUI** By modifying the `ui_options` dictionary in the configuration file, the X,Y,Z, focus, rotation, and load/unload buttons can be disabled. This allows modifing the UI for mesoSPIM setups which do not utilize the full set of 5 axes. Disabled buttons are greyed out.
* :sparkles: **Improvement:** **Updated multicolor tiling wizard** The tiling wizard now displays the FOV size and calculates the X and Y FOV offsets using a percentage setting. For this, the pixel size settings in the configuration file need to be set correctly.
* :sparkles: **Improvement:** **Physik Instrumente stages now report their referencing status after startup in the logfile** This allows for easier diagnosis of unreferenced stages during startup. Feature by @raacampbell.
* :bug: **Bugfix:** Binning was not working properly with all cameras.
* :bug: **Bugfix:** Removed unnecessary imports.
* :bug: **Bugfix:** Laser power setting `max_laser_voltage` was always 10V, ignoring the config file. This can damage some lasers that operate on lower command voltage.

## Release March 13, 2020 [0.1.3]
* :warning: **Depending on your microscope configuration, this release breaks backward compatibility with previous configuration files. If necessary, update your configuration file using `demo_config.py` as an example.**
* :warning: **There are new startup parameters in the config file - make sure to update your config files accordingly**. For example, `average_frame_rate` has been added.
* :warning: **This release removes unnecessary configuration files from the public repository - make sure to back up your mesoSPIM & ETL configuration files beforehand. In addition, old example acquisition tables (in `mesoSPIM-control\mesoSPIM\acquisitions\`) are removed as well.** 
* :gem: **New: Support for more cameras**: **Photometrics** cameras are now supported if `PyVCAM` and the PVCAM-SDK are installed. Only the Iris 15 has been tested so far. In addition, the **Hamamatsu Orca Fusion** is now supported.
* :gem: **New: Multicolor tiling wizard**: The Tiling wizard can now support up to 3 color channels with different ETL parameters and focus tracking settings.
* :gem: **New: Full demo mode - addresses #16**: `mesoSPIM-control` can now be run without any microscope hardware by using the `demo_config.py` configuration file. 
* :gem: **New: Snap function** -- Single pictures can now be taken by clicking the snap button. The filename is autogenerated from the current time. Files are saved as `.tif` which requires `tifffile` as an additional library.
* :gem: **New: Acquisition time prediction** -- `mesoSPIM-control` now measures the average framerate every 100 frames to predict the acquisition time. To have a correct initial estimate 
in the `Acquisition Manager`, please update the `average_frame_rate` with the measured values 
from your microscope (are now logged in the metadata files after an acquisition).
* :gem: **New: Focus tracking** -- Different start and end focus positions can now be specified in the Acquisition Manager. When moving the sample to acquire the stack, the microscope changes focus according to a linear interpolation between these values. At z_start, the microscope moves the detection path 
to f_start and at z_end, the detection path focus is at z_end. This allows imaging a liquid-filled sample cuvette without an immersion cuvette. The `Mark current focus` button changes both values at once. 
* :gem: **New: Improved acquisition previews** -- An additional checkbox allows to switch off Z axis movements when previewing acquisitions. This way, the field-of-view does not move outside of the sample which is especially helpful when updating ETL value for individual tiles/stacks in large acquisition tables. :warning: When previewing an acquistion requires a rotation, z movements still occur for safety reasons. 
* :gem: **New: Image Processing Wizard**: `mesoSPIM-control` now has an Image Processing Wizard (accessible via a button in the `Acquisition Manager`). Currently, this allows maximum projections to be generated automatically after acquisitions.  
* :sparkles: **Improvement:** `Acquisition Manager`: Naming of buttons has been improved, in addition, **tooltips** have been added to improve usability. 
* :sparkles: **Improvement:** Removed unnecessary microscope and ETL configuration files cluttering the repository. Changed `.gitignore` correspondingly - future changes to configuration files. This addresses issue #16.
* :sparkles: **Improvement:** The software now provides more verbose warnings when acquisitions cannot be started due to missing folders, duplicated filenames and already existing files.
* :sparkles: **Improvement:** Better warnings if no row is selected while clicking Mark buttons.
* :sparkles: **New:** Added a `CHANGELOG.md` file
* :bug: **Bugfix:** Manually entering a value in a field in the Acquisition Manager table would change values in other rows as well if the row had been copied before.
* :bug: **Bugfix:** Mark buttons and dropdown menus in the Acquisition Manager table slowed down the GUI when a lot of rows (>25) were present. As a fix, only the selected row shows the menu.
* :bug: **Bugfix #26:** Fixed: First row is selected by mark buttons by default if only a single row exists in the Acquisition Manager Table
* :bug: **Bugfix #27:** Fixed: Entering text into boxes is a bit buggy
* :bug: **Bugfix #30:** Fixed: Zooming drop down menu often fails to update after a zoom
* :bug: **Bugfix #31:** Fixed: `demo_config.py` now contains subsampling settings
* :bug: **Bugfix #34:** Fixed: Last frame in a stack is blank due to an off-by-one error
* :bug: **Bugfix #35:** Fixed: Software crashes when one folder (to save data in) in the acquisition list does not exist

## Release August 19th, 2019 [0.1.2]
* **New:** Logging is now supported. Logfiles go in the `log` folder. 
* **New:** Improved support for a specific mesoSPIM configuration using sample & focusing stages by Steinmayer Mechantronik and in combination with PI stages for sample rotation and z-movement.
* **Fix:** Reduced the output to the command line
* **Fix:** To decrease laggyness of the GUI in live mode and during acquisitions, display subsampling is now available. This way, less image data has to be rendered by the GUI. 
* **Fix:** Fixed a variety of multithreading bugs.
* **Fix:** Galvo amplitude and frequency in the startup part of the configuration file are now used to set startup parameters properly

## Contributors 
* Fabian Voigt (@ffvoigt)
* Nikita Vladimirov (@nvladimus)
* Kevin Dean (@AdvancedImagingUTSW)
* Christian Schulze (@drchrisch)
* Rob Campbell (@raacampbell)
