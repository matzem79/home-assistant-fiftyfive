# Changelog

## 0.11.0 — prepared, not yet published

- Port upstream issue #83 duration fix: parse `NdHH:mm` as well as `hh:mm`,
  so transactions longer than 24 hours no longer break the duration sensor.
- Add an absolute wallbox energy sensor in kWh using official meter start/end
  readings and cumulative transaction energy between readings.
- Add independently selectable external power and energy sources per charger.
  Accept HA sensor entities from ESPHome, Shelly, Modbus, MQTT or another meter;
  ESPHome is the only hardware setup reported working so far.
- Reconcile external counter increments with official charger readings, restore
  progress after HA restarts, and handle counter resets/outages without adding
  the previous total twice.
- Reject external power spikes above a configurable limit, default 11 kW.
- Keep usable external measurements available during a portal-session outage.
- Skip portal power-history imports for chargers using external power.
- Add English, German, Dutch and French source-selection labels.
- Fix the missing `update_state` data-class field used by the inherited update
  checker. Point repository metadata and update checks at this fork.
- Document setup, independent source selection, meter boundaries and timing
  limitations. Add an optional ESPHome filter example without credentials.
- Add 29 dependency-free local regression tests and a CI test workflow.

### Validation

The owner reported the ESPHome setup working in Home Assistant on 2026-11-01.
This does not certify every recovery scenario, impulse calibration or other
meter hardware. Local tests use HA boundary doubles; full HA/hassfest/lint CI
results must be checked before publishing the release.

### Upstream basis

pimhofstee/home-assistant-fiftyfive, branch `feature/add-2fa-support`,
commit `5000d90f307ce7476f1e5f08965cac959e70faf2`, version 0.10.16.
Based on Crazy-Duck/home-assistant-fiftyfive. The original GPL-3.0 license remains.
