'''
mesoSPIM configuration file (two-level format), converted from
config_BT_STANDARD_ZMB_exp20ms-wf267-3FPS.py.

The hardware is described in the shared files included below; everything
assigned after the include() call overrides them. See config/hardware/README.md.
'''
config_format = 2
include('hardware/cameras/photometrics_iris15.py',
        'hardware/DAQ/NI_benchtop_PXI1Slot4.py',
        'hardware/stages/TigerASI.py',
        'hardware/lasers/demo_lasers.py',
        'hardware/filterwheels/ZWO_EFW.py',
        'hardware/objectives/demo_zoom.py',
        'hardware/galvos/demo_galvos.py',
        'hardware/ETLs/demo_etl.py',
        'plugins/writers/default_writers.py',
        'UI/default_ui.py')

# NOTE startup['camera_sensor_mode'] dropped, the software does not read it any more
# NOTE startup['camera_display_snap_subsampling'] dropped, the software does not read it any more
# NOTE startup['filepath'] dropped, the software does not read it any more
# NOTE startup['stage_trigger_delay_%'] dropped, the software does not read it any more
# NOTE startup['stage_trigger_pulse_%'] dropped, the software does not read it any more
# NOTE camera_parameters['binning'] dropped, the software does not read it any more
# NOTE ui_options gains ['enable_f_zero_button', 'window_pos'] from the shared files
# NOTE stage_parameters gains ['f_objective_exchange'] from the shared files
# NOTE filterdict replaced as a whole, the shared file also offers ['535/22 Brightline', '595/31 Brightline']
# NOTE zoomdict replaced as a whole, the shared file also offers ['1x', '4x Olympus', '5x Mitutoyo']
# NOTE pixelsize replaced as a whole, the shared file also offers ['1x', '4x Olympus', '5x Mitutoyo']
# NOTE startup gains ['camera_display_temporal_subsampling'] from the shared files

# --- settings of this microscope/user, overriding the files included above ---
logging_level = 'DEBUG'
plugins = {'path_list': ['../src/plugins/ImageWriters', 'C:/a/different/plugin/location'],
 'first_image_writer': 'MP_OME_Zarr_Writer'}
ui_options.update({'enable_loading_buttons': False,
 'flip_XYZFT_button_polarity': (True, True, False, False, False),
 'button_sleep_ms_xyzft': (300, 300, 300, 0, 0)})
laser = 'NI'
shutter = 'NI'
shutterdict.update({'shutter_left': '/PXI1Slot4/port0/line6', 'shutter_right': '/PXI1Slot4/port0/line1'})
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
filterwheel_parameters.update({'COMport': 'COM31', 'baudrate': 115200, 'servo_id': 1})
filterdict = {'Empty': 0,
 '405-488-561-640-Quadrupleblock': 1,
 '488LB RazorEdge': 2,
 '520/35 BrightLine': 3,
 '595/31 BrightLine': 4}
zoom_parameters.update({'servo_id': 1, 'COMport': 'COM9', 'baudrate': 115200})
zoomdict = {'2x': 4, '5x': 6, '7.5x': 7, '10x': 8, '20x': 9}
pixelsize = {'2x': 2.125, '5x': 0.85, '7.5x': 0.5666666666666667, '10x': 0.425, '20x': 0.2125}
OME_Zarr_Writer.update({'base_chunks': (128, 1264, 1480), 'target_chunks': (128, 1264, 1480), 'async_finalize': False})
MP_OME_Zarr_Writer.update({'base_chunks': (128, 1264, 1480), 'target_chunks': (128, 1264, 1480), 'ring_buffer_size': 512})
startup.update({'state': 'init',
 'ETL_cfg_file': 'config/etl_parameters/ETL-parameters-benchtop.csv',
 'folder': 'F:/Test/',
 'snap_folder': 'X:/',
 'file_prefix': '',
 'file_suffix': '000001',
 'zoom': '5x',
 'pixelsize': 0.85,
 'shutterconfig': 'Left',
 'etl_l_delay_%': 5,
 'etl_l_ramp_rising_%': 90,
 'etl_l_ramp_falling_%': 5,
 'galvo_l_amplitude': 0.83,
 'galvo_l_phase': 0.4487989505128276,
 'galvo_r_amplitude': 0.83,
 'galvo_r_phase': 0.4487989505128276,
 'camera_line_interval': 7.5e-05})
