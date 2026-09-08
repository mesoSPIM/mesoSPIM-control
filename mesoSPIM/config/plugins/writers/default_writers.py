'''
ImageWriter plugin parameters. The variable name must match the writer plugin name().

'''
'''
H5_BDV_Writer plugin parameters, if this format is used for data saving (optional).
Downsampling and compression slows down writing by 5x - 10x, use with caution.
Imaris can open these files if no subsampling and no compression is used.
'''
H5_BDV_Writer = {'subsamp': ((1, 1, 1),), #((1, 1, 1),) no subsamp, ((1, 1, 1), (1, 4, 4)) for 2-level (z,y,x) subsamp.
        'compression': None, # None, 'gzip', 'lzf'
        'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
        'transpose_xy': False, # in case X and Y axes need to be swapped for the correct tile positions
        }

'''
OME.ZARR parameters
This writer generates ome.zarr specification multiscale data on the fly during acquisition.
The default parameter should work pretty well for most setups with little to no performance degradation
during acquisition. Defaults include compression which will save disk space and can also improve
performance because less data is written to disk. Data are written into shards which limits the number of
files generated on disk.

Chunks can be set to adjust with each multiscale. Base and target chunks are defined and will start
with the base shape and automatically shift towards target with each scale. Chunks have a big influence on IO.
Bigger chunks means less and more efficient IO, very small chunks will degrade performance on some hardware.
Test on your hardware.

ome_version: default: "0.5". Selects whether to write ome-zarr v0.5 (zarr v3 and support for sharding) or
v0.4 (zarr v2 and NO support for sharding). If "0.4" is selected, the 'shards' option is ignored.

compression: default: zstd-5. This is a good trade off of compute and compression. In our tests, there is
little to no performance degradation when using this setting.

generate_multiscales: default: True. True will generate ome-zarr specification multiscale during acquisition.
False will only save the original resolution data.

shards are defined by default. Be careful, shard shape must be defined carefully to prevent performance
degradation. We suggest that shards are shallow in Z and as large as you camera sensor in XY.
For best performance set the base and target chunks to the same z-depth as your shards.

async_finalize: default: True. Enables acquisition of the next tile to proceed immediately while the multiscale
is finalized in the background. On systems with slow IO, data can accumulate in RAM and cause a crash.
Slow IO can be improved by using bigger chunks. If bigger chunks do not help, use async_finalize: False
to make mesoSPIM pause after each tile acquisition until the multiscale is finished generating.
'''
OME_Zarr_Writer = {
    'ome_version': '0.4', # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': True, #True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd', # None, 'zstd', 'lz4'
    'compression_level': 5, # 1-9
    'shards': (64,6000,6000), # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (256,256,256), # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (256,256,256), # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': True, # True, False

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True, # True, False
    'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False, # in case X and Y axes need to be swapped for the correct BigStitcher tile positions
    }

MP_OME_Zarr_Writer = {
    'ome_version': '0.4',  # 0.4 (zarr v2), 0.5 (zarr v3, sharding supported)
    'generate_multiscales': True, # True, False. False: only the primary data is saved. True: multiscale data is generated
    'compression': 'zstd',  # None, 'zstd', 'lz4'
    'compression_level': 5,  # 1-9
    'shards': (64, 6000, 6000),  # None or Tuple specifying max shard size. (axes: z,y,x), ignored if ome_version "0.4"
    'base_chunks': (256, 256, 256),
    # Tuple specifying starting chunk size (multiscale level 0). Bigger chunks, less files (axes: z,y,x)
    'target_chunks': (256, 256, 256),
    # Tuple specifying ending chunk size (multiscale highest level). Bigger chunks, less files (axes: z,y,x)
    'async_finalize': True,  # True, False

    # BigStitcher Specific Options
    'write_big_stitcher_xml': True,  # True, False
    'flip_xyz': (True, True, False),  # match BigStitcher coordinates to mesoSPIM axes.
    'transpose_xy': False,  # in case X and Y axes need to be swapped for the correct BigStitcher tile positions

    # Multiprocess options
    'ring_buffer_size': 16,  # Max number of images in shared memory ring buffer, 16 for simulation mode (eg laptop), 512 for production mode (fast workstation)

    # Write cache options. Write tile data to cache then move to acquisition folder
    # None acquires data direct to acquisition folder.
    'write_cache': None # None, 'e:/path/to/fast/ssd/write/cache'
}
