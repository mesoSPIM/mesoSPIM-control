# Shared hardware configuration files

These files describe *hardware*, not users. Keep them up to date: a user config
file pulls them in with `include()` instead of copy-pasting their content.

One rule: a file here defines only the variables belonging to its own category,
and may contribute a **partial** `startup = {...}` dict with the initial values
that depend on that hardware.

```python
# hardware/cameras/demo_camera.py
camera = 'DemoCamera'
camera_parameters = {...}
startup = {'camera_exposure_time': 0.02}   # partial, merged with the others
```

Merge rules (implemented in `mesoSPIM/src/utils/config_loader.py`):

* dicts with the same name are merged key-by-key; the *later* `include()` wins;
* anything assigned in the user file **after** the `include()` call wins over
  everything included.

One exception to the "own category" rule: `startup['sweeptime']` is set by the
**camera** files, not by the DAQ files. It is a DAQ parameter, but in ASLM mode
the light-sheet sweep has to match the camera's rolling-shutter readout and
exposure time, so it only makes sense together with the camera.

Writer/plugin configuration is not hardware and lives in `config/plugins/`;
interface defaults live in `config/UI/`.

See `config/demo_config.py` for a complete user-facing example, and
`docs/source/configuration.rst` for the full description of every key.
