'''
Stage configuration: mixed PI + Galil (mesoSPIM H45).

Rotation (theta) and z run on a PI C-884 controller, while x, y and f run on a
Galil controller reached over Ethernet. From config_H45_standard.py,
examples/format1(legacy)/config_H45-2026-PFI0-direct-v1.2.py and
examples/format1(legacy)/config_HIFO-H45-PFI0-direct-connection.py.

TEMPLATE: 'serialnum', the Galil 'port' (IP address) and the travel limits must
be adjusted to your instrument before use.

WARNING: this stage type performs a reference z movement at startup (see
stage_referencing_check() in mesoSPIM_Control.py). The software asks you to
move the XYZ stage to a position where that movement is safe.

'velocity' maps PI axis number -> velocity; here axis 1 is theta, axis 2 is z.
'*_encodercounts_per_um' converts Galil encoder counts to micrometers.
'''
stage_parameters = {'stage_type' : 'PI_rotz_and_Galil_xyf',
                    'startfocus' : 40000,
                    'y_load_position': -6000,
                    'y_unload_position': 6000,
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 50000,
                    'y_min' : -50000,
                    'z_max' : 25000,
                    'z_min' : -25000,
                    'f_max' : 98000,
                    'f_min' : 0,
                    'theta_max' : 999,
                    'theta_min' : -999,
                    'x_rot_position': 0, # XYZ position where sample rotation is safe
                    'y_rot_position': 0,
                    'z_rot_position': 0,
                    }

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('M-061.PD', 'M-406.4PD'), # theta, z
                 'refmode' : ('FRF',),
                 'serialnum' : '118015799', # replace with your controller's serial number
                 'velocity' : {1: 22.5, 2: 3}, # PI axis number -> velocity
                 }

xyf_galil_parameters = {'port' : '192.168.1.43', # IP address of the Galil controller
                        'x_encodercounts_per_um' : 2,
                        'y_encodercounts_per_um' : 2,
                        'f_encodercounts_per_um' : 2,
                        }

startup = {
'position' : {'x_pos':0, 'y_pos':0, 'z_pos':0, 'f_pos':0, 'theta_pos':0},
}
