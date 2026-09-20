# Roadmap to merge

Where the AI Assistant and Remote Control contribution stands, and what is left before it is
proposed for merge. Dated entries; update as phases close.

## This phase: does it behave

Done (21 September 2026):

- The behavioural evaluation against local models on a Mac through Ollama, next to the cloud
  runs: gemma4 12B, 26B-A4B, E4B and E2B, qwen3.5 9B, qwen3-vl 8B, minicpm-v 4.6. The runs and
  what each model does wrong are in `mesoSPIM/test/ai_assistant/evals/runs/`
  (`2026-09-20-local-models-on-a-mac.md`).
- What those runs asked for, in code rather than in the prompt: `TurnGuard` (no other target after
  a move refused for a limit; a stop after a busy from the GUI waits for Run; a third change of the
  intensity or the exposure in one turn waits for Run; a look after a snap reads that frame), a
  reply that called no tool handed back once, and the tab's "no command was sent" line.
- A held-out set of 110 variant cases (`evals/cases_holdout.json`) to tell a change that made the
  assistant better from one that fitted `cases.json`.

To do, at the machines:

- **Demo mode on Windows.** Install from the branch, connect the tab to a cloud model and to a
  local one, see each of the rules above fire once, check that a turn is written to the traces
  folder, and that the repository checks out (the trace file names were made Windows-safe on a
  Mac, where that cannot be shown).
- **The real microscope.** The same rules with safe values, and what only hardware shows: moves
  completing and limits refusing on real axes, `look` on real frames instead of synthetic discs, a
  busy state started from the GUI, Stop microscope in the middle of a turn. Not with a sample that
  matters loaded.

Deferred within this phase: the full 110 cases, and the held-out 110, on the code as it now is.
Only targeted cases were run after the fixes.

Known and open: the standard `gemma4:12b` (GGUF) build loops under Ollama 0.34.2 where it ran all
110 cases under 0.30.7, on the old code too; the MLX builds are not affected. The 12B ranks the
brightness of three spots wrongly whatever the scaling or the wording; the 26B-A4B and qwen3.5 9B
rank them correctly.

## Last phase: is it ready

Two discussions, not more code:

- **The config files.** What the contribution adds to configuration, where each setting lives
  (`mesoSPIM_AiAssistent_Config.py`, `mesoSPIM_RemoteControl_Config.py`, the attributes a
  microscope config may set), which are constants and which an instrument should be able to
  change, and whether that split is the right one.
- **Whether the code is clean enough to merge into mesoSPIM-control.** A critical reading of the
  whole diff against `release/candidate-py312`: what is over-built, what a maintainer would push
  back on, whether it reads like the code around it.
