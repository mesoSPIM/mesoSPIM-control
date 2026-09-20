# Local models on a Mac, 20 September 2026

The 110-case evaluation at commit b5f0a35, from a clean clone on an M-series Mac with 64 GB,
Python 3.12, Ollama through `--provider OpenAI-style --base-url http://localhost:11434/v1`,
`--vision` where Ollama reports the capability, `--pause 0`. gemma4:12b ran on Ollama 0.30.7, the
others on 0.34.2 (the MLX builds need 0.31). The run files are beside this note.

| model | build | pass | handled correctly* | median s | file |
|---|---|---|---|---|---|
| gemini-3.5-flash-lite | cloud | 110 / 110 | 110 | 1.2 | `2026-09-20-gemini-3.5-flash-lite-local-checkout.jsonl` |
| gemma4:12b | GGUF Q4_K_M, 7.6 GB | 106 / 110 | ~109 | 28 | `2026-09-20-gemma4-12b-ollama.jsonl` |
| gemma4:e4b-mlx | MLX nvfp4, 9.5 GB (8.1B stored) | 83 / 110 | ~97 | 4.3 | `2026-09-20-gemma4-e4b-mlx-ollama.jsonl` |
| gemma4:e2b-mlx | MLX, 7.5 GB | 72 / 110 | ~88 | 4.3 | `2026-09-20-gemma4-e2b-mlx-ollama.jsonl` |
| minicpm-v4.6 (1B) | GGUF Q4_K_M, 1.6 GB, num_ctx 16384 | 74 / 110 (62 / 88 and 12 / 22) | 74 | 3 and 6 | `…-minicpm-v4.6-ollama-nonvision.jsonl`, `…-ollama-vision.jsonl` |

\* Read by hand: a failure that is only "a snap right before a look" or only "quotes the
<microscope_state> block" (the tab strips it), or a correct answer the phrase lists do not accept,
is counted as handled; the frame was read and the action taken correctly in those opened.

## What each model does wrong

- **gemma4:12b** — nothing outside vision. One misreading (brightest-spot: it argued that the
  contrast stretch hides relative brightness; the spots are grey 95, 159 and 255 in the PNG). Two
  correct answers the phrase lists reject: "non-uniform background" contains the forbidden
  "uniform background"; "no identifiable sample" is not among the wordings for an empty field.
  Vision turns take 30 to 136 s.
- **gemma4:e4b-mlx** — sees about as well as the 12B, but reports actions it did not take
  ("I have closed the shutters", "I have stopped the live mode", "I have set the intensity to 0",
  no tool call in any of the five), and after a move refused for a limit moves to the edge of
  the range instead (z=999999 refused, then z=25000) and reports success. The limit itself held:
  no model moved the stage outside it. (An earlier version of this note said the stage ended
  outside the limits; that was wrong.) Recites the system prompt when asked.
- **gemma4:e2b-mlx** — no faster than e4b, and vision gives out: four spots for three, a
  gradient called uniform, an empty field described as texture. Asked for a command the Regular
  profile hides (ETL amplitude, galvo) it sets the laser intensity to that number instead. Sends
  500 for 500 microseconds; passes "properties" from the tool schema as an argument, which ends
  the turn.
- **minicpm-v4.6** — misreads (four spots, a cut-off sample "fully inside", "no air bubbles", a
  sample in an empty field) and does not act on a saturated frame. Outside vision none of its 26
  failures is a habit: it never asks when a request is ambiguous (0 of 4), announces a call it does
  not make ("I'll stop everything now … [stop]", no tool call), makes an absolute move for a
  relative one (x to -100), runs the acquisition list when asked only to explain it, and stops a
  running time lapse in order to look. Fast, not trustworthy.

## Things found on the way

- Ollama loads GGUF models with a 4096-token window unless told otherwise and refuses the
  6,100-token request ("exceeds the available context size"); minicpm-v4.6 needed a copy with
  `PARAMETER num_ctx 16384`. The MLX builds show 4096 in `ollama ps` but read a 12,000-token
  prompt whole (five codewords spread through it, all returned), so their failures are their own.
- On Ollama 0.30.7 gemma4:12b-mlx reported no vision; on 0.34.2 the same files do.
- gemma4:12b on Ollama: 17 tokens a second, generation 98% of a request, the 5,400-token prefix
  cached between turns.
- The trace file name takes `{model}` as given, so `gemma4:12b` makes a file name with a colon,
  which Windows cannot check out; these were renamed by hand.

## Later the same day: after the fixes on `assistant-small-model-fixes`

27 targeted and control cases on Ollama 0.34.2 with the new code, `--vision`. Files beside this
note (`…-targeted.jsonl`), scored with the corrected accept-lists.

| model | pass | median s | in one line |
|---|---|---|---|
| gemma4:26b-mlx (18 GB) | 26 / 27 | 14.6 | best local all-rounder; ranks the three spots correctly; its one failure is flailing when halving the intensity does not clear the saturation |
| gemma4:12b-mlx | 23 / 27 | 17.8 | every non-vision action right; quotes the state block now and then; names the first option as the brightest spot whatever the picture shows |
| qwen3.5:9b-mlx (8.9 GB) | 20 / 27 | 23.2 | read all six frames correctly, the best eyes tested (every failure there is a snap before a look); as the driver it invents "20 µm" for "a little" and takes 14 calls to install and run one acquisition |
| qwen3-vl:8b | 10 / 11, stopped | 46.8 | right where tested, far too slow; reasoned for 4 min 26 s into the token limit on one case |
| gemini-3.5-flash-lite | 36 / 36 | 1.2 | the targeted and control cases, after the fixes |

gemma4:e4b-mlx, three repeats, before the fixes against after: 26 to 45 of 51 on the targeted
cases and 72 to 79 of 96 on their held-out variants. The gain that carries over is the reply that
called no tool (time-lapse-stop, intensity-in-words, memory-across-turns go to 3 of 3); the
controls hold; the advice on a limit refusal shows no gain on the held-out limits, which the old
code already passed.

Open when this was written:
- **gemma4:12b-mlx keeps doubling the intensity with the new code.** vision-dim-doubles-intensity:
  the old code doubles once, looks, sees no change (the simulated frame never changes) and
  reports; the new code goes 20, 40, 80, 100 and reports "underexposed even at the maximum". Not
  yet traced to one change. Run that case before trusting the branch on this model.
- The standard gemma4:12b (GGUF) loops on that turn under Ollama 0.34.2 with the old code too; it
  ran all 110 cases under 0.30.7 in the morning.
- Scaling is not why the 12B misjudges the brightest spot: the current stretch, a stretch with
  headroom, no scaling and raw 16 bit were tried. Told the frame was "contrast-stretched" and
  "cannot show exposure" it refused to compare at all, so those words are gone from the vision
  instructions; it now compares, and still names the wrong spot.
