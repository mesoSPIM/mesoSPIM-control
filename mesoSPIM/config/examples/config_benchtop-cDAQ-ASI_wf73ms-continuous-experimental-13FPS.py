'''
Testing cDAQ configuration: 2x NI-9401 (digital) cards and 1x NI-9264 (analog) card.

FAST-MODE / CONTINUOUS-REGENERATION TEST CONFIG.
Derived from:
- config_benchtop-cDAQ-ASI.py (this rig's cDAQ hardware wiring, stage, laser, shutter,
  filterwheel, zoom, camera model, ETL calibration file -- all kept intact).
- config_BT_ZMB_exp10ms-wf73ms-6FPS-experimental.py (the 73 ms waveform / 10 ms exposure
  "fast mode" timing tuning: sweeptime, ETL/laser/camera ramp & delay percentages, exposure
  time, scan_line_delay, display subsampling).

Changes vs. plain-merging the two source files:
- 'samplerate' is kept at 25000 (NOT the example's 100000): cDAQ cards are limited to
  25 kS/s (see docstring below / NI-9264 spec), so samples-per-sweep = 25000*0.073 ~= 1825
  instead of 7300. Waveform shape (ramp/delay percentages) is unaffected by this.
- Galvo frequency/amplitude/offset/phase/duty values are this rig's own optical-alignment
  values from config_benchtop-cDAQ-ASI.py, NOT the NI-PXI example's (those are a different,
  unrelated physical instrument's alignment).
- acquisition_hardware['waveform_mode'] = 'continuous' to exercise the experimental
  continuous-regeneration acquisition path added in commit 37b4b95 (see
  PERFORMANCE_ANALYSIS.md sec 5b) instead of the default per-plane 'stepped' path.

cDAQ + continuous-mode compatibility check (done against commit 37b4b95):
- RegenerationMode.ALLOW_REGENERATION is a generic DAQmx AO stream property (not restricted
  to X-Series, unlike native retriggering which IS X-Series-only per PERFORMANCE_ANALYSIS.md
  sec 5) so it is expected to work on the NI-9264. Because the NI-9264's onboard FIFO
  (~128 samples for the bundled 8-channel task) is far smaller than this sweep's ~1825
  samples, regeneration will be PC-buffered (streamed repeatedly from the host over
  USB/Ethernet) rather than a pure onboard loop -- a supported but different code path.
- The original commit's create_tasks_continuous() did NOT call
  `.control(TaskMode.TASK_RESERVE)` on any task, unlike the stepped create_tasks(), where
  it is explicitly marked a "cDAQ requirement" (CompactDAQ chassis arbitrate concurrent
  hardware-timed tasks). This was a real gap for cDAQ and has been patched in
  mesoSPIM_WaveFormGenerator.py (create_tasks_continuous now reserves every task exactly
  like create_tasks does) so this config has a realistic chance of working on the bench.
- Not yet bench-validated: this is the first config meant to actually exercise continuous
  mode on the cDAQ-ASI rig. 'average_frame_rate' below is carried over from the NI-PXI
  example as a rough target, not a measurement on this hardware.

Falls back to 'stepped' automatically if asi_parameters['ttl_motion_enabled'] is not True
(see mesoSPIM_Core.py) -- it is True below, so continuous mode will actually engage.
'''

import numpy as np

logging_level = 'DEBUG'

'''
Options to control behavior of plugins
"paths_list": Optional: Enables arbirtary locations for mesoSPIM to find plugins
"first_image_writer": Optional: Enables a favorite plugin to be at the top of the filenaming wizard. Builtin plugins
are listed as options, by any ImageWriter plugin can be
'''
plugins = {
    'path_list': [
        "../src/plugins",         # Ignored if it does not exits (use '/')
        "C:/a/different/plugin/location",  # Ignored if it does not exits (use '/')
    ],
    'first_image_writer': 'MP_OME_Zarr_Writer', # 'H5_BDV_Writer', 'OME_Zarr_Writer', 'MP_OME_Zarr_Writer', 'Tiff_Writer', 'Big_Tiff_Writer', 'RAW_Writer'
}

ui_options = {'dark_mode' : True, # Dark mode: Renders the UI dark if enabled
              'enable_x_buttons' : True, # Here, specific sets of UI buttons can be disabled
              'enable_y_buttons' : True,
              'enable_z_buttons' : True,
              'enable_f_buttons' : True,
              'enable_rotation_buttons' : True,
              'enable_loading_buttons' : True,
              'flip_XYZFT_button_polarity': (True, True, False, False, False), # flip the polarity of the stage buttons (X, Y, Z, F, Theta)
              'button_sleep_ms_xyzft' : (0, 0, 0, 0, 0), # step-motion buttons disabled for N ms after click. Prevents stage overshooting outside of safe limits, for slow stages.
              'usb_webcam_ID': 0, # open USB web-camera (if available): 0 (first cam), 1 (second cam), ...
              'flip_auto_LR_illumination': False, # flip the polarity of the "Auto L/R illumination" button in Acquisition Manager
               }

'''
Waveform output for Galvos, ETLs etc.
'''

waveformgeneration = 'cDAQ' # 'DemoWaveFormGeneration' or 'NI' or 'cDAQ'

'''
compactDAQ limitations:
https://www.ni.com/en/support/documentation/supplemental/18/number-of-concurrent-tasks-on-a-compactdaq-chassis-gen-ii.html

Tasks:
- DO: master_trigger_task,
- CO: camera_trigger_task, stage_trigger_task (if ASI stages used)
- AO: galvo_etl_laser_task, ao lines: 2 + 2 + 4 = 8, each 16 bit (2 bytes), so 16 bytes/sample point, 128 samples per buffer max (2048 bytes)
        if 1 laser task is used: 2 + 2 + 1 = 5, each 2 bytes, 10 bytes/sample point, 204 samples per buffer max (2048 bytes). Sampling rate 1kHZ max for waveform of 200 ms.


Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

Physical connections:
DIGITAL OUTPUTS (P0.0-P0.3, NI-9401 card in slot 1, 'cDAQ1Mod1'):
- 'master_trigger_out_line' (aka 'cDAQ1Mod1/port0/line0', P0.0/PFI0, Pin14) must be physically connected to P0.4/PFI4 terminal (pin20) of the same card cDAQ1Mod1.
- 'camera_trigger_out_line' to '/cDAQ1Mod1/ctr0' (Pin19 of cDAQ1Mod1 card)
- 'stage_trigger_out_line' to '/cDAQ1Mod1/ctr2' (Pin16 of cDAQ1Mod1 card)

DIGITAL INPUTS (P0.4, NI-9401 card in slot 1, 'cDAQ1Mod1'):
- '/cDAQ1Mod1/PFI4' (aka P0.4/PFI4, pin20, see above) of the same card cDAQ1Mod1. Triggers camera, stage, galvo/ETL tasks.
Note: This also makes four pins P0.4-0.7 configured for input-only.

ANALOG OUTPUTS (NI-9264 card in slot 3, 'cDAQ1Mod3'):
- galvos, ETL controllers to 'cDAQ1Mod3/ao0:3' terminals. Pins 1-4, ground pins on the opposite side.
- laser analog modulation cables to 'cDAQ1Mod3/ao4:7' terminals. Pins 5-8, ground pins on the opposite side.

NI-9401 (digital) card peculiarity:
Input/output mode can be assigned only to digital pins P0.0-P0.3, P0.4-P0.7, or both, so assignment must be grouped by 4 channels (called a nibble).

Connecting BNC cables to the ground:
Signal pin - Ground pin, label:

'cDAQ1Mod1', NI-9401 (digital) card in slot 1:
<< hardware timed tasks, needs them reserved >>
Pin14-Pin1, 'master_trigger_out_line'
Pin19-Pin6, 'camera_trigger_out_line', must be counter-out type of pin
Pin16-Pin3, 'stage_trigger_out_line', must be counter-out type of pin
Pin20-Pin7, '/cDAQ1Mod1/PFI4' ('camera_trigger_source', 'galvo_etl_task_trigger_source', 'laser_task_trigger_source', and 'stage_trigger_source'). Could this be done via internal wiring instead?

'cDAQ1Mod2', NI-9401 (digital) card in slot 2:
<< software timed tasks, needs NO task reservation >>
Pin14-Pin3, 'cDAQ1Mod2/port0/line0', 'shutter_right', arm switching
Pin16-Pin3, 'cDAQ1Mod2/port0/line1', laser enable line for 405 nm
Pin17-Pin4, 'cDAQ1Mod2/port0/line2', laser enable line for 488 nm
Pin19-Pin6, 'cDAQ1Mod2/port0/line3', laser enable line for 561 nm
Pin20-Pin7, 'cDAQ1Mod2/port0/line4', laser enable line for 638 nm

'cDAQ1Mod3', NI-9264 (analog, DSUB-connector version) card in slot 3:
<< hardware timed tasks, needs them reserved >>
Pin1-Pin20, 'cDAQ1Mod3/ao0', galvo L
Pin2-Pin21, 'cDAQ1Mod3/ao1', galvo R
Pin3-Pin22, 'cDAQ1Mod3/ao2', ETL L
Pin4-Pin23, 'cDAQ1Mod3/ao3', ETL R
Pin5-Pin24, 'cDAQ1Mod3/ao4', laser 405 nm
Pin6-Pin25, 'cDAQ1Mod3/ao5', laser 488 nm
Pin7-Pin26, 'cDAQ1Mod3/ao6', laser 561 nm
Pin8-Pin27, 'cDAQ1Mod3/ao7', laser 638 nm
'''

acquisition_hardware = {'master_trigger_out_line' : 'cDAQ1Mod1/port0/line0',
                        'camera_trigger_source' : '/cDAQ1Mod1/PFI4',
                        'camera_trigger_out_line' : '/cDAQ1Mod1/ctr0', # must be COUNTER-OUT (CO) type of pin.
                        'galvo_etl_task_line' : 'cDAQ1Mod3/ao0:3',
                        'galvo_etl_task_trigger_source' : '/cDAQ1Mod1/PFI4',
                        'laser_task_line' :  'cDAQ1Mod3/ao4:7',
                        'laser_task_trigger_source' : '/cDAQ1Mod1/PFI4',
                        # EXPERIMENTAL: 'stepped' (default) = arm/trigger/stop DAQ tasks per plane.
                        # 'continuous' = single-launch continuous-regeneration for the whole stack
                        # (removes ~50-100 ms/plane overhead; see PERFORMANCE_ANALYSIS.md sec 5b).
                        # Requires ASI TTL stepping (asi_parameters['ttl_motion_enabled'] = True).
                        # See the module docstring above for the cDAQ-specific compatibility notes
                        # and the TASK_RESERVE fix applied to create_tasks_continuous().
                        'waveform_mode' : 'continuous', # 'stepped' or 'continuous'
                        }

'''
Human interface device (Joystick)
'''
sidepanel = 'Demo' #'Demo' or 'FarmSimulator'

laser = 'cDAQ' # 'Demo' or 'NI', or 'cDAQ'

''' Laser blanking indicates whether the laser enable lines should be set to LOW between individual
'images' or 'stacks'. This is helpful to avoid laser bleedthrough between images caused by insufficient
modulation depth of the analog input (even at 0V, some laser light is still emitted).

Set to 'stack' here (rather than the usual 'images' default): continuous mode fixes the waveform
for the whole stack and enables the laser once for the whole stack regardless of this setting
(see mesoSPIM_Core._run_acquisition_continuous), so 'stack' keeps this config's declared intent
consistent with what continuous mode actually does. Per-plane blanking is not meaningful in
continuous mode since there is no per-plane task start/stop.
'''
laser_blanking = 'stack' # 'images' by default, unless laser enable is connected to a slow mechanical shutter

''' The laserdict keys are the laser designation that will be shown in the user interface.
Values are DO ports used for laser ENABLE digital signal.
Critical: keys must be sorted by increasing wavelength order: 405, 488, 561, etc.
'''
laserdict = {'405 nm': 'cDAQ1Mod2/port0/line1',
             '488 nm': 'cDAQ1Mod2/port0/line2',
             '561 nm': 'cDAQ1Mod2/port0/line3',
             '638 nm': 'cDAQ1Mod2/port0/line4',
             }

'''
Shutter configuration
'''

shutter = 'cDAQ' # 'Demo' or 'NI' or 'cDAQ'
shutterdict = {'shutter_left' : None, # empty terminal, general shutter, optional
              'shutter_right' : 'cDAQ1Mod2/port0/line0', # arm switching
              }

''' A bit of a hack: Shutteroptions for the GUI '''
shutteroptions = ('Left','Right')

''' A bit of a hack: Assumes that the shutter_left line is the general shutter
and the shutter_right line is the left/right switch (Right==True)'''

shutterswitch = False # If True, shutter_left line is the general shutter

'''
Camera configuration:
=======================================================================================================
camera = 'Photometrics' # Photometrics Iris 15
camera_parameters = {'x_pixels' : 5056,
                     'y_pixels' : 2960,
                     'x_pixel_size_in_microns' : 4.25,
                     'y_pixel_size_in_microns' : 4.25,
                     'subsampling' : [1,2,4],
                     'speed_table_index': 0,
                     'exp_mode' : 'Edge Trigger', # Lots of options in PyVCAM --> see constants.py
                     'readout_port': 0,
                     'gain_index': 1,
                     'exp_out_mode': 4, # 4: line out
                     'binning' : '1x1',
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 0, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 6, # 10.26 us x factor, a factor = 6 equals 71.82 us
                    }
=======================================================================================================
camera = 'DemoCamera'
camera_parameters = {'x_pixels' : 1024,
                     'y_pixels' : 1024,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4]}
'''

camera = 'Photometrics' # 'DemoCamera' or 'HamamatsuOrca' or 'Photometrics'

camera_parameters = {'x_pixels' : 5056,
                     'y_pixels' : 2960,
                     'x_pixel_size_in_microns' : 4.25,
                     'y_pixel_size_in_microns' : 4.25,
                     'subsampling' : [1,2,4],
                     'speed_table_index': 0,
                     'exp_mode' : 'Edge Trigger', # Lots of options in PyVCAM --> see constants.py
                     'readout_port': 0,
                     'gain_index': 1,
                     'exp_out_mode': 4, # 4: line out
                     'binning' : '1x1',
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 0, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 1, # 10.26 us x factor, a factor = 1 equals 10.26 us. Fast-mode value (from the wf73ms example), needed so 5056x2960 readout fits inside a 73 ms sweep.
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

'''
Stage configuration
'''

'''
The stage_parameter dictionary defines the general stage configuration, initial positions,
and safety limits. The rotation position defines a XYZ position (in absolute coordinates)
where sample rotation is safe. Additional hardware dictionaries (e.g. pi_parameters)
define the stage configuration details.

ASI stages supported: 'stage_type' : 'TigerASI', 'MS2000ASI'
PI stage support: 'stage_type' : 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Mixed stage types: 'stage_type' : 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz', 'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy',
'''

stage_parameters = {'stage_type' : 'TigerASI', # 'DemoStage', 'PI', 'TigerASI' or other configs, see above.
                    'y_load_position': -45000,
                    'y_unload_position': -75000,
                    'x_max' : 51000,
                    'x_min' : -46000,
                    'y_max' : 160000,
                    'y_min' : -160000,
                    'z_max' : 99000,
                    'z_min' : -99000,
                    'f_max' : 99000,
                    'f_min' : -8500,
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }

'''
For a benchtop mesoSPIM with an ASI Tiger controller, the following parameters are necessary.
The stage assignment dictionary assigns a mesoSPIM stage (xyzf and theta - dict key) to an ASI stage (XYZ etc)
which are the values of the dict.
'''
asi_parameters = {'COMport' : 'COM23',
                  'baudrate' : 115200,
                  'stage_assignment': {'y':'V', 'z':'Z', 'theta':'T', 'x':'X', 'f':'Y'},
                  'encoder_conversion': {'V': 10., 'Z': 10., 'T': 1000., 'X': 10., 'Y': 10.}, # num of encoder counts per um or degree, depending on stage type.
                  'speed': {'V': 3., 'Z': 3., 'T': 30., 'X': 3., 'Y': 3.}, # mm/s or deg/s.
                  'stage_trigger_source': '/cDAQ1Mod1/PFI4',
                  'stage_trigger_out_line': '/cDAQ1Mod1/ctr2', # must be COUNTER-OUT (CO) type of pin and sit on the same card as 'master_trigger_out_line' and 'camera_trigger_out_line' lines.
                  'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
                  'stage_trigger_pulse_%' : 1,
                  'ttl_motion_enabled': True, # required for 'waveform_mode': 'continuous' above -- do not set False in this config.
                  'ttl_cards':(2,3),
                  }

'''
Filterwheel configuration
For a DemoFilterWheel, no COMport needs to be specified.
For a Ludl Filterwheel, a valid COMport is necessary. Ludl marking 10 = position 0.
For a Dynamixel FilterWheel, valid baudrate and servoi_id are necessary.
'''
filterwheel_parameters = {'filterwheel_type' : 'ZWO', # 'Demo', 'Ludl', 'Dynamixel', 'ZWO'
                          'COMport' : 'COM31', # irrelevant for 'ZWO'
                          'baudrate' : 115200, # relevant only for 'Dynamixel'
                          'servo_id' :  1, # relevant only for 'Dynamixel'
                          }

'''
filterdict contains filter labels and their positions. The valid positions are:
For Ludl: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For Dynamixel: servo encoder counts (360 deg = 4096 counts, or 11.377 counts/deg), e.g. 0 for 0 deg, 819 for 72 deg.
Dynamixel encoder range in multi-turn mode: -28672 .. +28672 counts.
For ZWO EFW Mini 5-slot wheel: positions 0, 1, .. 4.
'''

filterdict = {'Empty' : 0, # Every config should contain this
              '405-488-561-640-Quadrupleblock' : 1,
              '535/22 Brightline': 2,
              '595/31 Brightline': 3,
              }


'''
Zoom configuration
For the 'Demo', 'servo_id', 'COMport' and 'baudrate' do not matter.
For a 'Dynamixel' servo-driven zoom, 'servo_id', 'COMport' and 'baudrate' (default 1000000) must be specified
For 'Mitu' (Mitutoyo revolver), 'COMport' and 'baudrate' (default 9600) must be specified
'''
zoom_parameters = {'zoom_type' : 'Demo', # # 'Demo', 'Dynamixel', or 'Mitu'
                   'servo_id' :  1, # only for 'Dynamixel'
                   'COMport' : 'COM9',
                   'baudrate' : 115200} # 57142

'''
The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface.
There should be always '1x' zoom present, for correct initialization of the software.
'''

zoomdict = {
            '2x' : 4,
            '5x' : 6,
            '7.5x' : 7,
            '10x' : 8,
            '20x' : 9,
            '25x' : 10
            }
'''
Pixelsize in micron
'''
pixelsize = {
            '2x' : 4.25/2,
            '5x' : 4.25/5,
            '7.5x' : 4.25/7.5,
            '10x' : 4.25/10,
            '20x' : 4.25/20,
            '25x' : 4.25/25,
            }

'''
H5_BDV_Writer plugin parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
H5_BDV_Writer = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy': False, # in case X and Y axes need to be swapped for the correct tile positions
        }

'''
OME.ZARR parameters
This write generates ome.zarr specification multiscale data on the fly during acquisition.
The default parameter should work pretty well for most setups with little to no performance degradation
during acquisition. Defaults include compression which will save disk space and can also improve
performance because less data is written to disk. Data are written into shards which limits the number of
files generated on disk.

Chunks can be set to adjust with each multiscale. Base and target chunks are defined and will start
with the base shape and automatically shift towards target with each scale. Chunks have a big influence on IO.
Bigger chunks means less and more efficient IO, very small chunks will degrade performance on some hardware.
Test on your hardware.

ome_version: default: "0.5". Selects whether to write ome-zarr v0.5 (zarr v3 and support for sharding) or
v0.4 (zarr v2 and NO support for sharding). If "0.4" is selected, the 'shards' option is ignored.

compression: default: zstd-5. This is a good trade off of compute and compression. In our tests, there is
little to no performance degradation when using this setting.

generate_multiscales: default: True. True will generate ome-zarr specification multiscale during acquisition.
False will only save the original resolution data.

shards are defined by default. Be careful, shard shape must be defined carefully to prevent performance
degradation. We suggest that shards are shallow in Z and as large as you camera sensor in XY.
For best performance set the base and target chunks to the same z-depth as your shards.

async_finalize: default: True. Enables acquisition of the next tile to proceed immediately while the multiscale
is finalized in the background. On systems with slow IO, data can accumulate in RAM and cause a crash.
Slow IO can be improved by using bigger chunks. If bigger chunks do not help, use async_finalize: False
to make mesoSPSIM pause after each tile acquisition until the multiscale is finished generating.

    IMPORTANT: async_finalize applies to OME_Zarr_Writer (in-process) ONLY. The multiprocess
    MP_OME_Zarr_Writer always closes synchronously and ignores this setting (it logs a warning
    if you set it). It is also NOT a throughput knob for either writer: the pause between tiles
    is the level-0 frame backlog draining to disk, which happens upstream of finalize. To
    shorten that gap, look at compression / write_cache / ring_buffer_size instead.
'''
OME_Zarr_Writer = {
    'ome_version': '0.5', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': False, #True, False. False: only the primary data is saved. True: multiscale data is generated. 
    'compression': 'zstd', # None, 'zstd', 'lz4'
    'compression_level': 5, # 1-9
    # Tuned for the 5056x2960 Iris 15 sensor -- see the note above MP_OME_Zarr_Writer.
    # Only shards[0] is a real knob: 64 -> 16 files/stack of ~1.8 GB, 256 -> 4 of ~7.1 GB.
    'shards': (64,6000,6000), # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (32,296,316), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (64,64,64), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': True, # True, False

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True, # True, False
    'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False, # in case X and Y axes need to be swapped for the correct BigStitcher tile positions
    }

MP_OME_Zarr_Writer = {
    'ome_version': '0.5',  # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': False, # True, False. False: only the primary data is saved. True: multiscale data is generated. 
    'compression': None,  # None, 'zstd', 'lz4'
    'compression_level': 5,  # 1-9
    # Chunk/shard geometry for the 5056x2960 Iris 15 sensor at 1x1 binning.
    #
    # IMPORTANT: the SAVED array is (z, 5056, 2960), i.e. y and x are SWAPPED relative to
    # the camera frame -- the writer rotates every plane by 90 deg (OmeZarrWriterMP.open:
    # Z_EST, Y, X = req.shape[0], req.shape[2], req.shape[1]). base_chunks is (z, y, x) in
    # SAVED axes, so the divisors must be taken against 5056 (y) and 2960 (x), not the
    # other way round. Getting this backwards is silent and very expensive -- see below.
    #
    # pick_shards_for_level() snaps the shard DOWN to a whole multiple of the chunk on
    # each axis: k = min(desired, extent) // chunk; shard = k * chunk. So:
    #   (64, 316, 296): 5056/316 = 16, 2960/296 = 10  -> shard (64, 5056, 2960) = FULL plane,
    #                   one shard file per 64-z slab, 16 files/stack.  <-- correct
    #   (32, 296, 316): 5056//296 = 17 -> 5032 (24 px short), 2960//316 = 9 -> 2844 (116 px
    #                   short) -> shard (64, 5032, 2844) misses the plane edges, so every
    #                   z-slab is stored as a 2x2 XY tiling with sliver files
    #                   (646 MB + 54 MB + 6 MB + 0.3 MB).  <-- what we had, do not use
    #
    # base_chunks[0] MUST equal shards[0]. If the chunk is shallower than the shard (e.g.
    # 32 vs 64) each flush writes only part of a shard, forcing zarr to read-modify-write
    # the whole ~650 MB shard on the next flush. Matching them makes writes pure sequential
    # appends. The cost is a chunk_z x full_plane pre-flush buffer in the child: 1.78 GB at
    # z=64 (x2 for two channels), which is nothing on a 128 GB machine.
    #
    # NB: recompute these divisors if binning or ROI changes.
    # Only shards[0] is a real knob: 64 -> 16 files/stack of ~1.8 GB, 256 -> 4 of ~7.1 GB.
    'shards': (64, 6000, 6000),  # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (32, 316, 296),
    # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (64, 64, 64),
    # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': True,  # IGNORED by the multiprocess writer -- it always closes synchronously.

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True,  # True, False
    'flip_xyz': (True, True, False),  # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False,  # in case X and Y axes need to be swapped for the correct BigStitcher tile positions

    # Multiprocess options
    'ring_buffer_size': 512,  # Max number of images in shared memory ring buffer, 16 for simulation mode (eg laptop), 512 for production mode (fast workstation)

    # Write cache options. Write tile data to cache then move to acquisition folder
    # None acquires data direct to acquisition folder.
    'write_cache': None # None, 'e:/path/to/fast/ssd/write/cache'
}

'''
Rescale the galvo amplitude when zoom is changed
For example, if 'galvo_l_amplitude' = 1 V at zoom '1x', it will ve 2 V at zoom '0.5x'
'''
scale_galvo_amp_with_zoom = True

'''
Initial acquisition parameters

Used as initial values after startup

When setting up a new mesoSPIM, make sure that:
* 'max_laser_voltage' is correct (5 V for Toptica MLEs, 10 V for Omicron SOLE)
* 'galvo_l_amplitude' and 'galvo_r_amplitude' (in V) are correct (not above the max input allowed by your galvos)
* all the filepaths exist
* the initial filter exists in the filter dictionary above

FAST-MODE TIMING NOTE: 'sweeptime' and the ETL/laser/camera delay & ramp percentages below are
adopted from config_BT_ZMB_exp10ms-wf73ms-6FPS-experimental.py (the 73 ms / 10 ms-exposure fast
mode). 'samplerate' stays at this rig's cDAQ maximum (25 kS/s) rather than that example's 100 kS/s
NI-PXI rate. Galvo frequency/amplitude/offset/duty/phase keep this rig's own optical-alignment
values from config_benchtop-cDAQ-ASI.py.
'''

startup = {
'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
'samplerate' : 25000, # limited to 25kS/s for cDAQ cards (see docstring above) -- NOT the 100000 used by the NI-PXI wf73ms example
'sweeptime' : 0.073, # fast-mode 73 ms waveform, from config_BT_ZMB_exp10ms-wf73ms-6FPS-experimental.py
'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters-BT-DBE.csv', # kept: this rig's own ETL calibration
'filepath' : 'F:/Test/file.tif',
'folder' : 'F:/Test/',
'snap_folder' : 'F:/Test/',
'file_prefix' : '',
'file_suffix' : '000001',
'zoom' : '5x',
'pixelsize' : pixelsize['5x'],
'laser' : '488 nm',
'max_laser_voltage': 5.0,
'intensity' : 10,
'shutterstate':False, # Is the shutter open or not?
'shutterconfig':'Left', # Can be "Left", "Right","Both","Interleaved"
'laser_interleaving':False,
'filter' : 'Empty',
'etl_l_delay_%' : 0, # fast-mode ramp shape (was 5.0 at 267ms sweeptime)
'etl_l_ramp_rising_%' : 95, # 94,
'etl_l_ramp_falling_%' : 5, #2,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.3,
'etl_r_delay_%' : 0, # fast-mode ramp shape (was 2.5 at 267ms sweeptime)
'etl_r_ramp_rising_%' : 5, #0,
'etl_r_ramp_falling_%' : 95,
'etl_r_amplitude' : 0.65,
'etl_r_offset' : 2.36,
'galvo_l_frequency' : 99.9, # this rig's own alignment value (config_benchtop-cDAQ-ASI.py), not the NI-PXI example's
'galvo_l_amplitude' : 0.8, #0.8V at 5x
'galvo_l_offset' : -0.17999999999999994,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : 0.45,
'galvo_r_frequency' : 99.9, # this rig's own alignment value (config_benchtop-cDAQ-ASI.py), not the NI-PXI example's
'galvo_r_amplitude' : 0.8, #0.8V at 5x
'galvo_r_offset' : 0.06,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : 0.45,
'laser_l_delay_%' : 5, # fast-mode duty cycle (was 10 at 267ms sweeptime)
'laser_l_pulse_%' : 95, # fast-mode duty cycle (was 87.0 at 267ms sweeptime)
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 5,
'laser_r_pulse_%' : 95,
'laser_r_max_amplitude_%' : 100,
'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
'stage_trigger_pulse_%' : 1,
'camera_delay_%' : 5, # fast-mode timing (was 10 at 267ms sweeptime)
'camera_pulse_%' : 1,
'camera_exposure_time':0.010, # 10 ms, fast-mode value (was 0.02)
'camera_line_interval':0.000075,
'camera_display_live_subsampling': 2,
'camera_display_snap_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 10, # newly added for performance and stability boost
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM',
'average_frame_rate': 11.6, # rough target carried over from the NI-PXI wf73ms example; UNVERIFIED on this cDAQ rig / in continuous mode -- measure and update after bench testing.
}
