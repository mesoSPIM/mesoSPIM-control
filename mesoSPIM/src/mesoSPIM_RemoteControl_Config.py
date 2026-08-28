"""Shared configuration for the mesoSPIM Remote Control feature.

This module is the single source of truth for protocol identity, network defaults, wire limits,
timeouts, hardware parameter ranges, command vocabulary, and operation-completion milestones.
Keeping those values together makes safety limits easy to review and prevents TCP, MCP, the
dispatcher, and the GUI from quietly using different defaults.

The module contains data only. It does not import Qt, open sockets, validate commands, or interact
with microscope hardware, so every other Remote Control module can import it safely.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

# --- identity ---
APP_NAME = "mesoSPIM-control"
PROTOCOL_VERSION = 1
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "mesoSPIM MCP server"
MCP_SERVER_VERSION = "1.0"

# Value used for the HTTP Server response header.
MCP_SERVER_BANNER = "mesoSPIM-MCP/1.0"

# The MCP `initialize` result includes these instructions so every client receives the same safe
# startup and completion workflow before it calls a microscope command.
MCP_INSTRUCTIONS = (
    "You are controlling a mesoSPIM light-sheet microscope over a validated named-call API. "
    "Call get_manual first: it returns the full command reference, workflows, typed errors, and "
    "completion contract. An ordinary mutation returns an operation; poll get_progress until its "
    "status is 'completed' or 'failed', and never infer completion from elapsed time. Emergency "
    "commands execute immediately and do not create a new operation. Read get_info and get_limits "
    "before mutating, and never exceed a limit get_limits reports."
)

# --- network ---
# Loopback is the safe default. Any other address exposes the service to a network.
DEFAULT_HOST = "127.0.0.1"
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
DEFAULT_TCP_PORT = 42000
DEFAULT_MCP_PORT = 42100
ALLOWED_ORIGINS = ("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")

# --- wire ---
ENCODING = "utf-8"
OK_MARKER = "__MESOSPIM_OK__"
# One mebibyte is the largest accepted TCP frame or MCP request body.
MAX_FRAME_BYTES = 1 << 20
MAX_FRAME_HEADER_BYTES = 16
MAX_MCP_BODY_BYTES = 1 << 20
RECV_CHUNK_BYTES = 4096
MAX_ACQUISITION_PLANES = 1_000_000

# --- timeouts (seconds) ---
CLIENT_TIMEOUT_SEC = 10.0

# Limit only the wait while a network request is being marshalled onto the Core thread.
DISPATCH_TIMEOUT_SEC = 30.0

# --- Operator-selected transport defaults ---
# The GUI offers both modes, while Servers binds exactly one mode per session.
TRANSPORT_MODES = ("TCP", "MCP")
DEFAULT_MODE = "TCP"

# This public placeholder is convenient on loopback. Server startup refuses to use it on a
# non-loopback host because the value is visible in the repository.
DEFAULT_TOKEN = "smart_mesospim"

# --- parameter ranges ---
PERCENT_RANGE = (0, 100)

# Bounds for the hardware-affecting numeric settings that are NOT percentages — voltages, a
# frequency, a phase, and the camera/scan timings. Values match the upstream GUI spin-box ranges
# (mesoSPIM_MainWindow.ui), converted to Core's native units. Camera exposure and sweep time are
# displayed in milliseconds but stored in seconds. Every remotely settable numeric hardware value
# has a range; settings without a trustworthy bound are intentionally not exposed.
PARAMETER_RANGES = {
    "etl_l_amplitude": (0.0, 2.0),
    "etl_r_amplitude": (0.0, 2.0),
    "etl_l_offset": (0.0, 5.0),
    "etl_r_offset": (0.0, 5.0),
    "galvo_l_amplitude": (0.0, 5.0),
    "galvo_l_frequency": (0.0, 400.0),
    "galvo_r_frequency": (0.0, 400.0),
    "galvo_l_offset": (-5.0, 5.0),
    "galvo_r_offset": (-5.0, 5.0),
    "galvo_l_phase": (0.0, 360.0),
    "galvo_r_phase": (0.0, 360.0),
    "camera_exposure_time": (0.001, 5.0),
    "sweeptime": (0.010, 10.0),
}

# --- completion milestones ---
MILESTONE_FINISHED = "finished"
MILESTONE_TIMELAPSE = "time_lapse"
MILESTONE_PREVIEW = "preview_returned_idle"
MILESTONE_POSITION = "position_reached"

# Stage moves are issued without blocking the Core thread. A short Qt timer checks mesoSPIM's
# normal position readback until every requested axis is within tolerance. Linear axes use um;
# theta uses degrees.
POSITION_POLL_INTERVAL_MS = 50
POSITION_TOLERANCE = {"x": 1.0, "y": 1.0, "z": 1.0, "f": 1.0, "theta": 1.0}

# --- environment variable names (the reading lives in Commands) ---
LIMITS_ENV_VAR = "MESOSPIM_RS_LIMITS"

# --- vocabulary ---
AXES = ("x", "y", "z", "f", "theta")

MODES = (
    "live",
    "snap",
    "run_selected_acquisition",
    "run_acquisition_list",
    "preview_acquisition_with_z_update",
    "preview_acquisition_without_z_update",
    "idle",
    "lightsheet_alignment_mode",
    "visual_mode",
)

DEFAULT_SHUTTER_OPTIONS = ("Left", "Right", "Both")

# "state" is deliberately NOT settable here: routing it through the generic setter re-opens the
# blocking-mode path set_mode's removal closed (a mode change would run synchronously as an ACTION
# and time out while the hardware keeps going). Use the dedicated start_*/run_*/preview commands.
SETTABLE_STATE_KEYS = (
    "filter",
    "zoom",
    "laser",
    "intensity",
    "shutterconfig",
    "camera_exposure_time",
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
    "camera_display_live_subsampling",
    "camera_display_acquisition_subsampling",
    "camera_binning",
    "galvo_amp_scale_w_zoom",
)

SETTING_GROUPS = {
    "set_camera": (
        "camera_exposure_time",
        "camera_delay_%",
        "camera_pulse_%",
        "camera_display_live_subsampling",
        "camera_display_acquisition_subsampling",
        "camera_binning",
    ),
    "set_etl": (
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
    ),
    "set_galvo": (
        "galvo_l_frequency",
        "galvo_l_amplitude",
        "galvo_l_offset",
        "galvo_l_duty_cycle",
        "galvo_l_phase",
        "galvo_r_frequency",
        "galvo_r_offset",
        "galvo_r_duty_cycle",
        "galvo_r_phase",
        "galvo_amp_scale_w_zoom",
    ),
    "set_laser_timing": ("laser_l_delay_%", "laser_l_pulse_%", "laser_r_delay_%", "laser_r_pulse_%"),
}

ACQUISITION_FIELDS = (
    "x_pos",
    "y_pos",
    "z_start",
    "z_end",
    "z_step",
    "planes",
    "rot",
    "f_start",
    "f_end",
    "laser",
    "intensity",
    "filter",
    "zoom",
    "shutterconfig",
    "folder",
    "filename",
    "image_writer_plugin",
    "etl_l_offset",
    "etl_l_amplitude",
    "etl_r_offset",
    "etl_r_amplitude",
    "processing",
)

ACQUISITION_AXIS_FIELDS = {
    "x_pos": "x",
    "y_pos": "y",
    "z_start": "z",
    "z_end": "z",
    "f_start": "f",
    "f_end": "f",
    "rot": "theta",
}
ACQUISITION_STRING_FIELDS = ("folder", "filename", "image_writer_plugin", "processing")

ETL_READBACK_KEYS = (
    "ETL_cfg_file",
    "laser",
    "zoom",
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
