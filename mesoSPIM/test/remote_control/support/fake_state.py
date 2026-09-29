"""A state object faithful to production ``mesoSPIM_StateSingleton``.

Production state (``mesoSPIM/src/mesoSPIM_State.py:103-172``) is a QObject exposing ONLY
``__getitem__`` (raising KeyError), ``__setitem__``, ``__len__``, ``set_parameters``,
``get_parameter_dict``, ``get_parameter_list`` and ``block_signals``. There is no
``.get()``, no ``__contains__``, no ``__delitem__``.

A plain-dict fake silently passes code that dies on the instrument -- ``acquire_finish``
did exactly that -- so every state-bearing fake uses this instead. The mutex is
production's concern, not the fake's; the observable access surface is what matters here.
"""

from __future__ import annotations

from copy import deepcopy

from mesoSPIM.test.remote_control.support.acquisitions import AcquisitionList

DEFAULTS = {
    "state": "idle",
    "position": {"x_pos": 0.0, "y_pos": 0.0, "z_pos": 0.0, "f_pos": 0.0, "theta_pos": 0.0},
    "selected_row": 0,
    "laser": "488 nm",
    "intensity": 10,
    "filter": "Empty",
    "zoom": "1x",
    "shutterconfig": "Both",
    "shutterstate": False,
    "folder": "",
    "ETL_cfg_file": "",
    "etl_l_delay_%": 7.5,
    "etl_l_ramp_rising_%": 85,
    "etl_l_ramp_falling_%": 2.5,
    "etl_l_amplitude": 0.7,
    "etl_l_offset": 2.3,
    "etl_r_delay_%": 2.5,
    "etl_r_ramp_rising_%": 5,
    "etl_r_ramp_falling_%": 85,
    "etl_r_amplitude": 0.65,
    "etl_r_offset": 2.36,
}
"""Production's own state defaults for the keys Remote Control reads.

The ten ETL keys are not decoration: ``_ETL_READBACK_KEYS`` hands all of them to
``get_parameter_dict``, which indexes every one and raises KeyError on a miss. Their values
are mesoSPIM_State.py:62-71 verbatim, so a readback here says what the instrument would.
"""


class FakeState:
    """The production access surface, and nothing more.

    Deep-copies DEFAULTS so each fake owns its nested values and one test's mutation
    cannot leak into the next. ``acq_list`` is seeded because it is a real default key in
    production (``mesoSPIM_State.py:40``) -- the acquire_finish bug hinges on it being
    present, and on there being no way to remove it.
    """

    def __init__(self, **overrides):
        values = deepcopy(DEFAULTS)
        values.update(overrides)
        values.setdefault("acq_list", AcquisitionList([]))
        self._state_dict = values

    def __getitem__(self, key):
        return self._state_dict[key]  # KeyError on a miss, like production

    def __setitem__(self, key, value):
        self._state_dict[key] = value

    def __len__(self):
        return len(self._state_dict)

    def set_parameters(self, values):
        self._state_dict.update(values)

    def get_parameter_dict(self, keys):
        """Index every requested key, raising KeyError on a miss, as production does.

        ``mesoSPIM_State.py:146-152``. Do not make this lenient -- a forgiving fake is what
        let the production-only failures through in the first place.
        """
        return {key: self._state_dict[key] for key in keys}

    def get_parameter_list(self, keys):
        """As get_parameter_dict, in list form. ``mesoSPIM_State.py:163-169``."""
        return [self._state_dict[key] for key in keys]

    def block_signals(self, _boolean):
        pass
