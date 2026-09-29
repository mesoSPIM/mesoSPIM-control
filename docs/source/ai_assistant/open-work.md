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

## Noted on 28 September, from a session at the instrument

Six items came up at the instrument that day and were done on the same branch: vision for an
OpenAI-style model with "Same as language model" (the *Can see images* box), a live mode that
does not block settings and moves whoever started it, acquisitions that return once under way so
"stop" can be typed, a scheduler for "every three minutes" and "at 15:00", a request interval for
a host with a tight per-minute limit, and the snap file name in the record of a look. What is
still open from that day:

- **The twenty-six new cases on Gemini 3.5 Flash-Lite: 25 of 26** (28 September; the five
  vision-history cases, thirteen vision cases, two live cases, six schedule cases). The one miss
  was a snap taken right before a look, which the harness counts as a wasted exposure; the same
  case passed in an earlier run. The first run found and fixed two things: the eyes' HTTP client
  refused a second thread, so the eyes now run on a loop of their own, and "take a snap" makes the
  model call `snap`, which saves a file but shows the eyes nothing, so the cases that need the
  eyes say "look". `vision-centre-with-a-convention` passed 2 of 3 runs: the axis reasoning is
  hard for Flash-Lite. The held-out twins: 25 of 26 on the same model, the miss a twin whose
  "have another look" let the model reuse the last frame (reworded). Not yet run on a local model.
- **The coordinate system cases on Gemini 3.5 Flash-Lite**: "up", "closer to the camera" and "to the
  right with x flipped" pass 3 of 3 each; the twins 3 of 3 each after the prompt section gained
  the word-to-sign line ("up is +y, down is -y, ..."); one run used an absolute move for a
  relative request. A local model has not seen them.
- **The full set of 158 on Gemini 3.5 Flash-Lite: 155 of 158** (28 September, after the day's prompt
  changes). The three misses were one pattern: "Take a snap. If the image is ..." made the model
  call snap and then look, a second round trip (on hardware the guard reuses the frame, so not a
  second exposure). The snap tool's description and the manual now name that wording; on a re-run
  of the 29 cases whose prompts say snap, 55 of 58, and the worst case went from 2 of 2 misses to
  1 of 3. The rest of the set passed unchanged, so the eyes, the schedules, the live changes and
  the coordinate section cost nothing elsewhere.
- **All 158 held-out twins on Gemini 3.5 Flash-Lite: 155 of 158**, the same day. One twin asked for
  "two minutes from now" and the model set a clock time two minutes ahead instead of a delay, which
  fires just the same, so that twin now accepts either. The other two are the model's: a look with
  a fresh snap where the last frame would do, and a look to confirm a zoom setting. Both are one
  run each, on cases the original set passes.
- **Bench validation** of the two dispatcher changes on an instrument: a live mode started by the
  assistant releases the operation gate once live runs, and an acquisition returns to the chat as
  soon as the run is under way. Both change what the Remote Control transports see too.
- **"Stop" on the small models.** The `stop` tool halts the stage only; `stop_activity` ends a
  run. The `stop` case now runs with an acquisition in progress and requires it to end; try it on
  the local models. A stop that would end a run the operator started still asks Run / Cancel
  first, on purpose.
- **The inference provider.** Baseten lifts limits by tier only; Fireworks gives 6,000 requests
  a minute with a card and caches the prompt prefix; Groq's gpt-oss-120b has the lowest measured
  time to first token. The prefix is byte-identical, so a provider that caches skips it after the
  first turn, which is most of the wait. The tab needs no change for any of them; a tight limit
  is bridged with `ai_assistant_request_interval_s`.
- **The record as training data.** Each turn's line in `~/mesoSPIM/assistant_traces` has the
  prompt, the readout, the tool calls with their results, the reply, the model, the session and
  the turn; a look's line names the snap file it saw. The full request as the model saw it (the
  manual and the tool schemas) is the same for every turn and reproducible from the version.
