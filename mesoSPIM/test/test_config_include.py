'''
Tests for the two-level config loader (mesoSPIM/src/utils/config_loader.py):
include() resolution, dict merging, override precedence, backward compatibility.

Run from the mesoSPIM/ directory:  python -m pytest test/test_config_include.py -q
'''
import importlib.util
import pathlib
import sys

import pytest

MESOSPIM_DIR = pathlib.Path(__file__).resolve().parents[1]

# Load config_loader.py by path, so the test works from any working directory
# and without importing PyQt5.
_spec = importlib.util.spec_from_file_location('mesospim_config_loader',
                                               MESOSPIM_DIR / 'src' / 'utils' / 'config_loader.py')
config_loader = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = config_loader
_spec.loader.exec_module(config_loader)
load_config_from_file = config_loader.load_config_from_file
update_startup_in_source = config_loader.update_startup_in_source


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def test_included_names_appear_in_parent(tmp_path):
    sub = write(tmp_path / 'sub.py', "camera = 'DemoCamera'\ncamera_parameters = {'x_pixels': 1024}\n")
    main = write(tmp_path / 'main.py', f"include({str(sub)!r})\n")
    cfg = load_config_from_file(main)
    assert cfg.camera == 'DemoCamera'
    assert cfg.camera_parameters == {'x_pixels': 1024}


def test_assignment_after_include_overrides(tmp_path):
    sub = write(tmp_path / 'sub.py', "camera = 'DemoCamera'\ncamera_parameters = {'x_pixels': 1024, 'y_pixels': 1024}\n")
    main = write(tmp_path / 'main.py',
                 f"include({str(sub)!r})\n"
                 "camera = 'HamamatsuOrca'\n"
                 "camera_parameters['x_pixels'] = 2048\n")
    cfg = load_config_from_file(main)
    assert cfg.camera == 'HamamatsuOrca'
    assert cfg.camera_parameters == {'x_pixels': 2048, 'y_pixels': 1024}


def test_same_named_dicts_merge_key_by_key(tmp_path):
    first = write(tmp_path / 'first.py', "startup = {'zoom': '1x', 'filter': 'Empty'}\n")
    second = write(tmp_path / 'second.py', "startup = {'zoom': '2x', 'laser': '488 nm'}\n")
    main = write(tmp_path / 'main.py', f"include({str(first)!r}, {str(second)!r})\n")
    cfg = load_config_from_file(main)
    # later include wins per key, keys of both are kept
    assert cfg.startup == {'zoom': '2x', 'filter': 'Empty', 'laser': '488 nm'}


def test_relative_paths_resolve_against_config_dir(tmp_path):
    main = write(tmp_path / 'main.py', "include('hardware/cameras/demo_camera.py')\n")
    cfg = load_config_from_file(main)
    assert cfg.camera == 'DemoCamera'


def test_legacy_config_without_include_still_loads(tmp_path):
    main = write(tmp_path / 'legacy.py', "camera = 'DemoCamera'\nstartup = {'zoom': '1x'}\n")
    cfg = load_config_from_file(main)
    assert cfg.camera == 'DemoCamera'
    assert cfg.startup == {'zoom': '1x'}
    assert getattr(cfg, 'config_format', 1) == 1


def test_missing_include_raises(tmp_path):
    main = write(tmp_path / 'main.py', "include('hardware/cameras/does_not_exist.py')\n")
    with pytest.raises(FileNotFoundError):
        load_config_from_file(main)


# Names the application reads off the config module. If the split demo config
# stops providing any of them, the GUI breaks at startup.
EXPECTED_ATTRIBUTES = (
    'microscope_parameters', 'plugins', 'ui_options', 'logging_level', 'sidepanel',
    'waveformgeneration', 'acquisition_hardware',
    'camera', 'camera_parameters', 'binning_dict',
    'stage_parameters',
    'laser', 'laserdict', 'laser_blanking',
    'shutter', 'shutterswitch', 'shutteroptions', 'shutterdict',
    'filterwheel_parameters', 'filterdict',
    'zoom_parameters', 'zoomdict', 'pixelsize',
    'scale_galvo_amp_with_zoom',
    'H5_BDV_Writer', 'OME_Zarr_Writer', 'MP_OME_Zarr_Writer',
    'startup',
)

EXPECTED_STARTUP_KEYS = (
    'state', 'samplerate', 'sweeptime', 'position', 'ETL_cfg_file',
    'folder', 'snap_folder', 'file_prefix', 'file_suffix',
    'zoom', 'pixelsize', 'laser', 'max_laser_voltage', 'intensity',
    'shutterstate', 'shutterconfig', 'laser_interleaving', 'filter',
    'etl_l_delay_%', 'etl_l_ramp_rising_%', 'etl_l_ramp_falling_%', 'etl_l_amplitude', 'etl_l_offset',
    'etl_r_delay_%', 'etl_r_ramp_rising_%', 'etl_r_ramp_falling_%', 'etl_r_amplitude', 'etl_r_offset',
    'galvo_l_frequency', 'galvo_l_amplitude', 'galvo_l_offset', 'galvo_l_duty_cycle', 'galvo_l_phase',
    'galvo_r_frequency', 'galvo_r_offset', 'galvo_r_duty_cycle', 'galvo_r_phase',
    'laser_l_delay_%', 'laser_l_pulse_%', 'laser_l_max_amplitude_%',
    'laser_r_delay_%', 'laser_r_pulse_%', 'laser_r_max_amplitude_%',
    'camera_delay_%', 'camera_pulse_%', 'camera_exposure_time',
    'camera_display_live_subsampling', 'camera_display_acquisition_subsampling',
    'camera_display_temporal_subsampling', 'camera_binning',
    'average_frame_rate',
)  # 'camera_line_interval' is Hamamatsu-only and optional, so it is not required here


def test_save_back_substitutes_existing_keys():
    source = "startup = {\n'sweeptime' : 0.2, # comment kept\n'zoom' : '1x',\n}\n"
    new, updated, appended = update_startup_in_source(source, {'sweeptime': 0.5})
    assert updated == ['sweeptime'] and appended == []
    assert "'sweeptime' : 0.5, # comment kept" in new


def test_save_back_ignores_commented_out_lines():
    source = "startup.update({'folder': 'D:/tmp/'})\n# startup.update({'sweeptime': 0.05})\n"
    new, updated, appended = update_startup_in_source(source, {'sweeptime': 0.5})
    assert updated == [] and appended == ['sweeptime']
    assert "# startup.update({'sweeptime': 0.05})" in new  # comment untouched


def test_save_back_appends_then_substitutes_in_place():
    source = "include('hardware/DAQ/demo_daq.py')\n"
    once, updated, appended = update_startup_in_source(source, {'sweeptime': 0.5})
    assert appended == ['sweeptime']
    assert 'startup.update({' in once
    # second save finds the appended key and rewrites it instead of appending again
    twice, updated, appended = update_startup_in_source(once, {'sweeptime': 0.7})
    assert updated == ['sweeptime'] and appended == []
    assert twice.count('startup.update({') == 1
    assert '0.7' in twice and '0.5' not in twice


def test_demo_config_provides_everything_the_app_reads():
    cfg = load_config_from_file(MESOSPIM_DIR / 'config' / 'demo_config.py')
    assert cfg.config_format == 2
    missing = [name for name in EXPECTED_ATTRIBUTES if not hasattr(cfg, name)]
    assert missing == []
    missing_keys = [key for key in EXPECTED_STARTUP_KEYS if key not in cfg.startup]
    assert missing_keys == []
