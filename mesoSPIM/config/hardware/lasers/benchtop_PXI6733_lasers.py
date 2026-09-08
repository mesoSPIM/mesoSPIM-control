'''
Lasers and shutters of a standard Benchtop mesoSPIM: everything on the single NI PXI-6733
card (named 'PXI1Slot4' in NI MAX), so pair this file with hardware/DAQ/NI_benchtop_PXI6733.py
or NI_benchtop_PXIe6738.py.

The most common wiring in this repository (10 rig configs). The other laser files are:
* V5_PXI6733_lasers.py - a V5/V6 mesoSPIM, lasers on 'PXI6733', shutters on 'PXI6259';
* cDAQ_lasers.py - a CompactDAQ chassis;
* demo_lasers.py - this file with the drivers switched to 'Demo'.

Make sure that 'max_laser_voltage' is correct (5 V for Toptica MLEs, 10 V for Omicron SOLE).
'''
laser = 'NI' # 'Demo', 'NI', or 'cDAQ'

''' The `laserdict` specifies laser labels of the GUI and their digital modulation channels.
Keys are the laser designation that will be shown in the user interface
Values are DO ports used for laser ENABLE digital signal.
Critical: entries must be sorted in the increasing wavelength order: 405, 488, etc.
'''
laserdict = {'405 nm': 'PXI1Slot4/port0/line2',
             '488 nm': 'PXI1Slot4/port0/line3',
             '561 nm': 'PXI1Slot4/port0/line4',
             '638 nm': 'PXI1Slot4/port0/line5',
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
shutter = 'NI' # 'Demo', 'NI', or 'cDAQ'
shutterswitch = False # see legend above
shutteroptions = ('Left', 'Right') # Shutter options of the GUI
shutterdict = {'shutter_left' : '/PXI1Slot4/port0/line6', # left (general) shutter
              'shutter_right' : '/PXI1Slot4/port0/line1'} # flip mirror or right shutter, depending on physical configuration

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
