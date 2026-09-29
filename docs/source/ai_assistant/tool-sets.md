# The two tool sets

What the assistant may do in each tool set. **Full** is every command; **Regular**, the default,
is Full minus the right-hand column: the Parameters tab of the main window (camera, laser timing,
galvos, the ETL's delays and ramps) and the two alignment modes stay with the operator. A command
in both sets is the same tool in both, except `set_etl`, which in Regular takes the four voltages
only. The set is chosen in the tab's setup box, or per microscope with the config attribute
`ai_assistant_tools`; TCP and MCP always serve every command.

| Area | Regular (and Full) | Full only |
|---|---|---|
| Reads and checks | hello, ping, get_state, get_state_all, get_position, get_config, get_info, get_limits, get_capabilities, get_progress, get_snapshot, get_frame, self_test, get_acquisition_list, stat_files, get_disk_space, check_motion_limits | — |
| Sample and stage | move_absolute, move_relative, load_sample, unload_sample, center_sample, zero, unzero | — |
| Optics for the session | set_laser, set_intensity, set_filter, set_zoom, set_shutterconfig, open_shutters, close_shutters | — |
| ETL | set_etl (amplitude and offset only), reload_etl_config, update_etl_from_laser, update_etl_from_zoom, save_etl_config | set_etl's delay and ramps |
| Camera | — | set_camera (exposure, delay, pulse, binning, display subsampling) |
| Galvos and laser timing | — | set_galvo, set_laser_timing |
| Seeing | snap, look, ask_eyes (with a model that sees), start_live, stop_activity, stop, clear_stuck_operation | start_visual_mode, start_lightsheet_alignment_mode |
| Acquiring | set_acquisition_list, update_acquisition_row, run_acquisition_list, run_selected_acquisition, preview_acquisition, acquire_start, acquire_finish, time_lapse_start, time_lapse_stop | — |
| Anything by name | — | set_state (the generic setting call) |
| Memory | recall_turn, search_history | — |
| Time | schedule, cancel_schedule | — |

Regular offers 49 commands plus `look`, `ask_eyes` when the model can see, the two memory tools
and the two schedule tools; Full 55 plus the same. A
command not in the set is not offered to the model at all, so it cannot be talked into it; the
model is told which set it runs with and what that set leaves out, so a request for one gets
"not in this tool set" rather than a stand-in.

The sets are defined in `mesoSPIM_AiAssistent_Config.py` (`TOOL_PROFILES`, `REGULAR_ARGS`);
`test_ai_assistent.py` checks that Regular offers and withholds what this page says.
