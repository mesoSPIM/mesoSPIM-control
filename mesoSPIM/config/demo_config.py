"""
mesoSPIM user configuration, converted from the single-file format.

The microscope itself is described in hardware/demo_config_hw.py: camera, stages, lasers, filters,
objectives, DAQ lines, writer defaults. Change that file when the instrument changes.

Here, keep only what differs for your session. Anything assigned below the include()
line overrides the hardware file, e.g.:

    startup['camera_exposure_time'] = 0.05
    filterdict['Empty-Alignment'] = 0
"""
config_format = 2

include('hardware/demo_config_hw.py')

startup.update({
    'state': 'init',
    'folder': 'D:/tmp/',
    'snap_folder': 'D:/tmp/',
    'file_prefix': '',
    'file_suffix': '000001',
})
