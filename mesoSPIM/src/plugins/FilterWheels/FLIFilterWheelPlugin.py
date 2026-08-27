"""Filter-wheel plugin for FLI High Speed Filter Wheels."""

from __future__ import annotations

import logging
import math
import time
from numbers import Real
from typing import Any, Mapping

from mesoSPIM.src.plugins.FilterWheelApi import API_VERSION, FilterWheel


logger = logging.getLogger(__name__)


def _load_serial_module():
    try:
        import serial
    except ImportError as exc:
        raise ImportError(
            "FLI requires pyserial. Install the mesoSPIM runtime dependencies."
        ) from exc
    return serial


class FLIFilterWheelPlugin:
    """Factory for FLI HS-625, HS-1025, and HS-1032 filter wheels."""

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return "FLI"

    @classmethod
    def description(cls) -> str:
        return "FLI High Speed Filter Wheel over an RS-232 serial connection."

    @classmethod
    def required_parameters(cls) -> tuple[str, ...]:
        return ("COMport", "baudrate", "wait_until_done_delay")

    @classmethod
    def create(
        cls,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> FilterWheel:
        return _FLIFilterWheel(filterwheel_parameters, filterdict)


class _FLIFilterWheel:
    def __init__(
        self,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        self._validate_config(filterwheel_parameters, filterdict)
        self.filterdict = dict(filterdict)
        self.wait_until_done_delay = float(filterwheel_parameters["wait_until_done_delay"])
        self._faulted = False

        serial = _load_serial_module()
        self._serial = serial.Serial(
            port=filterwheel_parameters["COMport"],
            baudrate=filterwheel_parameters["baudrate"],
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0,
            write_timeout=0,
            xonxoff=False,
        )

    @staticmethod
    def _validate_config(
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        required = FLIFilterWheelPlugin.required_parameters()
        missing = [key for key in required if key not in filterwheel_parameters]
        if missing:
            raise ValueError(
                "Missing required FLI filter wheel parameters: " + ", ".join(missing)
            )

        comport = filterwheel_parameters["COMport"]
        if not isinstance(comport, str) or not comport.strip():
            raise ValueError("FLI COMport must be a non-empty string")

        baudrate = filterwheel_parameters["baudrate"]
        if isinstance(baudrate, bool) or not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("FLI baudrate must be a positive integer")

        delay = filterwheel_parameters["wait_until_done_delay"]
        valid_delay = (
            not isinstance(delay, bool)
            and isinstance(delay, Real)
            and math.isfinite(delay)
            and 0 < delay <= 60
        )
        if not valid_delay:
            raise ValueError(
                "FLI wait_until_done_delay must be between 0 and 60 seconds"
            )

        if not isinstance(filterdict, Mapping) or not filterdict:
            raise ValueError("FLI requires a non-empty filterdict")
        for name, position in filterdict.items():
            if not isinstance(name, str) or not name:
                raise ValueError("FLI filter names must be non-empty strings")
            valid_position = (
                isinstance(position, int)
                and not isinstance(position, bool)
                and 0 <= position <= 9
            )
            if not valid_position:
                raise ValueError(
                    f"FLI filter {name!r} must map to an integer position from 0 to 9"
                )

    def _write_command(self, command: bytes) -> None:
        bytes_written = self._serial.write(command)
        if bytes_written != len(command):
            raise IOError(
                f"FLI wrote {bytes_written} of {len(command)} command bytes"
            )

    def _close_after_error(self) -> None:
        try:
            self.close()
        except Exception:
            logger.exception("Failed to close faulted FLI filter wheel")

    def set_filter(self, filter_name: str, wait_until_done: bool = False) -> None:
        if self._faulted:
            raise RuntimeError("FLI filter wheel is faulted and must be reinitialized")
        if self._serial is None:
            raise RuntimeError("FLI filter wheel is closed")
        if filter_name not in self.filterdict:
            raise ValueError(f"Filter {filter_name!r} not found in the configuration file")

        command = f"{self.filterdict[filter_name]}\n".encode("ascii")
        try:
            self._serial.flush()
            self._write_command(command)
            self._serial.flush()
        except Exception:
            self._faulted = True
            self._close_after_error()
            raise

        if wait_until_done:
            time.sleep(self.wait_until_done_delay)

    def close(self) -> None:
        serial_connection = self._serial
        if serial_connection is None:
            return
        self._serial = None
        try:
            serial_connection.flush()
        finally:
            serial_connection.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logger.debug("Failed to close FLI filter wheel during cleanup", exc_info=True)
