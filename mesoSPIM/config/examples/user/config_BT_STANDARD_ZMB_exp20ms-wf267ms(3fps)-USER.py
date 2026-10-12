"""
mesoSPIM user configuration, converted from the single-file format.

The microscope itself is described in hardware/config_BT_STANDARD_ZMB_exp20ms-wf267_hw.py: camera, stages, lasers, filters,
objectives, DAQ lines, writer defaults. Change that file when the instrument changes.

Here, keep only what differs for your session. Anything assigned below the include()
line overrides the hardware file, e.g.:

    startup['camera_exposure_time'] = 0.05
    filterdict['Empty-Alignment'] = 0
"""
config_format = 2

include('hardware/config_BT_STANDARD_ZMB_exp20ms-wf267_hw.py')

startup.update({
    'folder': 'F:\\TEMP',
    'average_frame_rate': 3.0,    
})
