# Hardware configuration files

One file per microscope, named `<rig>_hw.py`. It describes the *instrument*, not the
person using it: camera model and parameters, stages and their travel limits, lasers,
filter wheel and filters, objectives and zoom, DAQ lines and trigger wiring, galvo
offsets and amplitudes, writer defaults.

The user config one directory up pulls the whole file in with a single line:

```python
include('hardware/my_scope_hw.py')
```

and then overrides only what differs for the session. Everything written after that
line wins, because it is simply later Python.

## Rules

* **Do not call `include()` here.** Only the user file gets it; a hardware file that
  calls it raises `NameError`. A configuration is two files deep, never more — chasing
  a setting through a chain of includes is worse than a few duplicated lines.
* **Keep the session settings out**: `state`, `folder`, `snap_folder`, `file_prefix`
  and `file_suffix` belong in the user file.
* One file per instrument. Two exposure presets for the same microscope are two *user*
  files including the same hardware file, not two hardware files.

## Converting an old single-file config

```bash
python -m mesoSPIM.src.utils.convert_config path/to/my_config.py
```

writes the user file and `hardware/my_config_hw.py` next to it. The hardware file is
the original byte for byte, minus the five session settings. The converter loads the
new pair and compares it against the original before writing anything.

It proves the values are unchanged; it cannot test the instrument. Check trigger lines,
COM ports and travel limits before running a converted config on a microscope.

## Version control

Files here are git-ignored (except `demo_config_hw.py`), because they describe one
specific machine. Keep your own backup of your rig's file — it is the only record of
how the instrument is wired.

See `docs/source/configuration.rst` for the description of every variable.
