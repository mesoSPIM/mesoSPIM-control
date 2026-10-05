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

plugins['first_image_writer'] = 'MP_OME_Zarr_Writer'

'''Sharded OME-Zarr v0.5 at 12 FPS (benchmarked 2026-10-01).'''
MP_OME_Zarr_Writer.update({
    'ome_version': '0.5',
    'generate_multiscales': True,
    'compression': 'zstd',
    'compression_level': 1,
    'shards': (64, 6000, 6000),        # shards[0] MUST equal base_chunks[0]
    'base_chunks': (64, 1264, 1480),
    'target_chunks': (64, 64, 64),
    'ring_buffer_size': 512,
    'write_cache': None,
})

startup.update({
    'folder': 'F:\\TEMP',
})
