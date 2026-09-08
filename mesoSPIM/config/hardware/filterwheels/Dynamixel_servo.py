'''
Filterwheel: Dynamixel servo-driven wheel (serial).

From config-servo-filterwheel-test.py.

Positions are servo ENCODER COUNTS, not slot ids: 0 for 0 deg, 1024 for 45 deg
(360 deg = 4096 counts, i.e. 11.377 counts/deg), and they may be negative.
Encoder range in multi-turn mode: -28672 .. +28672 counts.
'''
filterwheel_parameters = {'filterwheel_type' : 'Dynamixel',
                          'COMport' : 'COM3',
                          'baudrate' : 115200, # 1000000 for some servo models
                          'servo_id' : 1,
                          }

'''
Replace with the filters actually installed in your wheel, in encoder counts.
Every config must contain an empty/alignment position.
Dictionary labels must be unique.
'''
filterdict = {'Empty-Alignment' : 0,
              '405-488-647-Tripleblock' : 1024,
              '405-488-561-640-Quadrupleblock' : 2048,
              '464 482-35' : -1024,
              '508 520-35' : -2048,
              }

startup = {
'filter' : 'Empty-Alignment', # must exist in filterdict above
}
