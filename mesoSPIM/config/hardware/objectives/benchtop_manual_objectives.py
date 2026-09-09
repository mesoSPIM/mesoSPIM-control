'''
Objectives of a Benchtop mesoSPIM: changed by hand, not by a motor.

The benchtop has no motorised zoom, so it runs the 'Demo' zoom driver: nothing is moved when
you pick another objective in the interface, but the choice selects the pixel size written
into the metadata, and mesoSPIM scales the galvo amplitude with it if
scale_galvo_amp_with_zoom is True (see hardware/galvos/).

12 rig configs, among them examples/format1(legacy)/config_benchtop_standard2025_v1.2.py,
config_benchtop-cDAQ.py, config_benchtop_UCL_5laser.py.

IMPORTANT: after screwing in a different objective, select it in the interface as well -
nothing else tells mesoSPIM which one is in place.

TEMPLATE: list the objectives your instrument actually has, with their pixel sizes.
'''
zoom_parameters = {'zoom_type' : 'Demo', # 'Demo', 'Dynamixel', or 'Mitu'
                   } # the manual changer needs no connection settings

'''
The keys of zoomdict are the objectives offered in the interface. The values are the positions
a motorised changer would move to; with the manual changer they are never used, so keep them
as plain position numbers (rig configs use 1 .. 10, or 0 .. 4 as on the UCL instrument).
'''
zoomdict = {'2x' : 4,
            '5x' : 6,
            '7.5x' : 7,
            '10x' : 8,
            '20x' : 9,
            }

'''
Pixel size in the sample plane, in micron. Keys must match the zoomdict keys.

Pixel size = the camera pixel pitch (data sheet) divided by the magnification. The values below
are those of a 4.25 um camera (Photometrics Iris 15); a benchtop with an Orca Lightning
(5.5 um) lists 2.75 um at 2x instead of 2.125 um
(examples/format1(legacy)/config_benchtop_HIFO-J90-OrcaLightning.py).

They are used for the acquisition metadata, the tile view and the scale bar, so a wrong value
here silently produces data with the wrong scale.
'''
pixelsize = {'2x' : 2.125,
             '5x' : 0.85,
             '7.5x' : 0.56667,
             '10x' : 0.425,
             '20x' : 0.2125,
             }

startup = {
'zoom' : '5x', # must exist in zoomdict above
'pixelsize' : 0.85, # must match pixelsize[startup['zoom']]
}
