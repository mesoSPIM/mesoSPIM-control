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
# kind: which Pydantic AI model class is built. "openai-compatible" is any server speaking the
# OpenAI chat API (Ollama >= 0.22, vLLM, LM Studio) and needs a base URL instead of a key. Local
# model files served by mesoSPIM itself use that same kind behind the scenes.
PROVIDERS = {
    "Gemini": {
        "kind": "google",
        "model": "gemini-3.5-flash-lite",  # 250K input tokens/min free tier, native tool calling
        "fallback_model": "gemini-3.1-flash-lite",  # rolls over on rate limit; its own quota
        "key_env": "GEMINI_API_KEY",
        "vision": True,
    },
    "OpenAI": {"kind": "openai", "model": "gpt-5-mini", "key_env": "OPENAI_API_KEY", "vision": True},
    "Anthropic": {"kind": "anthropic", "model": "claude-sonnet-5", "key_env": "ANTHROPIC_API_KEY", "vision": True},
    "OpenAI-compatible server": {
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
# The "Vision model" choice that means: the main model reads frames itself (if it can).
SAME_AS_MODEL = "same as model"

# Commands the tab asks the operator about before they run (Run / Cancel), whatever the model was
# told. They move the sample or start a long run. An unanswered question counts as Cancel.
CONFIRM_FIRST = (
    "load_sample",
    "unload_sample",
    "run_acquisition_list",
    "run_selected_acquisition",
    "preview_acquisition",
    "time_lapse_start",
)
CONFIRM_TIMEOUT_S = 120

POLL_INTERVAL_S = 0.15
MAX_HISTORY_TURNS = 20  # older turns (and their tool results) are dropped from what the model sees
WAIT_CAP_S = 120  # past this a WAIT op returns "still_running"; the agent then polls get_progress
