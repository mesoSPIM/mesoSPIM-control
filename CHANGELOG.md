## Release candidate [1.9.0]
### User Interface :lollipop:
- :gem:  "Auto L/R illumination" button in the Acquisition manager to select tile illumination based on its x-position.
- :gem: A long awaited feature: **Tile Overview** window (*View/Open Tile Overview*), showing the entire acquisition area with tile positions, their overlap, and current FOV position relative to them.
    - Some setups need to flip x- and/or y-stage polarity for correct tile display: use `'flip_XYZFT_button_polarity': (True, False, False, False, False),` in the config file.
- :gem: Center Button added in the Main Window GUI, for bringing the sample holder in the X- and Z- center relative to the light-sheet and detection objective.
- during acqusition, the currently acquiring row is highlighted in **Acquisition Manager** and in **Tile Overview** windows. 
This has to be set up in the config file with `'x_center_position'` and `'z_center_position'` parameters for stage motion.
- Buttons for movement in horizontal plane got shorter, for more intuitive navigation.
- Current FPS shown in the progress bar.
- Webcam window always opens at startup, empty if no camera is present in config file: `'usb_webcam_ID': 0, # open USB web-camera (if available): None,  0 (first cam), 1 (second cam), ...`
- Tooltips were added to the navigation buttons.

### Bugfixes :bug: 
- occasional glitch with ASI stages caused by updating stage positions between acquisitions, with serial communication going in two separate threads (mainWindow vs Core).
- check motion limits for all tiles before starting the acquisition list, in absolute or relative coodinates (zeroed axes or not).
- estimated remaining acquisition time is now calculated correctly, based on the current frame rate.
- sample centering and objectiv exchange positions work also when in zeroed-stage regime (local coordinates, user-defined). No need to inactivate `Zero F-stage` button for safe revolver operation.

## Release February 2024 [1.8.3]

### User Interface :lollipop:
:gem: Light-sheet direction is shown in the camera window as an image overlay. It interactively changes depending on the Left/Right/Both arms illimination state.

### Hardware control :wrench:
- Support of Mitutoyo 5-position objective turret (revolver, part #378-726D), for mesoSPIM v4-5 [upgrade](https://github.com/mesoSPIM/benchtop-hardware/tree/main/v4-5-upgrade-2023).
- Safety movement of the focus stage backward to `f_objective_exchange` position for motorized objective exchange. The `f_objective_exchange` parameter is defined in the config file.
- Optional buffering of images into RAM and flushing to disk when RAM is full or the stack is finished, [PR#72](https://github.com/mesoSPIM/mesoSPIM-control/pull/72) by [@AlanMWatson](https://github.com/AlanMWatson). Controlled by adding `buffering` dictionary to the config file.
- support of ZWO 2" 7-position filterwheel support (PR#79 by Fabian Voigt)
- checks and warnings for AO maximum voltage range (5V or 10V, which depends on hardware, but can be damaging if not set correctly).

### Bugfixes :bug: 
- incorrect focus stage steps when interpolating between two focus positions in a stack. Reported and tested by Ivana Gantar and Laura Batti (Wyss Center Geneva). Affected small-amplitude focus interpolation, where required F-stage steps between planes were smaller than minimum feasible stage step. The minimum feasible stage step changed from 0.1 to 0.25 µm in function `get_focus_stepsize_generator(self, f_stage_min_step_um=0.25)`.
- no more dropped frames during long acquisitions with slow disks.

## Release January 2023 [1.8.2]
### Hardware control 
- New filter wheel [ZWO EFWmini](https://astronomy-imaging-camera.com/product/efw-mini) supported
- added `'speed'` config parameter for ASI Tiger controller that allows to change default speed settings.
- more [config examples](https://github.com/mesoSPIM/mesoSPIM-control/tree/master/mesoSPIM/config/examples) from various systems were uploaded.

### User interface
- official [mesoSPIM logo](https://github.com/mesoSPIM/mesoSPIM-control/tree/master/mesoSPIM/gui/mesoSPIM-logo.png) is uploaded, also for use as desktop icon (mesoSPIM-logo.ico)
- non-relevant ETL settings are grayed out depending on the left/right illumination to minimize confusion during ETL optimization (#71).
- for slow stages the **Move** buttons can be set to sleep for *N* ms to limit the click frequency from the user (prevent stage runout): paremeter `'button_sleep_ms_xyzft' : (250, 0, 250, 0, 0),` in the [config file](https://github.com/mesoSPIM/mesoSPIM-control/blob/master/mesoSPIM/config/demo_config.py).
- file names now include magnification and rotation (if several rotations are present)
- GUI allows to change `scale_galvo_amp_with_zoom` flag interactively,
- developer-only GUI sections have smaller font and are marked as such,
- **STOP Stages** button is big red.

### Bug fixes
- tile translation metadata in XML/H5 data were transposed in some configurations (x-y)
- `'etl_l_delay_%'` config parameter was updated to avoid edge artifacts in ETL scanning
- in auto-focus optimization pipeline, the first image of the sequence was incorrect


## Release November 2022 [1.8.1]
### Hardware control
:sparkles: Galvo amplitude can be automatically rescaled depending on selected zoom. 
Add `scale_galvo_amp_with_zoom = True` to config file to enable this feature.

:wrench: Galvo and ETL of non-active arm are held still to minimize unnecessary heating and stress.

:gem: Optional webcam window can be opened (e.g. for sample overview)

### Logging and data management
:wrench: Logging can be defined in config file using `logging_level = 'DEBUG'` parameter (possible values `INFO`,`DEBUG`).

:wrench: Log messages are printed in `Log` tab for quick review, in addition to the log file.

:gem: BigTIFF file support

### User interface
:wrench: User is forced to select clearing-specific ETL parameters file (e.g. `ETL-CLARITY-cuvette40x40.csv`) at the startup, to avoid non-optimal default settings (often forgotten step).

:gem: `Acquisition Manager` shows estimated dataset size (GB) before acquisition to help planning data management.

:gem: Disk space check: if the disk has insufficient free space, acquisition does not start (shows error message).

:sparkles: New icon for the desktop shortcut.

:gem: Optional `Image Contrast` window can be opened from Alignment Tab (for calibration purposes)

:wrench: Multi-tile wizard can have up to 4 channels (previously max: 3).

:wrench: Version management can now be done using PyPi: `pip install mesospim-control`. 
Control software can be launched in Anaconda prompt from any folder, by `mesospim-control` command. 
Beware that installation path is determined by Anaconda and can be deep (inconvenient). Feature for developers.

:gem: Stage position indicators turn red if stage is within 1 mm from software limits.

:gem: `Main Window > View > Cascade windows` to bring all windows to screen center (for small screens).

:wrench: Config file simplified, redundant blocks removed (`galvo_etl_designation`, `laser_designation`), warnings are issued if deprecated blocks are present.

:wrench: Remove F-stage homing to `startfocus` position, since it added overhead (manual focusing) every time the software was restarted.

### Bug fixes

:bug: laser lines were hard-coded `0:7`, irrespective of config file settings.

:bug: PI stage did not send position updates properly due to missing signal/slot connection: stages were frequently stuck outside of allowed range.

:bug: Image and metadata files are closed properly if the acquisition is aborted.

:bug: `npy2bdv` was creating XML files unreadabla for Imaris, due to extra spaces between affine transofmration matrix values. 
Fixed in `npy2bdv==1.0.8`, upgrade via `pip install -U npy2bdv`.

### Benchtop hardware support
:gem: All DAQ waveforms can be generated by a single NI-6733 card (up to 4 laser lines).

:gem: ASI Tiger stage controller, with TTL triggering option.

:gem: Photometrics Iris 15 camera

:gem: Arm switching / shutter control by `shutterswitch` parameter in config file.

:gem: DIY filter wheel, driven by Dynamixel servo (same model as V5 zoom servo)

:bug: fix: ASI Tiger communication issues resolved, multithreading simplified.

## Release November 2021 [1.7.1]
:sparkles: TIFF file name pattern for multi-tile/channel datasets is fully compatible with BigStitcher auto-loader, no renaming is needed.

:bug: fix: Files must always have extension (currently one of `.tiff`, `.tif`, `.raw`, `.h5`). Files without extension return an error.

:warning: Default file format for data saving has changed to `.h5` for streamlined import into BigStitcher.

:gem: :gem: :gem: Autofocus has been added and works beautifully, outperforming expert human in focusing accuracy by 10x. Highly recommended!

:bug: fix: Going back to previously configured channel in the `Tiling Manager` appended a new channel to the acquisition list, rather than amending it. 

:sparkles: Laser intensity can be edited directly via spinbox, alternative to slider. 
  In Acquisition manager, slider is replaced by a spinbox for convenience. 
  :warning: This change makes old acq tables incompatible with the new software.

:sparkles: `Mark All` button is added to the Acquisition Manager, per @raacampbell request.

:recycle: Buttons `Mark Rotation Position` and `Go To Rotation Position` are removed from the main panel, 
since they are redundant and rarely (if ever) used. Rotation position can be marked in the Acquisition Manager, 
and one can go to rotation position by using increment buttons.

:bug: fixed: Image processing option generates MAX projections as TIFF files when output file format is either `.raw` or `.tiff`, #60.

:sparkles: File name wizard auto-starts after Tiling Wizard.

:gem: Image sharpness metric of user-defined ROI (by DCTS algorithm) is added to the Camera Window for easier adjustment of focus and ETL values.

:gem: TIFF files can be opened for preview: `Ctrl + O`.

:gem: Button `Freeze galvos` is added to ETL tab for quick adjustment of ETL parameters outside of sample, see [video tutorial](https://www.youtube.com/watch?v=dcJ9a7VALi8).

:warning: Recommended Python upgrade to 3.7 because some libraries have limited support for 3.6 (e.g. `tifffile`).

:gem: :gem: Saving datasets as ImageJ TIFF files, including big ones (Fiji TIFF format that allows > 4 GB size). Voxel dimension saved in TIFF metadata.

## Release July 2021 [1.6.0]
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
