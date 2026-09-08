'''
User interface options.

Override single keys in your own config file after the include(), e.g.
    ui_options['dark_mode'] = False
'''
ui_options = {'dark_mode' : True, # Dark mode: Renders the UI dark if enabled
              'enable_x_buttons' : True, # Here, specific sets of UI buttons can be disabled
              'enable_y_buttons' : True,
              'enable_z_buttons' : True,
              'enable_f_buttons' : True,
              'enable_f_zero_button' : True, # set to False if objective change requires F-stage movement (e.g. mesoSPIM v6-Revolver), for safety reasons
              'enable_rotation_buttons' : True,
              'enable_loading_buttons' : True,
              'flip_XYZFT_button_polarity': (True, False, False, False, False), # flip the polarity of the stage buttons (X, Y, Z, F, Theta)
              'button_sleep_ms_xyzft' : (250, 0, 250, 0, 0), # step-motion buttons disabled for N ms after click. Prevents stage overshooting outside of safe limits, for slow stages.
              'window_pos': (0, 0), # position of the main window on the screen, top left corner.
              'usb_webcam_ID': 0, # open USB web-camera (if available): None,  0 (first cam), 1 (second cam), ...
              'flip_auto_LR_illumination': False, # flip the polarity of the "Auto L/R illumination" button in Acquisition Manager
               }

sidepanel = 'Demo' #'Demo' or 'FarmSimulator', deprecated
