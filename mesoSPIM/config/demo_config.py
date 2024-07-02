import numpy as np

'''
mesoSPIM configuration file.

Use this file as a starting point to set up all mesoSPIM hardware by replacing the 'Demo' designations
with real hardware one-by-one. Make sure to rename your new configuration file to a different filename
(The extension has to be .py).
'''

'''
Dark mode: Renders the UI dark
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
              'window_pos': (100, 100), # position of the main window on the screen, top left corner.
              'usb_webcam_ID': 0, # open USB web-camera (if available): None,  0 (first cam), 1 (second cam), ...
              'flip_auto_LR_illumination': False, # flip the polarity of the "Auto L/R illumination" button in Acquisition Manager
               }

logging_level = 'DEBUG' # 'DEBUG' for ultra-detailed, 'INFO' for general logging level

'''
Waveform output for Galvos, ETLs etc.
'''
waveformgeneration = 'DemoWaveFormGeneration' # 'DemoWaveFormGeneration' or 'NI'

'''
Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

The new mesoSPIM configuration (benchtop-inspired) uses one card (PXI6733) and allows up to 4 laser channels.

Physical channels must be connected in certain order:
- 'galvo_etl_task_line' takes Galvo-L, Galvo-R, ETL-L, ETL-R 
(e.g. value 'PXI6259/ao0:3' means Galvo-L on ao0, Galvo-R on ao1, ETL-L on ao2, ETL-R on ao3)

- 'laser_task_line' takes laser modulation, lasers sorted in increasing wavelength order,
(e.g. value 'PXI6733/ao4:7' means '405 nm' connected to ao4, '488 nm' to ao5, etc.)
'''

acquisition_hardware = {'master_trigger_out_line' : 'PXI6259/port0/line1',
                        'camera_trigger_source' : '/PXI6259/PFI0',
                        'camera_trigger_out_line' : '/PXI6259/ctr0',
                        'galvo_etl_task_line' : 'PXI6259/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI6259/PFI0',
                        'laser_task_line' :  'PXI6733/ao0:3',
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}

sidepanel = 'Demo' #'Demo' or 'FarmSimulator', deprecated

'''
Digital laser enable lines
'''

laser = 'Demo' # 'Demo' or 'NI'

''' The `laserdict` specifies laser labels of the GUI and their digital modulation channels. 
Keys are the laser designation that will be shown in the user interface
Values are DO ports used for laser ENABLE digital signal.
Critical: entries must be sorted in the increasing wavelength order: 405, 488, etc.
'''
laserdict = {'488 nm': 'PXI6733/port0/line2',
             '520 nm': 'PXI6733/port0/line3',
             '568 nm': 'PXI6733/port0/line4',
             '638 nm': 'PXI6733/port0/line5',
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
shutter = 'Demo' # 'Demo' or 'NI'
shutterswitch = False # see legend above
shutteroptions = ('Left', 'Right') # Shutter options of the GUI
shutterdict = {'shutter_left' : 'PXI6259/port0/line0', # left (general) shutter
              'shutter_right' : 'PXI6259/port2/line0'} # flip mirror or right shutter, depending on physical configuration
              
'''
Camera configuration

For a DemoCamera, only the following options are necessary
(x_pixels and y_pixels can be chosen arbitrarily):

camera_parameters = {'x_pixels' : 1024,
                     'y_pixels' : 1024,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4]}

For a Hamamatsu Orca Flash 4.0 V2 or V3, the following parameters are necessary:

camera_parameters = {'x_pixels' : 2048,
                     'y_pixels' : 2048,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4],
                     'camera_id' : 0,
                     'sensor_mode' : 12,    # 12 for progressive
                     'defect_correct_mode': 2,
                     'binning' : '1x1',
                     'readout_speed' : 1,
                     'trigger_active' : 1,
                     'trigger_mode' : 1, # it is unclear if this is the external lightsheeet mode - how to check this?
                     'trigger_polarity' : 2, # positive pulse
                     'trigger_source' : 2, # external
                    }

For a Photometrics Iris 15, the following parameters are necessary:

camera_parameters = {'x_pixels' : 5056, 
                     'y_pixels' : 2960, 
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
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

For a Photometrics Prime BSI Express, the following parameters are necessary:

camera_parameters = {'x_pixels' : 2048, #5056
                     'y_pixels' : 2048, # 2960
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4],
                     'speed_table_index': 1, # 1 for 100 MHz
                     'exp_mode' : 'Edge Trigger', # Lots of options in PyVCAM --> see constants.py
                     'readout_port': 0,
                     'gain_index': 1, # Enable HDR mode
                     'exp_out_mode': 4, # 4: line out 
                     'binning' : '1x1',
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 0, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 7, # 11.2 us x factor, a factor = 3 equals 33.6 us
                    }

'''
camera = 'DemoCamera' # 'DemoCamera' or 'HamamatsuOrca' or 'Photometrics'

camera_parameters = {'x_pixels' : 2000,
                     'y_pixels' : 1000,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4],
                     'camera_id' : 0,
                     'sensor_mode' : 12,    # 12 for progressive
                     'defect_correct_mode': 2,
                     'binning' : '1x1',
                     'readout_speed' : 1,
                     'trigger_active' : 1,
                     'trigger_mode' : 1, # it is unclear if this is the external lightsheeet mode - how to check this?
                     'trigger_polarity' : 2, # positive pulse
                     'trigger_source' : 2, # external
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
All positions are absolute.

'stage_type' option:
ASI stages, 'stage_type' : 'TigerASI', 'MS2000ASI'
PI stages, 'stage_type' : 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Mixed stages, 'stage_type' : 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz', 'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy',
'''

stage_parameters = {'stage_type' : 'DemoStage', # one of 'DemoStage', 'PI_1controllerNstages', 'PI_NcontrollersNstages', 'TigerASI', etc, see above
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

''''
If 'stage_type' = 'PI_1controllerNstages' (vanilla mesoSPIM V5 with single 6-axis controller):
pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118075764'),
                 }

If 'stage_type' = 'PI_NcontrollersNstages' (mesoSPIM V5 with multiple single-axis controllers):
pi_parameters = {'axes_names': ('x', 'y', 'z', 'theta', 'f'),
                'stages': ('L-509.20SD00', 'L-509.40SD00', 'L-509.20SD00', None, 'MESOSPIM_FOCUS'),
                'controllername': ('C-663', 'C-663', 'C-663', None, 'C-663'),
                'serialnum': ('**********', '**********', '**********', None, '**********'),
                'refmode': ('FRF', 'FRF', 'FRF', None, 'RON')
                }
                

If 'stage_type' = 'TigerASI' (benchtop mesoSPIM with an ASI Tiger controller)
The stage assignment dictionary assigns a mesoSPIM stage (xyzf and theta - dict key) to an ASI stage (XYZ etc) 
which are the values of the dict.


asi_parameters = {'COMport' : 'COM32',
                  'baudrate' : 115200,
                  'stage_assignment': {'x':'X', 'y':'V', 'z':'Z', 'theta':'T', 'f':'Y'},
                  'encoder_conversion': {'V': 10., 'Z': 10., 'R': 100., 'X': 10., 'Y': 10.}, # num of encoder counts per um or degree, depending on stage type.
                  'stage_trigger_source': '/PXI1Slot4/PFI0',
                  'stage_trigger_out_line': '/PXI1Slot4/ctr1',
                  'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
                  'stage_trigger_pulse_%' : 1,
                  'ttl_motion_enabled': True,
                  'ttl_cards':(2,3),
                  }
'''

'''
Filterwheel configuration
For a DemoFilterWheel, no COMport needs to be specified.
For a Ludl Filterwheel, a valid COMport is necessary. Ludl marking 10 = position 0.
For a Dynamixel FilterWheel, valid baudrate and servoi_id are necessary. 
'''
filterwheel_parameters = {'filterwheel_type' : 'Demo', # 'Demo', 'Ludl', 'Sutter', 'Dynamixel', 'ZWO'
                          'COMport' : 'COM3', # irrelevant for 'ZWO'
                          'baudrate' : 115200, # relevant only for 'Dynamixel'
                          'servo_id' :  1, # relevant only for 'Dynamixel'
                          }
'''
filterdict contains filter labels and their positions. The valid positions are:
For Ludl: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For Dynamixel: servo encoder counts, e.g. 0 for 0 deg, 1024 for 45 deg (360 deg = 4096 counts, or 11.377 counts/deg). 
Dynamixel encoder range in multi-turn mode: -28672 .. +28672 counts.
For ZWO EFW Mini 5-slot wheel: positions 0, 1, .. 4.
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

'''
Zoom configuration
For the 'Demo', 'servo_id', 'COMport' and 'baudrate' do not matter. 
For a 'Dynamixel' servo-driven zoom, 'servo_id', 'COMport' and 'baudrate' (default 1000000) must be specified
For 'Mitu' (Mitutoyo revolver), 'COMport' and 'baudrate' (default 9600) must be specified
'''
zoom_parameters = {'zoom_type' : 'Demo', # 'Demo', 'Dynamixel', or 'Mitu'
                   'COMport' : 'COM1',
                   'baudrate' : 9600,
                   'servo_id': 4, # only for 'Dynamixel'
                   }

'''
The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface.
'''
'''
The 'Dynamixel' servo default zoom positions
'''
zoomdict = {'1x' : 2707,
            '2x' : 1706,
            '4x' : 637,
            '5x' : 318,
            }    


'''
The 'Mitu' (Mitutoyo revolver) positions

zoomdict = {'2x': 'A',
            '5x': 'B',
            '7.5x': 'C',
            '10x': 'D',
            '20x': 'E',
            }
'''
'''
Pixelsize in micron
'''
pixelsize = {
            '1x' : 1,
            '2x' : 2.0,
            '4x' : 4.0,
            '5x' : 5.0,}

'''
 HDF5 parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
hdf5 = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy': False, # in case X and Y axes need to be swapped for the correct tile positions
        }

buffering = {'use_ram_buffer': False, # If True, the data is buffered in RAM before writing to disk. If False, data is written to disk immediately after each frame
             'percent_ram_free': 20, # If use_ram_buffer is True and once the free RAM is below this value, the data is written to disk.
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
'''
startup = {
'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
'samplerate' : 100000,
'sweeptime' : 0.2,
'position' : {'x_pos':0,'y_pos':1000,'z_pos':2000,'f_pos':5000,'theta_pos':180},
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
'folder' : 'D:/tmp/',
'snap_folder' : 'D:/tmp/',
'file_prefix' : '',
'file_suffix' : '000001',
'zoom' : '1x',
'pixelsize' : 1.0,
'laser' : '488 nm',
'max_laser_voltage':5,
'intensity' : 10,
'shutterstate':False, # Is the shutter open or not?
'shutterconfig':'Right', # Can be "Left", "Right","Both","Interleaved"
'laser_interleaving':False,
'filter' : 'Empty',
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
'galvo_l_frequency' : 99.9,
'galvo_l_amplitude' : 2.5,
'galvo_l_offset' : 0,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : np.pi/2,
'galvo_r_frequency' : 99.9,
'galvo_r_amplitude' : 2.5,
'galvo_r_offset' : 0,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/2,
'laser_l_delay_%' : 10,
'laser_l_pulse_%' : 87,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 10,
'laser_r_pulse_%' : 87,
'laser_r_max_amplitude_%' : 100,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_exposure_time':0.02,
'camera_line_interval':0.000075, # Hamamatsu-specific parameter
'camera_display_live_subsampling': 2,
#'camera_display_snap_subsampling': 1, #deprecated
'camera_display_acquisition_subsampling': 2,
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM', # Hamamatsu-specific parameter
'average_frame_rate': 2.5,
}
