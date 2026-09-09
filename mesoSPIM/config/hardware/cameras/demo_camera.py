'''
Camera configuration: demo camera (no hardware).

For the demo camera, only the following options are necessary
(x_pixels and y_pixels can be chosen arbitrarily):

camera_parameters = {'x_pixels' : 1024,
                     'y_pixels' : 1024,
                     'x_pixel_size_in_microns' : 6.5,
                     'y_pixel_size_in_microns' : 6.5,
                     'subsampling' : [1,2,4]}

For real cameras, see the other files in this folder.
'''
camera = 'Demo' # 'Demo', 'HamamatsuOrca', 'Photometrics' or 'PCO'

camera_parameters = {'x_pixels' : 5056,
                     'y_pixels' : 2960,
                     'x_pixel_size_in_microns' : 5,
                     'y_pixel_size_in_microns' : 5,
                     'subsampling' : [1,2,4],
                    }

binning_dict = {'1x1': (1,1), '2x2':(2,2), '4x4':(4,4)}

startup = {
# 'sweeptime' is a DAQ parameter, but in ASLM mode the light-sheet sweep must match the
# camera's rolling-shutter readout (see 'scan_line_delay'/'camera_line_interval') and the
# exposure time, so it belongs to the camera rather than to the DAQ card.
'sweeptime' : 0.2, # demo default
'camera_exposure_time' : 0.02,
'camera_delay_%' : 10,
'camera_pulse_%' : 1,
'camera_binning' : '1x1',
'camera_display_live_subsampling': 2, # un-deprecated for older computers
'camera_display_acquisition_subsampling': 2, # un-deprecated for older computers
'camera_display_temporal_subsampling': 2, # newly added for performance and stability boost
'average_frame_rate': 4.5,
}
