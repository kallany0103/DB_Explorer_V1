# ui/title_bar.py
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QSize, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
import qtawesome as qta

_AVATAR_SIZE = 20
_RENDER_DPR = 2
_TITLE_BAR_HEIGHT = 30


class UserControl(QWidget):
    """Compact avatar + chevron control shown in the title bar."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBarBtnUser")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedHeight(_TITLE_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(3)

        self._avatar_lbl = QLabel()
        self._avatar_lbl.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
        self._avatar_lbl.setScaledContents(True)
        self._avatar_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._avatar_lbl)

        self._chevron_lbl = QLabel()
        self._chevron_lbl.setFixedSize(12, 12)
        self._chevron_lbl.setScaledContents(True)
        self._chevron_lbl.setPixmap(_chevron_icon_pixmap(12))
        self._chevron_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._chevron_lbl)

    def set_user_state(self, auth_session) -> None:
        """Show the Google photo, or a letter avatar, plus the chevron."""
        if auth_session.is_signed_in:
            name = auth_session.display_name or "User"
            initial = (name.split()[0][:1] if name.split() else "?").upper()
            photo = _rounded_avatar_pixmap(auth_session.avatar, _AVATAR_SIZE)
            pixmap = photo if photo is not None else _letter_avatar_pixmap(initial, _AVATAR_SIZE)
            self.setToolTip(f"Signed in as {name}")
        else:
            pixmap = qta.icon("mdi.account-circle-outline", color="#555555").pixmap(
                _AVATAR_SIZE * _RENDER_DPR, _AVATAR_SIZE * _RENDER_DPR
            )
            self.setToolTip("Sign in")
        self._avatar_lbl.setPixmap(pixmap)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class TitleBarWidget(QWidget):
    """Custom VS Code-style compact title bar.

    Contains (left to right):
      - App icon (16×16)
      - The window's QMenuBar
      - Stretch spacer (draggable region)
      - User / Settings / Min / Max / Close buttons
    """

    _TITLE_BAR_HEIGHT = 30  # px — matches VS Code compact title bar

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(parent_window)
        self._window = parent_window
        self._drag_pos: QPoint | None = None

        # Keep window controls minimal and consistent with the app's icon style.
        self._icon_minimize = qta.icon("msc.chrome-minimize", color="#333333")
        self._icon_maximize = qta.icon("msc.chrome-maximize", color="#333333")
        self._icon_restore = qta.icon("msc.chrome-restore", color="#333333")
        self._icon_close = qta.icon("msc.close", color="#333333")

        self.setObjectName("titleBar")
        self.setFixedHeight(self._TITLE_BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(0)

        # --- App icon ---
        self._icon_label = QLabel()
        self._icon_label.setObjectName("titleBarIcon")
        self._icon_label.setFixedSize(20, 20)
        self._icon_label.setScaledContents(True)
        self._icon_label.setPixmap(QIcon("assets/sql_icon.svg").pixmap(QSize(16, 16)))
        self._icon_label.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(4)

        # --- Placeholder for menu bar (inserted later) ---
        self._menu_placeholder = QWidget()
        self._menu_placeholder.setObjectName("menuBarHolder")
        self._menu_placeholder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._menu_placeholder)

        # --- Draggable stretch ---
        spacer = QWidget()
        spacer.setObjectName("titleBarSpacer")
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(spacer)

        # --- Account and application controls ---
        btn_size = QSize(self._TITLE_BAR_HEIGHT + 16, self._TITLE_BAR_HEIGHT)

        self._btn_settings = QPushButton()
        self._btn_settings.setObjectName("titleBarBtnSettings")
        self._btn_settings.setIcon(qta.icon("mdi.cog-outline", color="#555555"))
        self._btn_settings.setIconSize(QSize(20, 20))
        self._btn_settings.setFixedSize(btn_size)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_settings.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_settings.clicked.connect(self._window.show_preferences)
        layout.addWidget(self._btn_settings)

        self._btn_user = UserControl(self)
        self._btn_user.clicked.connect(self._show_account_menu)
        layout.addWidget(self._btn_user)

        self._btn_min = QPushButton()
        self._btn_min.setObjectName("titleBarBtnMin")
        self._btn_min.setIcon(self._icon_minimize)
        self._btn_min.setIconSize(QSize(16, 16))
        self._btn_min.setFixedSize(btn_size)
        self._btn_min.setToolTip("Minimize")
        self._btn_min.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_min.clicked.connect(self._window.showMinimized)
        layout.addWidget(self._btn_min)

        self._btn_max = QPushButton()
        self._btn_max.setObjectName("titleBarBtnMax")
        self._btn_max.setIcon(self._icon_maximize)
        self._btn_max.setIconSize(QSize(16, 16))
        self._btn_max.setFixedSize(btn_size)
        self._btn_max.setToolTip("Maximize")
        self._btn_max.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_max.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        self._btn_close = QPushButton()
        self._btn_close.setObjectName("titleBarBtnClose")
        self._btn_close.setIcon(self._icon_close)
        self._btn_close.setIconSize(QSize(16, 16))
        self._btn_close.setFixedSize(btn_size)
        self._btn_close.setToolTip("Close")
        self._btn_close.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_close.clicked.connect(self._window.close)
        layout.addWidget(self._btn_close)

    # Public helpers

    def embed_menu_bar(self, menu_bar) -> None:
        """Re-parent the existing QMenuBar into the title bar layout."""
        menu_bar.setParent(self)
        menu_bar.setFixedHeight(self._TITLE_BAR_HEIGHT)
        menu_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = self.layout()
        idx = layout.indexOf(self._menu_placeholder)
        layout.removeWidget(self._menu_placeholder)
        self._menu_placeholder.deleteLater()
        layout.insertWidget(idx, menu_bar, 0, Qt.AlignmentFlag.AlignVCenter)

    # Window drag support

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if getattr(self._window, "_is_maximized", False):
                self._window.toggle_maximize()
                self.update_maximize_button()
                # Recalculate offset after restore to avoid sudden jump
                self._drag_pos = QPoint(self._window.width() // 2, self._TITLE_BAR_HEIGHT // 2)
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()

    # Internal helpers


    def update_maximize_button(self) -> None:
        """Sync maximize button icon and menu action icon with window state."""
        # Use _is_maximized flag as the source of truth; the window is frameless
        # so Qt's isMaximized() / isFullScreen() are not reliable here.
        is_maximized = getattr(self._window, "_is_maximized", False)
        if is_maximized:
            self._btn_max.setIcon(self._icon_restore)
            self._btn_max.setToolTip("Restore")
            if hasattr(self._window, "maximize_action"):
                self._window.maximize_action.setIcon(self._icon_restore)
        else:
            self._btn_max.setIcon(self._icon_maximize)
            self._btn_max.setToolTip("Maximize")
            if hasattr(self._window, "maximize_action"):
                self._window.maximize_action.setIcon(self._icon_maximize)

    def _toggle_maximize(self) -> None:
        """Toggle between maximized and normal state via main_window logic."""
        self._window.toggle_maximize()

    def set_user_state(self, auth_session) -> None:
        """Reflect the signed-in state on the user control (avatar + chevron)."""
        self._btn_user.set_user_state(auth_session)

    def _show_account_menu(self) -> None:
        """Open account sign-in choices from the user control."""
        self._window.show_login_menu(self._btn_user)


def _rounded_avatar_pixmap(data: bytes | None, size: int = 20) -> QPixmap | None:
    """Build a circular-clipped avatar from raw image bytes, or None if unusable."""
    if not data:
        return None
    source = QImage.fromData(data)
    if source.isNull():
        return None
    ph = size * _RENDER_DPR
    source = source.scaled(
        ph,
        ph,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(ph, ph)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, ph, ph))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, QPixmap.fromImage(source))
    painter.end()
    return out


_LETTER_COLORS = ("#4285F4", "#EA4335", "#FBBC05", "#34A853", "#7B1FA2", "#FF6D00")


def _letter_avatar_pixmap(initial: str, size: int = 20) -> QPixmap:
    """Build a circular coloured avatar showing the user's initial."""
    ch = (initial or "?").upper()
    color = _LETTER_COLORS[sum(ord(c) for c in ch) % len(_LETTER_COLORS)]
    ph = size * _RENDER_DPR
    out = QPixmap(ph, ph)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(0, 0, ph, ph)
    font = QFont()
    font.setPixelSize(round(ph * 0.5))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(QRectF(0, 0, ph, ph), Qt.AlignmentFlag.AlignCenter, ch)
    painter.end()
    return out


def _chevron_icon_pixmap(size: int = 12) -> QPixmap:
    """Render the dropdown chevron at 2x; the label scales it down to fit."""
    physical = size * _RENDER_DPR
    return qta.icon("fa5s.chevron-down", color="#555555").pixmap(physical, physical)
