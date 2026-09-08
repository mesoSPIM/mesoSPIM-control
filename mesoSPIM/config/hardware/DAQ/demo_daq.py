'''
Waveform generation / DAQ: demo (no hardware).
'''
waveformgeneration = 'DemoWaveFormGeneration' # 'DemoWaveFormGeneration', 'NI' or 'cDAQ'

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
