"""Opt-in DemoStage sweep of every mesoSPIM Remote Control command through the SINGLE bound
transport (MCP or TCP, chosen by MESOSPIM_LIVE_DEMO_TRANSPORT; a session hosts one transport).

Excluded from normal CI; refuses to run unless the operator explicitly opts in and the remote
configuration reports a DemoStage. Exercises all 56 allowlisted commands: every operational
mutation and every read/query command. Reads counts from contracts, never hardcodes them.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
import shutil
import tempfile
import time

import pytest

from mesoSPIM.test.remote_control.support.clients import RemoteControl
from mesoSPIM.test.remote_control.support.contracts import (OPERATIONAL_COMMANDS, TABLE_CALLS, VALID_CASES, WINDOW_CALLS,
                                                            WINDOW_FEATURE_CALLS)
from mesoSPIM.test.remote_control.support.live_session import bounded_delta as _bounded_delta
from mesoSPIM.test.remote_control.support.live_session import demo_acquisition as _demo_acquisition
from mesoSPIM.test.remote_control.support.live_session import different as _different
from mesoSPIM.test.remote_control.support.live_session import live_config as _live_config
from mesoSPIM.test.remote_control.support.live_session import must as _must
from mesoSPIM.test.remote_control.support.live_session import raw_mcp_tool as _raw_tool
from mesoSPIM.test.remote_control.support.live_session import raw_tcp_tool as _raw_tcp_tool
from mesoSPIM.test.remote_control.support.live_session import wait_for_operation as _wait_for_operation
from mesoSPIM.test.remote_control.support.live_session import wait_for_result as _wait_for_result
from mesoSPIM.test.remote_control.support.live_session import wait_until as _wait_until
from mesoSPIM.test.remote_control.support.live_session import write_test_stacks as _write_test_stacks


pytestmark = pytest.mark.live_demo_all

TOTAL = len(VALID_CASES)  # 67
OPERATIONAL = len(OPERATIONAL_COMMANDS)  # 49


def test_live_demo_all_commands_are_functional_safe_and_restored(request):
    host, port, token, hold, request_timeout, demo_root, etl_path, process_id = _live_config()
    transport = os.environ.get("MESOSPIM_LIVE_DEMO_TRANSPORT", "mcp").lower()
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
        raise ValueError("MESOSPIM_LIVE_DEMO_TRANSPORT must be 'mcp' or 'tcp'")

    limits = _must(tool, "get_limits")
    stage_type = (limits.get("stage") or {}).get("stage_type")
    if stage_type != "DemoStage":
        pytest.fail(f"refusing all-command sweep: remote stage_type is {stage_type!r}, not 'DemoStage'")

    capabilities = _must(tool, "get_capabilities")
    assert set(capabilities["commands"]) == set(VALID_CASES)
    assert len(capabilities["commands"]) == TOTAL
    assert "procedure" not in capabilities["commands"]
    assert "set_mode" not in capabilities["commands"]

    # Bound repetition without hiding cross-transport lifecycle defects: each lane may run one
    # complete sweep per Demo process.
    sentinel = Path(tempfile.gettempdir()) / (f".mesospim_demo_all_{process_id}_{transport}.done")
    if sentinel.exists():
        pytest.skip(f"all-command sweep already ran for PID {process_id}, transport={transport}")
    sentinel.write_text("all-command live demo sweep started\n", encoding="utf-8")

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
        "laser_l_delay_%",
        "snap_folder",
    ]
    original = _must(tool, "get_state_all", {"keys": state_keys})
    original_galvo_amplitude = _must(tool, "get_state_all", {"keys": ["galvo_l_amplitude"]})["galvo_l_amplitude"]
    original_acquisitions = _must(tool, "get_acquisition_list")["acquisitions"]
    etl_backup = etl_path.read_bytes()
    temp_folder = Path(tempfile.mkdtemp(prefix="mesospim_demo_all_"))
    failures = []
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
    alt_intensity = _bounded_delta(original["intensity"], 0, 100, 7)
    x_target = _bounded_delta(original["position"]["x_pos"], *axes["x"], 100)
    relative_target = _bounded_delta(x_target, *axes["x"], 25)
    relative_delta = relative_target - x_target

    acquisition = _demo_acquisition(temp_folder, "set-list.raw", original)
    x_here, y_here, z_here, f_here = (original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f"))
    beads_file, texture_file = _write_test_stacks(temp_folder)
    writer_before = _must(tool, "get_writer_parameters", {"writer": "OME_Zarr_Writer"})["parameters"]["compression_level"]["value"]
    chain_before = _must(tool, "get_processor_chain")["chain"]
    cases = copy.deepcopy(VALID_CASES)
    cases.update(
        {
            "move_absolute": {"targets": {"x": x_target}},
            "move_relative": {"deltas": {"x": relative_delta}},
            "zero": {"axes": ["x"]},
            "unzero": {"axes": ["x"]},
            "set_state": {"settings": {"intensity": alt_intensity}},
            "set_filter": {"filter": alt_filter, "wait": True},
            "set_zoom": {"zoom": alt_zoom, "wait": True, "update_etl": False},
            "set_laser": {"laser": alt_laser, "wait": True, "update_etl": False},
            "set_intensity": {"intensity": max(0, alt_intensity - 1), "wait": True},
            "set_shutterconfig": {"shutterconfig": alt_shutter},
            "set_camera": {"camera_exposure_time": alternate_parameter("camera_exposure_time", 0.001)},
            "set_etl": {"etl_l_amplitude": alternate_parameter("etl_l_amplitude", 0.01)},
            "set_galvo": {"galvo_l_frequency": alternate_parameter("galvo_l_frequency", 0.1)},
            "set_laser_timing": {"laser_l_delay_%": _bounded_delta(original["laser_l_delay_%"], 0, 100, 1)},
            "reload_etl_config": {"path": str(etl_path), "wait": True},
            "update_etl_from_laser": {"laser": alt_laser, "wait": True},
            "update_etl_from_zoom": {"zoom": alt_zoom, "wait": True},
            "set_acquisition_list": {"acquisitions": [acquisition], "selected_row": 0},
            "acquire_start": {"acquisition": _demo_acquisition(temp_folder, "acquire-start.raw", original)},
            "stat_files": {"files": [str(temp_folder / "acquire-start.raw")]},
            "get_disk_space": {"acquisitions": [acquisition]},
            "check_motion_limits": {"acquisitions": [acquisition]},
            "time_lapse_start": {"timepoints": 1, "interval_sec": 0},
            "snap": {"folder": str(temp_folder), "prefix": "remote"},
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
                                  "channels": [{"laser": original["laser"], "intensity": 10,
                                                "filter": original["filter"]}],
                                  "folder": str(temp_folder), "writer": "RAW_Writer"},
            "set_snap_folder": {"folder": str(temp_folder)},
            # the windows (gui_handles), on the running demo's own windows and files
            "set_display": {"levels": [123, 2345]},
            "set_windows": {"show": ["contrast"]},
            "get_picture": {"window": "camera", "max_size": 256},
            "open_image_file": {"path": beads_file},
            "set_table_view": {"select_rows": [0]},
            "get_writer_parameters": {"writer": "OME_Zarr_Writer"},
            "set_writer_parameters": {"writer": "OME_Zarr_Writer", "parameters": {"compression_level": 4}},
            "set_processor_chain": {"processors": [{"name": "GaussianBlur", "config": {"sigma": 2.0}}]},
            "set_alignment_toggles": {"freeze_galvo": True},
            "optimize": {"mode": "focus", "range": 50, "points": 5},
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

    def stop_and_wait():
        stopping = _must(tool, "stop_activity")
        _wait_for_operation(tool, stopping, "stop_activity")
        _wait_until(lambda: state_value("state") == "idle", "idle state")

    def install_acquisition(filename):
        item = _demo_acquisition(temp_folder, filename, original)
        accepted = _must(tool, "set_acquisition_list", {"acquisitions": [item], "selected_row": 0})
        _wait_for_operation(tool, accepted, "install acquisition list")

    def install_table():
        rows = [_demo_acquisition(temp_folder, name, original) for name in ("row-0.raw", "row-1.raw")]
        accepted = _must(tool, "set_acquisition_list", {"acquisitions": rows, "selected_row": 0})
        _wait_for_operation(tool, accepted, "install the two-row table")

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

    def verify(name, result):
        if name == "move_absolute":
            _wait_until(lambda: position()["x"] == x_target, "absolute X target")
        elif name == "move_relative":
            _wait_until(lambda: position()["x"] == relative_target, "relative X target")
        elif name == "zero":
            _wait_until(lambda: position()["x"] == 0, "zeroed X")
        elif name == "unzero":
            _wait_until(lambda: position()["x"] == relative_target, "unzeroed X")
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
            _wait_until(lambda: position()["y"] == limits["stage"]["y_load_position"], "sample load position")
        elif name == "unload_sample":
            _wait_until(
                lambda: position()["y"] == limits["stage"]["y_unload_position"], "sample unload position"
            )
        elif name == "center_sample":
            _wait_until(lambda: position()["x"] == limits["stage"]["x_center_position"], "sample center X")
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
        elif name == "set_windows":
            assert result["windows"]["contrast"] is True
            displayed(_must(tool, "set_windows", {"hide": ["contrast"]})["request"])
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
            assert result["parameters"]["compression_level"] == 4
            undone = _must(tool, "set_writer_parameters", {"writer": "OME_Zarr_Writer",
                                                           "parameters": {"compression_level": writer_before}})
            _wait_for_result(tool, undone, "writer parameters back")
        elif name == "get_processor_chain":
            assert "GaussianBlur" in [p["name"] for p in result["available"]]
        elif name == "set_processor_chain":
            assert result["chain"][0]["name"] == "GaussianBlur" and result["chain"][0]["config"]["sigma"] == 2.0
            undone = _must(tool, "set_processor_chain", {"processors": chain_before})
            _wait_for_result(tool, undone, "processor chain back")
        elif name == "set_alignment_toggles":
            assert result["freeze_galvo"] is True and state_value("galvo_l_amplitude") == 0
            undone = _must(tool, "set_alignment_toggles", {"freeze_galvo": False})
            _wait_for_result(tool, undone, "galvos unfrozen")
            assert state_value("galvo_l_amplitude") == original_galvo_amplitude
        elif name == "optimize":
            assert len(result["points"]) == 5 and result["points"][0] == f_here - 50 and result["points"][-1] == f_here + 50
        elif name == "finish_optimization":
            assert result["accepted"] is False and position()["f"] == f_here
        elif name == "save_parameters_to_config":
            assert (temp_folder / "saved_config.py").is_file()
        elif name == "auto_illumination":
            assert {row["shutterconfig"] for row in table()} <= {"Left", "Right"}
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

    try:
        for index, name in enumerate(VALID_CASES, 1):
            kind = ("CHANGE" if name in OPERATIONAL_COMMANDS else "WINDOW" if name in WINDOW_CALLS | WINDOW_FEATURE_CALLS
                    else "READ")
            print(f"[{index:02d}/{TOTAL}] {kind:10s} {name}", flush=True)
            seen.append(name)
            try:
                if name in acquisition_actions:
                    install_acquisition(acquisition_actions[name])
                if name in TABLE_CALLS - {"load_acquisition_list", "set_snap_folder"}:
                    install_table()
                before_save_mtime = etl_path.stat().st_mtime_ns if name == "save_etl_config" else None
                ok, result = tool(name, cases[name])
                assert ok, result
                if name in modes_to_stop:
                    verify(name, result)
                    time.sleep(hold)
                    stop_and_wait()
                elif name in WINDOW_CALLS and "request" in result:
                    verify(name, displayed(result["request"]))
                else:
                    completed_result = _wait_for_result(tool, result, name)
                    verify(name, completed_result)
                if name == "save_etl_config":
                    _wait_until(lambda: etl_path.stat().st_mtime_ns != before_save_mtime, "demo ETL save")
                    etl_path.write_bytes(etl_backup)
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
            etl_path.write_bytes(etl_backup)
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
    assert final_position == {
        axis: original["position"][axis + "_pos"] for axis in ("x", "y", "z", "f", "theta")
    }
    assert etl_path.read_bytes() == etl_backup
    assert not failures, "all-command demo sweep failures:\n" + "\n".join(failures)
    print(
        f"ALL {TOTAL} COMMANDS VERIFIED; {OPERATIONAL} OPERATIONAL CALLS EXECUTED; "
        f"DEMO STATE RESTORED via {transport}",
        flush=True,
    )

