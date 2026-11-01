# External power and energy meters

The 50five integration consumes existing Home Assistant sensor states. It does
not connect to the external meter itself. Set up the device's own integration
first, then select its entities under **50five → Configure** for the appropriate
charger.

## Independent sources

Power and energy are optional independently:

| Selection | Input needed | Behaviour |
| --- | --- | --- |
| Power only | One W/kW sensor | Fast power, portal-based energy |
| Energy only | One cumulative Wh/kWh sensor | External energy progress, portal power |
| Both | Both sensors | External power and energy progress |
| Neither | No additional sensor | Portal-only operation |

Selecting power alone does not create an energy counter by integration.
Selecting energy alone does not derive instantaneous power from energy changes.
No source is a prerequisite for the other. To return to portal-only behaviour,
clear the corresponding fields and save. Settings apply per charger.

## Examples

- **ESPHome pulse meter:** select `WB Ladeleistung` for power and/or
  `WB Energie gesamt` for cumulative energy. This setup was reported working
  by the owner of this fork.
- **Shelly energy meter:** select the device's active power and/or cumulative
  imported active energy for the dedicated wallbox circuit. For three-phase
  charging use a total across all three phases. Check the actual unit of each
  selected entity. Hardware compatibility here is inferred from the sensor
  contract; no Shelly model has been validated with this fork yet.
- **Dedicated meter before the wallbox:** expose its active power and cumulative
  imported active energy through its normal HA integration (for example
  Modbus or MQTT), and select those entities. The measurement circuit must be
  dedicated to the charger.

Shelly devices are available through the [official HA Shelly integration](https://www.home-assistant.io/integrations/shelly/).
Not every Shelly device measures power/energy; choose entities that actually
provide these measurements. This document is not a hardware installation guide.

## Units and measurement boundary

Power: W or kW. Energy: a cumulative counter in Wh or kWh. Unsupported units,
non-numeric states, negative values and non-finite values are ignored.
A signed net import/export total, a whole-house meter or a shared circuit is
not a suitable substitute for the charger's cumulative imported active energy.

A meter upstream of the wallbox can include cable losses and standby energy.
Consequently its deltas can differ from those of the wallbox's internal meter.
The integration uses external deltas for intermediate updates, then aligns the
absolute sensor with new official charger log readings. Keep the original
upstream meter entity if you also want its unadjusted lifetime total.

## Power peaks

The limit is configurable per charger, default 11 kW. A sample above the limit
is discarded; the previous valid power is retained. It is not clipped to 11 kW.
If no valid sample has arrived yet, the output remains unknown. An unavailable
external sensor falls back to portal power. This filter does not alter the
source entity or remove noise pulses from the source energy total.

For ESPHome, [the optional sensor snippet](../examples/esphome/pulse-sensor-filter.yaml)
rejects raw peaks before its EMA filter. Changing firmware is optional; the
integration already filters incoming power. Previously smoothed peaks below
the limit cannot be identified retrospectively as raw spikes.

The example preserves the submitted factors: 0.06 for kW and 0.001 for kWh,
which correspond to 1,000 impulses/kWh. At 10,000 impulses/kWh use 0.006 and
0.0001 instead. Confirm the meter's printed impulse constant before changing
these values. The original comments contradicted the factors, so calibration
has not been claimed as verified. No API keys, OTA passwords or Wi-Fi credentials
are included in the example.

## Alignment, restarts and gaps

The external raw total is tracked independently of the absolute wallbox meter.
Its offset is aligned when an official start/end reading is received. Saved
raw total, offset, start anchor and session progress allow a HA restart without
adding the same energy twice. A different selected energy entity gets a new
baseline rather than inheriting the previous source's raw counter.

A falling external total is treated as a counter reset: the lower value becomes
the next baseline. The unknown reset interval is not estimated. During an
external outage portal energy can advance the meter; on recovery a new external
baseline avoids double counting the outage interval. An official log update
can correct an intermediate estimate downward as well as upward.

Logs may arrive after the physical start/stop, while the external counter keeps
advancing. Alignment occurs when HA receives the log, not at a reconstructed
historic pulse timestamp. Likewise a portal session total may still belong to
the previous session at a transition. These timing limits can create temporary
differences and require live verification. Periodic official readings reconcile
the resulting absolute value. No billing-grade accuracy guarantee is made.

Direct 50five sensor sources are rejected to prevent feedback loops. Avoid
indirect loops through templates as well. When the portal session expires,
valid external measurements can keep updating, but new official readings require
manual 2FA reconfiguration. Account-wide portal totals remain separate.
