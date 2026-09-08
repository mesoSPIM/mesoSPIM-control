'''
Camera configuration: Hamamatsu Orca Lightning (C14120).

Verified against the working config file
config_mesoSPIM-v6-ZMB-exposure20ms(STANDARD)-v1.2.py.
Requires a CoaXPress frame grabber and the DCAM API.
'''
camera = 'HamamatsuOrca'

camera_parameters = {'x_pixels' : 4608,
                     'y_pixels' : 2592,
                     'x_pixel_size_in_microns' : 5.5,
                     'y_pixel_size_in_microns' : 5.5,
                     'subsampling' : [1,2,4],
                     'camera_id' : 0,
                     'sensor_mode' : 12,    # 12 for progressive
                     'defect_correct_mode': 2,
                     #'readout_speed' : 1, # not available for Orca Lightning
                     'trigger_active' : 1,
                     'trigger_mode' : 1, # 1: NORMAL, 6: START
                     'trigger_polarity' : 2, # positive pulse
                     'trigger_source' : 2, # external
                     'high_dynamic_range_mode': 2, # 2: 16-bit mode on Orca Lightning
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

startup = {
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.180, # manually adjusted for Orca Lightning, for the 2x-20x magnification range
'camera_exposure_time' : 0.02,
'camera_line_interval' : 200e-6, # max 200 us for Orca Lightning, manually selected. Hamamatsu-specific parameter
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 3, # affects overall performance! Default value 2. Increase to 4 or 5 if the CPUs are not powerful enough
'average_frame_rate': 5.0,
}
