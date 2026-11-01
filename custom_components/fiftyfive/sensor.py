"""Sensor platform for Fiftyfive."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from .entity import FiftyfiveEntity
from .meter import MeterEstimate
from .sources import ExternalEnergy, measurement
from .const import CONF_LOCAL_SOURCES, CONF_POWER_ENTITY, CONF_ENERGY_ENTITY, CONF_MAX_POWER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import FiftyfiveDataUpdateCoordinator
    from .data import FiftyfiveConfigEntry


@dataclass(frozen=True, kw_only=True)
class FiftyfiveSensorEntityDescription(SensorEntityDescription):
    """Class describing 50five sensor entities."""

    value_fn: Callable


_DURATION_RE = re.compile(r"(?:(\d+)d)?(\d+):(\d+)")


def hm_to_m(value: str) -> int:
    """Convert portal hh:mm or NdHH:mm duration into minutes."""
    if not value:
        return 0
    match = _DURATION_RE.fullmatch(value)
    if not match:
        return 0
    days, hours, minutes = match.groups()
    return int(days or 0) * 24 * 60 + int(hours) * 60 + int(minutes)


ENTITY_DESCRIPTIONS = (
    FiftyfiveSensorEntityDescription(
        key="power_draw",
        translation_key="power_draw",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        # ``MOM_POWER_KW`` is unreliable and often reads 0/null even while
        # charging (upstream issue #27).  Prefer it when it actually carries a
        # value, otherwise fall back to ``LIVE_POWER_KW`` which is derived from
        # the portal's own charging-power graph (the ``current`` service).
        value_fn=lambda network: (
            network.get("MOM_POWER_KW")
            or network.get("LIVE_POWER_KW")
            or 0
        ),
    ),
    FiftyfiveSensorEntityDescription(
        key="transaction_energy_delivered",
        translation_key="transaction_energy_delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda network: network["TRANS_ENERGY_DELIVERED_KWH"] or 0,
    ),
    FiftyfiveSensorEntityDescription(
        key="transaction_duration",
        translation_key="transaction_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda network: hm_to_m(network["TRANSACTION_TIME_H_M"]),
    ),
    FiftyfiveSensorEntityDescription(
        key="transaction_card",
        translation_key="transaction_card",
        # When no session is active the portal returns an empty CARDID which
        # would surface as "unknown"/"onbekend" in Home Assistant. Show a
        # clear "Geen" (none) value instead.
        value_fn=lambda network: network["CARDID"] or "Geen",
    ),
    FiftyfiveSensorEntityDescription(
        key="status",
        translation_key="status",
        value_fn=lambda network: network["NOTIFICATION"],
    ),
    FiftyfiveSensorEntityDescription(
        key="total_energy_delivered",
        translation_key="total_energy_delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        # Account-wide total energy delivered by all recharge spots.
        # Queried from the portal's totalUsage(mode="rechargeSpot") service.
        value_fn=lambda network: network.get("TOTAL_ENERGY_KWH"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: FiftyfiveConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    bridges = {
        str(network["IDX"]): FiftyfiveSourceBridge(
            hass, entry.runtime_data.coordinator, network["IDX"],
            entry.options.get(CONF_LOCAL_SOURCES, {}).get(str(network["IDX"]), {}),
        )
        for network in entry.runtime_data.coordinator.data
    }
    entities: list = [
        FiftyfiveChargerSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
            idx=network["IDX"],
            source=bridges[str(network["IDX"])],
        )
        for entity_description in ENTITY_DESCRIPTIONS
        for network in entry.runtime_data.coordinator.data
    ]

    entities.extend(
        FiftyfiveMeterSensor(entry.runtime_data.coordinator, network["IDX"], bridges[str(network["IDX"])])
        for network in entry.runtime_data.coordinator.data
    )
    async_add_entities(entities)


class FiftyfiveChargerSensor(FiftyfiveEntity, SensorEntity):
    """Fiftyfive Sensor class."""

    def __init__(
        self,
        coordinator: FiftyfiveDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        idx: str,
        source=None,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, idx)
        self.source = source
        self.entity_description = entity_description
        self._attr_unique_id = f"{idx}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Keep valid local measurements available during a portal outage."""
        if self.source is not None:
            if self.entity_description.key == "power_draw" and self.source.read(CONF_POWER_ENTITY, "power") is not None:
                return self.source.power() is not None
            if self.entity_description.key == "transaction_energy_delivered" and self.source.read(CONF_ENERGY_ENTITY, "energy") is not None:
                return self.source.value is not None
        return super().available

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        if self.source is not None:
            if self.entity_description.key == "power_draw":
                return self.source.power()
            if self.entity_description.key == "transaction_energy_delivered":
                return self.source.session_energy()
        return self.entity_description.value_fn(self.network)

    async def async_added_to_hass(self) -> None:
        """Refresh local measurements immediately on external state changes."""
        await super().async_added_to_hass()
        if self.source is not None and self.source.entities:
            self.async_on_remove(async_track_state_change_event(
                self.hass, self.source.entities, self._local_changed,
            ))

    @callback
    def _local_changed(self, event) -> None:
        self.source.refresh()
        self.async_write_ha_state()



class FiftyfiveMeterSensor(FiftyfiveEntity, RestoreSensor):
    """Absolute meter plus cumulative session energy, corrected by official logs."""

    _attr_translation_key = "hardware_meter"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: FiftyfiveDataUpdateCoordinator, idx: str, source=None) -> None:
        """Initialize a separate meter for each charger (channel 1)."""
        super().__init__(coordinator, idx)
        self._attr_unique_id = f"{idx}_hardware_meter"
        self.source = source
        self._meter = source.portal if source is not None else MeterEstimate()

    @property
    def available(self) -> bool:
        """The external counter can continue while the portal is offline."""
        if self.source is not None and self.source.local_energy_available and self.source.value is not None:
            return True
        return super().available

    @property
    def native_value(self) -> float | None:
        """Return the current absolute meter estimate in kWh."""
        return self.source.value if self.source is not None else self._meter.value

    @property
    def extra_state_attributes(self) -> dict:
        """Persist the official anchor separately from the estimated total."""
        return {
            "external_energy": self.source.restore_data if self.source is not None else None,
            "meter_event": self._meter.event,
            "session_energy_kwh": self._meter.energy_kwh,
            "meter_source": (
                "external" if self.source is not None and self.source.local_energy_available
                else "session" if self._meter.event and self._meter.event["kind"] == "start"
                else "official"
            ),
        }

    async def async_added_to_hass(self) -> None:
        """Restore the anchor and session progress without counting it twice."""
        await super().async_added_to_hass()
        previous = await self.async_get_last_sensor_data()
        if previous is not None:
            try:
                value = float(previous.native_value)
            except (TypeError, ValueError):
                pass
            else:
                if isfinite(value) and value >= 0:
                    if previous.native_unit_of_measurement == UnitOfEnergy.WATT_HOUR:
                        self._meter.value = value / 1000
                    elif previous.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
                        self._meter.value = value
        if (state := await self.async_get_last_state()) is not None:
            if self.source is not None:
                self.source.restore(state.attributes.get("external_energy"))
            event = state.attributes.get("meter_event")
            if isinstance(event, dict) and event.get("kind") in ("start", "stop") and isinstance(event.get("wh"), int) and event["wh"] >= 0:
                self._meter.update(event, state.attributes.get("session_energy_kwh"))
        self._update_meter()
        if self.source is not None and self.source.entities:
            self.async_on_remove(async_track_state_change_event(
                self.hass, self.source.entities, self._local_changed,
            ))
        self.async_write_ha_state()

    def _update_meter(self) -> None:
        """Apply a cumulative session reading or a new official anchor."""
        if self.source is not None:
            self.source.refresh()
            return
        self._meter.update(
            self.network.get("METER_EVENT"),
            self.network.get("TRANS_ENERGY_DELIVERED_KWH"),
        )

    @callback
    def _local_changed(self, event) -> None:
        self._update_meter()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update before writing coordinator state."""
        self._update_meter()
        super()._handle_coordinator_update()


class FiftyfiveSourceBridge:
    """Share optional local readings across one charger's energy sensors."""

    def __init__(self, hass, coordinator, idx, options):
        self.hass = hass
        self.coordinator = coordinator
        self.idx = idx
        self.options = options
        self.portal = MeterEstimate()
        self.external = ExternalEnergy()
        self.last_power = None
        self.start_wh = None
        self.local_energy_available = False
        self.value = None
        self.entities = [options[k] for k in (CONF_POWER_ENTITY, CONF_ENERGY_ENTITY) if options.get(k)]

    @property
    def network(self):
        return next(n for n in self.coordinator.data if n["IDX"] == self.idx)

    def read(self, key, kind):
        entity_id = self.options.get(key)
        return measurement(self.hass.states.get(entity_id), kind) if entity_id else None

    def refresh(self):
        self.portal.update(self.network.get("METER_EVENT"), self.network.get("TRANS_ENERGY_DELIVERED_KWH"))
        if self.portal.event and self.portal.event["kind"] == "start":
            self.start_wh = self.portal.event["wh"]
        raw = self.read(CONF_ENERGY_ENTITY, "energy")
        self.local_energy_available = raw is not None
        if self.options.get(CONF_ENERGY_ENTITY):
            self.value = self.external.update(self.portal.event, self.portal.value, raw)
        else:
            self.value = self.portal.value

    def power(self):
        local = self.read(CONF_POWER_ENTITY, "power")
        if local is not None:
            if local <= self.options.get(CONF_MAX_POWER, 11.0):
                self.last_power = local
            return self.last_power
        return self.network.get("MOM_POWER_KW") or self.network.get("LIVE_POWER_KW") or 0

    def session_energy(self):
        self.refresh()
        if self.options.get(CONF_ENERGY_ENTITY) and self.portal.event and self.start_wh is not None:
            if self.portal.event["kind"] == "stop":
                return max(0.0, (self.portal.event["wh"] - self.start_wh) / 1000)
            if self.value is not None:
                return max(0.0, self.value - self.start_wh / 1000)
        return self.network.get("TRANS_ENERGY_DELIVERED_KWH") or 0

    @property
    def restore_data(self):
        return {"entity_id": self.options.get(CONF_ENERGY_ENTITY), "raw": self.external.last_raw,
                "value": self.external.value, "event": self.external.event, "start_wh": self.start_wh}

    def restore(self, data):
        if not isinstance(data, dict) or data.get("entity_id") != self.options.get(CONF_ENERGY_ENTITY):
            return
        for key in ("raw", "value"):
            value = data.get(key)
            if value is not None and (not isinstance(value, (int, float)) or not isfinite(value) or value < 0):
                return
        if data.get("event") is not None and not isinstance(data["event"], dict):
            return
        start = data.get("start_wh")
        if isinstance(start, int) and start >= 0:
            self.start_wh = start
        self.external.last_raw = data.get("raw")
        self.external.value = data.get("value")
        self.external.event = data.get("event")
