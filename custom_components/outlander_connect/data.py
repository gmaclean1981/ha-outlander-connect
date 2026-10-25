"""Field mapping with source timestamps, independent of Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def timestamp(value, assume_utc=False):
    try:
        n = number(value)
        if n is not None:
            return datetime.fromtimestamp(n / 1000 if abs(n) > 100_000_000_000 else n, timezone.utc)
        if isinstance(value, str):
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if d.tzinfo is None:
                if not assume_utc:
                    return None
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    return None


def obj(value):
    return value if isinstance(value, dict) else {}


def items(value):
    return value if isinstance(value, list) else []


def code(value):
    return str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else None


@dataclass(frozen=True)
class Reading:
    value: object
    source: str
    updated_at: datetime | None = None
    unit: str | None = None
    raw_code: str | None = None


@dataclass
class Snapshot:
    readings: dict[str, Reading] = field(default_factory=dict)
    gps: tuple[float, float] | None = None
    gps_timestamp: datetime | None = None
    polled_at: datetime | None = None
    health_ok: bool = True


def parse_snapshot(state_response, health_response, *, polled_at=None, health_ok=True):
    state = obj(obj(state_response).get("state"))
    charging = obj(state.get("chargingControl"))
    assume_utc = state.get("timezone") == "UTC"
    charging_ts = timestamp(charging.get("eventTimestamp"), assume_utc)
    reports = obj(health_response).get("vhr", [])
    reports = [r for r in reports if isinstance(r, dict)] if isinstance(reports, list) else []
    report = max(reports, key=lambda r: timestamp(r.get("ts")) or datetime.min.replace(tzinfo=timezone.utc)) if reports else {}
    dt = obj(report.get("dt"))
    diagnostic = obj(dt.get("diagnostic"))
    health_ts = timestamp(obj(diagnostic.get("eventTimestamp")).get("value")) or timestamp(report.get("ts"))
    snapshot = Snapshot(polled_at=polled_at or datetime.now(timezone.utc), health_ok=health_ok)
    values = snapshot.readings

    def put(key, value, source="state", stamp=None, unit=None, raw=None):
        values[key] = Reading(value, source, stamp, unit, raw)

    def health_value(key):
        return obj(diagnostic.get(key)).get("value")

    def choose_numeric(key, state_value, health_key, unit, minimum=0, maximum=None):
        candidates = []
        for value, source, stamp in [(state_value, "state", charging_ts), (health_value(health_key), "health", health_ts)]:
            n = number(value)
            if n is not None and n >= minimum and (maximum is None or n <= maximum):
                candidates.append(Reading(n, source, stamp, unit))
        if candidates:
            # Only compare ages when BOTH sources supply meaningful timestamps.
            if len(candidates) == 2 and all(c.updated_at for c in candidates):
                candidates.sort(key=lambda c: c.updated_at, reverse=True)
            values[key] = candidates[0]
        else:
            put(key, None, unit=unit)

    units_message = str(obj(diagnostic.get("odo")).get("displayMessage", ""))
    units = "mi" if "_mi" in units_message else "km" if "_km" in units_message else None
    if units is None:
        message = str(obj(diagnostic.get("odos")).get("displayMessage", ""))
        units = "mi" if "_mi" in message else "km" if "_km" in message else None
    # This first release is specifically validated for the owner's Canadian model.
    units = units or "km"
    choose_numeric("battery", charging.get("hvBatteryLife"), "batteryLife", "%", maximum=100)
    choose_numeric("combined_range", charging.get("cruisingRangeCombined"), "availRange", units)

    ev_range = None
    second = charging.get("cruisingRangeSecond", [])
    if isinstance(second, list):
        engine = next((code(x.get("engineType")) for x in second if isinstance(x, dict) and "engineType" in x), None)
        if engine == "5":
            ev_range = next((number(x.get("range")) for x in second if isinstance(x, dict) and "range" in x), None)
    if ev_range is not None and ev_range >= 0:
        put("ev_range", ev_range, stamp=charging_ts, unit=units)
    else:
        for group in ("cruisingRangeFirst", "cruisingRangeSecond"):
            for item in items(obj(diagnostic.get(group)).get("cruisingRange")):
                for field_value in obj(item).values():
                    item_value = obj(field_value)
                    if item_value.get("displayMessage") == "range_electric":
                        n = number(item_value.get("value"))
                        if n is not None and n >= 0:
                            put("ev_range", n, "health", health_ts, units)

    odos = []
    for entry in state.get("odo", []) if isinstance(state.get("odo"), list) else []:
        for stamp, raw in obj(entry).items():
            n = number(raw)
            if n is not None and n >= 0:
                odos.append((timestamp(stamp, assume_utc), n))
    if odos:
        dated = [o for o in odos if o[0] is not None]
        stamp, odo = max(dated, key=lambda o: o[0]) if dated else odos[-1]
        put("odometer", odo, stamp=stamp, unit=units)
    hodo = number(health_value("odo"))
    if hodo is not None and hodo >= 0:
        old = values.get("odometer")
        if old is None or (old.updated_at is not None and health_ts is not None and health_ts > old.updated_at):
            put("odometer", hodo, "health", health_ts, units)

    mappings = {
        "charging": ("hvChargingStatus", {"0": False, "2": True}),
        "plugged_in": ("hvChargingPlugStatus", {"0": False, "2": True}),
    }
    for name, (key, mapping) in mappings.items():
        raw = code(charging.get(key))
        put(name, mapping.get(raw), stamp=charging_ts, raw=raw)
        put(name + "_code", raw, stamp=charging_ts)
    ignition = code(state.get("ignitionState"))
    ignition_ts = timestamp(state.get("ignitionStateTs"))
    put("ignition", {"0": False, "1": True}.get(ignition), stamp=ignition_ts, raw=ignition)
    accessible = state.get("accessible")
    put("accessible", accessible if isinstance(accessible, bool) else None)

    for key in ("breakWarn", "engineOilWarn", "tireStatus"):
        warning = obj(diagnostic.get(key)).get("warning")
        put(key, warning if isinstance(warning, bool) else None, "health", health_ts)
    doors = obj(obj(dt.get("vehicleStatus")).get("doorStatus")).get("doors", [])
    positions = {"doorFrontLeft": "front_left_door", "doorFrontRight": "front_right_door", "doorRearLeft": "rear_left_door", "doorRearRight": "rear_right_door", "doorHood": "hood", "doorTrunk": "tailgate"}
    for door in doors if isinstance(doors, list) else []:
        door = obj(door)
        key = positions.get(obj(door.get("position")).get("displayMessage"))
        if key:
            message = obj(door.get("state")).get("displayMessage")
            opened = {"#msg_close_close": False, "#msg_open_open": True}.get(message)
            put(key, opened, "health", health_ts)
    lights = obj(obj(dt.get("vehicleStatus")).get("lightStatus")).get("lights", [])
    for light in lights if isinstance(lights, list) else []:
        light = obj(light)
        if obj(light.get("position")).get("displayMessage") == "lightHead":
            put("headlights", {"#msg_off_off": False, "#msg_on_on": True}.get(obj(light.get("state")).get("displayMessage")), "health", health_ts)

    location = obj(state.get("extLocMap"))
    lat, lon = number(location.get("lat")), number(location.get("lon"))
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0, 0):
        snapshot.gps = (lat, lon)
        snapshot.gps_timestamp = timestamp(location.get("ts"))
    put("gps_updated", snapshot.gps_timestamp, stamp=snapshot.gps_timestamp)
    put("charging_updated", charging_ts, stamp=charging_ts)
    put("health_updated", health_ts, "health", health_ts)
    odometer_reading = values.get("odometer", Reading(None, "state"))
    put("odometer_updated", odometer_reading.updated_at, odometer_reading.source, odometer_reading.updated_at)
    put("last_cloud_poll", snapshot.polled_at, "cloud")
    for key, value in [("time_to_full_raw", charging.get("hvTimeToFullCharge")), ("temperature_raw", state.get("temp")), ("theft_alarm_raw", state.get("theftAlarm"))]:
        put(key, code(value), stamp=charging_ts if key == "time_to_full_raw" else None)
    first_range = charging.get("cruisingRangeFirst", [])
    raw_gas = next((number(x.get("range")) for x in first_range if isinstance(x, dict) and "range" in x), None) if isinstance(first_range, list) else None
    put("gasoline_range_raw", raw_gas, stamp=charging_ts)
    put("health_time_to_full_raw", code(health_value("timeToFullCharge")), "health", health_ts)
    return snapshot
