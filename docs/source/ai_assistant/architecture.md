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
config.py     provider presets, local-model settings, timing, and the rules held in code
assistant.py  the Endpoint chosen in the tab, the tool builder, the completion wrapper
              (dispatch_and_wait), and the AssistantWorker that runs each turn off the GUI/Core threads
local.py      the models-folder scan and the llama.cpp server child that serves a local .gguf file
gui.py        the AiAssistantGUI tab (setup, status, Connect and Disconnect) and the AssistantWindow
              it opens while connected: transcript, input line, Stop microscope, Cancel prompt,
              Clear context, Show tool calls
manual.md     the rules (units, frames, safety); the system prompt adds the offered commands by kind,
              and each tool's description and schema, derived from the command registry
```

Dependencies: `pydantic-ai` (imported lazily, only when a turn runs); `llama-cpp-python` with its
server only for local models (the `ai-assistant-local` extra).

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

Each offered command becomes one tool with the command's own JSON schema, the one MCP's
`tools/list` serves, so the tool list is never maintained by hand. The tools skip pydantic's own
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
but a stop until it ends (`RUNS_ON_ITS_OWN`). Anything else still running after `WAIT_CAP_S`
returns `still_running`, and the model polls from there.

The eyes (`VisionSession`) are the vision model's own conversation, kept by the worker for the
session. `look` sends the frame into it as a turn (time, the readout keys a picture depends on,
the numbers, the image, the question), `ask_eyes` sends a question alone, and after each turn
`detach_old_frames` strips the image from every frame turn but the last `VISION_FRAMES_KEPT`,
keeping the text, so the cost per look stays about one frame with a provider that caches the
prefix. The main model never carries an image.

The scheduler is the tab's, not the model's: `Scheduler` holds named schedules, the two tools
add and cancel them from the worker thread, and a one-second Qt timer on the GUI thread pops the
first due one and submits its instruction as a turn (`SCHEDULED_TURN`), never while a turn runs.
The readout carries the clock and the schedules on every turn, so the model has a clock without
having to keep time.

## What the model is offered

The **Regular** tool set leaves out what a user setting up a sample has no business with: the
camera settings, the galvos, laser timing, the alignment modes, the generic setting call, and the
ETL's delay and ramps (`set_etl` takes the voltages only). The model is not offered them at all
and is told they exist in the Full set, so it cannot be talked into them and does not stand another
command in for one. **Full** offers every command. See [the two tool sets](tool-sets.md).

## Rules in code, where the prompt was not enough

Small models read a rule and do otherwise, so the rules that matter most are held in code.
`load_sample`, `unload_sample` and `preview_acquisition` cross the stage's range and wait for the
operator's **Run**. `TurnGuard` keeps, for one turn, what a refusal ruled out: no other target on
an axis refused for its limit, no stop to clear a GUI-busy instrument without **Run**, no third
intensity or exposure change without **Run**, no second exposure for a look right after a snap,
and no value the operator did not give: a number or option in their words, or arithmetic they
named on a readout value, passes; "brighter" sent as 20 % waits for **Run**. A reply that called
no tool is handed back once, and the tab says when a turn sent nothing to the microscope.

## The voice

The manual speaks to the operator as *you*, gives each rule its reason, and on a refusal asks for
the next step ("propose one fix as a question") instead of stopping; a manual written as orders
got answers in kind. Two things to watch when softening a rule: a model told to ask may ask where
it was allowed to correct (a listed option spelled differently), and may "help" by clamping an
out-of-range value to the limit; both exceptions are named in the manual.

## Context and memory

Every operator message carries the instrument's readout in a `<microscope_state>` block, so the
model acts on current values without reading them first; the block is data, escaped so that no
text in it can close it. Older turns are compacted to a one-line readout and shortened tool
results before each request, and every turn stays whole in a session store the model can search
and recall, so a long session costs little and loses nothing.

The conversation lives in memory only. Nothing of the chat (prompts, replies, tool calls, frames)
is written to disk or to the mesoSPIM log; Clear context and Disconnect discard it.

## Failures

A model that is rate-limited or unavailable is an error the operator sees; there is no
whole-turn retry, which would re-run every tool call the first attempt made. The Gemini preset
names no fallback model: a stand-in model can obey a note planted in the readout that the chosen
model does not. When another model answers anyway, the tab says so above the reply.
