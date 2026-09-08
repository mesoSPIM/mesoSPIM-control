'''
Filterwheel: ZWO EFW (USB).

The most common filter wheel in this repository (24 rig configs, among them
examples/format1(legacy)/config_benchtop_standard2025_v1.2.py, config_mesoSPIM-v6-ZMB-*.py,
examples/format1(legacy)/config_benchtop_UCL_5laser.py).

The ZWO EFW is a USB device: no COM port, no baud rate. Older config files
carry 'COMport'/'baudrate'/'servo_id' next to the ZWO type; those are ignored.

Positions are slot ids (int) starting at 0, e.g. 0 .. 4 for the EFW Mini
5-slot wheel, 0 .. 7 for the 8-slot wheel.
'''
filterwheel_parameters = {'filterwheel_type' : 'ZWO'}

# To use the plugin-based ZWO EFW driver instead (all keys optional):
# filterwheel_parameters = {'filterwheel_type': 'ZWOPlugin',
#                           'wait_until_done_delay': 1.0,  # defaults to 1.0 s
#                           'wheel_index': 0,  # for >1 connected EFW wheel
#                           'dll_path': 'C:/path/to/EFW_filter.dll',  # overrides the bundled library
#                           }

'''
Replace with the filters actually installed in your wheel.
Every config must contain an empty/alignment position.
Dictionary labels must be unique.
'''
filterdict = {'Empty' : 0,
              '405-488-561-640-Quadrupleblock' : 1,
              '535/22 Brightline' : 2,
              '595/31 Brightline' : 3,
              }

startup = {
'filter' : 'Empty', # must exist in filterdict above
}
