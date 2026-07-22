"""Endpoint + timing for the AI Assistant — its own file so the Remote Control config
stays clean. No secret here: a cloud endpoint names the env var holding its key; a local
endpoint (Ollama/vLLM/LM Studio — OpenAI-compatible) sets BASE_URL and needs none.

Maintainer (2026):
    Thom de Hoog
    Center for Microscopy and Image Analysis
    thom.dehoog@zmb.uzh.ch
    thomdehoog@gmail.com
"""

# The endpoint. Cloud: PROVIDER="google", set MODEL + KEY_ENV.
# Local: PROVIDER="openai-compatible", set MODEL + BASE_URL, leave KEY_ENV None.
PROVIDER = "google"                       # "google" (Gemini/Gemma) or "openai-compatible"
MODEL = "gemini-3.5-flash-lite"           # primary: 250K input tokens/min free tier, native tool-calling
FALLBACK_MODEL = "gemini-3.1-flash-lite"  # rolls over on rate-limit/unavailable; its own separate 250K/min
                                          # quota. Set to None to disable rollover.
KEY_ENV = "GEMINI_API_KEY"
BASE_URL = None

# Alternatives:
#   gemma-4-31b-it            16K TPM, no 503s, but mis-shapes nested args on small models.
#   gemini-flash-latest       higher-TPM alias if a versioned id 404s.
#   Gemma 4 31B, local free:  PROVIDER="openai-compatible"; MODEL="gemma4:31b";
#                             BASE_URL="http://localhost:11434/v1"; KEY_ENV=None  (Ollama >= 0.22, ~20 GB VRAM)

POLL_INTERVAL_S = 0.15
WAIT_CAP_S = 120                          # past this a WAIT op returns "still_running"; the agent
                                          # then polls get_progress (tune — design open question #1)
