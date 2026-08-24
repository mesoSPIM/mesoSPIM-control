import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mesoSPIM.src.plugins import manager
from mesoSPIM.src.plugins.FilterWheels import LudlFilterWheelPlugin as ludl_module
from mesoSPIM.src.plugins import utils as plugin_utils


PLUGIN_DIR = Path(ludl_module.__file__).parent
VALID_PARAMETERS = {
    "COMport": "COM7",
    "baudrate": 115200,
    "wait_until_done_delay": 0.25,
}


class FakeSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_TWO = 2

    def __init__(self):
        self.connection = MagicMock()
        self.connection.write.side_effect = lambda command: len(command)
        self.Serial = MagicMock(return_value=self.connection)


class TestLudlFilterWheelPlugin(unittest.TestCase):
    def create_wheel(self, filterdict=None):
        serial_module = FakeSerialModule()
        if filterdict is None:
            filterdict = {"Empty": 0, "Green": 3}
        with patch.object(ludl_module, "_load_serial_module", return_value=serial_module):
            wheel = ludl_module.LudlFilterWheelPlugin.create(
                VALID_PARAMETERS,
                filterdict,
            )
        return wheel, serial_module

    def test_plugin_registry_discovers_ludl_without_cross_registration(self):
        with patch.object(manager, "DEFAULT_DIRS", [PLUGIN_DIR]):
            registry = manager.PluginRegistry(SimpleNamespace())

        plugin_class = registry.filter_wheels["LudlPlugin"]
        self.assertIs(plugin_class, plugin_utils.get_filter_wheel_plugin_class_from_name("LudlPlugin"))
        self.assertNotIn("LudlPlugin", registry.processors)
        self.assertNotIn("LudlPlugin", registry._writers)
        self.assertEqual(
            plugin_class.required_parameters(),
            ("COMport", "baudrate", "wait_until_done_delay"),
        )

    def test_runtime_lookup_rejects_incompatible_api_version(self):
        class IncompatiblePlugin:
            @classmethod
            def api_version(cls):
                return "1.0.0"

            @classmethod
            def name(cls):
                return "IncompatibleWheel"

            @classmethod
            def description(cls):
                return "Test plugin"

            @classmethod
            def required_parameters(cls):
                return ()

            @classmethod
            def create(cls, filterwheel_parameters, filterdict):
                raise AssertionError("must not be created")

        with patch.object(manager, "DEFAULT_DIRS", []):
            registry = manager.PluginRegistry(SimpleNamespace())
        self.assertFalse(registry.register_filter_wheel(IncompatiblePlugin))
        self.assertIsNone(
            plugin_utils.get_filter_wheel_plugin_class_from_name("IncompatibleWheel")
        )

    def test_reserved_legacy_names_are_rejected(self):
        class ReservedNamePlugin:
            @classmethod
            def api_version(cls):
                return "0.0.1"

            @classmethod
            def name(cls):
                return "Ludl"

            @classmethod
            def description(cls):
                return "Test plugin"

            @classmethod
            def required_parameters(cls):
                return ()

            @classmethod
            def create(cls, filterwheel_parameters, filterdict):
                raise AssertionError("must not be created")

        with patch.object(manager, "DEFAULT_DIRS", []):
            registry = manager.PluginRegistry(SimpleNamespace())
        self.assertFalse(registry.register_filter_wheel(ReservedNamePlugin))
        self.assertNotIn("Ludl", registry.filter_wheels)

    def test_runtime_lookup_uses_explicit_registry_entries(self):
        class HookRegisteredPlugin:
            @classmethod
            def api_version(cls):
                return "0.0.1"

            @classmethod
            def name(cls):
                return "HookRegisteredWheel"

            @classmethod
            def description(cls):
                return "Test plugin"

            @classmethod
            def required_parameters(cls):
                return ()

            @classmethod
            def create(cls, filterwheel_parameters, filterdict):
                raise AssertionError("must not be created")

        with patch.object(manager, "DEFAULT_DIRS", []):
            registry = manager.PluginRegistry(SimpleNamespace())
        self.assertFalse(registry.register_filter_wheel(manager.FilterWheelPlugin))
        self.assertTrue(registry.register_filter_wheel(HookRegisteredPlugin))
        self.assertIs(
            plugin_utils.get_filter_wheel_plugin_class_from_name("HookRegisteredWheel"),
            HookRegisteredPlugin,
        )

    def test_duplicate_plugin_name_does_not_replace_registered_class(self):
        class DuplicateLudlPlugin(ludl_module.LudlFilterWheelPlugin):
            pass

        with patch.object(manager, "DEFAULT_DIRS", [PLUGIN_DIR]):
            registry = manager.PluginRegistry(SimpleNamespace())
        original = registry.filter_wheels["LudlPlugin"]
        self.assertFalse(registry.register_filter_wheel(DuplicateLudlPlugin))
        self.assertIs(registry.filter_wheels["LudlPlugin"], original)

    def test_missing_required_parameters_fail_before_serial_connection(self):
        for missing_key in VALID_PARAMETERS:
            with self.subTest(missing_key=missing_key):
                parameters = dict(VALID_PARAMETERS)
                del parameters[missing_key]
                with patch.object(ludl_module, "_load_serial_module") as load_serial:
                    with self.assertRaisesRegex(ValueError, missing_key):
                        ludl_module.LudlFilterWheelPlugin.create(
                            parameters,
                            {"Empty": 0},
                        )
                load_serial.assert_not_called()

    def test_serial_connection_uses_ludl_settings(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        serial_module.Serial.assert_called_once_with(
            port="COM7",
            baudrate=115200,
            bytesize=serial_module.EIGHTBITS,
            parity=serial_module.PARITY_NONE,
            stopbits=serial_module.STOPBITS_TWO,
            timeout=0,
            write_timeout=1,
            xonxoff=False,
        )

    def test_single_wheel_command(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        wheel.set_filter("Green")

        serial_module.connection.write.assert_called_once_with(b"Rotat S M 3\n")
        self.assertEqual(serial_module.connection.flush.call_count, 2)

    def test_dual_wheel_commands(self):
        wheel, serial_module = self.create_wheel({"Empty": (0, 1), "Green": (3, 4)})
        self.addCleanup(wheel.close)

        wheel.set_filter("Green")

        self.assertEqual(
            serial_module.connection.write.call_args_list,
            [
                unittest.mock.call(b"Rotat S M 3\n"),
                unittest.mock.call(b"Rotat S A 4\n"),
            ],
        )

    def test_invalid_filter_mappings_fail_before_serial_connection(self):
        invalid_filterdicts = (
            {},
            {"Empty": True},
            {"Empty": -1},
            {"Empty": 10},
            {"Empty": (0, 1), "Green": 3},
            {"Empty": (0, 1, 2)},
            {"Empty": (0, 10)},
        )
        for filterdict in invalid_filterdicts:
            with self.subTest(filterdict=filterdict):
                with patch.object(ludl_module, "_load_serial_module") as load_serial:
                    with self.assertRaises(ValueError):
                        ludl_module.LudlFilterWheelPlugin.create(
                            VALID_PARAMETERS,
                            filterdict,
                        )
                load_serial.assert_not_called()

    def test_unknown_filter_name_does_not_write(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)

        with self.assertRaisesRegex(ValueError, "Missing"):
            wheel.set_filter("Missing")

        serial_module.connection.write.assert_not_called()

    def test_partial_serial_write_raises(self):
        wheel, serial_module = self.create_wheel()
        self.addCleanup(wheel.close)
        serial_module.connection.write.side_effect = None
        serial_module.connection.write.return_value = 2

        with self.assertRaisesRegex(IOError, "2 of"):
            wheel.set_filter("Green")
        serial_module.connection.close.assert_called_once_with()
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_invalid_wait_delays_fail_before_serial_connection(self):
        for delay in (0, -1, float("nan"), float("inf"), 61):
            with self.subTest(delay=delay):
                parameters = dict(VALID_PARAMETERS, wait_until_done_delay=delay)
                with patch.object(ludl_module, "_load_serial_module") as load_serial:
                    with self.assertRaisesRegex(ValueError, "between 0 and 60"):
                        ludl_module.LudlFilterWheelPlugin.create(
                            parameters,
                            {"Empty": 0},
                        )
                load_serial.assert_not_called()

    def test_wait_until_done_uses_configured_delay(self):
        wheel, _ = self.create_wheel()
        self.addCleanup(wheel.close)

        with patch.object(ludl_module.time, "sleep") as sleep:
            wheel.set_filter("Empty", wait_until_done=False)
            sleep.assert_not_called()
            wheel.set_filter("Empty", wait_until_done=True)
            sleep.assert_called_once_with(0.25)

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
