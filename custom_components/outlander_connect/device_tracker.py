"""GPS tracker with the vehicle's actual location timestamp."""
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity

from .const import DOMAIN, CONF_GPS
from .entity import OutlanderEntity


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.options.get(CONF_GPS, True):
        async_add_entities([OutlanderTracker(hass.data[DOMAIN][entry.entry_id])])


class OutlanderTracker(OutlanderEntity, TrackerEntity):
    _attr_name = "Location"
    _attr_icon = "mdi:car"
    _attr_source_type = SourceType.GPS
    _attr_entity_category = None

    def __init__(self, coordinator):
        super().__init__(coordinator, "gps_updated")
        # Location identity must differ from the diagnostic timestamp sensor.
        self._attr_unique_id = self._attr_unique_id.removesuffix("gps_updated") + "location"

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data.gps is not None

    @property
    def latitude(self):
        return self.coordinator.data.gps[0] if self.coordinator.data.gps else None

    @property
    def longitude(self):
        return self.coordinator.data.gps[1] if self.coordinator.data.gps else None

    @property
    def location_accuracy(self):
        return 0  # API supplies no accuracy estimate.
