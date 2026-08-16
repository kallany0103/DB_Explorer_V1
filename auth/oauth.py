"""Starts the backend-mediated Google login: opens the system browser, then
waits for the loopback token redirect."""

import uuid
import webbrowser
from urllib.parse import quote

from auth import config, loopback


def start_google_login(cancel_event=None) -> dict | None:
    """Return {'access_token', 'refresh_token'} or None if the user cancels/times out."""
    device_id = str(uuid.uuid4())
    server = loopback.LoopbackServer()
    url = (
        f"{config.API_BASE_URL}/api/v1/auth/google"
        f"?device_id={device_id}&callback={quote(server.callback_url, safe='')}"
    )
    webbrowser.open(url)
    return server.wait(cancel_event=cancel_event)
