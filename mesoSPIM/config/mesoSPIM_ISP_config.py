import numpy as np

'''
mesoSPIM configuration file.

Use this file as a starting point to set up all mesoSPIM hardware by replacing the 'Demo' designations
with real hardware one-by-one. Make sure to rename your new configuration file to a different filename
(The extension has to be .py).
'''


'''
Waveform output for Galvos, ETLs etc.
'''
waveformgeneration = "NI" #  'DemoWaveFormGeneration' or 'NI'


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
                        'laser_task_line' :  'PXI6733/ao0:7',
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}


'''
Human interface device (Joystick)
'''
sidepanel = 'FarmSimulator' #  'Demo' #'Demo' or 'FarmSimulator'


'''
Digital laser enable lines
'''
laser = "NI" #  'Demo' or 'NI'


''' The laserdict keys are the laser designation that will be shown
in the user interface '''
'''
Assignment of the analog outputs of the Laser card to the channels
The Empty slots are placeholders (and mandatory to reach 8 entries).
'''
laserdict = {'488 nm': 'PXI6733/port0/line2',
             '561 nm': 'PXI6733/port0/line3',
             '640 nm': 'PXI6733/port0/line4'}
"""488 nm : 'PXI6259/ao0"""
laser_designation = {'488 nm' : 0,
                     '561 nm' : 1,
                     '640 nm' : 2,
                     'Empty 0' : 3,
                     'Empty 1' : 4,
                     'Empty 2' : 5,
                     'Empty 3' : 6,
                     'Empty 4' : 7
                     }


'''
Assignment of the galvos and ETLs to the 6259 AO channels.
'''
galvo_etl_designation = {'Galvo-L' : 0,
                         'Galvo-R' : 1,
                         'ETL-L' : 2,
                         'ETL-R' : 3,
                         }

'''
Shutter configuration
'''
shutter = "NI" #  'Demo' or 'NI'
shutterdict = {'shutter_left' : 'PXI6259/port0/line2',
               'shutter_right' : 'PXI6259/port0/line3'}


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
'''
camera = "HamamatsuOrca" # 'DemoCamera' or 'HamamatsuOrca' or 'PhotometricsIris15'
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

The stage_parameter dictionary defines the general stage configuration, initial positions,
and safety limits. The rotation position defines a XYZ position (in absolute coordinates)
where sample rotation is safe. Additional hardware dictionaries (e.g. pi_parameters)
define the stage configuration details.
'''
stage_parameters = {'stage_type' : 'PI_xyzf', #  'DemoStage' or 'PI' or other configs found in mesoSPIM_serial.py
                    'startfocus' : 0,
                    'y_load_position': 97000,
                    'y_unload_position': 35000,
                    'x_max' : 35000,
                    'x_min' : 15000,
                    'y_max' : 102000,
                    'y_min' : 0,
                    'z_max' : 51000,
                    'z_min' : 20000,
                    'f_max' : 10000,
                    'f_min' : -10000,
                    'theta_max' : 999,
                    'theta_min' : -999,
                    'x_rot_position': 0,
                    'y_rot_position': -121000,
                    'z_rot_position': 66000,
                    }


'''
Depending on the stage hardware, further dictionaries define further details of the stage configuration
For a standard mesoSPIM V5 with PI stages, the following pi_parameters are necessary (replace the
serialnumber with the one of your controller):

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118015799'),
'''
'''
pi_parameters = {'stage_x' : ('L-509.20SD00'),
                 'serialnum_x' : ('0020550154'),
                 'stage_y' : ('L-509.40SD00'),
                 'serialnum_y' : ('0020550158'),
                 'stage_z' : ('L-509.20SD00'),
                 'serialnum_z' : ('0020550156'),
                 'controllername' : ('C-663'),
                 'refmode' : ('FRF'),
                 'stage_f' : ('MESOSPIM_FOCUS'),
                 'serialnum_f' : ('0021550121')                 
                 }
'''
pi_parameters = {'stage_names': ('x', 'y', 'z', 'r', 'f'),
                 'stages': ('L-509.20SD00', 'L-509.40SD00', 'L-509.20SD00', None, 'MESOSPIM_FOCUS'),
                 'controller': ('C-663', 'C-663', 'C-663', None, 'C-663'),
                 'serialnum': ('0020550154', '0020550158', '0020550156', None, '0021550121'),
                 'refmode': ('FRF', 'FRF', 'FRF', None, 'RON')
                 }


'''
Filterwheel configuration

For a DemoFilterWheel, no COMport needs to be specified, for a Ludl Filterwheel,
a valid COMport is necessary.

filterwheel_parameters = {'filterwheel_type' : 'DemoFilterWheel', # 'DemoFilterWheel' or 'Ludl'
                          'COMport' : 'COM53'}

# Ludl marking 10 = position 0

A Ludl double filter wheel can be

              '405-488-647-Tripleblock' : 1,
              '405-488-561-640-Quadrupleblock' : 2,
              '464 482-35' : 3,
              '508 520-35' : 4,
              '515LP' : 5,
              '529 542-27' : 6,
              '561LP' : 7,
              '594LP' : 8,
              '417 447-60' : 9}
'''
filterwheel_parameters = {'filterwheel_type' : 'DemoFilterWheel'}
filterdict = {'Empty-Alignment' : 0}


'''
Zoom configuration

For the DemoZoom, servo_id, COMport and baudrate do not matter. For a Dynamixel zoom,
these values have to be there

zoom_parameters = {'zoom_type' : 'DemoZoom', # 'DemoZoom' or 'Dynamixel'
                   'servo_id' :  4,
                   'COMport' : 'COM38',
                   'baudrate' : 1000000}

The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface.

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

Pixelsize in micron
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
zoom_parameters = {'zoom_type' : 'DemoZoom'}
zoomdict = {'1x' : 30}
pixelsize = {'1x' : 6.55}



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
'ETL_cfg_file' : 'config/etl_parameters/ETL-parameters_mesoSPIM_ISP.csv',
'filepath' : 'C:/Users/Public/Documents/mesoSPIM Images/junk.raw',
'folder' : 'C:/Users/Public/Documents/mesoSPIM Images/',
'snap_folder' : 'C:/Users/Public/Documents/mesoSPIM Images/',
'file_prefix' : '',
'file_suffix' : '000001',
'zoom' : '1x',
'pixelsize' : 6.55,
'laser' : '488 nm',
'max_laser_voltage' : 5,
'intensity' : 5,
'shutterstate' : False, # Is the shutter open or not?
'shutterconfig' : 'Both', # Can be "Left", "Right","Both","Interleaved"
'laser_interleaving' : False,
'filter' : 'Empty-Alignment', #  '405-488-561-640-Quadrupleblock',
'etl_l_delay_%' : 2.5,
'etl_l_ramp_rising_%' : 85,
'etl_l_ramp_falling_%' : 2.5,
'etl_l_amplitude' : 0.7,
'etl_l_offset' : 2.50,
'etl_r_delay_%' : 2.5,
'etl_r_ramp_rising_%' : 2.5,
'etl_r_ramp_falling_%' : 85,
'etl_r_amplitude' : 0.7,
'etl_r_offset' : 2.50,
'galvo_l_frequency' : 99.9,
'galvo_l_amplitude' : 0.5,
'galvo_l_offset' : 0,
'galvo_l_duty_cycle' : 50,
'galvo_l_phase' : np.pi/2,
'galvo_r_frequency' : 99.9,
'galvo_r_amplitude' : 0.5,
'galvo_r_offset' : 0,
'galvo_r_duty_cycle' : 50,
'galvo_r_phase' : np.pi/2,
'laser_l_delay_%' : 1,
'laser_l_pulse_%' : 87,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 1,
'laser_r_pulse_%' : 87,
'laser_r_max_amplitude_%' : 100,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_exposure_time':0.01,
'camera_line_interval':0.000075,
'camera_display_live_subsampling': 1,
'camera_display_snap_subsampling': 1,
'camera_display_acquisition_subsampling': 2,
'camera_binning':'1x1',
'camera_sensor_mode':'ASLM',
'average_frame_rate': 4.969,
}
