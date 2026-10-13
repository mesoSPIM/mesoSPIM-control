# Architecture

Where the AI Assistant's code sits, how it joins mesoSPIM-control, and the decisions behind it.
The [manual](index.md) says how the tab behaves.

## One more caller of the Acceptor

The assistant is an in-process sibling of the TCP and MCP transports: its tools call
`Acceptor.dispatch()`, so every action passes the same validation, movement limits and
one-mutation gate, and the assistant adds no command logic and no safety logic of its own. Going
through the loopback MCP server instead would have spared the lifecycle code, but put the chat
outside the application. One controller holds the session at a time: the assistant refuses to
start while a transport runs, and a transport refuses while the assistant holds the Acceptor.

Integrate Remote Control first ([architecture](../remote_control/architecture.md)); the assistant
reuses its `Acceptor`, dispatcher, and completion signals.

## Files

All in `mesoSPIM/src/ai_assistant/`:

```text
config.py     provider presets (with each model's token warning and ceiling), timing, texts
assistant.py  the Endpoint chosen in the tab, the tool builder, the completion wrapper
              (dispatch_and_wait), and the AssistantWorker that runs each turn off the GUI/Core threads
frames.py     the frame history, its measures, the map and the calibration
gui.py        the AiAssistantGUI tab (setup, status, Connect and Disconnect) and the AssistantWindow
              it opens while connected: transcript, input line, Stop microscope, Cancel prompt,
              Clear context, Show tool calls
manual.md     the rules (units, frames, safety); the system prompt adds the offered commands by kind,
              and each tool's description and schema, derived from the command registry
```

Dependencies: `pydantic-ai` (imported lazily, only when a turn runs).

## Joining mesoSPIM-control

**Acceptor lifecycle**, in `assistant.py`. The two lifecycle functions reuse the Remote Control
`Acceptor` and `self_test`:

```python
def start_assistant_for_core(core): ...   # self-test, then Acceptor(core); None if a transport runs
def stop_assistant_for_core(core): ...    # acceptor.stop(); drop the handle
```

Exclusion holds both ways: `start_assistant_for_core` refuses while a TCP/MCP transport runs, and
`start_for_core` in `remote_control/servers.py` refuses while the assistant's acceptor exists.

**`mesoSPIM_Core.py`**: one attribute, `self._assistant_acceptor = None`, beside
`self._remote_control`, and two Qt slots next to `start_remote_control` / `stop_remote_control`:

```python
@QtCore.pyqtSlot()
def start_ai_assistant(self):
    from .ai_assistant.assistant import start_assistant_for_core
    start_assistant_for_core(self)

@QtCore.pyqtSlot()
def stop_ai_assistant(self):
    from .ai_assistant.assistant import stop_assistant_for_core
    stop_assistant_for_core(self)
```

Like the transport slots, these only hand work to the module. They run on the Core thread — the
thread that may build the `Acceptor` (a QObject takes its affinity from where it is created) and
the only thread allowed to call Core methods. The tab reads `core._assistant_acceptor` after the
call: `None` means a transport is busy (or the self-test failed), and the tab says so.

**`mesoSPIM_MainWindow.py`**: the tab is imported with the other tabs
(`from .ai_assistant.gui import AiAssistantGUI`), created after the Remote Control tab
(`self.ai_assistant = AiAssistantGUI(self)`; it inserts itself directly after Remote Control), and
closed near the start of `close_app`, beside `self.remote_control.shutdown()`. `shutdown()`
interrupts a running turn, joins the worker thread with a bound, and releases the Core-owned
Acceptor.

## Tools from the command registry

Every registered command but `get_manual` becomes one tool with the command's own JSON schema,
the one MCP's `tools/list` serves, so the tool list is never maintained by hand and the model can
do exactly what TCP and MCP clients can. Every tool is sequential: two calls in one reply run one
after the other. The tools skip pydantic's own
validation of a call: the command's `accept()` stays the one place a call is refused, with one
error vocabulary, and the refusal goes back to the model as data. Tool arguments pass straight to
the dispatcher, which validates shape and limits before hardware.

A tool returns when the instrument is done, not when the command is admitted: the wrapper polls
`get_progress` until the operation ends, so one tool call is one finished action and the model
needs no polling rule. Two kinds of command return earlier, on purpose. A mode that runs until
stopped (live, the visual and alignment modes) returns once it runs, and the dispatcher then
treats it as the operator's live view: the operation that started it is complete, settings and
moves pass as they do from the GUI, a take-over is refused with a message that names this
session, and `stop_activity` ends it (`RUNS_UNTIL_STOPPED`). A run that ends by itself but takes
minutes to hours (the acquisition commands and the time lapse) returns once it is under way, so
the turn ends and the input line is free for "stop"; the run holds the gate against everything
but a stop until it ends (`RUNS_ON_ITS_OWN`); the model is told not to poll, and a two-second
check in the tab, asked of the worker between turns, writes one line when the run ends, with no
model turn. Anything else still running after `WAIT_CAP_S` returns `still_running`.

The eyes (`VisionSession`) are the vision model's own conversation, kept by the worker for the
session. `look` sends the frame into it as a turn (time, the readout keys a picture depends on,
the numbers, the image, the question), `ask_eyes` sends a question alone, and after each turn
`detach_old_frames` strips the image from every frame turn but the last `VISION_FRAMES_KEPT`,
keeping the text, so the cost per look stays about one frame with a provider that caches the
prefix. The main model never carries an image.

## No safety layer of its own

The safety is the instrument's and the same for every client: Core's stage limits, the
dispatcher's one operation at a time, and Stop microscope. The assistant adds no gate, no
confirmation and no rule held in code; what it adds is advice, attached to a refusal where the
model reads it next. A look right after a snap of the same place and settings reads that frame
instead of exposing the sample twice.

## Context and memory

Every operator message carries the instrument's readout in a `<microscope_state>` block, so the
model acts on current values without reading them first; the block is data, escaped so that no
text in it can close it. The history is append-only until Clear context: nothing earlier is ever
rewritten, which keeps a provider's signed thinking valid and its prompt cache warm. The
instructions and tools come first and never change; on Anthropic they are cached for an hour
and the conversation for five minutes. The tab shows each request's input tokens and stops at
the model's ceiling.

The conversation lives in memory only. Nothing of the chat (prompts, replies, tool calls, frames)
is written to disk or to the mesoSPIM log; Clear context and Disconnect discard it.

## Failures

A model that is rate-limited or unavailable is an error the operator sees; there is no
whole-turn retry, which would re-run every tool call the first attempt made. The SDK's own retry
of a 429 or 529 is a retry of one request on the same history, whose results are already in the
messages, and is fine. The Gemini preset
names no fallback model: a stand-in model can obey a note planted in the readout that the chosen
model does not. When another model answers anyway, the tab says so above the reply.
