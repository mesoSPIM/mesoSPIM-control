# Remote Control call list

TCP and MCP provide the same 84 calls. The call names and behavior are identical on both
transports.

Before changing the microscope, call `get_manual` and `get_limits`. Ordinary changes return an
accepted or rejected reply. After acceptance, poll `get_progress` until the operation is completed,
stopped or failed.

For connection details, arguments, polling, and errors, see the
[Remote Control manual](index.md).

## Read and inspect

| Call | Purpose |
| --- | --- |
| `hello` | Return basic application, protocol, and state information. |
| `ping` | Check that the server responds. |
| `get_state` | Read the main microscope settings. |
| `get_position` | Read the current stage position. |
| `get_state_all` | Read selected or all state fields. |
| `get_config` | Read configured lasers, filters, zooms, axes, camera size, and image writers. |
| `get_info` | Read detailed microscope and Remote Control information. |
| `get_limits` | Read the limits currently enforced by Remote Control. |
| `get_capabilities` | Read the available calls, axes, the states Core can report, and fields. |
| `get_manual` | Read the built-in usage guide and generated command list. |
| `get_snapshot` | One compact readout of the whole microscope: state, position, optics, camera, list, disk, warnings. |
| `get_frame` | The last displayed frame as numbers (exposure, focus, signal position) and a small PNG. |
| `get_progress` | Read acquisition progress and the latest operation. |
| `self_test` | Check configured limits without moving hardware. |
| `get_acquisition_list` | Read the current acquisition list. |
| `stat_files` | Check whether supplied files exist and read their sizes. |
| `get_disk_space` | Read free and required disk space for acquisitions. |
| `check_motion_limits` | Check acquisition positions against stage limits. |

## Move and stop

| Call | Purpose |
| --- | --- |
| `move_absolute` | Move selected axes to absolute positions. |
| `move_relative` | Move selected axes by relative distances. |
| `zero` | Set the current position of selected axes to zero. |
| `unzero` | Restore physical coordinates after zeroing selected axes. |
| `stop` | Stop stage movement. |
| `stop_activity` | Stop live mode, an acquisition or a time lapse. |
| `clear_stuck_operation` | Release a safely verified lost-completion operation. |
| `open_shutters` | Open the shutters. |
| `close_shutters` | Close the shutters, including during another operation. |

## Change settings

| Call | Purpose |
| --- | --- |
| `set_state` | Change supported microscope state fields. |
| `set_filter` | Select a configured filter. |
| `set_zoom` | Select a configured zoom. |
| `set_laser` | Select a configured laser. |
| `set_intensity` | Set laser intensity. |
| `set_shutterconfig` | Select a configured shutter arrangement. |
| `set_camera` | Change supported camera settings. |
| `set_etl` | Change supported ETL settings. |
| `set_galvo` | Change supported galvo settings. |
| `set_laser_timing` | Change supported laser timing settings. |
| `reload_etl_config` | Reload an ETL configuration file. |
| `update_etl_from_laser` | Load ETL values for a selected laser. |
| `update_etl_from_zoom` | Load ETL values for a selected zoom. |
| `save_etl_config` | Save ETL settings to the current file. |

## Start modes and position the sample

| Call | Purpose |
| --- | --- |
| `start_live` | Start live mode. |
| `start_visual_mode` | Start visual mode. |
| `start_lightsheet_alignment_mode` | Start light-sheet alignment mode. |
| `snap` | Capture one frame and save it, as the GUI's Snap does, to the snap folder or a named one; the operation result gives the path. |
| `load_sample` | Move to the configured sample-load position. |
| `unload_sample` | Move to the configured sample-unload position. |
| `center_sample` | Move to the configured sample-center position. |

## Acquire and run time lapses

| Call | Purpose |
| --- | --- |
| `set_acquisition_list` | Validate and install an acquisition list. |
| `run_acquisition_list` | Run the installed acquisition list. |
| `run_selected_acquisition` | Run one selected acquisition-list row. |
| `preview_acquisition` | Preview one acquisition-list row. |
| `acquire_start` | Start one supplied acquisition. |
| `acquire_finish` | Restore the list saved by `acquire_start`. |
| `time_lapse_start` | Start a time lapse using the installed list. |
| `time_lapse_stop` | Stop the time-lapse schedule. |

## Edit the acquisition list

What the acquisition manager's buttons and wizards do. Each call builds the whole new list and
installs it as `set_acquisition_list` does, with the same checks.

| Call | Purpose |
| --- | --- |
| `update_acquisition_row` | Change named keys of one row; the rest stays. |
| `add_acquisition_rows` | Add rows, a default one or copies of a row, at a position. |
| `delete_acquisition_rows` | Delete rows; the list keeps at least one. |
| `move_acquisition_row` | Move a row to another position. |
| `mark_acquisition_rows` | Give rows the instrument's current position, rotation, focus, ETL or settings. |
| `save_acquisition_list` | Save the list as a CSV file. |
| `load_acquisition_list` | Replace the list with one saved as CSV. |
| `name_acquisition_rows` | Name every row by an image writer's rules, as the filename wizard does. |
| `track_focus` | Set each row's focus range on the line through two (z, focus) points. |
| `build_tiling_list` | Replace the list with the tiling wizard's grid of tiles and channels. |
| `set_snap_folder` | Choose the folder snaps are saved to. |

## Change what the windows show

These calls change only what mesoSPIM's windows show, never the instrument, so they are never
refused as busy and work during a run too. A change returns a request number at once and the
window applies it a moment later; `get_display` with that number says when. Positions are in the
camera frame's own pixels (x the column, y the row, as `get_frame` gives the frame) and in um.

| Call | What it does |
| --- | --- |
| `get_display` | Read what the windows show: the camera window's levels, lookup table, overlay, view and regions of interest (with their size and offset from the frame's centre), the contrast map, the tile overview, the main window's tab, status message, progress bars and time-lapse estimate, the acquisition table's grouping, selection and estimates, and which windows are open. |
| `set_display` | Set what a window shows: in the camera and contrast windows the levels, a lookup table by name or by its colours, the histogram's range, the region on screen, inverted axes, the image view's own ROI and its profile, and normalisation; in the camera window also Adjust levels, the overlay, the box and line regions of interest and the frame of an opened stack; the tile overview's scale and scroll; the main window's tab. |
| `set_windows` | Open, close and cascade windows, as the View menu and their close buttons do. |
| `get_picture` | A picture of a window as it is on screen, returned as PNG or saved to a file. |
| `open_image_file` | Open a TIFF image or stack in the camera window, as File > Open TIFF. |
| `set_table_view` | Select rows of the acquisition table and group it by laser, by illumination or by the selected rows. |

## The windows' own instrument features

What only a window offers, as calls. They change the instrument, so they are ordinary operations
under the busy gate; the toggles and the optimizer are carried out by the window itself.

| Call | What it does |
| --- | --- |
| `get_writer_parameters` | Read an image writer's own settings, as the filename wizard's Writer parameters page shows them. |
| `set_writer_parameters` | Set an image writer's settings for this session (OME-Zarr chunks, compression, shards, ...). |
| `get_processor_chain` | Read the processors there are, with their parameters, and the chain applied to images. |
| `set_processor_chain` | Set the whole processor chain, as the Processor Chain window's Apply does, and optionally save it. |
| `set_alignment_toggles` | The ETL tab's AmpL=0, AmpR=0 and Freeze galvos. |
| `optimize` | Run the optimizer (AUTO Focus, Launch Optimizer) over focus or an ETL, within a region of interest. |
| `finish_optimization` | Accept or discard the optimizer's result. |
| `save_parameters_to_config` | Save the Parameters tab into the config file, as Save config file does. |
| `auto_illumination` | Light each tile from the left or right by its X position, as Auto L/R illumination does. |

## Analyse image files

The Utils menu's tools, as calls. mesoSPIM runs these tools as programs of their own; they read
files and never touch the instrument, so the calls are never refused as busy. Each returns a
request number at once and runs in the background; `get_display` with that number gives the result.

| Call | What it does |
| --- | --- |
| `analyse_psf` | PSF (beads) analysis of a TIFF z-stack: each bead's lateral and axial FWHM, and their median and spread. |
| `analyse_field_curvature` | Field curvature / chromatic shift of one or more TIFF z-stacks: depth of field, sag, best plane and a best-focus map per channel, with a reference channel's tilt subtracted if asked. |
