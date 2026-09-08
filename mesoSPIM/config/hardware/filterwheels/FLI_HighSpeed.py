'''
Filterwheel: FLI High Speed Filter Wheel (HS-625 / HS-1025 / HS-1032, serial).

Plugin-based driver (mesoSPIM/src/plugins/FilterWheels/FLIFilterWheelPlugin.py).
No rig config in this repository uses it yet, so the port and the filter set
below are placeholders - the driver itself is covered by
mesoSPIM/test/test_fli_filter_wheel_plugin.py.

Positions are configured integers 0 .. 9, transmitted without conversion or
indexing offset, so set them to the numbering verified on your wheel.
'''
filterwheel_parameters = {'filterwheel_type' : 'FLI',
                          'COMport' : 'COM3',
                          'baudrate' : 9600,
                          'wait_until_done_delay' : 0.2,
                          }

'''
Replace with the filters actually installed in your wheel.
Every config must contain an empty/alignment position.
Dictionary labels must be unique.
'''
filterdict = {'Empty-Alignment' : 0,
              '405-488-561-640-Quadrupleblock' : 1,
              '525/50' : 2,
              '595/31' : 3,
              }

startup = {
'filter' : 'Empty-Alignment', # must exist in filterdict above
}
