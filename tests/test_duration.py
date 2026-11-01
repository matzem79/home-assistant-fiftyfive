"""Regression coverage for portal durations including whole days."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

# Load the actual parser and its pattern without importing Home Assistant.
source = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive/sensor.py"
tree = ast.parse(source.read_text())
nodes = [
    node for node in tree.body
    if (isinstance(node, ast.FunctionDef) and node.name == "hm_to_m")
    or (isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "_DURATION_RE"
        for target in node.targets
    ))
]
namespace = {"re": re}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
hm_to_m = namespace["hm_to_m"]


class DurationTests(unittest.TestCase):
    def test_hours_and_minutes(self):
        for value, expected in (("00:00", 0), ("01:30", 90), ("23:55", 1435), ("25:30", 1530)):
            with self.subTest(value=value):
                self.assertEqual(hm_to_m(value), expected)

    def test_one_day(self):
        self.assertEqual(hm_to_m("1d01:30"), 1530)
        self.assertEqual(hm_to_m("1d00:00"), 1440)

    def test_multiple_days(self):
        self.assertEqual(hm_to_m("2d03:15"), 3075)
        self.assertEqual(hm_to_m("12d00:05"), 17285)

    def test_empty_duration(self):
        self.assertEqual(hm_to_m(""), 0)
        self.assertEqual(hm_to_m(None), 0)

    def test_invalid_duration_does_not_break_sensor(self):
        for value in ("unknown", "1d", "01:30 extra", "-1:30", "1d01:30:00"):
            with self.subTest(value=value):
                self.assertEqual(hm_to_m(value), 0)


if __name__ == "__main__":
    unittest.main()
