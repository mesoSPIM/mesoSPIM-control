import numpy as np

logging_level = 'DEBUG' # 'INFO' or 'DEBUG'

'''
Options to control behavior of plugins
"paths_list": Optional: Enables arbirtary locations for mesoSPIM to find plugins 
"first_image_writer": Optional: Enables a favorite plugin to be at the top of the filenaming wizard. Builtin plugins 
are listed as options, by any ImageWriter plugin can be 
'''
plugins = {
    'path_list': [
        "../src/plugins/ImageWriters",         # Ignored if it does not exits (use '/')
        "C:/a/different/plugin/location",  # Ignored if it does not exits (use '/')
    ],
    'first_image_writer': 'MP_OME_Zarr_Writer', # 'H5_BDV_Writer', 'MP_OME_Zarr_Writer', 'OME_Zarr_Writer', 'Tiff_Writer', 'Big_Tiff_Writer', 'RAW_Writer'
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

waveformgeneration = 'NI' # 'DemoWaveFormGeneration' or 'NI'

'''
Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

Physical connections:
- 'master_trigger_out_line' ('PXI1Slot4/port0/line0') must be physically connected to BNC-2110 "PFI0 / AI start" terminal.
- 'camera_trigger_out_line' to PFI12 / P2.4 ('/PXI1Slot4/ctr0') terminal
- 'stage_trigger_out_line' to PFI13 / P2.5 ('/PXI1Slot4/ctr1') terminal
- galvos, ETL controllers to 'PXI1Slot4/ao0:3' terminals
- laser analog modulation cables to 'PXI1Slot4/ao4:7' terminals
'''

acquisition_hardware = {'master_trigger_out_line' : 'PXI1Slot4/port0/line0',
                        'camera_trigger_source' : '/PXI1Slot4/PFI0',
                        'camera_trigger_out_line' : '/PXI1Slot4/ctr0',
                        'galvo_etl_task_line' : 'PXI1Slot4/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI1Slot4/PFI0',
                        'laser_task_line' :  'PXI1Slot4/ao4:7',
                        'laser_task_trigger_source' : '/PXI1Slot4/PFI0'}

'''
Human interface device (Joystick)
'''
sidepanel = 'Demo' #'Demo' or 'FarmSimulator'

laser = 'NI' # 'Demo' or 'NI'

''' Laser blanking indicates whether the laser enable lines should be set to LOW between individual
'images' or 'stacks'. This is helpful to avoid laser bleedthrough between images caused by insufficient
modulation depth of the analog input (even at 0V, some laser light is still emitted).
'''
laser_blanking = 'images' # 'images' by default, unless laser enable is connected to a slow mechanical shutter

''' The laserdict keys are the laser designation that will be shown in the user interface. 
Values are DO ports used for laser ENABLE digital signal.
Critical: keys must be sorted by increasing wavelength order: 405, 488, 561, etc.
'''
laserdict = {'405 nm': 'PXI1Slot4/port0/line2',
             '488 nm': 'PXI1Slot4/port0/line3',
             '561 nm': 'PXI1Slot4/port0/line4', 
             '638 nm': 'PXI1Slot4/port0/line5',
             }

'''
Shutter configuration
'''

shutter = 'NI' # 'Demo' or 'NI'
shutterdict = {'shutter_left' : '/PXI1Slot4/port0/line6', # empty terminal here, general shutter
              'shutter_right' : '/PXI1Slot4/port0/line1', # flip mirror control
              }

''' A bit of a hack: Shutteroptions for the GUI '''
shutteroptions = ('Left','Right')

''' A bit of a hack: Assumes that the shutter_left line is the general shutter
and the shutter_right line is the left/right switch (Right==True)'''

shutterswitch = False # If True, shutter_left line is the general shutter

'''
Camera configuration
'''

'''
For a DemoCamera, only the following options are necessary
(x_pixels and y_pixels can be chosen arbitrarily):

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
                     'scan_line_delay' : 3, # 10.26 us x factor, a factor = 6 equals 71.82 us
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
                    'y_load_position': 35000,
                    'y_unload_position': -20000,
                    'x_center_position': 500,
                    'z_center_position': 500,
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 550000,
                    'y_min' : -25000,
                    'z_max' : 50000,
                    'z_min' : -55000,
                    'f_max' : 50000,
                    'f_min' : -55000,
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }
'''
Depending on the stage hardware, further dictionaries define further details of the stage configuration

For a standard mesoSPIM V4 with PI stages, the following pi_parameters are necessary (replace the
serialnumber with the one of your controller):
'''
'''
pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('M-605.2DD','L-406.40DG10','M-112K033','M-116.DG','M-112K033','NOSTAGE'), # M-605.2DD, M-112K033
                 'refmode' : ('FRF',),
                 'serialnum' : ('119046748'),
                 }
'''

'''
For a standard mesoSPIM V5 with PI stages, the following pi_parameters are necessary (replace the
serialnumber with the one of your controller):

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118015799'),
'''

'''
For a benchtop mesoSPIM with an ASI Tiger controller, the following parameters are necessary.
The stage assignment dictionary assigns a mesoSPIM stage (xyzf and theta - dict key) to an ASI stage (XYZ etc)
which are the values of the dict.
'''
asi_parameters = {'COMport' : 'COM6',
                  'baudrate' : 115200,
                  'stage_assignment': {'x':'X', 'f':'Y', 'z':'Z', 'theta':'T', 'y':'V'}, # The dictionary order is important here! Must match the ASI cards 1,2,3, let to right. This is standard ASI cards order: XYZTV
                  'encoder_conversion': {'X': 10., 'Y': 10., 'Z': 10., 'T': 1000., 'V': 10.}, # Num of encoder counts per um or degree, depending on stage type. The order match the 'stage_assignment' dictionary order.
                  'speed': {'X': 3., 'Y': 3., 'Z': 3., 'T': 30., 'V': 3.}, # mm/s or deg/s.
                  'stage_trigger_source': '/PXI1Slot4/PFI0',
                  'stage_trigger_out_line': '/PXI1Slot4/ctr1',
                  'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
                  'stage_trigger_pulse_%' : 1,
                  'ttl_motion_enabled': True,
                  'ttl_cards':(1,2),
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
              '488LB RazorEdge': 2,
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

zoomdict = {'2x' : 4,
            '5x' : 6,
            '7.5x' : 7,
            '10x' : 8,
            '20x' : 9,
            }
'''
Pixelsize in micron
'''
pixelsize = {'2x' : 4.25/2,
            '5x' : 4.25/5,
            '7.5x' : 4.25/7.5,
            '10x' : 4.25/10,
            '20x' : 4.25/20,
            }

'''
H5_BDV_Writer parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
H5_BDV_Writer = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy' : False, # True for Hamamatsu, False for Photometrix, possibly due to different coordinate systems.
        }
            
'''
Rescale the galvo amplitude when zoom is changed
For example, if 'galvo_l_amplitude' = 1 V at zoom '1x', it will ve 2 V at zoom '0.5x'
'''        
scale_galvo_amp_with_zoom = True 

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
'''

OME_Zarr_Writer = {
    'ome_version': '0.4', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': False, #True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd', # None, 'zstd', 'lz4'
    'compression_level': 5, # 1-9
    'shards': (64,6000,6000), # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (128,5056//4,2960//2), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x). Here, optimized for fewer files.
    'target_chunks': (128,5056//4,2960//2), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x). Here, optimized for fewer files.
    'async_finalize': False, # True, False
    'write_big_stitcher_xml': True, # BigStitcher XML file for compatibiliyt ('ome_version': '0.4')
    'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy' : False, # True for Hamamatsu, False for Photometrix, possibly due to different coordinate systems.
    }

MP_OME_Zarr_Writer = {
    'ome_version': '0.4',  # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': False, # True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd',  # None, 'zstd', 'lz4'
    'compression_level': 5,  # 1-9
    'shards': (64, 6000, 6000),  # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (128, 5056//4, 2960//2),
    # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (128, 5056//4, 2960//2),
    # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': False,  # True, False

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True,  # True, False
    'flip_xyz': (True, True, False),  # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False,  # in case X and Y axes need to be swapped for the correct BigStitcher tile positions

    # Multiprocess options
    'ring_buffer_size': 512,  # Max number of images in shared memory ring buffer
         
    # Write cache options. Write tile data to cache then move to acquisition folder
    # None acquires data direct to acquisition folder.
    'write_cache': 'F:/mesoSPIM_CACHE', # None, 'e:/path/to/fast/ssd/write/cache'
}

'''
Initial acquisition parameters

Used as initial values after startup

When setting up a new mesoSPIM, make sure that:
* 'max_laser_voltage' is correct (5 V for Toptica MLEs, 10 V for Omicron SOLE)
* 'galvo_l_amplitude' and 'galvo_r_amplitude' (in V) are correct (not above the max input allowed by your galvos)
* all the filepaths exist
* the initial filter exists in the filter dictionary above
'''

startup = {
'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
'samplerate' : 100000,
'sweeptime' : 0.130,
'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters-benchtop.csv',
'filepath' : 'F:/Test/file.tif',
'folder' : 'F:/Test/',
'snap_folder' : 'X:/',
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
'etl_l_delay_%' : 0,
'etl_l_ramp_rising_%' : 99, # 94,
'etl_l_ramp_falling_%' : 1, #2,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.3,
'etl_r_delay_%' : 0,
'etl_r_ramp_rising_%' : 2, #0,
'etl_r_ramp_falling_%' : 98,
'etl_r_amplitude' : 0.65,
'etl_r_offset' : 2.36,
'galvo_l_frequency' : 100,
'galvo_l_amplitude' : 0.8, #0.8V at 5x
'galvo_l_offset' : -0.75,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : 1.0,
'galvo_r_frequency' : 100,
'galvo_r_amplitude' : 0.8, #0.8V at 5x
'galvo_r_offset' : 1.3,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/7,
'laser_l_delay_%' : 1,
'laser_l_pulse_%' : 98,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 1,
'laser_r_pulse_%' : 98,
'laser_r_max_amplitude_%' : 100,
'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
'stage_trigger_pulse_%' : 1,
'camera_delay_%' : 1,
'camera_pulse_%' : 1,
'camera_exposure_time':0.010,
'camera_line_interval':0.000075, # Hamamatsu parameter
'camera_display_live_subsampling': 2,
'camera_display_snap_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 10, # newly added for performance and stability boost
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM',
'average_frame_rate': 4.4,
}
