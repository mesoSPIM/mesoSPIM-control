# Remote Control

TCP and MCP expose the same 53 commands. They use the same names, arguments, limits, operation
state, and error codes. The operator chooses one transport in the Remote Control tab; both cannot
run together.

Call `get_manual`, `get_info`, and `get_limits` before making changes. `get_manual` returns this same
accepted/rejected-and-poll workflow over both transports, together with a command list generated
from the running command registry.

## Connect

### TCP

The default address is `127.0.0.1:42000`. TCP messages use this frame format:

```text
<number of UTF-8 bytes>\n<payload>
```

Send the password as the first frame. The server replies `OK` or `AUTH-FAILED`. After that, send one
JSON command per frame. A successful reply begins with `__MESOSPIM_OK__`; an error begins with
`error: [code]`.

### MCP

The default URL is `http://127.0.0.1:42100/mcp`. Send JSON-RPC POST requests with:

```text
Authorization: Bearer <Remote Control password>
```

Microscope commands use the MCP method `tools/call`. `initialize` and `tools/list` are also
supported. The endpoint advertises MCP revision `2024-11-05` and intentionally implements only
these three methods as authenticated HTTP POST requests. It does not claim the resources, prompts,
streaming, sessions, or complete lifecycle of newer MCP Streamable HTTP revisions.

The host and ports can be changed in the tab. Do not hard-code or commit the password.

## Call format

TCP payload:

```json
{"move_absolute":{"targets":{"x":100}}}
```

Equivalent MCP request:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"move_absolute","arguments":{"targets":{"x":100}}}}
```

The server executes only names from its fixed command list. It never executes Python or text sent by
the client.

## Accepted calls and polling

Read commands return their data directly and do not create an operation. Every ordinary mutation
is either rejected before it starts or accepted with a new operation record. Rejection checks
include the command name, argument shape, value types, configured options, hardware and stage
limits, and the one-mutation gate.

```json
{
  "accepted": true,
  "accepted_command": "move_absolute",
  "operation": {
    "id": "op-000123",
    "command": "move_absolute",
    "status": "processing"
  }
}
```

For an ordinary mutation, `accepted` means the request passed validation, was admitted by the gate,
and was scheduled. Core, hardware, and GUI work begins afterward. It does not mean the requested
work has finished.

When the status is `processing` or `stopping`, call `get_progress` through the same TCP or MCP
transport and verify that the returned operation ID is unchanged. Stop when its status becomes
`completed` or `failed`. On completion, command-specific output is stored in `operation.result`.
On failure, the reason is stored in `operation.error`.

Emergency commands validate and execute immediately so they remain available while the ordinary
mutation gate is busy. They do not create a new operation. Their reply contains the current
operation snapshot; if it has an ID, continue polling that operation until it is terminal.

For stage movement, the command is sent with `wait_until_done=False`. mesoSPIM remains able to answer
reads while the stage travels. The operation becomes `completed` only when position readback reaches
every requested axis within the configured tolerance. The operation reports both `target` and the
latest `observed` position.

Important client rules:

- Never resend accepted ordinary work because polling is slow.
- If a response is lost, reconnect and inspect `get_progress` before deciding what happened.
- A synchronous acquisition preflight can temporarily delay TCP reads. Retrying the read-only
  `get_progress` call is safe; retrying the accepted mutation is not.
- Match the operation ID; `get_progress` reports the latest operation, not an operation history.
- A second mutation is rejected with `busy` while one is still running.
- Reads and emergency commands remain available while an asynchronous mutation is active, subject
  to the Core event loop being responsive.

## Small TCP client example

This example uses only the Python standard library:

```python
import json
import os
import socket
import time


def send_frame(sock, text):
    data = text.encode("utf-8")
    sock.sendall(str(len(data)).encode("ascii") + b"\n" + data)


def receive_frame(sock):
    data = b""
    while b"\n" not in data:
        data += sock.recv(4096)
    header, _, payload = data.partition(b"\n")
    size = int(header)
    while len(payload) < size:
        payload += sock.recv(4096)
    return payload[:size].decode("utf-8")


def call(sock, name, **arguments):
    send_frame(sock, json.dumps({name: arguments}))
    reply = receive_frame(sock)
    if not reply.startswith("__MESOSPIM_OK__"):
        raise RuntimeError(reply)
    return json.loads(reply[len("__MESOSPIM_OK__") :])


def wait_for_operation(sock, accepted):
    operation_id = accepted["operation"]["id"]
    while True:
        operation = call(sock, "get_progress")["operation"]
        if operation.get("id") != operation_id:
            raise RuntimeError("the latest operation changed")
        if operation.get("status") == "completed":
            return operation
        if operation.get("status") == "failed":
            raise RuntimeError(operation.get("error", "operation failed"))
        time.sleep(0.05)


host = os.environ.get("MESOSPIM_REMOTE_HOST", "127.0.0.1")
port = int(os.environ.get("MESOSPIM_REMOTE_PORT", "42000"))
timeout = float(os.environ.get("MESOSPIM_REMOTE_TIMEOUT", "10"))
with socket.create_connection((host, port), timeout=timeout) as sock:
    send_frame(sock, os.environ["MESOSPIM_REMOTE_PASSWORD"])
    assert receive_frame(sock) == "OK"
    print(call(sock, "get_info"))
    accepted = call(sock, "move_absolute", targets={"x": 100})
    print(wait_for_operation(sock, accepted))
```

## Error codes

Both transports return the same code and a readable message.

| Code | Meaning | Client action |
| --- | --- | --- |
| `validation` | A type, option, range, limit, or argument name is wrong. Nothing started. | Correct the request. |
| `busy` | Another mutation is running. | Keep polling the active operation, then try again. |
| `unknown_command` | The command name is not supported. | Correct the name. |
| `execution` | Dispatch or an immediate read/emergency handler failed. | Read the message; poll any returned operation ID before retrying. |

## Calls

The concise [Remote Control call list](calls.md) names all 53 calls and explains
their purpose. For exact arguments, call `get_manual` against the running microscope. Its command
hints are generated from the same registry used by TCP and MCP, so they cannot drift from the
installed implementation.

## Limit enforcement

The server validates structure, names, types, configured options, numeric ranges, stage travel, and
the active operation before calling mesoSPIM.

Before opening a network port, startup runs the same movement checks against a simulated Core using
the loaded microscope configuration. If any axis lacks a usable limit or the check fails, the
server does not start. `self_test` repeats this hardware-free check on demand.

```{toctree}
:hidden:

calls
architecture
testing
```
