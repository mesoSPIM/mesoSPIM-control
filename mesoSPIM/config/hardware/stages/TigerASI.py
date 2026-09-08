'''
Stage configuration: benchtop mesoSPIM with an ASI Tiger controller.

The most common stage setup in this repository (20 rig configs). Values below
are from examples/format1(legacy)/config_benchtop_standard2025_v1.2.py; adjust 'COMport', the
travel limits and the trigger lines to your instrument.

The stage assignment dictionary assigns a mesoSPIM stage (xyzf and theta - dict key)
to an ASI stage (XYZ etc), which are the values of the dict.

'encoder_conversion' is encoder counts per um (per degree for theta).
Note the two variants in use: T = 1000.0 on the benchtop standard rigs,
T = 100.0 on some older ones (CBI, V20) - check yours before moving theta.

'ttl_cards' is the tuple of Tiger card numbers used for TTL motion: (1, 2) on
the 2024/2025 benchtop standard, (2, 3) on the older V20 / CBI rigs.
Set 'ttl_motion_enabled' to False to drive the stage without TTL triggering.

The stage trigger lines must match the DAQ file you include: the values below
pair with NI_benchtop_PXI1Slot4.py ('/PXI1Slot4/...'). With the cDAQ chassis
they are '/cDAQ1Mod1/PFI4' and '/cDAQ1Mod1/ctr2'; with the UCL PXIe-6738 card
'/PXI1Slot2/PFI0' and '/PXI1Slot2/ctr1'.

For a 'Mixed' setup (some axes on ASI, some on PI), set
stage_parameters['stage_type'] = 'Mixed' and provide both asi_parameters and
pi_parameters, each with its own 'stage_assignment' dict (None for unassigned axes), e.g.
  asi_parameters['stage_assignment'] = {'z': 'Z', 'theta': 'T', 'x': None, 'y': None, 'f': None}
  pi_parameters['stage_assignment'] = {'x': 1, 'y': 2, 'f': 3}
'''
stage_parameters = {'stage_type' : 'TigerASI', # 'TigerASI' or 'MS2000ASI'
                    'y_load_position': -6000,
                    'y_unload_position': 6000,
                    'x_center_position': 0, # x-center position for the sample holder, relative to the detection objective and light-sheet
                    'z_center_position': 0, # z-center position for the sample holder, relative to the detection objective and light-sheet
                    'x_max' : 25000,
                    'x_min' : -25000,
                    'y_max' : 50000,
                    'y_min' : -50000,
                    'z_max' : 25000,
                    'z_min' : -25000,
                    'f_max' : 98000,
                    'f_min' : 0,
                    'f_objective_exchange': None, # DANGER ZONE: None means 'stay in the current f-position'. Set a value only after checking it against your setup, to avoid collisions!
                    'theta_max' : 999,
                    'theta_min' : -999,
                    }

# The key ORDER of 'stage_assignment' is the axis order of the 'W' (where) query sent to the
# controller, so it is part of the rig configuration, not cosmetic. If your controller reports
# positions in a different axis order, list the axes here in that order (and keep
# 'encoder_conversion' and 'speed' readable by using the same order there).
asi_parameters = {'COMport' : 'COM6',
                  'baudrate' : 115200,
                  'stage_assignment': {'x':'X', 'f':'Y', 'z':'Z', 'theta':'T', 'y':'V'},
                  'encoder_conversion': {'X': 10., 'Y': 10., 'Z': 10., 'T': 1000., 'V': 10.}, # counts per um, or per degree for theta
                  'speed': {'X': 3., 'Y': 3., 'Z': 3., 'T': 30., 'V': 3.},
                  'stage_trigger_source': '/PXI1Slot4/PFI0',
                  'stage_trigger_out_line': '/PXI1Slot4/ctr1',
                  'stage_trigger_delay_%' : 92.5, # Set to 92.5 for stage triggering exactly after the ETL sweep
                  'stage_trigger_pulse_%' : 1,
                  'ttl_motion_enabled': True,
                  'ttl_cards':(1, 2), # None if MS2000ASI; tuple of card numbers if TigerASI
                  }

startup = {
'position' : {'x_pos':0, 'y_pos':0, 'z_pos':0, 'f_pos':0, 'theta_pos':0},
}
