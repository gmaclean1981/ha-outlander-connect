# Outlander Connect for Home Assistant

Read-only cloud sensors and GPS tracking for the **North American Mitsubishi Connect** service. Tested with a **Canadian 2023 Mitsubishi Outlander PHEV** on Home Assistant **2026.10.3**. Other models, markets and accounts are unverified.

**AI-agent disclosure:** This project was coded using an **AI coding agent (OpenAI Codex)**, with protocol research and hands-on testing by the vehicle owner.

This is an independent community integration, not an official Mitsubishi product or an integration shipped with Home Assistant. It requires a working Mitsubishi Connect account and service access. It runs directly in Home Assistant without extra hardware, a separate PC service or MQTT broker.

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories** and add `https://github.com/gmaclean1981/ha-outlander-connect` with type **Integration**.
2. Download **Outlander Connect** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Outlander Connect**.
4. Enter your Mitsubishi Connect email and password directly in Home Assistant, then select the vehicle. No remote-control PIN is required.

This is a custom repository, not a listing in the default HACS catalogue. Manual installation is also supported: copy `custom_components/outlander_connect` to `/config/custom_components/outlander_connect` and restart.

Home Assistant stores credentials in its integration configuration. Protect configuration files and backups. Do not post credentials, tokens, VINs, location history or raw cloud exports in issues.

## Sensors and tracker

- Drive battery percentage, EV range, combined range and odometer.
- Charging, charge cable connected, ignition and cloud accessibility.
- Door, hood and tailgate openings, headlights and available warning indicators.
- GPS tracker, independent source timestamps and last successful cloud poll.
- A **Refresh cloud reports** button.

There are 32 integration entities: 25 enabled and seven raw diagnostics disabled by default. Availability depends on the fields returned for your vehicle. Missing fields and unknown codes remain unavailable. A closed door does not establish whether it is locked. Cloud accessibility does not mean LAN reachability.

Charging and cable codes 2/0 are mapped from observations on the tested vehicle. Other codes remain unknown. Unverified gasoline range, temperature, theft-alarm and time-to-full fields are available only as disabled raw diagnostics. This release does not claim a validated charging-power or charging-completion-time sensor.

## Polling, timestamps and GPS

State reports are polled every **five minutes**, with health reports at most every **15 minutes**. Options allow a 1–60 minute state interval and disabling the GPS tracker. All entities share requests. The refresh button uses the same client and rate-limit backoff; no explicit vehicle wake or control commands are sent.

Successful cloud polling can return cached vehicle data. Inspect the independent location, charging, health and odometer timestamps before treating a measurement as current. An optional health-read failure makes health-derived readings unavailable while successful state readings remain usable.

Distance defaults to kilometres for the tested Canadian deployment; explicit health-report km/mi markers take precedence. EV range requires an electric-labelled range entry. The unverified gasoline field is never substituted for EV or combined range.

GPS uses Home Assistant zones and maps. The API supplies no accuracy estimate. Invalid, missing and (0,0) coordinates remain unavailable. Location may be stale. Recorder settings control history retention; disabling the tracker does not delete existing history.

Tokens refresh automatically. Expired credentials trigger Home Assistant reauthentication. HTTP 429 causes shared backoff. Only authentication, vehicle listing and the two tested read-only report endpoints are allowed by the client.

## Daily distance and driving time

The Mitsubishi app's authoritative daily distance and driving-time history is not implemented. As an optional approximation, create a Home Assistant **Utility Meter** helper using **Odometer**, a **daily** cycle and a non-resetting source. Leave delta and net consumption disabled. Name it **Observed daily distance**.

This tracks observed odometer increases from installation onward. The first day is incomplete; cloud gaps and midnight attribution can differ from Mitsubishi's trip log. The helper follows Home Assistant's configured time zone. Daily driving duration is not estimated.

## Validation and development

Live setup, sensor updates, GPS, manual cloud refresh and restart persistence were verified on the tested vehicle and Home Assistant version. Sixteen offline tests cover field mapping, source timestamps, missing/unknown data, token refresh, bounded authentication retries, rate-limit handling, error sanitization and blocking command endpoints. They use synthetic responses and never contact Mitsubishi.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

No vehicle exports, account credentials or owner location data are included. A broader compatibility test matrix and official daily trip history remain future work.

## Attribution and license

MIT licensed. Authentication header methods are adapted from [pcartwright81/mitsubishi_connect_client](https://github.com/pcartwright81/mitsubishi_connect_client), commit `80a3a114586976e7b6542980b0fdc44514b6d30d`. The upstream MIT notice is preserved in `custom_components/outlander_connect/LICENSE-UPSTREAM`. No upstream vehicle-control methods are included.
