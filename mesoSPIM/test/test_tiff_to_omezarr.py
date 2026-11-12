"""Tests for mesoSPIM/src/utils/tiff_to_omezarr.py (TIFF -> OME-Zarr converter)."""
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import tifffile
import zarr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'utils'))
import tiff_to_omezarr as t2z  # noqa: E402

SMALL = dict(shards=(16, 256, 256), base_chunks=(16, 64, 64), target_chunks=(16, 32, 32))


def _ramp(z, y, x, seed=0, dtype=np.uint16):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 4000, size=(z, y, x)).astype(dtype)


def _scale(group, level):
    attrs = group.attrs.asdict()
    ms = attrs['ome']['multiscales'][0] if 'ome' in attrs else attrs['multiscales'][0]
    return ms['datasets'][level]['coordinateTransformations'][0]['scale']


def _write_mesospim_tile(path, data, laser, x_pos, y_pos, px=0.85, dz=5.0):
    # same tags as the mesoSPIM TiffWriter: ImageJ, resolution in px/um, spacing = z step
    tifffile.imwrite(path, data, imagej=True, resolution=(1 / px, 1 / px),
                     metadata={'spacing': dz, 'unit': 'um', 'axes': 'ZYX'})
    with open(str(path) + '_meta.txt', 'w') as f:
        for k, v in [('Laser', laser), ('Zoom', '5x'), ('Pixelsize in um', px), ('Shutter', 'Left'),
                     ('x_pos', x_pos), ('y_pos', y_pos), ('z_start', 100.0), ('z_stepsize', dz), ('rot', 0)]:
            f.write(f'[{k}] {v}\n')


def test_mesospim_tiles_and_channels(tmp_path):
    files, data = [], {}
    for tile, (x, y) in enumerate([(0.0, 0.0), (1000.0, 0.0)]):
        for laser in ('488 nm', '561 nm'):
            p = tmp_path / f'tile{tile}_{laser[:3]}.tif'
            d = _ramp(40, 200, 120, seed=tile * 10 + int(laser[:3]))
            _write_mesospim_tile(p, d, laser, x, y)
            files.append(str(p))
            data[p.name] = d

    sources = t2z.collect_sources(files)
    assert [s.voxel_zyx for s in sources] == [[5.0, 0.85, 0.85]] * 4
    assert sorted({s.tile for s in sources}) == [0, 1]
    assert sorted({s.channel for s in sources}) == [0, 1]

    out = t2z.convert(sources, tmp_path / 'out.ome.zarr', {**SMALL, 'levels': 3}, log=lambda m: None)
    for s in sources:
        g = zarr.open_group(os.path.join(out, s.name), mode='r')
        np.testing.assert_array_equal(g['0'][:], data[os.path.basename(s.path)])
        assert len([k for k in g.array_keys()]) == 3
        assert _scale(g, 0) == [5.0, 0.85, 0.85]
        assert g['0'].shards is not None

    root = ET.parse(out + '.xml').getroot()
    assert root.find('.//ImageLoader').get('zarr.version') == 'ZarrV3'
    sizes = {e.text for e in root.iter('voxelSize') for e in e.iter('size')}
    assert sizes == {'0.85 0.85 5.0'}
    labels = [c.find('name').text for c in root.iter('Channel')]
    assert labels == ['488nm', '561nm']


def test_default_options_match_request():
    d = t2z.DEFAULT_OPTIONS
    assert (d['ome_version'], d['levels'], d['compression'], d['compression_level']) == ('0.5', 5, 'zstd', 5)
    assert d['shards'] is not None and d['shards'][0] == d['base_chunks'][0]
    assert t2z.check_options(d) == []


def test_ome_tiff_voxel_size_kept(tmp_path):
    p = tmp_path / 'stack.ome.tif'
    d = _ramp(70, 300, 260)
    tifffile.imwrite(p, d, ome=True, metadata={'axes': 'ZYX', 'PhysicalSizeX': 0.4, 'PhysicalSizeY': 0.5,
                                               'PhysicalSizeZ': 2.0, 'PhysicalSizeXUnit': 'µm'})
    [s] = t2z.collect_sources([str(p)])
    assert s.voxel_zyx == [2.0, 0.5, 0.4] and 'OME' in s.voxel_source
    out = t2z.convert([s], tmp_path / 'o', {**SMALL, 'levels': 5, 'write_big_stitcher_xml': False},
                      log=lambda m: None)
    g = zarr.open_group(os.path.join(out, s.name), mode='r')
    np.testing.assert_array_equal(g['0'][:], d)
    assert _scale(g, 0) == [2.0, 0.5, 0.4]
    assert len(list(g.array_keys())) == 5
    assert out.endswith('o.ome.zarr')


def test_imagej_hyperstack_channels_split(tmp_path):
    p = tmp_path / 'hyper.tif'
    d = _ramp(12 * 2, 64, 80).reshape(12, 2, 64, 80)
    tifffile.imwrite(p, d, imagej=True, resolution=(1 / 0.3, 1 / 0.3),
                     metadata={'axes': 'ZCYX', 'spacing': 1.5, 'unit': 'um'})
    sources = t2z.collect_sources([str(p)])
    assert len(sources) == 2 and [s.channel for s in sources] == [0, 1]
    out = t2z.convert(sources, tmp_path / 'h.ome.zarr', {**SMALL, 'levels': 2, 'ome_version': '0.4'},
                      log=lambda m: None)
    for c, s in enumerate(sources):
        g = zarr.open_group(os.path.join(out, s.name), mode='r')
        np.testing.assert_array_equal(g['0'][:], d[:, c])
        assert _scale(g, 0) == [1.5, 0.3, 0.3]


def test_signed_int16_scanimage_like(tmp_path):
    """Non-mesoSPIM TIFF: int16 with a few negatives, voxel size only in resolution tags (px/cm)."""
    p = tmp_path / 'si.tif'
    d = _ramp(20, 64, 64, dtype=np.int16)
    d[0, 0, :5] = -7
    tifffile.imwrite(p, d, resolution=(1e4 / 0.268, 1e4 / 0.268), resolutionunit='CENTIMETER')
    [s] = t2z.collect_sources([str(p)], fallback_voxel=(0.3, 9.0, 9.0))  # fallback only fills z
    assert s.voxel_zyx[0] == 0.3 and s.voxel_zyx[1] == pytest.approx(0.268, rel=1e-5)

    logs = []
    out = t2z.convert([s], tmp_path / 'c.ome.zarr', {**SMALL, 'levels': 1}, log=logs.append)
    a = zarr.open_group(os.path.join(out, s.name), mode='r')['0'][:]
    np.testing.assert_array_equal(a, np.clip(d, 0, None).astype(np.uint16))
    assert any('5 negative values' in m for m in logs)

    out = t2z.convert([s], tmp_path / 's.ome.zarr', {**SMALL, 'levels': 1, 'signed_integers': 'shift'},
                      log=lambda m: None)
    a = zarr.open_group(os.path.join(out, s.name), mode='r')['0'][:]
    np.testing.assert_array_equal(a, (d.astype(np.int32) + 32768).astype(np.uint16))

    with pytest.raises(ValueError, match='negative'):
        t2z.convert([s], tmp_path / 'e.ome.zarr', {**SMALL, 'levels': 1, 'signed_integers': 'error'},
                    log=lambda m: None)


def test_scanimage_z_step_from_metadata():
    frame = {'SI.hStackManager.actualStackZStepSize': -0.3000000000000682,
             'SI.hRoiManager.imagingFovUm': [[-10, -10], [10, -10], [10, 10], [-10, 10]],
             'SI.hRoiManager.pixelsPerLine': 100, 'SI.hRoiManager.linesPerFrame': 50}

    class FakePage:
        tags = {}

    class FakeTif:
        is_ome = False
        ome_metadata = None
        imagej_metadata = None
        pages = [FakePage()]
        scanimage_metadata = {'FrameData': frame}

    (z, y, x), src = t2z.read_tiff_voxel_size(FakeTif())
    assert src == 'ScanImage'
    assert abs(z - 0.3) < 1e-9 and x == pytest.approx(0.2) and y == pytest.approx(0.4)


def test_unknown_voxel_size_is_refused(tmp_path):
    p = tmp_path / 'plain.tif'
    tifffile.imwrite(p, _ramp(9, 32, 32))
    [s] = t2z.collect_sources([str(p)])
    assert not s.voxel_known
    with pytest.raises(ValueError, match='voxel size unknown'):
        t2z.convert([s], tmp_path / 'x', SMALL, log=lambda m: None)
    assert t2z.main([str(p), '-o', str(tmp_path / 'cli.ome.zarr'), '--voxel-size', '2,1,1',
                     '--shards', '16,256,256', '--base-chunks', '16,64,64', '--levels', '2']) == 0
    g = zarr.open_group(str(tmp_path / 'cli.ome.zarr' / 'plain.ome.zarr'), mode='r')
    assert _scale(g, 0) == [2.0, 1.0, 1.0]


def test_auto_chunk_exact_divisor_closest_to_512():
    assert t2z.auto_chunk(5056) == 632     # 5056 / 8
    assert t2z.auto_chunk(2960) == 592     # 2960 / 5
    assert t2z.auto_chunk(2048) == 512
    assert t2z.auto_chunk(512) == 512
    assert t2z.auto_chunk(300) == 300      # smaller than 512: one chunk
    assert t2z.auto_chunk(4099) == 513     # prime: ceil(4099 / 8), no exact divisor near 512
    assert t2z.auto_chunk(700) == 350      # 350 is closer to 512 than 700
    assert t2z.resolve_chunks((64, 'auto', 'auto'), (100, 5056, 2960)) == (64, 632, 592)
    assert t2z.DEFAULT_OPTIONS['base_chunks'] == (64, 'auto', 'auto')


def test_auto_chunks_written(tmp_path):
    p = tmp_path / 'a.tif'
    d = _ramp(10, 1200, 700)
    tifffile.imwrite(p, d, imagej=True, resolution=(1, 1), metadata={'axes': 'ZYX', 'spacing': 2, 'unit': 'um'})
    [s] = t2z.collect_sources([str(p)])
    out = t2z.convert([s], tmp_path / 'a.ome.zarr', {'base_chunks': (16, 'auto', 'auto'), 'shards': (16, 6000, 6000),
                                                    'levels': 2}, log=lambda m: None)
    a = zarr.open_group(os.path.join(out, s.name), mode='r')['0']
    assert a.chunks == (10, 600, 350) and a.shards == (10, 1200, 700)   # 1200/2, 700/2
    np.testing.assert_array_equal(a[:], d)


def test_long_paths_get_short_group_names(tmp_path):
    long_stem = 'ROI_04_Top_Zoom_8x_8avg_Zstep_0p3um_512x512_Power_18_XYMotorsOFF_00001_' + 'x' * 120
    p = tmp_path / (long_stem + '.tif')
    tifffile.imwrite(p, _ramp(6, 32, 32), imagej=True, resolution=(1, 1),
                     metadata={'axes': 'ZYX', 'spacing': 1, 'unit': 'um'})
    [s] = t2z.collect_sources([str(p)])
    logs = []
    out = t2z.convert([s], tmp_path / (long_stem[:60] + '.ome.zarr'), {**SMALL, 'levels': 1}, log=logs.append)
    assert s.name == 'Tile0_Ch0.ome.zarr'
    assert any('short image names' in m for m in logs)
    root = zarr.open_group(out, mode='r')
    assert root.attrs['tiff_to_omezarr']['images']['Tile0_Ch0.ome.zarr']['source'] == str(p)
    longest = max(len(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    assert longest <= t2z.MAX_PATH_SAFE or len(str(tmp_path)) > 120


def test_z_crop(tmp_path):
    files, data = [], []
    for tile in range(2):
        p = tmp_path / f'tile{tile}.tif'
        d = _ramp(40, 64, 48, seed=tile)
        _write_mesospim_tile(p, d, '488 nm', 1000.0 * tile, 0.0)  # z_start 100 um, z step 5 um
        files.append(str(p))
        data.append(d)
    sources = t2z.collect_sources(files)
    out = t2z.convert(sources, tmp_path / 'c.ome.zarr', {**SMALL, 'levels': 2, 'z_start': 10, 'z_end': 25},
                      log=lambda m: None)
    for s, d in zip(sources, data):
        g = zarr.open_group(os.path.join(out, s.name), mode='r')
        np.testing.assert_array_equal(g['0'][:], d[10:25])
        transforms = g.attrs['ome']['multiscales'][0]['datasets'][0]['coordinateTransformations']
        assert transforms[1]['translation'][0] == 100.0 + 10 * 5.0
    assert sources[0].shape_zyx[0] == 40  # the caller's sources are not changed
    root = ET.parse(out + '.xml').getroot()
    assert {vs.find('size').text for vs in root.iter('ViewSetup')} == {'48 64 15'}
    images = zarr.open_group(out, mode='r').attrs['tiff_to_omezarr']['images']
    assert images[sources[0].name]['z_planes_of_source'] == [10, 25]

    # z_end past the stack is clamped; z_start past it is an error
    out = t2z.convert(sources[:1], tmp_path / 'd.ome.zarr', {**SMALL, 'levels': 1, 'z_start': 30, 'z_end': 999},
                      log=lambda m: None)
    np.testing.assert_array_equal(zarr.open_group(os.path.join(out, sources[0].name), mode='r')['0'][:],
                                  data[0][30:])
    with pytest.raises(ValueError, match='outside'):
        t2z.convert(sources[:1], tmp_path / 'e.ome.zarr', {**SMALL, 'z_start': 40}, log=lambda m: None)
    assert t2z.check_options({**t2z.DEFAULT_OPTIONS, 'z_start': 5, 'z_end': 5})
