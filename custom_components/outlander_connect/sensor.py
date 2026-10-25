"""Confirmed vehicle measurements and explicitly unverified diagnostics."""
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import OutlanderEntity


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    dynamic_unit: bool = False


SENSORS = (
    Description(key="battery", name="Drive battery", device_class=SensorDeviceClass.BATTERY, native_unit_of_measurement="%", state_class=SensorStateClass.MEASUREMENT),
    Description(key="ev_range", name="EV range", device_class=SensorDeviceClass.DISTANCE, state_class=SensorStateClass.MEASUREMENT, dynamic_unit=True),
    Description(key="combined_range", name="Combined range", device_class=SensorDeviceClass.DISTANCE, state_class=SensorStateClass.MEASUREMENT, dynamic_unit=True),
    Description(key="odometer", name="Odometer", device_class=SensorDeviceClass.DISTANCE, state_class=SensorStateClass.TOTAL_INCREASING, dynamic_unit=True),
    Description(key="charging_updated", name="Charging data timestamp", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    Description(key="health_updated", name="Health data timestamp", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    Description(key="gps_updated", name="Location data timestamp", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    Description(key="odometer_updated", name="Odometer data timestamp", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    Description(key="last_cloud_poll", name="Last cloud poll", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    *(Description(key=k, name=n, entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False) for k,n in (
        ("charging_code", "Charging status code"), ("plugged_in_code", "Plug status code"),
        ("time_to_full_raw", "Time to full raw — unverified"), ("health_time_to_full_raw", "Health time to full raw — unverified"),
        ("gasoline_range_raw", "Gasoline range raw — unverified"), ("temperature_raw", "Temperature code — unverified"),
        ("theft_alarm_raw", "Theft alarm field — unverified"),
    )),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(OutlanderSensor(coordinator, desc) for desc in SENSORS)


class OutlanderSensor(OutlanderEntity, SensorEntity):
    def __init__(self, coordinator, description):
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.reading.value if self.reading is not None else None

    @property
    def native_unit_of_measurement(self):
        if self.entity_description.dynamic_unit:
            return self.reading.unit if self.reading is not None else None
        return self.entity_description.native_unit_of_measurement
