# Changelog

## 0.2.0

Add Mitsubishi Mileage Tracker daily distance and driving-time sensors for today and yesterday, current-month daily records as attributes, explicit miles-to-kilometres conversion, Home Assistant time-zone requests and calendar rollover handling. History reads share authentication and rate-limit backoff and fail independently of vehicle-state readings. Existing setup and helpers are preserved.

Validated all ten owner-supplied daily app readings against the API; 30 offline tests pass. No account exports or app binaries are included. AI-agent disclosure: coded using OpenAI Codex, with vehicle/app validation by the owner.

## 0.1.0

Initial community release: North American Mitsubishi Connect account setup, read-only sensors, optional GPS tracker, shared polling, token refresh, reauthentication, rate-limit backoff and per-source timestamps. Includes 16 offline tests. Tested with a Canadian 2023 Outlander PHEV on Home Assistant 2026.10.3.

AI-agent disclosure: coded using OpenAI Codex, with protocol research and hands-on testing by the vehicle owner.
