'''
Loading of mesoSPIM configuration files.

A config file is a plain Python module. A format-2 config is split in two:

* a *hardware file* that is the ground truth for one instrument (camera model,
  filter wheel and filters, galvo offsets and amplitudes, objectives, DAQ lines,
  stages, default writer settings),
* a *user file* that pulls it in with ``include('hardware/<rig>_hw.py')`` and then
  overrides only the values that deviate for this session.

Anything assigned after the ``include()`` call wins, because it is simply later
Python. Only the user file gets an ``include`` function, so a hardware file that
calls ``include()`` raises NameError: a config is never more than two levels deep.

Format-1 (single-file) configs load unchanged.
'''
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def load_config_from_file(path_to_config):
    '''
    Load a microscope configuration from a file using importlib
    '''
    path = Path(path_to_config).resolve()

    def include(rel_path):
        '''Copy all public names from another config file into this one.

        The path is relative to the file calling include(), so the same line works
        for a config in config/ and for a copy of it in config/examples/.
        '''
        hardware = _import_from_path(path.parent / rel_path)
        # Dunders are skipped so that cfg.__file__ keeps pointing at the user file:
        # save_parameters_to_config() and processor_chain.json are written next to it.
        config.__dict__.update({k: v for k, v in vars(hardware).items() if not k.startswith('__')})

    spec = importlib.util.spec_from_file_location(f'mesospim_config_{path.stem}', path)
    config = importlib.util.module_from_spec(spec)
    config.include = include
    spec.loader.exec_module(config)
    print(f'Configuration file loaded: {path_to_config}')
    return config


def _import_from_path(path):
    '''Import a hardware config file as a module.'''
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file includes '{path.name}', which does not exist: {path}")
    spec = importlib.util.spec_from_file_location(f'mesospim_config_hw_{path.stem}', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def is_demo(driver_name):
    '''True for any demo driver name: 'Demo', 'DemoCamera', 'DemoStage', ...'''
    return isinstance(driver_name, str) and 'demo' in driver_name.lower()


def check_zoom_keys(cfg):
    '''Raise if the zoom tables cannot work.

    pixelsize[zoom] is looked up while an acquisition is running, where a KeyError
    costs the whole run.
    '''
    only_in_one = set(cfg.zoomdict) ^ set(cfg.pixelsize)
    if only_in_one:
        raise ValueError(f"Config file: 'zoomdict' and 'pixelsize' must have the same keys, "
                         f"but {sorted(only_in_one)} appears in only one of them.")
    if cfg.startup['zoom'] not in cfg.zoomdict:
        raise ValueError(f"Config file: startup['zoom'] = {cfg.startup['zoom']!r} is not one of "
                         f"the zoom positions in 'zoomdict': {sorted(cfg.zoomdict)}.")
