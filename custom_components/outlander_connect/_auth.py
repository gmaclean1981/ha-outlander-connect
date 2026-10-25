"""Authentication headers adapted from pcartwright81/mitsubishi_connect_client, MIT, commit 80a3a114586976e7b6542980b0fdc44514b6d30d. See LICENSE-UPSTREAM."""

class AuthHeaders:

    def _add_basic_auth_header(self, headers: dict[str, str]) -> None:
        """Add the basic auth header."""
        headers['authorization'] = 'Basic ZTU4NjUzY2QtMzkxOS00MjYxLWE1N2UtNWYyZjdjMjAwMGRhOmFtcENsaWVudFRydXN0ZWRTZWNyZXQ='

    def _get_headers(self) -> dict[str, str]:
        """Get the headers."""
        if self._region == 'EU':
            host = 'eu-m.aerpf.com:15443'
        else:
            host = 'us-m.aerpf.com:15443'
        return {'content-type': 'application/json; charset=UTF-8', 'user-agent': 'Mobile', 'x-client-id': 'mobile', 'ampapikey': '3f5547161b5d4bdbbb2bf8b26c69d1de', 'host': host, 'connection': 'Keep-Alive', 'accept-encoding': 'gzip'}
