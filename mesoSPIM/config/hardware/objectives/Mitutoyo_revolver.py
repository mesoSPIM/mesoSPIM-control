'''
Zoom configuration: motorised Mitutoyo objective revolver (mesoSPIM v6 Revolver).

9 rig configs, among them config_mesoSPIM-v6-ZMB-exposure20ms(STANDARD)-v1.2.py,
examples/format1(legacy)/config_ZMB_mesoSPIM-v6Revolver(OrcaLightning_MitutoyoRevolver_ZWO-filterwheel).py,
USZ2_config_2025-UPGRADE.py.

TEMPLATE: set 'COMport' to the port of the revolver (COM6 and COM17 are in use). The revolver
speaks RS-232 at 9600 baud with even parity; it uses no servo id.

Unlike a zoom body, this is a turret of five objectives: the zoomdict values are the revolver
positions 'A' .. 'E' (mesoSPIM_Zoom.py sends them as 'RWRMV<X>'), and only those five letters
are accepted. The keys name the objective actually screwed into each position, so edit them
to match your turret - one instrument labels position E '20x_custom(t25)' instead of '20x'
(same 0.275 um pixel size).
'''
zoom_parameters = {'zoom_type' : 'Mitu', # 'Demo', 'Dynamixel', or 'Mitu'
                   'COMport' : 'COM17',
                   'baudrate' : 9600,
                   }

'''
The keys of zoomdict are the objectives offered in the interface, the values are the revolver
positions. Valid positions are 'A', 'B', 'C', 'D', 'E' - nothing else.
'''
zoomdict = {'2x' : 'A',
            '5x' : 'B',
            '7.5x' : 'C',
            '10x' : 'D',
            '20x' : 'E',
            }

'''
Pixel size in the sample plane, in micron. Keys must match the zoomdict keys.

Pixel size = the camera pixel pitch (data sheet) divided by the magnification of the objective
in that revolver position. The values below are those of a 5.5 um camera (Orca Lightning).
Swapping an objective means changing both dicts.

They are used for the acquisition metadata, the tile view and the scale bar, so a wrong value
here silently produces data with the wrong scale.
'''
pixelsize = {'2x' : 2.75,
             '5x' : 1.1,
             '7.5x' : 0.73333,
             '10x' : 0.55,
             '20x' : 0.275,
             }

startup = {
'zoom' : '2x', # must exist in zoomdict above
'pixelsize' : 2.75, # must match pixelsize[startup['zoom']]
}
