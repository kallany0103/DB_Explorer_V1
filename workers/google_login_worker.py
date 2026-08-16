"""Qt worker for the blocking browser-based Google sign-in flow."""

from threading import Event

from PySide6.QtCore import QThread, Signal


class GoogleSignInWorker(QThread):
    completed = Signal(bool, str)

    def __init__(self, auth_session, parent=None):
        super().__init__(parent)
        self.auth_session = auth_session
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self):
        try:
            success = self.auth_session.sign_in_google(self.cancel_event)
        except Exception as exc:
            self.completed.emit(False, str(exc))
        else:
            message = "" if success else "Google sign-in was cancelled."
            self.completed.emit(success, message)
