# Remote Control call list

TCP and MCP provide the same 53 calls. The call names and behavior are identical on both
transports.

Before changing the microscope, call `get_manual` and `get_limits`. Ordinary changes return an
accepted or rejected reply. After acceptance, poll `get_progress` until the operation is completed
or failed.

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
| `get_config` | Read configured lasers, filters, zooms, axes, and camera size. |
| `get_info` | Read detailed microscope and Remote Control information. |
| `get_limits` | Read the limits currently enforced by Remote Control. |
| `get_capabilities` | Read the available calls, axes, modes, and fields. |
| `get_manual` | Read the built-in usage guide and generated command list. |
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
| `stop_activity` | Stop live or acquisition activity. |
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
