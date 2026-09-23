"""
Tests for the two-file (format 2) config files.

Run from the mesoSPIM/ directory:  python -m pytest test/test_config_format2.py -q

No PyQt5 and no hardware needed: the config loader and the converter are plain Python.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from mesoSPIM.src.utils.config_loader import load_config_from_file, check_zoom_keys, is_demo
from mesoSPIM.src.utils.convert_config import split_config, _namespace

CONFIG_DIR = REPO_ROOT / 'mesoSPIM' / 'config'
DEMO_CONFIG = CONFIG_DIR / 'demo_config.py'
LEGACY_CONFIG = CONFIG_DIR / 'examples' / 'demo_config_legacy.py'


def test_two_file_config_loads():
    """The demo config pulls its hardware in with include() and overrides the session keys."""
    cfg = load_config_from_file(DEMO_CONFIG)

    assert cfg.config_format == 2
    assert cfg.camera_parameters['x_pixels'] > 0      # came from the hardware file
    assert cfg.startup['folder']                      # came from the user file
    # __file__ must stay the user file: save_parameters_to_config() writes next to it
    assert Path(cfg.__file__).name == 'demo_config.py'


def test_hardware_file_cannot_include(tmp_path):
    """Only the user file gets include(), so configs are never more than two levels deep."""
    (tmp_path / 'hardware').mkdir()
    (tmp_path / 'hardware' / 'deep_hw.py').write_text("include('deeper.py')\n", encoding='utf-8')
    (tmp_path / 'user.py').write_text("include('hardware/deep_hw.py')\n", encoding='utf-8')

    with pytest.raises(NameError, match='include'):
        load_config_from_file(tmp_path / 'user.py')


def test_format1_config_still_loads():
    """Single-file configs keep working, and report format 1."""
    cfg = load_config_from_file(LEGACY_CONFIG)

    assert getattr(cfg, 'config_format', 1) == 1
    check_zoom_keys(cfg)


def test_converted_config_matches_the_original(tmp_path):
    """The pair produced by the converter defines exactly what the single file defined."""
    split_config(LEGACY_CONFIG, tmp_path)

    old = _namespace(load_config_from_file(LEGACY_CONFIG))
    new = _namespace(load_config_from_file(tmp_path / LEGACY_CONFIG.name))
    assert old == new

    hardware_text = (tmp_path / 'hardware' / 'demo_config_legacy_hw.py').read_text(encoding='utf-8')
    assert "'folder'" not in hardware_text


def test_converting_twice_is_refused(tmp_path):
    """A user file has no session settings left to split out, and would lose its include()."""
    split_config(LEGACY_CONFIG, tmp_path)

    with pytest.raises(ValueError, match='already in the two-file format'):
        split_config(tmp_path / LEGACY_CONFIG.name, tmp_path)


def test_zoom_keys_must_match():
    """pixelsize[zoom] is read during an acquisition, where a KeyError costs the whole run."""
    cfg = load_config_from_file(DEMO_CONFIG)
    check_zoom_keys(cfg)

    cfg.pixelsize.pop(next(iter(cfg.pixelsize)))
    with pytest.raises(ValueError, match='same keys'):
        check_zoom_keys(cfg)

    cfg = load_config_from_file(DEMO_CONFIG)
    cfg.startup['zoom'] = 'no such zoom'
    with pytest.raises(ValueError, match='not one of'):
        check_zoom_keys(cfg)


@pytest.mark.parametrize('name, expected', [
    ('Demo', True), ('DemoCamera', True), ('DemoStage', True), ('DemoZoom', True),
    ('DemoWaveFormGeneration', True), ('demo', True),
    ('HamamatsuOrca', False), ('PI', False), ('NI', False), (None, False),
])
def test_is_demo(name, expected):
    assert is_demo(name) is expected
