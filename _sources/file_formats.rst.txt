Output File Formats
======================

mesoSPIM-control writes acquired image data through a pluggable **image
writer** system. Each acquisition entry in the Acquisition Manager selects
its own writer via the file-naming wizard, so a single acquisition list can
mix formats across rows if needed.

.. tip::

   Not sure which one to pick?

   * **Tiff_Writer** (ImageJ-TIFF) for the broadest compatibility with
     external viewers and stitchers — the safest default if you're not sure
     what your downstream tools support.
   * **MP_OME_Zarr_Writer** for new acquisitions on a fast (NVMe/SSD) system
     — natively saves multi-resolution pyramids with compression, and won't
     stall acquisition on disk I/O.
   * **H5_BDV_Writer** for the easiest BigStitcher stitching workflow. See
     the caveats below before relying on it for Imaris.

At a glance
-------------

.. list-table::
   :widths: 20 12 14 14 14 26
   :header-rows: 1

   * - Writer
     - Extension
     - Files per acquisition
     - Pyramid
     - Compression
     - Notes
   * - ``MP_OME_Zarr_Writer``
     - ``.ome.zarr``
     - One store (per-tile subgroups)
     - Yes
     - zstd / lz4
     - Writes in a background process; recommended default
   * - ``OME_Zarr_Writer``
     - ``.ome.zarr`` / ``.zarr``
     - One store (per-tile subgroups)
     - Yes
     - zstd / lz4
     - Single-core; same format as above
   * - ``H5_BDV_Writer``
     - ``.h5``
     - One file (all tiles)
     - Not in practice :sup:`†`
     - gzip / lzf / none
     - Easiest BigStitcher stitching workflow; Imaris-compatible only for a single-tile, uncompressed, pyramid-free dataset
   * - ``Tiff_Writer``
     - ``.tif`` / ``.tiff``
     - One per tile/channel
     - No
     - No
     - ImageJ-compatible; broadest compatibility with external viewers/stitchers
   * - ``Big_Tiff_Writer``
     - ``.btf`` / ``.tf2`` / ``.tf8``
     - One per tile/channel
     - No
     - No
     - Same as TIFF, in the BigTIFF container format
   * - ``RAW_Writer``
     - ``.raw``
     - One per tile/channel
     - No
     - No
     - Uncompressed uint16 binary dump, no metadata

:sup:`†` ``H5_BDV_Writer`` accepts a pyramid (``subsamp``) option, but
generating it during acquisition is slow enough (see below) that it's not
used in practice.

Selecting a writer
---------------------

Pick the writer for each acquisition entry in the **file-naming wizard**.
The ``plugins['first_image_writer']`` setting in the config file only
controls which writer is pre-selected/listed first there — it does not
restrict which writers are available:

.. code-block:: python

   plugins = {
       'path_list': ["../src/plugins"],
       'first_image_writer': 'OME_Zarr_Writer',
   }

See :doc:`configuration` for the full ``plugins`` config reference.

OME-Zarr (``OME_Zarr_Writer`` / ``MP_OME_Zarr_Writer``)
----------------------------------------------------------

Both write the same `OME-Zarr <https://ngff.openmicroscopy.org/>`_ format —
one ``.ome.zarr`` store per acquisition, with each tile in its own subgroup
— and accept identical configuration. The only difference is *how* the
writing happens:

* **``OME_Zarr_Writer``** writes on the main acquisition thread (single-core).
* **``MP_OME_Zarr_Writer``** offloads writing to a separate background
  process via a shared-memory ring buffer, so a slow disk can't stall
  acquisition. This is the **recommended writer for new acquisitions** on
  systems with fast (NVMe/SSD) storage.

Both save multi-resolution pyramids natively, with compression, and can
optionally emit an XML file for drag-and-drop stitching in BigStitcher.

.. code-block:: python

   OME_Zarr_Writer = {
       'ome_version': '0.5',          # '0.4' (zarr v2) or '0.5' (zarr v3, sharding supported)
       'generate_multiscales': True,  # False: only save the original resolution
       'compression': 'zstd',         # None, 'zstd', 'lz4'
       'compression_level': 5,        # 1-9
       'shards': (64, 6000, 6000),    # max shard size (z,y,x); ignored if ome_version == '0.4'
       'base_chunks': (64, 256, 256),   # starting chunk size (level 0), (z,y,x)
       'target_chunks': (64, 64, 64),   # chunk size at the highest pyramid level, (z,y,x)
       'async_finalize': True,        # let the next tile start before this one's pyramid finishes

       # BigStitcher-specific
       'write_big_stitcher_xml': True,       # only takes effect for ome_version == '0.4'
       'flip_xyz': (True, True, False),      # match BigStitcher coordinates to mesoSPIM axes
       'transpose_xy': False,                # swap X/Y if tile positions come out wrong
   }

   MP_OME_Zarr_Writer = {
       # ... same keys as above, plus:
       'ring_buffer_size': 512,  # frames buffered in shared memory; lower (e.g. 16) for demo/simulation mode
       'write_cache': None,      # optional fast local scratch path, moved to the final folder once a tile finishes
   }

.. note::

   The BigStitcher XML export only works with ``ome_version: '0.4'`` (zarr
   v2). Choosing ``'0.5'`` gets you sharding (fewer files on disk) but no
   BigStitcher XML.

.. important::

   Bigger chunks/shards generally mean fewer, more efficient files; very
   small chunks can noticeably slow down writing on some hardware. The
   defaults above are a reasonable starting point — benchmark on your own
   hardware before changing them for a real acquisition.

H5_BDV_Writer
----------------

Writes all tiles of the acquisition into a **single** ``.h5`` file in
`BigDataViewer <https://imagej.net/plugins/bdv/>`_ format, plus a companion
BigDataViewer/BigStitcher XML — the **easiest stitching workflow in
BigStitcher** of any of the writers here.

.. code-block:: python

   H5_BDV_Writer = {
       'subsamp': ((1, 1, 1),),         # e.g. ((1,1,1), (1,4,4)) for a 2-level (z,y,x) pyramid
       'compression': None,             # None, 'gzip', 'lzf'
       'flip_xyz': (True, True, False), # match BigStitcher coordinates to mesoSPIM axes
       'transpose_xy': False,           # swap X/Y if tile positions come out wrong
   }

.. warning::

   ``subsamp`` (multiscale pyramid) is technically available but **not used
   in practice** — generating pyramids and/or compressing on the fly during
   acquisition can slow writing down by **5-10×**, which most acquisitions
   can't afford. Leave both at their defaults (no subsampling, no
   compression) unless you've specifically benchmarked otherwise.

.. important::

   **Imaris can only open these files if the dataset has a single tile
   (one position, no mosaic), with no compression and no multiscale
   pyramid.**

Tiff_Writer / Big_Tiff_Writer
---------------------------------

One plain, uncompressed, ImageJ-compatible TIFF stack per tile, no pyramid.
``Tiff_Writer`` (regular TIFF) and ``Big_Tiff_Writer`` (the BigTIFF
container format) are both **not limited to 4 GB per file** — pick either;
``Tiff_Writer``'s plain ImageJ-TIFF output has the broadest compatibility
with external viewers and stitchers, and is a safe default if you're unsure
what your downstream tools support. Filenames from both follow the
BigStitcher auto-loader naming convention, so individual-TIFF acquisitions
can still be imported into BigStitcher.

RAW_Writer
-------------

The simplest possible option: a single uncompressed ``uint16`` binary file
per tile (no header, no metadata), written via a direct memory-mapped array.
Useful for custom downstream pipelines that read raw binary directly, or as
a baseline for debugging I/O performance issues in the other writers.

Writer capabilities
-----------------------

.. list-table::
   :widths: 25 15 15 15 15 15
   :header-rows: 1

   * - Writer
     - Chunking
     - Compression
     - Multiscale
     - Overwrite existing
     - dtypes
   * - ``MP_OME_Zarr_Writer``
     - Yes
     - Yes
     - Yes
     - No
     - uint16
   * - ``OME_Zarr_Writer``
     - Yes
     - Yes
     - Yes
     - No
     - uint16
   * - ``H5_BDV_Writer``
     - No
     - No :sup:`*`
     - No :sup:`*`
     - No
     - uint8, uint16, float32
   * - ``Tiff_Writer``
     - No
     - No
     - No
     - No
     - uint8, uint16, float32
   * - ``Big_Tiff_Writer``
     - No
     - No
     - No
     - No
     - uint8, uint16, float32
   * - ``RAW_Writer``
     - No
     - No
     - No
     - No
     - uint16

:sup:`*` ``H5_BDV_Writer`` declares ``supports_compression=False`` and
``supports_multiscale=False`` in its plugin capabilities, but its
``compression`` and ``subsamp`` config keys (above) do work at runtime — a
known inconsistency between the declared capability flags and actual
behavior, not a documentation error.

For the plugin architecture itself (writing a new writer, the
``ImageWriter`` interface, discovery rules), see :doc:`plugins`.
