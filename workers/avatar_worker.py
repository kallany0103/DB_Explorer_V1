"""Qt worker that fetches the Google profile picture off the main thread.

Refreshes the user profile from the backend first (so the picture URL field is
picked up), then downloads the image bytes.
"""

from PySide6.QtCore import QThread, Signal


class AvatarRefreshWorker(QThread):
    fetched = Signal(bytes)

    def __init__(self, auth_session, parent=None):
        super().__init__(parent)
        self._session = auth_session

    def run(self):
        session = self._session
        session._refresh_profile()
        url = session._resolve_avatar_url()
        data = b""
        if url:
            try:
                data = session.api.fetch_avatar(url)
            except Exception:
                data = b""
        self.fetched.emit(data)
