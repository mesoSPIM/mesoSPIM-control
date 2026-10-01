"""
mesoSPIM user configuration: sharded OME-Zarr v0.5 pyramids at 12 FPS.

Same as config_benchtop-cDAQ-ASI_user.py, plus MP_OME_Zarr_Writer settings benchmarked on 2026-10-01
(real plugin, real 5056x2960 frames, 2 stacks x 1001 planes paced at 12 FPS):
    F: (XPG S70 NVMe)       keeps up: writer done 4.9 s after the last frame, data verified.
    D: (Samsung 870 QVO)    disk-bound at ~8.8 FPS sustained (169 MB/s after its SLC cache fills).

Requires the FastShardWriter change in support_files/ImageWriters/OmeZarrWriterMP/omezarr_writer.py;
without it zarr-python writes these shards at only ~5.6 FPS.
"""
config_format = 2

include('hardware/config_benchtop-cDAQ-ASI_hw.py')

startup.update({
    'state': 'init',
    'folder': 'F:/Test/',
    'snap_folder': 'F:/Test/',
    'file_prefix': '',
    'file_suffix': '000001',
})

plugins['first_image_writer'] = 'MP_OME_Zarr_Writer'

MP_OME_Zarr_Writer.update({
    'ome_version': '0.5',
    'generate_multiscales': True,
    # zstd-1 and lz4 both reach 12 FPS (zstd-1 files ~2% smaller); zstd-3 gives 10.6 FPS, zstd-5 7.6 FPS.
    # Do not use None: in v0.5, zarr then applies its default zstd anyway.
    'compression': 'zstd',
    'compression_level': 1,
    # Saved array is (z, 5056, 2960). 1264 and 1480 divide the plane exactly, so each z-slab is ONE shard file,
    # and they are the largest such sizes that still shrink to 64x64 chunks at the deepest pyramid level.
    # shards[0] MUST equal base_chunks[0]: a shallower chunk makes two writer threads fill the same shard
    # concurrently, and one half is lost. z=64 is the max (chunk z is capped by target_chunks z) -> fewest files,
    # ~43 files per 1001-plane stack.
    'shards': (64, 6000, 6000),
    'base_chunks': (64, 1264, 1480),
    'target_chunks': (64, 64, 64),
    'ring_buffer_size': 512,
    'write_cache': None,
})
