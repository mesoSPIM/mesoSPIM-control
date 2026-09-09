'''
Zoom / objective configuration ('objectives' is the historical name for zoom).

For 'Demo', no connection settings are needed.
For a 'Dynamixel' servo-driven zoom, 'servo_id', 'COMport' and 'baudrate' (default 1000000) must be specified.
For 'Mitu' (Mitutoyo revolver), 'COMport' and 'baudrate' (default 9600) must be specified.
'''
zoom_parameters = {'zoom_type' : 'Demo', # 'Demo', 'Dynamixel', or 'Mitu'
                   }

'''
The keys in the zoomdict define what zoom positions are displayed in the selection box
(combobox) in the user interface. Values are the 'Dynamixel' servo positions.

The 'Mitu' (Mitutoyo revolver) positions are letters instead:
zoomdict = {'2x': 'A', '5x': 'B', '7.5x': 'C', '10x': 'D', '20x': 'E'}
'''
zoomdict = {'1x' : 2707,
            '2x' : 1706,
            '4x Olympus' : 637,
            '5x Mitutoyo' : 318,
            }

'''
Pixelsize in micron. Keys must match the zoomdict keys.
'''
pixelsize = {
            '1x' : 5.0,
            '2x' : 2.5,
            '4x Olympus' : 1.25,
            '5x Mitutoyo' : 1.0,}

startup = {
'zoom' : '2x', # must exist in zoomdict above
'pixelsize' : 1.0,
}
