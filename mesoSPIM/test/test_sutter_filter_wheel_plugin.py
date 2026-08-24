import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mesoSPIM.src.plugins import manager
from mesoSPIM.src.plugins import utils as plugin_utils
from mesoSPIM.src.plugins.FilterWheels import SutterFilterWheelPlugin as sutter_module


PLUGIN_DIR = Path(sutter_module.__file__).parent
VALID_PARAMETERS = {
    "COMport": "COM8",
    "baudrate": 9600,
    "wheel_speed": 3,
    "wait_until_done_delay": 0.5,
}


class FakeSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_ONE = 1

    def __init__(self, response=None):
        self.response = response
        self.connection = MagicMock()
        self.connection.write.side_effect = lambda command: len(command)
        self.connection.read.side_effect = self.read_response
        self.Serial = MagicMock(return_value=self.connection)

    def read_response(self, _length):
        if self.response is not None:
            return self.response
        command = self.connection.write.call_args.args[0]
        return command + b"\r"


class TestSutterFilterWheelPlugin(unittest.TestCase):
    def create_wheel(self, serial_module=None, filterdict=None):
        if serial_module is None:
            serial_module = FakeSerialModule()
        if filterdict is None:
            filterdict = {"Empty": 0, "Green": 4}
        with patch.object(sutter_module, "_load_serial_module", return_value=serial_module):
            wheel = sutter_module.SutterFilterWheelPlugin.create(
                VALID_PARAMETERS,
                filterdict,
            )
        return wheel, serial_module

    def test_plugin_registry_discovers_sutter_without_cross_registration(self):
        with patch.object(manager, "DEFAULT_DIRS", [PLUGIN_DIR]):
            registry = manager.PluginRegistry(SimpleNamespace())

        plugin_class = registry.filter_wheels["SutterPlugin"]
        self.assertIs(
            plugin_class,
            plugin_utils.get_filter_wheel_plugin_class_from_name("SutterPlugin"),
        )
        self.assertNotIn("SutterPlugin", registry.processors)
        self.assertNotIn("SutterPlugin", registry._writers)
        self.assertEqual(
            plugin_class.required_parameters(),
            ("COMport", "baudrate", "wheel_speed", "wait_until_done_delay"),
        )

    def test_missing_required_parameters_fail_before_serial_connection(self):
        for missing_key in VALID_PARAMETERS:
            with self.subTest(missing_key=missing_key):
                parameters = dict(VALID_PARAMETERS)
                del parameters[missing_key]
                with patch.object(sutter_module, "_load_serial_module") as load_serial:
                    with self.assertRaisesRegex(ValueError, missing_key):
                        sutter_module.SutterFilterWheelPlugin.create(
                            parameters,
                            {"Empty": 0},
                        )
                load_serial.assert_not_called()

    def test_invalid_configuration_fails_before_serial_connection(self):
        invalid_cases = (
            (dict(VALID_PARAMETERS, COMport=""), {"Empty": 0}),
            (dict(VALID_PARAMETERS, baudrate=0), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wheel_speed=-1), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wheel_speed=8), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wheel_speed=0), {"Empty": 0, "Green": 4}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=0), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=float("inf")), {"Empty": 0}),
            (VALID_PARAMETERS, {}),
            (VALID_PARAMETERS, {"Empty": True}),
            (VALID_PARAMETERS, {"Empty": -1}),
            (VALID_PARAMETERS, {"Empty": 10}),
            (VALID_PARAMETERS, {"Empty": (0, 1)}),
        )
        for parameters, filterdict in invalid_cases:
            with self.subTest(parameters=parameters, filterdict=filterdict):
                with patch.object(sutter_module, "_load_serial_module") as load_serial:
                    with self.assertRaises(ValueError):
                        sutter_module.SutterFilterWheelPlugin.create(
                            parameters,
                            filterdict,
                        )
                load_serial.assert_not_called()

    def test_serial_connection_and_online_initialization(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        serial_module.Serial.assert_called_once_with(
            port="COM8",
            baudrate=9600,
            bytesize=serial_module.EIGHTBITS,
            parity=serial_module.PARITY_NONE,
            stopbits=serial_module.STOPBITS_ONE,
            timeout=2,
            write_timeout=1,
            xonxoff=False,
        )
        serial_module.connection.reset_input_buffer.assert_called_once_with()
        serial_module.connection.write.assert_called_once_with(b"\xee")
        serial_module.connection.read.assert_called_once_with(2)

    def test_filter_command_combines_speed_and_position(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.write.reset_mock()
        serial_module.connection.read.reset_mock()

        wheel.set_filter("Green")

        serial_module.connection.write.assert_called_once_with(b"\x34")
        serial_module.connection.read.assert_called_once_with(2)
        self.assertEqual(serial_module.connection.reset_input_buffer.call_count, 2)

    def test_unknown_filter_name_does_not_write(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.write.reset_mock()

        with self.assertRaisesRegex(ValueError, "Missing"):
            wheel.set_filter("Missing")

        serial_module.connection.write.assert_not_called()

    def test_wait_until_done_uses_configured_delay(self):
        wheel, _ = self.create_wheel()
        self.addCleanup(wheel.close)

        with patch.object(sutter_module.time, "sleep") as sleep:
            wheel.set_filter("Empty", wait_until_done=False)
            sleep.assert_not_called()
            wheel.set_filter("Empty", wait_until_done=True)
            sleep.assert_called_once_with(0.5)

    def test_short_initialization_response_closes_connection(self):
        serial_module = FakeSerialModule(response=b"\x00")

        with patch.object(sutter_module, "_load_serial_module", return_value=serial_module):
            with self.assertRaisesRegex(TimeoutError, "initialization"):
                sutter_module.SutterFilterWheelPlugin.create(
                    VALID_PARAMETERS,
                    {"Empty": 0},
                )

        serial_module.connection.close.assert_called_once_with()

    def test_partial_movement_write_faults_and_closes_driver(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.write.side_effect = None
        serial_module.connection.write.return_value = 0

        with self.assertRaisesRegex(IOError, "0 of"):
            wheel.set_filter("Green")

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_short_movement_response_faults_and_closes_driver(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.read.side_effect = None
        serial_module.connection.read.return_value = b""

        with self.assertRaisesRegex(TimeoutError, "movement"):
            wheel.set_filter("Green")

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_unexpected_movement_response_faults_and_closes_driver(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.read.side_effect = None
        serial_module.connection.read.return_value = b"\x00\r"

        with self.assertRaisesRegex(IOError, "unexpected response"):
            wheel.set_filter("Green")

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_close_is_idempotent_and_prevents_further_commands(self):
        wheel, serial_module = self.create_wheel()

        wheel.close()
        wheel.close()

        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            wheel.set_filter("Empty")


if __name__ == "__main__":
    unittest.main()
