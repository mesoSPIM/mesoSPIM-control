"""
mesoSPIM user configuration for bench-testing on the cDAQ-ASI benchtop:
continuous-regeneration DAQ mode at 12 FPS, writing sharded OME-Zarr v0.5 pyramids.

= config_benchtop-cDAQ-ASI_user-shardedZARR-12FPS.py (writer settings) plus:

1. waveform_mode 'continuous': one hardware launch per stack. The camera and stage counters
   count ticks of the AO sample clock (/cDAQ1/ao/SampleClock), so the light sheet cannot drift
   against the rolling shutter -- the cause of the progressive right-edge blur in the July tests.
   Check the log line '[continuous] counters clocked from the AO sample clock ...'; if it says
   'falling back to time-based counter pulses' instead, the fallback is in use.

2. sweeptime 0.08332 s = 2083 samples at 25 kS/s = 83.32 ms per plane = 12.002 FPS.

3. Fast-mode camera/waveform timing from the 13 FPS continuous config that ran on this rig
   (claude-performance, commit 2d13b0f, tuned at a 73 ms sweep). The percentages are scaled by
   73/83.32 so every ABSOLUTE timing is unchanged -- ETL ramp 69.35 ms, laser pulse 3.65-73 ms,
   camera trigger at 3.65 ms, stage step at 67.5 ms -- and the extra 10.3 ms per plane is idle.
   The stage therefore gets ~19 ms to settle before the next exposure instead of ~9 ms.
   Galvo and ETL calibration stay as in the hardware file.

   Camera frame: 10 ms exposure + 2960 rows x 10.26 us (scan_line_delay 1) = ~40 ms < 83.32 ms.
"""
config_format = 2

include('hardware/config_benchtop-cDAQ-ASI_hw.py')

startup.update({
    'state': 'init',
    'folder': 'F:/Test/',
    'snap_folder': 'F:/Test/',
    'file_prefix': '',
    'file_suffix': '000001',
})

plugins['first_image_writer'] = 'MP_OME_Zarr_Writer'

'''Sharded OME-Zarr v0.5 at 12 FPS (benchmarked 2026-10-01, see the -12FPS user config).'''
MP_OME_Zarr_Writer.update({
    'ome_version': '0.5',
    'generate_multiscales': True,
    'compression': 'zstd',
    'compression_level': 1,
    'shards': (64, 6000, 6000),        # shards[0] MUST equal base_chunks[0]
    'base_chunks': (64, 1264, 1480),
    'target_chunks': (64, 64, 64),
    'ring_buffer_size': 512,
    'write_cache': None,
})

'''Continuous-regeneration DAQ mode. Requires ASI TTL stepping (on in the hardware file).'''
acquisition_hardware['waveform_mode'] = 'continuous'
assert asi_parameters['ttl_motion_enabled'] is True, "continuous mode needs asi_parameters['ttl_motion_enabled'] = True"
laser_blanking = 'stack'  # the laser is enabled once per stack in continuous mode anyway

'''Camera: line-delay readout short enough for an 83 ms sweep.'''
camera_parameters['scan_line_delay'] = 1  # 10.26 us per row (hardware file: 6)
# PVCAM circular buffer for image series: 64 frames = 1.9 GB = 5.3 s of slack at 12 FPS.
# Must stay under 2 GiB (71 frames): a 100-frame (3 GB) buffer made start_live() fail.
# The default 16 (1.3 s) overflowed on 2026-10-01: 108 of 1101 frames were overwritten.
camera_parameters['series_buffer_frames'] = 64

'''Waveform timing: 73 ms-tuned absolute timings inside an 83.32 ms period (percent x 73/83.32).'''
startup.update({
    'samplerate': 25000,            # cDAQ NI-9264 limit
    'sweeptime': 0.08332,           # 2083 samples -> 83.32 ms -> 12.002 FPS (hardware file: 0.267)
    'etl_l_delay_%': 0,
    'etl_l_ramp_rising_%': 83.23,   # 69.35 ms
    'etl_l_ramp_falling_%': 4.38,   # 3.65 ms
    'etl_r_delay_%': 0,
    'etl_r_ramp_rising_%': 4.38,
    'etl_r_ramp_falling_%': 83.23,
    'laser_l_delay_%': 4.38,        # laser on 3.65 ms ...
    'laser_l_pulse_%': 83.23,       # ... to 73 ms
    'laser_r_delay_%': 4.38,
    'laser_r_pulse_%': 83.23,
    'camera_delay_%': 4.38,         # camera trigger at 3.65 ms
    'camera_pulse_%': 1,
    'stage_trigger_delay_%': 81.04, # stage step at 67.5 ms, ~19 ms settle before the next exposure
    'stage_trigger_pulse_%': 1,
    'camera_exposure_time': 0.010,  # 10 ms (hardware file: 20 ms)
    'camera_display_temporal_subsampling': 10,
    'average_frame_rate': 12.0,
})
asi_parameters['stage_trigger_delay_%'] = startup['stage_trigger_delay_%']  # the counter reads asi_parameters
asi_parameters['stage_trigger_pulse_%'] = startup['stage_trigger_pulse_%']
