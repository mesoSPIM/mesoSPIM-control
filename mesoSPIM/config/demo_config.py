'''
mesoSPIM configuration file (two-level format).

The hardware is described once, in the shared files under config/hardware/ and
config/plugins/. This file picks the hardware of *this* microscope and overrides
whatever is specific to *this* user. Copy it, rename it (extension .py), and edit.

Rules:
* everything assigned below the include() call wins over the included values;
* dicts of the same name are merged key-by-key, so several hardware files each
  contribute their part of the `startup` dict;
* only this file may include(): the included files never include each other, so
  there is never more than one level to follow;
* old single-file configs (without include()) keep working unchanged.
  demo_config_format1.py is this very configuration written as one such file.
'''
config_format = 2 # 2 = two-level config (include-based); absent or 1 = legacy single file

include('hardware/cameras/demo_camera.py',
        'hardware/DAQ/demo_daq.py',
        'hardware/stages/demo_stage.py',
        'hardware/lasers/demo_lasers.py',
        'hardware/filterwheels/demo_filterwheel.py',
        'hardware/objectives/demo_zoom.py',
        'hardware/galvos/demo_galvos.py',
        'hardware/ETLs/demo_etl.py',
        'plugins/writers/demo_writers.py',
        'UI/default_ui.py')

'''
Microscope metadata
Stored in acquisition metadata sidecars and does not change mesoSPIM behavior.
Add or remove keys as needed for your microscope.
'''
microscope_parameters = {
            'name': 'Demo mesoSPIM',
            'institution': 'University of Demo',
            'location': 'Demo room',
            'instrument_id': 'DEMO-001',
            'notes': 'Example configuration for demo mode',
            'objective_parameters': {
                        'name': 'Demo objective',
                        'model_number': 'DEMO-001',
                        'magnification': '1x',
                        'numerical_aperture': 0.28,
                        'working_distance_mm': 34,
                        'immersion_medium': 'air',
                        'design_refractive_index': 1.0,
                        'coverglass_thickness_mm': 0.17,
                        },
            'users': {
                        'authorized': ['Doe, John', 'Doe, Jane', 'Chewbacca'],
                        'owner': 'Demo Operator',
                        }
            }

logging_level = 'DEBUG' # 'DEBUG' for ultra-detailed, 'INFO' for general logging level

'''
Personal settings and overrides.
Everything here wins over the hardware files included above.
Make sure that all the file paths exist.
'''
startup.update({
'state' : 'init', # 'init', 'idle' , 'live', 'snap', 'running_script'
'folder' : 'D:/tmp/',
'snap_folder' : 'D:/tmp/',
'file_prefix' : '',
'file_suffix' : '000001',
})

# Examples of overriding a single setting for this user only:
# ui_options['dark_mode'] = False
# camera_parameters['x_pixels'] = 2048
# stage_parameters['y_load_position'] = -8000
# startup.update({'zoom': '1x', 'camera_exposure_time': 0.05})
