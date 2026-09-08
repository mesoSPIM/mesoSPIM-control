'''
Camera configuration: Photometrics Prime BSI Express.
'''
camera = 'Photometrics'

camera_parameters = {'x_pixels' : 2048,
                     'y_pixels' : 2048,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4],
                     'speed_table_index': 1, # 1 for 100 MHz
                     'exp_mode' : 'Edge Trigger', # Lots of options in PyVCAM --> see constants.py
                     'readout_port': 0,
                     'gain_index': 1, # Enable HDR mode
                     'exp_out_mode': 4, # 4: line out
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 0, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 7, # 11.2 us x factor, a factor = 3 equals 33.6 us
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

startup = {
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.2, # NOT from a rig config - no BSI Express config exists here; tune for your setup
'camera_exposure_time' : 0.02,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 2,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 2,
'average_frame_rate': 4.5,
}
