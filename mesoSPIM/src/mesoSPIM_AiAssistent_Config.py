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
# The context window the local server is started with. llama-cpp-python's own default is 2,048
# tokens, less than one request here (about 5,700 tokens of instructions, tools and readout).
# 32K holds a request, twenty turns as compaction keeps them, tool results and a margin; the
# microscope config may set the attribute named in CONTEXT_CONFIG_KEY to another size.
LOCAL_CONTEXT_TOKENS = 32768
CONTEXT_CONFIG_KEY = "ai_assistant_context_tokens"
# A server the operator runs themselves may not be so generous: Ollama loads a GGUF model with a
# 4,096-token window unless told otherwise and refuses every request here outright. These are the
# words llama.cpp and Ollama refuse with; the help is what the tab shows in front of them.
CONTEXT_TOO_SMALL_SIGNS = ("exceed_context_size", "exceeds the available context size")
CONTEXT_TOO_SMALL_HELP = ("The model server's context window is smaller than one request (about 6,000 tokens). "
                          "Give it 16,384 or more: for Ollama, OLLAMA_CONTEXT_LENGTH=16384 on the server, or a "
                          "copy of the model made with PARAMETER num_ctx 16384")
LOCAL_BATCH_TOKENS = 2048      # prompt batches: the ~5,700-token prefix is processed in fewer passes than at 512
LOCAL_FLASH_ATTENTION = True   # smaller KV cache and faster attention where the build supports it

# Sampling and retries for every model, cloud or local: an agent that drives an instrument
# wants the most likely tool call, not a creative one, and a small model's malformed call is
# handed back to it a couple of times before the turn fails.
MODEL_TEMPERATURE = 0.0
TOOL_CALL_RETRIES = 2
# A reply at the end of a turn that called no tool goes back to the model once with this text
# (see _challenge_a_reply_that_called_nothing); empty switches the check off.
CALLED_NOTHING_CHALLENGE = (
    "No tool was called in this turn, so nothing at the microscope has changed. If your reply says or implies that "
    "you did, set, moved, stopped, opened or closed anything, that is not true yet: call the tool now. If your "
    "reply only answers, asks the operator a question, or declines, answer with the single word SAME and your "
    "reply goes to the operator as it is.")
LOCAL_SERVER_TIMEOUT_S = 300  # a 12B file can take minutes to load from a slow disk

# The frame handed to a vision model: longer side in pixels.
LOOK_IMAGE_SIZE = 1024

# Whether the chat lists the commands each answer ran; the Configure box switches it.
SHOW_TOOL_CALLS = False

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
# What the assistant tells the model a command is for, where the wire hint is not enough. The
# hint stays as it is for TCP and MCP clients; this is the assistant's tool description only.
TOOL_DESCRIPTIONS = {
    "snap": "Save one frame to the snap folder, without looking at it. To see the sample, call look, "
            "which takes its own snap; never snap and then look.",
    # The wire schema gives the range (0.001 to 5) and no unit, and the GUI shows milliseconds.
    "set_camera": "Camera settings. camera_exposure_time is in SECONDS: 50 ms is 0.05, 500 microseconds is 0.0005.",
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

# What TurnGuard holds a turn to (see mesoSPIM_AiAssistent). The moves and the argument that maps
# axis to number; the commands that end a running activity; and the words by which the dispatcher's
# refusals are told apart. test_ai_assistent.py pins those words to the real refusals, so a change
# of wording there fails a test here instead of silently disarming the guard.
MOVE_ARGS = {"move_absolute": "targets", "move_relative": "deltas"}
STOP_COMMANDS = ("stop", "stop_activity", "time_lapse_stop")
# How often one turn may change the light on the sample before the next change waits for the
# operator's Run: twice covers "set it to 30, snap, put it back"; a third is an escalation.
LIGHT_CHANGES_PER_TURN = {"set_intensity": 2, "set_camera": 2}
LIMIT_REFUSAL = "outside the allowed range"
# Said with every failure that has no advice of its own: the operator asked for a way forward, not
# only the error. It rides on the failure because the manual has no room left for a local model.
FAILURE_ADVICE = ("Unless configured_options holds the value that was meant, tell the operator the cause and "
                  "propose one fix as a question; do not carry it out until they answer. 'Try again' means "
                  "the same command again.")
BUSY_FROM_GUI = "from the GUI"

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
