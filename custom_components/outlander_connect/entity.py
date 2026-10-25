"""Shared vehicle identity and per-field freshness."""
import hashlib

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_VEHICLE


def vehicle_key(vin):
    return hashlib.sha256(vin.encode()).hexdigest()[:20]


class OutlanderEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{vehicle_key(coordinator.vin)}_{key}"
        v = coordinator.entry.data.get(CONF_VEHICLE, {})
        model = str(v.get("model") or "Outlander PHEV")
        label = f"{v.get('year', '')} {model}".strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle_key(coordinator.vin))},
            name=label, manufacturer="Mitsubishi Motors", model=model,
        )

    @property
    def reading(self):
        return self.coordinator.data.readings.get(self.key)

    @property
    def available(self):
        if not super().available:
            return False
        reading = self.reading
        return reading is not None and reading.value is not None and (
            reading.source != "health" or self.coordinator.data.health_ok
        )

    @property
    def extra_state_attributes(self):
        reading = self.reading
        if reading is None:
            return {}
        attrs = {"source": reading.source, "last_cloud_poll": self.coordinator.data.polled_at.isoformat()}
        if reading.updated_at is not None:
            attrs["vehicle_data_timestamp"] = reading.updated_at.isoformat()
        else:
            attrs["vehicle_data_timestamp_known"] = False
        if reading.raw_code is not None:
            attrs["raw_code"] = reading.raw_code
        if reading.source == "health":
            attrs["health_fetch_success"] = self.coordinator.data.health_ok
        return attrs
