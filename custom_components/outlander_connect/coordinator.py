"""One state poll shared by all entities; slower optional health reads."""
from datetime import datetime, timedelta, timezone
import logging
import time

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CloudClient, CloudError, AuthenticationError, RateLimitError
from .const import CONF_VIN, CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES, DOMAIN, HEALTH_INTERVAL_SECONDS
from .data import parse_snapshot

LOGGER = logging.getLogger(__name__)


class OutlanderCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client: CloudClient):
        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN,
            update_interval=timedelta(minutes=entry.options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES)),
        )
        self.client = client
        self.entry = entry
        self.vin = entry.data[CONF_VIN]
        self.health = {}
        self.health_ok = False
        self._next_health = 0.0

    async def _async_update_data(self):
        try:
            state = await self.client.async_state(self.vin)
            if time.monotonic() >= self._next_health:
                # Set before requesting so a failing optional endpoint is not hammered.
                self._next_health = time.monotonic() + HEALTH_INTERVAL_SECONDS
                try:
                    self.health = await self.client.async_health(self.vin)
                    self.health_ok = True
                except AuthenticationError:
                    raise
                except RateLimitError:
                    self.health_ok = False
                    # Retain the successful state read. The API client enforces backoff.
                except CloudError:
                    self.health_ok = False
                    LOGGER.debug("Optional vehicle-health read failed; state sensors remain available")
            return parse_snapshot(state, self.health, polled_at=datetime.now(timezone.utc), health_ok=self.health_ok)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Mitsubishi Connect sign-in is required") from err
        except RateLimitError as err:
            raise UpdateFailed("Mitsubishi Connect rate limit", retry_after=err.retry_after) from err
        except CloudError as err:
            raise UpdateFailed(str(err)) from err

    async def async_refresh_all(self):
        self._next_health = 0.0
        await self.async_request_refresh()
