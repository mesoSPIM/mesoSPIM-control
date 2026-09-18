# AI Assistant

An optional chat tab that drives the microscope in natural language. A [Pydantic AI](https://ai.pydantic.dev)
agent turns the Remote Control commands into tools and dispatches them through the **same**
`Acceptor` as the TCP and MCP transports, so every action obeys the existing accept-validation,
movement limits and one-mutation gate. The tab is idle until the operator sends a message, and the
Assistant and a network transport are mutually exclusive — only one controller holds the session.

This builds on [Remote Control](../remote_control/index.md); read that first.

```{toctree}
:maxdepth: 1

design
integration
```

## Requirements

- `pydantic-ai`, declared as the optional extra `ai-assistant`: install with
  `pip install -e ".[ai-assistant]"`. The extra also keeps the `anthropic` SDK below 1.0, whose
  newer client library pydantic-ai 2.14 cannot drive. It is imported lazily, so the application
  starts and every other feature works without it; the tab reports the missing module when the
  operator sends a first message.
- An API key for the chosen provider, or any server that speaks the OpenAI API (Ollama, vLLM, LM Studio).
- For a local model file, `llama-cpp-python`: the extra `ai-assistant-local` installs both.

## Setting it up

The tab opens as a chat. The line under the input box, **Set up AI assistant**, expands to three
boxes, **Preferences**, **Language model** and **Vision model**, with one **Connect** under them,
and opens by itself when something needs the operator: nothing configured yet, a missing key, or
a local model that failed to start. Once the assistant is ready it folds back. Each model box
starts with a **Type** dropdown; the fields after it follow the choice.

**Language model, Cloud AI.** Choose a provider (Gemini, OpenAI, Anthropic, or **OpenAI-style**
for any server that speaks the OpenAI API, such as an Ollama or vLLM already running somewhere, or
a hosted gateway), keep or edit the prefilled model name, and type the API key into the masked
field. OpenAI-style also asks for the server's base URL, and there the key is optional: Ollama
wants none, a gateway or a hosted API wants its token. The key is kept in memory for this mesoSPIM
session only and is never written to the repository, the microscope config, or a log. An empty
field falls back to the provider's environment variable (`GEMINI_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`), so a key exported before starting mesoSPIM keeps working. Any model the
provider serves under that key works by name: under Gemini, for example, `gemini-3.6-flash` or the
open-weight `gemma-4-31b-it`, which the evaluation below has driven the tools with (slower, and
looser on ambiguous requests until the manual spelled the rule out).

**Language model, Local AI.** One **Model** dropdown lists the `.gguf` files in the models folder
(`~/mesoSPIM/models`, or the `ai_assistant_models_folder` attribute of the microscope config;
**Models folder…** points it elsewhere for the session). Download a file from Hugging Face, drop
it in, choose it, Connect. Nothing leaves the machine and no key is needed. Behind Connect,
mesoSPIM serves the file itself with llama.cpp's OpenAI-compatible server (`pip install
llama-cpp-python`, or the `ai-assistant-local` extra) as a child process on a loopback port; the
Connect button reads "Starting…" while the model loads, then turns green with "Connected".
Connecting again, or closing mesoSPIM, stops the child. A server that fails to start is reported
with the path of its log. Use a GPU build of llama-cpp-python for anything above a few billion
parameters; the 4B to 12B instruction models are the realistic range on a microscope PC.

**Vision model.** The model that reads camera frames when the assistant looks. *Same as language
model* (the default) lets the language model read frames itself when it can: the cloud models
can, and a local file can when its projector file (`mmproj-…gguf`) sits beside it in the models
folder, since mesoSPIM serves the two together; a local file without one decides from the numbers
alone. Choosing Cloud AI or Local AI here gives a text-only language model eyes of its own: the
same fields as above, and the frame goes to this model in a separate call with the question, so
the conversation itself never carries images. A local vision model must have its projector file;
choosing the same file in both boxes serves it once. Whether a given local file can see depends
on llama-cpp-python supporting that model family's projector.

**Preferences** apply at once. **Tool set** chooses what the assistant may do: *Regular* (the
default) is for a user setting up a sample on a configured microscope: reads, stage and sample
moves, laser, intensity, filter, zoom, shutters, the camera exposure time, snap, live, and the
acquisition and time lapse commands. *Full* adds the machine: ETL, galvo, laser and camera timing,
the ETL calibration files, the alignment modes and the generic setting call. In Regular the other
commands are not offered to the model at all, so it cannot be talked into them, and an
acquisition row may not carry the ETL settings either (it takes the current ones). The model is
told which commands the set withholds, so a request for one gets "not in this tool set" rather
than a stand-in command dressed up as the result. The start-up
choice can be fixed per microscope with the config attribute `ai_assistant_tools` ("Regular" or
"Full"). TCP and MCP always serve every command; this is the assistant only. **Memory** is how
many of the operator's messages, with their answers, the model remembers. **Downsample image to** is the size of the frame handed to the
vision model (longer side, 1024 px by default): smaller is cheaper and faster, and enough for "is
it centred" or "is it saturated"; the numbers always come from the full frame.

**Connect** applies the three boxes; a first message sent without pressing it applies them as
typed. Building a cloud endpoint does not contact the provider, so a wrong key shows up as an
error on the first message. The models can be changed between turns and the transcript is kept.
The presets live in `mesoSPIM_AiAssistent_Config.py` as defaults only.

## Using it

Open the **AI Assistant** tab and type. Enter or **Send** submits; Shift+Enter starts a new line,
as in an editor. Commands the agent runs stream live above each answer, so
the operator sees exactly which named calls were issued. **Cancel** stops the assistant: no
further tool calls this turn, an open Run / Cancel question is cancelled, and the turn ends at the
model's next reply; what the assistant already started keeps running. **Stop microscope** is
the main window's Stop: the same queued signals to Core (state idle aborts the running mode, the
time lapse is cancelled) plus the stage stop, sent straight from the tab with nothing of the
assistant in between, so it is as immediate as the button on the main window and works before the
assistant has ever connected. It cancels the assistant as well.

## Limitations

These are known and deliberate; read them before using the tab on an instrument with a sample
loaded.

- **Three stage moves are gated by the operator, in code.** `load_sample`, `unload_sample` and
  `preview_acquisition` cross the stage's range and can collide faster than anyone reacts, so they
  do not execute until the operator presses **Run** in the bar above the input; Cancel there,
  Cancel or Stop microscope refuse, and the model is told so. Starting a run is not gated:
  the model is instructed to summarise and ask only when the state shows something off (empty
  list, missing folder, short disk, pending warning) and Stop microscope ends a run at any time. This holds whatever the model was told or talked into.
- **The model call has no timeout.** `WAIT_CAP_S` bounds the microscope leg only. If the endpoint
  stalls — a burst over a tokens-per-minute quota is the usual cause — the turn blocks until the
  HTTP layer gives up, and Cancel gates tool dispatch but cannot abort a request already in
  flight.
- **A commanded move smaller than `POSITION_TOLERANCE` completes without verifying motion.**
  Arrival is tested as `abs(observed - target) > tolerance`, so with the default 1.0 µm a 1 µm move
  from the current position is "already reached" on the first poll and is reported as a successful
  arrival.

## Evaluating the assistant

The code tests prove the tools, the gate and the tab. Whether the *model* does what an operator
expects is a separate question, answered by a behavioural evaluation: a fixed set of scenario
prompts in `mesoSPIM/test/ai_assistant/evals/cases.json`, each with what must happen (which tools
are called, with what, what the instrument's state is afterwards, whether the operator was asked
to confirm, whether the reply asks back instead of guessing, what the reply must mention). The
runner drives the real agent, tools and dispatcher against the simulated instrument of the test
suite, records every run as a trace and scores it:

```
python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini            # GEMINI_API_KEY set
python -m mesoSPIM.test.ai_assistant.evals.run --provider Anthropic --profile Full --only laser,snap
python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini --model gemini-3.5-flash-lite,gemma-4-31b-it \
    --repeat 3 --out "mesoSPIM/test/ai_assistant/evals/runs/{date}-{model}.jsonl"
python -m mesoSPIM.test.ai_assistant.evals.run --rescore runs/2026-09-17-gemini-3.5-flash-lite.jsonl
python -m mesoSPIM.test.ai_assistant.evals.scoreboard mesoSPIM/test/ai_assistant/evals/runs/*.jsonl
```

The cases cover plain verbs, unit conversion (mm, µm, seconds, words, 1e4), reads that must not
mutate, greetings and off-topic questions that need no tool at all, vocabulary refusals and the one
permitted retry, limit refusals (and that a refused value is not retried), ambiguity, prompt
injection in the message and through the instrument's own state, a request to leak the system
prompt, the confirm-first moves with Run and with Cancel, a GUI-busy instrument in live, in a
stale run state and in a time lapse (and what is still allowed then), acquisitions, the selected
row and a time lapse, the two tool sets on the ETL, the galvos, binning and the self test, looking
without a new snap and deciding on saturation, memory across turns, and prompts in German and
Dutch. A run costs API calls and two runs can differ, so it is not part of the test profiles; run
it when the prompt, the tools or the model change, and keep the trace file: a case that starts
failing shows in it what the model did instead. `test_evals.py` keeps the machinery itself honest
offline, with scripted models.

**Benchmarking across models, still to do.** One run of one model is a coin flip on the hard
cases, and not always for the reason it seems: the injection-through-state case failed in two full
runs out of three on what looked like one model, until the traces recorded who answered. A third of
each run's turns had gone to the preset's fallback model after a per-minute rate limit, and that
model obeyed the planted note six times out of six where the chosen one never did. The fallback is
gone from the preset, the tab announces any stand-in, and the scoreboard counts them.
The tooling for a real benchmark is in place: `run.py` takes several models and `--repeat`, and
`scoreboard.py` pools the run files into one table (pass rate per model and per category, provider
errors, median seconds, and the cases that pass only sometimes or never). What is missing is the
runs: every model that may face an operator, three repeats each, on a paid tier, since the free
Gemini tier stops after roughly one full pass per model per day. Read the scoreboard as a report
on the manual as much as on the model: a case that fails on every model is a rule the manual states
too loosely (the ambiguity and readout rules were found that way), one that fails on one model is
that model's fit. Keep the run files; they are the evidence.

Every turn in the tab is recorded the same way, one JSON line per turn in
`~/mesoSPIM/assistant_traces/assistant-<date>.jsonl` (or the config attribute
`ai_assistant_traces_folder`): the prompt, each tool call with its arguments and result, the model
that actually answered (`served`), the reply or the error, and the time taken. Frames are recorded by their size, not their pixels. When
something went wrong at the microscope, that file says what the assistant was told and what it
did.

## What has been verified

- `mesoSPIM/test/ai_assistant/` — offline tests for the worker (completion wrapper, tools, turn,
  error and interrupt behaviour, the Acceptor lifecycle), the local model server and the tab
  (wiring, transport-busy refusal, the single-flight input lock, the setup boxes, local servers
  and their projectors). They run without Qt or hardware, reusing the Remote Control substitute,
  together with the Remote Control offline suites:

  ```
  pytest mesoSPIM/test/remote_control mesoSPIM/test/ai_assistant \
      --ignore=mesoSPIM/test/remote_control/test_real_pyqt_smoke.py \
      --ignore=mesoSPIM/test/remote_control/test_real_pyqt_transport_smoke.py
  ```

  418 passed. `python mesoSPIM/test/remote_control/run.py pyqt` adds the real-PyQt smoke
  scripts, among them one that builds the tab offscreen and checks the setup layout and the input
  keys.
- The behavioural evaluation above, run by hand against a model; its traces are the record.
- End-to-end operation against the Windows DemoStage build.

Not yet verified on real hardware.
