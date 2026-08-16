"""Account menu used by the custom title bar."""

from collections.abc import Callable

import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget, QWidgetAction


class ActionWidget(QWidget):
    def __init__(self, icon_name: str, icon_color: str, text: str, callback: Callable[[], None], menu: QMenu):
        super().__init__(menu)
        self.menu = menu
        self.callback = callback
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("ActionWidget { background-color: transparent; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)  # The reduced gap!
        
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(QSize(16, 16)))
        layout.addWidget(icon_lbl)
        
        text_lbl = QLabel(text)
        text_lbl.setStyleSheet("font-size: 9pt; color: #333333; background: transparent;")
        layout.addWidget(text_lbl)
        
        layout.addStretch()
        
    def enterEvent(self, event):
        self.setStyleSheet("ActionWidget { background-color: #e8e8e8; }")
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.setStyleSheet("ActionWidget { background-color: transparent; }")
        super().leaveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.menu.close()
            self.callback()
        super().mouseReleaseEvent(event)


class AccountMenu(QMenu):
    """Compact account panel for the signed-out and signed-in states."""

    def __init__(
        self,
        parent: QWidget,
        signed_in: bool,
        display_name: str,
        email: str,
        on_google: Callable[[], None],
        on_email: Callable[[], None],
        on_sign_out: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("accountMenu")
        self.setMinimumWidth(280)

        header = QWidget(self)
        header.setObjectName("accountMenuHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 13, 16, 13)
        header_layout.setSpacing(6)

        avatar = QLabel()
        avatar.setObjectName("accountMenuAvatar")
        avatar.setFixedSize(24, 24)
        avatar.setPixmap(
            qta.icon("mdi.account-circle-outline", color="#5F6368").pixmap(QSize(24, 24))
        )
        header_layout.addWidget(avatar)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title = QLabel(display_name if signed_in else "Not signed in")
        title.setObjectName("accountMenuTitle")
        text_layout.addWidget(title)
        if signed_in:
            subtitle = QLabel(email)
            subtitle.setObjectName("accountMenuSubtitle")
            text_layout.addWidget(subtitle)
        header_layout.addLayout(text_layout)

        header_action = QWidgetAction(self)
        header_action.setDefaultWidget(header)
        self.addAction(header_action)
        self.addSeparator()

        if signed_in:
            sign_out_widget = ActionWidget("mdi.logout", "#555555", "Sign out", on_sign_out, self)
            sign_out_action = QWidgetAction(self)
            sign_out_action.setDefaultWidget(sign_out_widget)
            self.addAction(sign_out_action)
        else:
            google_widget = ActionWidget("fa5b.google", "#4285F4", "Sign in with Google", on_google, self)
            google_action = QWidgetAction(self)
            google_action.setDefaultWidget(google_widget)
            self.addAction(google_action)
            
            email_widget = ActionWidget("mdi.email-outline", "#555555", "Sign in with email", on_email, self)
            email_action = QWidgetAction(self)
            email_action.setDefaultWidget(email_widget)
            self.addAction(email_action)
