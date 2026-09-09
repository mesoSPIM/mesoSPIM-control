'''
Waveform generation / DAQ: benchtop mesoSPIM with an NI PXIe-6738 card,
the configuration for 5-6 lasers.

https://github.com/mesoSPIM/benchtop-hardware/wiki/Electronics#configuration-with-5-6-lasers

The PXIe-6738 is the lower-cost option for instruments with more than 4 lasers:
32 analog output channels, but only 10 digital I/O channels. Both peculiarities
of this file follow from that card:

- all analog outputs sit on the same card: galvos/ETLs on ao0:3 and the lasers
  further up the range (ao20:24 for 5 lasers here), instead of a separate laser card;
- 'master_trigger_out_line' is '/PXI1Slot2/PFI0' used directly. With so few
  digital lines the trigger is routed in the config file rather than wired from
  a digital output to PFI0, which also saves wiring time.

The scarce DIO also needs a different connector block than the BNC-2110 used
with the standard 4-laser PXI-6733 configuration; see the wiki page above and
the benchtop/Benchtop-UCL-London folder of that repository.

From examples/format1(legacy)/config_benchtop_UCL_5laser.py.

Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

Physical connections:
- 'master_trigger_out_line' ('PXI1Slot2/port0/line0') must be physically connected to BNC-2110 "PFI0 / AI start" terminal.
- 'camera_trigger_out_line' to PFI12 / P2.4 ('/PXI1Slot2/ctr0') terminal
- 'stage_trigger_out_line' to PFI13 / P2.5 ('/PXI1Slot2/ctr1') terminal
  (the stage trigger itself is configured in asi_parameters, see the stages file)
- galvos, ETL controllers to 'PXI1Slot2/ao0:3' terminals
- laser analog modulation cables to 'PXI1Slot2/ao20:24' terminals
'''
waveformgeneration = 'NI' # 'Demo', 'NI' or 'cDAQ'

acquisition_hardware = {'master_trigger_out_line' : '/PXI1Slot2/PFI0', # PFI0 used directly, see above
                        'camera_trigger_source' : '/PXI1Slot2/PFI0',
                        'camera_trigger_out_line' : '/PXI1Slot2/ctr0',
                        'galvo_etl_task_line' : 'PXI1Slot2/ao0:3',
                        'galvo_etl_task_trigger_source' : '/PXI1Slot2/PFI0',
                        'laser_task_line' :  'PXI1Slot2/ao20:24', # 5 lasers; extend to ao20:25 for 6
                        'laser_task_trigger_source' : '/PXI1Slot2/PFI0'}

startup = {
'samplerate' : 100000,
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
}
