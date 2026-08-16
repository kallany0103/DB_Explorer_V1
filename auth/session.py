"""Current user/session state for the desktop app."""

from PySide6.QtCore import QObject, Signal

from auth import api_client, oauth, token_store


class AuthSession(QObject):
    """Holds the signed-in user and persists tokens in the OS keyring."""

    state_changed = Signal(bool)  # signed_in

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.user: dict | None = token_store.load_user()
        self.access_token: str | None = token_store.load_access_token()
        self.refresh_token: str | None = token_store.load_refresh_token()
        self.api = api_client.ApiClient()

    @property
    def is_signed_in(self) -> bool:
        return self.user is not None and self.access_token is not None

    @property
    def display_name(self) -> str:
        if not self.user:
            return ""
        return self.user.get("display_name") or self.user.get("email") or ""

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
