# Outlander Connect for Home Assistant

Read-only cloud sensors and GPS tracking for the **North American Mitsubishi Connect** service. Tested with a **Canadian 2023 Mitsubishi Outlander PHEV** on Home Assistant **2026.10.3**. Other models, markets and accounts are unverified.

**AI-agent disclosure:** This project was coded using an **AI coding agent (OpenAI Codex)**, with protocol research and hands-on testing by the vehicle owner.

This is an independent community integration, not an official Mitsubishi product or an integration shipped with Home Assistant. It requires a working Mitsubishi Connect account and service access. It runs directly in Home Assistant without extra hardware, a separate PC service or MQTT broker.

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories** and add `https://github.com/gmaclean1981/ha-outlander-connect` with type **Integration**.
2. Download **Outlander Connect** and restart Home Assistant.
3. Go to **Settings ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Devices & services ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Add integration ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Outlander Connect**.
4. Enter your Mitsubishi Connect email and password directly in Home Assistant, then select the vehicle. No remote-control PIN is required.

This is a custom repository, not a listing in the default HACS catalogue. Manual installation is also supported: copy `custom_components/outlander_connect` to `/config/custom_components/outlander_connect` and restart.

Home Assistant stores credentials in its integration configuration. Protect configuration files and backups. Do not post credentials, tokens, VINs, location history or raw cloud exports in issues.

## Sensors and tracker

- Drive battery percentage, EV range, combined range and odometer.
- Charging, charge cable connected, ignition and cloud accessibility.
- Door, hood and tailgate openings, headlights and available warning indicators.
- GPS tracker, independent source timestamps and last successful cloud poll.
- A **Refresh cloud reports** button.

There are 40 integration entities: 33 enabled and seven raw diagnostics disabled by default. Availability depends on the fields returned for your vehicle. Missing fields and unknown codes remain unavailable. A closed door does not establish whether it is locked. Cloud accessibility does not mean LAN reachability.

Charging and cable codes 2/0 are mapped from observations on the tested vehicle. Other codes remain unknown. Unverified gasoline range, temperature, theft-alarm and time-to-full fields are available only as disabled raw diagnostics. This release does not claim a validated charging-power or charging-completion-time sensor.

## Polling, timestamps and GPS

State reports are polled every **five minutes**, with health and mileage-history reports at most every **15 minutes**. Options allow a 1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“60 minute state interval and disabling the GPS tracker. All entities share requests. The refresh button uses the same client and rate-limit backoff; no explicit vehicle wake or control commands are sent.

Successful cloud polling can return cached vehicle data. Inspect the independent location, charging, health and odometer timestamps before treating a measurement as current. An optional health-read failure makes health-derived readings unavailable while successful state readings remain usable.

Distance defaults to kilometres for the tested Canadian deployment; explicit health-report km/mi markers take precedence. EV range requires an electric-labelled range entry. The unverified gasoline field is never substituted for EV or combined range.

GPS uses Home Assistant zones and maps. The API supplies no accuracy estimate. Invalid, missing and (0,0) coordinates remain unavailable. Location may be stale. Recorder settings control history retention; disabling the tracker does not delete existing history.

Tokens refresh automatically. Expired credentials trigger Home Assistant reauthentication. HTTP 429 causes shared backoff. Only authentication, vehicle listing and the tested read-only state, health and mileage-report endpoints are allowed by the client.

## Daily distance and driving time (v0.2.0)

Eight sensors read Mitsubishi Connect's Mileage Tracker records:

- **Distance driven today** and **Distance driven yesterday**, in kilometres.
- **Driving time today** and **Driving time yesterday**, in minutes.
- **Distance driven this month/year** and **Driving time this month/year** report the current calendar month and year-to-date totals.

Yearly history is fetched at most hourly, plus the shared refresh button. The yearly distance sensor includes `monthly_history` for monthly comparisons. Monthly and yearly totals are read from the service report, with explicit units; they are not estimates from recorder history. Missing or failed yearly reports leave daily readings working.

The North American service returned miles (`MI`) and minutes (`MIN`) for the tested Canadian account. Miles are converted using exactly 1.609344 km per mile; explicit `KM` reports are already kilometres. Ten daily records were compared with the owner's iPhone app and matched its displayed kilometres and driving minutes. The app's `hh:mm` display is represented as minutes in Home Assistant (for example, 01:02 becomes 62 min).

Reports use Home Assistant's configured time zone. A second monthly request is made only when yesterday falls in the previous month. Every state update selects calendar dates afresh, so an old day's total is never presented as today's total at midnight. Missing days stay unavailable; only explicit zero records mean zero driving. Server reports may arrive late or be corrected. These daily totals are not monotonic counters and have no cumulative statistics state class.

Each sensor includes `period_date`, `timezone`, `history_last_fetched` and fetch status. **Distance driven today** also carries `daily_history`: the current month's available dates, kilometres and driving minutes for custom charts. Historical records in this attribute are not automatically backfilled into Home Assistant's recorder or long-term statistics. A history-read failure leaves normal vehicle sensors working and makes affected history readings unavailable. The refresh button requests history through the same rate-limited client.

An existing **Observed daily distance** Utility Meter remains separate. It estimates increases in cloud odometer readings from its installation date and can differ from Mitsubishi's trip log. You may retain it for comparison. Official daily totals need no Utility Meter helper.

### Upgrading an existing installation

Update this integration through HACS and restart Home Assistant. Your existing vehicle entry, credentials, device/entity IDs and helpers are retained; the history sensors are added to the same device. Do not remove and recreate the integration.

## Validation and development

Live setup, sensor updates, GPS, manual cloud refresh and restart persistence were verified on the tested vehicle and Home Assistant version. Thirty-four offline tests cover field mapping, source timestamps, missing/unknown data, token refresh, bounded authentication retries, rate-limit handling, error sanitization and blocking command endpoints. They use synthetic responses and never contact Mitsubishi. History coverage includes unit conversion, missing versus zero days, invalid records, month/year rollover and the expanded read-only allowlist.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

No vehicle exports, account credentials or owner location data are included. A broader vehicle compatibility test matrix and historical statistics backfill remain future work.

## Attribution and license

MIT licensed. Authentication header methods are adapted from [pcartwright81/mitsubishi_connect_client](https://github.com/pcartwright81/mitsubishi_connect_client), commit `80a3a114586976e7b6542980b0fdc44514b6d30d`. The upstream MIT notice is preserved in `custom_components/outlander_connect/LICENSE-UPSTREAM`. No upstream vehicle-control methods are included.
