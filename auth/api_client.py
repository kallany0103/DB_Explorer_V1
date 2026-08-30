"""Minimal HTTP client for the Universal SQL Client API."""

import re

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
            "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        return resp.json()

    def userinfo_picture(self, access_token: str) -> str | None:
        """Read the profile picture straight from Google using the access token."""
        resp = self._client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("picture")

    def fetch_avatar(self, url: str) -> bytes:
        resp = self._client.get(self._upsize_google_avatar(url))
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _upsize_google_avatar(url: str) -> str:
        """Request a larger Google profile image for a sharp render."""
        if "googleusercontent.com" in url:
            return re.sub(r"=s\d+(-c)?", "=s256-c", url)
        return url

    def refresh(self, refresh_token: str) -> dict:
        resp = self._client.post(
            "/auth/refresh", params={"refresh_token": refresh_token}
        )
        resp.raise_for_status()
        return resp.json()

    def logout(self, refresh_token: str) -> None:
        try:
            self._client.post(
                "/auth/logout", params={"refresh_token": refresh_token}
            )
        except httpx.HTTPError:
            pass
