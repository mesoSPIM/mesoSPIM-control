'''
Stage configuration: mesoSPIM v5/v6 with a single 6-axis PI controller (C-884).

Second most common stage setup in this repository (17 rig configs), among them
config_mesoSPIM-v6-ZMB-exposure20ms(STANDARD)-v1.2.py, examples/format1(legacy)/config_WyssGeneva.py,
config_NV_Fusion_40x40x100-CUBIC-R+.py, examples/format1(legacy)/config_MDIBL_Kinetix.py.

TEMPLATE: 'serialnum', the stage models and the travel limits below must be
adjusted to your instrument before use - the serial number identifies your
specific controller.

'stage_type' can be 'PI' or 'PI_1controllerNstages'; the two are equivalent.

Two stage sets are in use across the rigs; pick the one matching your hardware:
  ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE')  # below
  ('M-112K033','L-406.40DG10','M-112K033','M-116.DG','M-406.4PD','NOSTAGE')        # v6-ZMB, WyssGeneva, MDC Berlin
The last focus stage differs on some rigs too, e.g. 'M-605.2DD' (MDIBL Kinetix).

For multiple single-axis PI controllers use instead:
stage_parameters['stage_type'] = 'PI_NcontrollersNstages'
pi_parameters = {'axes_names': ('x', 'y', 'z', 'theta', 'f'),
                 'stages': ('L-509.20SD00', 'L-509.40SD00', 'L-509.20SD00', None, 'MESOSPIM_FOCUS'),
                 'controllername': ('C-663', 'C-663', 'C-663', None, 'C-663'),
                 'serialnum': ('**********', '**********', '**********', None, '**********'),
                 'refmode': ('FRF', 'FRF', 'FRF', None, 'RON')
                 }
'''
stage_parameters = {'stage_type' : 'PI', # 'PI' or 'PI_1controllerNstages' (equivalent)
                    'y_load_position': -6000,
                    'y_unload_position': 6000,
                    'x_center_position': 0,
                    'z_center_position': 0,
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 50000,
                    'y_min' : -50000,
                    'z_max' : 25000,
                    'z_min' : -25000,
                    'f_max' : 98000,
                    'f_min' : 0,
                    'f_objective_exchange': 2000, # DANGER ZONE: set up carefully to avoid collisions!
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }

pi_parameters = {'controllername' : 'C-884',
                 'stages' : ('L-509.20DG10','L-509.40DG10','L-509.20DG10','M-060.DG','M-406.4PD','NOSTAGE'),
                 'refmode' : ('FRF',),
                 'serialnum' : ('118075764'), # replace with your controller's serial number
                 }

startup = {
'position' : {'x_pos':0, 'y_pos':0, 'z_pos':0, 'f_pos':0, 'theta_pos':0},
}
