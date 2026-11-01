"""Observed-tariff cost accounting independent of Home Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo


def price_value(state, currency):
    """Normalize supported tariffs without converting currencies."""
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    if not isfinite(value):
        return None
    unit = str(state.attributes.get("unit_of_measurement", "")).replace(" ", "")
    unit = unit.replace("€", "EUR").replace("£", "GBP")
    if unit == f"{currency}/kWh":
        return value
    if unit == f"{currency}/MWh":
        return value / 1000
    if currency == "EUR" and unit in ("ct/kWh", "c/kWh", "EURct/kWh"):
        return value / 100
    return None


class CostLedger:
    """Price cumulative energy deltas using observed price periods."""

    def __init__(self, timezone="Europe/Berlin"):
        self.timezone = timezone
        self.last_energy = None
        self.last_energy_time = None
        self.last_seen = None
        self.points = []
        self.days = {}
        self.session = None
        self.session_started = None
        self.session_closed = False
        self.session_cost = 0.0
        self.session_unpriced = 0.0
        self.lots = []
        self.total_cost = 0.0
        self.total_unpriced = 0.0

    def dump(self):
        """Return JSON-compatible persistent state."""
        return {k: v for k, v in vars(self).items() if k != "timezone"}

    def restore(self, data):
        """Restore versioned integration storage."""
        if isinstance(data, dict):
            for key in self.dump():
                if key in data:
                    setattr(self, key, data[key])

    def _point(self, when, price):
        if not self.points or self.points[-1][1] != price:
            self.points.append([when, price])

    def resume(self, now, dynamic):
        """Mark unobserved dynamic prices during downtime as missing."""
        if dynamic and self.last_seen is not None and now > self.last_seen:
            self._point(self.last_seen, None)

    def _book(self, day, energy, price, remember=True, session=True):
        bucket = self.days.setdefault(day, [0.0, 0.0])
        cost = energy * price if price is not None else 0.0
        missing = energy if price is None else 0.0
        bucket[0] += cost
        bucket[1] += missing
        self.total_cost += cost
        self.total_unpriced += missing
        if session and self.session is not None:
            self.session_cost += cost
            self.session_unpriced += missing
        if remember:
            if self.lots and self.lots[-1][0] == day and self.lots[-1][2] == price and self.lots[-1][3] == session:
                self.lots[-1][1] += energy
            else:
                self.lots.append([day, energy, price, session])

    def observe(self, now, energy, session, price, start_energy=None, active=True):
        """Distribute energy across observed tariff periods and local days."""
        self._point(now, price)
        self.last_seen = now
        if energy is None or not isfinite(energy) or energy < 0:
            return
        if session is not None and session != self.session:
            self.session = session
            self.session_started = now
            self.session_closed = False
            self.session_cost = 0.0
            self.session_unpriced = 0.0
            self.lots = []
            if self.last_energy is not None and start_energy is not None:
                # A newly observed start establishes a fresh session boundary;
                # do not spread its consumption over the preceding idle time.
                self.last_energy = min(start_energy, energy)
                self.last_energy_time = now
        if self.last_energy is None:
            self.last_energy = energy
            self.last_energy_time = now
            if not active:
                self.session_closed = True
            return
        delta = energy - self.last_energy
        if abs(delta) < 1e-9:
            if not active:
                self.session_closed = True
            return
        if delta < 0:
            remaining = -delta
            while remaining > 1e-9 and self.lots:
                day, amount, rate, charged_session = self.lots[-1]
                correction = min(remaining, amount)
                self._book(day, -correction, rate, remember=False, session=charged_session)
                remaining -= correction
                self.lots[-1][1] -= correction
                if self.lots[-1][1] < 1e-9:
                    self.lots.pop()
        else:
            begin = self.last_energy_time
            boundaries = {begin, now}
            boundaries.update(t for t, _ in self.points if begin < t < now)
            zone = ZoneInfo(self.timezone)
            local = datetime.fromtimestamp(begin, zone)
            midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), zone)
            while midnight.timestamp() < now:
                boundaries.add(midnight.timestamp())
                midnight = datetime.combine(midnight.date() + timedelta(days=1), datetime.min.time(), zone)
            ordered = sorted(boundaries) if now > begin else [now, now]
            for left, right in zip(ordered, ordered[1:]):
                rate = None
                for timestamp, candidate in self.points:
                    if timestamp <= left:
                        rate = candidate
                    else:
                        break
                share = (right - left) / (now - begin) if now > begin else 1
                day = datetime.fromtimestamp(left, zone).date().isoformat()
                self._book(day, delta * share, rate, session=not self.session_closed)
        if not active:
            self.session_closed = True
        self.last_energy = energy
        self.last_energy_time = now
        self.points = self.points[-1:]

    def result(self, period, now):
        """Return known cost and unpriced kWh for a local calendar period."""
        day = datetime.fromtimestamp(now, ZoneInfo(self.timezone)).date().isoformat()
        if period == "session":
            return self.session_cost, self.session_unpriced
        if period == "total":
            return self.total_cost, self.total_unpriced
        if period == "day":
            return tuple(self.days.get(day, [0.0, 0.0]))
        values = [v for k, v in self.days.items() if k[:7] == day[:7]]
        return sum(v[0] for v in values), sum(v[1] for v in values)
