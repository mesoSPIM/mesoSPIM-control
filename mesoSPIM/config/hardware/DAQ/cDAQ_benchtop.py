'''
Waveform generation / DAQ: NI CompactDAQ chassis (cDAQ1Mod1 for triggers,
cDAQ1Mod3 for the analog waveforms).

From examples/format1(legacy)/config_benchtop-cDAQ.py, including the physical wiring notes below.

Note the lower sample rate: cDAQ analog output modules are much slower than
the PXI cards, 25 kHz instead of 100 kHz.

The laser ENABLE lines and the shutter lines mentioned in the wiring notes
(cDAQ1Mod2) are configured in hardware/lasers/cDAQ_lasers.py, not here.
'''
waveformgeneration = 'cDAQ' # 'Demo', 'NI' or 'cDAQ'

'''
compactDAQ limitations:
https://www.ni.com/en/support/documentation/supplemental/18/number-of-concurrent-tasks-on-a-compactdaq-chassis-gen-ii.html

Tasks:
- DO: master_trigger_task,
- CO: camera_trigger_task, stage_trigger_task (if ASI stages used)
- AO: galvo_etl_laser_task, ao lines: 2 + 2 + 4 = 8, each 16 bit (2 bytes), so 16 bytes/sample point, 128 samples per buffer max (2048 bytes)
        if 1 laser task is used: 2 + 2 + 1 = 5, each 2 bytes, 10 bytes/sample point, 204 samples per buffer max (2048 bytes). Sampling rate 1kHZ max for waveform of 200 ms.


Card designations need to be the same as in NI MAX, if necessary, use NI MAX
to rename your cards correctly.

Physical connections:
DIGITAL OUTPUTS (P0.0-P0.3, NI-9401 card in slot 1, 'cDAQ1Mod1'):
- 'master_trigger_out_line' (aka 'cDAQ1Mod1/port0/line0', P0.0/PFI0, Pin14) must be physically connected to P0.4/PFI4 terminal (pin20) of the same card cDAQ1Mod1.
- 'camera_trigger_out_line' to '/cDAQ1Mod1/ctr0' (Pin19 of cDAQ1Mod1 card)
- 'stage_trigger_out_line' to '/cDAQ1Mod1/ctr2' (Pin16 of cDAQ1Mod1 card)

DIGITAL INPUTS (P0.4, NI-9401 card in slot 1, 'cDAQ1Mod1'):
- '/cDAQ1Mod1/PFI4' (aka P0.4/PFI4, pin20, see above) of the same card cDAQ1Mod1. Triggers camera, stage, galvo/ETL tasks.
Note: This also makes four pins P0.4-0.7 configured for input-only.

ANALOG OUTPUTS (NI-9264 card in slot 3, 'cDAQ1Mod3'):
- galvos, ETL controllers to 'cDAQ1Mod3/ao0:3' terminals. Pins 1-4, ground pins on the opposite side.
- laser analog modulation cables to 'cDAQ1Mod3/ao4:7' terminals. Pins 5-8, ground pins on the opposite side.

NI-9401 (digital) card peculiarity:
Input/output mode can be assigned only to digital pins P0.0-P0.3, P0.4-P0.7, or both, so assignment must be grouped by 4 channels (called a nibble).

Connecting BNC cables to the ground:
Signal pin - Ground pin, label:

'cDAQ1Mod1', NI-9401 (digital) card in slot 1:
<< hardware timed tasks, needs them reserved >>
Pin14-Pin1, 'master_trigger_out_line'
Pin19-Pin6, 'camera_trigger_out_line', must be counter-out type of pin
Pin16-Pin3, 'stage_trigger_out_line', must be counter-out type of pin
Pin20-Pin7, '/cDAQ1Mod1/PFI4' ('camera_trigger_source', 'galvo_etl_task_trigger_source', 'laser_task_trigger_source', and 'stage_trigger_source'). Could this be done via internal wiring instead?

'cDAQ1Mod2', NI-9401 (digital) card in slot 2:
<< software timed tasks, needs NO task reservation >>
Pin14-Pin3, 'cDAQ1Mod2/port0/line0', 'shutter_right', arm switching
Pin16-Pin3, 'cDAQ1Mod2/port0/line1', laser enable line for 405 nm
Pin17-Pin4, 'cDAQ1Mod2/port0/line2', laser enable line for 488 nm
Pin19-Pin6, 'cDAQ1Mod2/port0/line3', laser enable line for 561 nm
Pin20-Pin7, 'cDAQ1Mod2/port0/line4', laser enable line for 638 nm

'cDAQ1Mod3', NI-9264 (analog, DSUB-connector version) card in slot 3:
<< hardware timed tasks, needs them reserved >>
Pin1-Pin20, 'cDAQ1Mod3/ao0', galvo L
Pin2-Pin21, 'cDAQ1Mod3/ao1', galvo R
Pin3-Pin22, 'cDAQ1Mod3/ao2', ETL L
Pin4-Pin23, 'cDAQ1Mod3/ao3', ETL R
Pin5-Pin24, 'cDAQ1Mod3/ao4', laser 405 nm
Pin6-Pin25, 'cDAQ1Mod3/ao5', laser 488 nm
Pin7-Pin26, 'cDAQ1Mod3/ao6', laser 561 nm
Pin8-Pin27, 'cDAQ1Mod3/ao7', laser 638 nm
'''

acquisition_hardware = {'master_trigger_out_line' : 'cDAQ1Mod1/port0/line0',
                        'camera_trigger_source' : '/cDAQ1Mod1/PFI4',
                        'camera_trigger_out_line' : '/cDAQ1Mod1/ctr0', # must be COUNTER-OUT (CO) type of pin.
                        'galvo_etl_task_line' : 'cDAQ1Mod3/ao0:3',
                        'galvo_etl_task_trigger_source' : '/cDAQ1Mod1/PFI4',
                        'laser_task_line' :  'cDAQ1Mod3/ao4:7',
                        'laser_task_trigger_source' : '/cDAQ1Mod1/PFI4'}

startup = {
'samplerate' : 25000, # cDAQ AO modules are slower than the PXI cards
# 'sweeptime' is set in the camera file: in ASLM mode it must match the camera readout.
}
