# 50five for Home Assistant: 2FA and external meters

Custom integration for 50five-managed EV chargers, with e-mail two-factor
login, an absolute wallbox energy sensor, and optional external power and
energy measurements.

This fork extends [pimhofstee's 2FA branch](https://github.com/pimhofstee/home-assistant-fiftyfive/tree/feature/add-2fa-support),
based on [Crazy-Duck's original integration](https://github.com/Crazy-Duck/home-assistant-fiftyfive).
Original authorship and the GPL-3.0 license are preserved.

## Features

- Charger status, power, transaction energy and duration, card information.
- Start/stop charging with a selected card, unlock, block/unblock, soft/hard reset.
- E-mail 2FA setup with session-cookie reuse and persistence across HA restarts.
- Absolute **hardware meter** in kWh, anchored to official `Meter start` and
  `Meter stop` readings from the charger log.
- Between official readings: cumulative transaction energy from the portal,
  or faster updates from an optional external energy counter.
- Independent, optional external power and energy sources per charger.
- Configurable external power spike rejection (default: above 11 kW).
- Stored meter offset and progress survive Home Assistant restarts.

## Installation

Requires Home Assistant 2026.1 or newer, as declared in `hacs.json`.

### HACS custom repository

After this fork is published:

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/matzem79/home-assistant-fiftyfive`, category **Integration**.
3. Download **50five** and restart Home Assistant.
4. Add the integration under **Settings → Devices & services**.

The integration domain remains `fiftyfive`. Install one fork at a time. To
switch from another 50five fork, back up the existing component directory and
replace it with this version; the existing config entry and entity IDs can be
reused. HACS must track this fork to avoid overwriting it with another fork's
updates.

### Manual installation

1. Back up `/config/custom_components/fiftyfive`.
2. Replace that directory with this repository's `custom_components/fiftyfive`.
3. Restart Home Assistant.

## Account setup and 2FA

Enter your e-mail address, password, market and customer type. If the portal
requires 2FA, enter the code sent by e-mail. The authenticated cookies are
reused for polling and updated in the config entry.

When the portal session expires, portal entities become unavailable and a
notification asks you to sign in again. Open **Reconfigure** and complete 2FA
manually. The integration does not automatically request another e-mail code.
Valid external measurements can continue while the portal is unavailable;
new official anchors and charger commands still require a valid session.

## External power and energy sources

Open **Settings → Devices & services → 50five → Configure**. Choose a charger,
then select either source independently. Leave a field empty to use the portal.

| External selection | Power sensor | Session energy and absolute meter |
| --- | --- | --- |
| None | Portal | Portal transaction energy + official meter logs |
| Power only | External | Portal transaction energy + official meter logs |
| Energy only | Portal | External counter increments + official meter logs |
| Power and energy | External | External counter increments + official meter logs |

External power accepts **W or kW**; energy accepts a cumulative **Wh or kWh**
counter. Both integration energy sensors publish **kWh**, and power publishes
**kW**. Energy is not derived by integrating the external power sensor.

The input is a normal Home Assistant sensor: ESPHome pulse meters, suitable
Shelly energy meters, Modbus meters, MQTT meters or a dedicated upstream meter
can supply it. There is no direct ESPHome or Shelly dependency in this feature.
A three-phase source must provide the sum across all phases for the charger.

The measurement must cover **only this wallbox**. A whole-house meter or a
circuit shared with other loads cannot represent the wallbox's energy. A meter
before the wallbox can include standby use and cable losses that its internal
meter excludes. The calculated absolute meter is aligned with official charger
readings, so it is not an independent lifetime reading of that upstream meter.

External power above the configured limit (default **11 kW**) is discarded;
the last accepted power remains visible. This limit can be adjusted for a
different charger rating. Zero is valid. An unavailable external power source
falls back to the portal. Invalid units, negative values, NaN and infinity are
not used. The original input entity is never changed.

See [external meter behaviour and examples](docs/EXTERNAL-METERS.md).

## Charging costs

Under **50five → Configure**, choose a charger and set **Cost calculation**:

- **Disabled:** no cost sensors; existing saved totals are retained.
- **Fixed price:** enter the price per kWh in your HA-configured currency,
  for example `0.30` EUR/kWh.
- **Price entity:** select a live tariff sensor, for example Tibber's current
  electricity price. Supported units are the HA currency per kWh or MWh;
  EUR cent/kWh values are also accepted. Negative prices are supported.

Four monetary entities appear on the charger: **Session cost**, **Cost today**,
**Monthly cost** and **Total cost**. Tracking starts with the first valid energy
sample after activation; past charging history is not retroactively billed.
Totals survive HA restarts and are independent of whether external energy
is selected. Local calendar days/months use the HA time zone.

Dynamic tariffs are applied to energy increments using observed price changes.
For delayed energy samples, increments are distributed uniformly across the
elapsed price/day periods. Frequent external energy updates improve accuracy.
Missing prices are recorded as `unpriced_energy_kwh`; `cost_complete: false`
means the displayed numeric cost is only the known subtotal. No missing price
is silently assumed to be zero. This is an estimate, not a supplier invoice.

See [cost accounting and configuration](docs/COSTS.md) for restart gaps,
reconciliation and reset behaviour. Cost accounting is covered by isolated tests
but has not yet been verified in a live HA/Tibber installation.

## Absolute hardware meter

During a transaction the portal calculation is:

```text
absolute meter (kWh) = official Meter start (Wh) / 1000 + transaction energy (kWh)
```

With an external energy source, its increments advance the aligned meter and
session energy instead. Its raw total need not equal the wallbox's lifetime
reading. On each new official start/end reading the aligned value is corrected,
including downward corrections. `state_class: total` allows these corrections
without treating them as a reset. The entity keeps its stable unique ID
`<charger IDX>_hardware_meter`.

Without a usable official anchor, local increments cannot establish the
wallbox's absolute reading. Missing data never resets the meter to zero.
The existing **account-wide total energy** is a separate portal statistic.

## Commands and history

Buttons and actions remain available for start/stop, unlock, block/unblock and
soft/hard reset. Starting requires the charge card RFID. Optional local sensors
do not control charging.

Portal power history is imported at startup and hourly for chargers using
portal power. For a charger with external power selected, history imports are
skipped so portal averages do not overwrite external measurement statistics.
Previously recorded history is retained. The upstream actions
`fiftyfive.import_power_history` and `fiftyfive.check_for_update` remain available.
The update checker now points to this fork; releases must be published here.

## Validation and limitations

The owner reported that the modified integration works in their Home Assistant
installation with an ESPHome pulse meter. This is a user-reported functional
check, not independent validation of every failure/recovery scenario. Shelly,
Modbus, MQTT and separate upstream meters are compatible by the sensor contract
but have not been tested with hardware in this project.

Local dependency-free tests cover meter parsing, kWh conversion, session
accounting, official corrections, restarts, external counter resets, outage
recovery, source selection and power spike rejection:

```sh
python3 -m unittest discover -s tests -v
```

The HA options dialog and firmware are not covered by these isolated tests.
This extension currently uses charger **channel 1**. The portal normally updates
transaction energy about every 15 minutes. External measurements update as HA
receives their state changes. Delayed portal logs and counter outages can cause
interim differences; official readings provide the eventual reconciliation.
A hardware meter replacement/reset needs separate handling.

## Development and release

See [fork preparation](FORK-PREPARATION.md), [changelog](CHANGELOG.md) and
[contribution guidelines](CONTRIBUTING.md). A German implementation and test
record is available in [METER-COUNTER.md](METER-COUNTER.md).
