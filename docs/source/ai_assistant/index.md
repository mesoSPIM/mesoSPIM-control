# AI Assistant

An optional chat tab that drives the microscope in natural language. A [Pydantic AI](https://ai.pydantic.dev)
agent turns the Remote Control commands into tools and dispatches them through the **same**
`Acceptor` as the TCP and MCP transports, so every action obeys the existing accept-validation,
movement limits and one-mutation gate. The tab is idle until the operator sends a message, and the
Assistant and a network transport are mutually exclusive — only one controller holds the session.

This builds on [Remote Control](../remote_control/index.md); read that first.

```{figure} ../../screenshots/AIAssistantTab.png
:alt: AI Assistant tab in the Main window
:width: 60%

The AI Assistant tab: language and vision model, preferences, coordinate system, and Connect.
```

```{toctree}
:maxdepth: 1

architecture
tool-sets
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
out of the chat: a frame goes to the vision model only. Each model box starts with a
**Type** dropdown; the fields after it follow the choice.

**Language model, Cloud AI.** Choose a provider (Gemini, OpenAI, Anthropic, or **OpenAI-style**
for any server that speaks the OpenAI API, such as an Ollama or vLLM already running somewhere, or
a hosted gateway), keep or edit the prefilled model name, and type the API key into the masked
field. OpenAI-style also asks for the server's base URL, and there the key is optional: Ollama
wants none, a gateway or a hosted API wants its token. On a PC whose network inspects HTTPS (an
antivirus or a company proxy re-signing traffic), a cloud server of this kind fails with
"Connection error" although Gemini works: the Python client trusts only its own certificate
bundle. Point it at one that includes the Windows roots (`SSL_CERT_FILE=<bundle.pem>` in the
environment mesoSPIM starts from). The key is kept in memory for this mesoSPIM
session only and is never written to the repository, the microscope config, or a log. An empty
field falls back to the provider's environment variable (`GEMINI_API_KEY`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`), so a key exported before starting mesoSPIM keeps working. Any model the
provider serves under that key works by name: under Gemini, for example, `gemini-3.6-flash` or the
open-weight `gemma-4-31b-it`.

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
the turn fails. The `ai_assistant_*` attributes (`_tools`, `_models_folder`, `_context_tokens`)
describe the microscope, so in a configuration split into a hardware file and a
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
the first message. To change the models, disconnect and connect again; the next Connect starts a fresh conversation.
The presets live in `mesoSPIM/src/ai_assistant/config.py` as defaults only.

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
assistant has ever connected. It cancels the assistant as well, and every schedule.

**Live and long runs do not hold the line.** A live mode the assistant starts returns as soon as
live runs, and from then on it is the operator's live view whoever started it: settings and moves
go through while it runs, from the window or from the assistant, a snap or a run is refused, and
"stop" ends it. An acquisition or time lapse the assistant starts returns as soon as the run is
under way, so the input line is free and "stop" can be typed; the run is refused nothing but
`stop_activity` until it ends, and the main window shows its progress. During live, a look reads
the frame live shows instead of taking a snap.

**Schedules.** "Take a snap every three minutes", "in ten minutes close the shutters", "at 15:00
start the list": the assistant sets a named schedule (`schedule`; `cancel_schedule` removes one,
or all), and the tab's own timer fires each due instruction as a turn of its own, marked
`[scheduled 'name']` in the transcript, through the same tools, gate and refusals as anything
typed, never while a turn runs. The readout carries the clock and the schedules, the model's only
clock. Stop microscope and Disconnect clear every schedule; at most ten, none more often than
every five seconds.

**The eyes remember.** The vision model has a conversation of its own for the session: every
look is a turn in it, with the frame, its time, the settings it was taken with and its numbers,
so "is this sharper than before?" and "has the sample moved since the first frame?" are answered
by looking, and `ask_eyes` puts a question to the frames seen without taking a new one. The
last eight frames stay attached as images; older turns keep their text. Clear context and
Disconnect clear the eyes with the transcript. A scheduled "look and tell me if anything changed"
is one look into a memory of the previous ones.

**The coordinate system.** The box under Preferences says what a positive move on x, y and z
does to the sample in the image: right or left, up or down, toward or away from the camera.
The model is told, so "move it up", "a bit to the left" and "closer to the camera" become signed
moves on the right axis, and it says which axis and sign it used. The microscope config can set
the start-up choice with `ai_assistant_axes`, a dict such as `{"x": "left", "y": "up", "z":
"toward the camera"}`; the box is locked while connected, like the rest of the setup.

**An OpenAI-style server and images.** The preset cannot know whether the model behind an
arbitrary server accepts images, so `look` gives such a model the frame's numbers only, and the
status line says "no vision". Tick **Can see images** next to the base URL when it does; a model
chosen in the Vision model box is always shown the frame.

**A tight per-minute limit at the host.** Set `ai_assistant_request_interval_s` in the microscope
config to space the requests to the model by at least that many seconds; the status line shows
it.

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
- **Five rules are held in code for the length of a turn** (`TurnGuard`), because a model can
  read a rule and still break it. After a move is refused for a movement limit, no other target
  on that axis is taken until the operator's next message. After a command is refused because the
  operator is running something from the GUI, a stop waits for **Run** in the same bar as the
  three moves above. A turn may change the laser intensity, or the exposure, twice; a third change
  waits for **Run**. A `look` right after a `snap` reads that frame instead of exposing the sample
  again. A value the operator did not give waits for **Run** ("make it brighter" sent as 20 %,
  "change the filter" sent as the one other filter); a value counts as theirs when it is in their
  words, this turn or earlier and in any unit the manual converts, or made from a readout value
  by an operation they named (double, halve, back to what it was, an amount further). A stop the
  operator asks for is never held back. A refusal carries its advice ("say so and wait; do not
  stop it") where the model reads it next.
- **A reply that called no tool goes back to the model once, and the tab says when it sent
  nothing.** A model can report an action it never took ("I have stopped the time lapse").
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

## Privacy

Nothing of the chat is saved. Prompts, replies, tool calls and frames stay in memory for the
session and are discarded by Clear context, Disconnect, or closing mesoSPIM; none of it is
written to disk or to the mesoSPIM log. What leaves the machine is what a cloud provider receives
to answer a turn; a local model keeps everything on the PC.

## Testing

`python mesoSPIM/test/remote_control/run.py pyqt` runs the real-PyQt scripts, among them one that
builds the tab offscreen and checks the setup layout and the input keys, and one that connects
the tab to a real worker thread and Acceptor against a scripted model and lets the tab's own
timer fire a schedule twice, then checks that Stop microscope ends it. No model, network or
hardware is involved.
