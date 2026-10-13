"""One reviewed valid example and dispatch classification for every API command."""
import os
import tempfile

# The files and folders the table and folder calls name: a folder that exists, a list saved in it.
FOLDER = tempfile.mkdtemp(prefix="mesospim_contracts_")
SAVED_LIST = os.path.join(FOLDER, "saved.csv")
with open(SAVED_LIST, "w", newline="") as _file:
    _file.write("z_start,z_end,z_step,planes\n0,0,1,1\n")
IMAGE_FILE = os.path.join(FOLDER, "image.tif")       # what open_image_file opens: a TIFF that exists
with open(IMAGE_FILE, "wb") as _file:
    _file.write(b"II*" + bytes(1))

VALID_CASES = {
    "hello": {},
    "ping": {},
    "get_state": {},
    "get_position": {},
    "get_state_all": {"keys": ["state", "intensity"]},
    "get_config": {},
    "get_info": {},
    "get_limits": {},
    "get_capabilities": {},
    "get_manual": {},
    "get_progress": {},
    "get_snapshot": {},
    "get_frame": {"max_size": 256},
    "self_test": {},
    "move_absolute": {"targets": {"x": 100}},
    "move_relative": {"deltas": {"x": -1}},
    "zero": {"axes": ["x"]},
    "unzero": {"axes": ["x"]},
    "stop": {},
    "stop_activity": {},
    "clear_stuck_operation": {},
    "set_state": {"settings": {"intensity": 25}},
    "set_filter": {"filter": "Empty", "wait": True},
    "set_zoom": {"zoom": "1x", "wait": True, "update_etl": False},
    "set_laser": {"laser": "488 nm", "wait": True, "update_etl": False},
    "set_intensity": {"intensity": 25, "wait": True},
    "set_shutterconfig": {"shutterconfig": "Left"},
    "set_camera": {"camera_exposure_time": 0.02},
    "set_etl": {"etl_l_amplitude": 1.0},
    "set_galvo": {"galvo_l_frequency": 100.0},
    "set_laser_timing": {"laser_l_delay_%": 10.0},
    "reload_etl_config": {"path": "etl.csv", "wait": True},
    "update_etl_from_laser": {"laser": "488 nm", "wait": True},
    "update_etl_from_zoom": {"zoom": "1x", "wait": True},
    "open_shutters": {},
    "close_shutters": {},
    "start_live": {},
    "start_visual_mode": {},
    "start_lightsheet_alignment_mode": {},
    "snap": {"prefix": "remote"},
    "load_sample": {},
    "unload_sample": {},
    "center_sample": {},
    "save_etl_config": {},
    "get_acquisition_list": {},
    "set_acquisition_list": {
        "acquisitions": [
            {
                "z_start": 0,
                "z_end": 0,
                "z_step": 1,
                "planes": 1,
            }
        ],
        "selected_row": 0,
    },
    "run_acquisition_list": {},
    "run_selected_acquisition": {"row": 0},
    "preview_acquisition": {"row": 0, "z_update": True},
    "acquire_start": {
        "acquisition": {
            "folder": "tmp",
            "filename": "valid.tif",
            "z_start": 0,
            "z_end": 0,
            "z_step": 1,
            "planes": 1,
            "laser": "488 nm",
            "intensity": 10,
            "filter": "Empty",
            "zoom": "1x",
            "shutterconfig": "Left",
        }
    },
    "stat_files": {"files": []},
    "acquire_finish": {},
    "get_disk_space": {},
    "check_motion_limits": {},
    "time_lapse_start": {"timepoints": 1, "interval_sec": 0},
    "time_lapse_stop": {},
    "update_acquisition_row": {"row": 0, "changes": {"z_end": 10}},
    "add_acquisition_rows": {"rows": [{"z_start": 0, "z_end": 0, "z_step": 1}]},
    "delete_acquisition_rows": {"rows": [1]},
    "move_acquisition_row": {"row": 0, "to": 0},
    "mark_acquisition_rows": {"rows": [0], "marks": ["state"]},
    "save_acquisition_list": {"path": os.path.join(FOLDER, "list.csv"), "overwrite": True},
    "load_acquisition_list": {"path": SAVED_LIST},
    "name_acquisition_rows": {"writer": "Tiff_Writer", "description": "sample"},
    "track_focus": {"z_1": 0, "f_1": 1000, "z_2": 100, "f_2": 1100},   # f within the fake's 0..98000
    "build_tiling_list": {"x_start": 0, "x_end": 1000, "y_start": 0, "y_end": 0, "z_start": 0, "z_end": 20,
                          "z_step": 10, "channels": [{"laser": "488 nm", "intensity": 10, "filter": "Empty"}],
                          "folder": FOLDER, "writer": "Tiff_Writer"},
    "set_snap_folder": {"folder": FOLDER},
    # the windows (gui_handles)
    "get_display": {},
    "set_display": {"levels": [100, 3000]},
    "set_windows": {"show": ["tile_overview"]},
    "get_picture": {"window": "camera"},
    "open_image_file": {"path": IMAGE_FILE},
    "set_table_view": {"group": "none"},
    # the windows' own instrument features (gui_handles)
    "get_writer_parameters": {"writer": "OME_Zarr_Writer"},
    "set_writer_parameters": {"writer": "OME_Zarr_Writer", "parameters": {"compression_level": 3}},
    "get_processor_chain": {},
    "set_processor_chain": {"processors": [{"name": "GaussianBlur", "config": {"sigma": 2.0}}]},
    "set_alignment_toggles": {"freeze_galvo": True},
    "optimize": {"mode": "focus", "range": 300},
    "finish_optimization": {"accept": False},
    "save_parameters_to_config": {"path": os.path.join(FOLDER, "saved_config.py"), "overwrite": True},
    "auto_illumination": {},
    # the Utils menu's analyses of files
    "analyse_psf": {"path": IMAGE_FILE},
    "analyse_field_curvature": {"channels": [{"path": IMAGE_FILE}]},
}

# What a call's valid example needs installed first: delete keeps at least one row.
SETUP = {"delete_acquisition_rows": lambda core: core.state.__setitem__("acq_list", [{}, {}])}

# The calls on mesoSPIM's windows (gui_handles): no Core call, a request to the GUI thread's handles.
WINDOW_CALLS = {"get_display", "set_display", "set_windows", "get_picture", "open_image_file", "set_table_view",
                "analyse_psf", "analyse_field_curvature"}
# The windows' own instrument features: no Core call; the toggles and the optimizer are operations the
# GUI thread carries out.
GUI_OPERATIONS = {"set_alignment_toggles", "optimize", "finish_optimization"}
WINDOW_FEATURE_CALLS = GUI_OPERATIONS | {"get_writer_parameters", "set_writer_parameters", "get_processor_chain",
                                         "set_processor_chain", "save_parameters_to_config", "auto_illumination"}

# The calls that edit the acquisition table: each installs through set_acquisition_list, no Core call.
TABLE_CALLS = {"update_acquisition_row", "add_acquisition_rows", "delete_acquisition_rows", "move_acquisition_row",
               "mark_acquisition_rows", "save_acquisition_list", "load_acquisition_list", "name_acquisition_rows",
               "track_focus", "build_tiling_list", "set_snap_folder"}

EXPECTED_CORE_CALL = {
    "move_absolute": "move_absolute",
    "move_relative": "move_relative",
    "zero": "zero_axes",
    "unzero": "unzero_axes",
    "stop": "sig_stop_movement",
    "set_state": "state_request_handler",
    "set_filter": "set_filter",
    "set_zoom": "set_zoom",
    "set_laser": "set_laser",
    "set_intensity": "set_intensity",
    "set_shutterconfig": "set_shutterconfig",
    "set_camera": "state_request_handler",
    "set_etl": "state_request_handler",
    "set_galvo": "state_request_handler",
    "set_laser_timing": "state_request_handler",
    "reload_etl_config": "sig_state_request_and_wait_until_done",
    "update_etl_from_laser": "sig_state_request_and_wait_until_done",
    "update_etl_from_zoom": "sig_state_request_and_wait_until_done",
    "open_shutters": "open_shutters",
    "close_shutters": "close_shutters",
    "start_live": "set_state",
    "start_visual_mode": "set_state",
    "start_lightsheet_alignment_mode": "set_state",
    "snap": "snap",
    "load_sample": "move_absolute",
    "unload_sample": "move_absolute",
    "center_sample": "move_absolute",
    "save_etl_config": "sig_save_etl_config",
    "run_acquisition_list": "start",
    "run_selected_acquisition": "start",
    "preview_acquisition": "preview_acquisition",
    "acquire_start": "start",
    "get_disk_space": "get_free_disk_space",
    "check_motion_limits": "check_motion_limits",
    "time_lapse_start": "run_time_lapse",
    "time_lapse_stop": "stop_time_lapse",
}

READ_ONLY_WITHOUT_CORE_CALL = {
    "hello",
    "ping",
    "get_state",
    "get_position",
    "get_state_all",
    "get_config",
    "get_info",
    "get_limits",
    "get_capabilities",
    "get_manual",
    "get_progress",
    "get_snapshot",
    "get_frame",
    "self_test",
    "get_acquisition_list",
    "stat_files",
    "stop_activity",
    "clear_stuck_operation",  # EMERGENCY, makes no Core call (frees the gate only if core is idle)
}

OPERATIONAL_COMMANDS = set(EXPECTED_CORE_CALL) | {
    "set_acquisition_list",
    "stop_activity",
} | TABLE_CALLS

CALL_COUNT = 84
assert len(VALID_CASES) == CALL_COUNT
assert len(OPERATIONAL_COMMANDS) == 49
