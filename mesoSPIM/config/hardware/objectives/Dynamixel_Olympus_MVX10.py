'''
Zoom configuration: Olympus MVX-ZB10 zoom body turned by a Dynamixel servo.

The zoom of the classic mesoSPIM (v4/v5/v6): 15 rig configs, among them
config_H45_standard.py, config_NV_Fusion_40x40x100-CUBIC-R+.py,
examples/format1(legacy)/config_WyssGeneva.py, config_MDIBL_Kinetix.py,
config_ZMB-mesoSPIM-v4(OrcaFlash4-OlympusZoomBody-Ludl-filterwheel).py.

TEMPLATE: 'COMport' and 'servo_id' differ per instrument (COM5 .. COM24 and ids 1 .. 4 are
in use) and must be set for yours. The baudrate of the Dynamixel bus is 1000000 on all
mesoSPIM zoom bodies; the CBI benchtop rigs run their servo at 57600 with a different
zoomdict entirely (4x .. 32x, see examples_private/CBI_*.py), so check yours.

'zoomdict' values are servo goal positions, decreasing with increasing magnification: the
servo turns the zoom ring from 0.63x (3423) to 6.3x (0). The positions below are those of
the MVX-ZB10 body and are the same on every instrument using it; only the pixel sizes differ.
'''
zoom_parameters = {'zoom_type' : 'Dynamixel', # 'Demo', 'Dynamixel', or 'Mitu'
                   'COMport' : 'COM10',
                   'baudrate' : 1000000,
                   'servo_id' : 1,
                   }

'''
The keys of zoomdict are the zoom positions offered in the interface; the values are the
Dynamixel servo positions. Remove the entries your zoom body cannot reach.
'''
zoomdict = {'0.63x' : 3423,
            '0.8x' : 3071,
            '1x' : 2707,
            '1.25x' : 2389,
            '1.6x' : 2047,
            '2x' : 1706,
            '2.5x' : 1354,
            '3.2x' : 967,
            '4x' : 637,
            '5x' : 318,
            '6.3x' : 0,
            }

'''
Pixel size in the sample plane, in micron. Keys must match the zoomdict keys.

Pixel size = the camera pixel pitch (data sheet) divided by the total magnification, so it
depends on the camera and the tube lens, not only on the zoom setting. The values below are
those of a 6.5 um camera (Orca Flash4, Fusion, Kinetix) and are shared by 10 rig configs; a
mesoSPIM with a different tube lens lists e.g. 6.09 um at 1x instead of 6.55 um
(examples/format1(legacy)/config_USZ_AnnaMaria(filters-swapped)-Oct2023.py).

They are used for the acquisition metadata, the tile view and the scale bar, so a wrong
value here silently produces data with the wrong scale.
'''
pixelsize = {'0.63x' : 10.52,
             '0.8x' : 8.23,
             '1x' : 6.55,
             '1.25x' : 5.26,
             '1.6x' : 4.08,
             '2x' : 3.26,
             '2.5x' : 2.6,
             '3.2x' : 2.03,
             '4x' : 1.6,
             '5x' : 1.27,
             '6.3x' : 1.03,
             }

startup = {
'zoom' : '1x', # must exist in zoomdict above
'pixelsize' : 6.55, # must match pixelsize[startup['zoom']]
}
