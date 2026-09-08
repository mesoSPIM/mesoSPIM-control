'''
Filterwheel: Sutter Lambda 10-B / 10-3 (serial).

From the CBI Retiga E9 benchtop configs (examples_private/CBI_PhotometricsRetigaE9_*.py).

'wheel_speed' is 0 (fastest) .. 7 (slowest).
Positions are ids 0 .. 9 (int).

Note the baud rate: those rigs run the built-in driver at 115200, while Sutter
Lambda 10 controllers are often set to 9600. It must match the controller's
serial-interface setting.
'''
filterwheel_parameters = {'filterwheel_type' : 'Sutter',
                          'COMport' : 'COM8',
                          'baudrate' : 115200,
                          'wheel_speed': 3, # 0 (fastest) .. 7 (slowest)
                          }

# To use the plugin-based Sutter driver instead:
# filterwheel_parameters = {'filterwheel_type': 'SutterPlugin',
#                           'COMport': 'COM8',
#                           'baudrate': 9600,
#                           'wheel_speed': 3,
#                           'wait_until_done_delay': 0.5}

'''
Replace with the filters actually installed in your wheel.
Every config must contain an empty/alignment position.
Dictionary labels must be unique.
'''
filterdict = {'open' : 0,
              'Empty-Alignment' : 1,
              'Dapi' : 2,
              '525/50 (GFP)' : 3,
              '595/44 (RFP)' : 4,
              '700/75 cy5' : 5,
              }

startup = {
'filter' : 'Empty-Alignment', # must exist in filterdict above
}
