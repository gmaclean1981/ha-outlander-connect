"""Export only nonsensitive status metadata, never raw API payloads."""
from .const import DOMAIN, VERSION, CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES, CONF_GPS


async def async_get_config_entry_diagnostics(hass, entry):
    c = hass.data[DOMAIN][entry.entry_id]
    snapshot = c.data
    return {
        "version": VERSION,
        "region": "North America",
        "poll_minutes": entry.options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES),
        "gps_enabled": entry.options.get(CONF_GPS, True),
        "last_update_success": c.last_update_success,
        "health_fetch_success": snapshot.health_ok,
        "last_cloud_poll": snapshot.polled_at.isoformat(),
        "field_metadata": {
            key: {"present": r.value is not None, "source": r.source,
                  "vehicle_timestamp": r.updated_at.isoformat() if r.updated_at else None}
            for key, r in snapshot.readings.items()
        },
    }
