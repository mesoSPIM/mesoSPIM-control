'''
Filterwheel: Ludl 10-position wheel (serial).

Second most common wheel in this repository (10 rig configs, among them
config_H45_standard.py, examples/format1(legacy)/config_MDC(Berlin)-OrcaFusion.py,
examples/format1(legacy)/config_WyssGeneva.py). Set 'COMport' to your instrument's port.

Positions are ids 0 .. 9 (int). Note the Ludl marking 10 = position 0.

DOUBLE WHEEL: if the filterdict values are (int, int) tuples instead of
plain ints, the driver treats the hardware as a double filter wheel and sets
both wheels (see LudlFilterWheel). Used e.g. by
examples/format1(legacy)/config_USZ_Francesca(filter-swapped)-Oct2023.py:
    filterdict = {'Empty-Alignment': (0, 0),
                  '405-488-561-640-Quadrupleblock': (2, 0),
                  '565 585-40': (0, 1),
                  ...}
All entries must then be tuples.
'''
filterwheel_parameters = {'filterwheel_type' : 'Ludl',
                          'COMport' : 'COM6',
                          }

# To use the plugin-based Ludl driver instead:
# filterwheel_parameters = {'filterwheel_type': 'LudlPlugin',
#                           'COMport': 'COM6',
#                           'baudrate': 9600,
#                           'wait_until_done_delay': 0.2}

'''
Replace with the filters actually installed in your wheel.
Every config must contain an empty/alignment position.
Dictionary labels must be unique.
'''
filterdict = {'Empty-Alignment' : 0,
              '405-488-647-Tripleblock' : 1,
              '405-488-561-640-Quadrupleblock' : 2,
              '464 482-35' : 3,
              '508 520-35' : 4,
              '515LP' : 5,
              '529 542-27' : 6,
              '561LP' : 7,
              '594LP' : 8,
              '417 447-60' : 9,
              }

startup = {
'filter' : 'Empty-Alignment', # must exist in filterdict above
}
