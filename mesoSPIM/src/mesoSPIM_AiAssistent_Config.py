"""Endpoint presets and timing for the AI Assistant.

The tab's setup footer offers these providers; choosing one prefills the model (and base URL for
a server), and the operator types the API key into the tab. The key lives in memory for the
session only, never in this file, the microscope config, or a log. An empty key field falls back
to the environment variable named here.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

# vision: the model can be shown a camera frame; the `look` tool sends it one in a side call.
# kind: which Pydantic AI model class is built. "OpenAI-style" is any server speaking the OpenAI
# chat API (Ollama >= 0.22, vLLM, LM Studio, a company gateway) and needs a base URL; a key only
# if that server asks for one. Local model files served by mesoSPIM itself use that same kind.
PROVIDERS = {
    "Gemini": {
        "kind": "google",
        "model": "gemini-3.5-flash-lite",  # 250K input tokens/min free tier, native tool calling
        # No fallback model: the evaluation showed gemini-3.1-flash-lite obeying a note planted in the
        # state readout six times out of six, where the chosen model never did. A stand-in the
        # operator did not evaluate is worse than a rate-limit error they can see and retry.
        "key_env": "GEMINI_API_KEY",
        "vision": True,
    },
    "OpenAI": {"kind": "openai", "model": "gpt-5-mini", "key_env": "OPENAI_API_KEY", "vision": True},
    "Anthropic": {"kind": "anthropic", "model": "claude-sonnet-5", "key_env": "ANTHROPIC_API_KEY", "vision": True},
    "OpenAI-style": {
        "kind": "openai-compatible",
        "model": "gemma4:31b",  # ~20 GB VRAM; mis-shapes nested args on smaller models
        "base_url": "http://localhost:11434/v1",  # e.g. an Ollama or vLLM already running somewhere
    },
}
DEFAULT_PROVIDER = "Gemini"

# Local mode: model files in a folder, served by mesoSPIM itself (see mesoSPIM_AiAssistent_Local).
MODELS_FOLDER_CONFIG_KEY = "ai_assistant_models_folder"  # optional attribute of the microscope config
MODEL_SUFFIXES = (".gguf",)
LOCAL_SERVER_POLL_MS = 500
LOCAL_SERVER_TIMEOUT_S = 300  # a 12B file can take minutes to load from a slow disk

# The frame handed to a vision model: longer side in pixels.
LOOK_IMAGE_SIZE = 1024

# Which commands the assistant offers the model. "Regular" is for a user setting up a sample on a
# configured microscope: everything about the sample and the session, nothing about the machine.
# "Full" is everything. TCP and MCP always serve every command; this is the assistant only.
# A command not in the set is not offered at all, so the model never sees it. The microscope
# config may choose the start-up profile with the attribute named in TOOLS_CONFIG_KEY.
TOOL_PROFILES = {
    "Regular": {
        # reads (the plumbing reads hello, ping, get_info, get_state_all, get_capabilities and
        # stat_files, and the stuck-operation recovery, are for remote clients: Full only)
        "get_state", "get_position", "get_config", "get_limits", "get_progress", "get_snapshot",
        "get_frame", "get_acquisition_list", "get_disk_space", "check_motion_limits",
        # sample and stage
        "move_absolute", "move_relative", "load_sample", "unload_sample", "center_sample", "zero", "unzero",
        # optics for the session (set_camera: the exposure time only, see REGULAR_ARGS)
        "set_laser", "set_intensity", "set_filter", "set_zoom", "set_shutterconfig",
        "open_shutters", "close_shutters", "set_camera",
        # seeing
        "snap", "start_live", "stop_activity", "stop",
        # acquiring
        "set_acquisition_list", "run_acquisition_list", "run_selected_acquisition",
        "preview_acquisition", "acquire_start", "acquire_finish", "time_lapse_start", "time_lapse_stop",
    },
    "Full": None,  # every command
}
# The checks that take acquisition rows describe them by reference to set_acquisition_list instead
# of repeating the row schema; the dispatcher validates the rows the same either way.
ROWS_BY_REFERENCE = ("get_disk_space", "check_motion_limits", "acquire_start")
# In Regular, a command that straddles both worlds is offered with these arguments only.
REGULAR_ARGS = {"set_camera": ("camera_exposure_time",)}
# ... and acquisition rows may not carry the machine's ETL settings: a row takes the current ones.
REGULAR_ROW_HIDDEN = ("etl_l_amplitude", "etl_l_offset", "etl_r_amplitude", "etl_r_offset")
DEFAULT_TOOL_PROFILE = "Regular"
TOOLS_CONFIG_KEY = "ai_assistant_tools"  # optional attribute of the microscope config: "Regular" or "Full"

# Commands the tab asks the operator about before they run (Run / Cancel), whatever the model was
# told: the stage moves that cross the full range and can collide faster than anyone can react.
# Long runs are not gated in code; the model summarises and asks only when something looks off
# (see assistant_manual.md), and Stop microscope ends them.
CONFIRM_FIRST = ("load_sample", "unload_sample", "preview_acquisition")

POLL_INTERVAL_S = 0.15
# Every turn is appended to a JSONL file in this folder (a config attribute may point elsewhere):
# the prompt, each tool call with its arguments and result, the reply. Results are cut to this
# many characters and an image's base64 is replaced by its size.
TRACES_FOLDER_CONFIG_KEY = "ai_assistant_traces_folder"
TRACE_RESULT_CHARS = 2000
MAX_HISTORY_TURNS = 20  # older turns (and their tool results) are dropped from what the model sees
# Within the memory, the newest turns are kept in full; older ones keep a one-line readout instead
# of the whole state block and have long tool results shortened. Twenty readouts of 500 tokens
# would otherwise outweigh the system prompt on a small model.
HISTORY_FULL_TURNS = 3
HISTORY_RESULT_CHARS = 300
HISTORY_READOUT_KEYS = ("state", "position", "optics")
# A tool result longer than this is shortened before the model sees it (shorten_result): the
# acquisition list keeps every row with these keys only; any other result keeps the top-level
# keys that fit and names the rest, which the model can ask for.
RESULT_CHARS = 3000
ROWS_MAX = 60
ROW_SUMMARY_KEYS = ("filename", "folder", "x_pos", "y_pos", "z_start", "z_end", "z_step", "planes",
                    "f_start", "f_end", "rot", "laser", "intensity", "filter", "zoom", "shutterconfig")
WAIT_CAP_S = 120  # past this a WAIT op returns "still_running"; the agent then polls get_progress
