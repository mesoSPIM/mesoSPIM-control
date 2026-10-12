"""
mesoSPIM user configuration, converted from the single-file format.

The microscope itself is described in hardware/config_BT_STANDARD_ZMB_exp20ms-wf267_hw.py: camera, stages, lasers, filters,
objectives, DAQ lines, writer defaults. Change that file when the instrument changes.

Here, keep only what differs for your session. Anything assigned below the include()
line overrides the hardware file, e.g.:

    startup['camera_exposure_time'] = 0.05
    filterdict['Empty-Alignment'] = 0
"""
config_format = 2

include('hardware/config_BT_STANDARD_ZMB_exp20ms-wf267_hw.py')

camera_parameters['scan_line_delay'] = 1 # 10.26 us x factor, a factor = 6 equals 71.82 us

startup.update({
    'folder': 'F:\\TEMP',
    'sweeptime' : 0.083,
    'etl_l_delay_%' : 0,
    'etl_l_ramp_rising_%' : 95, # 94,
    'etl_l_ramp_falling_%' : 5, #2,
    'etl_r_delay_%' : 0,
    'etl_r_ramp_rising_%' : 5, #0,
    'etl_r_ramp_falling_%' : 95,
    'galvo_l_frequency' : 100,
    'laser_l_delay_%' : 0,
    'laser_l_pulse_%' : 95,
    'laser_l_max_amplitude_%' : 100,
    'laser_r_delay_%' : 0,
    'laser_r_pulse_%' : 95,
    'laser_r_max_amplitude_%' : 100,
    'camera_delay_%' : 5,
    'camera_exposure_time':0.010,
    'camera_display_temporal_subsampling': 10, # newly added for performance and stability boost
    'average_frame_rate': 8.5,    
})