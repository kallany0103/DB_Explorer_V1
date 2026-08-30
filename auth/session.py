"""Current user/session state for the desktop app."""

from PySide6.QtCore import QObject, Signal

from auth import api_client, oauth, token_store
from workers.avatar_worker import AvatarRefreshWorker


class AuthSession(QObject):
    """Holds the signed-in user and persists tokens in the OS keyring."""

    state_changed = Signal(bool)  # signed_in

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.user: dict | None = token_store.load_user()
        self.access_token: str | None = token_store.load_access_token()
        self.refresh_token: str | None = token_store.load_refresh_token()
        self._avatar_bytes: bytes | None = token_store.load_avatar()
        self._avatar_thread: AvatarRefreshWorker | None = None
        self.api = api_client.ApiClient()

    @property
    def is_signed_in(self) -> bool:
        return self.user is not None and self.access_token is not None

    @property
    def display_name(self) -> str:
        if not self.user:
            return ""
        return self.user.get("display_name") or self.user.get("email") or ""

    @property
    def avatar(self) -> bytes | None:
        return self._avatar_bytes

    def _avatar_url(self) -> str | None:
        user = self.user or {}
        for key in ("avatar_url", "picture", "avatar", "photo", "image", "profile_pic", "profile_image"):
            value = user.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _resolve_avatar_url(self) -> str | None:
        """Prefer the backend's picture URL; fall back to Google userinfo."""
        url = self._avatar_url()
        if url:
            return url
        if self.access_token:
            try:
                return self.api.userinfo_picture(self.access_token)
            except Exception:
                pass
        return None

    def _fetch_avatar(self) -> bytes | None:
        url = self._resolve_avatar_url()
        if not url:
            return None
        try:
            return self.api.fetch_avatar(url)
        except Exception:
            return None

    def _refresh_profile(self) -> None:
        """Re-fetch the user profile so a picture URL is picked up if present."""
        if not self.access_token:
            return
        token = self.access_token
        try:
            user = self.api.get_me(token)
        except Exception:
            user = None
        if user is None and self.refresh_token:
            try:
                refreshed = self.api.refresh(self.refresh_token)
                new_token = refreshed.get("access_token")
                if new_token:
                    self.access_token = new_token
                    token_store.save_tokens(self.access_token, self.refresh_token)
                    user = self.api.get_me(new_token)
            except Exception:
                user = None
        if user:
            self.user = user
            token_store.save_user(user)

    def refresh_avatar(self) -> None:
        """Fetch the Google profile picture in the background if none is cached."""
        if not self.is_signed_in or self._avatar_bytes:
            return
        if self._avatar_thread is not None and self._avatar_thread.isRunning():
            return
        self._avatar_thread = AvatarRefreshWorker(self)
        self._avatar_thread.fetched.connect(self._on_avatar_fetched)
        self._avatar_thread.start()

    def _on_avatar_fetched(self, data: bytes) -> None:
        self._avatar_bytes = data or None
        token_store.save_avatar(self._avatar_bytes)
        self.state_changed.emit(self.is_signed_in)

    def sign_in_google(self, cancel_event=None) -> bool:
        """Run the full Google flow. Returns True on success."""
        tokens = oauth.start_google_login(cancel_event=cancel_event)
        if tokens and tokens.get("error"):
            raise RuntimeError(tokens["error"])
        if not tokens or not tokens.get("access_token"):
            return False
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens["refresh_token"]
        token_store.save_tokens(self.access_token, self.refresh_token)
        try:
            self.user = self.api.get_me(self.access_token)
        except Exception:
            self.user = {
                "id": "",
                "email": "Signed in",
                "display_name": None,
                "avatar_url": None,
            }
        token_store.save_user(self.user)
        self._avatar_bytes = self._fetch_avatar()
        token_store.save_avatar(self._avatar_bytes)
        self.state_changed.emit(True)
        return True

    def sign_out(self) -> None:
        if self.refresh_token:
            self.api.logout(self.refresh_token)
        self.access_token = None
        self.refresh_token = None
        self.user = None
        token_store.clear()
        self.state_changed.emit(False)
