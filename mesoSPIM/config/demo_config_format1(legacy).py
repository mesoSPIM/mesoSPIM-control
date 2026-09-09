'''
mesoSPIM configuration file (legacy single-file format, "format 1").

The same demo microscope as config/demo_config.py, which describes it in the two-level
format: a short user file that include()s the shared hardware definitions from
config/hardware/. Both files load into exactly the same settings, so use whichever form
you prefer - format 1 stays fully supported.

This one is flat on purpose: everything the software reads is in this single file, and
nothing in it is shared with the other users of the same microscope.
'''
# ===== from config/hardware/cameras/demo_camera.py =====
'''
Camera configuration: demo camera (no hardware).

For the demo camera, only the following options are necessary
(x_pixels and y_pixels can be chosen arbitrarily):

camera_parameters = {'x_pixels' : 1024,
                     'y_pixels' : 1024,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4]}

For real cameras, see the other files in this folder.
'''
camera = 'Demo' # 'Demo', 'HamamatsuOrca', 'Photometrics' or 'PCO'

camera_parameters = {'x_pixels' : 5056,
                     'y_pixels' : 2960,
                     'x_pixel_size_in_microns' : 5,
                     'y_pixel_size_in_microns' : 5,
                     'subsampling' : [1,2,4],
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

# ===== from config/hardware/DAQ/demo_daq.py =====
'''
Waveform generation / DAQ: demo (no hardware).
'''
waveformgeneration = 'Demo' # 'Demo', 'NI' or 'cDAQ'

acquisition_hardware = {'master_trigger_out_line' : 'PXI6259/port0/line1',
                        'camera_trigger_source' : '/PXI6259/PFI0',
                        'camera_trigger_out_line' : '/PXI6259/ctr0',
                        'galvo_etl_task_line' : 'PXI6259/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI6259/PFI0',
                        'laser_task_line' :  'PXI6733/ao0:3',
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}

# ===== from config/hardware/stages/demo_stage.py =====
'''
Stage configuration: demo stage (no hardware).

The stage_parameters dictionary defines the general stage configuration, initial positions,
and safety limits. The rotation position defines a XYZ position (in absolute coordinates)
where sample rotation is safe. Additional hardware dictionaries (e.g. pi_parameters,
asi_parameters, see the other files in this folder) define the stage configuration details.
All positions are absolute.

'stage_type' options:
ASI stages: 'TigerASI', 'MS2000ASI'
PI stages: 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Legacy mixed stages: 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz',
                     'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy'
New flexible mixed stages: 'Mixed' (requires both asi_parameters and pi_parameters with
                     stage_assignment dicts)
Demo mode: 'Demo'
'''
stage_parameters = {'stage_type' : 'Demo',
                    'y_load_position': -6000,
                    'y_unload_position': 6000,
                    'x_center_position': 0, # x-center position for the sample holder. Make sure the sample holder is actually centered at this position relative to the detection objective and light-sheet.
                    'z_center_position': 0, # z-center position for the sample holder. Make sure the sample holder is actually centered at this position relative to the detection objective and light-sheet.
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 50000,
                    'y_min' : -50000,
                    'z_max' : 25000,
                    'z_min' : -25000,
                    'f_max' : 98000,
                    'f_min' : 0,
                    'f_objective_exchange': 2000, # DANGER ZONE: position for the objective exchange, either manually or by the revolver. Set up carefully to avoid collisions! If missing, the objective revolver will rotate in the current f-position.
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }

# ===== from config/hardware/lasers/demo_lasers.py =====
'''
Lasers and shutters of a demo/simulation machine.

Identical to hardware/lasers/benchtop_PXI6733_lasers.py apart from the two driver flags
('laser' and 'shutter'), so that mesoSPIM runs without an NI card attached. Config files
never include each other in a chain: this file repeats the content instead.
'''
laser = 'Demo' # 'Demo', 'NI', or 'cDAQ'

''' The `laserdict` specifies laser labels of the GUI and their digital modulation channels.
Keys are the laser designation that will be shown in the user interface
Values are DO ports used for laser ENABLE digital signal.
Critical: entries must be sorted in the increasing wavelength order: 405, 488, etc.
'''
laserdict = {'405 nm': 'PXI1Slot4/port0/line2',
             '488 nm': 'PXI1Slot4/port0/line3',
             '561 nm': 'PXI1Slot4/port0/line4',
             '638 nm': 'PXI1Slot4/port0/line5',
             }

''' Laser blanking indicates whether the laser enable lines should be set to LOW between
individual images or stacks. This is helpful to avoid laser bleedthrough between images caused by insufficient
modulation depth of the analog input (even at 0V, some laser light is still emitted).
'''
laser_blanking = 'images' # if 'images', laser is off before and after every image; if 'stacks', before and after each stack.

'''
Shutter configuration
If shutterswitch = True:
    'shutter_left' is the general shutter
    'shutter_right' is the left/right switch (Right==True)

If shutterswitch = False or missing:
    'shutter_left' and 'shutter_right' are two independent shutters.
'''
shutter = 'Demo' # 'Demo', 'NI', or 'cDAQ'
shutterswitch = False # see legend above
shutteroptions = ('Left', 'Right') # Shutter options of the GUI
shutterdict = {'shutter_left' : '/PXI1Slot4/port0/line6', # left (general) shutter
              'shutter_right' : '/PXI1Slot4/port0/line1'} # flip mirror or right shutter, depending on physical configuration

# ===== from config/hardware/filterwheels/demo_filterwheel.py =====
'''
Filterwheel configuration.

For the 'Demo' wheel, no COMport needs to be specified.
For a Ludl Filterwheel, a valid COMport is necessary. Ludl marking 10 = position 0.
For the plugin-based LudlPlugin, COMport, baudrate, and wait_until_done_delay are required.
For SutterPlugin, COMport, baudrate, wheel_speed, and wait_until_done_delay are required.
For ZWOPlugin, no parameters are required ('wait_until_done_delay', 'wheel_index' and 'dll_path' are optional).
For a Dynamixel FilterWheel, valid baudrate and servo_id are necessary.
'''
filterwheel_parameters = {'filterwheel_type' : 'Demo', # 'Demo', 'Ludl', 'LudlPlugin', 'Sutter', 'SutterPlugin', 'Dynamixel', 'ZWO', 'ZWOPlugin', 'FLI'
                          } # the 'Demo' wheel needs no connection settings, see the examples below
# To use the plugin-based Ludl driver instead:
# filterwheel_parameters = {'filterwheel_type': 'LudlPlugin',
#                           'COMport': 'COM3',
#                           'baudrate': 9600,
#                           'wait_until_done_delay': 0.2}
# To use the plugin-based Sutter driver instead:
# filterwheel_parameters = {'filterwheel_type': 'SutterPlugin',
#                           'COMport': 'COM3',
#                           'baudrate': 128200,
#                           'wheel_speed': 3,
#                           'wait_until_done_delay': 0.5}
# To use the plugin-based ZWO EFW driver instead (no COMport, USB SDK):
# filterwheel_parameters = {'filterwheel_type': 'ZWOPlugin',
#                           'wait_until_done_delay': 1.0,  # optional, defaults to 1.0 s
#                           'wheel_index': 0,  # optional, for >1 connected EFW wheel
#                           }
# To use an FLI High Speed Filter Wheel instead:
# filterwheel_parameters = {'filterwheel_type': 'FLI',
#                           'COMport': 'COM3',
#                           'baudrate': 9600,
#                           'wait_until_done_delay': 0.2}

'''
filterdict contains filter labels and their positions. The valid positions are:
For Ludl: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For Sutter and SutterPlugin: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For FLI: configured integer positions 0 .. 9 are transmitted without conversion.
For Dynamixel: servo encoder counts, e.g. 0 for 0 deg, 1024 for 45 deg (360 deg = 4096 counts, or 11.377 counts/deg).
Dynamixel encoder range in multi-turn mode: -28672 .. +28672 counts.
For ZWO and ZWOPlugin: slot ids (int) starting at 0, e.g. 0 .. 4 for the EFW Mini 5-slot wheel.
'''
filterdict = {'Empty' : 0, # Every config should contain at least this entry
              '405-488-647-Tripleblock' : 1,
              '405-488-561-640-Quadrupleblock' : 2,
              '464 482-35' : 3,
              '508 520-35' : 4,
              '515LP' : 5,
              '529 542-27' : 6,
              '561LP' : 7,
              '594LP' : 8,
              'Empty-1' : 9} # Dictionary labels must be unique!

# ===== from config/hardware/objectives/demo_zoom.py =====
'''
Zoom / objective configuration ('objectives' is the historical name for zoom).

For 'Demo', no connection settings are needed.
For a 'Dynamixel' servo-driven zoom, 'servo_id', 'COMport' and 'baudrate' (default 1000000) must be specified.
For 'Mitu' (Mitutoyo revolver), 'COMport' and 'baudrate' (default 9600) must be specified.
'''
zoom_parameters = {'zoom_type' : 'Demo', # 'Demo', 'Dynamixel', or 'Mitu'
                   }

'''
The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface. Values are the 'Dynamixel' servo positions.

The 'Mitu' (Mitutoyo revolver) positions are letters instead:
zoomdict = {'2x': 'A', '5x': 'B', '7.5x': 'C', '10x': 'D', '20x': 'E'}
'''
zoomdict = {'1x' : 2707,
            '2x' : 1706,
            '4x Olympus' : 637,
            '5x Mitutoyo' : 318,
            }

'''
Pixelsize in micron. Keys must match the zoomdict keys.
'''
pixelsize = {
            '1x' : 5.0,
            '2x' : 2.5,
            '4x Olympus' : 1.25,
            '5x Mitutoyo' : 1.0,}

# ===== from config/hardware/galvos/demo_galvos.py =====
'''
Galvo configuration.

Make sure that 'galvo_l_amplitude' and 'galvo_r_amplitude' (in V) are correct,
i.e. not above the max input allowed by your galvos.
'''
import numpy as np

'''
Rescale the galvo amplitude when zoom is changed.
For example, if 'galvo_l_amplitude' = 1 V at zoom '1x', it will be 2 V at zoom '0.5x'
'''
scale_galvo_amp_with_zoom = True

# ===== from config/hardware/ETLs/demo_etl.py =====
'''
ETL (electrically tunable lens) configuration.

The zoom-dependent ETL offsets/amplitudes live in the CSV file referenced by
'ETL_cfg_file' (path relative to the working directory, see config/etl_parameters/).
The values below are the initial state before that file is applied.
'''

# ===== from config/plugins/writers/demo_writers.py =====
'''
ImageWriter plugin parameters for a demo/simulation machine (e.g. a laptop).

Identical to plugins/writers/production_writers.py apart from 'ring_buffer_size' of
MP_OME_Zarr_Writer, which is kept small so that the writer fits in the RAM of a laptop.
Config files never include each other in a chain: this file repeats the content instead.
'''

'''
Options to control the behavior of plugins.
"path_list": where mesoSPIM looks for plugins. Entries that do not exist are ignored, so add
your own location in the user config rather than removing the built-in one.
"first_image_writer": the writer offered first in the filenaming wizard. Any ImageWriter
plugin name works, not only the built-in ones.
'''
plugins = {
    'path_list': [
        "../src/plugins",         # the plugins shipped with mesoSPIM (use '/')
        "C:/a/different/plugin/location",  # Ignored if it does not exist (use '/')
    ],
    'first_image_writer': 'MP_OME_Zarr_Writer', # 'H5_BDV_Writer', 'OME_Zarr_Writer', 'MP_OME_Zarr_Writer', 'Tiff_Writer', 'Big_Tiff_Writer', 'RAW_Writer'
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
This writer generates ome.zarr specification multiscale data on the fly during acquisition.
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
to make mesoSPIM pause after each tile acquisition until the multiscale is finished generating.
Applies to OME_Zarr_Writer only: the multiprocess writer always finalizes synchronously.
'''
OME_Zarr_Writer = {
    'ome_version': '0.4', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': True, #True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd', # None, 'zstd', 'lz4'
    'compression_level': 5, # 1-9
    'shards': (64,6000,6000), # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (256,256,256), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (64,64,64), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': True, # True, False

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True, # True, False
    'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False, # in case X and Y axes need to be swapped for the correct BigStitcher tile positions
    }

MP_OME_Zarr_Writer = {
    'ome_version': '0.4',  # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': True, # True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd',  # None, 'zstd', 'lz4'
    'compression_level': 5,  # 1-9
    'shards': (64, 6000, 6000),  # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (256, 256, 256),
    # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (64, 64, 64),
    # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True,  # True, False
    'flip_xyz': (True, True, False),  # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False,  # in case X and Y axes need to be swapped for the correct BigStitcher tile positions

    # Multiprocess options
    'ring_buffer_size': 16,  # Max number of images in the shared memory ring buffer;
    # 16 for a laptop/simulation, 512 for a production workstation with fast IO

    # Write cache options. Write tile data to cache then move to acquisition folder
    # None acquires data direct to acquisition folder.
    'write_cache': None # None, 'e:/path/to/fast/ssd/write/cache'
}

# ===== from config/UI/default_ui.py =====
'''
User interface options.

Override single keys in your own config file after the include(), e.g.
    ui_options['dark_mode'] = False
'''
ui_options = {'dark_mode' : True, # Dark mode: Renders the UI dark if enabled
              'enable_x_buttons' : True, # Here, specific sets of UI buttons can be disabled
              'enable_y_buttons' : True,
              'enable_z_buttons' : True,
              'enable_f_buttons' : True,
              'enable_f_zero_button' : True, # set to False if objective change requires F-stage movement (e.g. mesoSPIM v6-Revolver), for safety reasons
              'enable_rotation_buttons' : True,
              'enable_loading_buttons' : True,
              'flip_XYZFT_button_polarity': (True, False, False, False, False), # flip the polarity of the stage buttons (X, Y, Z, F, Theta)
              'button_sleep_ms_xyzft' : (250, 0, 250, 0, 0), # step-motion buttons disabled for N ms after click. Prevents stage overshooting outside of safe limits, for slow stages.
              'window_pos': (0, 0), # position of the main window on the screen, top left corner.
              'usb_webcam_ID': 0, # open USB web-camera (if available): None,  0 (first cam), 1 (second cam), ...
              'flip_auto_LR_illumination': False, # flip the polarity of the "Auto L/R illumination" button in Acquisition Manager
               }

sidepanel = 'Demo' #'Demo' or 'FarmSimulator', deprecated

'''
Microscope metadata
Stored in acquisition metadata sidecars and does not change mesoSPIM behavior.
Add or remove keys as needed for your microscope.
'''
microscope_parameters = {
            'name': 'Demo mesoSPIM',
            'institution': 'University of Demo',
            'location': 'Demo room',
            'instrument_id': 'DEMO-001',
            'notes': 'Example configuration for demo mode',
            'objective_parameters': {
                        'name': 'Demo objective',
                        'model_number': 'DEMO-001',
                        'magnification': '1x',
                        'numerical_aperture': 0.28,
                        'working_distance_mm': 34,
                        'immersion_medium': 'air',
                        'design_refractive_index': 1.0,
                        'coverglass_thickness_mm': 0.17,
                        },
            'users': {
                        'authorized': ['Doe, John', 'Doe, Jane', 'Chewbacca'],
                        'owner': 'Demo Operator',
                        }
            }

logging_level = 'DEBUG' # 'DEBUG' for ultra-detailed, 'INFO' for general logging level

'''
Personal settings and overrides.
Everything here wins over the hardware files included above.
Make sure that all the file paths exist.
'''

# Examples of overriding a single setting for this user only:
# ui_options['dark_mode'] = False
# camera_parameters['x_pixels'] = 2048
# stage_parameters['y_load_position'] = -8000
# startup.update({'zoom': '1x', 'camera_exposure_time': 0.05})

'''
Initial state of the microscope at startup, collected from the sections above.
'''
startup = {
# --- hardware/cameras/demo_camera.py ---
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.2, # demo default
'camera_exposure_time' : 0.02,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 2, # un-deprecated for older computers
'camera_display_acquisition_subsampling': 2, # un-deprecated for older computers
'camera_display_temporal_subsampling': 2, # newly added for performance and stability boost
'average_frame_rate': 4.5,
# --- hardware/DAQ/demo_daq.py ---
'samplerate' : 100000,
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
# --- hardware/stages/demo_stage.py ---
'position' : {'x_pos':0, 'y_pos':1000, 'z_pos':2000, 'f_pos':5000, 'theta_pos':180},
# --- hardware/lasers/demo_lasers.py ---
'laser' : '488 nm',
'max_laser_voltage' : 5, # 5 V for Toptica MLEs, 10 V for Omicron SOLE
'intensity' : 10,
'laser_interleaving' : False,
'shutterstate' : False, # Is the shutter open or not?
'shutterconfig' : 'Right', # Can be "Left", "Right", "Both", "Interleaved"
'laser_l_delay_%' : 10,
'laser_l_pulse_%' : 87,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 10,
'laser_r_pulse_%' : 87,
'laser_r_max_amplitude_%' : 100,
# --- hardware/filterwheels/demo_filterwheel.py ---
'filter' : 'Empty', # must exist in filterdict above
# --- hardware/objectives/demo_zoom.py ---
'zoom' : '2x', # must exist in zoomdict above
'pixelsize' : 2.5, # must match pixelsize[startup['zoom']]
# --- hardware/galvos/demo_galvos.py ---
'galvo_l_frequency' : 99.9,
'galvo_l_amplitude' : 2.5,
'galvo_l_offset' : 0,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : np.pi/2,
'galvo_r_frequency' : 99.9,
#'galvo_r_amplitude' : 0.0, # currently not used
'galvo_r_offset' : 0,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/2,
# --- hardware/ETLs/demo_etl.py ---
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
'etl_l_delay_%' : 7.5,
'etl_l_ramp_rising_%' : 85,
'etl_l_ramp_falling_%' : 2.5,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.3,
'etl_r_delay_%' : 2.5,
'etl_r_ramp_rising_%' : 5,
'etl_r_ramp_falling_%' : 85,
'etl_r_amplitude' : 0.65,
'etl_r_offset' : 2.36,
# --- personal settings of this user ---
'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
'folder' : 'D:/tmp/',
'snap_folder' : 'D:/tmp/',
'file_prefix' : '',
'file_suffix' : '000001',
}
