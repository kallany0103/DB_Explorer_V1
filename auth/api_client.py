"""Minimal HTTP client for the Universal SQL Client API."""

import httpx

from auth import config


class ApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or config.API_BASE_URL
        self._client = httpx.Client(base_url=self.base_url, timeout=30)

    def close(self) -> None:
        self._client.close()

    def get_me(self, access_token: str) -> dict:
        resp = self._client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()

    def refresh(self, refresh_token: str) -> dict:
        resp = self._client.post(
            "/api/v1/auth/refresh", data={"refresh_token": refresh_token}
        )
        resp.raise_for_status()
        return resp.json()

    def logout(self, refresh_token: str) -> None:
        try:
            self._client.post(
                "/api/v1/auth/logout", data={"refresh_token": refresh_token}
            )
        except httpx.HTTPError:
            pass
