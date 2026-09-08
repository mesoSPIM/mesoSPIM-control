'''
Waveform generation / DAQ: standard benchtop mesoSPIM, single NI PXI-6733 card
(named 'PXI1Slot4' in NI MAX), the configuration for up to 4 lasers.

https://github.com/mesoSPIM/benchtop-hardware/wiki/Electronics

The PXI-6733 sits in a hybrid slot (#4, 5 or 6) of the PXIe-1073 chassis and
has 8 analog outputs: ao0:3 for the galvos/ETLs, ao4:7 for the lasers.
It is used with a BNC-2110 connector block. For 5-6 lasers, use the
PXIe-6738 card and NI_benchtop_PXIe6738.py instead.

The most common configuration in this repository (12 rig configs, among them
examples/format1(legacy)/config_benchtop_standard2025_v1.2.py, config_benchtop_HIFO-J90.py,
USZ2_config_2025-UPGRADE.py).

Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

Physical connections:
- 'master_trigger_out_line' ('PXI1Slot4/port0/line0') must be physically connected to BNC-2110 "PFI0 / AI start" terminal.
- 'camera_trigger_out_line' to PFI12 / P2.4 ('/PXI1Slot4/ctr0') terminal
- 'stage_trigger_out_line' to PFI13 / P2.5 ('/PXI1Slot4/ctr1') terminal
  (the stage trigger itself is configured in asi_parameters, see the stages file)
- galvos, ETL controllers to 'PXI1Slot4/ao0:3' terminals
- laser analog modulation cables to 'PXI1Slot4/ao4:7' terminals

Physical channels must be connected in certain order:
- 'galvo_etl_task_line' takes Galvo-L, Galvo-R, ETL-L, ETL-R
(here 'PXI1Slot4/ao0:3' means Galvo-L on ao0, Galvo-R on ao1, ETL-L on ao2, ETL-R on ao3)

- 'laser_task_line' takes laser modulation, lasers sorted in increasing wavelength order,
(here 'PXI1Slot4/ao4:7' means '405 nm' connected to ao4, '488 nm' to ao5, etc.)
Shrink or extend the range to the number of lasers you have.
'''
waveformgeneration = 'NI' # 'DemoWaveFormGeneration', 'NI' or 'cDAQ'

acquisition_hardware = {'master_trigger_out_line' : 'PXI1Slot4/port0/line0',
                        'camera_trigger_source' : '/PXI1Slot4/PFI0',
                        'camera_trigger_out_line' : '/PXI1Slot4/ctr0',
                        'galvo_etl_task_line' : 'PXI1Slot4/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI1Slot4/PFI0',
                        'laser_task_line' :  'PXI1Slot4/ao4:7',
                        'laser_task_trigger_source' : '/PXI1Slot4/PFI0'}

startup = {
'samplerate' : 100000,
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
}
