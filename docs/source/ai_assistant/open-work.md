# Open work

What is known to be unfinished.

- **Real hardware.** The assistant has run against demo mode only, on Windows and on macOS. What
  only a microscope shows: moves completing and limits refusing on real axes, `look` on real
  frames, a busy state started from the GUI, Stop microscope in the middle of a turn. Try it first
  with safe values and no sample that matters.
- **A time limit on the model call.** A stalled endpoint holds the turn until the HTTP layer gives
  up (see Limitations); Cancel prompt ends it at once, but nothing ends it on its own.
- **Asking back.** In the last full evaluation of gemini-3.5-flash-lite (126 of 129 cases, 124 of
  the 129 held out), the misses were steps the model chose for a request that gave no value
  ("brighter"), and two of the cases about when to look.
- **Across models.** Three repeats of every model that may face an operator, on a paid tier.
- **Local models.** Under Ollama 0.34.2 the standard `gemma4:12b` (GGUF) build loops, where 0.30.7
  ran it through every case; the MLX builds are not affected. The 12B ranks the brightness of three
  spots wrongly whatever the scaling or the wording; the 26B-A4B and qwen3.5 9B rank them correctly.
