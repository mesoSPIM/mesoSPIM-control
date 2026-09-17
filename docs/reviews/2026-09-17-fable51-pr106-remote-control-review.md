# Review of mesoSPIM-control PR 106: TCP/MCP Remote Control and AI Assistant

Date: 2026-09-17
Reviewed head: `bd058ca2fb7ba1946c36cc623e57fadb6c6f3232` (branch of https://github.com/mesoSPIM/mesoSPIM-control/pull/106)
Base at review time: upstream `master` at `98d74d35` (merges cleanly)

Related: https://github.com/mesoSPIM/mesoSPIM-control/pull/105 ("Add optional remote scripting server") was closed unmerged on 2026-07-27 and is superseded by PR 106. Its Core and MainWindow hunks conflict with PR 106, and its description mentions an `enable_remote_scripting` config gate that the diff does not contain. It should stay closed.

## Summary

PR 106 adds a constrained, allowlisted remote control layer (framed TCP and an MCP-style HTTP endpoint) plus an optional in-process AI Assistant tab that drives the same command registry. The architecture is sound: one dispatcher, one atomic mutation gate, validation before admission, a fail-closed self-test before binding, and a large offline test suite.

Offline verification performed for this review, using the fake PyQt5 substitute the PR ships in its `conftest.py`:

| Suite | Result |
| --- | --- |
| `test/remote_control` offline profile + `test/ai_assistant` | 244 passed, 1 skipped |

The first run showed five failures caused only by the `indexed` package being absent in the review environment. It is already a project dependency, so this is not a PR defect.

Open thread on the PR: Nikita Vladimirov asked on 2026-08-27 whether the author wants this merged now or intends to keep developing. That question appears unanswered.

Recommendation: fix findings 1 and 2 before merge, clean up findings 4 and 5 before merge, and treat the rest as follow-ups or documentation changes.

## Findings

### 1. Soft motion limits are checked in the wrong coordinate frame after zeroing (must fix)

Status: fixed on this branch by the commit "Remote Control: enforce motion limits in the stage frame after zeroing", with regression tests and a self-test check.

Where: `mesoSPIM/src/mesoSPIM_RemoteControl_Commands.py`, `check_absolute` (line 461), `check_relative` (line 470), `check_acquisition` (line 514), and the callers `_accept_move_absolute` (line 1018) and `_accept_move_relative` (line 1044).

The validators compare the user-visible target (from `state["position"]`, the software-zeroed frame) against `stage_parameters.x_min` / `x_max`, which are physical stage coordinates. The stage drivers subtract `int_<axis>_pos_offset` before their own check (`mesoSPIM_Stages.py`, `move_absolute`), and `Core.check_motion_limits` does the same. So the remote layer and the hardware layer disagree as soon as any axis is zeroed.

Consequences:

- `zero` is itself a remote ACTION (line 1083), so a client can shift the frame and then submit a target that the remote layer accepts but the stage silently refuses (only a status message is emitted). The operation then polls position readback until the wait cap or a stop, never reaching the target.
- The reverse also happens: a legitimate in-range physical move is refused after zeroing.
- The tightened `MESOSPIM_RS_LIMITS` envelope is enforced only by this layer, so zeroing bypasses it entirely. This is the case that matters for the PR's safety claims.

Fix: convert to the physical frame before checking. The per-axis offset is `state["position"][axis] - state["position_absolute"][axis]`; physical target is user target minus that offset. The preset moves (`_preset_targets`, line 1471) already operate in the physical frame with `use_internal_position=False`, so the pattern exists. Apply the same conversion in `check_acquisition` for `x_pos`, `y_pos`, `z_start`, `z_end`, `f_start`, `f_end`. Add a test with a nonzero offset in `test/remote_control/support/fake_state.py`; the current fake state has no offset, which is why the suite does not catch this.

### 2. Blocking cross-thread connections can deadlock the GUI and Core threads (must fix)

Status: fixed on this branch by the commit "Remote Control: never block Core on the GUI thread (deadlock fix)", with a real-Qt regression scenario.

Where: `mesoSPIM/src/mesoSPIM_RemoteControl_GUI.py` lines 57 to 60; `mesoSPIM/src/mesoSPIM_AiAssistent_GUI.py` line 63; `mesoSPIM/src/mesoSPIM_AiAssistent.py` `interrupt` (lines 266 to 271).

- The acquisition-list bridge `sig_install_acquisition_list` is a `BlockingQueuedConnection` from the Core thread to the GUI thread.
- `sig_stop_remote_control` and the assistant's `_call_on_core` are `BlockingQueuedConnection` from the GUI thread to the Core thread.

If Core is inside the bridge emit (a remote `set_acquisition_list` just ran) at the moment the operator clicks Stop or sends a first assistant message, each thread waits for the other and neither returns. The window is short but the outcome is a frozen application.

Separately, `AssistantWorker.interrupt` runs `acceptor.dispatch("stop", {})` on the GUI thread, which waits up to `DISPATCH_TIMEOUT_SEC` (30 s) for Core. A busy Core freezes the GUI for that long on the one button meant for emergencies.

Fix: make the bridge a plain `QueuedConnection` (Core already installs the list in its own state before emitting, so the GUI reset does not need to be synchronous), and issue the interrupt's stop dispatch from the worker thread or through a queued signal to Core.

### 3. Transport/assistant mutual exclusion is one-directional (should fix)

Where: `mesoSPIM/src/mesoSPIM_AiAssistent.py`, `start_assistant_for_core` (line 195) refuses while `core._remote_control` is set. `mesoSPIM/src/mesoSPIM_RemoteControl_Servers.py`, `start_for_core` (line 538) does not refuse while `core._assistant_acceptor` exists.

The docs state the two are mutually exclusive. Today an operator can use the assistant, then start TCP or MCP, and both controllers are live. They share `core._remote_session`, so the gate still serialises mutations, but the assistant's blocking wait can then observe an operation created by a network client. Add the symmetric check in `start_for_core`.

### 4. Files that should not land on master (must clean up)

- `docs/screenshots/AI-assistand-first-test.png`, `docs/screenshots/AI-assistand-first-test-joke.png`, `docs/screenshots/AI-assistand-first-test-depression-treatment.png`: about 2.5 MB of binaries, not referenced from any doc, with filenames that are not suitable for the upstream repository.
- `mesoSPIM/log/20260721-remote_control_session_report.md`: a session report committed into the runtime log directory.

These arrived in Nikita's commits ("add snapshots funny", "Create AI-assistand-first-test.png"), so coordinate with him, but they should be dropped before merge.

### 5. Naming: "AiAssistent" vs "AI Assistant" (should fix before merge)

`mesoSPIM_AiAssistent.py`, `mesoSPIM_AiAssistent_Config.py`, `mesoSPIM_AiAssistent_GUI.py`, class `AiAssistentGUI`, attribute `main_window.ai_assistent`, and the test directory contents use "Assistent", while the docs, the tab title and the PR title say "Assistant". Renames after merge are disruptive, so settle the spelling now.

### 6. AI provider settings are hardcoded in package source (should fix)

Where: `mesoSPIM/src/mesoSPIM_AiAssistent_Config.py` lines 14 to 16 (`PROVIDER`, `MODEL = "gemini-3.5-flash-lite"`, `FALLBACK_MODEL`).

Operators would have to edit installed source to switch provider or model, and pinned model IDs go stale quickly. The project convention is per-microscope config files. Suggest an `ai_assistant = {...}` section in the config file, with the module holding defaults only.

The docs should also state plainly what leaves the machine: the system prompt embeds the full `get_manual` output, and every tool result (state, config, file paths, acquisition rows) is sent to the configured cloud provider.

### 7. MCP compatibility claims need qualifying (should fix or document)

Where: `mesoSPIM/src/mesoSPIM_RemoteControl_Config.py` line 21 (`MCP_PROTOCOL_VERSION = "2024-11-05"`); `mesoSPIM/src/mesoSPIM_RemoteControl_Servers.py` line 347 (`tools/list`).

- The server declares protocol `2024-11-05` but serves a POST-only JSON endpoint. That version's HTTP transport is HTTP+SSE; the POST-only shape corresponds to the later Streamable HTTP transport, which also expects `Accept` negotiation and `Mcp-Session-Id` handling. Off-the-shelf MCP clients may not connect.
- Every tool advertises `inputSchema: {"type": "object"}` with no properties, so a client-side model only sees the short `hint` string.

Either name the real MCP client that was validated in the docs, or generate JSON schemas from the `accept` validators (at least top-level keys and types) and align the declared protocol version with the transport actually implemented.

### 8. Smaller items

- `_run_move_relative` (Commands line 1056) calls `serial_worker.move_relative` directly, while `_run_move_absolute` goes through `core.move_absolute`. Works because the serial worker lives on the Core thread, but the asymmetry deserves a comment or should be removed.
- `check_acquisition` checks `z_step > 0` twice (lines 531 and 548).
- `mesoSPIM/src/assistant_manual.md` line 29 lists axes x, y, z, f and omits theta, which is in `config.AXES` and settable remotely.
- `pyproject.toml` line 37 pins `pydantic-ai==2.14.1` exactly inside an optional extra. A compatible range (`>=2.14,<3`) will age better.
- The MCP handler drains up to 1 MiB of request body before authenticating (Servers line 277). Bounded and intentional, so acceptable; noted for completeness.
- `mesoSPIM/test/remote_control/support/fake_state.py` carries no stage offset, which is why finding 1 is invisible to the suite.

## What is good

- Single dispatcher and atomic `_GATE`; TCP and MCP cannot diverge in validation or busy semantics.
- Admission is acknowledged before hardware work, and completion is tied to real milestones or position readback rather than elapsed time.
- Fail-closed startup: unknown mode, missing token, public default token on a non-loopback host, or a failed limits self-test all refuse to bind.
- Strict JSON (duplicate keys and non-finite numbers rejected), bounded frames, constant-time token comparison.
- Env-based tightening of limits that can only narrow the configured envelope.
- Tool errors returned to the model as data with the instrument's own vocabulary attached, which is the right pattern for self-correction.
- 244 offline tests that run without PyQt5 or hardware.
