"""Mitsubishi Connect cloud sensors for the Canadian Outlander PHEV."""
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CloudClient
from .const import DOMAIN, PLATFORMS
from .coordinator import OutlanderCoordinator


async def async_setup_entry(hass, entry):
    client = CloudClient(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    coordinator = OutlanderCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        client.clear()
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.client.clear()
        return True
    return False
