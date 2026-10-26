"""Read-only cloud client. No vehicle command endpoints are implemented."""
from __future__ import annotations

import asyncio
import json
import re
import time
from urllib.parse import quote, urlsplit, urlencode, parse_qs
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp

from ._auth import AuthHeaders
from .const import HOST

VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


class CloudError(Exception):
    """A sanitized cloud error, without response bodies or credentials."""


class AuthenticationError(CloudError):
    """Account credentials must be re-entered."""


class RateLimitError(CloudError):
    def __init__(self, retry_after: int = 900):
        self.retry_after = retry_after
        super().__init__(f"Cloud rate limit; retry in {retry_after} seconds")


def allowed_request(method: str, url: str) -> bool:
    """Enforce the same status-only boundary as the validated desktop probe."""
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.hostname != HOST or p.username or p.password or p.fragment:
            return False
        if method.upper() == "POST":
            return p.path == "/auth/v1/token" and not p.query and p.port in (None, 443)
        return method.upper() == "GET" and (
            (re.fullmatch(r"/user/v1/users/[^/]+/vehicles", p.path) and not p.query and p.port in (None, 443))
            or (re.fullmatch(r"/avi/v1/vehicles/[A-HJ-NPR-Z0-9]{17}/vehiclestate", p.path) and not p.query and p.port in (None, 443))
            or (re.fullmatch(r"/avi/v1/vehicles/[A-HJ-NPR-Z0-9]{17}/vehicleStatus", p.path) and p.query == "count=1" and p.port == 15443)
            or (re.fullmatch(r"/api/v1/services/metrics/mileage/[A-HJ-NPR-Z0-9]{17}", p.path) and p.port == 15443 and valid_mileage_query(p.query))
        )
    except ValueError:
        return False


def valid_mileage_query(query: str) -> bool:
    """Only the app's monthly read, with one value for each expected parameter."""
    try:
        params = parse_qs(query, strict_parsing=True, keep_blank_values=True)
        if set(params) != {"year", "month", "timezone"} or any(len(v) != 1 for v in params.values()):
            return False
        year, month = params["year"][0], params["month"][0]
        if not re.fullmatch(r"20\d{2}", year) or not re.fullmatch(r"[1-9]|1[0-2]", month):
            return False
        ZoneInfo(params["timezone"][0])
        return True
    except (ValueError, ZoneInfoNotFoundError):
        return False


class CloudClient(AuthHeaders):
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self.session = session
        self.username = username.strip()
        self.password = password
        self._region = "US"  # North America includes Canada.
        self._token = {}
        self._expires_at = 0.0
        self._backoff_until = 0.0
        self._auth_lock = asyncio.Lock()

    async def _send(self, method: str, url: str, headers: dict, data=None):
        if not allowed_request(method, url):
            raise CloudError("Request outside the read-only endpoint allowlist")
        if method.upper() == "POST" and (
            not isinstance(data, dict) or data.get("grant_type") not in ("password", "refresh_token")
        ):
            raise CloudError("Unexpected authentication request")
        remaining = self._backoff_until - time.monotonic()
        if remaining > 0:
            raise RateLimitError(max(1, int(remaining) + 1))
        try:
            async with self.session.request(
                method, url, headers=headers, json=data,
                timeout=aiohttp.ClientTimeout(total=30), allow_redirects=False,
            ) as response:
                if response.status == 429:
                    try:
                        retry = int(response.headers.get("Retry-After", "900"))
                    except (ValueError, TypeError):
                        retry = 900
                    retry = max(60, min(retry, 86400))
                    self._backoff_until = time.monotonic() + retry
                    raise RateLimitError(retry)
                if response.status == 401:
                    raise AuthenticationError("Cloud authentication was rejected")
                if response.status >= 300:
                    raise CloudError(f"Cloud returned HTTP {response.status}")
                payload = await response.json(content_type=None)
                if not isinstance(payload, dict):
                    raise CloudError("Unexpected cloud response format")
                return payload
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError, UnicodeError):
            raise CloudError("Cloud network, TLS, timeout, or response-format error") from None

    async def _grant(self, data: dict):
        headers = self._get_headers()
        self._add_basic_auth_header(headers)
        payload = await self._send("POST", f"https://{HOST}/auth/v1/token", headers, data)
        account = payload.get("accountDN", self._token.get("accountDN"))
        access = payload.get("access_token")
        if not isinstance(account, str) or not account or not isinstance(access, str) or not access:
            raise CloudError("Incomplete authentication response")
        try:
            lifetime = max(0, int(payload.get("expires_in", 900)))
        except (ValueError, TypeError):
            raise CloudError("Invalid token expiry") from None
        self._token = {**self._token, **payload, "accountDN": account}
        self._expires_at = time.monotonic() + max(0, lifetime - 60)

    async def _authenticate(self, force: bool = False):
        async with self._auth_lock:
            if not force and self._token and time.monotonic() < self._expires_at:
                return
            refresh = self._token.get("refresh_token")
            if refresh:
                try:
                    await self._grant({"grant_type": "refresh_token", "refresh_token": refresh})
                    return
                except AuthenticationError:
                    self._token = {}
            await self._grant({"grant_type": "password", "username": self.username, "password": self.password})

    async def _get(self, url: str):
        await self._authenticate()
        for attempt in range(2):
            headers = self._get_headers()
            headers["authorization"] = f"Bearer {self._token['access_token']}"
            try:
                return await self._send("GET", url, headers)
            except AuthenticationError:
                if attempt:
                    raise
                await self._authenticate(force=True)
        raise AuthenticationError("Cloud authentication was rejected")

    async def async_vehicles(self) -> list[dict]:
        await self._authenticate()
        account = quote(self._token["accountDN"], safe="")
        payload = await self._get(f"https://{HOST}/user/v1/users/{account}/vehicles")
        vehicles = payload.get("vehicles")
        if not isinstance(vehicles, list):
            raise CloudError("Unexpected vehicle-list response")
        return [v for v in vehicles if isinstance(v, dict) and VIN_RE.fullmatch(str(v.get("vin", "")))]

    async def async_state(self, vin: str) -> dict:
        if not VIN_RE.fullmatch(vin):
            raise CloudError("Invalid configured vehicle identifier")
        data = await self._get(f"https://{HOST}/avi/v1/vehicles/{vin}/vehiclestate")
        if not isinstance(data.get("state"), dict):
            raise CloudError("Vehicle-state response is missing state data")
        return data

    async def async_health(self, vin: str) -> dict:
        if not VIN_RE.fullmatch(vin):
            raise CloudError("Invalid configured vehicle identifier")
        data = await self._get(f"https://{HOST}:15443/avi/v1/vehicles/{vin}/vehicleStatus?count=1")
        if not isinstance(data.get("vhr"), list):
            raise CloudError("Unexpected vehicle-health response")
        return data

    async def async_mileage(self, vin: str, year: int, month: int, timezone_name: str) -> dict:
        if not VIN_RE.fullmatch(vin):
            raise CloudError("Invalid configured vehicle identifier")
        query = urlencode({"year": str(year), "month": str(month), "timezone": timezone_name})
        if not valid_mileage_query(query):
            raise CloudError("Invalid mileage-report period or time zone")
        data = await self._get(f"https://{HOST}:15443/api/v1/services/metrics/mileage/{vin}?{query}")
        if data.get("status") != "Success" or data.get("periodType") != "Monthly" or not isinstance(data.get("data"), list):
            raise CloudError("Unexpected mileage-history response")
        return data

    def clear(self):
        self._token.clear()
        self.password = ""
        self.username = ""
