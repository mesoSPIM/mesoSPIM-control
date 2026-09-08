'''
Camera configuration: Teledyne Photometrics Retiga E9.

Verified against the working config files
examples_private/CBI_PhotometricsRetigaE9_4X_benchtop-fast-v2(11FPS).py
(values below) and ...-v1.py (slower variant, alternatives noted in comments).
Requires PVCAM + PVCAM-SDK + PyVCAM.
'''
camera = 'Photometrics'

camera_parameters = {'x_pixels' : 3000,
                     'y_pixels' : 3000,
                     'x_pixel_size_in_microns' : 3.76,
                     'y_pixel_size_in_microns' : 3.76,
                     'subsampling' : [1,2,4],
                     'speed_table_index': 0,
                     'exp_mode' : 'Edge Trigger', # Lots of options in PyVCAM --> see constants.py
                     'readout_port': 0,
                     'gain_index': 3, # Enable HDR mode
                     'exp_out_mode': 4, # 4: line out
                     'scan_mode' : 1, # Scan mode options: {'Auto': 0, 'Line Delay': 1, 'Scan Width': 2}
                     'scan_direction' : 0, # Scan direction options: {'Down': 0, 'Up': 1, 'Down/Up Alternate': 2}
                     'scan_line_delay' : 0, # 1 in the slower v1 config
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

startup = {
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.0770, # fast v2 config (11 FPS); the slower v1 config uses 0.086
'camera_exposure_time' : 0.005, # 0.01 in the slower v1 config
'camera_delay_%' : 0, # 10 in the slower v1 config
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 1,
'camera_display_acquisition_subsampling': 2,
'camera_display_temporal_subsampling': 5, # affects overall performance! Lower it if the CPUs can keep up
'average_frame_rate': 8,
}
