"""Local loopback HTTP server that receives the post-login token redirect.

The backend redirects the browser to http://127.0.0.1:<port>/callback with
the app session tokens in the query string; this server captures them.
"""

import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer


class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self) -> None:  # noqa: N802 (http naming)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            self.__class__.result = {
                "access_token": params.get("access_token", [""])[0],
                "refresh_token": params.get("refresh_token", [""])[0],
                "error": params.get("error", [""])[0],
            }
            body = (
                b"<html><body style='font-family:sans-serif;text-align:center;"
                b"padding:80px;'><h2>Signed in! You can close this window.</h2></body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # noqa: D102
        pass


class LoopbackServer:
    """One-shot loopback server: starts, waits for a single callback, then closes.

    Uses an OS-assigned ephemeral port (0) so the port is always available and
    cannot collide with earlier abandoned login attempts.
    """

    def __init__(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        self.server.timeout = 0.25
        self.port = self.server.server_address[1]
        self.callback_url = f"http://127.0.0.1:{self.port}/callback"

    def wait(self, timeout: int = 120, cancel_event=None) -> dict | None:
        _CallbackHandler.result = {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                break
            self.server.handle_request()
            if _CallbackHandler.result:
                break
        self.server.server_close()
        result = dict(_CallbackHandler.result)
        _CallbackHandler.result = {}
        return result or None
