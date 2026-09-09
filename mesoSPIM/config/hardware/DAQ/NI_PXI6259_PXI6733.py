'''
Waveform generation / DAQ: classic mesoSPIM v5/v6, two NI cards
(PXI6259 for galvos/ETLs and triggers, PXI6733 for the lasers).

Second most common configuration in this repository (11 rig configs, among them
config_mesoSPIM-v6-ZMB-exposure20ms(STANDARD)-v1.2.py, examples/format1(legacy)/config_WyssGeneva.py).

Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

A standard mesoSPIM configuration uses two cards:
PXI6733 is responsible for the lasers (analog intensity control)
PXI6259 is responsible for the shutters, ETL waveforms and galvo waveforms

Physical channels must be connected in certain order:
- 'galvo_etl_task_line' takes Galvo-L, Galvo-R, ETL-L, ETL-R
(e.g. value 'PXI6259/ao0:3' means Galvo-L on ao0, Galvo-R on ao1, ETL-L on ao2, ETL-R on ao3)

- 'laser_task_line' takes laser modulation, lasers sorted in increasing wavelength order,
(e.g. value 'PXI6733/ao0:3' means '405 nm' connected to ao0, '488 nm' to ao1, etc.)
Set the range to your laser count: ao0:3 for 4 lasers (as below), ao0:4 for 5,
ao0:5 for 6, ao0:7 for 8 - all of these are in use across the rig configs.

If your master trigger comes straight off PFI0 instead of a digital output line,
use NI_PXI6259_PXI6733_PFI0_direct.py instead.

Pair it with hardware/lasers/V5_PXI6733_lasers.py: laser ENABLE lines on the PXI-6733,
shutters on the PXI-6259.
'''
waveformgeneration = 'NI' # 'Demo', 'NI' or 'cDAQ'

acquisition_hardware = {'master_trigger_out_line' : 'PXI6259/port0/line1',
                        'camera_trigger_source' : '/PXI6259/PFI0',
                        'camera_trigger_out_line' : '/PXI6259/ctr0',
                        'galvo_etl_task_line' : 'PXI6259/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI6259/PFI0',
                        'laser_task_line' :  'PXI6733/ao0:3',
                        'laser_task_trigger_source' : '/PXI6259/PFI0'}

startup = {
'samplerate' : 100000,
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
}
