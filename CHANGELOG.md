# Changelog

## 0.12.2 — prepared, not yet published

- Preserve the portal decimal separator when converting total energy to kWh;
  variable decimal precision no longer changes the scale. Existing incorrect
  recorder history is not repaired automatically.
- Declare optional recorder use and the EV charging category; skip history
  imports when recorder is not configured. Validate the meter-counter branch
  and pin CI runners to Ubuntu 24.04.
- Add a separate Wallbox dashboard card with original-image crop, charging
  controls, vehicle values, cost sensors and an embedded detail/history view.
  Dashboard installation remains separate from the HACS integration install.
- Local verification: 54 Python tests and 8 card tests pass. Live dashboard
  rendering and GitHub HACS/Hassfest checks still need verification.

## 0.12.1 — prepared, not yet published

- Fix the options form failing to render: HA number selectors reject numeric
  steps below 0.001. Use `step: any` for precise fixed kWh prices.
- Add three options-form regression tests; all 51 local tests pass.

## 0.12.0 — prepared, not yet published

- Add optional per-charger fixed kWh pricing or a live price entity (e.g. Tibber).
- Add session, daily, monthly and lifetime monetary cost sensors.
- Account for observed dynamic and negative prices, local calendar boundaries,
  official meter corrections and unavailable tariff periods.
- Persist accounting across restarts; expose unpriced energy instead of treating
  missing prices as free electricity. Costs start with the first observed sample.
- Add 19 cost-ledger and HA-adapter tests; all 48 local tests pass.
- Cost configuration and a real Tibber price entity still need live validation.

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
