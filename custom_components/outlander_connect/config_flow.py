"""UI setup, account reauthentication, and polling/GPS options."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import CloudClient, CloudError, AuthenticationError, RateLimitError
from .const import DOMAIN, CONF_VIN, CONF_VEHICLE, CONF_POLL_MINUTES, CONF_GPS, DEFAULT_POLL_MINUTES
from .entity import vehicle_key


def credentials_schema(username=""):
    return vol.Schema({
        vol.Required(CONF_USERNAME, default=username): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    })


class OutlanderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._credentials = {}
        self._vehicles = []

    async def _check(self, user_input):
        client = CloudClient(async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        try:
            return await client.async_vehicles()
        finally:
            client.clear()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._vehicles = await self._check(user_input)
                if not self._vehicles:
                    errors["base"] = "no_vehicles"
                else:
                    self._credentials = dict(user_input)
                    return await self.async_step_vehicle()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RateLimitError:
                errors["base"] = "rate_limited"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=credentials_schema(), errors=errors)

    async def async_step_vehicle(self, user_input=None):
        if user_input is not None:
            vehicles = {vehicle_key(v["vin"]): v for v in self._vehicles}
            vehicle = vehicles.get(user_input[CONF_VEHICLE])
            if vehicle is None:
                return self.async_abort(reason="vehicle_not_found")
            await self.async_set_unique_id(vehicle_key(vehicle["vin"]))
            self._abort_if_unique_id_configured()
            safe_vehicle = {k: vehicle[k] for k in ("make", "model", "year") if k in vehicle}
            title = f"{safe_vehicle.get('year', '')} {safe_vehicle.get('model') or 'Outlander PHEV'}".strip()
            return self.async_create_entry(
                title=title,
                data={**self._credentials, CONF_VIN: vehicle["vin"], CONF_VEHICLE: safe_vehicle},
                options={CONF_POLL_MINUTES: DEFAULT_POLL_MINUTES, CONF_GPS: True},
            )
        options = [selector.SelectOptionDict(
            value=vehicle_key(v["vin"]),
            label=f"{v.get('year', '')} {v.get('model') or 'Vehicle'} · VIN ending {v['vin'][-4:]}",
        ) for v in self._vehicles]
        return self.async_show_form(step_id="vehicle", data_schema=vol.Schema({
            vol.Required(CONF_VEHICLE): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            try:
                vehicles = await self._check(user_input)
                if not any(v["vin"] == entry.data[CONF_VIN] for v in vehicles):
                    errors["base"] = "vehicle_not_found"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RateLimitError:
                errors["base"] = "rate_limited"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="reauth_confirm", data_schema=credentials_schema(entry.data[CONF_USERNAME]), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OutlanderOptionsFlow()


class OutlanderOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_POLL_MINUTES, default=options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES)): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            vol.Required(CONF_GPS, default=options.get(CONF_GPS, True)): bool,
        }))
