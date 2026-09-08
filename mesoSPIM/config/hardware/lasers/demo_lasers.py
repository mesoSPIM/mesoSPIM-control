'''
Lasers and shutters of a demo/simulation machine.

Identical to hardware/lasers/benchtop_PXI6733_lasers.py apart from the two driver flags, so
that mesoSPIM runs without an NI card attached.
'''
include('hardware/lasers/benchtop_PXI6733_lasers.py')

laser = 'Demo' # 'Demo', 'NI', or 'cDAQ'
shutter = 'Demo' # 'Demo', 'NI', or 'cDAQ'
