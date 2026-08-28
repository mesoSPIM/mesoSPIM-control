# Testing Remote Control

Remote Control has four reviewer-facing test commands. Run them from the repository root.

Install pytest once if it is not already available in the mesoSPIM environment:

```text
python -m pip install pytest==8.3.4
```

```text
python mesoSPIM/test/remote_control/run.py offline
python mesoSPIM/test/remote_control/run.py pyqt
python mesoSPIM/test/remote_control/run.py live mcp
python mesoSPIM/test/remote_control/run.py live tcp
```

| Profile | Requires | Can change a microscope? | Expected result |
| --- | --- | --- | --- |
| `offline` | Python and pytest | No | All command, validation, protocol, and GUI tests pass. |
| `pyqt` | PyQt5 | No | Both real-PyQt smoke scripts pass on temporary loopback ports. |
| `live mcp` | Running DemoStage and an operator-started MCP server | Yes, DemoStage only | 2 valid and 6 adversarial tests pass. |
| `live tcp` | Running DemoStage and an operator-started TCP server | Yes, DemoStage only | 2 valid and 6 adversarial tests pass. |

The runner only selects and orders tests. It never starts or stops mesoSPIM, MCP, or TCP.

## Offline tests

The offline profile uses an in-memory Core and a small PyQt substitute. It verifies:

- the complete 53-call registry over TCP and MCP;
- accepted, rejected, completed, failed, stopping, and busy replies;
- argument types, configured options, numeric ranges, and stage limits;
- strict JSON, TCP framing, MCP authentication, origins, paths, and body limits;
- the one-mutation gate, cross-transport behavior, and concurrent admission;
- acquisition-list handling, native `planes` metadata, preflight recovery, and time lapses;
- operator controls and the acquisition-table bridge.

No listener is exposed outside temporary loopback addresses, and no microscope process is started.

## Real PyQt smoke tests

The PyQt profile runs two scripts outside pytest's fake-Qt environment. The first constructs the
Remote Control widgets and checks signal, timer, and shutdown behavior without opening a port. The
second opens temporary loopback TCP and MCP listeners against a fake Core and verifies that:

- a mutation returns its accepted operation before Core work starts;
- reads remain available while the operation is processing;
- stage completion is reported only after position readback reaches the target;
- both listeners and their worker threads stop cleanly.

These scripts do not start mesoSPIM or access hardware.

## Live DemoStage tests

Live tests are intentionally operator-gated. Start mesoSPIM with DemoStage, then use the Remote
Control tab to start exactly one transport. Confirm the other transport is stopped.

Set these safety variables before either live profile:

```text
MESOSPIM_ALLOW_DEVICE_CHANGE=1
MESOSPIM_OPERATOR_PRESENT=1
MESOSPIM_CONFIRM_DEMO_MODE=1
MESOSPIM_RUN_ALL_COMMANDS=1
MESOSPIM_RUN_LIVE_ADVERSARIAL=1
MESOSPIM_DEMO_ROOT=<tested checkout>
MESOSPIM_DEMO_ETL_CONFIG_PATH=<ETL file inside the tested checkout>
MESOSPIM_DEMO_PROCESS_ID=<running mesoSPIM process ID>
```

For MCP, also set:

```text
MESOSPIM_LIVE_MCP_URL=http://127.0.0.1:42100/mcp
MESOSPIM_LIVE_MCP_TOKEN=<password entered in the tab>
```

For TCP, also set:

```text
MESOSPIM_LIVE_TCP_HOST=127.0.0.1
MESOSPIM_LIVE_TCP_PORT=42000
MESOSPIM_LIVE_TCP_TOKEN=<password entered in the tab>
```

The live runner executes the valid movement and complete command sweep first. It starts the
adversarial suite only if the valid phase passes. The live tests independently verify that
`get_limits` reports `DemoStage` before broad mutations.

For each transport:

1. Start the transport manually in the Remote Control tab.
2. Verify the other transport is stopped.
3. Run the matching live command.
4. Confirm Core state, position, settings, acquisition list, ETL file, and generated files were
   restored.
5. Stop the transport manually before switching.

After both transports pass, close mesoSPIM with **File > Exit**. Verify that the application
process exits, ports 42000 and 42100 close, and no mesoSPIM, Python, or Qt worker remains.

## Interpreting asynchronous results

An accepted mutation has started an operation; it has not necessarily succeeded yet. Tests retain
the operation ID and poll `get_progress` until the same operation becomes `completed` or `failed`.
They never repeat an accepted mutation because its first response was delayed.

If polling is delayed, retrying the read-only `get_progress` call is safe after Core becomes
responsive. Resending the mutation is not. Record any visible warning dialog or slow acquisition
preflight so the delay can be diagnosed.
