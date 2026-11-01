"""Persistent cost sensors driven by charger energy and optional live prices."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_PRICE_MODE, CONF_FIXED_PRICE, CONF_PRICE_ENTITY, DOMAIN
from .costs import CostLedger, price_value
from .entity import FiftyfiveEntity


async def async_setup_cost_sensors(hass, entry, bridges, add_entities):
    """Load one ledger and register four cost entities for each priced charger."""
    for bridge in bridges.values():
        if bridge.options.get(CONF_PRICE_MODE, "none") == "none":
            store = Store(hass, 1, f"{DOMAIN}_costs_{entry.entry_id}_{bridge.idx}")
            data = await store.async_load()
            if data:
                # Disabling cost tracking preserves totals but pauses billing.
                ledger = data.get("ledger", {})
                ledger.update(last_energy=None, last_energy_time=None, points=[], lots=[])
                await store.async_save(data)
            continue
        controller = CostController(hass, entry, bridge)
        await controller.load()
        entry.runtime_data.cost_controllers.append(controller)
        entities = [FiftyfiveCostSensor(controller, period) for period in ("session", "day", "month", "total")]
        controller.entities = entities
        add_entities(entities)
        controller.start()


class CostController:
    """Account once per energy/price event and persist totals outside entities."""

    def __init__(self, hass, entry, bridge):
        self.hass = hass
        self.entry = entry
        self.bridge = bridge
        self.currency = hass.config.currency
        self.ledger = CostLedger(hass.config.time_zone)
        self.store = Store(hass, 1, f"{DOMAIN}_costs_{entry.entry_id}_{bridge.idx}")
        self.entities = []
        self.price = None
        self._unsubscribers = []

    async def load(self):
        data = await self.store.async_load()
        if data and data.get("currency") == self.currency:
            self.ledger.restore(data.get("ledger"))
            self.ledger.resume(dt_util.utcnow().timestamp(), (self.bridge.options.get(CONF_PRICE_MODE) == "entity" or data.get("price_mode") == "entity"))
        # Different physical energy inputs must not produce a synthetic delta.
        if data and data.get("energy_entity") != self.bridge.options.get("energy_entity"):
            self.ledger.last_energy = None
            self.ledger.last_energy_time = None

    def snapshot(self):
        return {"currency": self.currency, "price_mode": self.bridge.options.get(CONF_PRICE_MODE), "energy_entity": self.bridge.options.get("energy_entity"), "ledger": self.ledger.dump()}

    def start(self):
        self._unsubscribers.append(self.bridge.coordinator.async_add_listener(self.changed))
        entity_ids = list(self.bridge.entities)
        price_entity = self.bridge.options.get(CONF_PRICE_ENTITY)
        if price_entity:
            entity_ids.append(price_entity)
        if entity_ids:
            self._unsubscribers.append(async_track_state_change_event(self.hass, entity_ids, self.changed))
        self._unsubscribers.append(async_track_time_interval(self.hass, self.changed, timedelta(minutes=1)))
        self._unsubscribers.append(self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.save_on_stop))
        self.entry.async_on_unload(self.stop)
        self.bridge.ready_callbacks.append(self.changed)
        self.changed()

    async def save_on_stop(self, event):
        await self.store.async_save(self.snapshot())

    @callback
    def stop(self):
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self.changed in self.bridge.ready_callbacks:
            self.bridge.ready_callbacks.remove(self.changed)

    @callback
    def changed(self, event=None):
        if not self.bridge.ready:
            return
        self.bridge.refresh()
        options = self.bridge.options
        if options.get(CONF_PRICE_MODE) == "fixed":
            self.price = options[CONF_FIXED_PRICE]
        else:
            self.price = price_value(self.hass.states.get(options.get(CONF_PRICE_ENTITY, "")), self.currency)
        anchor = self.bridge.portal.event
        session = self.ledger.session
        if anchor and anchor["kind"] == "start":
            session = f"{anchor.get('transaction')}|{anchor.get('time')}|{anchor['wh']}"
        self.ledger.observe(
            dt_util.utcnow().timestamp(), self.bridge.value, session, self.price,
            anchor["wh"] / 1000 if anchor and anchor["kind"] == "start" else None,
            active=bool(anchor and anchor["kind"] == "start"),
        )
        self.store.async_delay_save(self.snapshot, 5)
        for entity in self.entities:
            if entity.hass is not None:
                entity.async_write_ha_state()


class FiftyfiveCostSensor(FiftyfiveEntity, SensorEntity):
    """Known energy cost for a charging session or calendar period."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    def __init__(self, controller, period):
        super().__init__(controller.bridge.coordinator, controller.bridge.idx)
        self.controller = controller
        self.period = period
        self._attr_unique_id = f"{self.idx}_cost_{period}"
        self._attr_translation_key = f"cost_{period}"
        self._attr_native_unit_of_measurement = controller.currency

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return round(self.controller.ledger.result(self.period, dt_util.utcnow().timestamp())[0], 6)

    @property
    def extra_state_attributes(self):
        missing = self.controller.ledger.result(self.period, dt_util.utcnow().timestamp())[1]
        return {"unpriced_energy_kwh": round(max(0.0, missing), 6),
                "cost_complete": missing < 1e-8, "current_price_per_kwh": self.controller.price,
                "price_available": self.controller.price is not None}

    @property
    def last_reset(self):
        now = dt_util.now()
        if self.period == "day":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.period == "month":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if self.period == "session" and self.controller.ledger.session_started is not None:
            return dt_util.utc_from_timestamp(self.controller.ledger.session_started)
        return None
