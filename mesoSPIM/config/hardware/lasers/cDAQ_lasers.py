'''
Lasers and shutters of a mesoSPIM on an NI CompactDAQ chassis: the digital lines live on the
cDAQ1Mod2 module, so pair this file with hardware/DAQ/cDAQ_benchtop.py.

From examples/format1(legacy)/config_benchtop-cDAQ.py. Note that 'shutter_left' is an empty
terminal here: the single shutter line switches the illumination arm.

Make sure that 'max_laser_voltage' is correct (5 V for Toptica MLEs, 10 V for Omicron SOLE).
'''
laser = 'cDAQ' # 'Demo', 'NI', or 'cDAQ'

''' The `laserdict` specifies laser labels of the GUI and their digital modulation channels.
Keys are the laser designation that will be shown in the user interface
Values are DO ports used for laser ENABLE digital signal.
Critical: entries must be sorted in the increasing wavelength order: 405, 488, etc.
'''
laserdict = {'405 nm': 'cDAQ1Mod2/port0/line1',
             '488 nm': 'cDAQ1Mod2/port0/line2',
             '561 nm': 'cDAQ1Mod2/port0/line3',
             '638 nm': 'cDAQ1Mod2/port0/line4',
             }

''' Laser blanking indicates whether the laser enable lines should be set to LOW between
individual images or stacks. This is helpful to avoid laser bleedthrough between images caused by insufficient
modulation depth of the analog input (even at 0V, some laser light is still emitted).
'''
laser_blanking = 'images' # if 'images', laser is off before and after every image; if 'stacks', before and after each stack.

'''
Shutter configuration
If shutterswitch = True:
    'shutter_left' is the general shutter
    'shutter_right' is the left/right switch (Right==True)

If shutterswitch = False or missing:
    'shutter_left' and 'shutter_right' are two independent shutters.
'''
shutter = 'cDAQ' # 'Demo', 'NI', or 'cDAQ'
shutterswitch = False # see legend above
shutteroptions = ('Left', 'Right') # Shutter options of the GUI
shutterdict = {'shutter_left' : None, # empty terminal, general shutter, optional
              'shutter_right' : 'cDAQ1Mod2/port0/line0'} # flip mirror or right shutter, depending on physical configuration

startup = {
'laser' : '488 nm',
'max_laser_voltage' : 5, # 5 V for Toptica MLEs, 10 V for Omicron SOLE
'intensity' : 10,
'laser_interleaving' : False,
'shutterstate' : False, # Is the shutter open or not?
'shutterconfig' : 'Right', # Can be "Left", "Right", "Both", "Interleaved"
'laser_l_delay_%' : 10,
'laser_l_pulse_%' : 87,
'laser_l_max_amplitude_%' : 100,
'laser_r_delay_%' : 10,
'laser_r_pulse_%' : 87,
'laser_r_max_amplitude_%' : 100,
}
