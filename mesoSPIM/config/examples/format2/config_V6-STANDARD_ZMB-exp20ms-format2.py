'''
mesoSPIM configuration file (two-level format), converted from
config_mesoSPIM-v6-ZMB-exposure20ms(STANDARD)-v1.2.py.

The hardware is described in the shared files included below; everything
assigned after the include() call overrides them. See config/hardware/README.md.
'''
config_format = 2
include('hardware/cameras/hamamatsu_orca_lightning.py',
        'hardware/DAQ/NI_PXI6259_PXI6733.py',
        'hardware/stages/PI_C884_xyzft.py',
        'hardware/lasers/V5_PXI6733_lasers.py',
        'hardware/filterwheels/ZWO_EFW.py',
        'hardware/galvos/demo_galvos.py',
        'plugins/writers/production_writers.py',
        'UI/default_ui.py')

# NOTE startup['camera_sensor_mode'] dropped, the software does not read it any more
# NOTE startup['camera_display_snap_subsampling'] dropped, the software does not read it any more
# NOTE startup['filepath'] dropped, the software does not read it any more
# NOTE camera_parameters['binning'] dropped, the software does not read it any more
# NOTE MP_OME_Zarr_Writer['async_finalize'] dropped, the software does not read it any more
# NOTE filterwheel_parameters['COMport'] dropped, the 'ZWO' driver does not use it
# NOTE filterwheel_parameters['baudrate'] dropped, the 'ZWO' driver does not use it
# NOTE filterwheel_parameters['servo_id'] dropped, the 'ZWO' driver does not use it
# NOTE zoom_parameters['servo_id'] dropped, the 'Mitu' driver does not use it
# NOTE pixelsize['7.5x'] 0.7333333333333333 written as 0.73333
# NOTE startup['galvo_l_phase'] 1.5707963267948966 written as 1.5708
# NOTE startup['galvo_r_phase'] 1.5707963267948966 written as 1.5708
# NOTE ui_options gains ['flip_auto_LR_illumination'] from the shared files
# NOTE laserdict replaced as a whole, the shared file also offers ['638 nm']
# NOTE filterdict replaced as a whole, the shared file also offers ['535/22 Brightline', '595/31 Brightline']
# NOTE laser_blanking comes from the shared files, the old config had no such setting
# NOTE shutterswitch comes from the shared files, the old config had no such setting

# --- settings of this microscope/user, overriding the files included above ---
logging_level = 'INFO'
ui_options.update({'flip_XYZFT_button_polarity': (True, True, True, True, False),
 'button_sleep_ms_xyzft': (400, 0, 400, 0, 0),
 'window_pos': (400, 100)})

laser = 'Demo'
laserdict = {'405 nm': 'PXI6733/port0/line2',
 '488 nm': 'PXI6733/port0/line3',
 '561 nm': 'PXI6733/port0/line4',
 '647 nm': 'PXI6733/port0/line5'}

shutteroptions = ('Left', 'Right', 'Both')
stage_parameters.update({'startfocus': 48000,
 'y_load_position': 35000,
 'y_unload_position': 1500,
 'x_max': 40000,
 'x_min': 5500,
 'y_max': 90000,
 'y_min': 0,
 'z_max': 40000,
 'z_min': 5000,
 'f_max': 82000,
 'x_center_position': 24000,
 'z_center_position': 27000})

pi_parameters.update({'stages': ('M-112K033', 'L-406.40DG10', 'M-112K033', 'M-116.DG', 'M-406.4PD', 'NOSTAGE'),
 'serialnum': '118015797'})

filterdict = {'Empty': 0, '405-488-561-640-Quadrupleblock': 1, '520/35': 2, 'Empty-1': 3, '590/36': 4}

zoom_parameters = {'zoom_type': 'Mitu', 'COMport': 'COM17', 'baudrate': 9600}

zoomdict = {'2x': 'A', '5x': 'B', '7.5x': 'C', '10x': 'D', '20x_custom(t25)': 'E'}

pixelsize = {'2x': 2.75, '5x': 1.1, '7.5x': 0.73333, '10x': 0.55, '20x_custom(t25)': 0.275}

OME_Zarr_Writer.update({'base_chunks': (128, 1152, 648), 'target_chunks': (128, 288, 162)})

MP_OME_Zarr_Writer.update({'base_chunks': (128, 1152, 648), 'target_chunks': (128, 288, 162)})

startup.update({'state': 'init',
 'ETL_cfg_file': 'config/etl_parameters/ETL-parameters-upgrade2023.csv',
 'folder': '/tmp/',
 'snap_folder': 'D:/Data/mesoSPIM_snapped_images',
 'file_prefix': '',
 'file_suffix': '000001',
 'zoom': '2x',
 'pixelsize': 5.5,
 'intensity': 15,
 'filter': '405-488-561-640-Quadrupleblock',
 'etl_l_delay_%': 5,
 'etl_l_ramp_rising_%': 90,
 'etl_l_ramp_falling_%': 5,
 'etl_l_amplitude': 0.1,
 'etl_l_offset': 2.5,
 'etl_r_delay_%': 2.5,
 'etl_r_ramp_rising_%': 5,
 'etl_r_ramp_falling_%': 85,
 'etl_r_amplitude': 0.1,
 'etl_r_offset': 2.5,
 'galvo_l_amplitude': 2.0,
 'galvo_l_offset': 0.13,
 'galvo_r_amplitude': 2.0,
 'galvo_r_offset': 0.07})
