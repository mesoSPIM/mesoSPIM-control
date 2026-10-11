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
skills
```

## Requirements

- `pydantic-ai`, declared as the optional extra `ai-assistant`: install with
  `pip install -e ".[ai-assistant]"`. The extra also keeps the `anthropic` SDK below 1.0, whose
  newer client library pydantic-ai 2.14 cannot drive. It is imported lazily, so the application
  starts and every other feature works without it; the tab reports the missing module when the
  operator sends a first message.
- An API key for the chosen provider, or any server that speaks the OpenAI API (Ollama, vLLM, LM Studio).
  The assistant is built and evaluated for the cloud models Gemini 3.5 Flash-Lite and Claude
  Haiku 5.5; a model served locally works through the OpenAI-style preset.

## Setting it up

The tab is the setup, shaped like the Remote Control tab: one **Setup AI assistant** box with
**Language model**, **Vision model** and **Preferences**, a **Status** line, and **Connect** and
**Disconnect**. Connect applies the boxes, takes the microscope session and opens the assistant
window, where the chat is; the status line then names the model that answers. Disconnect, or
closing that window, cancels a running turn, closes it and hands the session back, so the Remote
Control tab can start a transport without restarting mesoSPIM. While connected the boxes are
read-only: Disconnect to change them. When a Connect cannot go ahead (a missing key, say) the
status line says what is needed. Images stay out of the chat: a frame goes to the vision model
only.

**Language model.** Choose a provider (Gemini, OpenAI, Anthropic, or **OpenAI-style**
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

Every model is sampled at temperature 0 where it accepts one, and a malformed tool call is
handed back to it twice before the turn fails. The `ai_assistant_*` attributes describe the
microscope, so in a configuration split into a hardware file and a user file they belong in the
hardware file (`config/hardware/…_hw.py`); the user file can override any of them below its
`include()` line.

**Vision model.** The model that reads camera frames when the assistant looks. *Same as language
model* (the default) lets the language model read frames itself; the cloud models can. Choosing
Cloud AI here gives a text-only language model eyes of its own: the same fields as above, and the
frame goes to this model in a separate call with the question, so the conversation itself never
carries images.

**Preferences** apply at once. **Bin image** bins the frame handed to the vision model 1, 2, 4
or 8 times (2 by default: a 2048-pixel camera frame arrives as 1024): coarser is cheaper and
faster, and enough for "is it centred" or "is it saturated"; the numbers always come from the
full frame. **Focus metric** chooses the focus measure: Laplacian, or the Auto-Focus DCT-Shannon.
The model is offered every Remote Control command, the same ones TCP and MCP serve. That includes
what the windows show and offer: the live view's levels, lookup tables and regions of interest,
pictures of the windows, the optimizer, the processor chain and the analyses of image files. A
change to a window is waited for until the window shows it, and the tool returns what it then shows.

Building a cloud endpoint does not contact the provider, so a wrong key shows up as an error on
the first message. To change the models, disconnect and connect again; the next Connect starts a fresh conversation.
The presets live in `mesoSPIM/src/ai_assistant/config.py` as defaults only.

## Using it

Press **Connect** in the tab and type in the window that opens. Enter submits; Shift+Enter starts
a new line, as in an editor. **Stop microscope** sits right of the input; under them **Cancel
prompt**, **Clear context** and **Show tool calls**, which lists the commands each answer ran above
it, streamed live, so the operator sees exactly which named calls were issued. **Cancel prompt**
stops the assistant: the turn ends at once and a model request in flight is abandoned; what the
assistant already started keeps running. **Stop microscope** is
the main window's Stop: the same queued signals to Core (state idle aborts the running mode, the
time lapse is cancelled) plus the stage stop, sent straight from the tab with nothing of the
assistant in between, so it is as immediate as the button on the main window and works before the
assistant has ever connected. It cancels the assistant as well.

**Live and long runs do not hold the line.** A live mode the assistant starts returns as soon as
live runs, and from then on it is the operator's live view whoever started it: settings and moves
go through while it runs, from the window or from the assistant, a snap or a run is refused, and
"stop" ends it. An acquisition or time lapse the assistant starts returns as soon as the run is
under way, so the input line is free and "stop" can be typed; the run is refused nothing but
`stop_activity` until it ends, and the main window shows its progress. When it ends, the chat
says so in one grey line ("Acquisition list finished 14:02:00"); no model is asked. A time
course is the software's own time lapse (`time_lapse_start`, an interval and a number of
points); the assistant keeps no timer of its own. During live, a look reads the frame live shows
instead of taking a snap.

**The session's size.** The conversation is kept whole until **Clear context**, so every request
carries the session so far. The line above the input shows what the last request cost in input
tokens; past the model's warning it says the session is large, and past its ceiling no message is
sent until Clear context. On Anthropic models the request is cached: the tools and instructions
for an hour, the conversation for five minutes, so each request pays in full only for what is
new. Gemini and OpenAI cache such a prefix on their own.

**Unclear requests and plans.** When a request is unclear, the assistant suggests what it would
do and asks before doing it; when it does not know, it asks. For several steps it says its plan in
a line or two first. The manual stays short and general: each tool's own description says what it
takes, and repeatable workflows belong in skills.

**Frames and the map.** Every frame a look, a snap or live delivers is kept for the session as a
small copy with its number, time, position and settings, and code adds its measures: focus, peak,
and the offset of the sample from the centre with the stage move that would centre it. `look`
takes `frames` ("last 3", "1,7", "3-10") and compares them (image shift, focus, peak); the vision
model sees exactly those frames and keeps only its text afterwards. The readout carries the
history in brief and a map made from it: per zoom and light, where the frames put the sample, its
best focus from the focus curve, the last good light and labelled places. The vision model has a
conversation of its own for the session, so `ask_eyes` puts a question to the frames seen without
taking a new one. Clear context and Disconnect clear the frames and the eyes with the transcript.

**Calibrate.** Until calibrated, the move that centres the sample uses the nominal pixel size and
the coordinate system below. `calibrate` moves x and y by
a tenth of the field and back, measures how the image moved, and keeps the result per zoom beside
the configuration, in a git-ignored file. Centring moves then use the measured scale and
direction, which also corrects a coordinate system set the wrong way round.

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

- **The safety is the instrument's, for every client alike.** Core's stage limits, the one
  operation at a time and Stop microscope hold whatever the model was told; the assistant adds no
  gate of its own. Load, unload, preview, calibrate and any move within the limits run when asked.
  When a request leaves a value or a choice open, the model is told to ask; otherwise it acts and
  says what it chose. Every refusal carries its advice where the model reads it next.
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
builds the tab offscreen and checks the setup layout and the input keys. No model, network or
hardware is involved.
