"""Confirmed vehicle measurements and explicitly unverified diagnostics."""
from dataclasses import dataclass
from datetime import timedelta

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
    Description(key="today_distance_km", name="Distance driven today", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement="km", suggested_display_precision=2),
    Description(key="today_driving_minutes", name="Driving time today", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement="min", suggested_display_precision=0),
    Description(key="yesterday_distance_km", name="Distance driven yesterday", device_class=SensorDeviceClass.DISTANCE, native_unit_of_measurement="km", suggested_display_precision=2),
    Description(key="yesterday_driving_minutes", name="Driving time yesterday", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement="min", suggested_display_precision=0),
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

    @property
    def extra_state_attributes(self):
        attrs = super().extra_state_attributes
        if self.key.startswith(("today_", "yesterday_")):
            day = self.coordinator.mileage_today
            if day is None:
                return attrs
            if self.key.startswith("yesterday_"):
                day -= timedelta(days=1)
            report = self.coordinator.mileage.get((day.year, day.month), {})
            attrs.update(period_date=day.isoformat(), timezone=self.coordinator.mileage_timezone, mileage_fetch_success=report.get("ok", False))
            fetched_at = report.get("fetched_at")
            if fetched_at:
                attrs["history_last_fetched"] = fetched_at.isoformat()
            if self.key == "today_distance_km" and report.get("ok"):
                attrs["daily_history"] = [{"date": d.isoformat(), **values} for d, values in sorted(report.get("records", {}).items()) if d <= self.coordinator.mileage_today]
        return attrs
