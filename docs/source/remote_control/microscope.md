# Testing at the microscope

How to check this branch on a real mesoSPIM, in about an hour. Stand by the instrument the whole
time. Run from a local clone on the microscope PC, not from a network drive.

## Before you start

- Check out `remote-control-ai-assistant`, start mesoSPIM as usual, and put a sample (or a bead
  slide) under the objective that can take a little light.
- The mesoSPIM environment needs `pytest`, `numpy` and `tifffile` for the sweep.
- Note the stage position, the laser intensity and the acquisition list, so you can compare them
  afterwards.

## 1. The automatic sweep, over TCP

In the Remote Control tab, choose TCP, port 42000, a token of your own, and Start. Then, in
PowerShell from the clone's folder:

```powershell
$env:MESOSPIM_ALLOW_DEVICE_CHANGE="1"; $env:MESOSPIM_OPERATOR_PRESENT="1"
$env:MESOSPIM_RUN_REAL_ALL_COMMANDS="1"
$env:MESOSPIM_CONFIRM_REAL_HARDWARE="I_UNDERSTAND_THIS_MOVES_REAL_HARDWARE"
$env:MESOSPIM_LIVE_REAL_TRANSPORT="tcp"; $env:MESOSPIM_LIVE_TCP_PORT="42000"; $env:MESOSPIM_LIVE_TCP_TOKEN="<your token>"
python -m pytest -s mesoSPIM/test/remote_control/live/test_all_commands_real_hardware.py
```

It sends every call once, with small changes only, and puts each back:
- **Stage:** at most 25 µm on X.
- **Focus:** the autofocus over ±20 µm, discarded.
- **Laser:** 1–2 % intensity.
- **Settings:** one step each, restored.
- **ETL file:** a copy is used; the real file is never written.

It ends with `81 OF 84 COMMANDS VERIFIED; NOT RUN: load_sample, unload_sample, center_sample`.

**Watch for:**
- **The window:** it follows every change.
- **The galvos:** the beam stops briefly when Freeze galvos is on.
- **The clean-up:** at the end, position, intensity and the acquisition list are as you noted them.

**If it goes wrong:**
- **A move "never arrives":** set `$env:MESOSPIM_REAL_POSITION_TOLERANCE_UM="5"` and run again.
- **Running again:** it runs once per port and transport, so delete `.mesospim_real_all_*.done`
  in `$env:TEMP` first.
- **If you stop it midway:** check by hand the stage position, the laser intensity, Freeze galvos
  (ETL tab), the processor chain, the ETL file in use, and the acquisition list.

## 2. The same over MCP

Stop Remote Control, choose MCP, Start, and run the same command with these two lines changed:

```powershell
$env:MESOSPIM_LIVE_REAL_TRANSPORT="mcp"; $env:MESOSPIM_LIVE_MCP_TOKEN="<your token>"
```

## 3. Load, unload and centre sample (optional, empty stage only)

These travel to the positions in the config, which can be far. With the sample out, set
`$env:MESOSPIM_REAL_LARGE_MOVES="1"`, delete the `.done` file, and run step 1 again: it should
end with `84 OF 84`.

## 4. By eye, over TCP

With Remote Control on TCP, in Python from the clone's folder:

```python
from mesoSPIM.test.remote_control.support.clients import RemoteControl
rc = RemoteControl(port=42000, token="<your token>")
rc.call("start_live")
rc.call("set_display", colormap="magma", adjust_levels=True)         # the live view turns magma
rc.call("set_display", box_roi={"x": 500, "y": 500, "width": 400, "height": 300})
rc.call("get_display")["camera_window"]["box_roi"]                    # the box, in pixels and um
rc.call("stop_activity")
```

Check that each change shows in the camera window as you would set it by hand.

## 5. One tiling list, built by call and run

Build a small list around the sample (2 × 2 tiles, a few planes, low intensity) with
`build_tiling_list`, look at it in the acquisition manager, and run it with
`run_acquisition_list`. The files should appear where the list says, and the progress bars should
move.

## 6. The AI Assistant

Before starting mesoSPIM, set the model's key (`$env:ANTHROPIC_API_KEY` for Claude). If the
network inspects HTTPS, the assistant cannot connect; see [Open items](open.md). In the AI
Assistant tab, connect, then ask:
- **"Take a look at the sample":** it should snap a frame and describe what it sees.
- **"Move 20 µm to the left":** the stage should move 20 µm, in the direction you meant.
- **"Use the magma lookup table":** the live view should turn magma.
- **"Find the best focus automatically, ±20 µm, and use it":** the autofocus should run and its
  result be applied.
- **"Start a time lapse of 2 time points, 10 s apart":** it should end with one grey line in the
  chat.

Note anything it gets wrong: its words and what it did.

## What to report

For each step: passed, or the failing line of the output, plus anything you saw that the output
did not say. Report in the PR.
