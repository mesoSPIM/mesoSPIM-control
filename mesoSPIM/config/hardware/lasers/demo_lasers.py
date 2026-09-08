'''
Laser and shutter configuration of a demo/simulation machine.

Identical to hardware/lasers/production_lasers.py (a standard Benchtop mesoSPIM) apart from the
two driver flags, so that mesoSPIM runs without an NI card attached.
'''
include('hardware/lasers/production_lasers.py')

laser = 'Demo' # 'Demo', 'NI', or 'cDAQ'
shutter = 'Demo' # 'Demo', 'NI', or 'cDAQ'
