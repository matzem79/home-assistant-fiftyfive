"""Absolute hardware meter readings from transaction logs."""

from __future__ import annotations

import re
from typing import Any

_METER_READING = re.compile(r"\bMeter\s+(?:start|stop):\s*(\d+)\s*Wh\b", re.IGNORECASE)


def extract_meter_stop(rows: Any) -> int | None:
    """Return the highest absolute Wh reading, independent of log ordering."""
    if not isinstance(rows, list):
        return None
    readings = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        event = row.get("EVENT_DATA")
        if isinstance(event, str) and (match := _METER_READING.search(event)):
            readings.append(int(match[1]))
    return max(readings, default=None)


def extract_meter_event(rows: Any) -> dict | None:
    """Identify the latest absolute meter event, including its transaction."""
    from datetime import datetime

    if not isinstance(rows, list):
        return None
    events = []
    pattern = re.compile(r"\bMeter\s+(start|stop):\s*(\d+)\s*Wh\b", re.I)
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("EVENT_DATA"), str):
            continue
        match = pattern.search(row["EVENT_DATA"])
        if not match:
            continue
        date = str(row.get("LOG_DATE") or "")
        timestamp = ""
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                timestamp = datetime.strptime(date, fmt).isoformat()
                break
            except ValueError:
                continue
        tx = re.search(r"Transaction ID:\s*(\d+)", row["EVENT_DATA"], re.I)
        event = {"kind": match[1].lower(), "wh": int(match[2]), "time": date,
                 "transaction": tx[1] if tx else None, "order": timestamp}
        events.append((timestamp, event["wh"], event["kind"] == "stop", event))
    return max(events, key=lambda item: item[:3])[3] if events else None


class MeterEstimate:
    """Combine an absolute start reading with cumulative session energy."""

    def __init__(self) -> None:
        self.event = None
        self.energy_kwh = 0.0
        self.value = None

    def update(self, event: dict | None, energy: Any) -> None:
        """Use official readings as anchors; never repeatedly add a session total."""
        from math import isfinite

        if event is not None and event != self.event:
            # Ignore older log windows. Official events may correct an estimate
            # downward, but an old reading must never replace a newer anchor.
            if self.event is not None:
                if event["wh"] < self.event["wh"]:
                    return
                if event.get("order") and self.event.get("order") and event["order"] < self.event["order"]:
                    return
            self.event = event
            self.energy_kwh = 0.0
            self.value = event["wh"] / 1000
        if self.event is None or self.event["kind"] != "start":
            return
        try:
            energy = float(energy)
        except (TypeError, ValueError):
            return
        if not isfinite(energy) or energy < 0:
            return
        # Reset/decreasing session totals may arrive before the new start log.
        # Wait for that anchor instead of counting a second transaction twice.
        self.energy_kwh = max(self.energy_kwh, energy)
        self.value = self.event["wh"] / 1000 + self.energy_kwh
