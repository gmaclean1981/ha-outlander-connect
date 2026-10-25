"""Refresh cached cloud reports; never issue a vehicle wake/control request."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import OutlanderEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RefreshCloudButton(hass.data[DOMAIN][entry.entry_id])])


class RefreshCloudButton(OutlanderEntity, ButtonEntity):
    _attr_name = "Refresh cloud reports"
    _attr_icon = "mdi:cloud-refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "refresh_cloud")

    @property
    def available(self):
        return True  # Allows a recovery attempt after a network failure.

    @property
    def extra_state_attributes(self):
        return {}

    async def async_press(self):
        await self.coordinator.async_refresh_all()
