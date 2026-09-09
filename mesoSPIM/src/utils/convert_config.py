'''
Convert a legacy (single-file) mesoSPIM config into the two-level format.

The converter loads the old config, picks for every hardware category the
shared file under config/hardware/ (config/plugins/, config/UI/) that fits it
best, and writes a short user-facing file that include()s those and overrides
whatever still differs. The result is then loaded again and compared key by key
with the original: the conversion is only reported as successful if both give
exactly the same configuration.

Usage (from the repository root):

    python -m mesoSPIM.src.utils.convert_config mesoSPIM/config/my_config.py
    python -m mesoSPIM.src.utils.convert_config OLD.py -o NEW.py
    python -m mesoSPIM.src.utils.convert_config mesoSPIM/config/examples/*.py -o outdir/
    python -m mesoSPIM.src.utils.convert_config OLD.py --check   # verify only, write nothing

Comments of the old file are not carried over. Read the generated file before
using it on an instrument.
'''

import argparse
import contextlib
import io
import os
import pprint
import sys
import types

if __package__ in (None, ''):  # allow running the file directly
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    from mesoSPIM.src.utils.config_loader import CONFIG_DIR, is_demo, load_config_from_file
else:
    from .config_loader import CONFIG_DIR, is_demo, load_config_from_file

# Categories in include() order: hardware first, then plugin/UI configuration.
CATEGORIES = ['hardware/cameras', 'hardware/DAQ', 'hardware/stages', 'hardware/lasers',
              'hardware/filterwheels', 'hardware/objectives', 'hardware/galvos', 'hardware/ETLs',
              'plugins/writers', 'UI']

IGNORED = ('include', 'config_format')  # loader plumbing, not configuration

# Dicts whose keys are choices offered to the operator (filter names, laser lines, zoom
# positions): an extra entry coming from a shared file would be selectable but not installed,
# so these are replaced as a whole instead of being merged key by key.
LABEL_DICTS = ('filterdict', 'laserdict', 'zoomdict', 'pixelsize', 'binning_dict', 'shutterdict')

# Float values that carry more digits than anyone typed are written with at most
# SIGNIFICANT_DIGITS. Config files collect these from the GUI ('galvo_l_phase':
# 0.4487989505128276) and from arithmetic ('7.5x': 0.5666666666666667); the extra digits are
# noise and they make a converted file hard to read. A value that already fits in
# TYPED_DIGITS is left alone, so a deliberate 'galvo_l_frequency': 199.195 is not shortened,
# and the count is of significant digits rather than decimals so that a small value such as
# 'camera_line_interval': 7.5e-05 keeps its precision.
SIGNIFICANT_DIGITS = 5
TYPED_DIGITS = 8


# Settings that only some drivers of a device read, where the driver is named by another
# variable of the config. 'camera_line_interval' is pushed to the camera only by the Hamamatsu
# class (mesoSPIM_Camera.py); every other camera reads it into a variable nothing uses, so a
# config carrying it for a Photometrics or PCO camera only misleads its next reader.
# (container, key, variable naming the driver, drivers that read the setting)
DRIVER_ONLY = (('startup', 'camera_line_interval', 'camera', ('HamamatsuOrca',)),)


# Dicts whose key ORDER is part of the configuration, not just their content. StageControlASI
# builds its axis string from 'stage_assignment' in insertion order and sends it as the 'W'
# (where) query, so a config that lists the axes in a different order talks to the controller
# differently even when it maps every axis the same way. Such a dict is written out verbatim
# instead of being merged away, so that a converted config keeps the order it was running with.
ORDER_SIGNIFICANT = {'asi_parameters': ('stage_assignment', 'encoder_conversion', 'speed'),
                     'pi_parameters': ('stage_assignment',)}


# The setting that names the driver of each category: variable -> key inside it (None = the
# variable itself). Used to recognise which shared file describes the same device.
DRIVER_NAMES = {'camera': None, 'waveformgeneration': None, 'laser': None, 'shutter': None,
                'stage_parameters': 'stage_type',
                'filterwheel_parameters': 'filterwheel_type',
                'zoom_parameters': 'zoom_type'}

# Settings the application does not read any more. They are dropped rather than carried over,
# so that converted files do not keep spreading them. Container '' means module level;
# 'stage_trigger_*' is dead in acquisition_hardware only - in asi_parameters it is live.
OBSOLETE = {
    '': ('waveform_mode',),
    'startup': ('camera_sensor_mode', 'camera_display_snap_subsampling', 'filepath',
                'stage_trigger_delay_%', 'stage_trigger_pulse_%'),  # the live ones are in asi_parameters
    'camera_parameters': ('binning',),  # superseded by startup['camera_binning']
    'MP_OME_Zarr_Writer': ('async_finalize',),  # the multiprocess writer always closes synchronously
    'acquisition_hardware': ('stage_trigger_source', 'stage_trigger_out_line',
                             'stage_trigger_delay_%', 'stage_trigger_pulse_%'),
}

# Connection settings that only some drivers of a category read: a config written for one
# device often keeps the COM port, baud rate or servo id of the device it replaced. Carrying
# those over invites talking to the wrong port, so the converter keeps per driver only the keys
# that driver actually reads (see mesoSPIM_Serial.py and src/plugins/FilterWheels/) and drops
# the rest. A driver name that is not listed here keeps all of its settings.
CONNECTION_KEYS = {'filterwheel_parameters': ('COMport', 'baudrate', 'servo_id', 'wheel_speed'),
                   'zoom_parameters': ('COMport', 'baudrate', 'servo_id')}
CONNECTION_USED = {
    'filterwheel_parameters': {
        'Demo': (),
        'ZWO': (),  # USB
        'ZWOPlugin': (),  # USB
        'Ludl': ('COMport',),
        'LudlPlugin': ('COMport', 'baudrate'),
        'Dynamixel': ('COMport', 'baudrate', 'servo_id'),
        'Sutter': ('COMport', 'baudrate', 'wheel_speed'),
        'SutterPlugin': ('COMport', 'baudrate', 'wheel_speed'),
        'FLI': ('COMport', 'baudrate'),
    },
    'zoom_parameters': {
        'Demo': (),
        'DemoZoom': (),
        'Mitu': ('COMport', 'baudrate'),
        'Mitutoyo': ('COMport', 'baudrate'),
        'Dynamixel': ('COMport', 'baudrate', 'servo_id'),
    },
}


def _namespace(module):
    '''Configuration variables of a loaded config module.'''
    return {name: value for name, value in vars(module).items()
            if not name.startswith('__') and name not in IGNORED
            and not isinstance(value, types.ModuleType) and not callable(value)}


def _load(path, notes=None):
    with contextlib.redirect_stdout(io.StringIO()):  # the loader prints one line per file
        namespace = _namespace(load_config_from_file(path))
    dropped = _drop_obsolete(namespace)
    dropped.extend(_round_floats(namespace))
    if notes is not None:
        notes.extend(dropped)
    return namespace


def _rounded(value):
    '''`value` with every float shortened to SIGNIFICANT_DIGITS, containers included.'''
    if isinstance(value, bool) or not isinstance(value, (float, dict, list, tuple)):
        return value
    if isinstance(value, float):
        if float(f'{value:.{TYPED_DIGITS}g}') == value:  # short enough to have been typed
            return value
        return float(f'{value:.{SIGNIFICANT_DIGITS}g}')
    if isinstance(value, dict):
        return {key: _rounded(sub) for key, sub in value.items()}
    return type(value)(_rounded(sub) for sub in value)


def _round_floats(namespace):
    '''Shorten the floats of a loaded config in place. Returns a note per changed setting.'''
    rounded = []
    for name, value in namespace.items():
        if isinstance(value, dict):
            for key, sub in value.items():
                short = _rounded(sub)
                if short != sub:
                    value[key] = short
                    rounded.append(f'{name}[{key!r}] {sub!r} written as {short!r}')
        else:
            short = _rounded(value)
            if short != value:
                namespace[name] = short
                rounded.append(f'{name} {value!r} written as {short!r}')
    return rounded


def _drop_obsolete(namespace):
    '''Remove settings the application no longer reads. Returns a note per dropped setting.'''
    dropped = []
    for container, keys in OBSOLETE.items():
        target = namespace if container == '' else namespace.get(container)
        if not isinstance(target, dict):
            continue
        for key in keys:
            if key in target:
                del target[key]
                name = f'{container}[{key!r}]' if container else key
                dropped.append(f'{name} dropped, the software does not read it any more')
    dropped.extend(_drop_unused_connection_keys(namespace))
    dropped.extend(_drop_driver_only(namespace))
    return dropped


def _drop_unused_connection_keys(namespace):
    '''Remove COM port / baud rate / servo id settings the configured driver ignores.

    Returns a note per dropped setting.
    '''
    dropped = []
    for container, keys in CONNECTION_KEYS.items():
        target = namespace.get(container)
        if not isinstance(target, dict):
            continue
        driver = target.get(DRIVER_NAMES[container])
        if is_demo(driver):  # 'Demo', 'DemoZoom', 'DemoFilterWheel', ...: simulated, opens nothing
            driver = 'Demo'
        if driver not in CONNECTION_USED[container]:  # unknown driver: keep everything
            continue
        for key in keys:
            if key in target and key not in CONNECTION_USED[container][driver]:
                del target[key]
                dropped.append(f'{container}[{key!r}] dropped, '
                               f"the '{driver}' driver does not use it")
    return dropped


def _drop_driver_only(namespace):
    '''Remove settings only some drivers of a device read. Returns a note per dropped setting.'''
    dropped = []
    for container, key, driver_name, drivers in DRIVER_ONLY:
        target = namespace if container == '' else namespace.get(container)
        driver = namespace.get(driver_name)
        if not isinstance(target, dict) or key not in target or driver is None or driver in drivers:
            continue
        del target[key]
        dropped.append(f'{container}[{key!r}] dropped, '
                       f"the '{driver}' {driver_name} does not use it")
    return dropped


def _identity(candidate, legacy):
    '''
    Same device driver? +1 per matching driver name, -1 per conflicting one.

    A rig config differs from the shared file in almost every travel limit, COM port and
    voltage, so counting values alone would reject the right file. The driver names below
    decide which file belongs to which category; the values are then overridden.
    '''
    score = 0
    for name, key in DRIVER_NAMES.items():
        if name not in candidate or name not in legacy:
            continue
        left = candidate[name] if key is None else candidate[name].get(key)
        right = legacy[name] if key is None else legacy[name].get(key)
        if left is not None and right is not None:
            # 'Demo', 'DemoCamera', 'DemoStage', ... all name the same simulated device
            same = left == right or (is_demo(left) and is_demo(right))
            score += 1 if same else -1
    return score


def _score(candidate, legacy):
    '''How well a hardware file fits a legacy config: +1 per equal, -1 per conflicting value.'''
    score = 0
    for name, value in candidate.items():
        if name not in legacy:
            continue
        if isinstance(value, dict) and isinstance(legacy[name], dict):
            for key, sub in value.items():  # e.g. the partial `startup` dicts
                if key in legacy[name]:
                    score += 1 if legacy[name][key] == sub else -1
        else:
            score += 1 if legacy[name] == value else -1
    return score


def _pick_includes(legacy):
    '''Best-fitting file per category, as (relative include path, namespace) pairs.'''
    chosen = []
    for category in CATEGORIES:
        folder = os.path.join(CONFIG_DIR, category)
        candidates = sorted(f for f in os.listdir(folder) if f.endswith('.py'))
        scored = []
        for name in candidates:
            namespace = _load(os.path.join(folder, name))
            scored.append((_identity(namespace, legacy), _score(namespace, legacy), name))
        identity, score, best_file = max(scored)
        if identity <= 0 and score <= 0:  # nothing in this category resembles the old config
            continue
        chosen.append((f'{category}/{best_file}', _load(os.path.join(folder, best_file))))
    return chosen


def _merge(includes):
    '''Replay the include() merge rules to get the namespace before any override.'''
    merged = {}
    for _, namespace in includes:
        for name, value in namespace.items():
            if isinstance(merged.get(name), dict) and isinstance(value, dict):
                merged[name].update(value)
            else:
                merged[name] = value.copy() if isinstance(value, dict) else value
    return merged


def _format(value):
    return pprint.pformat(value, width=100, sort_dicts=False)


def _reordered(name, value, merged_value):
    '''Order-significant sub-dicts of `value` that the shared files list in another order.'''
    return {key for key in ORDER_SIGNIFICANT.get(name, ())
            if isinstance(value.get(key), dict) and isinstance(merged_value.get(key), dict)
            and list(value[key]) != list(merged_value[key])}


def _overrides(legacy, merged):
    '''Python source lines that turn `merged` into `legacy`, plus notes about what was added.'''
    lines, notes = [], []
    for name, value in legacy.items():
        reordered = (_reordered(name, value, merged[name])
                     if isinstance(value, dict) and isinstance(merged.get(name), dict) else set())
        if name in merged and merged[name] == value and not reordered:
            continue
        if not (isinstance(value, dict) and isinstance(merged.get(name), dict)):
            lines.append(f'{name} = {_format(value)}')
            continue
        extra = sorted(key for key in merged[name] if key not in value)
        if extra and name in LABEL_DICTS:
            notes.append(f'{name} replaced as a whole, the shared file also offers {extra}')
            lines.append(f'{name} = {_format(value)}')
            continue
        if extra:
            notes.append(f'{name} gains {extra} from the shared files')
        for key in sorted(reordered):
            notes.append(f'{name}[{key!r}] written out to keep the axis order of the old config, '
                         f'which the shared file lists as {list(merged[name][key])}')
        differing = {key: sub for key, sub in value.items()
                     if key in reordered or key not in merged[name] or merged[name][key] != sub}
        lines.append(f'{name}.update({_format(differing)})')
    for name in sorted(set(merged) - set(legacy)):
        notes.append(f'{name} comes from the shared files, the old config had no such setting')
    return lines, notes


def _spaced(lines):
    '''Blank line after every dictionary block, so that the overrides stay readable.'''
    spaced = []
    for line in lines:
        spaced.append(line)
        if line.rstrip().endswith(('}', '})')):
            spaced.append('')
    while spaced and spaced[-1] == '':
        spaced.pop()
    return spaced


def convert(source_path):
    '''Return (source text of the converted config, chosen includes, notes).'''
    dropped = []
    legacy = _load(source_path, dropped)
    includes = _pick_includes(legacy)
    merged = _merge(includes)
    lines, notes = _overrides(legacy, merged)
    notes = dropped + notes

    header = ["'''", f"mesoSPIM configuration file (two-level format), converted from",
              f"{os.path.basename(source_path)}.", '',
              'The hardware is described in the shared files included below; everything',
              'assigned after the include() call overrides them. See config/hardware/README.md.',
              "'''", 'config_format = 2', '']
    text = '\n'.join(header)
    text += 'include(' + (',\n        '.join(repr(path) for path, _ in includes)) + ')\n'
    if notes:
        text += '\n' + '\n'.join(f'# NOTE {note}' for note in notes) + '\n'
    text += '\n# --- settings of this microscope/user, overriding the files included above ---\n'
    text += '\n'.join(_spaced(lines)) + '\n'
    return text, includes, notes


def verify(source_path, converted_path):
    '''
    Compare the two configs key by key.

    Returns (differences, additions). A difference is a setting the old config had and the
    converted one does not reproduce - the conversion is wrong. An addition is a setting only
    the converted file has, because the shared hardware files are newer than the old config.
    '''
    legacy, new = _load(source_path), _load(converted_path)
    differences, additions = [], []
    for name in sorted(set(legacy) | set(new)):
        if name not in new:
            differences.append(f'{name}: missing in the converted file')
        elif name not in legacy:
            additions.append(f'{name} = {new[name]!r}')
        elif isinstance(legacy[name], dict) and isinstance(new[name], dict):
            for key in sorted(set(legacy[name]) | set(new[name])):
                if key not in legacy[name]:
                    additions.append(f'{name}[{key!r}] = {new[name][key]!r}')
                elif key not in new[name]:
                    differences.append(f'{name}[{key!r}]: {legacy[name][key]!r} -> missing')
                elif legacy[name][key] != new[name][key]:
                    differences.append(f'{name}[{key!r}]: {legacy[name][key]!r} -> {new[name][key]!r}')
        elif legacy[name] != new[name]:
            differences.append(f'{name}: {legacy[name]!r} -> {new[name]!r}')
    return differences, additions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[1],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('config', nargs='+', help='legacy config file(s) to convert')
    parser.add_argument('-o', '--output', help='output file, or output directory for several inputs')
    parser.add_argument('--check', action='store_true',
                        help='convert to a temporary file and only report the comparison')
    parser.add_argument('-f', '--force', action='store_true', help='overwrite an existing output file')
    args = parser.parse_args(argv)

    failures = 0
    for source in args.config:
        if args.check:
            target = os.path.join(CONFIG_DIR, '_converted_check.py')  # inside config/ for include() paths
        elif args.output and len(args.config) == 1 and not os.path.isdir(args.output):
            target = args.output
        else:
            folder = args.output or os.path.dirname(source)
            target = os.path.join(folder, os.path.basename(source))
        if os.path.exists(target) and not (args.force or args.check):
            print(f'{source}: SKIPPED, {target} exists (use --force to overwrite)')
            failures += 1
            continue

        try:
            text, includes, notes = convert(source)
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, 'w') as file:
                file.write(text)
            try:
                differences, additions = verify(source, target)
            finally:
                if args.check:
                    os.remove(target)
        except Exception as error:  # a broken config must not stop the other conversions
            failures += 1
            print(f'\n{source}\n    FAILED to convert: {type(error).__name__}: {error}')
            continue

        print(f'\n{source}')
        for path, _ in includes:
            print(f'    include {path}')
        for note in notes:
            print(f'    NOTE {note}')
        for addition in additions:
            print(f'    ADDED (newer default from the shared files) {addition}')
        if differences:
            failures += 1
            print(f'    FAILED: {len(differences)} setting(s) of the old config not reproduced:')
            for difference in differences:
                print(f'        {difference}')
        else:
            print('    old settings reproduced exactly' + ('' if args.check else f' -> {target}'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
