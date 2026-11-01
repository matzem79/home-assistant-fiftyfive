"""Exercise the actual options form against HA's selector constraints."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class Marker:
    def __init__(self, key, **kwargs):
        self.key = key
        self.kwargs = kwargs


class Selector:
    def __init__(self, config):
        self.config = config


class NumberSelector(Selector):
    def __init__(self, config):
        # HA NumberSelector.CONFIG_SCHEMA requires step='any' or >= 1e-3:
        # homeassistant/helpers/selector.py (2026.10.4).
        step = config.get("step", 1)
        if step != "any" and float(step) < 1e-3:
            raise ValueError("NumberSelector step must be 'any' or >= 0.001")
        super().__init__(config)


class OptionsFlow:
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


source = Path(__file__).resolve().parents[1] / "custom_components/fiftyfive/config_flow.py"
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "FiftyfiveOptionsFlow")
namespace = {"config_entries": SimpleNamespace(OptionsFlow=OptionsFlow),
             "vol": SimpleNamespace(Schema=lambda value: value, Required=Marker, Optional=Marker),
             "selector": SimpleNamespace(SelectSelector=Selector, SelectSelectorConfig=dict,
                                         NumberSelector=NumberSelector, NumberSelectorConfig=dict,
                                         EntitySelector=Selector, EntitySelectorConfig=dict)}
for name, value in (("CONF_LOCAL_SOURCES", "local_sources"), ("CONF_POWER_ENTITY", "power_entity"),
                    ("CONF_ENERGY_ENTITY", "energy_entity"), ("CONF_MAX_POWER", "max_power_kw"),
                    ("CONF_PRICE_MODE", "price_mode"), ("CONF_FIXED_PRICE", "fixed_price"),
                    ("CONF_PRICE_ENTITY", "price_entity")):
    namespace[name] = value
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
Flow = namespace["FiftyfiveOptionsFlow"]


class OptionsTests(unittest.IsolatedAsyncioTestCase):
    def make_flow(self, saved=None):
        flow = Flow()
        flow.config_entry = SimpleNamespace(options=saved or {}, runtime_data=SimpleNamespace(
            coordinator=SimpleNamespace(data=[{"IDX": "one", "NAME": "Wallbox"}])))
        flow.hass = SimpleNamespace(config=SimpleNamespace(currency="EUR"))
        return flow

    async def test_charger_selection_renders(self):
        result = await self.make_flow().async_step_init()
        self.assertEqual(result["step_id"], "init")

    async def test_source_and_price_form_renders_after_charger_selection(self):
        result = await self.make_flow().async_step_init({"charger": "one"})
        self.assertEqual(result["step_id"], "sources")
        fields = {marker.key: value for marker, value in result["data_schema"].items()}
        self.assertEqual(fields["fixed_price"].config["step"], "any")
        self.assertEqual(fields["fixed_price"].config["unit_of_measurement"], "EUR/kWh")
        self.assertIn("price_entity", fields)

    async def test_saved_precise_tariff_can_be_reopened(self):
        flow = self.make_flow({"local_sources": {"one": {"fixed_price": 0.30251, "price_mode": "fixed"}}})
        result = await flow.async_step_init({"charger": "one"})
        marker = next(m for m in result["data_schema"] if m.key == "fixed_price")
        self.assertEqual(marker.kwargs["description"]["suggested_value"], 0.30251)


if __name__ == "__main__":
    unittest.main()
