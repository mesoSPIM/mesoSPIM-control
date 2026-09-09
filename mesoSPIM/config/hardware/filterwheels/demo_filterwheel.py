'''
Filterwheel configuration.

For the 'Demo' wheel, no COMport needs to be specified.
For a Ludl Filterwheel, a valid COMport is necessary. Ludl marking 10 = position 0.
For the plugin-based LudlPlugin, COMport, baudrate, and wait_until_done_delay are required.
For SutterPlugin, COMport, baudrate, wheel_speed, and wait_until_done_delay are required.
For ZWOPlugin, no parameters are required ('wait_until_done_delay', 'wheel_index' and 'dll_path' are optional).
For a Dynamixel FilterWheel, valid baudrate and servo_id are necessary.
'''
filterwheel_parameters = {'filterwheel_type' : 'Demo', # 'Demo', 'Ludl', 'LudlPlugin', 'Sutter', 'SutterPlugin', 'Dynamixel', 'ZWO', 'ZWOPlugin', 'FLI'
                          } # the 'Demo' wheel needs no connection settings, see the examples below
# To use the plugin-based Ludl driver instead:
# filterwheel_parameters = {'filterwheel_type': 'LudlPlugin',
#                           'COMport': 'COM3',
#                           'baudrate': 9600,
#                           'wait_until_done_delay': 0.2}
# To use the plugin-based Sutter driver instead:
# filterwheel_parameters = {'filterwheel_type': 'SutterPlugin',
#                           'COMport': 'COM3',
#                           'baudrate': 128200,
#                           'wheel_speed': 3,
#                           'wait_until_done_delay': 0.5}
# To use the plugin-based ZWO EFW driver instead (no COMport, USB SDK):
# filterwheel_parameters = {'filterwheel_type': 'ZWOPlugin',
#                           'wait_until_done_delay': 1.0,  # optional, defaults to 1.0 s
#                           'wheel_index': 0,  # optional, for >1 connected EFW wheel
#                           }
# To use an FLI High Speed Filter Wheel instead:
# filterwheel_parameters = {'filterwheel_type': 'FLI',
#                           'COMport': 'COM3',
#                           'baudrate': 9600,
#                           'wait_until_done_delay': 0.2}

'''
filterdict contains filter labels and their positions. The valid positions are:
For Ludl: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For Sutter and SutterPlugin: 0, 1, 2, 3, .., 9, i.e. position ids (int)
For FLI: configured integer positions 0 .. 9 are transmitted without conversion.
For Dynamixel: servo encoder counts, e.g. 0 for 0 deg, 1024 for 45 deg (360 deg = 4096 counts, or 11.377 counts/deg).
Dynamixel encoder range in multi-turn mode: -28672 .. +28672 counts.
For ZWO and ZWOPlugin: slot ids (int) starting at 0, e.g. 0 .. 4 for the EFW Mini 5-slot wheel.
'''
filterdict = {'Empty' : 0, # Every config should contain at least this entry
              '405-488-647-Tripleblock' : 1,
              '405-488-561-640-Quadrupleblock' : 2,
              '464 482-35' : 3,
              '508 520-35' : 4,
              '515LP' : 5,
              '529 542-27' : 6,
              '561LP' : 7,
              '594LP' : 8,
              'Empty-1' : 9} # Dictionary labels must be unique!

startup = {
'filter' : 'Empty', # must exist in filterdict above
}
