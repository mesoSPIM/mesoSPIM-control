# AI Assistant — Minimal Design

*Reviewed against the dispatcher / servers / GUI code; the review's findings are incorporated below.*

## Goal
An in-process chat tab in mesoSPIM that lets an operator drive the microscope in
natural language via an LLM, reusing the existing Remote Control command core.
Provider-agnostic (local or cloud model) through Pydantic AI. Safety is inherited
from the dispatcher.

## Design principle
Smallest thing that **actually works**. The assistant is one more in-process caller of
`Acceptor.dispatch()` — a sibling of the TCP/MCP transports, minus the socket. No new
command logic, no new safety logic. "Minimal" = enforce the real invariants (a tool
call completes before it returns; the Acceptor is wired exactly once) — not omit the
parts that make it correct.

*In-process (not the existing MCP server) is deliberate — it keeps the chat inside the
app. The cost is owning the threading/Acceptor lifecycle below; the alternative
(agent → loopback MCP) trades the in-app tab for avoiding that. Kept in-process.*

## In scope
- One model from `mesoSPIM_AiAssistent_Config.py` — a **list of named endpoint profiles**
  (`name`, provider/`base_url`, `model`, key-*reference*); v1 active = `gemini-3.5-flash`.
  Cloud (key via env-var reference, not the secret) or local (no key). The list makes
  operator-selectable endpoints a cheap later add.
- Tools generated from `COMMANDS` (single source of truth), as **untyped object-passthrough
  tools** (one `{type: object}` param + the command `hint` — same shape as the MCP
  `tools/list`). Per-arg correctness comes from the command's `accept()` validator, with
  errors fed back to the model.
- **Short mutating ops block until done**: the tool wrapper waits (polling `get_progress`,
  a READ) until the op is terminal, then returns the finished result. One tool call = one
  completed action — the agent needs no polling rule.
- **Long ops** (acquisitions, time-lapse) return after a cap with "still running — poll
  `get_progress`"; that poll guidance lives in the manual.
- The agent can **query state on demand** (`get_position` / `get_state` / `get_progress` …)
  — READ tools return directly.
- **No per-command operator confirmation** — expert microscopy tool; the dispatcher's
  validation + movement limits + one-op gate are the backstop. Guardrails added only if
  real use shows the need.
- **System prompt = the auto-generated `get_manual` output + a thin hand-written preamble**
  (units, frames, safety tone). Rules come from context, not code; the command list is
  never hand-maintained.

## Out of scope
- Typed/JSON-schema tools — `Command` has no declarative schema, so tools are untyped
  passthroughs (add a schema field to `Command` later if richer typing is wanted — a
  dispatcher change).
- Per-command confirmation / destructive-op guard — deferred; add if needed (`kind` alone
  can't express "catastrophic", so a guard would be a per-command risk flag).
- Streaming token deltas — start with reply + tool-call/result notices.
- Session persistence, branching, skills, subagents.
- Context compaction — unnecessary at 1M context; if a small local model needs it, a
  Pydantic AI `history_processor` (sliding window / drop old tool-result bodies).
- Operator endpoint selection (dropdown) → add/edit UI — phase 2/3.
- The provider *menu* (OpenAI, Claude, OpenRouter, Ollama, vLLM, …) — config, not code.
- MCP / network transport — not needed in-process.

## Modules
```
mesoSPIM_RemoteControl_Dispatcher.py  unchanged  COMMANDS, validation, _GATE, kind    (shared core, imported)
mesoSPIM_RemoteControl_Commands.py    unchanged  53 commands + limits + get_manual    (imported)
mesoSPIM_RemoteControl_Servers.py     CHANGES    Acceptor ownership → shared lifecycle (see below)
mesoSPIM_AiAssistent.py               NEW        tools (+ poll-to-done) + agent + worker
mesoSPIM_AiAssistent_Config.py        NEW        endpoint profiles / model / key-refs
mesoSPIM_AiAssistent_GUI.py           NEW        the "AI Assistant" tab (AiAssistentGUI)
assistant_manual.md                   NEW        thin system-prompt preamble (get_manual is the spine)
```
Own module family `mesoSPIM_AiAssistent_*` — separate from Remote Control, imports the shared core.
Tab label: `"AI Assistant"` · Class: `AiAssistentGUI`.

## Pieces

1. **Tools** — `build_tools(acceptor)` iterates `COMMANDS` and returns one untyped
   passthrough tool per command; each calls `Acceptor.dispatch(name, args)`. The tool list
   *is* `COMMANDS`, never hand-maintained.

2. **Completion** — READ / short-ACTION tools return their dispatch result directly. A WAIT
   tool (move, mode change) does not: after `dispatch()` returns `processing`, the worker
   **block-polls `get_progress`** (short READ dispatches, each well under
   `DISPATCH_TIMEOUT_SEC`) until the op is terminal, then returns the finished result. Long
   ops return after a configurable cap with a "still running — poll `get_progress`" result.
   Safety stays in the dispatcher (validation, limits, `_GATE`); no confirmation.

3. **Agent** — `build_agent(model, tools, system_prompt)` constructs a Pydantic AI `Agent`.
   Model from `mesoSPIM_AiAssistent_Config.py`. System prompt = `get_manual` output + thin
   preamble. Built lazily on first submit, reused (keeps history), no connect step.

4. **Worker** — runs `agent.run(user_text)` off the GUI/Core threads via the shared Acceptor.
   **Single-flight**: one turn at a time (input disabled while running), so no concurrent
   runs corrupt the Agent's history. Emits `sig_reply`, `sig_tool`, `sig_result`,
   `sig_error`, `sig_done`. Supports **cancel** (interrupt the turn; on shutdown,
   request-cancel + bounded join — never block the GUI on a cloud call).

5. **GUI (`AiAssistentGUI`)** — output `QPlainTextEdit` (agent text + tool calls + results),
   input `QLineEdit` (Enter submits; disabled during a turn), and a small **interrupt**
   control (cancels the turn and fires `stop`). No config row, no Start/Stop.

## Acceptor ownership
The assistant needs a live `Acceptor` — the Core-thread bridge **and** the WAIT
completion-signal wiring that lets `get_progress` ever read `completed`. **The assistant is
a peer of the transports in the existing "one at a time" model:** it asks Core (via a queued
signal, like `RemoteControlGUI`'s start) to build + wire an Acceptor on the Core thread while
active, and it is **mutually exclusive with TCP/MCP** — it can't run alongside a transport.
That avoids both the double completion-wiring and the "operator hits Stop and silently kills
the assistant" trap. This touches Core / the `RemoteControl` lifecycle in `_Servers.py`, so
that module **does change** (an earlier draft wrongly called it unchanged). Optional cleanup:
hoist the Acceptor to a neutral shared module so the assistant needn't import it from the
transport module.

## Safety invariants
- Every actuation goes through `Acceptor.dispatch()` → validation, movement limits, `_GATE`.
- Out-of-range, malformed, or concurrent calls are rejected by the dispatcher.
- Short mutating ops block until terminal, so the agent can't race ahead into `BusyError`.
- The assistant has no side channel to Core. No per-command confirmation (deferred).

## Tests (TDD, no live model)
- Tools: each `COMMANDS` entry yields a passthrough tool that calls `dispatch(name, args)` (fake acceptor).
- Completion: a WAIT tool returns only once the fake op goes `processing → completed`; a long op returns the cap fallback.
- Safety: out-of-range move rejected by limits; a call while busy gets `BusyError`; a valid call dispatches.
- Worker: single-flight (a second submit mid-turn is rejected/queued); interrupt cancels; shutdown joins within the bound.

## Open questions
1. Cost/latency cap for the long-op poll fallback — what cap, and what does the agent see past it?
2. Manual preamble scope — how much units/frames/safety tone on top of `get_manual`?
3. Endpoint keys on a shared instrument — profile stores a key *reference* (env-var / keyring), never the secret; local needs none.
4. Fail-fast if the configured model lacks tool-calling.
5. (Deferred) a per-command guard on irreversible ops (sample presets, acquisitions, large moves) — add only if real use shows the need.

## Build sequence
1. **Review** — done; findings incorporated.
2. **Acceptor lifecycle** — Core-built, single-wired instance the assistant borrows; assistant ↔ transport mutually exclusive (`_Servers.py` / Core).
3. **Config** — endpoint-profile list in `mesoSPIM_AiAssistent_Config.py` (v1 = `gemini-3.5-flash`).
4. **`mesoSPIM_AiAssistent.py`** (TDD — fakes, no live model): `build_tools(acceptor)` from `COMMANDS`; the poll-to-done wrapper; `build_agent(...)` with `get_manual` + preamble; the single-flight / cancellable QThread worker.
5. **`assistant_manual.md`** — thin preamble.
6. **`mesoSPIM_AiAssistent_GUI.py`** — the tab (output + input + interrupt); wire into MainWindow after the Remote Control tab.
7. **Validate** — Gemini Flash on real tasks, iterate the preamble; final quality check on a paid frontier model.
8. **Deferred** — operator endpoint selection/UI, streaming deltas, image input, guardrails.

## Files touched
**Create:** `mesoSPIM_AiAssistent.py`, `mesoSPIM_AiAssistent_Config.py`, `mesoSPIM_AiAssistent_GUI.py`, `assistant_manual.md`, `test_ai_assistent.py`.
**Edit:** `mesoSPIM_MainWindow.py` (3-line tab wiring); **`mesoSPIM_RemoteControl_Servers.py` / Core** (Acceptor lifecycle + assistant↔transport mutual exclusion — *not* unchanged); dependency/env (add `pydantic-ai`).
**Unchanged (imported):** `mesoSPIM_RemoteControl_Dispatcher.py`, `_Commands.py` (incl. `get_manual`), `_Config.py`.
