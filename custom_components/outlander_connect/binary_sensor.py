"""Vehicle status; unknown codes remain unavailable rather than false."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import OutlanderEntity

BINARY_SENSORS = (
    BinarySensorEntityDescription(key="charging", name="Charging", device_class=BinarySensorDeviceClass.BATTERY_CHARGING),
    BinarySensorEntityDescription(key="plugged_in", name="Charge cable connected", device_class=BinarySensorDeviceClass.PLUG),
    BinarySensorEntityDescription(key="ignition", name="Ignition", icon="mdi:car-key"),
    BinarySensorEntityDescription(key="accessible", name="Cloud reports vehicle accessible", entity_category=EntityCategory.DIAGNOSTIC),
    *(BinarySensorEntityDescription(key=k, name=n, device_class=BinarySensorDeviceClass.DOOR) for k,n in (
        ("front_left_door", "Front left door"), ("front_right_door", "Front right door"),
        ("rear_left_door", "Rear left door"), ("rear_right_door", "Rear right door"),
        ("hood", "Hood"), ("tailgate", "Tailgate"),
    )),
    BinarySensorEntityDescription(key="headlights", name="Headlights", device_class=BinarySensorDeviceClass.LIGHT),
    *(BinarySensorEntityDescription(key=k, name=n, device_class=BinarySensorDeviceClass.PROBLEM) for k,n in (
        ("breakWarn", "Brake warning"), ("engineOilWarn", "Engine oil pressure warning"), ("tireStatus", "Tyre pressure warning"),
    )),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(OutlanderBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class OutlanderBinarySensor(OutlanderEntity, BinarySensorEntity):
    def __init__(self, coordinator, description):
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self):
        return self.reading.value if self.reading is not None else None
