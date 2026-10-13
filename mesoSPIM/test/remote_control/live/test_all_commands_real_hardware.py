"""Opt-in REAL-HARDWARE sweep of every mesoSPIM Remote Control command through the SINGLE bound
transport (MCP or TCP, chosen by MESOSPIM_LIVE_REAL_TRANSPORT; a session hosts one transport).

This is the real-hardware counterpart to test_all_commands.py, which refuses to run against
anything but a DemoStage. This file is the opposite: it refuses to run against a DemoStage (use
the other file for that) and is gated behind a distinct, explicit confirmation string because it
drives a real instrument. Excluded from normal CI.

The sweep's one aim is to show that every call has an effect, not to exercise the instrument: each
change is small, is checked by reading it back, and is put back. One full sweep, on the attached
hardware:
  - moves the stage on X by at most 25 um (absolute) and 10 um (relative) from where it is, and back;
  - sweeps the focus by +-20 um in 5 snaps for the optimizer (AUTO Focus), then discards its result,
    so the focus is where it was;
  - sets the laser intensity to 1-2 % (MESOSPIM_REAL_LASER_PERCENT, 0 to 10, default 1) before any
    light: live, visual and alignment mode are entered briefly and stopped, single frames are snapped,
    and single-plane acquisitions run at that intensity onto whatever is under the objective;
  - changes filter, zoom, laser, shutter side, exposure, one ETL, galvo and laser-timing value one
    step each, and restores them;
  - turns Freeze galvos on and off, applies a Gaussian blur to the processor chain and removes it,
    changes the OME-Zarr writer's compression level one step and back, and changes the camera
    window's levels and the contrast window's visibility and back;
  - opens a small test stack in the camera window (the next frame replaces it) and analyses test
    stacks it writes itself (PSF, field curvature);
  - points mesoSPIM at a copy of the ETL calibration file, saves into the copy, and points it back:
    the real ETL file is never written;
  - writes acquisition lists, a config copy and test files into a temporary folder, and puts the
    operator's acquisition list back.
Load, unload and centre sample travel to the positions in the microscope's config, which can be far:
they are skipped and reported as not run unless MESOSPIM_REAL_LARGE_MOVES=1, for an empty stage.

An operator must be physically present and watching the instrument for the whole run. If the
process is killed mid-sweep, the finally-block cleanup will not run: check the stage position, the
laser intensity, Freeze galvos, the processor chain, the ETL file in use and the acquisition list by
hand before trusting the instrument again.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.parse

import pytest

from mesoSPIM.test.remote_control.support.clients import RemoteControl
from mesoSPIM.test.remote_control.support.contracts import (OPERATIONAL_COMMANDS, TABLE_CALLS, VALID_CASES, WINDOW_CALLS,
                                                            WINDOW_FEATURE_CALLS)
from mesoSPIM.test.remote_control.support.live_session import bounded_delta as _bounded_delta
from mesoSPIM.test.remote_control.support.live_session import demo_acquisition as _build_acquisition
from mesoSPIM.test.remote_control.support.live_session import different as _different
from mesoSPIM.test.remote_control.support.live_session import must as _must
from mesoSPIM.test.remote_control.support.live_session import network_timeout as _network_timeout
from mesoSPIM.test.remote_control.support.live_session import raw_mcp_tool as _raw_tool
from mesoSPIM.test.remote_control.support.live_session import raw_tcp_tool as _raw_tcp_tool
from mesoSPIM.test.remote_control.support.live_session import wait_for_operation as _wait_for_operation
from mesoSPIM.test.remote_control.support.live_session import wait_for_result as _wait_for_result
from mesoSPIM.test.remote_control.support.live_session import wait_until as _wait_until
from mesoSPIM.test.remote_control.support.live_session import write_test_stacks as _write_test_stacks


pytestmark = pytest.mark.live_real_all

TOTAL = len(VALID_CASES)
OPERATIONAL = len(OPERATIONAL_COMMANDS)

_CONFIRM_TOKEN = "I_UNDERSTAND_THIS_MOVES_REAL_HARDWARE"

# The largest changes the sweep makes: enough to read back, small enough for a sample in place.
MOVE_UM = 25                # move_absolute on X, from where the stage is
RELATIVE_MOVE_UM = 10       # move_relative on X
OPTIMIZER_RANGE_UM = 20     # the optimizer's focus sweep, either side
OPTIMIZER_POINTS = 5
LARGE_TRAVEL = ("load_sample", "unload_sample", "center_sample")   # to the config's positions: opt-in


def _real_config():
    required = {
        "MESOSPIM_ALLOW_DEVICE_CHANGE": "1",
        "MESOSPIM_OPERATOR_PRESENT": "1",
        "MESOSPIM_RUN_REAL_ALL_COMMANDS": "1",
    }
    for name, expected in required.items():
        if os.environ.get(name) != expected:
            pytest.skip(f"set {name}={expected} to permit the real-hardware sweep")

    if os.environ.get("MESOSPIM_CONFIRM_REAL_HARDWARE") != _CONFIRM_TOKEN:
        pytest.skip(
            f"set MESOSPIM_CONFIRM_REAL_HARDWARE={_CONFIRM_TOKEN} - this sweep moves the stage and the "
            "focus by a few tens of um, fires the laser at 1-2 % for brief live views, snaps and "
            "single-plane acquisitions, and changes and restores settings one step each; read this "
            "file's module docstring before setting it"
        )

    url = os.environ.get("MESOSPIM_LIVE_MCP_URL", "http://127.0.0.1:42100/mcp")
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.path != "/mcp"
        or parsed.port is None
    ):
        raise ValueError("live tests require a loopback http:// MCP URL ending in /mcp")

    hold = float(os.environ.get("MESOSPIM_REAL_COMMAND_HOLD_SECONDS", "0.25"))
    if not 0 <= hold <= 1:
        raise ValueError("MESOSPIM_REAL_COMMAND_HOLD_SECONDS must be between 0 and 1")

    laser_percent = float(os.environ.get("MESOSPIM_REAL_LASER_PERCENT", "1"))
    if not 0 <= laser_percent <= 10:
        raise ValueError("MESOSPIM_REAL_LASER_PERCENT must be between 0 and 10")

    large_moves = os.environ.get("MESOSPIM_REAL_LARGE_MOVES") == "1"
    return (parsed.hostname, parsed.port, os.environ.get("MESOSPIM_LIVE_MCP_TOKEN"), hold, _network_timeout(),
            laser_percent, large_moves)


def test_live_real_hardware_all_commands_are_functional_safe_and_restored(request):
    host, port, token, hold, request_timeout, laser_percent, large_moves = _real_config()
    transport = os.environ.get("MESOSPIM_LIVE_REAL_TRANSPORT", "mcp").lower()
    if transport == "mcp":
        if not token:
            pytest.skip("set MESOSPIM_LIVE_MCP_TOKEN for the live MCP server")
        def tool(name, arguments=None):
            return _raw_tool(host, port, token, request_timeout, name, arguments)
    elif transport == "tcp":
        tcp_host = os.environ.get("MESOSPIM_LIVE_TCP_HOST", "127.0.0.1")
        tcp_port = os.environ.get("MESOSPIM_LIVE_TCP_PORT")
        tcp_token = os.environ.get("MESOSPIM_LIVE_TCP_TOKEN")
        if tcp_host not in {"127.0.0.1", "localhost"} or not tcp_port or not tcp_token:
            pytest.skip("set loopback MESOSPIM_LIVE_TCP_PORT and MESOSPIM_LIVE_TCP_TOKEN")
        tcp_client = RemoteControl(tcp_host, int(tcp_port), tcp_token, timeout=request_timeout)
        request.addfinalizer(tcp_client.close)
        def tool(name, arguments=None):
            return _raw_tcp_tool(tcp_client, name, arguments)
    else:
        raise ValueError("MESOSPIM_LIVE_REAL_TRANSPORT must be 'mcp' or 'tcp'")

    limits = _must(tool, "get_limits")
    stage_type = (limits.get("stage") or {}).get("stage_type")
    if stage_type == "DemoStage":
        pytest.fail(
            "refusing real-hardware sweep: remote stage_type is 'DemoStage' - run "
            "test_all_commands.py (marker live_demo_all) against a DemoStage instead"
        )

    capabilities = _must(tool, "get_capabilities")
    assert set(capabilities["commands"]) == set(VALID_CASES)
    assert len(capabilities["commands"]) == TOTAL
    assert "procedure" not in capabilities["commands"]
    assert "set_mode" not in capabilities["commands"]

    info = _must(tool, "get_info")
    etl_path_text = info.get("etl_config_path")
    if not etl_path_text:
        pytest.skip("running microscope did not report an etl_config_path via get_info")
    etl_path = Path(etl_path_text).resolve()
    if not etl_path.is_file():
        pytest.skip(f"reported etl_config_path does not exist on this filesystem: {etl_path}")

    # Bound repetition without hiding cross-transport lifecycle defects: each lane may run one
    # complete sweep per server endpoint (no live process PID is required here, unlike the Demo
    # sweep, since a real instrument's identity is the endpoint itself).
    sentinel = Path(tempfile.gettempdir()) / f".mesospim_real_all_{host}_{port}_{transport}.done"
    if sentinel.exists():
        pytest.skip(f"real-hardware all-command sweep already ran for {host}:{port}, transport={transport}")
    sentinel.write_text("real-hardware all-command sweep started\n", encoding="utf-8")

    state_keys = [
        "state",
        "position",
        "selected_row",
        "shutterstate",
        "ETL_cfg_file",
        "filter",
        "zoom",
        "laser",
        "intensity",
        "shutterconfig",
        "camera_exposure_time",
        "etl_l_delay_%",
        "etl_l_ramp_rising_%",
        "etl_l_ramp_falling_%",
        "etl_l_amplitude",
        "etl_l_offset",
        "etl_r_delay_%",
        "etl_r_ramp_rising_%",
        "etl_r_ramp_falling_%",
        "etl_r_amplitude",
        "etl_r_offset",
        "galvo_l_frequency",
        "galvo_l_amplitude",
        "laser_l_delay_%",
        "snap_folder",
    ]
    original = _must(tool, "get_state_all", {"keys": state_keys})
    original_acquisitions = _must(tool, "get_acquisition_list")["acquisitions"]
    etl_backup = etl_path.read_bytes()
    temp_folder = Path(tempfile.mkdtemp(prefix="mesospim_real_all_"))
    etl_copy = temp_folder / etl_path.name           # save_etl_config writes here, never the real file
    shutil.copyfile(etl_path, etl_copy)
    failures = []
    skipped = []
    seen = []
    connection_lost = False

    config = _must(tool, "get_config")
    filters = config["filters"]
    zooms = [item["name"] for item in config["zooms"]]
    lasers = [item["name"] for item in config["lasers"]]
    shutters = config["shutter_configs"]
    axes = limits["enforced"]["axes"]
    parameters = limits["enforced"]["parameters"]

    def alternate_parameter(key, delta):
        low, high = parameters[key]["range"]
        return _bounded_delta(original[key], low, high, delta)

    alt_filter = _different(filters, original["filter"])
    alt_zoom = _different(zooms, original["zoom"])
    alt_laser = _different(lasers, original["laser"])
    alt_shutter = _different(shutters, original["shutterconfig"])
    # The two intensity calls set the low intensity every later exposure runs at: two different
    # values, the first different from the operator's.
    low_intensity = laser_percent if original["intensity"] != laser_percent else laser_percent + 1
    lower_intensity = laser_percent + 1 if low_intensity == laser_percent else laser_percent
    x_target = _bounded_delta(original["position"]["x_pos"], *axes["x"], MOVE_UM)
    relative_target = _bounded_delta(x_target, *axes["x"], RELATIVE_MOVE_UM)
    relative_delta = relative_target - x_target

    def acquisition_row(filename, x_offset=0):
        row = dict(_build_acquisition(temp_folder, filename, original), intensity=laser_percent)
        row["x_pos"] += x_offset
        return row

    acquisition = acquisition_row("set-list.raw")
    x_here, y_here, z_here, f_here = (original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f"))
    beads_file, texture_file = _write_test_stacks(temp_folder)
    display_before = _must(tool, "get_display")
    levels_before = display_before["camera_window"]["levels"]
    contrast_open = display_before["windows"]["contrast"]
    writer_before = _must(tool, "get_writer_parameters", {"writer": "OME_Zarr_Writer"})["parameters"]["compression_level"]["value"]
    writer_changed = writer_before + 1 if writer_before < 9 else writer_before - 1
    chain_before = _must(tool, "get_processor_chain")["chain"]
    cases = copy.deepcopy(VALID_CASES)
    cases.update(
        {
            "move_absolute": {"targets": {"x": x_target}},
            "move_relative": {"deltas": {"x": relative_delta}},
            "zero": {"axes": ["x"]},
            "unzero": {"axes": ["x"]},
            "set_state": {"settings": {"intensity": low_intensity}},
            "set_filter": {"filter": alt_filter, "wait": True},
            "set_zoom": {"zoom": alt_zoom, "wait": True, "update_etl": False},
            "set_laser": {"laser": alt_laser, "wait": True, "update_etl": False},
            "set_intensity": {"intensity": lower_intensity, "wait": True},
            "set_shutterconfig": {"shutterconfig": alt_shutter},
            "set_camera": {"camera_exposure_time": alternate_parameter("camera_exposure_time", 0.001)},
            "set_etl": {"etl_l_amplitude": alternate_parameter("etl_l_amplitude", 0.01)},
            "set_galvo": {"galvo_l_frequency": alternate_parameter("galvo_l_frequency", 0.1)},
            "set_laser_timing": {"laser_l_delay_%": _bounded_delta(original["laser_l_delay_%"], 0, 100, 1)},
            "reload_etl_config": {"path": str(etl_copy), "wait": True},
            "update_etl_from_laser": {"laser": alt_laser, "wait": True},
            "update_etl_from_zoom": {"zoom": alt_zoom, "wait": True},
            "snap": {"folder": str(temp_folder), "prefix": "remote"},
            "set_acquisition_list": {"acquisitions": [acquisition], "selected_row": 0},
            "acquire_start": {"acquisition": acquisition_row("acquire-start.raw")},
            "stat_files": {"files": [str(temp_folder / "acquire-start.raw")]},
            "get_disk_space": {"acquisitions": [acquisition]},
            "check_motion_limits": {"acquisitions": [acquisition]},
            "time_lapse_start": {"timepoints": 1, "interval_sec": 0},
            # the table calls, on the two rows install_table puts in, with the instrument's own options
            "update_acquisition_row": {"row": 0, "changes": {"filename": "updated.raw"}},
            "add_acquisition_rows": {"like": 0},
            "save_acquisition_list": {"path": str(temp_folder / "list.csv"), "overwrite": True},
            "load_acquisition_list": {"path": str(temp_folder / "list.csv")},
            "name_acquisition_rows": {"writer": "RAW_Writer", "description": "remote"},
            "track_focus": {"z_1": z_here, "f_1": f_here, "z_2": z_here + 100,
                            "f_2": _bounded_delta(f_here, *axes["f"], 10)},
            "build_tiling_list": {"x_start": x_here, "x_end": x_here, "y_start": y_here, "y_end": y_here,
                                  "z_start": z_here, "z_end": z_here, "z_step": 1,
                                  "channels": [{"laser": original["laser"], "intensity": laser_percent,
                                                "filter": original["filter"]}],
                                  "folder": str(temp_folder), "writer": "RAW_Writer"},
            "set_snap_folder": {"folder": str(temp_folder)},
            # the windows (gui_handles): each change is read back and put back
            "set_display": {"levels": [123, 2345]},
            "set_windows": {"hide": ["contrast"]} if contrast_open else {"show": ["contrast"]},
            "get_picture": {"window": "camera", "max_size": 256},
            "open_image_file": {"path": beads_file},
            "set_table_view": {"select_rows": [0]},
            "get_writer_parameters": {"writer": "OME_Zarr_Writer"},
            "set_writer_parameters": {"writer": "OME_Zarr_Writer", "parameters": {"compression_level": writer_changed}},
            "set_processor_chain": {"processors": [{"name": "GaussianBlur", "config": {"sigma": 2.0}}]},
            "set_alignment_toggles": {"freeze_galvo": True},
            "optimize": {"mode": "focus", "range": OPTIMIZER_RANGE_UM, "points": OPTIMIZER_POINTS},
            "finish_optimization": {"accept": False},
            "save_parameters_to_config": {"path": str(temp_folder / "saved_config.py")},
            "analyse_psf": {"path": beads_file, "min_intensity": 1300, "z_step_um": 1.0, "z_fit_window_um": 10,
                            "min_bead_distance_um": 12},      # windows that fit the 21-plane stack
            "analyse_field_curvature": {"channels": [{"path": texture_file}], "z_step_um": 1.0, "n_rois_x": 4, "n_rois_y": 4},
        }
    )

    def state_value(key):
        return _must(tool, "get_state_all", {"keys": [key]}).get(key)

    def position():
        return _must(tool, "get_position")

    # Real hardware position readback settles with sub-micron jitter around the commanded target
    # even after the server itself reports the move "completed" (its own POSITION_TOLERANCE check
    # already passed server-side). Checking exact float equality here - fine for DemoStage's
    # instant, exact simulated position - would then wait the full MESOSPIM_OPERATION_TIMEOUT_SECONDS
    # for an equality that real hardware will essentially never hit. Compare within a tolerance
    # instead, configurable per run since it depends on the specific stage's actual precision.
    position_tolerance_um = float(os.environ.get("MESOSPIM_REAL_POSITION_TOLERANCE_UM", "1.0"))
    if position_tolerance_um <= 0:
        raise ValueError("MESOSPIM_REAL_POSITION_TOLERANCE_UM must be positive")

    def near(axis_value, target):
        return abs(axis_value - target) <= position_tolerance_um

    def stop_and_wait():
        stopping = _must(tool, "stop_activity")
        _wait_for_operation(tool, stopping, "stop_activity")
        _wait_until(lambda: state_value("state") == "idle", "idle state")

    def install(rows, label):
        accepted = _must(tool, "set_acquisition_list", {"acquisitions": rows, "selected_row": 0})
        _wait_for_operation(tool, accepted, label)

    def install_acquisition(filename):
        install([acquisition_row(filename)], "install acquisition list")

    def install_table(x_offsets=(0, 0)):
        install([acquisition_row(f"row-{i}.raw", offset) for i, offset in enumerate(x_offsets)], "install the two-row table")

    def table():
        return _must(tool, "get_acquisition_list")["acquisitions"]

    def displayed(number, timeout=120):
        """A display call's outcome, once the windows (or an analysis's thread) have carried it out."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            shown = _must(tool, "get_display", {"request": number})
            if shown["request"]["status"] != "queued":
                assert shown["request"]["status"] == "applied", shown["request"]
                return shown
            time.sleep(0.2)
        raise AssertionError(f"display request {number} still queued after {timeout} s")

    def put_back(name, arguments, label):
        undone = _must(tool, name, arguments)
        if name in WINDOW_CALLS:
            return displayed(undone["request"])
        return _wait_for_result(tool, undone, label)

    def verify(name, result):
        if name == "move_absolute":
            _wait_until(lambda: near(position()["x"], x_target), "absolute X target")
        elif name == "move_relative":
            _wait_until(lambda: near(position()["x"], relative_target), "relative X target")
        elif name == "zero":
            _wait_until(lambda: near(position()["x"], 0), "zeroed X")
        elif name == "unzero":
            _wait_until(lambda: near(position()["x"], relative_target), "unzeroed X")
        elif name in {"set_state", "set_intensity"}:
            expected = cases[name].get("settings", {}).get("intensity", cases[name].get("intensity"))
            _wait_until(lambda: state_value("intensity") == expected, f"{name} readback")
        elif name == "set_filter":
            _wait_until(lambda: state_value("filter") == alt_filter, "filter readback")
        elif name == "set_zoom":
            _wait_until(lambda: state_value("zoom") == alt_zoom, "zoom readback")
        elif name == "set_laser":
            _wait_until(lambda: state_value("laser") == alt_laser, "laser readback")
        elif name == "set_shutterconfig":
            _wait_until(lambda: state_value("shutterconfig") == alt_shutter, "shutter config readback")
        elif name in {"set_camera", "set_etl", "set_galvo", "set_laser_timing"}:
            key, expected = next(iter(cases[name].items()))
            _wait_until(lambda: state_value(key) == expected, f"{key} readback")
        elif name == "reload_etl_config":
            assert state_value("ETL_cfg_file") == str(etl_copy)
        elif name == "open_shutters":
            assert result["shutterstate"] is True
        elif name == "close_shutters":
            assert result["shutterstate"] is False
        elif name == "start_live":
            _wait_until(lambda: state_value("state") == "live", "start_live mode")
        elif name == "start_visual_mode":
            _wait_until(lambda: state_value("state") == "visual_mode", "visual mode")
        elif name == "start_lightsheet_alignment_mode":
            _wait_until(lambda: state_value("state") == "lightsheet_alignment_mode", "alignment mode")
        elif name == "load_sample":
            _wait_until(
                lambda: near(position()["y"], limits["stage"]["y_load_position"]), "sample load position"
            )
        elif name == "unload_sample":
            _wait_until(
                lambda: near(position()["y"], limits["stage"]["y_unload_position"]), "sample unload position"
            )
        elif name == "center_sample":
            _wait_until(
                lambda: near(position()["x"], limits["stage"]["x_center_position"]), "sample center X"
            )
        elif name == "set_acquisition_list":
            assert result["count"] == 1
            assert len(_must(tool, "get_acquisition_list")["acquisitions"]) == 1
        elif name in {"run_acquisition_list", "run_selected_acquisition", "preview_acquisition"}:
            assert result["scheduled"] is True
        elif name == "get_info":
            assert {"save_path", "warnings"} <= set(result)
        elif name == "acquire_start":
            assert result["started"] is True and result["planes"] == 1
        elif name == "get_disk_space":
            assert result["free_bytes"] >= 0 and result["required_bytes"] >= 0
        elif name == "check_motion_limits":
            assert isinstance(result["outside_limits"], list)
        elif name == "self_test":
            assert result["ok"] is True
        elif name == "time_lapse_start":
            assert result["started"] is True
        elif name == "time_lapse_stop":
            assert result["stopped"] is True
        elif name == "update_acquisition_row":
            assert [row["filename"] for row in table()] == ["updated.raw", "row-1.raw"]
        elif name == "add_acquisition_rows":
            assert len(table()) == 3
        elif name == "delete_acquisition_rows":
            assert [row["filename"] for row in table()] == ["row-0.raw"]
        elif name == "save_acquisition_list":
            assert (temp_folder / "list.csv").is_file()
        elif name in {"load_acquisition_list", "move_acquisition_row", "mark_acquisition_rows"}:
            assert len(table()) == 2
        elif name == "name_acquisition_rows":
            assert all(row["filename"].endswith(".raw") for row in table())
        elif name == "track_focus":
            assert [row["f_start"] for row in table()] == [f_here, f_here]
        elif name == "build_tiling_list":
            assert result["count"] == len(table()) == 1
        elif name == "set_snap_folder":
            _wait_until(lambda: state_value("snap_folder") == str(temp_folder), "snap folder readback")
        elif name == "get_display":
            assert {"camera_window", "main_window", "acquisition_manager", "windows"} <= set(result)
        elif name == "set_display":
            assert result["camera_window"]["levels"] == [123.0, 2345.0]
            if levels_before:
                put_back("set_display", {"levels": levels_before}, "levels back")
        elif name == "set_windows":
            assert result["windows"]["contrast"] is (not contrast_open)
            put_back("set_windows", {"show": ["contrast"]} if contrast_open else {"hide": ["contrast"]}, "contrast window back")
        elif name == "get_picture":
            picture = result["request"]["result"]
            assert picture["format"] == "png" and max(picture["width"], picture["height"]) <= 256
        elif name == "open_image_file":
            assert result["request"]["result"]["shape"] == [21, 64, 64]
        elif name == "set_table_view":
            assert result["acquisition_manager"]["selected_rows"] == [0]
        elif name == "get_writer_parameters":
            assert {"compression", "shards", "base_chunks"} <= set(result["parameters"])
        elif name == "set_writer_parameters":
            assert result["parameters"]["compression_level"] == writer_changed
            put_back("set_writer_parameters", {"writer": "OME_Zarr_Writer", "parameters": {"compression_level": writer_before}},
                     "writer parameters back")
        elif name == "get_processor_chain":
            assert "GaussianBlur" in [p["name"] for p in result["available"]]
        elif name == "set_processor_chain":
            assert result["chain"][0]["name"] == "GaussianBlur" and result["chain"][0]["config"]["sigma"] == 2.0
            put_back("set_processor_chain", {"processors": chain_before}, "processor chain back")
        elif name == "set_alignment_toggles":
            assert result["freeze_galvo"] is True and state_value("galvo_l_amplitude") == 0
            put_back("set_alignment_toggles", {"freeze_galvo": False}, "galvos unfrozen")
            assert state_value("galvo_l_amplitude") == original["galvo_l_amplitude"]
        elif name == "optimize":
            points = result["points"]
            assert len(points) == OPTIMIZER_POINTS
            assert near(points[0], f_here - OPTIMIZER_RANGE_UM) and near(points[-1], f_here + OPTIMIZER_RANGE_UM)
        elif name == "finish_optimization":
            assert result["accepted"] is False
            _wait_until(lambda: near(position()["f"], f_here), "focus back after the optimizer")
        elif name == "save_parameters_to_config":
            assert (temp_folder / "saved_config.py").is_file()
        elif name == "auto_illumination":
            sides = [row["shutterconfig"] for row in table()]
            assert len(set(sides)) == 2, sides           # the two rows, 25 um apart, lit from opposite sides
        elif name == "analyse_psf":
            psf = result["request"]["result"]
            assert psf["beads_found"] == 3
            assert abs(psf["fwhm_lateral_um"]["median"] - 1.0) < 0.1 and abs(psf["fwhm_axial_um"]["median"] - 2.0) < 0.2
        elif name == "analyse_field_curvature":
            assert result["request"]["result"]["channels"][0]["metrics"]["dof_um"] is not None
        else:
            assert isinstance(result, dict)

    acquisition_actions = {
        "run_acquisition_list": "run-list.raw",
        "run_selected_acquisition": "run-selected.raw",
        "preview_acquisition": "preview.raw",
    }
    modes_to_stop = {"start_live", "start_visual_mode", "start_lightsheet_alignment_mode"}
    optimizer_open = False

    try:
        # From here on mesoSPIM reads and saves the copy of the ETL file; cleanup points it back.
        _wait_for_result(tool, _must(tool, "reload_etl_config", {"path": str(etl_copy), "wait": True}), "ETL copy in use")
        for index, name in enumerate(VALID_CASES, 1):
            kind = ("CHANGE" if name in OPERATIONAL_COMMANDS else "WINDOW" if name in WINDOW_CALLS | WINDOW_FEATURE_CALLS
                    else "READ")
            seen.append(name)
            if name in LARGE_TRAVEL and not large_moves:
                skipped.append(name)
                print(f"[{index:02d}/{TOTAL}] {'SKIPPED':10s} {name} (travels to the config's position; "
                      "MESOSPIM_REAL_LARGE_MOVES=1 runs it)", flush=True)
                continue
            print(f"[{index:02d}/{TOTAL}] {kind:10s} {name}", flush=True)
            try:
                if name in acquisition_actions:
                    install_acquisition(acquisition_actions[name])
                if name in TABLE_CALLS - {"load_acquisition_list", "set_snap_folder"}:
                    install_table()
                if name == "auto_illumination":
                    install_table((0, MOVE_UM))
                before_save_mtime = etl_copy.stat().st_mtime_ns if name == "save_etl_config" else None
                ok, result = tool(name, cases[name])
                assert ok, result
                if name == "optimize":
                    optimizer_open = True
                if name in modes_to_stop:
                    verify(name, result)
                    time.sleep(hold)
                    stop_and_wait()
                elif name in WINDOW_CALLS and "request" in result:
                    verify(name, displayed(result["request"]))
                else:
                    completed_result = _wait_for_result(tool, result, name)
                    verify(name, completed_result)
                if name == "finish_optimization":
                    optimizer_open = False
                if name == "save_etl_config":
                    _wait_until(lambda: etl_copy.stat().st_mtime_ns != before_save_mtime, "ETL saved into the copy")
                    assert etl_path.read_bytes() == etl_backup, "save_etl_config wrote the real ETL file"
                if name in acquisition_actions or name == "acquire_start":
                    _wait_until(lambda: state_value("state") == "idle", f"{name} idle state")
                time.sleep(hold)
            except Exception as exc:  # continue so one run reports every broken command
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
                print(f"           FAIL {failures[-1]}", flush=True)
                if isinstance(exc, OSError):
                    connection_lost = True
                    print("           ABORT remote server connection lost; app restart required", flush=True)
                    break
                try:
                    stopped = _must(tool, "stop_activity")
                    _wait_for_operation(tool, stopped, "failure cleanup stop_activity")
                except Exception:
                    pass
    finally:
        cleanup_errors = []
        cleanup_calls = (
            ("time_lapse_stop", {}),
            ("stop_activity", {}),
            ("acquire_finish", {}),
            *([("finish_optimization", {"accept": False})] if optimizer_open else []),
            ("set_alignment_toggles", {"freeze_galvo": False}),
            ("set_processor_chain", {"processors": chain_before}),
            ("set_writer_parameters", {"writer": "OME_Zarr_Writer", "parameters": {"compression_level": writer_before}}),
            ("unzero", {"axes": ["x"]}),
            (
                "move_absolute",
                {
                    "targets": {
                        axis: original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f", "theta")
                    }
                },
            ),
            ("set_filter", {"filter": original["filter"], "wait": True}),
            ("set_zoom", {"zoom": original["zoom"], "wait": True, "update_etl": False}),
            ("set_laser", {"laser": original["laser"], "wait": True, "update_etl": False}),
            ("reload_etl_config", {"path": original["ETL_cfg_file"], "wait": True}),
            ("set_intensity", {"intensity": original["intensity"], "wait": True}),
            ("set_shutterconfig", {"shutterconfig": original["shutterconfig"]}),
            ("set_camera", {"camera_exposure_time": original["camera_exposure_time"]}),
            (
                "set_etl",
                {
                    key: original[key]
                    for key in (
                        "etl_l_delay_%",
                        "etl_l_ramp_rising_%",
                        "etl_l_ramp_falling_%",
                        "etl_l_amplitude",
                        "etl_l_offset",
                        "etl_r_delay_%",
                        "etl_r_ramp_rising_%",
                        "etl_r_ramp_falling_%",
                        "etl_r_amplitude",
                        "etl_r_offset",
                    )
                },
            ),
            ("set_galvo", {"galvo_l_frequency": original["galvo_l_frequency"]}),
            ("set_laser_timing", {"laser_l_delay_%": original["laser_l_delay_%"]}),
            (
                "set_acquisition_list",
                {
                    "acquisitions": original_acquisitions,
                    "selected_row": max(int(original.get("selected_row") or 0), 0),
                },
            ),
            ("open_shutters" if original.get("shutterstate") else "close_shutters", {}),
            *([("set_snap_folder", {"folder": original["snap_folder"]})] if original.get("snap_folder") else []),
        )
        if not connection_lost:
            for name, arguments in cleanup_calls:
                try:
                    cleanup_result = _must(tool, name, arguments)
                    _wait_for_operation(tool, cleanup_result, f"cleanup {name}")
                except Exception as exc:
                    cleanup_errors.append(f"{name}: {exc}")
                    if isinstance(exc, OSError):
                        connection_lost = True
                        break
        try:
            if etl_path.read_bytes() != etl_backup:     # never expected: the sweep saves into the copy
                etl_path.write_bytes(etl_backup)
                cleanup_errors.append("the real ETL file was written; restored from the backup")
        except Exception as exc:
            cleanup_errors.append(f"restore ETL file: {exc}")
        try:
            shutil.rmtree(temp_folder)
        except Exception as exc:
            cleanup_errors.append(f"remove temp acquisition folder: {exc}")
        if cleanup_errors:
            failures.extend(f"cleanup {item}" for item in cleanup_errors)

    assert seen == list(VALID_CASES)
    if connection_lost:
        pytest.fail(
            "remote server connection was lost; mesoSPIM app restart required:\n" + "\n".join(failures)
        )
    final_position = _must(tool, "get_position")
    expected_position = {axis: original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f", "theta")}
    assert all(near(final_position[axis], expected_position[axis]) for axis in expected_position), (
        final_position,
        expected_position,
    )
    assert state_value("ETL_cfg_file") == original["ETL_cfg_file"]
    assert etl_path.read_bytes() == etl_backup
    assert not failures, "real-hardware all-command sweep failures:\n" + "\n".join(failures)
    not_run = f"; NOT RUN: {', '.join(skipped)}" if skipped else ""
    print(
        f"{TOTAL - len(skipped)} OF {TOTAL} COMMANDS VERIFIED{not_run}; REAL-HARDWARE STATE RESTORED via {transport}",
        flush=True,
    )
