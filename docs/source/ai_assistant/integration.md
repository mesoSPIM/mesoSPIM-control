# Integrating the AI Assistant into mesoSPIM-control

The AI Assistant is a separate `mesoSPIM_AiAssistent_*` module family layered on Remote Control. It
adds a chat tab that lets an operator drive the microscope in natural language: a Pydantic AI agent
turns the Remote Control commands into tools and dispatches them through the **same** `Acceptor`,
so every action obeys the existing validation, movement limits, and one-mutation gate.

Integrate Remote Control first ([architecture](../remote_control/architecture.md)); the Assistant
reuses its `Acceptor`, dispatcher, and completion signals.

## 1. New files (all self-contained, in `mesoSPIM/src/`)

- `mesoSPIM_AiAssistent_Config.py` — provider presets, local-model settings, and timing.
- `mesoSPIM_AiAssistent.py` — the `Endpoint` chosen in the tab, the tool builder, the completion
  wrapper (`dispatch_and_wait`), and the `AssistantWorker` that runs each turn off the GUI/Core
  threads.
- `mesoSPIM_AiAssistent_Local.py` — the models-folder scan and the llama.cpp server child that
  serves a local `.gguf` file on loopback.
- `mesoSPIM_AiAssistent_GUI.py` — the `AiAssistentGUI` tab: transcript, input line, Cancel prompt,
  Clear context, Stop microscope, and the collapsible setup footer.
- `assistant_manual.md` — the rules (units, frames, safety, what the evaluation taught); the
  system prompt adds the offered commands by kind, and each tool's description and schema, derived
  from the command registry, carry what it does and its arguments.

Dependencies: `pydantic-ai` (imported lazily, only when a turn runs); `llama-cpp-python` with its
server only for local models (the `ai-assistant-local` extra).

## 2. Acceptor lifecycle — in `mesoSPIM_AiAssistent.py`

The two lifecycle functions reuse the Remote Control `Acceptor` and `self_test`:

```python
def start_assistant_for_core(core): ...   # self-test, then Acceptor(core); None if a transport runs
def stop_assistant_for_core(core): ...    # acceptor.stop(); drop the handle
```

Exclusion holds both ways: `start_assistant_for_core` refuses while a TCP/MCP transport runs, and
`start_for_core` in `mesoSPIM_RemoteControl_Servers.py` refuses while the Assistant's acceptor
exists. That refusal is the only Remote Control edit the Assistant needed.

## 3. `mesoSPIM_Core.py` — one attribute and two delegate slots

Create the handle in `__init__`, beside `self._remote_control = None`:

```python
self._assistant_acceptor = None
```

Add two Qt methods next to `start_remote_control` / `stop_remote_control`:

```python
@QtCore.pyqtSlot()
def start_ai_assistant(self):
    from .mesoSPIM_AiAssistent import start_assistant_for_core
    start_assistant_for_core(self)

@QtCore.pyqtSlot()
def stop_ai_assistant(self):
    from .mesoSPIM_AiAssistent import stop_assistant_for_core
    stop_assistant_for_core(self)
```

Like the transport slots, these only hand work to the server module. They run on the Core thread —
the thread that may build the `Acceptor` (a QObject takes its affinity from where it is created) and
the only thread allowed to call Core methods. The tab reads `core._assistant_acceptor` after the
call: `None` means a transport is busy (or the self-test failed), and the tab says so.

## 4. `mesoSPIM_MainWindow.py` — import the tab, create it, close it

Import with the other tab imports:

```python
from .mesoSPIM_AiAssistent_GUI import AiAssistentGUI
```

Create it after `self.remote_control = RemoteControlGUI(self)` (the tab inserts itself directly after
Remote Control):

```python
self.ai_assistent = AiAssistentGUI(self)
```

Close it near the start of `close_app`, beside `self.remote_control.shutdown()`:

```python
self.ai_assistent.shutdown()
```

`shutdown()` interrupts a running turn, joins the worker thread with a bound, and releases the
Core-owned Acceptor.

## 5. Behavior that stays inside the new modules

- The Acceptor is acquired lazily on the first message, not at startup; until then the Remote Control
  transports stay usable.
- One turn runs at a time — the input disables while the agent works (single-flight); Cancel
  prompt ends the turn at once; Stop microscope stops the instrument the main window's way.
- Every mutating tool blocks until the microscope actually finishes, so the agent sees completed
  actions, not `processing`; a long acquisition past the wait cap returns `still_running`.
- A rate-limited or unavailable model is an error the operator sees and retries; there is no
  whole-turn retry, which would re-run every tool call the first attempt made, and no fallback
  model (a preset may name one, but the Gemini preset no longer does: the evaluation found the
  stand-in obeying a note planted in the state readout). Should another model than the chosen
  one answer a turn, the tab says so above the reply and the trace records it under `served`.
- Tool arguments pass straight to the dispatcher, which validates shape and limits before hardware.

## 6. Verification

The offline suites in `mesoSPIM/test/ai_assistant/` test the completion wrapper, the tool builder,
the endpoint, the worker turn and interrupt, the local server child (with a stand-in process), and
the tab: setup footer, Cloud and Local modes, transport-busy refusal and the single-flight lock,
all under the Qt-free substitute. `mesoSPIM/test/remote_control/run.py pyqt` builds the tab with
real PyQt, offscreen; `mesoSPIM/test/ai_assistant/live/demo_walkthrough.py` runs the agent, with
scripted calls or a live model, against a running demo mesoSPIM over TCP.
