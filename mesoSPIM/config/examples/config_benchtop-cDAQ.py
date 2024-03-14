'''
Testing cDAQ configuration: 2x NI-9401 (digital) cards and 1x NI-9264 (analog) card.
'''

import numpy as np

logging_level = 'DEBUG'

ui_options = {'dark_mode' : True, # Dark mode: Renders the UI dark if enabled
              'enable_x_buttons' : True, # Here, specific sets of UI buttons can be disabled
              'enable_y_buttons' : True,
              'enable_z_buttons' : True,
              'enable_f_buttons' : True,
              'enable_rotation_buttons' : True,
              'enable_loading_buttons' : True,
              'usb_webcam_ID': 0, # open USB web-camera (if available): 0 (first cam), 1 (second cam), ...
               }

'''
Waveform output for Galvos, ETLs etc.
'''

waveformgeneration = 'cDAQ' # 'DemoWaveFormGeneration' or 'NI' or 'cDAQ'

'''
compactDAQ limitations:
https://www.ni.com/en/support/documentation/supplemental/18/number-of-concurrent-tasks-on-a-compactdaq-chassis-gen-ii.html
Number of tasks is limited (1 DI, 1 DO, 1 AO, 4 general-purpose counters), first reserved task gets the most resources.
The data streams are comprised by an 8KB block of memory that is divided up into six or seven First In First Out (FIFO) data buffers. 
These data buffers vary in size, and the largest data buffers are assigned to the first tasks that get reserved. 
Thus, in order to get the best streaming performance, make sure to reserve your highest bandwidth tasks first. 
Your first two tasks will reserve 2048 bytes each, the third, fourth and fifth tasks will reserve 1024 bytes each and the sixth and seventh tasks will reserve 512 bytes each.

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
- 'stage_trigger_out_line' to '/cDAQ1Mod1/port0/line2' (Pin17 of cDAQ1Mod1 card)

DIGITAL INPUTS (P0.4, NI-9401 card in slot 1, 'cDAQ1Mod1'):
- '/cDAQ1Mod1/PFI4' (aka P0.4/PFI4, pin20, see above) of the same card cDAQ1Mod1. Triggers camera, stage, galvo/ETL tasks.

ANALOG OUTPUTS (NI-9264 card in slot 3, 'cDAQ1Mod3'):
- galvos, ETL controllers to 'cDAQ1Mod3/ao0:3' terminals. Pins 1-4, ground pins on the opposite side.
- laser analog modulation cables to 'cDAQ1Mod3/ao4:7' terminals. Pins 5-8, ground pins on the opposite side.

NI-9401 (digital) card peculiarity:
Input/output mode can be assigned only to digital pins P0.0-P0.3, P0.4-P0.7, or both, so assignment must be grouped by 4 channels (called a nibble).

Connecting BNC cables to the ground: 
Signal pin - Ground pin, label:

'cDAQ1Mod1', NI-9401 (digital) card in slot 1:
Pin14-Pin1, 'master_trigger_out_line'
Pin19-Pin6, 'camera_trigger_out_line' 
Pin16-Pin3, 'shutter_right', arm switching
Pin17-Pin3, 'stage_trigger_out_line'
Pin20-Pin7, '/cDAQ1Mod1/PFI4' ('camera_trigger_source', 'galvo_etl_task_trigger_source', 'laser_task_trigger_source', and 'stage_trigger_source'). Could this be done via internal wiring instead?

'cDAQ1Mod2', NI-9401 (digital) card in slot 2:
Pin14-Pin1, 'cDAQ1Mod2/port0/line0', laser enable line for 405 nm
Pin16-Pin3, 'cDAQ1Mod2/port0/line1', laser enable line for 488 nm
Pin17-Pin4, 'cDAQ1Mod2/port0/line2', laser enable line for 561 nm
Pin19-Pin6, 'cDAQ1Mod2/port0/line3', laser enable line for 637 nm

'cDAQ1Mod3', NI-9264 (analog, DSUB-connector version) card in slot 3:
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
                        'laser_task_trigger_source' : '/cDAQ1Mod1/PFI4'}

'''
Human interface device (Joystick)
'''
sidepanel = 'Demo' #'Demo' or 'FarmSimulator'

laser = 'cDAQ' # 'Demo' or 'NI', or 'cDAQ'

''' Laser blanking indicates whether the laser enable lines should be set to LOW between individual
'images' or 'stacks'. This is helpful to avoid laser bleedthrough between images caused by insufficient
modulation depth of the analog input (even at 0V, some laser light is still emitted).
'''
laser_blanking = 'images' # 'images' by default, unless laser enable is connected to a slow mechanical shutter

''' The laserdict keys are the laser designation that will be shown in the user interface. 
Values are DO ports used for laser ENABLE digital signal.
Critical: keys must be sorted by increasing wavelength order: 405, 488, 561, etc.
'''
laserdict = {'405 nm': 'cDAQ1Mod2/port0/line0',
             '488 nm': 'cDAQ1Mod2/port0/line1',
             '561 nm': 'cDAQ1Mod2/port0/line2',
             '638 nm': 'cDAQ1Mod2/port0/line3',
             }

'''
Shutter configuration
'''

shutter = 'cDAQ' # 'Demo' or 'NI' or 'cDAQ'
shutterdict = {'shutter_left' : None, # empty terminal, general shutter, optional
              'shutter_right' : '/cDAQ1Mod1/port0/line1', # arm switching
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

camera = 'DemoCamera' # 'DemoCamera' or 'HamamatsuOrca' or 'Photometrics'

camera_parameters = {'x_pixels' : 1024,
                     'y_pixels' : 1024,
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

ASI stages supported: 'stage_type' : 'TigerASI', 'MS2000ASI'
PI stage support: 'stage_type' : 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Mixed stage types: 'stage_type' : 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz', 'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy', 
'''

stage_parameters = {'stage_type' : 'DemoStage', # 'DemoStage', 'PI', 'TigerASI' or other configs, see above.
                    'y_load_position': 10000,
                    'y_unload_position': -45000,
                    'x_max' : 51000,
                    'x_min' : -46000,
                    'y_max' : 160000,
                    'y_min' : -160000,
                    'z_max' : 99000,
                    'z_min' : -99000,
                    'f_max' : 99000,
                    'f_min' : -99000,
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
                  'stage_trigger_out_line': '/cDAQ1Mod1/port0/line2',
                  'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
                  'stage_trigger_pulse_%' : 1,
                  'ttl_motion_enabled': True,
                  'ttl_cards':(2,3),
                  }
                  
'''
Filterwheel configuration
For a DemoFilterWheel, no COMport needs to be specified.
For a Ludl Filterwheel, a valid COMport is necessary. Ludl marking 10 = position 0.
For a Dynamixel FilterWheel, valid baudrate and servoi_id are necessary. 
'''
filterwheel_parameters = {'filterwheel_type' : 'Demo', # 'Demo', 'Ludl', 'Dynamixel', 'ZWO'
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

zoomdict = {'1x' : 2,
            '1.2x' : 3,
            '2x' : 4,
            '4x' : 5,
            '5x' : 6,
            '7.5x' : 7,
            '10x' : 8,
            '20x' : 9,
            }
'''
Pixelsize in micron
'''
pixelsize = {'1x': 4.25,
            '1.2x' : 4.25/1.2,
            '2x' : 4.25/2,
            '4x' : 4.25/4,
            '5x' : 4.25/5,
            '7.5x' : 4.25/7.5,
            '10x' : 4.25/10,
            '20x' : 4.25/20,
            }

'''
 HDF5 parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
hdf5 = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy' : False, # True for Hamamatsu, False for Photometrix, possibly due to different coordinate systems.
        }

buffering = {'use_ram_buffer': True, # If True, the data is buffered in RAM before writing to disk. If False, data is written to disk immediately after each frame
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
'samplerate' : 25000, # limited to 25kS/s for cDAQ cards
'sweeptime' : 0.26734,
'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters-BT-DBE.csv',
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
'etl_l_delay_%' : 5,
'etl_l_ramp_rising_%' : 90,
'etl_l_ramp_falling_%' : 5,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.3,
'etl_r_delay_%' : 2.5,
'etl_r_ramp_rising_%' : 5,
'etl_r_ramp_falling_%' : 85,
'etl_r_amplitude' : 0.65,
'etl_r_offset' : 2.36,
'galvo_l_frequency' : 99.9,
'galvo_l_amplitude' : 0.8, #0.8V at 5x
'galvo_l_offset' : 0.0,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : np.pi/7,
'galvo_r_frequency' : 99.9,
'galvo_r_amplitude' : 0.8, #0.8V at 5x
'galvo_r_offset' : 0.0,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/7,
'laser_l_delay_%' : 10,
'laser_l_pulse_%' : 87,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 10,
'laser_r_pulse_%' : 87,
'laser_r_max_amplitude_%' : 100,
'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
'stage_trigger_pulse_%' : 1,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_exposure_time':0.02,
'camera_line_interval':0.000075,
'camera_display_live_subsampling': 2,
'camera_display_snap_subsampling': 1,
'camera_display_acquisition_subsampling': 2,
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM',
'average_frame_rate': 2.5,
}
