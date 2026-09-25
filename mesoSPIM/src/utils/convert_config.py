'''
Convert a single-file (format 1) mesoSPIM config into a two-file (format 2) pair:

* ``hardware/<name>_hw.py`` - the old file verbatim, minus the session settings.
  Comments, spacing and even the dead "uncomment the block for your camera"
  re-assignments are preserved, so the microscope behaves exactly as before.
* ``<name>.py`` - the user file: one ``include()`` plus the session settings.

Usage::

    python -m mesoSPIM.src.utils.convert_config path/to/config.py [more.py ...] [-o OUTDIR]

The conversion is verified before it is reported as done: the new pair is loaded
and its namespace compared against the original. A mismatch raises.
'''
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from mesoSPIM.src.utils.config_loader import load_config_from_file

# Settings that belong to the person running the microscope, not to the microscope.
SESSION_KEYS = ('state', 'folder', 'snap_folder', 'file_prefix', 'file_suffix')

USER_FILE_TEMPLATE = '''\
"""
mesoSPIM user configuration, converted from the single-file format.

The microscope itself is described in {hw_rel}: camera, stages, lasers, filters,
objectives, DAQ lines, writer defaults. Change that file when the instrument changes.

Here, keep only what differs for your session. Anything assigned below the include()
line overrides the hardware file, e.g.:

    startup['camera_exposure_time'] = 0.05
    filterdict['Empty-Alignment'] = 0
"""
config_format = 2

include('{hw_rel}')

startup.update({{
{session_lines}}})
'''


def split_config(path, outdir=None):
    '''Write the hardware/user pair for one config file. Returns both paths.'''
    path = Path(path).resolve()
    outdir = Path(outdir).resolve() if outdir else path.parent
    # newline='' throughout: the hardware file must keep the original line endings,
    # or the whole file shows up as changed in a diff.
    with open(path, encoding='utf-8', newline='') as f:
        source = f.read()
    if re.search(r"^\s*include\s*\(", source, re.M):
        raise ValueError(f'{path.name}: already in the two-file format (it calls include())')
    old = load_config_from_file(path)

    session = {k: old.startup[k] for k in SESSION_KEYS if k in old.startup}
    if not session:
        raise ValueError(f"{path.name}: none of the session keys {SESSION_KEYS} found in startup")

    hw_lines, dropped = [], []
    for line in source.splitlines(keepends=True):
        key = re.match(r"\s*['\"](" + '|'.join(session) + r")['\"]\s*:", line)
        if key:
            dropped.append(key.group(1))
        else:
            hw_lines.append(line)
    duplicated = {k for k in dropped if dropped.count(k) > 1}
    if duplicated:
        raise ValueError(f"{path.name}: {sorted(duplicated)} set on more than one line; "
                         f"remove the dead assignments before converting")

    hw_name = f'{path.stem}_hw.py'
    user_text = USER_FILE_TEMPLATE.format(
        hw_rel=f'hardware/{hw_name}',
        session_lines=''.join(f'    {k!r}: {v!r},\n' for k, v in session.items()),
    )

    # Build the pair in a temp directory and move it into place only once it verifies:
    # converting in place overwrites the file being read, so a late failure would lose it.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'hardware').mkdir()
        _write(tmp / 'hardware' / hw_name, ''.join(hw_lines))
        _write(tmp / path.name, user_text)
        _verify(old, tmp / path.name)

        hw_path = outdir / 'hardware' / hw_name
        hw_path.parent.mkdir(parents=True, exist_ok=True)
        user_path = outdir / path.name
        shutil.copyfile(tmp / 'hardware' / hw_name, hw_path)
        shutil.copyfile(tmp / path.name, user_path)
    return hw_path, user_path


def _write(path, text):
    '''Write text with its line endings exactly as given.'''
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def _namespace(module):
    '''The config values a module defines, as text, so numpy arrays compare cleanly.

    'startup' is sorted first: the session keys move to the end of it during the split,
    and nothing reads that dict in order. Every other dict keeps its order in the
    comparison, because for some of them (the ASI stage dicts) the order is the setting.
    '''
    ignore = {'include', 'config_format'}   # added by the new format, absent from the old file
    return {k: repr(dict(sorted(v.items())) if k == 'startup' else v)
            for k, v in vars(module).items()
            if not k.startswith('__') and k not in ignore}


def _verify(old, user_path):
    '''Raise unless the new pair defines exactly what the old single file defined.'''
    new = _namespace(load_config_from_file(user_path))
    old = _namespace(old)
    differing = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    if differing:
        raise ValueError(f'{user_path.name}: conversion changed {differing} - not written as valid. '
                         f'First difference:\n  old: {old.get(differing[0])}\n  new: {new.get(differing[0])}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('configs', nargs='+', type=Path, help='config file(s) to convert')
    parser.add_argument('-o', '--outdir', type=Path, default=None,
                        help="output directory (default: next to each input file)")
    args = parser.parse_args(argv)

    for config in args.configs:
        hw_path, user_path = split_config(config, args.outdir)
        print(f'{config.name} -> {user_path} + {hw_path}')


if __name__ == '__main__':
    main()
