"""Optional local measurement sources and absolute energy alignment."""
from __future__ import annotations

from math import isfinite
from typing import Any


def measurement(state: Any, kind: str) -> float | None:
    """Normalize HA energy/power states, rejecting unavailable or invalid values."""
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    units = {"energy": {"Wh": 0.001, "kWh": 1}, "power": {"W": 0.001, "kW": 1}}
    factor = units[kind].get(state.attributes.get("unit_of_measurement"))
    if factor is None or not isfinite(value) or value < 0:
        return None
    return value * factor


class ExternalEnergy:
    """Track local counter deltas separately from the wallbox absolute offset."""

    def __init__(self) -> None:
        self.last_raw = None
        self.value = None
        self.event = None

    def update(self, event: dict | None, portal: float | None, raw: float | None) -> float | None:
        """Align on new official events; otherwise add each local delta once."""
        if event is not None and event != self.event:
            self.event = dict(event)
            self.value = portal
            self.last_raw = raw
            return self.value
        if raw is None:
            # On recovery establish a fresh offset; portal covers the gap.
            self.last_raw = None
            if portal is not None:
                self.value = portal if self.value is None else max(self.value, portal)
            return self.value
        if self.value is None:
            self.value = portal
        if self.value is not None and self.last_raw is not None:
            delta = raw - self.last_raw
            # ESP pulse totals can restart at zero after reboot. Count only
            # subsequent increments; the unknown reboot gap needs the portal.
            if delta >= 0:
                self.value += delta
        self.last_raw = raw
        return self.value
