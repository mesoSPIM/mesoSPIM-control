# Remote Control architecture

## Design goals

Remote Control should be small, predictable, and removable. It therefore follows four rules:

1. Existing Core and MainWindow files contain only short integration hooks.
2. TCP and MCP use the same commands and validation.
3. Only one remote mutation may run at a time.
4. The operator must start and stop the selected transport manually.

## Request path

```text
TCP client ─┐
            ├─> authentication ─> Core thread ─> validation and busy gate ─> accepted operation
MCP client ─┘
                                                                         │
                                                       next Qt turn ─────┘
                                                                         │
                                                    named command ─> mesoSPIM Core or GUI
```

“Request routing” is implemented by `Acceptor`. It moves work from a network thread to the Qt Core
thread. This matters because mesoSPIM Core and its stage objects belong to that thread.

Both transports then call the same `run(core, name, arguments)` function. This shared function is
the only path from a remote request to a command. It creates the operation record, enforces the
one-operation rule, and produces the public reply.

## Files

```text
mesoSPIM_RemoteControl_Config.py     constants, defaults, and shared names
mesoSPIM_RemoteControl_Dispatcher.py operation state, dispatch, JSON, and errors
mesoSPIM_RemoteControl_Commands.py   validation, limits, and 53 commands
mesoSPIM_RemoteControl_Servers.py    Core-thread routing, TCP, MCP, startup, and shutdown
mesoSPIM_RemoteControl_GUI.py        operator controls and acquisition-table bridge
```

Existing files receive only integration hooks:

- Core owns the current operation and active transport handle.
- MainWindow creates and closes the tab.


## One transport per session

The tab starts TCP or MCP, never both. Switching transport first stops the current listener. This
keeps operation ownership simple and prevents two independent network implementations from writing
to Core at the same time.

The tab is off by default. It does not bind a port during mesoSPIM startup.

## Threads

- The Qt Core thread owns Core, the serial worker, command execution, and operation state.
- TCP uses Qt's `QTcpServer` on the Core thread.
- MCP accepts HTTP on its own Python threads, then sends each command to the Core thread.
- The GUI thread owns widgets and the visible acquisition table.

Network threads never call hardware methods directly. The `Acceptor` sends a queued Qt signal and
waits only for Core to validate, reject, or admit the call. Every admitted ordinary mutation is
scheduled for a later Qt event-loop turn. Hardware and GUI work therefore begins after the accepted
reply has been created.

## Startup

`servers.start(core, mode, host, port, token)` checks everything before opening a port:

1. The selected transport name must be TCP or MCP.
2. A password is required.
3. The public default password is allowed only on loopback.
4. The loaded configuration must provide a usable limit for every stage axis.
5. `self_test` must prove, against a simulated Core, that valid values pass and invalid values are
   rejected.
6. Only then are request routing and the selected listener created.

If a check fails, startup reports the error to the tab and no port is opened.

## Validation order

Each command has a fixed name, argument validator, and implementation. A request is checked in this
order:

1. Is the command name supported?
2. Is the argument object valid?
3. Are types, options, and numeric ranges valid?
4. Are movement targets within the active limits?
5. Is another mutation already running?
6. Reserve an operation ID and schedule the command.

Input errors are reported before the busy check. This lets a client correct a bad request even when
another operation is active. Two valid mutations arriving together cannot both enter: admission is
protected by one lock and one Core-owned operation record.

## Extending the command set

> **Extension rule:** add new remote calls to `mesoSPIM_RemoteControl_Commands.py`. Do not add
> command-specific branches to the TCP server, MCP server, dispatcher, Core integration hooks, or
> MainWindow. A command registered once in `_Commands.py` is available through both transports.

Each new command should have three small parts:

1. An acceptance function validates the complete argument object and returns a clean dictionary.
   It must not change Core state or call hardware. Reuse validators such as `only`, `number`,
   `integer`, `flag`, `choice`, `axes_list`, and the movement-limit helpers.
2. An execution function receives only validated arguments. Keep it short and delegate to the
   existing mesoSPIM Core API instead of duplicating Core behavior.
3. A `command(...)` registration gives the call its public name, kind, validator, completion rule,
   and a concise input/output description.

For example, a short setting command follows this shape:

```python
def _accept_set_example(_core, args):
    only(args, ("value",))
    return {"value": number(args, "value", bounds=(0, 100))}


def _run_set_example(core, args):
    core.set_example(args["value"])
    return {"value": args["value"]}


command(
    "set_example",
    ACTION,
    _run_set_example,
    accept=_accept_set_example,
    hint="in: {value: 0..100}. out: {value}",
)
```

Choose the command kind according to its real completion rule. Both mutation kinds are admitted and
scheduled before their execution function runs:

- `READ` returns current information and never opens the mutation gate.
- `ACTION` is a short asynchronous mutation. It completes when its scheduled execution function
  returns.
- `WAIT` starts asynchronous work and retains the mutation gate until a verified milestone marks
  the operation `completed` or `failed`.
- `EMERGENCY` is reserved for bounded safety actions that must remain available while another
  mutation is active.

A `WAIT` command must not block the Core event loop. Use an existing completion signal through
`defer_wait`, or use a short Qt timer to poll authoritative readback as stage movement does. Never
mark an operation complete only because enough time has elapsed. If a genuinely new completion
signal is required, connect it in `Acceptor` and guard it against late signals from older
operations.

Before merging a new command:

- add its valid arguments and expected Core call to the shared test contracts;
- add missing, extra, wrong-type, boundary, out-of-range, and busy-state cases;
- prove the same acceptance, rejection, and result over TCP and MCP;
- add live DemoStage coverage when it can affect stage position, optics, acquisition, files, or
  other hardware state;
- update the command count and the table in `REMOTE_CONTROL_REFERENCE.md`;
- update the static workflow portion of `get_manual` when the command introduces a new workflow;
- extend `get_limits`, `get_capabilities`, and startup `self_test` when the command introduces a new
  hardware value, option, or safety limit.

The command list returned by `get_manual` is generated from the registry, so a correctly registered
command appears automatically over both transports. Its `hint` is also used by MCP `tools/list`;
write it as a compact but complete description rather than relying on private implementation
details.

## Replies and operation state

Reads return data directly. Emergency calls execute immediately. Every ordinary mutation first
returns the same small admission acknowledgement:

```json
{
  "accepted": true,
  "accepted_command": "move_absolute",
  "operation": {"id": "op-000001", "status": "processing"}
}
```

An operation has one of these useful public states:

- `processing`: accepted and still active;
- `stopping`: an emergency stop was requested;
- `completed`: its completion condition was confirmed;
- `failed`: execution or completion failed.

Clients poll `get_progress` and match the returned operation ID. The server stores the latest
operation, not a history. A completed operation includes the command-specific output under
`operation.result`. A failed operation includes `operation.error`. An accepted mutation must not be
resent merely because it is slow.

```json
{
  "operation": {
    "id": "op-000001",
    "command": "set_acquisition_list",
    "status": "completed",
    "result": {"count": 1}
  }
}
```

## Asynchronous stage movement

Absolute, relative, load, unload, and center moves use the same sequence:

```text
validate target
  -> reserve operation ID
  -> return processing
  -> enter the movement handler on the next Qt turn
  -> issue move with wait_until_done=False
  -> check position readback on a short Qt timer
  -> completed when every target axis is within tolerance
```

This keeps the Core event loop free. MCP and TCP can answer `get_progress`, `get_position`, and
emergency commands while movement is active.

The operation exposes its requested `target` and latest `observed` values. A stop before arrival
marks the move failed with `stop_requested: true`. Recovery cannot clear an unconfirmed stage move
just because Core's general state says `idle`; the operator must stop it first.

## Other long operations

Live mode, acquisitions, previews, and time lapse use mesoSPIM completion signals or independently
checked state. Their operation stays `processing` until the matching completion condition occurs.
Late signals are ignored when they do not belong to the active phase or running state.

Parts of upstream acquisition preflight are synchronous and may inspect network storage or show an
operator warning. They now run only after the acquisition call has returned its accepted operation
ID. The Qt TCP listener still shares Core's event loop, so preflight can temporarily delay a new TCP
connection or polling read. A client may safely retry `get_progress` after a network timeout, but it
must never resend the accepted mutation. MCP accepts HTTP connections on its server thread, although
read dispatch still waits for Core.

`clear_stuck_operation` is deliberately limited. It can release a lost-completion operation only
when independent Core state shows the activity has ended. It refuses queued work, active time lapse,
non-idle Core, and unconfirmed movement.

## Acquisition-list ownership

Time-lapse code reads the visible GUI acquisition model as well as Core state. A remote list must
therefore update both places with the same validated object. The tab owns a Qt bridge from Core to
the GUI thread and waits for the table replacement to finish. That bridge runs after the accepted
reply; clients observe its success or failure by polling the operation. This prevents old GUI rows
from overwriting a remote list later without making TCP or MCP wait for the GUI update.

`acquire_start` temporarily installs one supplied row and saves the operator's previous list.
`acquire_finish` restores that exact object, including `planes` metadata.

## Shutdown

Shutdown closes request acceptance first, closes the selected listener, disconnects completion
signals, and clears the transport handle. A request queued before shutdown is discarded before it
can call hardware. MainWindow waits for this sequence before continuing application teardown.

## Security boundaries

- Commands are fixed names; no remote code is evaluated.
- All arguments are strict JSON with duplicate keys and non-finite numbers rejected.
- A password is required and compared in constant time.
- MCP rejects non-local browser origins.
- TCP and MCP default to loopback.
- Plain TCP and HTTP do not provide encryption. Use an SSH tunnel or VPN on an untrusted network.
- An authenticated client is treated as a trusted microscope operator, not as a sandboxed tenant.
  `stat_files` can inspect supplied paths, `reload_etl_config` can read an ETL file by path, and
  `save_etl_config` writes the active ETL configuration. Protect the password and restrict network
  access accordingly.

## Known limits

1. The one-operation rule coordinates remote clients, not local GUI actions. The operator must not
   start conflicting GUI work during remote control.
2. `get_progress` reports only the latest operation. Clients must retain and compare its ID.
3. The MCP endpoint advertises revision `2024-11-05` and implements the methods needed here
   (`initialize`, `tools/list`, `tools/call`), not the complete lifecycle or newer Streamable HTTP
   revisions.
4. The API reports acquisition metadata and progress, not image pixels.
5. Warning dialogs remain mesoSPIM dialogs; Remote Control does not dismiss them.
6. Remote Control does not provide a filesystem sandbox. Its authenticated file-related commands
   intentionally use the same host access as the local mesoSPIM operator.
