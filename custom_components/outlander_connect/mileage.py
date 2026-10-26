"""Mitsubishi's daily driving records, with explicit units and calendar dates."""
from datetime import date, timedelta
import re

from .data import Reading, number


def parse_month(payload, year, month):
    """Reject ambiguous reports; missing days are never assumed to mean no driving."""
    if not isinstance(payload, dict) or payload.get("status") != "Success" or payload.get("periodType") != "Monthly":
        raise ValueError("Invalid mileage report")
    # startYear/startMonth describe the account's earliest history, not this query.
    if not isinstance(payload.get("data"), list):
        raise ValueError("Missing mileage data")
    factor = {"MI": 1.609344, "KM": 1.0}.get(payload.get("distanceUnit"))
    if factor is None or payload.get("durationUnit") != "MIN":
        raise ValueError("Unknown mileage units")
    records = {}
    for row in payload["data"]:
        if not isinstance(row, dict) or not isinstance(row.get("eventPeriod"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["eventPeriod"]):
            raise ValueError("Invalid mileage day")
        day = date.fromisoformat(row["eventPeriod"])
        if (day.year, day.month) != (year, month) or day in records:
            raise ValueError("Duplicate or misplaced mileage day")
        distance, duration = number(row.get("distance")), number(row.get("duration"))
        # Validate each metric independently. Zero is a real reading, not missing.
        records[day] = {
            "distance_km": round(distance * factor, 6) if distance is not None and distance >= 0 else None,
            "driving_minutes": duration if duration is not None and duration >= 0 else None,
        }
    return records


def apply_mileage(snapshot, reports, today):
    """Select today/yesterday afresh on every state update, including midnight."""
    for prefix, day in (("today", today), ("yesterday", today - timedelta(days=1))):
        report = reports.get((day.year, day.month), {})
        row = report.get("records", {}).get(day, {})
        for metric, unit in (("distance_km", "km"), ("driving_minutes", "min")):
            snapshot.readings[f"{prefix}_{metric}"] = Reading(row.get(metric) if report.get("ok") else None, "mileage", unit=unit)
    return snapshot
