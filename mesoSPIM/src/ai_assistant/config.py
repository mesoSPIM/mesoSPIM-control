"""Endpoint presets and timing for the AI Assistant.

The tab's setup offers these providers; choosing one prefills the model (and base URL for
a server), and the operator types the API key into the tab. The key lives in memory for the
session only, never in this file, the microscope config, or a log. An empty key field falls back
to the environment variable named here.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

from pathlib import Path

# vision: the model can be shown a camera frame; the `look` tool sends it one in a side call.
# kind: which Pydantic AI model class is built. "OpenAI-style" is any server speaking the OpenAI
# chat API (Ollama >= 0.22, vLLM, LM Studio, a company gateway) and needs a base URL; a key only
# if that server asks for one. Local model files served by mesoSPIM itself use that same kind.
PROVIDERS = {
    "Gemini": {
        "kind": "google",
        "model": "gemini-3.5-flash-lite",  # 250K input tokens/min free tier, native tool calling
        # No fallback model: a stand-in can obey a note planted in the state readout that the chosen
        # model ignores. A model the operator did not choose is worse than a rate-limit error they
        # can see and retry.
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

# Local mode: model files in a folder, served by mesoSPIM itself (see local.py).
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
CONTEXT_TOO_SMALL_HELP = ("The model server's context window is smaller than one request (about 7,000 tokens). "
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
# A reply with no letter or digit in it (a model can answer a refusal with "_") goes
# back to the model once with this text; a second such reply reaches the operator as the fallback.
EMPTY_REPLY_CHALLENGE = "Your reply is empty: tell the operator in a sentence what happened in this turn."
EMPTY_REPLY_FALLBACK = "The model gave no answer for this turn."
LOCAL_SERVER_TIMEOUT_S = 300  # a 12B file can take minutes to load from a slow disk

# The frame handed to a vision model, binned n x n (one of the Remote Control's FRAME_BINS): 2 keeps
# a 2048-pixel camera frame at 1024 pixels, enough for "is it centred" or "is it saturated".
LOOK_BIN = 2

# Whether the chat lists the commands each answer ran; the Configure box switches it.
SHOW_TOOL_CALLS = False

# Which commands the assistant offers the model. "Regular" is for a user setting up a sample on a
# configured microscope: the sample, the session and the ETL voltages, without the camera, the ETL,
# galvo and laser timing, the generic setting call or the alignment modes. "Full" is everything. A
# command in both sets is the same tool in both, except as REGULAR_ARGS narrows it. TCP and MCP
# always serve every command; this is the assistant only.
# A command not in the set is not offered at all, so the model never sees it. The microscope
# config may choose the start-up profile with the attribute named in TOOLS_CONFIG_KEY.
TOOL_PROFILES = {
    "Regular": {
        # reads and checks
        "hello", "ping", "get_state", "get_state_all", "get_position", "get_config", "get_info",
        "get_limits", "get_capabilities", "get_progress", "get_snapshot", "get_frame", "self_test",
        "get_acquisition_list", "stat_files", "get_disk_space", "check_motion_limits",
        # sample and stage
        "move_absolute", "move_relative", "load_sample", "unload_sample", "center_sample", "zero", "unzero",
        # optics for the session
        "set_laser", "set_intensity", "set_filter", "set_zoom", "set_shutterconfig",
        "open_shutters", "close_shutters",
        # the ETL
        "set_etl", "reload_etl_config", "update_etl_from_laser", "update_etl_from_zoom", "save_etl_config",
        # seeing
        "snap", "start_live", "stop_activity", "stop", "clear_stuck_operation",
        # acquiring
        "set_acquisition_list", "run_acquisition_list", "run_selected_acquisition",
        "preview_acquisition", "acquire_start", "acquire_finish", "time_lapse_start", "time_lapse_stop",
    },
    "Full": None,  # every command
}
# What the assistant tells the model a command is for, where the wire hint is not enough. The
# hint stays as it is for TCP and MCP clients; this is the assistant's tool description only.
TOOL_DESCRIPTIONS = {
    # The wire hints say only "in: none"; a model told "stop the live mode" took stop, which halts
    # the stage and leaves live running.
    "stop": "Stops the stage only; live or an acquisition runs on (stop_activity ends it).",
    "stop_activity": "Ends live, an acquisition or a time lapse.",
    "wait": "End this turn; the request goes on in a new turn when the wait is over, with the result.",
    "update_acquisition_row": "Change named keys of one acquisition row; the rest stays. To rename or edit "
                              "a row use this, never set_acquisition_list.",
    "snap": "Save one frame to the snap folder, without looking at it. To see the sample, call look, "
            "which takes and saves its own snap; never snap and then look. 'Take a snap and tell me / "
            "check / is it ...' is one look call, not a snap.",
    # The wire schema gives the range (0.001 to 5) and no unit, and the GUI shows milliseconds.
    "set_camera": "Camera settings. camera_exposure_time is in SECONDS: 50 ms is 0.05, 500 microseconds is 0.0005.",
}
# The checks that take acquisition rows describe them by reference to set_acquisition_list instead
# of repeating the row schema; the dispatcher validates the rows the same either way.
ROWS_BY_REFERENCE = ("get_disk_space", "check_motion_limits", "acquire_start")
# In Regular, the ETL is set by its voltages only; its delay and ramps are the machine's timing.
REGULAR_ARGS = {"set_etl": ("etl_l_amplitude", "etl_l_offset", "etl_r_amplitude", "etl_r_offset")}
# Arguments the assistant's own code uses and the model never needs, withheld in every tool set.
CODE_ONLY_ARGS = {"get_frame": ("array_side",)}
DEFAULT_TOOL_PROFILE = "Regular"
TOOLS_CONFIG_KEY = "ai_assistant_tools"  # optional attribute of the microscope config: "Regular" or "Full"

# Commands the tab asks the operator about before they run (Run / Cancel), whatever the model was
# told: the stage moves that cross the full range and can collide faster than anyone can react.
# Long runs are not gated in code; the model summarises and asks only when something looks off
# (see manual.md), and Stop microscope ends them.
CONFIRM_FIRST = ("load_sample", "unload_sample", "preview_acquisition", "calibrate")

# What TurnGuard holds a turn to (see assistant.py). The moves and the argument that maps
# axis to number; the commands that end a running activity; and the words by which the dispatcher's
# refusals are told apart. These words must match the refusals in remote_control/: a change of
# wording there silently disarms the guard.
MOVE_ARGS = {"move_absolute": "targets", "move_relative": "deltas"}
STOP_COMMANDS = ("stop", "stop_activity", "time_lapse_stop")
# How often the light on the sample may change within LIGHT_WINDOW_S before the next change waits
# for the operator's Run: twice covers "set it to 30, snap, put it back"; a third is an escalation.
LIGHT_CHANGES_PER_WINDOW = {"set_intensity": 2, "set_camera": 2}
LIGHT_WINDOW_S = 600
LIMIT_REFUSAL = "outside the allowed range"
# The fourth rule: a value a turn sends is the operator's. It counts as theirs when it is in their
# words (this turn or an earlier one, in um or mm, s or ms or us, digits or number words), or made
# from a readout value by an operation they named (double, halve, back to what it was, an amount
# further). Any other value waits for their Run. These commands carry such values; their booleans
# and the arguments below are not values.
VALUE_COMMANDS = ("move_absolute", "move_relative", "set_intensity", "set_camera", "set_etl", "set_galvo",
                  "set_laser_timing", "time_lapse_start", "set_filter", "set_zoom", "set_laser",
                  "set_shutterconfig", "update_etl_from_laser", "update_etl_from_zoom")
NOT_VALUES = ("wait", "update_etl")
UNIT_FACTORS = (1, 1000, 0.001, 0.000001)
DOUBLING_WORDS = ("double", "twice", "verdoppel", "verdubbel")
HALVING_WORDS = ("half", "halve", "halb", "helft")
EARLIER_WORDS = ("back", "before", "previous", "was", "undo", "restore", "zurück", "vorher", "terug")
NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
                "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
                "half": 0.5, "quarter": 0.25}
# Said with every failure that has no advice of its own: the operator asked for a way forward, not
# only the error. It rides on the failure because the manual has no room left for a local model.
FAILURE_ADVICE = ("Tell the operator the cause and propose one fix as a question; do not carry it out until "
                  "they answer. 'Try again' means the same command again.")
# A refusal of a command that names the instrument's options carries the lists, and may be corrected
# from them once; for any other (a folder, a limit) the lists are noise, and the fix is the operator's.
OPTION_COMMANDS = ("set_filter", "set_zoom", "set_laser", "set_shutterconfig", "set_state", "set_acquisition_list",
                   "acquire_start")
OPTIONS_ADVICE = ("configured_options lists the instrument's own values. Correct and retry once only when one of them "
                  "is the same value spelled differently (\"561 nm\" for \"561\"). A different value, even the nearest, "
                  "is not what was asked: tell the operator the cause and propose it as a question; do not set it.")
BUSY_FROM_GUI = "from the GUI"

POLL_INTERVAL_S = 0.15
# A setter answers {} as soon as Core accepts it, and Core applies the value later, on other threads.
# So the assistant reads the keys a setter set until they read as asked or READ_BACK_S passes, and
# the result carries what they read as "changed".
SETTERS = ("set_laser", "set_intensity", "set_filter", "set_zoom", "set_shutterconfig", "set_camera", "set_etl",
           "set_galvo", "set_laser_timing", "set_state")
READ_BACK_S = 3.0
# Every result of an instrument tool ends with the readout keys that changed since the model last
# saw them (the turn's readout, then each result), as "state_changed"; these parts are compared.
TRAIL_KEYS = ("state", "position", "optics", "camera", "etl", "zeroed_axes", "time_lapse",
              "acquisition_list.rows", "acquisition_list.selected_row")
# Nothing of the chat is written to disk: the conversation lives in memory until Clear all or
# Disconnect. A tool result kept for recall_turn is cut to this many characters, an image's base64
# replaced by its size.
RECALL_RESULT_CHARS = 2000
MAX_HISTORY_TURNS = 50  # older turns (and their tool results) are dropped from what the model sees; compaction keeps them cheap
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
RUNS_ON_ITS_OWN_NOTE = ("{what} is under way and ends by itself; get_progress reports on it, stop_activity ends it "
                        "early, and settings and moves are refused until it ends.")
# Scheduled actions: "take a snap every three minutes", "at 15:00 start the list". The model has
# no clock; the tab's timer has one, and fires each due instruction as a turn of its own, through
# the same tools, gate and refusals as anything typed. Stop microscope and Disconnect clear them.
SCHEDULE_MIN_SECONDS = 5
SCHEDULES_MAX = 10
SCHEDULED_TURN = "[scheduled '{name}'] {instruction}"
# What the transcript shows for a turn the machine wrote: the model reads the bracketed text above,
# the operator a muted line that does not look typed.
SCHEDULED_SHOWN = "⏱ Scheduled: {name} · {instruction}"
CONTINUATION_SHOWN = "↻ Request {number} continues: {result}"
# A request (requests.py): a wait leaves one continuation pending, at most WAIT_MAX_S, at most
# CONTINUATIONS_MAX per request; its turn starts with CONTINUATION_TURN. A plan keeps PLAN_STEPS_MAX.
WAIT_MAX_S = 4 * 3600
CONTINUATIONS_MAX = 30
CONTINUATION_TURN = "[continuation of request {number}] {result}"
WAIT_NOTE = "End this turn now with one short sentence; the request continues when the wait is over."
PLAN_STEPS_MAX = 12
# At least this many seconds between requests to the model, for a host with a tight per-minute
# limit; 0 is no spacing. The microscope config may set it with the attribute named here, and a
# provider preset may carry "request_interval_s".
REQUEST_INTERVAL_CONFIG_KEY = "ai_assistant_request_interval_s"
# Measured values through the turn guard (measured.py): off unless the microscope config sets the
# attribute named here to True, after a check on the instrument with an operator present.
MEASURED_VALUES_CONFIG_KEY = "ai_assistant_measured_values"
MEASURED_TOLERANCE = 0.2
MEASURED_SLACK_UM = 5.0     # how much one image direction's offset may grow while the whole shrinks
MEASURED_MOVES_MAX = 8
MEASURED_FOCUS_STEP_UM = 100
MEASURED_FOCUS_RANGE_UM = 300
MEASURED_LIGHT_FACTOR = 2
MEASURED_SECTION = (
    "\n\n# Measured values\n\nOn this microscope a value that follows from a fresh measurement goes "
    "through without the operator's Run: a centring move equal to the newest frame's centre_move_um, while "
    "each next offset is smaller; a focus move to the map's best focus, or a search step of at most 100 um "
    "within 300 um of where the request began; an intensity or exposure within a factor of two of the "
    "frame's. Fresh means the frame was taken after the last move or setting, so look after each one. "
    "Anything else still waits for Run.")
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
