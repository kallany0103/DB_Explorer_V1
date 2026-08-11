# ui/title_bar.py
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
import qtawesome as qta


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

        self._btn_user = QPushButton()
        self._btn_user.setObjectName("titleBarBtnUser")
        self._btn_user.setIcon(qta.icon("mdi.account-circle-outline", color="#555555"))
        self._btn_user.setIconSize(QSize(20, 20))
        self._btn_user.setFixedSize(btn_size)
        self._btn_user.setToolTip("Sign in")
        self._btn_user.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_user.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
            if self._window.isMaximized() or self._window.isFullScreen():
                self._window.showNormal()
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
        # Frameless windows (custom title bar) enter WindowFullScreen on
        # maximize, so check both states to keep the icon in sync.
        is_maximized = self._window.isMaximized() or self._window.isFullScreen()
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

    def _show_account_menu(self) -> None:
        """Open account sign-in choices from the user control."""
        self._window.show_login_menu(self._btn_user)
