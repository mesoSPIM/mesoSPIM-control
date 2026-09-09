'''
mesoSPIM configuration file (two-level format), converted from
config_BT_STANDARD_ZMB_exp20ms-wf267-3FPS.py.

The hardware is described in the shared files included below; everything
assigned after the include() call overrides them. See config/hardware/README.md.
'''
config_format = 2
include('hardware/cameras/photometrics_iris15.py',
        'hardware/DAQ/NI_benchtop_PXI6733.py',
        'hardware/stages/TigerASI.py',
        'hardware/lasers/benchtop_PXI6733_lasers.py',
        'hardware/filterwheels/ZWO_EFW.py',
        'hardware/objectives/benchtop_manual_objectives.py',
        'hardware/galvos/demo_galvos.py',
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
# NOTE filterwheel_parameters['COMport'] dropped, the 'ZWO' driver does not use it
# NOTE filterwheel_parameters['baudrate'] dropped, the 'ZWO' driver does not use it
# NOTE filterwheel_parameters['servo_id'] dropped, the 'ZWO' driver does not use it
# NOTE zoom_parameters['COMport'] dropped, the 'Demo' driver does not use it
# NOTE zoom_parameters['baudrate'] dropped, the 'Demo' driver does not use it
# NOTE zoom_parameters['servo_id'] dropped, the 'Demo' driver does not use it
# NOTE startup['camera_line_interval'] dropped, the 'Photometrics' camera does not use it
# NOTE pixelsize['7.5x'] 0.5666666666666667 written as 0.56667
# NOTE startup['galvo_l_phase'] 0.4487989505128276 written as 0.4488
# NOTE startup['galvo_r_phase'] 0.4487989505128276 written as 0.4488
# NOTE ui_options gains ['enable_f_zero_button', 'window_pos'] from the shared files
# NOTE stage_parameters gains ['f_objective_exchange'] from the shared files
# NOTE filterdict replaced as a whole, the shared file also offers ['535/22 Brightline', '595/31 Brightline']
# NOTE startup gains ['camera_display_temporal_subsampling'] from the shared files

# --- settings of this microscope/user, overriding the files included above ---
logging_level = 'DEBUG'
ui_options.update({'enable_loading_buttons': False,
 'flip_XYZFT_button_polarity': (True, True, False, False, False),
 'button_sleep_ms_xyzft': (300, 300, 300, 0, 0)})

stage_parameters.update({'y_load_position': 10000,
 'y_unload_position': 0,
 'x_center_position': -3377,
 'x_max': 26000,
 'x_min': -22000,
 'y_max': 80000,
 'y_min': 0,
 'z_max': 50000,
 'z_min': -55000,
 'f_max': 50000,
 'f_min': -55000})

filterdict = {'Empty': 0,
 '405-488-561-640-Quadrupleblock': 1,
 '488LB RazorEdge': 2,
 '520/35 BrightLine': 3,
 '595/31 BrightLine': 4}

OME_Zarr_Writer.update({'base_chunks': (128, 1264, 1480), 'target_chunks': (128, 1264, 1480), 'async_finalize': False})

MP_OME_Zarr_Writer.update({'base_chunks': (128, 1264, 1480), 'target_chunks': (128, 1264, 1480)})

startup.update({'state': 'init',
 'ETL_cfg_file': 'config/etl_parameters/ETL-parameters-benchtop.csv',
 'folder': 'F:/Test/',
 'snap_folder': 'X:/',
 'file_prefix': '',
 'file_suffix': '000001',
 'shutterconfig': 'Left',
 'etl_l_delay_%': 5,
 'etl_l_ramp_rising_%': 90,
 'etl_l_ramp_falling_%': 5,
 'galvo_l_amplitude': 0.83,
 'galvo_l_phase': 0.4488,
 'galvo_r_amplitude': 0.83,
 'galvo_r_phase': 0.4488})
