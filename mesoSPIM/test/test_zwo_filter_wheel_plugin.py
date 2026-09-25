import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mesoSPIM.src.plugins import manager
from mesoSPIM.src.plugins import utils as plugin_utils
from mesoSPIM.src.plugins.FilterWheels import ZWOFilterWheelPlugin as zwo_module


PLUGIN_DIR = Path(zwo_module.__file__).parent
VALID_PARAMETERS = {"wait_until_done_delay": 1.0}
# Run the hardware tests with `python -m mesoSPIM.test.test_zwo_filter_wheel_plugin --hw`
# or by setting MESOSPIM_ZWO_HARDWARE_TEST=1.
HARDWARE_TEST = os.environ.get("MESOSPIM_ZWO_HARDWARE_TEST") == "1" or "--hw" in sys.argv


class FakeEFWModule:
    """Stand-in for pyzwoefw exposing a single 5-slot wheel."""

    def __init__(self, ids=(0,), slot_num=5):
        self.device = MagicMock()
        self.device.IDs = list(ids)
        self.device.GetProperty.return_value = {"slotNum": slot_num}
        self.device.GetPosition.return_value = 0
        self.EFW = MagicMock(return_value=self.device)
        self.__file__ = str(PLUGIN_DIR / "pyzwoefw.py")


class TestZWOFilterWheelPlugin(unittest.TestCase):
    def create_wheel(self, filterdict=None, parameters=None, efw_module=None):
        efw_module = efw_module or FakeEFWModule()
        if filterdict is None:
            filterdict = {"Empty": 0, "Green": 2, "Last": 4}
        with patch.object(zwo_module, "_load_efw_module", return_value=efw_module):
            wheel = zwo_module.ZWOFilterWheelPlugin.create(
                VALID_PARAMETERS if parameters is None else parameters,
                filterdict,
            )
        return wheel, efw_module

    def test_plugin_registry_discovers_zwo_without_cross_registration(self):
        with patch.object(manager, "DEFAULT_DIRS", [PLUGIN_DIR]):
            registry = manager.PluginRegistry(SimpleNamespace())

        plugin_class = registry.filter_wheels["ZWOPlugin"]
        self.assertIs(
            plugin_class,
            plugin_utils.get_filter_wheel_plugin_class_from_name("ZWOPlugin"),
        )
        self.assertNotIn("ZWOPlugin", registry.processors)
        self.assertNotIn("ZWOPlugin", registry._writers)
        self.assertEqual(plugin_class.required_parameters(), ())

    def test_plugin_name_does_not_shadow_the_legacy_zwo_driver(self):
        self.assertNotEqual(zwo_module.ZWOFilterWheelPlugin.name(), "ZWO")
        self.assertNotIn(
            zwo_module.ZWOFilterWheelPlugin.name(),
            manager.RESERVED_FILTER_WHEEL_NAMES,
        )

    def test_omitted_wait_until_done_delay_falls_back_to_the_default(self):
        wheel, _ = self.create_wheel(parameters={})
        self.addCleanup(wheel.close)

        self.assertEqual(
            wheel.wait_until_done_delay, zwo_module.DEFAULT_WAIT_UNTIL_DONE_DELAY
        )

    def test_default_delay_is_applied_when_waiting(self):
        wheel, _ = self.create_wheel(parameters={})
        self.addCleanup(wheel.close)

        with patch.object(zwo_module.time, "sleep") as sleep:
            wheel.set_filter("Green", wait_until_done=True)

        sleep.assert_called_once_with(zwo_module.DEFAULT_WAIT_UNTIL_DONE_DELAY)

    def test_invalid_delay_is_still_rejected_when_supplied(self):
        with patch.object(zwo_module, "_load_efw_module") as load_efw:
            with self.assertRaisesRegex(ValueError, "wait_until_done_delay"):
                zwo_module.ZWOFilterWheelPlugin.create(
                    {"wait_until_done_delay": 0}, {"Empty": 0}
                )
        load_efw.assert_not_called()

    def test_invalid_configuration_fails_before_hardware_access(self):
        invalid_cases = (
            (dict(VALID_PARAMETERS, wait_until_done_delay=0), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=61), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wait_until_done_delay=float("nan")), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wheel_index=-1), {"Empty": 0}),
            (dict(VALID_PARAMETERS, wheel_index=True), {"Empty": 0}),
            (dict(VALID_PARAMETERS, dll_path=""), {"Empty": 0}),
            (VALID_PARAMETERS, {}),
            (VALID_PARAMETERS, {"Empty": True}),
            (VALID_PARAMETERS, {"Empty": -1}),
            (VALID_PARAMETERS, {"Empty": (0, 1)}),
            (VALID_PARAMETERS, {"": 0}),
        )
        for parameters, filterdict in invalid_cases:
            with self.subTest(parameters=parameters, filterdict=filterdict):
                with patch.object(zwo_module, "_load_efw_module") as load_efw:
                    with self.assertRaises(ValueError):
                        zwo_module.ZWOFilterWheelPlugin.create(parameters, filterdict)
                load_efw.assert_not_called()

    def test_bundled_dll_is_used_by_default(self):
        _, efw_module = self.create_wheel()
        dll_path = efw_module.EFW.call_args.args[0]
        self.assertTrue(dll_path.endswith("EFW_filter.dll"))
        self.assertIn("lib", dll_path)

    def test_configured_dll_path_overrides_the_bundled_library(self):
        custom_path = "C:\\custom\\EFW_filter.dll"
        parameters = dict(VALID_PARAMETERS, dll_path=custom_path)
        _, efw_module = self.create_wheel(parameters=parameters)
        efw_module.EFW.assert_called_once_with(custom_path)

    def test_filterdict_exceeding_physical_slots_is_rejected_and_closes(self):
        efw_module = FakeEFWModule(slot_num=5)
        with patch.object(zwo_module, "_load_efw_module", return_value=efw_module):
            with self.assertRaisesRegex(ValueError, "slot count"):
                zwo_module.ZWOFilterWheelPlugin.create(
                    VALID_PARAMETERS, {"Empty": 0, "TooFar": 5}
                )
        efw_module.device.Close.assert_called_once_with(0)

    def test_missing_wheel_index_is_rejected(self):
        efw_module = FakeEFWModule(ids=(0,))
        parameters = dict(VALID_PARAMETERS, wheel_index=1)
        with patch.object(zwo_module, "_load_efw_module", return_value=efw_module):
            with self.assertRaisesRegex(ValueError, "wheel_index"):
                zwo_module.ZWOFilterWheelPlugin.create(parameters, {"Empty": 0})

    def test_second_wheel_is_addressed_by_its_own_id(self):
        efw_module = FakeEFWModule(ids=(0, 7))
        parameters = dict(VALID_PARAMETERS, wheel_index=1)
        wheel, _ = self.create_wheel(parameters=parameters, efw_module=efw_module)
        self.addCleanup(wheel.close)

        wheel.set_filter("Green")

        efw_module.device.SetPosition.assert_called_once_with(7, 2, False)

    def test_configured_slots_are_sent_without_conversion(self):
        wheel, efw_module = self.create_wheel()
        self.addCleanup(wheel.close)

        wheel.set_filter("Empty")
        wheel.set_filter("Green")
        wheel.set_filter("Last")

        self.assertEqual(
            efw_module.device.SetPosition.call_args_list,
            [
                unittest.mock.call(0, 0, False),
                unittest.mock.call(0, 2, False),
                unittest.mock.call(0, 4, False),
            ],
        )

    def test_unknown_filter_name_does_not_move_the_wheel(self):
        wheel, efw_module = self.create_wheel()
        self.addCleanup(wheel.close)

        with self.assertRaisesRegex(ValueError, "Missing"):
            wheel.set_filter("Missing")

        efw_module.device.SetPosition.assert_not_called()

    def test_wait_until_done_blocks_and_uses_configured_delay(self):
        wheel, efw_module = self.create_wheel()
        self.addCleanup(wheel.close)

        with patch.object(zwo_module.time, "sleep") as sleep:
            wheel.set_filter("Empty", wait_until_done=False)
            sleep.assert_not_called()
            wheel.set_filter("Green", wait_until_done=True)
            sleep.assert_called_once_with(1.0)

        self.assertEqual(
            efw_module.device.SetPosition.call_args_list[-1],
            unittest.mock.call(0, 2, True),
        )

    def test_sdk_failure_faults_and_closes_driver(self):
        wheel, efw_module = self.create_wheel()
        efw_module.device.SetPosition.side_effect = IOError("EFW move failed")

        with self.assertRaisesRegex(IOError, "EFW move failed"):
            wheel.set_filter("Green")

        efw_module.device.Close.assert_called_once_with(0)
        with self.assertRaisesRegex(RuntimeError, "faulted"):
            wheel.set_filter("Green")

    def test_close_is_idempotent_and_prevents_further_commands(self):
        wheel, efw_module = self.create_wheel()

        wheel.close()
        wheel.close()

        efw_module.device.Close.assert_called_once_with(0)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            wheel.set_filter("Empty")


@unittest.skipUnless(
    HARDWARE_TEST,
    "Pass --hw (or set MESOSPIM_ZWO_HARDWARE_TEST=1) with a ZWO EFW wheel connected.",
)
class TestZWOFilterWheelHardware(unittest.TestCase):
    """Live-hardware checks. These move the wheel: keep the light path clear."""

    def setUp(self):
        pyzwoefw = zwo_module._load_efw_module()
        device = pyzwoefw.EFW(zwo_module._default_dll_path(pyzwoefw))
        self.n_slots = device.GetProperty(device.IDs[0])["slotNum"]
        device.Close(device.IDs[0])

        self.filterdict = {f"Slot{i}": i for i in range(self.n_slots)}
        self.wheel = zwo_module.ZWOFilterWheelPlugin.create(
            VALID_PARAMETERS, self.filterdict
        )
        self.addCleanup(self.wheel.close)

    def test_every_configured_slot_is_reached(self):
        for name, slot in self.filterdict.items():
            with self.subTest(filter=name):
                self.wheel.set_filter(name, wait_until_done=True)
                self.assertEqual(self.wheel._device.GetPosition(self.wheel._id), slot)

    def test_unknown_filter_name_raises_on_hardware(self):
        with self.assertRaises(ValueError):
            self.wheel.set_filter("NotAFilter", wait_until_done=True)

    def test_oversized_filterdict_is_rejected_by_the_real_wheel(self):
        # The EFW SDK is global: a second handle on the same wheel would close
        # the device underneath the one opened in setUp. Release it first.
        self.wheel.close()
        with self.assertRaisesRegex(ValueError, "slot count"):
            zwo_module.ZWOFilterWheelPlugin.create(
                VALID_PARAMETERS, {"TooFar": self.n_slots}
            )


if __name__ == "__main__":
    sys.argv = [arg for arg in sys.argv if arg != "--hw"]
    unittest.main()
