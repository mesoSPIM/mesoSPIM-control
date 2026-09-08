'''
Camera configuration: Hamamatsu Orca Flash 4.0 V2 / V3.
'''
camera = 'HamamatsuOrca'

camera_parameters = {'x_pixels' : 2048,
                     'y_pixels' : 2048,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4],
                     'camera_id' : 0,
                     'sensor_mode' : 12,    # 12 for progressive
                     'defect_correct_mode': 2,
                     'readout_speed' : 1,
                     'trigger_active' : 1,
                     'trigger_mode' : 1, # it is unclear if this is the external lightsheeet mode - how to check this?
                     'trigger_polarity' : 2, # positive pulse
                     'trigger_source' : 2, # external
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

startup = {
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.2, # value used by the Orca Flash 4.0 rigs (config_H45_standard.py and others)
'camera_exposure_time' : 0.02,
'camera_line_interval' : 0.000075, # Hamamatsu-specific, required only for this camera
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 2,
'average_frame_rate': 4.5,
}
