# mesoSPIM-control: Architecture, Bottlenecks, and a Path to 10× Throughput

## 1. How the software is structured

The program is a PyQt5 application built around one orchestrator object, `mesoSPIM_Core`, that owns the hardware and paces every acquisition. Three long-lived Qt threads do the real work, wired together with signals/slots:

- **Core / GUI thread** — `mesoSPIM_Core` and `mesoSPIM_MainWindow`. The Core is the "pacemaker": it drives waveforms, steps the stage, and emits per-plane signals. The `mesoSPIM_Serial` stage worker also lives here (it was deliberately *not* moved to its own thread).
- **Camera thread** (`HighPriority`) — `mesoSPIM_Camera` + a driver subclass (`mesoSPIM_HamamatsuCamera`, `Photometrics`, `PCO`, `Demo`). Pulls frames from the camera SDK and pushes them into two `collections.deque` queues.
- **ImageWriter thread** (`HighPriority`) — `mesoSPIM_ImageWriter` + a pluggable writer backend (TIFF / BigTIFF / HDF5-BDV / OME-Zarr / OME-Zarr-MP / Raw). Pops frames off the shared queue and streams them to disk.

Data is handed between threads through two deques created in the Core, deliberately bypassing Qt's signal/slot payload marshalling for the pixel data (a v1.10 optimization):

- `frame_queue` — full-resolution frames destined for disk.
- `frame_queue_display` (`maxlen=1`) — a single latest frame for the live view.

### The per-plane acquisition loop (the hot path)

`mesoSPIM_Core.run_acquisition()` runs a synchronous Python `for` loop over Z planes. Each iteration does, **in order**:

1. `snap_image_in_series()` → `start_tasks()`, `run_tasks()`, `stop_tasks()` on the NI-DAQ. `run_tasks()` calls `wait_until_done()` on every AO/trigger task, so the Core thread **blocks for the full `sweeptime`** (exposure + galvo/ETL ramp) on every plane.
2. `sig_add_images_to_image_series.emit()` → queued to the Camera thread, which calls `camera.get_images_in_series()` (DCAM `getFrames` → `memmove` each frame into a fresh numpy array), runs the optional processor chain, `extend`s `frame_queue`, throttles a display frame, and emits `sig_write_images` to the writer thread.
3. `move_relative(move_dict)` → steps Z (and F) to the next plane over serial.
4. `QApplication.processEvents(…, 50)` → pumps the event loop so the queued camera/writer/stage slots actually run and the Stop button stays live.

So frame *grab* and *disk write* are genuinely concurrent (they run in other threads, and the SDK memmove, NI wait, and tifffile write all release the GIL). But the **stepping itself is stop-and-go and fully serialized on the Core thread**: expose → stop tasks → step stage → restart tasks → expose.

### Camera grab

`HamamatsuCameraMR` attaches DCAM-owned buffers, and `getFrames()` locks each new frame and `memmove`s it into a `uint16` numpy array (`HCamData`). Frames come out as a list, so multi-frame backlogs are drained in one call. Backlog vs. `number_image_buffers` is tracked and warned on.

### Disk streaming

The writer pops a frame, does `.T[::-1]` (a cheap view — but non-contiguous, so the backend re-copies it on write), and calls `writer.write_frame()`. Backends vary a lot: `TiffWriter` is a thin `tifffile` append (no compression, no chunking); `OmeZarrWriterMP` fans writes out to **separate writer processes**, which is the only backend that escapes the GIL for compression/encoding.

---

## 2. Where the bottlenecks are

**A. Stop-and-go stepping is the dominant limit.** The volume rate is `sweeptime + per-plane overhead` per plane, and the overhead is not small: NI tasks are `stop`/`start`-ed every plane, the stage does a discrete move-and-settle every plane, and everything is gated behind a `wait_until_done()` on the Core thread followed by `processEvents`. At short exposures (5–20 ms, the fast configs) this fixed overhead can rival or exceed the exposure itself, so you're often running at half the camera's intrinsic frame rate or worse.

**B. The Core thread does too much, synchronously.** Waveform pa/task control, the blocking `wait_until_done`, the stage `move_relative`, *and* the GUI all share one thread. The `processEvents()` call in the inner loop couples acquisition pacing to GUI responsiveness. The serial stage worker was intentionally left in the Core thread, so stage comms and pacing interleave.

**C. Per-plane NI task teardown/setup.** `start_tasks`/`stop_tasks` every plane adds driver-call latency that a single continuous (or retriggerable) waveform task would avoid entirely.

**D. Writer backend choice.** The default TIFF/BigTIFF path is single-threaded, uncompressed, and non-chunked. Under Python's GIL, one writer thread doing encode+write competes with the camera thread for the interpreter. Only `OmeZarrWriterMP` (multi-process) truly parallelizes writing and compression — but ImageJ-TIFF is still the common default.

**E. Extra copies / GIL contention on the hot path.** Frames get memmove'd out of DCAM, transposed to a non-contiguous view, then re-copied by the writer backend, plus optional processor-chain copies (`[process(img) for img in images]`). Each is modest, but they all land on the GIL and add up at high frame rates.

**F. Camera readout ceiling.** For a given sensor mode / ROI / exposure, the sCMOS has a hard FPS ceiling. Full-frame 2048² leaves less headroom than a cropped ROI or binned readout.

---

## 3. How to get ~10×

No single change gets 10×; it comes from removing the stop-and-go overhead **and** sustaining disk bandwidth **and** cutting per-frame Python cost. Roughly in order of impact:

**1. Continuous constant-velocity Z scanning with hardware-timed triggering (biggest win).**
Replace per-plane "move → settle → expose" with a constant-velocity stage sweep while the camera free-runs on a hardware trigger and the galvo/ETL waveform is a single continuous or retriggerable NI task. This deletes per-plane stage-settle time and per-plane task restart entirely, so the volume rate collapses toward the camera's intrinsic frame rate. ASI stages already expose TTL motion (`ttl_motion_enabled`), which is the hook for this — extend it from "TTL step per plane" to "scan + camera-paced planes." This alone often recovers 2–5×.

**2. Take the blocking wait and the stage worker off the Core/GUI thread.**
Let the camera's hardware trigger pace acquisition instead of a Python `wait_until_done()` loop calling `processEvents`. Move `mesoSPIM_Serial` to its own thread. The Core becomes an event-driven state machine rather than a synchronous stepping loop. This removes the coupling between GUI responsiveness and acquisition rate and eliminates dead time between planes.

**3. Use a parallel, chunked, streaming writer by default (`OmeZarrWriterMP`) and fast storage.**
Multi-process writing bypasses the GIL for compression/encoding and lets you scale write throughput with cores. Pair it with chunked output, a fast codec (e.g. Blosc/LZ4-class), and an NVMe or striped RAID target. If the camera can outrun one disk, you need parallel writers + parallel disk, not a single `tifffile` append. Verify with `test_writing_speed.py`-style measurement on the actual target volume.

**4. Cut per-frame copies and Python overhead on the hot path.**
Keep frames contiguous end-to-end (fold the `.T[::-1]` orientation into the writer or do it once, contiguously, so backends don't silently re-copy). Skip the processor chain when disabled (it already checks `is_enabled` — keep it truly zero-copy). Ensure `number_image_buffers` is generous so `getFrames` drains multi-frame backlogs instead of stalling. Drop `processEvents` out of the pacing path once acquisition is event-driven.

**5. Raise the camera ceiling where the science allows.**
Cropped/rolling ROI, binning, the fastest readout/sensor mode, and tuned line interval (ASLM) all raise the intrinsic FPS the pipeline can then keep up with. This is config-level and complements the above.

### Realistic expectation

- Items **1–2** attack the stop-and-go overhead and are where most of the factor comes from (commonly 3–5×).
- Item **3** ensures disk can absorb the higher frame rate rather than becoming the new wall.
- Items **4–5** recover the remaining Python/copy overhead and lift the camera ceiling.

Combined, 10× is plausible for the short-exposure regime where fixed overhead currently dominates; for long exposures (200 ms configs) you're already near the exposure-bound limit and the ceiling is lower — there the win is mostly hiding stage/task overhead, not multiplying the exposure-limited rate.

---

## 4. Step-and-shoot, optimized: measured overhead and realistic ceiling

Constraint: continuous constant-velocity scanning is ruled out because it tilts the imaged planes relative to Z. Keeping discrete step-and-shoot (planes orthogonal to Z), the achievable gain is bounded by how much *fixed software overhead* we can strip off each plane, plus any reduction of the sweeptime itself.

The example configs are revealing. Each encodes a `sweeptime` and an observed frame rate (in the filename / `average_frame_rate`):

| Config | sweeptime | ceiling = 1/sweeptime | observed FPS | per-plane time | fixed overhead/plane | headroom to ceiling |
|---|---|---|---|---|---|---|
| `exp10ms-wf73ms` | 73 ms | 13.7 FPS | 6 | 167 ms | ~94 ms | ~2.3× |
| `exp10ms-wf130ms` | 130 ms | 7.7 FPS | 4.4 | 227 ms | ~97 ms | ~1.7× |
| `exp5ms-wf73` | 73 ms | 13.7 FPS | 8 | 125 ms | ~52 ms | ~1.7× |
| `exp5ms-wf37` | 37 ms | 27 FPS | 8 | 125 ms | ~88 ms | ~3.4× |

Two things stand out:

1. **A near-constant ~50–100 ms of overhead sits on top of every plane, independent of sweeptime.** You are running at roughly 40–55% of your own waveform-limited ceiling.
2. **It is not the stage.** These configs use `ttl_motion_enabled: True` on the TigerASI, so Z/F stepping is hardware-triggered from the waveform — there is no per-plane serial move round-trip in `run_acquisition`'s loop (the non-TTL branch is skipped). The overhead is therefore dominated by:
   - **Per-plane NI task teardown/re-arm**: `start_tasks()` / `run_tasks()` / `stop_tasks()` are called every plane, arming and disarming the galvo-ETL, laser, camera-trigger, and stage-trigger tasks (~2 arming operations × 4 tasks × N planes). Restarting hardware-timed NI tasks has real driver latency.
   - **Core-thread Python cost**: the `QApplication.processEvents(…, 50)` pump in the pacing loop, per-plane progress bookkeeping, and queue handling all run synchronously on the Core thread between planes.

**What optimizing the current step motion buys (no geometry change):** arm the waveform generation *once* and let the hardware repeat it per plane instead of stop/start each plane; take pacing off `processEvents`; trim the per-plane Python. That moves you from ~45–55% of the sweeptime ceiling to ~85–95% of it:

- readout-heavy configs (`wf130`): 4.4 → ~7 FPS (**~1.6×**)
- mid configs (`wf73`): 6–8 → ~11–12 FPS (**~1.5–2×**)
- short-sweeptime config (`wf37`): 8 → ~22–24 FPS (**~2.7–3×**)

So **~2× is a realistic typical gain, up to ~3× where fixed overhead dominates — purely from removing software overhead, with planes staying orthogonal to Z.**

**Going beyond ~2–3× requires cutting the sweeptime itself**, which is independent of the stepping question. The sweeptime here is rolling-shutter/readout-bound: at a 75 µs line interval, a tall ROI dominates (e.g. 2048 rows × 75 µs ≈ 150 ms). Sweeptime scales roughly linearly with the number of rows, so cropping the ROI vertically, increasing the line rate, or vertical binning cuts sweeptime proportionally and is fully compatible with orthogonal-plane step-and-shoot. A genuine 10× would need the overhead fix **and** a ~5× sweeptime reduction — hard at full frame, feasible with a cropped ROI.

## 5. DAQ constraint: does the PXI-6733 support true retriggering?

**No — not natively.** The optimization in Section 4 ("arm once, retrigger per plane") assumes hardware retriggerable analog output, and the PXI-6733 does not support it natively.

Per NI's own documentation (*Retriggerable Tasks in NI-DAQmx*): "**Only NI X Series multifunction DAQ devices (63xx) natively support retriggerable tasks.**" A retriggerable finite task re-arms and generates a fresh finite waveform on every hardware start trigger, entirely in hardware, with no software involvement between triggers — which is exactly what would eliminate the per-plane re-arm overhead.

The PXI-6733 is a **673x-family high-speed analog-output device** (DAQ-STC-generation architecture, 8 AO channels, ~1 MS/s/ch, 2 onboard counter/timers), **not** an X-Series board. NI's supported-properties list for the 6733 does expose a `Start…Retriggerable` property name, but the authoritative guidance above is decisive: native retriggerable AO is an X-Series feature; on prior-generation devices it must be *emulated*.

Two hardware-timed paths keep step-and-shoot (orthogonal planes) while removing the per-plane `start/stop` on the existing 6733:

**(a) Continuous regeneration — recommended, lowest risk.** Program the AO task *once* in continuous sample mode with regeneration allowed. The single-plane sweep waveform repeats automatically every `sweeptime`; the camera-trigger and stage-step TTLs are embedded in the same clocked sequence. Software starts the generation once and streams N planes — no per-plane driver calls at all. This fits step-and-shoot precisely *because the cadence is fixed* (constant sweeptime), and the stage still steps discretely on its TTL and must settle within the fixed period (which it must today regardless). This is fully supported on the 6733 and captures essentially all of the Section-4 overhead gain.

**(b) Counter-emulated retriggering — the documented pre-X-Series workaround.** Use an onboard counter to emit a finite pulse train (N pulses) on each external start trigger, and use that as the AO sample clock. Caveat: the 6733 has only **2 counters**, which in the current design are likely already consumed by the camera-trigger and stage-trigger tasks. Freeing a counter would mean re-architecting the trigger topology (e.g. making the camera's exposure/timing output the master trigger). More invasive than (a).

**Bottom line:** you do *not* need to replace the 6733 to get the ~2× — continuous regeneration achieves it on the existing board. Native retriggering (variable inter-plane timing, simpler firmware, cleaner code) would be a reason to consider an X-Series board (PCIe/PXIe-63xx) later, but it is not required for the step-and-shoot speedup.

## 5b. Implementation sketch: continuous regeneration on the 6733

This is grounded in the actual task layout in `mesoSPIM_WaveFormGenerator.create_tasks()`. On the single-card 6733 benchtop path (`self.ao_cards == 1`) there are four DAQ tasks:

- `master_trigger_task` — a DO line pulsed once in `run_tasks()` (`write([False,True,…,False], auto_start=True)`); this is the common start trigger for everything else.
- `galvo_etl_laser_task` — one bundled AO task (galvo L/R + ETL L/R + all lasers), `sample_mode=FINITE`, `samps_per_chan=samples`, armed on a digital-edge start trigger from the master line. (Bundled because a multifunction DAQ runs only one hardware-timed AO task at a time.)
- `camera_trigger_task` — a counter (CO) emitting **one** pulse per master trigger, start-triggered off the master line.
- `stage_trigger_task` — a second counter (CO) emitting one stage-step TTL per master trigger (ASI TTL stepping).

That already consumes both of the 6733's counters — which is exactly why counter-emulated retriggering (§5b option b) is not viable here, and why continuous regeneration is the right path.

### The idea

Today the whole quartet is started, master-triggered, waited-on, and stopped **once per plane** (`snap_image_in_series` → `start_tasks`/`run_tasks`/`stop_tasks`). Instead, configure everything **once per stack** so the hardware repeats the per-plane pattern N times on its own:

- **AO** runs in `CONTINUOUS` sample mode with regeneration allowed. The single-sweep buffer (`samples` long) is written once and auto-repeats every `sweeptime` — one galvo/ETL/laser sweep per plane, forever, until stopped. Because it regenerates from the on-board buffer there is no host streaming and therefore no underflow risk.
- **Camera trigger** becomes a **finite pulse train** of exactly `N` pulses at `freq = 1/sweeptime` (`cfg_implicit_timing(FINITE, samps_per_chan=N)`), start-triggered off the master line. It emits one camera trigger per plane and then stops — giving a clean "stack complete" event via `wait_until_done()`.
- **Stage trigger** becomes a finite pulse train of `N-1` pulses at the same rate (no step after the last plane), phase-offset by `stage_trigger_delay_%` so the TTL fires in the readout window and the stage gets the rest of the period to settle.
- **One master pulse** launches all three synchronously; on a single 6733 they share the on-board timebase, so they stay phase-locked for the whole stack.

Per stack the DAQ interaction collapses from `N × (start + master-trigger + wait + stop)` to `1 × (start + master-trigger + wait + stop)`. That is the entire Section-4 overhead gain.

### Code changes

**`mesoSPIM_WaveFormGenerator.py`** — add a continuous variant (guard behind a flag so existing setups are untouched):

- `create_tasks(continuous=False, n_planes=None)`:
  - AO: `cfg_samp_clk_timing(rate=samplerate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=samples)`. Regeneration is the DAQmx default (`out_stream.regen_mode = RegenerationMode.ALLOW_REGENERATION`); set it explicitly for clarity.
  - `camera_trigger_task`: switch from `add_co_pulse_chan_time(single pulse)` to `add_co_pulse_chan_freq(line, freq=1/sweeptime, duty_cycle=camera_pulse_%)` + `timing.cfg_implicit_timing(sample_mode=AcquisitionType.FINITE, samps_per_chan=n_planes)`, keep the master start trigger.
  - `stage_trigger_task`: same pattern, `samps_per_chan=n_planes-1`, `initial_delay` from `stage_trigger_delay_%`.
- `run_tasks(continuous=False)`: for the continuous case, fire the master pulse **once** and return immediately (do **not** `wait_until_done` for the whole stack on the Core thread — let the Core drain frames and pump the GUI). Provide a `wait_for_stack_done()` that waits on `camera_trigger_task` if a blocking finish is wanted.
- `stop_tasks` / `close_tasks`: unchanged, but now called once per stack.

**`mesoSPIM_Core.py`** — the loop change is small because TTL stepping already removed the per-plane serial move:

- `prepare_acquisition` / `prepare_image_series`: call `create_tasks(continuous=True, n_planes=steps)` + `write_waveforms_to_tasks()` + `start_tasks()` once, then fire the single master trigger to launch.
- `run_acquisition`: replace the per-plane `snap_image_in_series()` (which does `start/run/stop`) with a **frame-drain loop** — the camera is free-running in external-trigger mode and produces exactly one frame per camera-trigger pulse, so the loop just emits `sig_add_images_to_image_series` to drain `getFrames`, updates progress, and calls `processEvents`. No per-plane waveform calls, no per-plane `move_relative` (TTL handles it).
- `close_acquisition` / `close_image_series`: `stop_tasks`/`close_tasks` once.
- Abort: `stopflag` now just stops the free-running tasks (simpler than the finite case).

### Config changes

The fast ASI configs already carry every timing parameter needed (`sweeptime`, `camera_delay_%`, `camera_pulse_%`, `stage_trigger_delay_%`, `stage_trigger_pulse_%`, `ttl_motion_enabled: True`). New/changed keys:

- A mode selector, e.g. `acquisition_hardware['waveform_mode'] = 'continuous'` (default `'stepped'` so existing configs behave exactly as now).
- Continuous mode should **assert** `ttl_motion_enabled: True` and an ASI/mixed stage — hardware stepping is mandatory (no per-plane serial moves in a free-running stack).
- Camera must stay in external-trigger light-sheet mode (already `trigger_source: external`).
- Verify `number_image_buffers` (in `hamamatsu_camera`) is generous enough to absorb bursts if the writer momentarily lags.
- Likely re-tune `stage_trigger_delay_%` so the step lands right after readout, maximizing settle time within the period.

### The one real risk

Today's ~90 ms of per-plane software overhead inadvertently gives the ASI stage extra time to settle between planes. Removing it means the stage only has the idle portion of one `sweeptime` (period − active readout/exposure) to step and settle. For small z-steps a TigerASI typically settles in a few ms, so a 73 ms sweep with ~10 ms exposure (~60 ms idle) has ample margin; the tight `wf37` case (~30 ms idle) is the one to validate on the bench. If settle becomes limiting, nudging `sweeptime` up slightly is still far cheaper than the current +90 ms. Also note continuous mode fixes the waveform for the whole stack, so per-plane changes to exposure/laser/intensity aren't possible mid-stack — which matches how mesoSPIM already runs one acquisition (single laser/zoom/exposure per stack). Pair it with `laser_blanking: 'stack'` so the laser is enabled once per stack rather than per plane.

## 6. Suggested first experiments

1. Instrument the per-plane loop: log time spent in `run_tasks` (`wait_until_done`) vs. `move_relative` vs. `processEvents`/queue handling for one stack. This tells you what fraction of each plane is exposure vs. overhead — and therefore your achievable ceiling.
2. Prototype continuous-scan + hardware-triggered acquisition on the ASI/TTL path for one config and compare volume rate against the same stack in stop-and-go.
3. Benchmark `OmeZarrWriterMP` vs. `Tiff_Writer` on your real storage at the target frame rate to confirm the writer isn't the new bottleneck.
4. Prototype **continuous-regeneration** AO on the PXI-6733: program the sweep waveform once in continuous mode with regeneration, embed the camera and stage-step TTLs in the clocked sequence, start once, and stream a fixed number of planes. Compare the resulting volume rate against the current stop/start-per-plane path on the same config — this is the concrete way to realize the Section-4 overhead gain without an X-Series board or continuous scanning.
