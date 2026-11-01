"""Tariff, calendar and reconciliation regression tests."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location("costs", Path(__file__).resolve().parents[1] / "custom_components/fiftyfive/costs.py")
costs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(costs)


def at(value):
    return datetime.fromisoformat(value).timestamp()


class PriceTests(unittest.TestCase):
    def test_price_units_and_negative_prices(self):
        for value, unit, currency, expected in ((0.3, "EUR/kWh", "EUR", 0.3), (30, "ct/kWh", "EUR", 0.3), (300, "EUR/MWh", "EUR", 0.3), (-0.1, "€/kWh", "EUR", -0.1), (3, "SEK/kWh", "SEK", 3)):
            state = SimpleNamespace(state=str(value), attributes={"unit_of_measurement": unit})
            self.assertAlmostEqual(costs.price_value(state, currency), expected)

    def test_invalid_and_wrong_currency(self):
        self.assertIsNone(costs.price_value(None, "EUR"))
        for value, unit in (("unavailable", "EUR/kWh"), ("NaN", "EUR/kWh"), ("inf", "EUR/kWh"), (1, "SEK/kWh"), (1, "kWh")):
            self.assertIsNone(costs.price_value(SimpleNamespace(state=str(value), attributes={"unit_of_measurement": unit}), "EUR"))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = costs.CostLedger()
        self.now = at("2026-11-01T12:00:00+01:00")

    def test_fixed_cost_no_historical_backcharge_or_double_count(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 5000, "one", 0.3)
        ledger.observe(now + 60, 5002, "one", 0.3)
        ledger.observe(now + 120, 5002, "one", 0.3)
        for period in ("session", "day", "month", "total"):
            self.assertAlmostEqual(ledger.result(period, now + 120)[0], 0.6)

    def test_dynamic_tariff_weights_intervals(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.2)
        ledger.observe(now + 300, 100, "one", 0.4)
        ledger.observe(now + 600, 102, "one", 0.4)
        self.assertAlmostEqual(ledger.total_cost, 0.6)
        ledger.observe(now + 900, 103, "one", 0.4)
        self.assertAlmostEqual(ledger.total_cost, 1)

    def test_new_price_does_not_reprice_old_interval(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.2)
        ledger.observe(now + 60, 101, "one", 0.8)
        self.assertAlmostEqual(ledger.total_cost, 0.2)
        ledger.observe(now + 120, 102, "one", 0.8)
        self.assertAlmostEqual(ledger.total_cost, 1)

    def test_negative_tariff(self):
        self.ledger.observe(self.now, 100, "one", -0.1)
        self.ledger.observe(self.now + 60, 102, "one", -0.1)
        self.assertAlmostEqual(self.ledger.total_cost, -0.2)

    def test_day_and_month_boundary(self):
        ledger = self.ledger
        begin = at("2026-10-31T23:55:00+01:00")
        end = at("2026-11-01T00:05:00+01:00")
        ledger.observe(begin, 100, "one", 0.3)
        ledger.observe(end, 102, "one", 0.3)
        self.assertAlmostEqual(ledger.result("day", end)[0], 0.3)
        self.assertAlmostEqual(ledger.result("month", end)[0], 0.3)
        self.assertAlmostEqual(ledger.result("total", end)[0], 0.6)

    def test_new_session_resets_only_session(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.3)
        ledger.observe(now + 60, 102, "one", 0.3)
        ledger.observe(now + 120, 102, "two", 0.3, start_energy=102)
        ledger.observe(now + 180, 103, "two", 0.3)
        self.assertAlmostEqual(ledger.session_cost, 0.3)
        self.assertAlmostEqual(ledger.total_cost, 0.9)

    def test_correction_uses_original_rates_and_original_calendar_day(self):
        ledger = self.ledger
        begin = at("2026-10-31T23:00:00+01:00")
        end = at("2026-11-01T00:00:00+01:00")
        ledger.observe(begin, 100, "one", 0.3)
        ledger.observe(begin + 60, 102, "one", 0.3)
        ledger.observe(end, 101, "one", 0.9)
        self.assertAlmostEqual(ledger.total_cost, 0.3)
        self.assertAlmostEqual(ledger.days["2026-10-31"][0], 0.3)
        self.assertEqual(ledger.result("day", end)[0], 0)

    def test_missing_price_is_unpriced_energy(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", None)
        ledger.observe(now + 60, 102, "one", 0.3)
        ledger.observe(now + 120, 103, "one", 0.3)
        self.assertAlmostEqual(ledger.total_unpriced, 2)
        self.assertAlmostEqual(ledger.total_cost, 0.3)

    def test_restore_without_double_count(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.3)
        ledger.observe(now + 60, 102, "one", 0.3)
        restored = costs.CostLedger()
        restored.restore(json.loads(json.dumps(ledger.dump())))
        restored.observe(now + 120, 102, "one", 0.3)
        restored.observe(now + 180, 103, "one", 0.3)
        self.assertAlmostEqual(restored.total_cost, 0.9)

    def test_session_stops_but_daily_total_can_continue(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.3)
        ledger.observe(now + 60, 102, "one", 0.3, active=False)
        ledger.observe(now + 120, 103, "one", 0.3, active=False)
        self.assertAlmostEqual(ledger.session_cost, 0.6)
        self.assertAlmostEqual(ledger.total_cost, 0.9)

    def test_dynamic_downtime_not_priced_at_current_tariff(self):
        ledger, now = self.ledger, self.now
        ledger.observe(now, 100, "one", 0.3)
        restored = costs.CostLedger()
        restored.restore(ledger.dump())
        restored.resume(now + 3600, True)
        restored.observe(now + 3600, 102, "one", 0.8)
        self.assertEqual(restored.total_cost, 0)
        self.assertEqual(restored.total_unpriced, 2)

    def test_dst_local_midnight_splitting(self):
        begin = at("2026-10-24T23:00:00+02:00")
        end = at("2026-10-26T00:00:00+01:00")
        self.ledger.observe(begin, 100, "one", 1)
        self.ledger.observe(end, 126, "one", 1)
        self.assertAlmostEqual(self.ledger.days["2026-10-24"][0], 1)
        self.assertAlmostEqual(self.ledger.days["2026-10-25"][0], 25)


if __name__ == "__main__":
    unittest.main()
