'''
Waveform generation / DAQ: classic mesoSPIM v5/v6 cards (PXI6259 + PXI6733),
wired with the master trigger taken directly from PFI0 instead of a digital
output line.

From examples/format1(legacy)/config_H45-2026-PFI0-direct-v1.2.py and
examples/format1(legacy)/config_HIFO-H45-PFI0-direct-connection.py.

Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

A standard mesoSPIM configuration uses two cards:
PXI6733 is responsible for the lasers (analog intensity control)
PXI6259 is responsible for the shutters, ETL waveforms and galvo waveforms

The only difference to NI_PXI6259_PXI6733.py is 'master_trigger_out_line':
here it is '/PXI6259/PFI0' used directly, instead of 'PXI6259/port0/line1'
plus a physical wire to PFI0. Use this file only if your instrument is wired
that way.
'''
waveformgeneration = 'NI' # 'DemoWaveFormGeneration', 'NI' or 'cDAQ'

acquisition_hardware = {'master_trigger_out_line' : '/PXI6259/PFI0', # Instead of 'PXI6259/port0/line1' + wire, use '/PXI6259/PFI0' directly
                        'camera_trigger_source' : '/PXI6259/PFI0',
                        'camera_trigger_out_line' : '/PXI6259/ctr0',
                        'galvo_etl_task_line' : 'PXI6259/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI6259/PFI0',
                        'laser_task_line' :  '/PXI6733/ao0:5', # 6 lasers; shrink/extend to your laser count
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}

startup = {
'samplerate' : 100000,
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
}
