"""Filter-wheel plugin for ZWO EFW astronomy filter wheels."""

from __future__ import annotations

import logging
import math
import struct
import time
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from mesoSPIM.src.plugins.FilterWheelApi import API_VERSION, FilterWheel


logger = logging.getLogger(__name__)

# Settle time applied after the SDK reports the wheel in position. Matches the
# fixed 1 s sleep of the legacy ZwoFilterWheel driver, so configs that omit
# 'wait_until_done_delay' behave as before.
DEFAULT_WAIT_UNTIL_DONE_DELAY = 1.0


def _load_efw_module():
    try:
        from mesoSPIM.src.devices.filter_wheels.ZWO_EFW import pyzwoefw
    except ImportError as exc:
        raise ImportError(
            "ZWOPlugin requires the bundled pyzwoefw bindings."
        ) from exc
    return pyzwoefw


def _default_dll_path(pyzwoefw) -> str:
    """Return the bundled EFW SDK library matching the interpreter bitness."""
    subdir = "Win64" if struct.calcsize("P") == 8 else "Win32"
    return str(Path(pyzwoefw.__file__).parent / "lib" / subdir / "EFW_filter.dll")


class ZWOFilterWheelPlugin:
    """Factory for ZWO EFW filter wheels (EFW-mini, 7-position 2", ...)."""

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return "ZWOPlugin"

    @classmethod
    def description(cls) -> str:
        return "ZWO EFW filter wheel over USB using the bundled EFW SDK."

    @classmethod
    def required_parameters(cls) -> tuple[str, ...]:
        # The wheel is addressed over USB and needs no operator-supplied
        # settings; 'wait_until_done_delay', 'wheel_index' and 'dll_path' are
        # all optional and fall back to sensible defaults.
        return ()

    @classmethod
    def create(
        cls,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> FilterWheel:
        return _ZWOFilterWheel(filterwheel_parameters, filterdict)


class _ZWOFilterWheel:
    def __init__(
        self,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        self._validate_config(filterwheel_parameters, filterdict)
        self.filterdict = dict(filterdict)
        self.wait_until_done_delay = float(
            filterwheel_parameters.get(
                "wait_until_done_delay", DEFAULT_WAIT_UNTIL_DONE_DELAY
            )
        )
        self._wheel_index = int(filterwheel_parameters.get("wheel_index", 0))
        self._faulted = False
        self._device = None

        pyzwoefw = _load_efw_module()
        dll_path = filterwheel_parameters.get("dll_path") or _default_dll_path(pyzwoefw)
        device = pyzwoefw.EFW(dll_path)
        if self._wheel_index >= len(device.IDs):
            if device.IDs:
                device.Close(device.IDs[0])
            raise ValueError(
                f"ZWOPlugin wheel_index {self._wheel_index} is not connected; "
                f"{len(device.IDs)} ZWO EFW wheel(s) found"
            )
        self._id = device.IDs[self._wheel_index]

        n_slots = device.GetProperty(self._id)["slotNum"]
        out_of_range = [
            name for name, position in self.filterdict.items() if position >= n_slots
        ]
        if out_of_range:
            device.Close(self._id)
            raise ValueError(
                f"ZWOPlugin filters {sorted(out_of_range)} exceed the physical slot "
                f"count ({n_slots}); update filterdict in the config file"
            )
        self._device = device

    @staticmethod
    def _validate_config(
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        # No required parameters; every key below is optional but must still be
        # valid when the operator does supply it.
        delay = filterwheel_parameters.get(
            "wait_until_done_delay", DEFAULT_WAIT_UNTIL_DONE_DELAY
        )
        valid_delay = (
            not isinstance(delay, bool)
            and isinstance(delay, Real)
            and math.isfinite(delay)
            and 0 < delay <= 60
        )
        if not valid_delay:
            raise ValueError(
                "ZWOPlugin wait_until_done_delay must be between 0 and 60 seconds"
            )

        wheel_index = filterwheel_parameters.get("wheel_index", 0)
        valid_index = (
            isinstance(wheel_index, int)
            and not isinstance(wheel_index, bool)
            and wheel_index >= 0
        )
        if not valid_index:
            raise ValueError("ZWOPlugin wheel_index must be a non-negative integer")

        dll_path = filterwheel_parameters.get("dll_path")
        if dll_path is not None and not (isinstance(dll_path, str) and dll_path.strip()):
            raise ValueError("ZWOPlugin dll_path must be a non-empty string")

        if not isinstance(filterdict, Mapping) or not filterdict:
            raise ValueError("ZWOPlugin requires a non-empty filterdict")
        for name, position in filterdict.items():
            if not isinstance(name, str) or not name:
                raise ValueError("ZWOPlugin filter names must be non-empty strings")
            valid_position = (
                isinstance(position, int)
                and not isinstance(position, bool)
                and position >= 0
            )
            if not valid_position:
                raise ValueError(
                    f"ZWOPlugin filter {name!r} must map to a non-negative integer slot"
                )

    def _close_after_error(self) -> None:
        try:
            self.close()
        except Exception:
            logger.exception("Failed to close faulted ZWO filter wheel")

    def set_filter(self, filter_name: str, wait_until_done: bool = False) -> None:
        if self._faulted:
            raise RuntimeError("ZWO filter wheel is faulted and must be reinitialized")
        if self._device is None:
            raise RuntimeError("ZWO filter wheel is closed")
        if filter_name not in self.filterdict:
            raise ValueError(f"Filter {filter_name!r} not found in the configuration file")

        try:
            self._device.SetPosition(
                self._id, self.filterdict[filter_name], wait_until_done
            )
        except Exception:
            self._faulted = True
            self._close_after_error()
            raise

        if wait_until_done:
            # ponytail: fixed settle delay after the SDK reports in-position;
            # tune wait_until_done_delay per wheel if filters land early.
            time.sleep(self.wait_until_done_delay)

    def close(self) -> None:
        device = self._device
        if device is None:
            return
        self._device = None
        device.Close(self._id)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logger.debug("Failed to close ZWO filter wheel during cleanup", exc_info=True)
