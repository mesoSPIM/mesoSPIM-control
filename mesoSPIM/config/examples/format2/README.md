# Two-level (format 2) example configs

The same real-instrument configs as in `../format1(legacy)/`, converted with

```
python -m mesoSPIM.src.utils.convert_config "mesoSPIM/config/examples/format1(legacy)/config_of_my_rig.py" -o mesoSPIM/config/examples/format2/
```

Each file picks its hardware from `config/hardware/` with `include()` and then lists only the
settings of that instrument: about 85 lines instead of 450. The `# NOTE` lines at the top record
what the converter changed - settings dropped because the software no longer reads them, and
dicts kept as a whole so no uninstalled filter or objective appears in the interface.

The converter reports these as reproducing the old settings exactly, but that is a comparison of
values, not a bench test. Check the trigger lines, COM ports and travel limits before running one
on an instrument.
