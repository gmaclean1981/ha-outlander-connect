"""One state poll shared by all entities; slower optional health reads."""
from datetime import datetime, timedelta, timezone
import logging
import time

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CloudClient, CloudError, AuthenticationError, RateLimitError
from .const import CONF_VIN, CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES, DOMAIN, HEALTH_INTERVAL_SECONDS
from .data import parse_snapshot
from .mileage import parse_month, parse_year, totals, apply_mileage

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
        self.mileage = {}
        self.mileage_today = None
        self.mileage_timezone = None
        self.yearly_mileage = {}

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
            polled_at = datetime.now(timezone.utc)
            self.mileage_timezone = self.hass.config.time_zone
            self.mileage_today = dt_util.as_local(polled_at).date()
            yesterday = self.mileage_today - timedelta(days=1)
            periods = {(d.year, d.month) for d in (self.mileage_today, yesterday)}
            self.mileage = {key: value for key, value in self.mileage.items() if key in periods and value.get("timezone") == self.mileage_timezone}
            for year, month in sorted(periods, reverse=True):
                report = self.mileage.setdefault((year, month), {"next_fetch": 0, "ok": False, "timezone": self.mileage_timezone})
                if time.monotonic() < report["next_fetch"]:
                    continue
                report["next_fetch"] = time.monotonic() + 900
                try:
                    payload = await self.client.async_mileage(self.vin, year, month, self.mileage_timezone)
                    report.update(records=parse_month(payload, year, month), totals=totals(payload), ok=True, fetched_at=polled_at)
                except AuthenticationError:
                    raise
                except (CloudError, ValueError):
                    report["ok"] = False
                    LOGGER.debug("Optional mileage-history read failed; vehicle-state sensors remain available")
            year_report = self.yearly_mileage
            if year_report.get("year") != self.mileage_today.year or year_report.get("timezone") != self.mileage_timezone:
                year_report = self.yearly_mileage = {"year": self.mileage_today.year, "timezone": self.mileage_timezone, "next_fetch": 0, "ok": False}
            if time.monotonic() >= year_report["next_fetch"]:
                year_report["next_fetch"] = time.monotonic() + 3600
                try:
                    payload = await self.client.async_yearly_mileage(self.vin, self.mileage_today.year, self.mileage_timezone)
                    year_report.update(records=parse_year(payload, self.mileage_today.year), totals=totals(payload), ok=True, fetched_at=polled_at)
                except AuthenticationError:
                    raise
                except (CloudError, ValueError):
                    year_report["ok"] = False
                    LOGGER.debug("Optional yearly mileage read failed; other sensors remain available")
            snapshot = parse_snapshot(state, self.health, polled_at=polled_at, health_ok=self.health_ok)
            return apply_mileage(snapshot, self.mileage, self.mileage_today, year_report)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Mitsubishi Connect sign-in is required") from err
        except RateLimitError as err:
            raise UpdateFailed("Mitsubishi Connect rate limit", retry_after=err.retry_after) from err
        except CloudError as err:
            raise UpdateFailed(str(err)) from err

    async def async_refresh_all(self):
        self._next_health = 0.0
        for report in self.mileage.values():
            report["next_fetch"] = 0.0
        self.yearly_mileage["next_fetch"] = 0.0
        await self.async_request_refresh()
