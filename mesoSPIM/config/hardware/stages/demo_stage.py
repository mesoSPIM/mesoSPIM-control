'''
Stage configuration: demo stage (no hardware).

The stage_parameters dictionary defines the general stage configuration, initial positions,
and safety limits. The rotation position defines a XYZ position (in absolute coordinates)
where sample rotation is safe. Additional hardware dictionaries (e.g. pi_parameters,
asi_parameters, see the other files in this folder) define the stage configuration details.
All positions are absolute.

'stage_type' options:
ASI stages: 'TigerASI', 'MS2000ASI'
PI stages: 'PI' or 'PI_1controllerNstages' (equivalent), 'PI_NcontrollersNstages'
Legacy mixed stages: 'PI_rot_and_Galil_xyzf', 'GalilStage', 'PI_f_rot_and_Galil_xyz',
                     'PI_rotz_and_Galil_xyf', 'PI_rotzf_and_Galil_xy'
New flexible mixed stages: 'Mixed' (requires both asi_parameters and pi_parameters with
                     stage_assignment dicts)
Demo mode: 'Demo'
'''
stage_parameters = {'stage_type' : 'Demo',
                    'y_load_position': -6000,
                    'y_unload_position': 6000,
                    'x_center_position': 0, # x-center position for the sample holder. Make sure the sample holder is actually centered at this position relative to the detection objective and light-sheet.
                    'z_center_position': 0, # z-center position for the sample holder. Make sure the sample holder is actually centered at this position relative to the detection objective and light-sheet.
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 50000,
                    'y_min' : -50000,
                    'z_max' : 25000,
                    'z_min' : -25000,
                    'f_max' : 98000,
                    'f_min' : 0,
                    'f_objective_exchange': 2000, # DANGER ZONE: position for the objective exchange, either manually or by the revolver. Set up carefully to avoid collisions! If missing, the objective revolver will rotate in the current f-position.
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }

startup = {
'position' : {'x_pos':0, 'y_pos':1000, 'z_pos':2000, 'f_pos':5000, 'theta_pos':180},
}
