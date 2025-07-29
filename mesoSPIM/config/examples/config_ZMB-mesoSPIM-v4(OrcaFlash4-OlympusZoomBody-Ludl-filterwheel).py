import numpy as np

'''
mesoSPIM configuration file.

Use this file as a starting point to set up all mesoSPIM hardware by replacing the 'Demo' designations
with real hardware one-by-one. Make sure to rename your new configuration file to a different filename
(The extension has to be .py).
'''

ui_options = {'dark_mode' : True, # Dark mode: Renders the UI dark if enabled
              'enable_x_buttons' : True, # Here, specific sets of UI buttons can be disabled   
              'enable_y_buttons' : True, 
              'enable_z_buttons' : True,
              'enable_f_buttons' : True,
              'enable_rotation_buttons' : True,
              'enable_loading_buttons' : True,
			  'window_pos': (400, 100), # position of the main window on the screen, top left corner.
               }
			   
'''
Waveform output for Galvos, ETLs etc.
'''

waveformgeneration = 'NI' # 'DemoWaveFormGeneration' or 'NI'

'''
Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

A standard mesoSPIM configuration uses two cards:

PXI6733 is responsible for the lasers (analog intensity control)
PXI6259 is responsible for the shutters, ETL waveforms and galvo waveforms


'''

acquisition_hardware = {'master_trigger_out_line' : 'PXI6259/port0/line1',
                        'camera_trigger_source' : '/PXI6259/PFI0',
                        'camera_trigger_out_line' : '/PXI6259/ctr0',
                        'galvo_etl_task_line' : 'PXI6259/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI6259/PFI0',
                        'laser_task_line' :  'PXI6733/ao0:3',
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}

'''
Human interface device (Joystick)
'''
sidepanel = 'FarmSimulator' #'Demo' or 'FarmSimulator'

'''
Digital laser enable lines
'''

laser = 'Demo' # 'Demo' or 'NI'

''' The laserdict keys are the laser designation that will be shown
in the user interface '''

laserdict = {'405 nm': 'PXI6733/port0/line2',
             '488 nm': 'PXI6733/port0/line3',
             '561 nm': 'PXI6733/port0/line4',
             '647 nm': 'PXI6733/port0/line5',
             }


'''
Shutter configuration
'''

shutter = 'NI' # 'Demo' or 'NI'
shutterdict = {'shutter_left' : 'PXI6259/port0/line0',
              'shutter_right' : 'PXI6259/port2/line0'}

''' A bit of a hack: Shutteroptions for the GUI '''
shutteroptions = ('Left','Right','Both')

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

For a Hamamatsu Orca Fusion, the following parameters are necessary:

camera_parameters = {'x_pixels' : 2304,
                     'y_pixels' : 2304,
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
                     'exp_mode' : 'Ext Trig Edge Rising', # Lots of options in PyVCAM --> see constants.py
                     'binning' : '1x1',
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 1, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 6, # 10.26 us x factor, a factor = 6 equals 71.82 us
                    }

'''
camera = 'HamamatsuOrca' # 'DemoCamera' or 'HamamatsuOrca' or 'PhotometricsIris15'

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

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

'''
Stage configuration
'''

'''
The stage_parameter dictionary defines the general stage configuration, initial positions,
and safety limits. The rotation position defines a XYZ position (in absolute coordinates)
where sample rotation is safe. Additional hardware dictionaries (e.g. pi_parameters)
define the stage configuration details.

'stage_type'
ASI stages supported, 'stage_type' : 'TigerASI', 'MS2000ASI'
PI stage support, 'stage_type' : 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Mixed stage types, 'stage_type' : 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz', 'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy'
'''

stage_parameters = {'stage_type' : 'PI', # 'PI' or 'DemoStage'
                    'startfocus' : 48000,
                    'y_load_position': 70000,
                    'y_unload_position': 20000,
                    'x_max' : 40000,
                    'x_min' : 5500,
                    'y_max' : 99000,
                    'y_min' : 0,
                    'z_max' : 40000,
                    'z_min' : 5000,
                    'f_max' : 99000,
                    'f_min' : 0,
                    'theta_max' : 999,
                    'theta_min' : -999,
                    'x_rot_position': 22000,
                    'y_rot_position': 40000,
                    'z_rot_position': 22000,
                    }

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118015797'),
                 }

'''
Depending on the stage hardware, further dictionaries define further details of the stage configuration

For a standard mesoSPIM V4 with PI stages, the following pi_parameters are necessary (replace the
serialnumber with the one of your controller):

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118015797'),
                 }

For a standard mesoSPIM V5 with PI stages, the following pi_parameters are necessary (replace the
serialnumber with the one of your controller):

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118015799'),
'''

'''
Filterwheel configuration
'''

'''
For a DemoFilterWheel, no COMport needs to be specified, for a Ludl Filterwheel,
a valid COMport is necessary.
'''
filterwheel_parameters = {'filterwheel_type' : 'Ludl',
                          'COMport' : 'COM22'}

# Ludl marking 10 = position 0

'''

A Ludl double filter wheel can be
'''

filterdict = {'Empty-Alignment' : 0,
              '405-488-561-640-Quadrupleblock' : 1,
              '508 520-35' : 2,
              '515LP' : 3,
              '561LP' : 4,
              '594LP' : 5,
              '590' : 6,
              }

'''
Zoom configuration
'''

'''
For the DemoZoom, servo_id, COMport and baudrate do not matter. For a Dynamixel zoom,
these values have to be there
'''
zoom_parameters = {'zoom_type' : 'Dynamixel',
                   'servo_id' :  1,
                   'COMport' : 'COM24',
                   'baudrate' : 1000000}

'''
The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface.
'''

zoomdict = {'0.63x' : 3423,
            '0.8x' : 3071,
            '1x' : 2707,
            '1.25x' : 2389,
            '1.6x' : 2047,
            '2x' : 1706,
            '2.5x' : 1354,
            '3.2x' : 967,
            '4x' : 637,
            '5x' : 318,
            '6.3x' : 0}
'''
Pixelsize in micron
'''
pixelsize = {'0.63x' : 10.52,
            '0.8x' : 8.23,
            '1x' : 6.55,
            '1.25x' : 5.26,
            '1.6x' : 4.08,
            '2x' : 3.26,
            '2.5x' : 2.6,
            '3.2x' : 2.03,
            '4x' : 1.60,
            '5x' : 1.27,
            '6.3x' : 1.03}

'''
 HDF5 parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
hdf5 = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
		'transpose_xy': False # flip it if X-Y order in BigStitcher is incorrect
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
'sweeptime' : 0.2,
'position' : {'x_pos':0,'y_pos':0,'z_pos':0,'f_pos':0,'theta_pos':0},
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters.csv',
'filepath' : '/tmp/file.raw',
'folder' : '/tmp/',
'snap_folder' : 'D:/Data/mesoSPIM_snapped_images',
'file_prefix' : '',
'file_suffix' : '000001',
'zoom' : '1x',
'pixelsize' : 6.55,
'laser' : '488 nm',
'max_laser_voltage':10,
'intensity' : 10,
'shutterstate':False, # Is the shutter open or not?
'shutterconfig':'Right', # Can be "Left", "Right","Both","Interleaved"
'laser_interleaving':False,
'filter' : '405-488-561-640-Quadrupleblock',
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
'camera_line_interval':0.000075,
'camera_display_live_subsampling': 2,
'camera_display_snap_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM',
'average_frame_rate': 4.8,
}
