"""Isolated HA adapter tests for the shared cost controller and sensors."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive"
spec = importlib.util.spec_from_file_location("costs", ROOT / "costs.py")
costs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(costs)


class FakeEntity:
    def __init__(self, coordinator, idx):
        self.idx = idx
        self.hass = None


class FakeSensor:
    pass


class FakeStore:
    def __init__(self, *args):
        self.saves = []

    def async_delay_save(self, data, delay):
        self.saves.append(data())


clock = SimpleNamespace(now=datetime(2026, 11, 1, 12, tzinfo=timezone.utc))
namespace = dict(callback=lambda f: f, Store=FakeStore, CostLedger=costs.CostLedger,
                 price_value=costs.price_value, DOMAIN="fiftyfive", CONF_PRICE_MODE="price_mode",
                 CONF_FIXED_PRICE="fixed_price", CONF_PRICE_ENTITY="price_entity",
                 FiftyfiveEntity=FakeEntity, SensorEntity=FakeSensor,
                 SensorDeviceClass=SimpleNamespace(MONETARY="monetary"),
                 SensorStateClass=SimpleNamespace(TOTAL="total"),
                 dt_util=SimpleNamespace(utcnow=lambda: clock.now, now=lambda: clock.now,
                                        utc_from_timestamp=lambda t: datetime.fromtimestamp(t, timezone.utc)))
nodes = [n for n in ast.parse((ROOT / "cost_sensor.py").read_text()).body if isinstance(n, ast.ClassDef)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), "cost_sensor.py", "exec"), namespace)
Controller = namespace["CostController"]
Sensor = namespace["FiftyfiveCostSensor"]


class ControllerTests(unittest.TestCase):
    def setUp(self):
        clock.now = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        self.states = {}
        self.bridge = SimpleNamespace(options={"price_mode": "fixed", "fixed_price": 0.3},
                                      ready=True, value=100, refresh=lambda: None,
                                      portal=SimpleNamespace(event={"kind": "start", "wh": 100000, "transaction": "1", "time": "start"}),
                                      idx="one", coordinator=None)
        self.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR", time_zone="Europe/Berlin"),
                                    states=SimpleNamespace(get=self.states.get))
        self.controller = Controller(self.hass, SimpleNamespace(entry_id="test"), self.bridge)
        self.sensors = [Sensor(self.controller, p) for p in ("session", "day", "month", "total")]

    def tick(self, minute):
        clock.now = clock.now.replace(minute=minute)
        self.controller.changed()

    def test_four_sensors_share_one_accounting(self):
        self.tick(0)
        self.bridge.value = 102
        self.tick(1)
        self.assertEqual([s.native_value for s in self.sensors], [0.6] * 4)
        self.tick(2)
        self.assertEqual([s.native_value for s in self.sensors], [0.6] * 4)
        self.assertEqual(self.controller.snapshot()["currency"], "EUR")

    def test_dynamic_price_event_preserves_prior_rate(self):
        self.bridge.options = {"price_mode": "entity", "price_entity": "sensor.tariff"}
        self.states["sensor.tariff"] = SimpleNamespace(state="0.2", attributes={"unit_of_measurement": "EUR/kWh"})
        self.tick(0)
        self.states["sensor.tariff"].state = "0.4"
        self.tick(1)
        self.bridge.value = 102
        self.tick(2)
        self.assertAlmostEqual(self.sensors[-1].native_value, 0.6)

    def test_missing_price_exposed_as_incomplete_not_free(self):
        self.bridge.options = {"price_mode": "entity", "price_entity": "sensor.missing"}
        self.tick(0)
        self.bridge.value = 102
        self.tick(1)
        attributes = self.sensors[-1].extra_state_attributes
        self.assertFalse(attributes["cost_complete"])
        self.assertFalse(attributes["price_available"])
        self.assertEqual(attributes["unpriced_energy_kwh"], 2)

    def test_wait_for_restored_meter_before_first_baseline(self):
        self.bridge.ready = False
        self.tick(0)
        self.assertIsNone(self.controller.ledger.last_energy)
        self.assertEqual(self.controller.store.saves, [])
        self.bridge.ready = True
        self.tick(1)
        self.assertEqual(self.controller.ledger.last_energy, 100)

    def test_period_reset_metadata(self):
        self.tick(0)
        self.assertIsNotNone(self.sensors[0].last_reset)
        self.assertEqual(self.sensors[1].last_reset.hour, 0)
        self.assertEqual(self.sensors[2].last_reset.day, 1)
        self.assertIsNone(self.sensors[3].last_reset)


if __name__ == "__main__":
    unittest.main()
