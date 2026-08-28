# Integrating the AI Assistant into mesoSPIM-control

The AI Assistant is a separate `mesoSPIM_AiAssistent_*` module family layered on Remote Control. It
adds a chat tab that lets an operator drive the microscope in natural language: a Pydantic AI agent
turns the Remote Control commands into tools and dispatches them through the **same** `Acceptor`,
so every action obeys the existing validation, movement limits, and one-mutation gate.

Integrate Remote Control first ([`INTEGRATION.md`](INTEGRATION.md)); the Assistant reuses its
`Acceptor`, dispatcher, and completion signals.

## 1. New files (all self-contained, in `mesoSPIM/src/`)

- `mesoSPIM_AiAssistent_Config.py` — the one endpoint (provider, model, key env var) and timing.
- `mesoSPIM_AiAssistent.py` — the tool builder, the completion wrapper (`dispatch_and_wait`), and
  the `AssistantWorker` that runs each turn off the GUI/Core threads.
- `mesoSPIM_AiAssistent_GUI.py` — the `AiAssistentGUI` tab (transcript + input line + Interrupt).
- `assistant_manual.md` — a thin preamble (units, frames, safety tone); `get_manual` supplies the
  full, always-in-sync command reference.

Dependency: `pydantic-ai` (imported lazily, only when a turn actually runs).

## 2. Acceptor lifecycle — in `mesoSPIM_AiAssistent.py` (no Remote Control file changes)

The Assistant is **purely additive**: the five `mesoSPIM_RemoteControl_*` modules stay byte-identical
to their shipped patch (CI enforces this). The two lifecycle functions therefore live in the new
`mesoSPIM_AiAssistent.py`, reusing the RC `Acceptor` and `self_test`:

```python
def start_assistant_for_core(core): ...   # self-test, then Acceptor(core); None if a transport runs
def stop_assistant_for_core(core): ...    # acceptor.stop(); drop the handle
```

Exclusion is one-way: `start_assistant_for_core` refuses while a TCP/MCP transport is running, so the
Assistant never starts a second controller behind the operator's back. The reverse guardrail — a
transport refusing to start while the Assistant is active — is intentionally left out of v1 because
it would require editing the frozen `start_for_core`, and running two Acceptors is in fact safe: the
completion transitions (`complete`/`fail`) are idempotent through the one gate, so nothing
double-completes. Add the reverse check (three lines at the top of `start_for_core`) when the RC
modules are next regenerated, if simultaneous control should be forbidden outright.

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
- One turn runs at a time — the input disables while the agent works (single-flight); Interrupt gates
  further dispatches and stops the hardware.
- Every mutating tool blocks until the microscope actually finishes, so the agent sees completed
  actions, not `processing`; a long acquisition past the wait cap returns `still_running`.
- Transient free-tier model errors (503 / 429) are retried with a short backoff.
- Tool arguments pass straight to the dispatcher, which validates shape and limits before hardware.

## 6. Verification

The offline suites (`tests/test_ai_assistent.py`, `tests/test_ai_assistent_gui.py`) test the
completion wrapper, the tool builder, the worker turn/retry/interrupt, and the tab's transport-busy
refusal and single-flight lock, all under the Qt-free shim. Real-thread hand-off and a live turn on
the DemoStage are the operator-gated bench checks (see the checklist in `ai_assistant/`).
