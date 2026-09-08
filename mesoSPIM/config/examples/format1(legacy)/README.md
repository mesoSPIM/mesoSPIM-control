# Legacy (format 1) example configs

Single-file configs from real instruments: everything - camera, DAQ, stages, lasers, filter
wheel, zoom, writers - in one file. They still load unchanged, and the hardware files in
`config/hardware/` were derived from them.

To move one to the two-level format, run from the repository root:

```
python -m mesoSPIM.src.utils.convert_config "mesoSPIM/config/examples/format1(legacy)/config_of_my_rig.py" -o mesoSPIM/config/my_config.py
```

The converter picks the matching shared hardware files, writes the remaining settings as
overrides, and then loads both files and compares them setting by setting. Read its report:
it lists what it dropped (settings the software no longer reads) and what the newer shared
files add. Use `--check` to see all of that without writing a file.
