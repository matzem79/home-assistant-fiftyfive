"""Optional local measurement tests without a Home Assistant installation."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sources = load("sources")
meter = load("meter")


def state(value, unit):
    return SimpleNamespace(state=str(value), attributes={"unit_of_measurement": unit})


class MeasurementTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(sources.measurement(state(11000, "W"), "power"), 11)
        self.assertEqual(sources.measurement(state(11, "kW"), "power"), 11)
        self.assertEqual(sources.measurement(state(1234, "Wh"), "energy"), 1.234)
        self.assertEqual(sources.measurement(state(12, "kWh"), "energy"), 12)

    def test_invalid(self):
        for value in (None, state("unavailable", "kW"), state("unknown", "kW"), state(-1, "kW"), state(float("nan"), "kW"), state(float("inf"), "kW"), state(1, "V")):
            self.assertIsNone(sources.measurement(value, "power"))


class EnergyTests(unittest.TestCase):
    def test_absolute_offset_and_no_double_count(self):
        energy = sources.ExternalEnergy()
        start = {"kind": "start", "wh": 100000}
        self.assertEqual(energy.update(start, 100, 7), 100)
        self.assertEqual(energy.update(start, 101, 7.5), 100.5)
        self.assertEqual(energy.update(start, 101, 7.5), 100.5)
        self.assertEqual(energy.update(start, 101, 8), 101)
        # Portal updates do not replace local pulse increments.
        self.assertEqual(energy.update(start, 102, 8), 101)

    def test_official_end_can_correct_downwards(self):
        energy = sources.ExternalEnergy()
        start = {"kind": "start", "wh": 100000}
        energy.update(start, 100, 7)
        energy.update(start, 103, 10)
        stop = {"kind": "stop", "wh": 102900}
        self.assertEqual(energy.update(stop, 102.9, 10), 102.9)
        self.assertEqual(energy.update(stop, 102.9, 10.1), 103)

    def test_reset_does_not_subtract_or_add_the_previous_counter(self):
        energy = sources.ExternalEnergy()
        event = {"kind": "start", "wh": 100000}
        energy.update(event, 100, 700)
        self.assertEqual(energy.update(event, 100, 701), 101)
        self.assertEqual(energy.update(event, 100, 0.1), 101)
        self.assertEqual(energy.update(event, 100, 0.3), 101.2)

    def test_outage_and_recovery(self):
        energy = sources.ExternalEnergy()
        event = {"kind": "start", "wh": 100000}
        energy.update(event, 100, 7)
        energy.update(event, 100, 8)
        self.assertEqual(energy.update(event, 102, None), 102)
        self.assertEqual(energy.update(event, 102, 10), 102)
        self.assertEqual(energy.update(event, 102, 10.5), 102.5)


# Execute the actual bridge against small state-machine doubles.
tree = ast.parse((ROOT / "sensor.py").read_text())
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FiftyfiveSourceBridge")
namespace = dict(MeterEstimate=meter.MeterEstimate, ExternalEnergy=sources.ExternalEnergy,
                 measurement=sources.measurement, CONF_POWER_ENTITY="power_entity",
                 CONF_ENERGY_ENTITY="energy_entity", CONF_MAX_POWER="max_power_kw",
                 isfinite=__import__("math").isfinite)
exec(compile(ast.Module(body=[node], type_ignores=[]), "sensor.py", "exec"), namespace)
Bridge = namespace["FiftyfiveSourceBridge"]


class BridgeTests(unittest.TestCase):
    def make_bridge(self):
        self.states = {"sensor.esp_power": state(5, "kW"), "sensor.esp_energy": state(7, "kWh")}
        self.network = {"IDX": "one", "METER_EVENT": {"kind": "start", "wh": 100000}, "TRANS_ENERGY_DELIVERED_KWH": 0, "MOM_POWER_KW": 6}
        return Bridge(SimpleNamespace(states=SimpleNamespace(get=self.states.get)), SimpleNamespace(data=[self.network]), "one", {"power_entity": "sensor.esp_power", "energy_entity": "sensor.esp_energy", "max_power_kw": 11})

    def test_spike_discard_zero_and_unavailable_fallback(self):
        bridge = self.make_bridge()
        self.assertEqual(bridge.power(), 5)
        self.states["sensor.esp_power"] = state(35, "kW")
        self.assertEqual(bridge.power(), 5)
        self.states["sensor.esp_power"] = state(11, "kW")
        self.assertEqual(bridge.power(), 11)
        self.states["sensor.esp_power"] = state(0, "kW")
        self.assertEqual(bridge.power(), 0)
        self.states["sensor.esp_power"] = state("unavailable", "kW")
        self.assertEqual(bridge.power(), 6)

    def test_local_session_and_meter(self):
        bridge = self.make_bridge()
        bridge.refresh()
        self.assertEqual(bridge.value, 100)
        self.states["sensor.esp_energy"] = state(8.5, "kWh")
        self.assertEqual(bridge.session_energy(), 1.5)
        self.assertEqual(bridge.value, 101.5)
        self.assertEqual(bridge.session_energy(), 1.5)

    def test_end_corrects_both_energy_sensors(self):
        bridge = self.make_bridge()
        bridge.refresh()
        self.states["sensor.esp_energy"] = state(8.5, "kWh")
        self.assertEqual(bridge.session_energy(), 1.5)
        self.network["METER_EVENT"] = {"kind": "stop", "wh": 101400}
        self.assertEqual(bridge.session_energy(), 1.4)
        self.assertEqual(bridge.value, 101.4)

    def test_restore_preserves_offset_and_counter_increment(self):
        bridge = self.make_bridge()
        bridge.refresh()
        self.states["sensor.esp_energy"] = state(8, "kWh")
        bridge.refresh()
        data = bridge.restore_data
        restored = self.make_bridge()
        restored.restore(data)
        self.states["sensor.esp_energy"] = state(8.5, "kWh")
        restored.refresh()
        self.assertEqual(restored.value, 101.5)

    def test_power_only_keeps_portal_energy(self):
        bridge = self.make_bridge()
        bridge.options.pop("energy_entity")
        self.network["TRANS_ENERGY_DELIVERED_KWH"] = 2
        bridge.refresh()
        self.assertEqual(bridge.power(), 5)
        self.assertEqual(bridge.value, 102)
        self.assertEqual(bridge.session_energy(), 2)

    def test_energy_only_keeps_portal_power(self):
        bridge = self.make_bridge()
        bridge.options.pop("power_entity")
        bridge.refresh()
        self.states["sensor.esp_energy"] = state(9, "kWh")
        self.assertEqual(bridge.power(), 6)
        self.assertEqual(bridge.session_energy(), 2)
        self.assertEqual(bridge.value, 102)

    def test_no_local_entities_uses_portal(self):
        bridge = self.make_bridge()
        bridge.options = {}
        self.network["TRANS_ENERGY_DELIVERED_KWH"] = 2
        bridge.refresh()
        self.assertEqual(bridge.value, 102)
        self.assertEqual(bridge.session_energy(), 2)
        self.assertEqual(bridge.power(), 6)


if __name__ == "__main__":
    unittest.main()
