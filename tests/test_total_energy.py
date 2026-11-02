"""Regression tests for the portal's totalUsage decimal precision."""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

source = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive/api.py"
tree = ast.parse(source.read_text())
client = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FiftyfiveApiClient")
method = next(node for node in client.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_get_total_energy")
namespace = {"TotalUsage": lambda **kwargs: kwargs, "_LOGGER": logging.getLogger(__name__)}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)


class TotalEnergyTests(unittest.IsolatedAsyncioTestCase):
    async def read_energy(self, number, unit):
        api = SimpleNamespace(make_requests=AsyncMock(return_value=[{"number": number, "unit": unit}]))
        return await namespace["async_get_total_energy"](SimpleNamespace(_api=api))

    async def test_variable_decimal_precision_does_not_change_scale(self):
        for number, expected in (("2,349", 2349), ("2,353", 2353), ("2,36", 2360), ("2,360", 2360), ("2,4", 2400)):
            with self.subTest(number=number):
                self.assertAlmostEqual(await self.read_energy(number, "MWh"), expected)

    async def test_units_and_number_formats(self):
        for number, unit, expected in (("2.360,5", "kWh", 2360.5), ("2\u00a0360,5", "kWh", 2360.5), ("2.36", "MWh", 2360), (2.36, "MWh", 2360), ("0,00236", "GWh", 2360), ("2360", "kWh", 2360)):
            with self.subTest(number=number, unit=unit):
                self.assertAlmostEqual(await self.read_energy(number, unit), expected)

    async def test_invalid_value_remains_optional(self):
        for number in (None, "", "unavailable"):
            with self.subTest(number=number):
                self.assertIsNone(await self.read_energy(number, "MWh"))


if __name__ == "__main__":
    unittest.main()
