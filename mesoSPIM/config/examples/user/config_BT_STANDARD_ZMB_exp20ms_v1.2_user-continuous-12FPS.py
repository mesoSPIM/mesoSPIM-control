"""
config_BT_STANDARD_ZMB_exp20ms_v1.2 (PXI-6733 benchtop) in continuous-regeneration mode at 12 FPS,
writing sharded OME-Zarr v0.5 pyramids.

The microscope itself is described in hardware/config_BT_STANDARD_ZMB_exp20ms_v1.2_hw.py, which is
config_BT_STANDARD_ZMB_exp20ms_v1.2.py verbatim. Everything assigned below the include() line
overrides it.

Derived from config_benchtop-cDAQ-ASI_user-shardedZARR-12FPS-continuos.py, verified on the cDAQ-ASI
benchtop on 2026-10-01 (log 20261001-152708): 2 channels x 1101 planes, 1101/1101 frames per stack,
11.95 FPS camera rate, no errors, the writer done 6 s after the last frame. Both rigs use the same
Photometrics Iris 15 camera and the same fast-mode waveform timing (taken from the PXI example
config_BT_ZMB_exp10ms-wf73ms-6FPS-experimental.py), so the camera and timing settings carry over.
NOT carried over: the cDAQ's 25 kS/s sample rate and its galvo/ETL alignment -- this file keeps the
PXI-6733's 100 kS/s and the hardware file's own calibration.
Not yet tested on the PXI-6733 itself.

What the cDAQ bench runs taught, applied here:

1. waveform_mode 'continuous': one hardware launch per stack. The camera and stage counters count
   ticks of the AO sample clock, so the light sheet cannot drift against the rolling shutter. Look
   for '[continuous] counters clocked from the AO sample clock /PXI1Slot4/ao/SampleClock' in the log;
   'falling back to time-based counter pulses' means the PXI cannot route that clock and the
   drift-checked fallback is in use.

2. sweeptime 0.08333 s = 8333 samples at 100 kS/s = 83.33 ms per plane = 12.0005 FPS.

3. The camera frame must fit in one sweep, or triggers are missed. In Line Delay scan mode a frame
   takes exposure + 2960 rows x scan_line_delay x 10.26 us: the hardware file's 20 ms and factor 6
   give ~202 ms, so this file uses 10 ms and factor 1: ~40 ms.

4. The fast-mode timings were tuned at a 73 ms sweep. The percentages are scaled by 73/83.33 so every
   ABSOLUTE timing is unchanged -- ETL ramp 69.35 ms, laser on 3.65-73 ms, camera trigger at 3.65 ms,
   stage step at 67.5 ms -- and the extra 10.3 ms per plane is idle: the stage gets ~19 ms to settle
   before the next exposure instead of ~9 ms. Re-check the ETL focus on this rig.

5. PVCAM circular buffer: PyVCAM's default 16 frames (1.3 s) overflowed at 12 FPS; 100 frames (3 GB)
   made start_live() fail (over 2 GiB). 64 frames = 1.9 GB = 5.3 s of slack.

6. Keep the image processor chain empty or disabled (config/processor_chain.json). Even the
   pass-through 'Identity' processor cost 53 ms per frame before 4de0180 and dropped frames.

7. Writer: sharded OME-Zarr v0.5 with shards[0] == base_chunks[0]. A shallower chunk lets two
   writer threads fill one shard concurrently and lose half of it. zstd-1 kept up at 12 FPS on the
   cDAQ PC's NVMe (F:); a SATA QLC drive did not (~8.8 FPS sustained). Benchmark this PC's target
   drive before relying on it. With 0.5 the BigStitcher XML now carries zarr.version="ZarrV3" and
   opens in BigStitcher 3.0.8.
"""
config_format = 2

include('hardware/config_BT_STANDARD_ZMB_exp20ms_v1.2_hw.py')

'''Continuous-regeneration DAQ mode. Requires ASI TTL stepping (on in the hardware file).'''
acquisition_hardware['waveform_mode'] = 'continuous'
assert asi_parameters['ttl_motion_enabled'] is True, "continuous mode needs asi_parameters['ttl_motion_enabled'] = True"
laser_blanking = 'stack'  # the laser is enabled once per stack in continuous mode anyway

'''Camera: line-delay readout short enough for an 83 ms sweep.'''
camera_parameters['scan_line_delay'] = 1        # 10.26 us per row (hardware file: 6)
camera_parameters['series_buffer_frames'] = 64  # 1.9 GB, 5.3 s of slack at 12 FPS; must stay under 2 GiB (71 frames)

'''Sharded OME-Zarr v0.5 at 12 FPS.'''
MP_OME_Zarr_Writer.update({
    'ome_version': '0.5',
    'generate_multiscales': True,
    'compression': 'zstd',
    'compression_level': 1,
    'shards': (64, 6000, 6000),        # shards[0] MUST equal base_chunks[0]
    'base_chunks': (64, 1264, 1480),   # divides the saved 5056 x 2960 plane: one shard file per z-slab
    'target_chunks': (64, 64, 64),
    'write_big_stitcher_xml': True,
})

'''Waveform timing: 73 ms-tuned absolute timings inside an 83.33 ms period (percent x 73/83.33).'''
startup.update({
    'samplerate': 100000,           # PXI-6733
    'sweeptime': 0.08333,           # 8333 samples -> 83.33 ms -> 12.0005 FPS (hardware file: 0.26734)
    'etl_l_delay_%': 0,
    'etl_l_ramp_rising_%': 83.22,   # 69.35 ms
    'etl_l_ramp_falling_%': 4.38,   # 3.65 ms
    'etl_r_delay_%': 0,
    'etl_r_ramp_rising_%': 4.38,
    'etl_r_ramp_falling_%': 83.22,
    'laser_l_delay_%': 4.38,        # laser on 3.65 ms ...
    'laser_l_pulse_%': 83.22,       # ... to 73 ms
    'laser_r_delay_%': 4.38,
    'laser_r_pulse_%': 83.22,
    'camera_delay_%': 4.38,         # camera trigger at 3.65 ms
    'camera_pulse_%': 1,
    'stage_trigger_delay_%': 81.03, # stage step at 67.5 ms, ~19 ms settle before the next exposure
    'stage_trigger_pulse_%': 1,
    'camera_exposure_time': 0.010,  # 10 ms (hardware file: 20 ms)
    'camera_display_temporal_subsampling': 10,
    'average_frame_rate': 12.0,
})
asi_parameters['stage_trigger_delay_%'] = startup['stage_trigger_delay_%']  # the counter reads asi_parameters
asi_parameters['stage_trigger_pulse_%'] = startup['stage_trigger_pulse_%']
