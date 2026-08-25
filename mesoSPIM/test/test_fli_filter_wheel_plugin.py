import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mesoSPIM.src.plugins import manager
from mesoSPIM.src.plugins import utils as plugin_utils
from mesoSPIM.src.plugins.FilterWheels import FLIFilterWheelPlugin as fli_module


PLUGIN_DIR = Path(fli_module.__file__).parent
VALID_PARAMETERS = {
    "COMport": "COM9",
    "baudrate": 9600,
    "wait_until_done_delay": 0.2,
}


class FakeSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_TWO = 2

    def __init__(self):
        self.connection = MagicMock()
        self.connection.write.side_effect = lambda command: len(command)
        self.Serial = MagicMock(return_value=self.connection)


class TestFLIFilterWheelPlugin(unittest.TestCase):
    def create_wheel(self, filterdict=None):
        serial_module = FakeSerialModule()
        if filterdict is None:
            filterdict = {"Empty": 1, "Green": 4, "Last": 10}
        with patch.object(fli_module, "_load_serial_module", return_value=serial_module):
            wheel = fli_module.FLIFilterWheelPlugin.create(
                VALID_PARAMETERS,
                filterdict,
            )
        return wheel, serial_module

    def test_plugin_registry_discovers_fli_without_cross_registration(self):
        with patch.object(manager, "DEFAULT_DIRS", [PLUGIN_DIR]):
            registry = manager.PluginRegistry(SimpleNamespace())

        plugin_class = registry.filter_wheels["FLI"]
        self.assertIs(
            plugin_class,
            plugin_utils.get_filter_wheel_plugin_class_from_name("FLI"),
        )
        self.assertNotIn("FLI", registry.processors)
        self.assertNotIn("FLI", registry._writers)
        self.assertEqual(
            plugin_class.required_parameters(),
            ("COMport", "baudrate", "wait_until_done_delay"),
        )

    def test_missing_required_parameters_fail_before_serial_connection(self):
        for missing_key in VALID_PARAMETERS:
            with self.subTest(missing_key=missing_key):
                parameters = dict(VALID_PARAMETERS)
                del parameters[missing_key]
                with patch.object(fli_module, "_load_serial_module") as load_serial:
                    with self.assertRaisesRegex(ValueError, missing_key):
                        fli_module.FLIFilterWheelPlugin.create(
                            parameters,
                            {"Empty": 1},
                        )
                load_serial.assert_not_called()

    def test_invalid_configuration_fails_before_serial_connection(self):
        invalid_cases = (
            (dict(VALID_PARAMETERS, COMport=""), {"Empty": 1}),
            (dict(VALID_PARAMETERS, baudrate=0), {"Empty": 1}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=0), {"Empty": 1}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=float("nan")), {"Empty": 1}),
            (VALID_PARAMETERS, {}),
            (VALID_PARAMETERS, {"Empty": True}),
            (VALID_PARAMETERS, {"Empty": -1}),
            (VALID_PARAMETERS, {"Empty": 0}),
            (VALID_PARAMETERS, {"Empty": 11}),
            (VALID_PARAMETERS, {"Empty": (1, 2)}),
        )
        for parameters, filterdict in invalid_cases:
            with self.subTest(parameters=parameters, filterdict=filterdict):
                with patch.object(fli_module, "_load_serial_module") as load_serial:
                    with self.assertRaises(ValueError):
                        fli_module.FLIFilterWheelPlugin.create(
                            parameters,
                            filterdict,
                        )
                load_serial.assert_not_called()

    def test_serial_connection_uses_working_framing(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        serial_module.Serial.assert_called_once_with(
            port="COM9",
            baudrate=9600,
            bytesize=serial_module.EIGHTBITS,
            parity=serial_module.PARITY_NONE,
            stopbits=serial_module.STOPBITS_TWO,
            timeout=0,
            write_timeout=0,
            xonxoff=False,
        )

    def test_configured_positions_are_sent_without_conversion(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        wheel.set_filter("Empty")
        wheel.set_filter("Green")
        wheel.set_filter("Last")

        self.assertEqual(
            serial_module.connection.write.call_args_list,
            [
                unittest.mock.call(b"1\n"),
                unittest.mock.call(b"4\n"),
                unittest.mock.call(b"10\n"),
            ],
        )
        serial_module.connection.read.assert_not_called()

    def test_unknown_filter_name_does_not_write(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        with self.assertRaisesRegex(ValueError, "Missing"):
            wheel.set_filter("Missing")

        serial_module.connection.write.assert_not_called()

    def test_wait_until_done_uses_configured_delay(self):
        wheel, _ = self.create_wheel()
        self.addCleanup(wheel.close)

        with patch.object(fli_module.time, "sleep") as sleep:
            wheel.set_filter("Empty", wait_until_done=False)
            sleep.assert_not_called()
            wheel.set_filter("Empty", wait_until_done=True)
            sleep.assert_called_once_with(0.2)

    def test_partial_write_faults_and_closes_driver(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.write.side_effect = None
        serial_module.connection.write.return_value = 1

        with self.assertRaisesRegex(IOError, "1 of 2"):
            wheel.set_filter("Green")

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_flush_failure_faults_and_closes_driver(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.flush.side_effect = IOError("flush failed")

        with patch.object(fli_module.logger, "exception"):
            with self.assertRaisesRegex(IOError, "flush failed"):
                wheel.set_filter("Green")

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_close_is_idempotent_and_prevents_further_commands(self):
        wheel, serial_module = self.create_wheel()

        wheel.close()
        wheel.close()

        serial_module.connection.close.assert_called_once_with()
        serial_module.connection.flush.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            wheel.set_filter("Empty")


if __name__ == "__main__":
    unittest.main()
