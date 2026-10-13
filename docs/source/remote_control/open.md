# Open items

What is not finished, not verified, or left for a decision, as of 2026-10-11. Everything else in the
[call list](calls.md) was checked on the demo on Windows: the live sweep of all 84 calls over TCP and
over MCP (each window call by its effect, the demo's state restored), the AI Assistant tab with
Claude Haiku 5.5, and the real-Qt tests.

## Not verified

- **The webcam's picture** (`get_picture` with `window: "webcam"`). The test PC's webcam showed no
  picture in its own window either, and its still capture never became ready, so the call returned
  "the webcam sent no picture within 5 s". To check on a PC with a working webcam.
- **The real microscope.** The calls were checked in demo mode only. The real-hardware sweep
  (`live/test_all_commands_real_hardware.py`) checks each call by its effect with small changes
  and puts each back; run on the demo with its DemoStage refusal taken out, it verified 81 of 84
  over TCP (the three stage travels not run by default) and 84 of 84 over MCP with them, the ETL
  file unchanged. It has not been run on the microscope.

## Not offered

- **Cancelling an analysis.** The field curvature tool's progress dialog has a Cancel; the
  `analyse_field_curvature` call runs to the end.
- **On purpose:** the jog buttons' step boxes (`move_relative` takes the step itself), the script
  editor (it runs code) and closing mesoSPIM.

## For a decision

- **The size of each AI Assistant request.** The assistant is offered every call, so the 17 window
  calls add about 2,900 tokens of tool definitions to every request (`set_display` about 1,000);
  in the tab the meter read about 21,000 tokens per request. On Anthropic models the tools are
  cached. Keeping the display, picture and analysis calls to TCP and MCP would leave about 900.
- **The laser pulse's max amplitude** can now be set remotely, as in the Parameters tab, but
  waveform generation does not apply it (it never has): applying it is a separate change to Core.

## Found, not fixed (outside this change)

- **HTTPS inspection.** On a network that inspects HTTPS, the AI Assistant cannot reach a cloud
  model ("certificate verify failed"): the client trusts certifi's list only. Pointing
  `SSL_CERT_FILE` at a bundle of certifi's roots and the Windows roots, before mesoSPIM starts, lets
  it connect.
- **Dragging a row in the acquisition table** may delete rows: drag-and-drop is enabled but
  `dropMimeData` does nothing and reports success (`utils/models.py`). Not tried by hand.
- **`test/test_tiling.py::test_image_counts`** fails, with or without this change: it builds the
  tiling wizard without the parent window it needs.

## Where the rest of the tests are

This branch carries the code, the docs, the live sweeps and the real-Qt tests. The offline suite
(the Remote Control stand-ins, the transport matrix, the window coverage map, and the AI
Assistant's evaluation with its recorded runs, the windows cases among them) is on the development
branch `agent/gui-handles`: 1355 tests, all passing there.
