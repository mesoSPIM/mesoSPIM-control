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
'''

import importlib.util
import os
import re
import time
import types

package_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # mesoSPIM/
CONFIG_DIR = os.path.join(package_directory, 'config')


def _make_include(target_dict):
    '''Create the include() function bound to the namespace of one config module.'''
    def include(*rel_paths):
        for rel in rel_paths:
            path = rel if os.path.isabs(rel) else os.path.join(CONFIG_DIR, rel)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Config include not found: {path} (from '{rel}')")
            sub = load_config_from_file(path)
            for name, value in vars(sub).items():
                if name.startswith('__') or name == 'include' or isinstance(value, types.ModuleType):
                    continue
                current = target_dict.get(name)
                if isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)  # shallow merge: later include wins per key
                else:
                    target_dict[name] = value
    return include


def load_config_from_file(path_to_config):
    '''
    Load a microscope configuration from a file using importlib
    '''
    spec = importlib.util.spec_from_file_location('module.name', path_to_config)
    config = importlib.util.module_from_spec(spec)
    config.include = _make_include(config.__dict__)
    spec.loader.exec_module(config)
    print(f'Configuration file loaded: {path_to_config}')
    return config


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
