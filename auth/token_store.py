"""Token/profile persistence in the OS credential store (Windows Credential Manager)."""

import json

import keyring

_SERVICE = "Universal SQL Client"
_KEYS = ("access_token", "refresh_token", "user")


def _get(key: str) -> str | None:
    try:
        return keyring.get_password(_SERVICE, key)
    except Exception:
        return None


def _set(key: str, value: str | None) -> None:
    try:
        if value is None:
            keyring.delete_password(_SERVICE, key)
        else:
            keyring.set_password(_SERVICE, key, value)
    except Exception:
        pass


def save_tokens(access_token: str | None, refresh_token: str | None) -> None:
    _set("access_token", access_token)
    _set("refresh_token", refresh_token)


def save_user(user: dict | None) -> None:
    _set("user", json.dumps(user) if user else None)


def load_access_token() -> str | None:
    return _get("access_token")


def load_refresh_token() -> str | None:
    return _get("refresh_token")


def load_user() -> dict | None:
    raw = _get("user")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def clear() -> None:
    for key in _KEYS:
        _set(key, None)
