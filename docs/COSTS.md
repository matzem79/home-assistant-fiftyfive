# Charging cost sensors

## Setup

Install version 0.12.0, restart Home Assistant, then open
**Settings → Devices & services → 50five → Configure** and choose your charger.
The cost options share the existing source-selection form. Select one mode:

| Mode | Required input | Calculation |
| --- | --- | --- |
| Disabled | None | No cost entities; saved accounting remains stored |
| Fixed price | Price per kWh | Newly observed energy × fixed price |
| Price entity | An existing HA tariff sensor | Energy deltas × observed time-dependent price |

A fixed value of `0.30` means 30 cents/kWh when HA uses EUR. Enter the total
variable price you want to account for, including taxes/charges as appropriate.
Fixed standing fees and supplier billing adjustments are not included.

For Tibber, select its **current electricity price** entity, not a total-cost or
consumption sensor. There is no direct Tibber API dependency. Tibber must already
be configured in HA; the integration only reads the selected entity.

The currency is HA's configured currency. Accepted units are `EUR/kWh`,
`EUR/MWh` (or the corresponding configured currency), plus `€/kWh`,
`ct/kWh`, `c/kWh`, and `EURct/kWh` for EUR. Mismatched currencies are rejected;
no currency conversion is performed. Negative prices and a fixed zero price
are valid. An unavailable/non-numeric price is missing, not zero.

## Entities

Each priced wallbox gets four entities, attached to its existing device:

| Entity | Scope | Reset |
| --- | --- | --- |
| Session cost / Kosten Sitzung | Recorded costs of the current or last session | Next observed official start |
| Cost today / Kosten heute | Recorded cost allocated to the current local date | Local midnight |
| Monthly cost / Kosten Monat | Recorded cost allocated to the current local month | Local first day of month |
| Total cost / Kosten gesamt | Cost recorded since activation | No automatic reset |

Each uses `device_class: monetary`, HA's currency and `state_class: total`.
Session/day/month resets include `last_reset` metadata. Negative tariff costs
and official meter corrections may decrease a value. Display precision is two
decimals; calculations and stored state retain more precision.

Attributes:

- `current_price_per_kwh`: current normalized tariff (or null).
- `price_available`: whether a current tariff can be read.
- `unpriced_energy_kwh`: observed energy in this period for which price was missing.
- `cost_complete`: false if the numeric result is only the known subtotal.

A displayed zero with `cost_complete: false` must not be read as free charging.
Missing historical prices are not later replaced with the current tariff.

## Which energy is used?

The shared wallbox meter is the input. If an external energy source is selected,
its aligned counter increments are used; otherwise the portal's cumulative
transaction energy and official meter logs are used. Power is never integrated
for costs, so a power sensor alone does not make cost accounting more granular.
The first observed valid absolute reading establishes the baseline and is not
charged as historic consumption. New official starts delimit sessions; an
already-running session is only counted from the first recorded sample.

All four entities share one ledger. Repeated polling and reads of individual
entities do not charge the same increment again. Official downward meter
corrections reverse the most recently booked energy of the session at its
original tariff and original date, rather than today's price. A new official
session start establishes a new boundary and does not reprice older sessions.
After a stop, later meter increments can still count towards daily/monthly/
total costs (for example standby consumption), but not towards the closed session.

## Dynamic price accuracy

HA state-change events record tariff changes as they are observed. If two energy
readings span a tariff change or local midnight, the intervening energy is split
in proportion to elapsed time across those periods. This assumes uniform use
between changed energy readings. For example, 2 kWh observed over equal durations
at 0.20 and 0.40 EUR/kWh produces 0.60 EUR.

The portal's roughly 15-minute energy updates and delayed start/stop logs limit
accuracy. Frequent ESPHome/Shelly/other cumulative energy updates reduce that
uncertainty. Historical tariffs are not fetched from Recorder or Tibber, and
this feature cannot reconstruct the true minute-by-minute consumption of a
period for which readings were not observed. It is a running estimate, not a
billing-grade accounting system.

Local day/month boundaries use HA's time zone, including daylight-saving changes.
A one-minute timer updates the calendar views even when no sensor event arrives.

## Persistence, gaps and configuration changes

The ledger is saved in HA `.storage` under a key containing the config-entry ID
and charger ID. It is not stored in the Git repository. Updates are saved with
a five-second delay; normal unload/reload and HA shutdown flush accounting.
An abrupt power loss can lose the newest unsaved changes.

Restarts preserve totals, the energy baseline, tariff periods and current
session accounting. Energy consumed during a gap can only be recognized if the
underlying absolute meter catches up later. During a dynamic-price downtime,
prices not observed while HA was stopped are marked unknown. A later energy
increment spanning that gap contributes unpriced energy for its unknown parts.
For a fixed unchanged tariff, recovered energy can be priced at that tariff.

Changing the energy-source entity starts a new meter baseline without discarding
cost totals. Disabling cost calculation retains totals but clears its energy
baseline; re-enabling starts observing again without billing the disabled gap.
Changing HA's currency starts a new ledger in that currency; previous amounts
are not converted. Back up HA before changing its currency if old totals matter.
Changing tariff settings does not reprice already recorded consumption.

Session boundaries depend on charger logs. When a new session cannot be
identified yet, session attribution can lag behind local energy updates. A
separate meter can include standby consumption and line losses; see
[external meter boundaries](EXTERNAL-METERS.md).

## Validation

19 new isolated tests cover tariff units, fixed/dynamic/negative prices, missing
prices, restarts, session boundaries, calendar changes including DST, end-reading
corrections, and the shared HA sensor adapter. All 48 local tests pass.
The cost options and actual Tibber entities have not yet been tested in a real
HA installation. Existing upstream lint/hassfest checks still need to run on
GitHub because a full HA environment is not available locally.

Sources: [HA Tibber integration](https://www.home-assistant.io/integrations/tibber/),
[HA sensor semantics](https://developers.home-assistant.io/docs/core/entity/sensor/).
