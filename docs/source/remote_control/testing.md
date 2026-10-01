# Testing Remote Control

Remote Control has three test commands. Run them from the repository root.

Install pytest once if it is not already available in the mesoSPIM environment:

```text
python -m pip install pytest==8.3.4
```

```text
python mesoSPIM/test/remote_control/run.py pyqt
python mesoSPIM/test/remote_control/run.py live mcp
python mesoSPIM/test/remote_control/run.py live tcp
```

| Profile | Requires | Can change a microscope? | Expected result |
| --- | --- | --- | --- |
| `pyqt` | PyQt5 | No | The real-PyQt scripts and the combo-box tests pass, on temporary loopback ports. |
| `live mcp` | Running DemoStage and an operator-started MCP server | Yes, DemoStage only | 2 tests pass. |
| `live tcp` | Running DemoStage and an operator-started TCP server | Yes, DemoStage only | 2 tests pass. |

The runner only selects and orders tests. It never starts or stops mesoSPIM, MCP, or TCP.

## Real PyQt tests

The PyQt profile runs four scripts, then the Main Window's combo-box tests
(`mesoSPIM/test/test_combobox_state_requests.py`). The first script constructs the Remote Control
widgets and checks the warning route, signals, timers and shutdown without opening a port. The
second opens temporary loopback TCP and MCP listeners against a fake Core and verifies that:

- `localhost` binds the loopback interface, an empty password or a hostname never binds, and a
  connected client that sends no password is dropped after the authentication timeout;
- a mutation returns its accepted operation before Core work starts;
- reads remain available while the operation is processing;
- stage completion is reported only after position readback reaches the target;
- every TCP client socket is one PyQt created, and a client that reconnects for every call is
  answered every time;
- both listeners and their worker threads stop cleanly.

The third builds the AI Assistant tab offscreen and checks its layout and input keys; the
offscreen platform on Windows has no fonts, so there it skips the width checks and says so
(`QT_QPA_PLATFORM=windows` measures them). The fourth runs the assistant's schedules through a
real worker thread and Acceptor against a scripted model.

These scripts do not start mesoSPIM or access hardware. `pytest mesoSPIM/test` leaves the
`remote_control` and `ai_assistant` folders out (`norecursedirs` in `pyproject.toml`); run them
through this runner.

## Live DemoStage tests

Live tests are intentionally operator-gated. Start mesoSPIM with DemoStage, then use the Remote
Control tab to start exactly one transport. Confirm the other transport is stopped.

Set these safety variables before either live profile:

```text
MESOSPIM_ALLOW_DEVICE_CHANGE=1
MESOSPIM_OPERATOR_PRESENT=1
MESOSPIM_CONFIRM_DEMO_MODE=1
MESOSPIM_RUN_ALL_COMMANDS=1
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

The live runner executes the valid X movement (`live/test_valid.py`) and the complete command sweep
(`live/test_all_commands.py`). The sweep verifies that `get_limits` reports `DemoStage` before
broad mutations.

For each transport:

1. Start the transport manually in the Remote Control tab.
2. Verify the other transport is stopped.
3. Run the matching live command.
4. Confirm Core state, position, settings, acquisition list, ETL file, and generated files were
   restored.
5. Stop the transport manually before switching.

After both transports pass, close mesoSPIM with **File > Exit**. Verify that the application
process exits, ports 42000 and 42100 close, and no mesoSPIM, Python, or Qt worker remains.

## Real-hardware command sweep

`live/test_all_commands_real_hardware.py` is the same sweep for a real instrument, and refuses to
run against a DemoStage. Read its module docstring first: it moves the stage to the configured
load, unload and center positions, fires the laser for single-plane acquisitions, and overwrites
and restores the live ETL file. An operator must watch the instrument for the whole run. On top of
the device and operator variables above, it needs `MESOSPIM_RUN_REAL_ALL_COMMANDS=1`,
`MESOSPIM_CONFIRM_REAL_HARDWARE=I_UNDERSTAND_THIS_MOVES_REAL_HARDWARE` and
`MESOSPIM_LIVE_REAL_TRANSPORT` (`mcp` or `tcp`), and it runs once per endpoint and transport.

## Interpreting asynchronous results

An accepted mutation has started an operation; it has not necessarily succeeded yet. Tests retain
the operation ID and poll `get_progress` until the same operation becomes `completed`, `stopped` or
`failed`.
They never repeat an accepted mutation because its first response was delayed.

If polling is delayed, retrying the read-only `get_progress` call is safe after Core becomes
responsive. Resending the mutation is not. Record any visible warning dialog or slow acquisition
preflight so the delay can be diagnosed.
