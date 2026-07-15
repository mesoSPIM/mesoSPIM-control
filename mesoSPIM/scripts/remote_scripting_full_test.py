"""Full demo-mode remote-scripting test client for mesoSPIM.

Run this from any Python environment that should control mesoSPIM, while the
mesoSPIM GUI is running in demo mode and Tools -> Remote Scripting... is
started.

The test talks to the remote scripting TCP server and executes small Python
snippets in the live mesoSPIM Core context. The default profile is the full demo
profile: it changes controls, camera settings, waveform/ETL parameters, stage
positions, shutters, zoom, and runs a no-write snap, then restores values where
possible.

Example:
    python mesoSPIM/scripts/remote_scripting_full_test.py --token YOUR_TOKEN

This script is intended for demo mode. It refuses to run against a non-demo stage
unless --allow-non-demo is provided.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sys
import textwrap
import time
from pathlib import Path


ENCODING = "utf-8"
RESULT_PREFIX = "__MESOSPIM_REMOTE_TEST_RESULT__ "
SHOW_REMOTE_OUTPUT = False


class RemoteScriptingError(RuntimeError):
    pass


class RemoteScriptingClient:
    def __init__(self, host: str, port: int, token: str | None, timeout: float):
        self.host = host
        self.port = port
        self.token = token
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def __enter__(self) -> "RemoteScriptingClient":
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if self.token is not None:
            self.sock.sendall(self._frame(self.token))
            reply = self._read_frame()
            if reply != "OK":
                raise RemoteScriptingError(f"authentication failed: {reply!r}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    @staticmethod
    def _frame(text: str) -> bytes:
        payload = text.encode(ENCODING)
        return str(len(payload)).encode("ascii") + b"\n" + payload

    def _read_frame(self) -> str:
        if self.sock is None:
            raise RemoteScriptingError("client is not connected")
        header = b""
        while not header.endswith(b"\n"):
            chunk = self.sock.recv(1)
            if not chunk:
                raise RemoteScriptingError("socket closed while reading frame header")
            header += chunk
        try:
            length = int(header[:-1])
        except ValueError as exc:
            raise RemoteScriptingError(f"invalid frame header: {header!r}") from exc

        payload = b""
        while len(payload) < length:
            chunk = self.sock.recv(length - len(payload))
            if not chunk:
                raise RemoteScriptingError("socket closed while reading frame payload")
            payload += chunk
        return payload.decode(ENCODING, "replace")

    def run_script(self, script: str) -> str:
        if self.sock is None:
            raise RemoteScriptingError("client is not connected")
        self.sock.sendall(self._frame(script))
        return self._read_frame()


def _remote_wrapper(name: str, body: str) -> str:
    indented_body = textwrap.indent(body.rstrip(), "    ")
    return f"""
import json
import time
import traceback

from PyQt5 import QtCore, QtWidgets

core = self
__result = {{"ok": True, "name": {name!r}}}

def __json_default(value):
    try:
        return str(value)
    except Exception:
        return "<unserializable>"

def __pump(ms=100):
    deadline = time.time() + (ms / 1000.0)
    while time.time() < deadline:
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 20)
        time.sleep(0.01)

try:
{indented_body}
except Exception:
    __result["ok"] = False
    __result["error"] = traceback.format_exc()

print({RESULT_PREFIX!r} + json.dumps(__result, default=__json_default, sort_keys=True))
"""


def parse_remote_result(reply: str) -> dict:
    for line in reversed(reply.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise RemoteScriptingError(
        "remote script did not emit a structured result; reply was:\n" + reply
    )


def run_remote_json(client: RemoteScriptingClient, name: str, body: str, raw_dir: Path | None) -> dict:
    reply = client.run_script(_remote_wrapper(name, body))
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
        (raw_dir / f"{safe_name}.reply.txt").write_text(reply, encoding=ENCODING)
    if SHOW_REMOTE_OUTPUT:
        remote_output = "\n".join(
            line for line in reply.splitlines() if not line.startswith(RESULT_PREFIX)
        ).strip()
        if remote_output:
            print("  Remote stdout/stderr:")
            print(textwrap.indent(remote_output, "    "))
    result = parse_remote_result(reply)
    if not result.get("ok"):
        raise RemoteScriptingError(result.get("error", "remote script failed"))
    return result


def choose_next(values: list, current):
    if not values:
        return current
    if current in values and len(values) > 1:
        return values[(values.index(current) + 1) % len(values)]
    return values[0]


def print_result(status: str, name: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def short_value(value, limit: int = 64) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, sort_keys=True)
    else:
        text = str(value)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def print_kv(label: str, value) -> None:
    print(f"  {label:<24} {short_value(value, 96)}")


def print_change_table(result: dict, keys: list[str] | None = None, *, limit: int | None = None) -> None:
    before = result.get("before", {})
    target = result.get("target", {})
    after = result.get("after", {})
    restored = result.get("restored", {})
    if keys is None:
        keys = sorted(set(before) | set(target) | set(after) | set(restored))
    if limit is not None:
        keys = keys[:limit]
    print("  Changes:")
    print("    key                                before -> target -> after -> restored")
    for key in keys:
        values = [
            short_value(before.get(key, "")),
            short_value(target.get(key, "")),
            short_value(after.get(key, "")),
            short_value(restored.get(key, "")),
        ]
        print(f"    {key:<34} {values[0]} -> {values[1]} -> {values[2]} -> {values[3]}")


def print_named_change_table(result: dict, columns: list[tuple[str, str]], keys: list[str]) -> None:
    print("  Changes:")
    header = " -> ".join(label for label, _ in columns)
    print(f"    {'key':<34} {header}")
    for key in keys:
        values = []
        for _, source_key in columns:
            source = result.get(source_key, {})
            values.append(short_value(source.get(key, "")))
        print(f"    {key:<34} {' -> '.join(values)}")


def print_position(label: str, position: dict) -> None:
    ordered = ["x_pos", "y_pos", "z_pos", "f_pos", "theta_pos"]
    parts = [f"{key}={position.get(key)}" for key in ordered if key in position]
    print(f"  {label:<24} " + ", ".join(parts))


def print_test_details(name: str, result: dict) -> None:
    if name == "probe":
        state = result.get("state", {})
        print_kv("Core state", state.get("state"))
        print_position("Position", state.get("position", {}))
        print_kv("Stage class", result.get("stage_class"))
        config = result.get("config", {})
        print_kv("Lasers", config.get("lasers", []))
        print_kv("Filters", config.get("filters", []))
        print_kv("Shutters", config.get("shutters", []))
        print_kv("Zooms", config.get("zooms", []))
    elif name == "status/control widgets":
        print_change_table(result, ["laser", "intensity", "filter", "shutterconfig"])
    elif name == "camera settings":
        print_change_table(result, list(result.get("target", {}).keys()))
    elif name == "waveform parameters":
        print_change_table(result, list(result.get("after", {}).keys()))
    elif name == "stage motion":
        for item in result.get("per_axis", []):
            move = item.get("move")
            delta = item.get("delta")
            before = item.get("before", {})
            after = item.get("after", {})
            axis = "theta_pos" if move == "theta_rel" else move.replace("_rel", "_pos")
            print(
                f"  {move:<12} {delta:+g}: "
                f"{short_value(before.get(axis))} -> {short_value(after.get(axis))}"
            )
        print_position("Final position", result.get("final", {}))
    elif name == "absolute motion":
        print_position("Initial position", result.get("initial", {}))
        print_kv("Absolute target", result.get("target", {}))
        print_position("After move", result.get("after", {}))
        print_position("Final position", result.get("final", {}))
    elif name == "zero/unzero":
        print_position("Before", result.get("before", {}))
        print_position("Zeroed", result.get("zeroed", {}))
        print_position("Restored", result.get("restored", {}))
    elif name == "sample helper moves":
        print_position("Initial position", result.get("initial", {}))
        print_position("Load sample", result.get("loaded", {}))
        print_position("Unload sample", result.get("unloaded", {}))
        print_position("Center sample", result.get("centered", {}))
        print_position("Final position", result.get("final", {}))
    elif name == "shutter open/close":
        print_named_change_table(
            result,
            [
                ("before", "before"),
                ("opened", "opened"),
                ("closed", "closed"),
                ("restored", "restored"),
            ],
            ["shutterconfig", "shutterstate"],
        )
    elif name == "ETL reload/update":
        print_kv("Laser used", result.get("laser"))
        print_kv("Zoom used", result.get("zoom"))
        print_named_change_table(
            result,
            [
                ("before", "before"),
                ("cfg reload", "after_cfg_reload"),
                ("laser update", "after_laser_update"),
                ("zoom update", "after_zoom_update"),
                ("restored", "restored"),
            ],
            [
                "ETL_cfg_file",
                "etl_l_amplitude",
                "etl_l_offset",
                "etl_r_amplitude",
                "etl_r_offset",
            ],
        )
    elif name == "zoom":
        print_change_table(result, ["zoom"])
    elif name == "snap(write_flag=False)":
        print_kv("State", f"{result.get('before_state')} -> {result.get('after_state')}")
        print_position("Before position", result.get("before_position", {}))
        print_position("After position", result.get("after_position", {}))


def numeric_target(key: str, value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int) and not isinstance(value, bool):
        if key == "samplerate":
            return max(1, value + 1)
        return value + 1
    if isinstance(value, float):
        if key == "sweeptime":
            return max(0.001, value + 0.001)
        if "phase" in key:
            return value + 0.01
        if "%" in key or "duty_cycle" in key or "pulse" in key:
            return value - 0.1 if value >= 99.0 else value + 0.1
        return value + 0.01
    return value


def test_probe(client: RemoteScriptingClient, raw_dir: Path | None) -> dict:
    body = """
keys = (
    'state', 'position', 'position_absolute', 'laser', 'intensity',
    'filter', 'shutterconfig', 'zoom', 'ETL_cfg_file',
    'camera_exposure_time', 'camera_line_interval',
    'camera_display_live_subsampling', 'camera_display_acquisition_subsampling',
    'camera_binning',
)
snapshot = {}
for key in keys:
    try:
        snapshot[key] = core.state[key]
    except Exception as exc:
        snapshot[key] = '<missing: %s>' % exc

__result['state'] = snapshot
__result['stage_class'] = core.serial_worker.stage.__class__.__name__
__result['config'] = {
    'lasers': list(core.cfg.laserdict.keys()),
    'filters': list(core.cfg.filterdict.keys()),
    'shutters': list(core.cfg.shutteroptions),
    'zooms': list(core.cfg.zoomdict.keys()),
}
core.sig_status_message.emit('Remote scripting full test: probe reached Core')
"""
    return run_remote_json(client, "probe", body, raw_dir)


def test_controls(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    body = f"""
control_keys = ('laser', 'intensity', 'filter', 'shutterconfig')
before = {{}}
for key in control_keys:
    before[key] = core.state[key]

lasers = list(core.cfg.laserdict.keys())
filters = list(core.cfg.filterdict.keys())
shutters = list(core.cfg.shutteroptions)

target_laser = lasers[(lasers.index(before['laser']) + 1) % len(lasers)] if before['laser'] in lasers and len(lasers) > 1 else before['laser']
target_filter = filters[(filters.index(before['filter']) + 1) % len(filters)] if before['filter'] in filters and len(filters) > 1 else before['filter']
target_shutter = shutters[(shutters.index(before['shutterconfig']) + 1) % len(shutters)] if before['shutterconfig'] in shutters and len(shutters) > 1 else before['shutterconfig']
target_intensity = 25 if before['intensity'] != 25 else 50

core.set_laser(target_laser, update_etl=False)
core.set_intensity(target_intensity)
core.serial_worker.set_filter(target_filter)
core.set_shutterconfig(target_shutter)
__pump(150)

after = {{
    'laser': core.state['laser'],
    'intensity': core.state['intensity'],
    'filter': core.state['filter'],
    'shutterconfig': core.state['shutterconfig'],
}}

if {restore!r}:
    core.set_laser(before['laser'], update_etl=False)
    core.set_intensity(before['intensity'])
    core.serial_worker.set_filter(before['filter'])
    core.set_shutterconfig(before['shutterconfig'])
    __pump(150)

restored = {{
    'laser': core.state['laser'],
    'intensity': core.state['intensity'],
    'filter': core.state['filter'],
    'shutterconfig': core.state['shutterconfig'],
}}

__result['before'] = before
__result['target'] = {{
    'laser': target_laser,
    'intensity': target_intensity,
    'filter': target_filter,
    'shutterconfig': target_shutter,
}}
__result['after'] = after
__result['restored'] = restored
"""
    return run_remote_json(client, "controls", body, raw_dir)


def test_camera_settings(
    client: RemoteScriptingClient,
    include_binning: bool,
    restore: bool,
    raw_dir: Path | None,
) -> dict:
    binning_part = ""
    if include_binning:
        binning_part = """
before['camera_binning'] = core.state['camera_binning']
target_binning = '2x2' if before['camera_binning'] != '2x2' else '1x1'
core.state_request_handler({'camera_binning': target_binning})
target['camera_binning'] = target_binning
"""
    restore_binning_part = ""
    if include_binning:
        restore_binning_part = """
    core.state_request_handler({'camera_binning': before['camera_binning']})
"""

    body = f"""
before = {{
    'camera_exposure_time': core.state['camera_exposure_time'],
    'camera_line_interval': core.state['camera_line_interval'],
    'camera_display_live_subsampling': core.state['camera_display_live_subsampling'],
    'camera_display_acquisition_subsampling': core.state['camera_display_acquisition_subsampling'],
}}
target = {{
    'camera_exposure_time': before['camera_exposure_time'] + 0.001,
    'camera_line_interval': before['camera_line_interval'] + 0.000001,
    'camera_display_live_subsampling': 1 if before['camera_display_live_subsampling'] != 1 else 2,
    'camera_display_acquisition_subsampling': 1 if before['camera_display_acquisition_subsampling'] != 1 else 2,
}}

core.set_camera_exposure_time(target['camera_exposure_time'])
core.set_camera_line_interval(target['camera_line_interval'])
core.state_request_handler({{'camera_display_live_subsampling': target['camera_display_live_subsampling']}})
core.state_request_handler({{'camera_display_acquisition_subsampling': target['camera_display_acquisition_subsampling']}})
{binning_part}
__pump(150)

after = {{}}
for key in target:
    after[key] = core.state[key]

if {restore!r}:
    core.set_camera_exposure_time(before['camera_exposure_time'])
    core.set_camera_line_interval(before['camera_line_interval'])
    core.state_request_handler({{'camera_display_live_subsampling': before['camera_display_live_subsampling']}})
    core.state_request_handler({{'camera_display_acquisition_subsampling': before['camera_display_acquisition_subsampling']}})
{restore_binning_part}
    __pump(150)

restored = {{}}
for key in before:
    restored[key] = core.state[key]

__result['before'] = before
__result['target'] = target
__result['after'] = after
__result['restored'] = restored
"""
    return run_remote_json(client, "camera_settings", body, raw_dir)


def test_waveform_parameters(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    keys = [
        "samplerate",
        "sweeptime",
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
        "galvo_l_offset",
        "galvo_l_duty_cycle",
        "galvo_l_phase",
        "galvo_r_frequency",
        "galvo_r_offset",
        "galvo_r_duty_cycle",
        "galvo_r_phase",
        "laser_l_delay_%",
        "laser_l_pulse_%",
        "laser_r_delay_%",
        "laser_r_pulse_%",
        "camera_delay_%",
        "camera_pulse_%",
    ]
    body = f"""
keys = {keys!r}
before = {{}}
target = {{}}
after = {{}}

def make_target(key, value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int) and not isinstance(value, bool):
        if key == 'samplerate':
            return max(1, value + 1)
        return value + 1
    if isinstance(value, float):
        if key == 'sweeptime':
            return max(0.001, value + 0.001)
        if 'phase' in key:
            return value + 0.01
        if '%' in key or 'duty_cycle' in key or 'pulse' in key:
            return value - 0.1 if value >= 99.0 else value + 0.1
        return value + 0.01
    return value

for key in keys:
    try:
        value = core.state[key]
    except Exception:
        continue
    before[key] = value
    target[key] = make_target(key, value)
    core.state_request_handler({{key: target[key]}})
    __pump(20)
    try:
        after[key] = core.state[key]
    except Exception as exc:
        after[key] = '<readback failed: %s>' % exc

if {restore!r}:
    for key, value in before.items():
        core.state_request_handler({{key: value}})
        __pump(20)

restored = {{}}
for key in before:
    try:
        restored[key] = core.state[key]
    except Exception as exc:
        restored[key] = '<readback failed: %s>' % exc

__result['before'] = before
__result['target'] = target
__result['after'] = after
__result['restored'] = restored
"""
    return run_remote_json(client, "waveform_parameters", body, raw_dir)


def test_stage_motion(
    client: RemoteScriptingClient,
    step_um: float,
    theta_step: float,
    restore: bool,
    raw_dir: Path | None,
) -> dict:
    body = f"""
moves = [
    ('x_rel', {step_um!r}),
    ('y_rel', {step_um!r}),
    ('z_rel', {step_um!r}),
    ('f_rel', {step_um!r}),
    ('theta_rel', {theta_step!r}),
]

initial = dict(core.state['position'])
per_axis = []

for key, delta in moves:
    before = dict(core.state['position'])
    core.serial_worker.move_relative({{key: delta}}, wait_until_done=True)
    core.serial_worker.stage.report_position()
    __pump(50)
    after = dict(core.state['position'])
    per_axis.append({{'move': key, 'delta': delta, 'before': before, 'after': after}})

if {restore!r}:
    for key, delta in reversed(moves):
        core.serial_worker.move_relative({{key: -delta}}, wait_until_done=True)
        core.serial_worker.stage.report_position()
        __pump(50)

final = dict(core.state['position'])
core.sig_status_message.emit('Remote scripting full test: stage motion complete')
__result['initial'] = initial
__result['per_axis'] = per_axis
__result['final'] = final
"""
    return run_remote_json(client, "stage_motion", body, raw_dir)


def test_absolute_motion(
    client: RemoteScriptingClient,
    step_um: float,
    theta_step: float,
    restore: bool,
    raw_dir: Path | None,
) -> dict:
    body = f"""
initial = dict(core.state['position'])
target = {{
    'x_abs': initial['x_pos'] + {step_um!r},
    'y_abs': initial['y_pos'] + {step_um!r},
    'z_abs': initial['z_pos'] + {step_um!r},
    'f_abs': initial['f_pos'] + {step_um!r},
    'theta_abs': initial['theta_pos'] + {theta_step!r},
}}

core.serial_worker.move_absolute(target, wait_until_done=True, use_internal_position=True)
core.serial_worker.stage.report_position()
__pump(100)
after = dict(core.state['position'])

if {restore!r}:
    restore_target = {{
        'x_abs': initial['x_pos'],
        'y_abs': initial['y_pos'],
        'z_abs': initial['z_pos'],
        'f_abs': initial['f_pos'],
        'theta_abs': initial['theta_pos'],
    }}
    core.serial_worker.move_absolute(restore_target, wait_until_done=True, use_internal_position=True)
    core.serial_worker.stage.report_position()
    __pump(100)

final = dict(core.state['position'])
core.sig_status_message.emit('Remote scripting full test: absolute stage motion complete')
__result['initial'] = initial
__result['target'] = target
__result['after'] = after
__result['final'] = final
"""
    return run_remote_json(client, "absolute_motion", body, raw_dir)


def test_zero_unzero(client: RemoteScriptingClient, raw_dir: Path | None) -> dict:
    body = """
stage = core.serial_worker.stage
before = dict(core.state['position'])
raw_x_before = stage.x_pos
offset_x_before = stage.int_x_pos_offset

stage.zero_axes(['x'])
stage.report_position()
__pump(50)
zeroed = dict(core.state['position'])

stage.unzero_axes(['x'])
stage.x_pos = raw_x_before
stage.int_x_pos_offset = offset_x_before
stage.report_position()
__pump(50)
restored = dict(core.state['position'])

if abs(zeroed['x_pos']) > 1e-9:
    raise AssertionError('zero_axes did not make X readout zero: %r' % zeroed)
if abs(restored['x_pos'] - before['x_pos']) > 1e-9:
    raise AssertionError('unzero/cleanup did not restore X readout: before=%r restored=%r' % (before, restored))

__result['before'] = before
__result['zeroed'] = zeroed
__result['restored'] = restored
"""
    return run_remote_json(client, "zero_unzero", body, raw_dir)


def test_sample_moves(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    body = f"""
initial = dict(core.state['position'])
stage = core.serial_worker.stage

stage.load_sample()
stage.report_position()
__pump(100)
loaded = dict(core.state['position'])

stage.unload_sample()
stage.report_position()
__pump(100)
unloaded = dict(core.state['position'])

stage.center_sample()
stage.report_position()
__pump(100)
centered = dict(core.state['position'])

if {restore!r}:
    restore_target = {{
        'x_abs': initial['x_pos'],
        'y_abs': initial['y_pos'],
        'z_abs': initial['z_pos'],
        'f_abs': initial['f_pos'],
        'theta_abs': initial['theta_pos'],
    }}
    core.serial_worker.move_absolute(restore_target, wait_until_done=True, use_internal_position=True)
    core.serial_worker.stage.report_position()
    __pump(100)

final = dict(core.state['position'])
core.sig_status_message.emit('Remote scripting full test: sample helper moves complete')
__result['initial'] = initial
__result['loaded'] = loaded
__result['unloaded'] = unloaded
__result['centered'] = centered
__result['final'] = final
"""
    return run_remote_json(client, "sample_moves", body, raw_dir)


def test_shutters(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    body = f"""
before = {{
    'shutterstate': core.state['shutterstate'],
    'shutterconfig': core.state['shutterconfig'],
}}

core.open_shutters()
__pump(50)
opened = {{
    'shutterstate': core.state['shutterstate'],
    'shutterconfig': core.state['shutterconfig'],
}}

core.close_shutters()
__pump(50)
closed = {{
    'shutterstate': core.state['shutterstate'],
    'shutterconfig': core.state['shutterconfig'],
}}

if {restore!r} and before['shutterstate']:
    core.open_shutters()
elif {restore!r}:
    core.close_shutters()
__pump(50)

restored = {{
    'shutterstate': core.state['shutterstate'],
    'shutterconfig': core.state['shutterconfig'],
}}
core.sig_status_message.emit('Remote scripting full test: shutter open/close complete')
__result['before'] = before
__result['opened'] = opened
__result['closed'] = closed
__result['restored'] = restored
"""
    return run_remote_json(client, "shutters", body, raw_dir)


def test_etl_updates(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    keys = [
        "ETL_cfg_file",
        "etl_l_amplitude",
        "etl_l_offset",
        "etl_r_amplitude",
        "etl_r_offset",
    ]
    body = f"""
keys = {keys!r}
before = {{key: core.state[key] for key in keys}}
laser = core.state['laser']
zoom = core.state['zoom']

core.state_request_handler({{'ETL_cfg_file': before['ETL_cfg_file']}})
__pump(100)
after_cfg_reload = {{key: core.state[key] for key in keys}}

core.state_request_handler({{'set_etls_according_to_laser': laser}})
__pump(100)
after_laser_update = {{key: core.state[key] for key in keys}}

core.state_request_handler({{'set_etls_according_to_zoom': zoom}})
__pump(100)
after_zoom_update = {{key: core.state[key] for key in keys}}

if {restore!r}:
    for key, value in before.items():
        core.state_request_handler({{key: value}})
        __pump(20)

restored = {{key: core.state[key] for key in keys}}
core.sig_status_message.emit('Remote scripting full test: ETL reload/update complete')
__result['before'] = before
__result['after_cfg_reload'] = after_cfg_reload
__result['after_laser_update'] = after_laser_update
__result['after_zoom_update'] = after_zoom_update
__result['restored'] = restored
__result['laser'] = laser
__result['zoom'] = zoom
"""
    return run_remote_json(client, "etl_updates", body, raw_dir)


def test_zoom(client: RemoteScriptingClient, restore: bool, raw_dir: Path | None) -> dict:
    body = f"""
zooms = list(core.cfg.zoomdict.keys())
before = core.state['zoom']
if before in zooms and len(zooms) > 1:
    target = zooms[(zooms.index(before) + 1) % len(zooms)]
else:
    target = before
core.set_zoom(target, wait_until_done=True, update_etl=False)
__pump(100)
after = core.state['zoom']
if {restore!r} and before != after:
    core.set_zoom(before, wait_until_done=True, update_etl=False)
    __pump(100)
restored = core.state['zoom']
__result['before'] = {{'zoom': before}}
__result['target'] = {{'zoom': target}}
__result['after'] = {{'zoom': after}}
__result['restored'] = {{'zoom': restored}}
"""
    return run_remote_json(client, "zoom", body, raw_dir)


def test_snap(client: RemoteScriptingClient, raw_dir: Path | None) -> dict:
    body = """
before_state = core.state['state']
before_position = dict(core.state['position'])
core.snap(write_flag=False, laser_blanking=True)
__pump(100)
after_state = core.state['state']
after_position = dict(core.state['position'])
core.sig_status_message.emit('Remote scripting full test: snap(write_flag=False) complete')
__result['before_state'] = before_state
__result['after_state'] = after_state
__result['before_position'] = before_position
__result['after_position'] = after_position
"""
    return run_remote_json(client, "snap_no_write", body, raw_dir)


def validate_changed(result: dict, keys: list[str]) -> str:
    changed = []
    unchanged = []
    for key in keys:
        before = result.get("before", {}).get(key)
        after = result.get("after", {}).get(key)
        if before != after:
            changed.append(key)
        else:
            unchanged.append(key)
    parts = []
    if changed:
        parts.append("changed: " + ", ".join(changed))
    if unchanged:
        parts.append("unchanged: " + ", ".join(unchanged))
    return "; ".join(parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a comprehensive smoke test against mesoSPIM remote scripting."
    )
    parser.add_argument(
        "--profile",
        choices=("safe", "full-demo"),
        default="full-demo",
        help=(
            "Test profile. 'full-demo' is the default and exercises all demo-mode "
            "remote scripting paths. 'safe' avoids motion/zoom/snap."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=42000)
    parser.add_argument(
        "--token",
        default=os.environ.get("MESOSPIM_REMOTE_TOKEN"),
        help="Remote scripting token. Defaults to MESOSPIM_REMOTE_TOKEN. Omit only when the server has no token.",
    )
    parser.add_argument(
        "--no-token",
        action="store_true",
        help="Connect without authentication. Use only if the remote scripting dialog token is blank.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Socket timeout in seconds. Full demo zoom tests can take several seconds.",
    )
    parser.add_argument("--raw-dir", type=Path, default=None, help="Optional directory for raw remote replies.")
    parser.add_argument(
        "--allow-non-demo",
        action="store_true",
        help="Allow running even if the remote stage is not mesoSPIM_DemoStage.",
    )
    parser.add_argument(
        "--show-remote-output",
        action="store_true",
        help="Print stdout/stderr emitted by each script inside mesoSPIM.",
    )
    parser.add_argument("--no-restore", action="store_true", help="Leave changed settings/position at test targets.")
    parser.add_argument(
        "--allow-motion",
        action="store_true",
        help="Test X/Y/Z/F/theta relative moves and restore them unless --no-restore is set.",
    )
    parser.add_argument("--step-um", type=float, default=100.0, help="Relative X/Y/Z/F move in micrometres.")
    parser.add_argument("--theta-step", type=float, default=1.0, help="Relative theta move in degrees.")
    parser.add_argument(
        "--include-zeroing",
        action="store_true",
        help="Test zero/unzero on X. Requires --allow-motion because it changes position readout.",
    )
    parser.add_argument(
        "--include-sample-moves",
        action="store_true",
        help="Test load_sample/unload_sample/center_sample. Demo-safe, but can move real hardware far.",
    )
    parser.add_argument(
        "--include-shutters",
        action="store_true",
        help="Test open_shutters/close_shutters. Demo-safe, but opens/closes real shutters on hardware.",
    )
    parser.add_argument(
        "--include-etl-updates",
        action="store_true",
        help="Test ETL config reload and set_etls_according_to_laser/zoom update paths.",
    )
    parser.add_argument(
        "--include-zoom",
        action="store_true",
        help="Test changing zoom and restore it. Can move focus/objective hardware.",
    )
    parser.add_argument(
        "--include-snap",
        action="store_true",
        help="Test core.snap(write_flag=False). Can trigger camera/illumination hardware.",
    )
    parser.add_argument(
        "--include-camera-binning",
        action="store_true",
        help="Test camera_binning. Avoid on real hardware unless you want to exercise binning changes.",
    )
    return parser


def apply_profile(args: argparse.Namespace) -> None:
    if args.profile == "full-demo":
        args.allow_motion = True
        args.include_zeroing = True
        args.include_sample_moves = True
        args.include_shutters = True
        args.include_etl_updates = True
        args.include_zoom = True
        args.include_snap = True
        args.include_camera_binning = True


def resolve_token(args: argparse.Namespace) -> str | None:
    if args.no_token:
        return None
    if args.token:
        return args.token
    if sys.stdin.isatty():
        token = getpass.getpass("Remote scripting token (leave blank if disabled): ")
        return token or None
    return None


def scrubbed_argv(argv: list[str]) -> str:
    scrubbed = []
    skip_next = False
    for item in argv:
        if skip_next:
            scrubbed.append("<token>")
            skip_next = False
            continue
        if item == "--token":
            scrubbed.append(item)
            skip_next = True
        elif item.startswith("--token="):
            scrubbed.append("--token=<token>")
        else:
            scrubbed.append(item)
    return " ".join(scrubbed)


def print_header(args: argparse.Namespace, restore: bool) -> None:
    print("=" * 78)
    print("mesoSPIM Remote Scripting Full Test")
    print("=" * 78)
    print(f"  {'Command':<24} {scrubbed_argv(sys.argv)}")
    print_kv("Client Python", sys.executable)
    print_kv("Target", f"{args.host}:{args.port}")
    print_kv("Profile", args.profile)
    print_kv("Default behavior", "full demo test suite")
    print_kv("Expected mode", "demo stage")
    print_kv("Token", "provided" if args.token else "off")
    print_kv("Restore changes", restore)
    if args.raw_dir is not None:
        print_kv("Raw replies", args.raw_dir)
    print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    apply_profile(args)
    args.token = resolve_token(args)
    restore = not args.no_restore
    failures = 0
    skipped = 0

    global SHOW_REMOTE_OUTPUT
    SHOW_REMOTE_OUTPUT = args.show_remote_output

    print_header(args, restore)

    tests = []

    def add(name, func):
        tests.append((name, func))

    add("probe", lambda client: test_probe(client, args.raw_dir))
    add("status/control widgets", lambda client: test_controls(client, restore, args.raw_dir))
    add(
        "camera settings",
        lambda client: test_camera_settings(client, args.include_camera_binning, restore, args.raw_dir),
    )
    add("waveform parameters", lambda client: test_waveform_parameters(client, restore, args.raw_dir))

    if args.include_etl_updates:
        add("ETL reload/update", lambda client: test_etl_updates(client, restore, args.raw_dir))

    if args.allow_motion:
        add(
            "stage motion",
            lambda client: test_stage_motion(client, args.step_um, args.theta_step, restore, args.raw_dir),
        )
        add(
            "absolute motion",
            lambda client: test_absolute_motion(client, args.step_um, args.theta_step, restore, args.raw_dir),
        )
        if args.include_zeroing:
            add("zero/unzero", lambda client: test_zero_unzero(client, args.raw_dir))
        if args.include_sample_moves:
            add("sample helper moves", lambda client: test_sample_moves(client, restore, args.raw_dir))
    else:
        skipped += 1
        print_result("SKIP", "stage motion", "pass --allow-motion to test X/Y/Z/F/theta moves")

    if args.include_zeroing and not args.allow_motion:
        skipped += 1
        print_result("SKIP", "zero/unzero", "--include-zeroing requires --allow-motion")
    if args.include_sample_moves and not args.allow_motion:
        skipped += 1
        print_result("SKIP", "sample helper moves", "--include-sample-moves requires --allow-motion")

    if args.include_shutters:
        add("shutter open/close", lambda client: test_shutters(client, restore, args.raw_dir))

    if args.include_zoom:
        add("zoom", lambda client: test_zoom(client, restore, args.raw_dir))
    else:
        skipped += 1
        print_result("SKIP", "zoom", "pass --include-zoom to test objective/zoom changes")

    if args.include_snap:
        add("snap(write_flag=False)", lambda client: test_snap(client, args.raw_dir))
    else:
        skipped += 1
        print_result("SKIP", "snap(write_flag=False)", "pass --include-snap to trigger a no-write snap")

    try:
        with RemoteScriptingClient(args.host, args.port, args.token, args.timeout) as client:
            for name, func in tests:
                started = time.perf_counter()
                print()
                print("-" * 78)
                print(f"Running: {name}")
                try:
                    result = func(client)
                    elapsed = time.perf_counter() - started
                    if name == "probe" and not args.allow_non_demo:
                        stage_class = result.get("stage_class")
                        if stage_class != "mesoSPIM_DemoStage":
                            raise RemoteScriptingError(
                                f"remote stage is {stage_class!r}, expected 'mesoSPIM_DemoStage'; "
                                "this script is demo-only unless --allow-non-demo is set"
                            )
                    print_result("PASS", name, f"{elapsed:.2f}s")
                    print_test_details(name, result)
                except Exception as exc:
                    failures += 1
                    print_result("FAIL", name, str(exc))
    except Exception as exc:
        print_result("FAIL", "connect/auth", str(exc))
        return 2

    print()
    print("=" * 78)
    print("Summary")
    print("=" * 78)
    print_kv("Tests run", len(tests))
    print_kv("Skipped", skipped)
    print_kv("Failures", failures)
    if failures:
        print(f"completed with {failures} failure(s)")
        return 1
    print("completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
