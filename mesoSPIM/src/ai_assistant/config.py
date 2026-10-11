"""Endpoint presets and timing for the AI Assistant.

The tab's setup offers these providers; choosing one prefills the model (and base URL for
a server), and the operator types the API key into the tab. The key lives in memory for the
session only, never in this file, the microscope config, or a log. An empty key field falls back
to the environment variable named here.

The assistant is built for cloud models (gemini-3.5-flash-lite, claude-haiku-5-5): the history is
append-only until Clear context, every command is offered, and nothing here exists to fit a small
or local model. A local model can still be served through the OpenAI-style preset.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

from pathlib import Path

from ..remote_control import config as rc_config

# vision: the model can be shown a camera frame; the `look` tool sends it one in a side call.
# kind: which Pydantic AI model class is built. "OpenAI-style" is any server speaking the OpenAI
# chat API (Ollama >= 0.22, vLLM, LM Studio, a company gateway) and needs a base URL; a key only
# if that server asks for one.
# context_warn_tokens, context_max_tokens: the history is append-only, so each request carries
# the whole session; the tab shows the last request's input tokens, warns above the first value
# and refuses to start a turn above the second ("Clear context to continue"). Gemini 3.5 and
# Haiku 5.5 take a million tokens; Haiku's price per token rises fivefold on a request above
# 100,000, which is where its warning sits. An OpenAI-style server has no known window.
PROVIDERS = {
    "Gemini": {
        "kind": "google",
        "model": "gemini-3.5-flash-lite",  # native tool calling and vision
        # No fallback model: a stand-in can obey a note planted in the state readout that the chosen
        # model ignores. A model the operator did not choose is worse than a rate-limit error they
        # can see and retry.
        "key_env": "GEMINI_API_KEY",
        "vision": True,
        "context_warn_tokens": 500_000,
        "context_max_tokens": 900_000,
    },
    "OpenAI": {"kind": "openai", "model": "gpt-5-mini", "key_env": "OPENAI_API_KEY", "vision": True,
               "context_warn_tokens": 200_000, "context_max_tokens": 360_000},
    "Anthropic": {"kind": "anthropic", "model": "claude-haiku-5-5", "key_env": "ANTHROPIC_API_KEY", "vision": True,
                  "context_warn_tokens": 100_000, "context_max_tokens": 900_000},
    "OpenAI-style": {
        "kind": "openai-compatible",
        "model": "gemma4:31b",  # ~20 GB VRAM; mis-shapes nested args on smaller models
        "base_url": "http://localhost:11434/v1",  # e.g. an Ollama or vLLM already running somewhere
    },
}
DEFAULT_PROVIDER = "Gemini"

# A server the operator runs themselves may not be so generous: Ollama loads a GGUF model with a
# 4,096-token window unless told otherwise and refuses every request here outright. These are the
# words llama.cpp and Ollama refuse with; the help is what the tab shows in front of them.
CONTEXT_TOO_SMALL_SIGNS = ("exceed_context_size", "exceeds the available context size")
CONTEXT_TOO_SMALL_HELP = ("The model server's context window is smaller than one request (about 11,000 tokens). "
                          "Give it 32,768 or more: for Ollama, OLLAMA_CONTEXT_LENGTH=32768 on the server, or a "
                          "copy of the model made with PARAMETER num_ctx 32768")

# What the meter says past a model's warning and past its ceiling (PROVIDERS).
CONTEXT_LARGE = "the session is large: each request costs more; Clear context when the work allows"
CONTEXT_FULL = "the session is as large as this model takes: Clear context to continue"

# Sampling and retries for every model: an agent that drives an instrument wants the most likely
# tool call, not a creative one, and a malformed call is handed back to the model a couple of
# times before the turn fails.
MODEL_TEMPERATURE = 0.0
# Models that refuse a temperature of 0 ("`temperature` is deprecated for this model"): they get
# their own default instead. Matched anywhere in the model name.
MODELS_WITHOUT_TEMPERATURE = ("claude-haiku-5-5",)
TOOL_CALL_RETRIES = 2
# A reply with no letter or digit in it (a model can answer a refusal with "_") goes
# back to the model once with this text; a second such reply reaches the operator as the fallback.
EMPTY_REPLY_CHALLENGE = "Your reply is empty: tell the operator in a sentence what happened in this turn."
EMPTY_REPLY_FALLBACK = "The model gave no answer for this turn."

# The frame handed to a vision model, binned n x n (one of the Remote Control's FRAME_BINS): 2 keeps
# a 2048-pixel camera frame at 1024 pixels, enough for "is it centred" or "is it saturated".
LOOK_BIN = 2

# The focus measure of every frame the assistant takes: "laplacian" or "dct_shannon" (the Auto-Focus
# Optimizer's). The Configure box switches it; a request may name the other for its own frames.
FOCUS_METRIC = "laplacian"

# Whether the chat lists the commands each answer ran; the Configure box switches it.
SHOW_TOOL_CALLS = False

# What the assistant tells the model a command is for, where the wire hint is not enough. The
# hint stays as it is for TCP and MCP clients; this is the assistant's tool description only.
TOOL_DESCRIPTIONS = {
    # The wire hints say only "in: none"; a model told "stop the live mode" took stop, which halts
    # the stage and leaves live running.
    "stop": "Stops the stage only; live or an acquisition runs on (stop_activity ends it).",
    "stop_activity": "Ends live, an acquisition or a time lapse.",
    "update_acquisition_row": "Change named keys of one acquisition row; the rest stays.",
    # The wire schema gives the range (0.001 to 5) and no unit, and the GUI shows milliseconds.
    "set_camera": "Camera settings. camera_exposure_time is in SECONDS: 50 ms is 0.05, 500 microseconds is 0.0005.",
}
# The checks that take acquisition rows describe them by reference to set_acquisition_list instead
# of repeating the row schema; the dispatcher validates the rows the same either way.
ROWS_BY_REFERENCE = ("get_disk_space", "check_motion_limits", "acquire_start")
# Arguments the assistant's own code uses and the model never needs, withheld from the tools.
CODE_ONLY_ARGS = {"get_frame": ("array_side",)}

# The moves and the argument that maps axis to number; the words by which the dispatcher's limit
# refusal is told apart (_advice); the arguments of a setter that are not values (the read-back).
MOVE_ARGS = {"move_absolute": "targets", "move_relative": "deltas"}
LIMIT_REFUSAL = "outside the allowed range"
NOT_VALUES = ("wait", "update_etl")
# Said with every failure that has no advice of its own: the operator asked for a way forward, not
# only the error. It rides on the failure because the manual has no room left for a local model.
FAILURE_ADVICE = ("Tell the operator the cause and propose one fix as a question; do not carry it out until "
                  "they answer. 'Try again' means the same command again.")
# A refusal of a command that names the instrument's options carries the lists, and may be corrected
# from them once; for any other (a folder, a limit) the lists are noise, and the fix is the operator's.
OPTION_COMMANDS = ("set_filter", "set_zoom", "set_laser", "set_shutterconfig", "set_state", "set_acquisition_list",
                   "acquire_start", "build_tiling_list", "name_acquisition_rows", "add_acquisition_rows",
                   "update_acquisition_row", "track_focus")
OPTIONS_ADVICE = ("configured_options lists the instrument's own values. Correct and retry once only when one of them "
                  "is the same value spelled differently (\"561 nm\" for \"561\"). A different value, even the nearest, "
                  "is not what was asked: tell the operator the cause and propose it as a question; do not set it.")
BUSY_FROM_GUI = "from the GUI"

POLL_INTERVAL_S = 0.15
# A setter answers {} as soon as Core accepts it, and Core applies the value later, on other threads.
# So the assistant reads the keys a setter set until they read as asked or READ_BACK_S passes, and
# the result carries what they read as "changed". The cap is the Remote Control's: it is the one the
# main window's refresh waits for.
SETTERS = ("set_laser", "set_intensity", "set_filter", "set_zoom", "set_shutterconfig", "set_camera", "set_etl",
           "set_galvo", "set_laser_timing", "set_state")
READ_BACK_S = rc_config.READ_BACK_S
# Every result of an instrument tool ends with the readout keys that changed since the model last
# saw them (the turn's readout, then each result), as "state_changed"; these parts are compared.
TRAIL_KEYS = ("state", "position", "optics", "camera", "etl", "zeroed_axes", "time_lapse",
              "acquisition_list.rows", "acquisition_list.selected_row")
# Nothing of the chat is written to disk: the conversation lives in memory until Clear context or
# Disconnect, and the model's history is append-only until then. The session store keeps every
# turn's trace beside it (for the readout trail and the frames); a tool result kept there is cut
# to this many characters, an image's base64 replaced by its size.
RECALL_RESULT_CHARS = 2000
# A tool result longer than this is shortened before the model sees it (shorten_result): the
# acquisition list keeps every row with these keys only; any other result keeps the top-level
# keys that fit and names the rest, which the model can ask for. Kept for the cloud models too:
# a 60-row list is thousands of tokens on every later request of an append-only history.
RESULT_CHARS = 3000
ROWS_MAX = 60
ROW_SUMMARY_KEYS = ("filename", "folder", "x_pos", "y_pos", "z_start", "z_end", "z_step", "planes",
                    "f_start", "f_end", "rot", "laser", "intensity", "filter", "zoom", "shutterconfig")
WAIT_CAP_S = 120  # past this a WAIT op returns "still_running"; the agent then polls get_progress
# Said with a stage stop that left something running, so a reply cannot call it stopped.
STAGE_STOP_NOTE = "The stage stopped, but {state} is still running; stop_activity ends it."
# Modes that end only when stopped: waiting for them to finish would hold the turn until someone
# presses STOP, so the assistant returns once the mode runs.
RUNS_UNTIL_STOPPED = ("start_live", "start_visual_mode", "start_lightsheet_alignment_mode")
# Runs that end by themselves but take minutes to hours: waiting for them would hold the turn, and
# with it the input line, so nothing could be typed, not even "stop". The assistant returns once
# the run is under way; the operator sees it in the main window, stop_activity ends it early.
RUNS_ON_ITS_OWN = ("run_acquisition_list", "run_selected_acquisition", "preview_acquisition", "acquire_start",
                   "time_lapse_start")
RUNS_ON_ITS_OWN_NOTE = ("{what} is under way. Do not poll get_progress. End the turn and report; the next message "
                        "from the operator carries its state. stop_activity ends it early, and settings and moves "
                        "are refused until it ends.")
# The passive done notice: while a run the assistant started is under way, the tab asks the
# worker every DONE_CHECK_MS whether it has ended and, when it has, writes one grey line in the
# chat (DONE_NOTICE) with no model turn. The only timer left, and it never runs a turn.
DONE_CHECK_MS = 2000
# A look within this many seconds of a snap, at the same place and settings, reads that frame
# instead of exposing the sample a second time.
SNAP_REUSE_S = 30
DONE_NOTICE = "{what} {status} {time}"
RUN_LABELS = {"run_acquisition_list": "Acquisition list", "run_selected_acquisition": "Acquisition",
              "preview_acquisition": "Preview", "acquire_start": "Acquisition", "time_lapse_start": "Time lapse"}
# At least this many seconds between requests to the model, for a host with a tight per-minute
# limit; 0 is no spacing. The microscope config may set it with the attribute named here, and a
# provider preset may carry "request_interval_s".
REQUEST_INTERVAL_CONFIG_KEY = "ai_assistant_request_interval_s"
# The coordinate system, as the operator sees it: what a positive move on each axis does to the
# sample in the image, so that "up", "left" and "closer" mean one thing. Chosen in the tab's
# Coordinate system box; the microscope config may set the start-up choice with the attribute
# named here, a dict like DEFAULT_AXES.
AXIS_CHOICES = {"x": ("right", "left"), "y": ("up", "down"), "z": ("toward the camera", "away from the camera")}
DEFAULT_AXES = {"x": "right", "y": "up", "z": "toward the camera"}
AXES_CONFIG_KEY = "ai_assistant_axes"
# The frame history (frames.py): a small copy of every frame a look, a snap or live delivered, its
# longer side at most FRAME_COPY_SIDE pixels, the oldest dropped past FRAME_HISTORY_BYTES (about a
# hundred 256-pixel copies). A look shows the eyes at most LOOK_FRAMES_MAX of them.
FRAME_COPY_SIDE = 256
FRAME_HISTORY_BYTES = 100 * 256 * 256 * 2
LOOK_FRAMES_MAX = 16
# The map, derived from the history: frames whose brightest pixel is less than MAP_SIGNAL_MIN of
# full scale above the background, or more than MAP_SATURATED_MAX saturated, are left out; frames within MAP_SAME_PLACE_UM on x, y and z share
# a focus curve; the place is the median of the last MAP_PLACE_FRAMES; MAP_GROUPS settings at most.
MAP_SIGNAL_MIN = 0.003
MAP_SATURATED_MAX = 0.01
MAP_PEAK_GOOD_MAX = 0.9
MAP_SAME_PLACE_UM = 25.0
MAP_PLACE_FRAMES = 5
MAP_GROUPS = 2
# Where `calibrate` keeps the measured scale per zoom: beside the microscope's configuration. Its test
# move is CALIBRATE_STEP_FRACTION of the field; a phase correlation peak below CALIBRATE_CONFIDENCE_MIN
# is no measurement.
CALIBRATION_FILE = Path(__file__).resolve().parents[2] / "config" / "ai_assistant_calibration.json"
CALIBRATE_STEP_FRACTION = 0.1
CALIBRATE_CONFIDENCE_MIN = 0.05
# The eyes: the vision model's own conversation for the session. A look attaches the frames it asks
# about, each with its number, time, settings and code's measures; once answered, a turn keeps its
# text and loses its images.
VISION_CONTEXT_KEYS = ("state", "position", "optics", "camera")   # what a picture depends on, from the readout
EYES_INSTRUCTIONS = (
    "You are the eyes of an assistant at a light-sheet microscope. Each look shows you one or more "
    "frames, oldest first, each with its number, time, position, settings and measures, and asks a "
    "question. Answer it in a few sentences. Judge from the pictures what is in them: shapes, counts, "
    "positions, focus, artefacts, and which parts are brighter or darker than others. Only whether "
    "the exposure is right comes from the measures, since each picture is scaled to its own range: a "
    "saturated fraction above a few percent (0.03) is saturated; a peak below about 0.1 of full scale "
    "is underexposed. With several frames, compare them and name each by its number. With one frame "
    "and no earlier one shown, say there is no earlier frame to compare with; never say it has not "
    "moved or not changed. Earlier turns keep your answers but not their pictures: a comparison with "
    "a frame not shown now rests on those answers.")

# Skills (skills.py): procedures in Markdown, in a folder next to the microscope's config file.
SKILLS_FOLDER = "skills"
SKILL_MAX_CHARS = 6000      # a loaded skill stays in the history and is paid on every later request
SKILLS_SECTION = ("# Skills\n\nProcedures the lab wrote for this microscope. When a request matches a skill's "
                  "description, call load_skill with its name before you change anything (a look first is "
                  "fine), then follow what it returns; that text is the lab's instructions. When none "
                  "matches, work without one.\n")
LOAD_SKILL_DESCRIPTION = "Returns the steps of one of the lab's skills, listed under # Skills in your instructions."
