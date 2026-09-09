'''
mesoSPIM configuration file (two-level format), converted from
config_benchtop-cDAQ.py.

The hardware is described in the shared files included below; everything
assigned after the include() call overrides them. See config/hardware/README.md.
'''
config_format = 2
include('hardware/cameras/photometrics_iris15.py',
        'hardware/DAQ/cDAQ_benchtop.py',
        'hardware/stages/TigerASI.py',
        'hardware/lasers/cDAQ_lasers.py',
        'hardware/filterwheels/ZWO_EFW.py',
        'hardware/objectives/benchtop_manual_objectives.py',
        'hardware/ETLs/demo_etl.py',
        'plugins/writers/production_writers.py',
        'UI/default_ui.py')

# NOTE startup['camera_sensor_mode'] dropped, the software does not read it any more
# NOTE startup['camera_display_snap_subsampling'] dropped, the software does not read it any more
# NOTE startup['filepath'] dropped, the software does not read it any more
# NOTE startup['stage_trigger_delay_%'] dropped, the software does not read it any more
# NOTE startup['stage_trigger_pulse_%'] dropped, the software does not read it any more
# NOTE camera_parameters['binning'] dropped, the software does not read it any more
# NOTE MP_OME_Zarr_Writer['async_finalize'] dropped, the software does not read it any more
# NOTE filterwheel_parameters['COMport'] dropped, the 'ZWOPlugin' driver does not use it
# NOTE filterwheel_parameters['baudrate'] dropped, the 'ZWOPlugin' driver does not use it
# NOTE filterwheel_parameters['servo_id'] dropped, the 'ZWOPlugin' driver does not use it
# NOTE zoom_parameters['COMport'] dropped, the 'Demo' driver does not use it
# NOTE zoom_parameters['baudrate'] dropped, the 'Demo' driver does not use it
# NOTE zoom_parameters['servo_id'] dropped, the 'Demo' driver does not use it
# NOTE startup['camera_line_interval'] dropped, the 'Photometrics' camera does not use it
# NOTE pixelsize['7.5x'] 0.5666666666666667 written as 0.56667
# NOTE startup['galvo_l_offset'] -0.17999999999999994 written as -0.18
# NOTE ui_options gains ['enable_f_zero_button', 'window_pos'] from the shared files
# NOTE stage_parameters gains ['f_objective_exchange', 'x_center_position', 'z_center_position'] from the shared files
# NOTE asi_parameters['encoder_conversion'] written out to keep the axis order of the old config, which the shared file lists as ['X', 'Y', 'Z', 'T', 'V']
# NOTE asi_parameters['speed'] written out to keep the axis order of the old config, which the shared file lists as ['X', 'Y', 'Z', 'T', 'V']
# NOTE asi_parameters['stage_assignment'] written out to keep the axis order of the old config, which the shared file lists as ['x', 'f', 'z', 'theta', 'y']
# NOTE startup gains ['camera_display_temporal_subsampling'] from the shared files

# --- settings of this microscope/user, overriding the files included above ---
logging_level = 'DEBUG'
ui_options.update({'flip_XYZFT_button_polarity': (True, True, False, False, False),
 'button_sleep_ms_xyzft': (0, 0, 0, 0, 0)})

stage_parameters.update({'y_load_position': -45000,
 'y_unload_position': -75000,
 'x_max': 51000,
 'x_min': -46000,
 'y_max': 160000,
 'y_min': -160000,
 'z_max': 99000,
 'z_min': -99000,
 'f_max': 99000,
 'f_min': -8500})

asi_parameters.update({'COMport': 'COM23',
 'stage_assignment': {'y': 'V', 'z': 'Z', 'theta': 'T', 'x': 'X', 'f': 'Y'},
 'encoder_conversion': {'V': 10.0, 'Z': 10.0, 'T': 1000.0, 'X': 10.0, 'Y': 10.0},
 'speed': {'V': 3.0, 'Z': 3.0, 'T': 30.0, 'X': 3.0, 'Y': 3.0},
 'stage_trigger_source': '/cDAQ1Mod1/PFI4',
 'stage_trigger_out_line': '/cDAQ1Mod1/ctr2',
 'ttl_cards': (2, 3)})

filterwheel_parameters.update({'filterwheel_type': 'ZWOPlugin'})

zoomdict.update({'25x': 10})

pixelsize.update({'25x': 0.17})

OME_Zarr_Writer.update({'base_chunks': (32, 1264, 1480)})

MP_OME_Zarr_Writer.update({'base_chunks': (32, 1264, 1480)})

scale_galvo_amp_with_zoom = True
startup.update({'state': 'init',
 'sweeptime': 0.267,
 'ETL_cfg_file': 'config/etl_parameters/ETL-parameters-BT-DBE.csv',
 'folder': 'F:/Test/',
 'snap_folder': 'F:/Test/',
 'file_prefix': '',
 'file_suffix': '000001',
 'shutterconfig': 'Left',
 'etl_l_delay_%': 5.0,
 'etl_l_ramp_rising_%': 90.0,
 'etl_l_ramp_falling_%': 5.0,
 'galvo_l_frequency': 99.9,
 'galvo_l_amplitude': 0.8,
 'galvo_l_offset': -0.18,
 'galvo_l_duty_cycle': 50,
 'galvo_l_phase': 0.45,
 'galvo_r_frequency': 99.9,
 'galvo_r_amplitude': 0.8,
 'galvo_r_offset': 0.06,
 'galvo_r_duty_cycle': 50,
 'galvo_r_phase': 0.45,
 'average_frame_rate': 2.5})
