'''
Loader for mesoSPIM configuration files.

A config file is a plain Python module. Two forms are supported:

1. Legacy (single file): all variables defined in one file. Nothing to do.
2. Two-level: the user-facing file calls include() to pull in shared hardware
   definitions from mesoSPIM/config/hardware/ and mesoSPIM/config/plugins/,
   then overrides whatever is specific to that user.

include() is injected into the config module namespace before execution, so
config files call it without importing anything.

Rules:
* Names assigned in the file after include() win (plain Python assignment).
* Dicts with the same name are merged key-by-key, so a partial `startup` dict
  can be contributed by several hardware files (later include wins per key).
* A file that never calls include() behaves exactly as before.
* Only the user file may include: an included file that calls include() raises,
  so a config is never more than two levels deep.
'''

import importlib.util
import os
import re
import time
import types

package_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # mesoSPIM/
CONFIG_DIR = os.path.join(package_directory, 'config')


def _make_include(target_dict, included=False):
    '''Create the include() function bound to the namespace of one config module.'''
    def include(*rel_paths):
        if included:
            raise ValueError("include() is only allowed in the user config file. An included "
                             "hardware file must not include another one: chains of config "
                             "files are hard to follow. Repeat the few settings instead.")
        for rel in rel_paths:
            path = rel if os.path.isabs(rel) else os.path.join(CONFIG_DIR, rel)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Config include not found: {path} (from '{rel}')")
            sub = load_config_from_file(path, included=True)
            for name, value in vars(sub).items():
                if name.startswith('__') or name == 'include' or isinstance(value, types.ModuleType):
                    continue
                current = target_dict.get(name)
                if isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)  # shallow merge: later include wins per key
                else:
                    target_dict[name] = value
    return include


def load_config_from_file(path_to_config, included=False):
    '''
    Load a microscope configuration from a file using importlib.

    included=True marks a file pulled in by include(); such a file may not include further
    files, so that a config is always at most two levels deep.
    '''
    spec = importlib.util.spec_from_file_location('module.name', path_to_config)
    config = importlib.util.module_from_spec(spec)
    config.include = _make_include(config.__dict__, included)
    spec.loader.exec_module(config)
    print(f'Configuration file loaded: {path_to_config}')
    return config


def is_demo(driver_name):
    '''
    Does this config value ask for a simulated device?

    Every driver name containing 'demo' selects the demo device, so 'Demo' works everywhere
    and the older spellings of the config files keep working: 'DemoCamera',
    'DemoWaveFormGeneration', 'DemoStage', 'DemoZoom', 'DemoFilterWheel'.
    '''
    return isinstance(driver_name, str) and 'demo' in driver_name.lower()


def check_zoom_and_pixelsize(zoomdict, pixelsize, startup, camera_parameters):
    '''
    Check that the zoom settings of a config file are consistent.

    Returns (errors, warnings), both lists of messages. An error means the configuration
    cannot work: mesoSPIM looks up pixelsize[zoom] for the metadata, the tile view and the
    scale bar, so a zoom without a pixel size raises a KeyError in the middle of an
    acquisition. A warning means a value looks wrong but the software runs.
    '''
    errors, warnings = [], []
    only_in_one = set(zoomdict) ^ set(pixelsize)
    if only_in_one:
        errors.append(f"'zoomdict' and 'pixelsize' must have the same keys, but "
                      f"{sorted(only_in_one)} appear only in one of them.")

    zoom = startup.get('zoom')
    if zoom not in zoomdict:
        errors.append(f"startup['zoom'] = {zoom!r} is not one of the zoom positions "
                      f"{sorted(zoomdict)}.")
    elif zoom in pixelsize and startup.get('pixelsize') != pixelsize[zoom]:
        warnings.append(f"startup['pixelsize'] = {startup.get('pixelsize')} um does not match "
                        f"pixelsize[{zoom!r}] = {pixelsize[zoom]} um; using the latter. Write "
                        f"'pixelsize': pixelsize[{zoom!r}] to keep the two in step.")

    pitch = camera_parameters.get('x_pixel_size_in_microns')
    pitch_y = camera_parameters.get('y_pixel_size_in_microns')
    if pitch and pitch_y and pitch != pitch_y:
        warnings.append(f"the camera pixels are not square: 'x_pixel_size_in_microns' = {pitch} um, "
                        f"'y_pixel_size_in_microns' = {pitch_y} um. mesoSPIM stores a single pixel "
                        f"size per zoom position, taken from the x value, so the y scale of the saved "
                        f"data and of the tile view will be wrong.")

    for label, value in pixelsize.items():
        # Zoom labels are magnifications ('2x', '4x Olympus', '20x_custom(t25)'), so the pixel
        # size should be the camera pixel pitch divided by that number.
        magnification = re.match(r'([0-9.]+)x', str(label))
        if not (pitch and magnification and value):
            continue
        expected = pitch / float(magnification.group(1))
        if abs(value - expected) > 0.05 * value:
            warnings.append(f"pixelsize[{label!r}] = {value} um, but the camera pixel pitch "
                            f"{pitch} um / {magnification.group(1)} = {expected:.4g} um. Correct if "
                            f"a relay lens adds magnification, wrong camera table otherwise.")
    return errors, warnings


def update_startup_in_source(content, params):
    '''
    Rewrite `startup` values in the text of a config file.

    Keys found in the file are substituted in place. Keys that are not there
    (typical for a two-level config, where they live in an included hardware
    file) are appended as a startup.update({...}) override block, which the next
    call finds and substitutes in place.

    Returns (new_content, updated_keys, appended_keys).
    '''
    lines = content.split('\n')
    updated_keys, appended_keys = [], []
    for key, value in params.items():
        # Match 'key' : value or "key" : value on any non-commented line;
        # stops before a comma, newline, or inline comment.
        # ponytail: commented-out examples inside ''' ''' blocks are still matched,
        # as they always were. Skipping those needs a real parser, not worth it.
        pattern = r"(['\"]" + re.escape(key) + r"['\"]\s*:\s*)([^,\n#]+)"
        count_total = 0
        for i, line in enumerate(lines):
            if line.lstrip().startswith('#'):
                continue
            lines[i], count = re.subn(pattern, r'\g<1>' + repr(value), line)
            count_total += count
        (updated_keys if count_total else appended_keys).append(key)

    content = '\n'.join(lines)
    if appended_keys:
        block = [f"\n\n# --- parameters saved from the GUI, {time.strftime('%Y-%m-%d %H:%M')} ---",
                 'startup.update({']
        block += [f"    {key!r}: {params[key]!r}," for key in appended_keys]
        block += ['})\n']
        content += '\n'.join(block)
    return content, updated_keys, appended_keys
