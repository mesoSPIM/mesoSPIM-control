"""Filter-wheel plugin for Sutter Lambda 10 controllers."""

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
            "SutterPlugin requires pyserial. Install the mesoSPIM runtime dependencies."
        ) from exc
    return serial


class SutterFilterWheelPlugin:
    """Factory for the plugin-based Sutter Lambda 10 filter-wheel driver."""

    @classmethod
    def api_version(cls) -> str:
        return API_VERSION

    @classmethod
    def name(cls) -> str:
        return "SutterPlugin"

    @classmethod
    def description(cls) -> str:
        return "Sutter Lambda 10 single filter wheel over a serial connection."

    @classmethod
    def required_parameters(cls) -> tuple[str, ...]:
        return ("COMport", "baudrate", "wheel_speed", "wait_until_done_delay")

    @classmethod
    def create(
        cls,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> FilterWheel:
        return _SutterFilterWheel(filterwheel_parameters, filterdict)


class _SutterFilterWheel:
    RESPONSE_BYTES = 2

    def __init__(
        self,
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        self._validate_config(filterwheel_parameters, filterdict)
        self.filterdict = dict(filterdict)
        self.wheel_speed = filterwheel_parameters["wheel_speed"]
        self.wait_until_done_delay = float(filterwheel_parameters["wait_until_done_delay"])
        self._faulted = False

        serial = _load_serial_module()
        self._serial = serial.Serial(
            port=filterwheel_parameters["COMport"],
            baudrate=filterwheel_parameters["baudrate"],
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2,
            write_timeout=1,
            xonxoff=False,
        )
        try:
            self._serial.reset_input_buffer()
            self._write_command(b"\xee")
            self._read_response(b"\xee", "initialization")
        except Exception:
            self._faulted = True
            self._close_after_error()
            raise

    @staticmethod
    def _validate_config(
        filterwheel_parameters: Mapping[str, Any],
        filterdict: Mapping[str, Any],
    ) -> None:
        required = SutterFilterWheelPlugin.required_parameters()
        missing = [key for key in required if key not in filterwheel_parameters]
        if missing:
            raise ValueError(
                "Missing required SutterPlugin filter wheel parameters: "
                + ", ".join(missing)
            )

        comport = filterwheel_parameters["COMport"]
        if not isinstance(comport, str) or not comport.strip():
            raise ValueError("SutterPlugin COMport must be a non-empty string")

        baudrate = filterwheel_parameters["baudrate"]
        if isinstance(baudrate, bool) or not isinstance(baudrate, int) or baudrate <= 0:
            raise ValueError("SutterPlugin baudrate must be a positive integer")

        wheel_speed = filterwheel_parameters["wheel_speed"]
        if (
            isinstance(wheel_speed, bool)
            or not isinstance(wheel_speed, int)
            or not 0 <= wheel_speed <= 7
        ):
            raise ValueError("SutterPlugin wheel_speed must be an integer from 0 to 7")

        delay = filterwheel_parameters["wait_until_done_delay"]
        valid_delay = (
            not isinstance(delay, bool)
            and isinstance(delay, Real)
            and math.isfinite(delay)
            and 0 < delay <= 60
        )
        if not valid_delay:
            raise ValueError(
                "SutterPlugin wait_until_done_delay must be between 0 and 60 seconds"
            )

        if not isinstance(filterdict, Mapping) or not filterdict:
            raise ValueError("SutterPlugin requires a non-empty filterdict")
        for name, position in filterdict.items():
            if not isinstance(name, str) or not name:
                raise ValueError("SutterPlugin filter names must be non-empty strings")
            valid_position = (
                isinstance(position, int)
                and not isinstance(position, bool)
                and 0 <= position <= 9
            )
            if not valid_position:
                raise ValueError(
                    f"SutterPlugin filter {name!r} must map to an integer position from 0 to 9"
                )
        if wheel_speed == 0 and any(position > 3 for position in filterdict.values()):
            raise ValueError(
                "SutterPlugin wheel_speed 0 is only valid for positions 0 to 3"
            )

    def _write_command(self, command: bytes) -> None:
        bytes_written = self._serial.write(command)
        if bytes_written != len(command):
            raise IOError(
                f"SutterPlugin wrote {bytes_written} of {len(command)} command bytes"
            )

    def _read_response(self, command: bytes, operation: str) -> bytes:
        response = self._serial.read(self.RESPONSE_BYTES)
        if len(response) != self.RESPONSE_BYTES:
            raise TimeoutError(
                f"SutterPlugin received {len(response)} of {self.RESPONSE_BYTES} "
                f"response bytes during {operation}"
            )
        expected = command + b"\r"
        if response != expected:
            raise IOError(
                f"SutterPlugin received unexpected response {response!r} "
                f"during {operation}; expected {expected!r}"
            )
        return response

    def _close_after_error(self) -> None:
        try:
            self.close()
        except Exception:
            logger.exception("Failed to close faulted SutterPlugin filter wheel")

    def set_filter(self, filter_name: str, wait_until_done: bool = False) -> None:
        if self._faulted:
            raise RuntimeError("SutterPlugin filter wheel is faulted and must be reinitialized")
        if self._serial is None:
            raise RuntimeError("SutterPlugin filter wheel is closed")
        if filter_name not in self.filterdict:
            raise ValueError(f"Filter {filter_name!r} not found in the configuration file")

        position = self.filterdict[filter_name]
        command = bytes((position + 16 * self.wheel_speed,))
        try:
            self._serial.reset_input_buffer()
            self._write_command(command)
            if wait_until_done:
                time.sleep(self.wait_until_done_delay)
            self._read_response(command, f"movement to {filter_name!r}")
        except Exception:
            self._faulted = True
            self._close_after_error()
            raise

    def close(self) -> None:
        serial_connection = self._serial
        if serial_connection is None:
            return
        self._serial = None
        serial_connection.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logger.debug("Failed to close SutterPlugin filter wheel during cleanup", exc_info=True)
