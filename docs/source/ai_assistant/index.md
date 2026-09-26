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
context
local-test
open-work
```

## Requirements

- `pydantic-ai`, declared as the optional extra `ai-assistant`: install with
  `pip install -e ".[ai-assistant]"`. The extra also keeps the `anthropic` SDK below 1.0, whose
  newer client library pydantic-ai 2.14 cannot drive. It is imported lazily, so the application
  starts and every other feature works without it; the tab reports the missing module when the
  operator sends a first message.
- An API key for the chosen provider, or any server that speaks the OpenAI API (Ollama, vLLM, LM Studio).
- For a local model file, `llama-cpp-python` with its server: the extra `ai-assistant-local`
  installs both.

## Setting it up

The tab is the setup, shaped like the Remote Control tab: one **Setup AI assistant** box with
**Language model**, **Vision model** and **Preferences**, a **Status** line, and **Connect** and
**Disconnect**. Connect applies the boxes, takes the microscope session and opens the assistant
window, where the chat is; the status line then names the model that answers. Disconnect, or
closing that window, cancels a running turn, closes it and hands the session back, so the Remote
Control tab can start a transport without restarting mesoSPIM. While connected the boxes are
read-only: Disconnect to change them. When a Connect cannot go ahead (nothing configured yet, a
missing key, a local model that failed to start) the status line says what is needed. Images stay
out of the chat: a frame goes to the vision model and the trace. Each model box starts with a
**Type** dropdown; the fields after it follow the choice.

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
"llama-cpp-python[server]"`, or the `ai-assistant-local` extra) as a child process on a loopback
port; the status line reads "starting …" while the model loads, and the window opens once it
answers. The
server is started with a 32K-token context window (llama.cpp's own default of 2,048 would not
hold one request), prompt batches of 2,048 tokens and flash attention where the build has it;
the config attribute `ai_assistant_context_tokens` sets another context size. Every model, cloud
or local, is sampled at temperature 0 and gets a malformed tool call handed back twice before
the turn fails. The four `ai_assistant_*` attributes (`_tools`, `_models_folder`, `_context_tokens`,
`_traces_folder`) describe the microscope, so in a configuration split into a hardware file and a
user file they belong in the hardware file (`config/hardware/…_hw.py`); the user file can
override any of them below its `include()` line.
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
default) is for a user setting up a sample on a configured microscope: reads and checks (the
self test and the stuck-operation reset included), stage and sample moves, laser, intensity,
filter, zoom, shutters, the ETL voltages (amplitude and offset) and its calibration files, snap,
live, and the acquisition and time lapse commands. *Full* adds the camera settings (the exposure
time included), the ETL's delay and ramps, galvo and laser timing, the alignment modes and the
generic setting call. In Regular the other commands are not offered to the model at all, so it
cannot be talked into them; a command offered in both sets takes the same arguments in both,
except `set_etl`, which in Regular takes the voltages only. The model is told which commands the
set withholds, so a request for one gets "not in this tool set" rather than a stand-in command
dressed up as the result. The start-up choice can be fixed per microscope with the config
attribute `ai_assistant_tools` ("Regular" or "Full"). TCP and MCP always serve every command; this
is the assistant only. **Memory** is how
many of the operator's messages, with their answers, the model remembers; the newest three stay
whole, older ones keep a one-line readout (state, position, optics) instead of the full state
block and have long tool results shortened, so twenty turns of memory cost a fraction of what
twenty full readouts would. Nothing is lost by it: every turn stays in a session store, and the
assistant has two tools on it, one that returns an earlier turn in full or the turns in which a
readout value changed, and one that finds earlier turns by words, for "what was the focus before
I moved it" or "which batch did I say this is". Clear context empties the store. **Bin image** bins
the frame handed to the vision model 1, 2, 4 or 8 times (2 by default: a 2048-pixel camera frame
arrives as 1024): coarser is cheaper and faster, and enough for "is it centred" or "is it
saturated"; the numbers always come from the full frame.

Building a cloud endpoint does not contact the provider, so a wrong key shows up as an error on
the first message. To change the models, disconnect and connect again; the transcript is kept.
The presets live in `mesoSPIM_AiAssistent_Config.py` as defaults only.

## Using it

Press **Connect** in the tab and type in the window that opens. Enter submits; Shift+Enter starts
a new line, as in an editor. **Stop microscope** sits right of the input; under them **Cancel
prompt**, **Clear context** and **Show tool calls**, which lists the commands each answer ran above
it, streamed live, so the operator sees exactly which named calls were issued. **Cancel prompt**
stops the assistant: the turn ends at once, a model
request in flight is abandoned and an open Run / Cancel question is cancelled; what the assistant
already started keeps running. **Stop microscope** is
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
  Cancel or Stop microscope refuse, and the model is told so. This holds whatever the model was
  told or talked into. Starting a run is not gated: the model is instructed to summarise and ask
  only when the state shows something off (empty list, missing folder, short disk, pending
  warning), and Stop microscope ends a run at any time.
- **Four rules are held in code for the length of a turn** (`TurnGuard`), because
  small local models read them and do otherwise. After a move is refused for a movement limit, no
  other target for that axis is taken until the operator's next message: a 4B model answered
  "z=999999 refused" with a move to z=25000 and reported success. After a command is refused
  because the operator is running something from the GUI, a stop waits for **Run** in the same
  bar as the three moves above: a 1B model stopped a running time lapse in order to take a look.
  A stop the operator asks for is never gated. A turn may change the laser intensity, or the
  exposure, twice; a third change waits for **Run** too: asked to double the intensity of a dim
  frame once, a 12B model went 20, 40, 80, 100 because the next frame looked no better. And a
  `look` right after a `snap` reads that frame instead of exposing the sample again. A refusal
  also carries its advice ("say so and wait; do not stop it") where the model reads it next.
- **A reply that called no tool goes back to the model once, and the tab says when it sent
  nothing.** Small models write "I have stopped the time lapse" having called nothing, and
  whether they do turns on the wording of unrelated lines of the manual, so no wording cures it.
  A turn that ends without a tool call is handed back with that fact: the model calls the tool
  after all, or answers with one word and its first reply reaches the operator unchanged (one
  short extra request on turns that send no command; `CALLED_NOTHING_CHALLENGE`, empty switches
  it off). It is not a guarantee, so under a reply that called nothing the tab also prints "no
  command was sent to the microscope in this turn". The Stop microscope button never depends on
  the model.
- **The model call has no time limit of its own.** `WAIT_CAP_S` bounds the microscope leg only. If
  the endpoint stalls (a burst over a tokens-per-minute quota is the usual cause), the turn waits
  until the HTTP layer gives up; **Cancel prompt** ends it at once.
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
python -m mesoSPIM.test.ai_assistant.evals.run --provider Gemini --model gemma-4-26b-a4b-it \
    --request-interval 25 --retry-wait 65      # a free tier's per-minute token cap: space the requests
python -m mesoSPIM.test.ai_assistant.evals.scoreboard mesoSPIM/test/ai_assistant/evals/runs/*.jsonl
```

The cases cover plain verbs and unit conversion, reads that must change nothing, greetings that
need no tool, vocabulary and limit refusals (and the one permitted retry), requests that lack a
value and must be asked back, prompt injection in the message and through the instrument's own
state, the confirm-first moves, a microscope busy from the GUI, acquisitions and time lapses, the
two tool sets, memory across turns, prompts in German and Dutch, and vision: synthetic frames whose
content the numbers do not give away (spots to count, a ring to tell from a disc, a sample the edge
cuts off, a defocused spot, shadow stripes, an empty field), decisions the picture must drive, and
when to look at all. A vision case passes only when the frame reached the vision model and came
back described. Every case also fails when a reply quotes the state block, which the manual
forbids; the tab strips a quoted block before showing a reply, and the evaluation keeps the habit
visible.

A run costs API calls and two runs can differ, so it is not part of the test profiles: run it when
the prompt, the tools or the model change, and keep the trace file, which shows what the model did
instead when a case starts failing. `test_evals.py` keeps the machinery itself honest offline, with
scripted models.

**Prompt size.** A turn carries the manual and the commands by kind (about 1,800 tokens in
Regular), the tool schemas (about 2,700 tokens for 37 tools) and the state block (about 500), so
roughly 5,000 input tokens before the conversation; a tool call makes it two requests. The row
schema is spelled out once, in `set_acquisition_list`, and the checks that take rows refer to it.
That size is what lets a local model with an 8K context keep twenty messages of memory, and what
keeps a free-tier per-minute token cap from stalling an evaluation; a test pins it.

**Across models.** One run of one model is a coin flip on the hard cases. `run.py` takes several
models and `--repeat`, and `scoreboard.py` pools the run files into one table: pass rate per model
and per category, provider errors, median seconds, the cases that pass only sometimes, and the
turns a fallback model answered in place of the chosen one. Read it as a report on the manual as
much as on the model: a case that fails on every model is a rule the manual states too loosely; one
that fails on one model is that model's fit. Still to do: three repeats of every model that may
face an operator, on a paid tier, since the free Gemini tier stops after roughly one full pass per
model per day.

A change made to pass these cases may only have fitted them. `evals/cases_holdout.json` holds a
variant of each case, with other wording, numbers, axes, settings and frames (some with the
opposite answer: a solid disc for the ring, no stripes, a well-exposed frame), written without
running a model on it. Develop against `cases.json`; run `--cases …/cases_holdout.json` afterwards
and compare. A gain that does not carry over was a fit.

Every turn in the tab is recorded the same way, one JSON line per turn in
`~/mesoSPIM/assistant_traces/assistant-<date>.jsonl` (or the config attribute
`ai_assistant_traces_folder`): the prompt, each tool call with its arguments and result, the model
that actually answered (`served`), the reply or the error, and the time taken; a turn cut short by
Cancel or an error lists the calls it started. Frames are recorded by their size, not their
pixels. When something went wrong at the microscope, that file says what the assistant was told
and what it did.

## What has been verified

- `mesoSPIM/test/ai_assistant/` — offline tests for the worker (completion wrapper, tools, turn,
  error and interrupt behaviour, the Acceptor lifecycle), the local model server and the tab
  (wiring, transport-busy refusal, the single-flight input lock, the setup boxes, local servers
  and their projectors). They run without Qt or hardware, on the Remote Control substitute, alone
  or with the Remote Control suites: `pytest mesoSPIM/test/remote_control mesoSPIM/test/ai_assistant`.
  `python mesoSPIM/test/remote_control/run.py pyqt` adds the real-PyQt scripts, among them one that
  builds the tab offscreen and checks the setup layout and the input keys.
- The behavioural evaluation above, run by hand against a model; its traces are the record.
- End-to-end operation against the Windows DemoStage build.

Not yet verified on real hardware.
