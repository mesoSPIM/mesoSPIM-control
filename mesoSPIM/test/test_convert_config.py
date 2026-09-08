'''
Tests for the legacy -> two-level config converter (mesoSPIM/src/utils/convert_config.py).

Run from the mesoSPIM/ directory:  python -m pytest test/test_convert_config.py -q
'''
import importlib.util
import pathlib
import sys

MESOSPIM_DIR = pathlib.Path(__file__).resolve().parents[1]

# Load by path: no PyQt5, and works from any working directory.
sys.path.insert(0, str(MESOSPIM_DIR.parent))
_spec = importlib.util.spec_from_file_location('mesospim_convert_config',
                                               MESOSPIM_DIR / 'src' / 'utils' / 'convert_config.py')
convert_config = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = convert_config
_spec.loader.exec_module(convert_config)


def test_demo_config_round_trip(tmp_path):
    '''
    The hand-written two-level demo config must be what the converter produces:
    same include list, and no setting of the original lost.
    '''
    source = MESOSPIM_DIR / 'config' / 'demo_config.py'
    text, includes, notes = convert_config.convert(source)
    assert [path for path, _ in includes] == [
        'hardware/cameras/demo_camera.py', 'hardware/DAQ/demo_daq.py',
        'hardware/stages/demo_stage.py', 'hardware/lasers/demo_lasers.py',
        'hardware/filterwheels/demo_filterwheel.py', 'hardware/objectives/demo_zoom.py',
        'hardware/galvos/demo_galvos.py', 'hardware/ETLs/demo_etl.py',
        'plugins/writers/default_writers.py', 'UI/default_ui.py']
    assert notes == []

    target = MESOSPIM_DIR / 'config' / '_test_converted.py'  # inside config/ for include() paths
    try:
        target.write_text(text, encoding='utf-8')
        differences, additions = convert_config.verify(source, target)
    finally:
        target.unlink(missing_ok=True)
    assert differences == [] and additions == []


def test_legacy_config_settings_survive(tmp_path):
    '''
    A single-file config keeps every value it sets. The camera file is recognised by the driver
    name ('DemoCamera') even though every value in it differs, and those values are overridden.
    '''
    source = tmp_path / 'legacy.py'
    source.write_text("camera = 'DemoCamera'\n"
                      "camera_parameters = {'x_pixels': 999, 'y_pixels': 999}\n"
                      "logging_level = 'WARNING'\n"
                      "startup = {'zoom': '1x', 'camera_exposure_time': 0.123}\n", encoding='utf-8')
    text, includes, _ = convert_config.convert(source)
    assert 'hardware/cameras/demo_camera.py' in [path for path, _ in includes]

    target = MESOSPIM_DIR / 'config' / '_test_converted.py'
    try:
        target.write_text(text, encoding='utf-8')
        differences, _ = convert_config.verify(source, target)
    finally:
        target.unlink(missing_ok=True)
    assert differences == []


def test_label_dicts_are_replaced_not_merged(tmp_path):
    '''A shorter filterdict must not gain filters that are not in the wheel.'''
    source = tmp_path / 'legacy.py'
    source.write_text("filterwheel_parameters = {'filterwheel_type': 'ZWO', 'COMport': 'COM1'}\n"
                      "filterdict = {'Empty-Alignment': 0}\n"
                      "startup = {'filter': 'Empty-Alignment'}\n", encoding='utf-8')
    text, _, _ = convert_config.convert(source)

    target = MESOSPIM_DIR / 'config' / '_test_converted.py'
    try:
        target.write_text(text, encoding='utf-8')
        differences, additions = convert_config.verify(source, target)
    finally:
        target.unlink(missing_ok=True)
    assert differences == []
    assert not [item for item in additions if item.startswith('filterdict')]
