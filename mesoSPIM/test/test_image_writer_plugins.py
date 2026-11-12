"""
The registered image writer plugins, the lookup by name, and the config warnings for the
removed single-core OME-Zarr writer.

Run from the mesoSPIM/ directory:  python -m pytest test/test_image_writer_plugins.py -q
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from mesoSPIM.src.plugins import manager
from mesoSPIM.src.plugins.utils import (
    get_image_writer_plugins, get_image_writer_from_name, get_image_writer_class_from_name,
    resolve_image_writer_name,
)
from mesoSPIM.src.utils.config_loader import load_config_from_file, retired_writer_warnings

CONFIG_DIR = Path(__file__).resolve().parents[1] / 'config'


@pytest.fixture(scope='module', autouse=True)
def registry():
    return manager.PluginRegistry(SimpleNamespace())


def test_single_core_ome_zarr_writer_is_gone():
    names = [w['name'] for w in get_image_writer_plugins()]
    assert 'MP_OME_Zarr_Writer' in names
    assert 'OME_Zarr_Writer' not in names


def test_retired_name_gives_the_multiprocess_writer():
    """Acquisition lists saved before the removal still name 'OME_Zarr_Writer'."""
    assert resolve_image_writer_name('OME_Zarr_Writer') == 'MP_OME_Zarr_Writer'
    assert resolve_image_writer_name('Tiff_Writer') == 'Tiff_Writer'
    assert get_image_writer_from_name('OME_Zarr_Writer')['name'] == 'MP_OME_Zarr_Writer'
    assert get_image_writer_class_from_name('OME_Zarr_Writer').name() == 'MP_OME_Zarr_Writer'


def test_config_with_single_core_writer_settings_warns():
    cfg = SimpleNamespace(OME_Zarr_Writer={'async_finalize': True},
                          plugins={'first_image_writer': 'OME_Zarr_Writer'},
                          MP_OME_Zarr_Writer={'async_finalize': False, 'compression': 'zstd'})
    warnings = retired_writer_warnings(cfg)
    assert len(warnings) == 3
    assert "'OME_Zarr_Writer' dictionary" in warnings[0]
    assert 'first_image_writer' in warnings[1]
    assert 'async_finalize' in warnings[2]


def test_demo_config_has_no_single_core_writer_settings():
    cfg = load_config_from_file(CONFIG_DIR / 'demo_config.py')
    assert retired_writer_warnings(cfg) == []
    assert retired_writer_warnings(load_config_from_file(CONFIG_DIR / 'examples' / 'demo_config_legacy.py')) == []
