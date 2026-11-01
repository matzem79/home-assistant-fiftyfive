"""Dependency-free parser and isolated entity lifecycle tests (no HA runtime)."""
from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive"
spec = importlib.util.spec_from_file_location("meter", ROOT / "meter.py")
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)


class FakeEntity:
    def __init__(self, coordinator, idx):
        self.network = coordinator

    async def async_added_to_hass(self):
        pass

    def async_write_ha_state(self):
        pass

    def _handle_coordinator_update(self):
        pass


class FakeRestore:
    async def async_get_last_state(self):
        return getattr(self, "previous_state", None)

    async def async_get_last_sensor_data(self):
        return self.previous


# Execute the actual sensor class with small HA boundary doubles. This does
# not replace an installation test with Home Assistant and the real portal.
tree = ast.parse((ROOT / "sensor.py").read_text())
node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FiftyfiveMeterSensor")
namespace = dict(FiftyfiveEntity=FakeEntity, RestoreSensor=FakeRestore,
                 UnitOfEnergy=SimpleNamespace(WATT_HOUR="Wh", KILO_WATT_HOUR="kWh"),
                 SensorDeviceClass=SimpleNamespace(ENERGY="energy"),
                 SensorStateClass=SimpleNamespace(TOTAL="total"),
                 MeterEstimate=meter.MeterEstimate,
                 callback=lambda f: f,
                 isfinite=math.isfinite)
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])), "sensor.py", "exec"), namespace)
Sensor = namespace["FiftyfiveMeterSensor"]


class MeterTests(unittest.TestCase):
    def test_readings_ignore_order(self):
        rows = [{"EVENT_DATA": f"Meter stop: {v} Wh"} for v in (3000123, 2900000, 3100000)]
        self.assertEqual(meter.extract_meter_stop(rows), 3100000)
        self.assertEqual(meter.extract_meter_stop(rows[::-1]), 3100000)

    def test_empty_and_invalid(self):
        for rows in (None, {}, [], [None, {}, {"EVENT_DATA": 12}], [{"EVENT_DATA": "Meter stop: -1 Wh"}], [{"EVENT_DATA": "Meter stop: 2 kWh"}]):
            self.assertIsNone(meter.extract_meter_stop(rows))

    def test_start_and_stop(self):
        self.assertEqual(meter.extract_meter_stop([{"EVENT_DATA": "Meter start: 1234 Wh"}, {"EVENT_DATA": "Meter stop: 1000 Wh"}]), 1234)

    def test_zero_and_case(self):
        self.assertEqual(meter.extract_meter_stop([{"EVENT_DATA": "meter STOP: 0 Wh"}]), 0)


def event(kind, wh, tx="1"):
    return {"kind": kind, "wh": wh, "transaction": tx, "time": tx}


class EstimateTests(unittest.TestCase):
    def test_cumulative_session_and_official_correction(self):
        estimate = meter.MeterEstimate()
        start = event("start", 100000)
        for energy in (0, 1.5, 1.5, 3):
            estimate.update(start, energy)
        self.assertEqual(estimate.value, 103)
        estimate.update(event("stop", 102900), 3)
        self.assertEqual(estimate.value, 102.9)
        estimate.update(event("stop", 102900), 3)
        self.assertEqual(estimate.value, 102.9)
        estimate.update(event("start", 102900, "2"), 1)
        self.assertEqual(estimate.value, 103.9)

    def test_missing_and_reset_energy(self):
        estimate = meter.MeterEstimate()
        estimate.update(None, 5)
        self.assertIsNone(estimate.value)
        estimate.update(event("start", 100000), 3)
        for energy in (None, "invalid", float("nan"), -1, 0, 2):
            estimate.update(None, energy)
            self.assertEqual(estimate.value, 103)
        estimate.update(event("stop", 102000), 0)
        self.assertEqual(estimate.value, 102)

    def test_event_order_and_transaction_identity(self):
        rows = [
            {"EVENT_DATA": "Meter stop: 100000 Wh Transaction ID: 1", "LOG_DATE": "01-Nov-2026 12:00:00"},
            {"EVENT_DATA": "Meter start: 100000 Wh Transaction ID: 2", "LOG_DATE": "01-Nov-2026 13:00:00"},
        ]
        latest = meter.extract_meter_event(rows[::-1])
        self.assertEqual(latest["kind"], "start")
        self.assertEqual(latest["transaction"], "2")


class SensorTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_session_without_double_counting(self):
        start = event("start", 100000)
        sensor = Sensor({"METER_EVENT": start, "TRANS_ENERGY_DELIVERED_KWH": 3}, "one")
        sensor.previous = SimpleNamespace(native_value=102, native_unit_of_measurement="kWh")
        sensor.previous_state = SimpleNamespace(attributes={"meter_event": start, "session_energy_kwh": 2})
        await sensor.async_added_to_hass()
        self.assertEqual(sensor.native_value, 103)
        sensor._handle_coordinator_update()
        self.assertEqual(sensor.native_value, 103)
        self.assertEqual(sensor.extra_state_attributes["meter_source"], "session")

    async def test_migrate_wh_and_keep_missing(self):
        sensor = Sensor({}, "one")
        sensor.previous = SimpleNamespace(native_value=2000, native_unit_of_measurement="Wh")
        await sensor.async_added_to_hass()
        self.assertEqual(sensor.native_value, 2)
        sensor._handle_coordinator_update()
        self.assertEqual(sensor.native_value, 2)

    async def test_no_initial_reading_and_charger_isolation(self):
        first = Sensor({}, "one")
        first.previous = None
        await first.async_added_to_hass()
        second = Sensor({"METER_EVENT": event("stop", 5000)}, "two")
        second.previous = None
        await second.async_added_to_hass()
        self.assertEqual(second.native_value, 5)
        self.assertIsNone(first.native_value)

    async def test_invalid_restoration(self):
        for value, unit in ((float("nan"), "Wh"), (-1, "Wh"), ("unknown", "Wh")):
            sensor = Sensor({}, "one")
            sensor.previous = SimpleNamespace(native_value=value, native_unit_of_measurement=unit)
            await sensor.async_added_to_hass()
            self.assertIsNone(sensor.native_value)


if __name__ == "__main__":
    unittest.main()
