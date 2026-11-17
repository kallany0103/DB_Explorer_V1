# widgets/connection_manager/context_menus/scrollable_menu.py
"""Scrollable context menu container for handling long action lists on small screens.

Embeds a QScrollArea inside a QWidgetAction so context menus with many actions
stay compact, fully visible, and smoothly scrollable with mouse wheel or scrollbar.
"""

from typing import Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)


class ScrollableMenuRow(QFrame):
    """A single interactive row inside a scrollable context menu."""

    def __init__(
        self,
        action: QAction,
        parent_menu: QMenu,
        scroll_area: QScrollArea,
    ) -> None:
        super().__init__()
        self.action = action
        self.parent_menu = parent_menu
        self.scroll_area = scroll_area
        self.submenu: Optional[QMenu] = action.menu()
        self.is_danger: bool = any(
            word in action.text().lower() for word in ("drop", "truncate", "delete")
        )

        self.setFixedHeight(28)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if action.isEnabled()
            else Qt.CursorShape.ArrowCursor
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        # Action icon
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(16, 16)
        icon = action.icon()
        if not icon.isNull():
            self.icon_lbl.setPixmap(icon.pixmap(16, 16))
        layout.addWidget(self.icon_lbl)

        # Action title
        self.text_lbl = QLabel(action.text())
        text_color = "#1F2937" if action.isEnabled() else "#9CA3AF"
        self.text_lbl.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
        layout.addWidget(self.text_lbl, 1)

        # Shortcut or Submenu arrow
        shortcut_text = action.shortcut().toString()
        if shortcut_text:
            sc_lbl = QLabel(shortcut_text)
            sc_lbl.setStyleSheet("color: #6B7280; font-size: 8.5pt;")
            layout.addWidget(sc_lbl)
        elif self.submenu:
            chevron_lbl = QLabel("›")
            chevron_lbl.setStyleSheet("color: #6B7280; font-size: 11pt; font-weight: bold;")
            layout.addWidget(chevron_lbl)

        self._apply_idle_style()

    def _apply_idle_style(self) -> None:
        self.setStyleSheet("ScrollableMenuRow { background: transparent; border-radius: 5px; }")

    def enterEvent(self, event) -> None:
        if not self.action.isEnabled():
            return super().enterEvent(event)
        bg = "#FEE2E2" if self.is_danger else "#EEF4FA"
        fg = "#DC2626" if self.is_danger else "#1E293B"
        self.setStyleSheet(f"ScrollableMenuRow {{ background-color: {bg}; border-radius: 5px; }}")
        self.text_lbl.setStyleSheet(f"color: {fg}; font-size: 9pt;")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_idle_style()
        text_color = "#1F2937" if self.action.isEnabled() else "#9CA3AF"
        self.text_lbl.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.action.isEnabled():
            if self.submenu:
                pos = self.mapToGlobal(QPoint(self.width() - 4, 0))
                selected = self.submenu.exec(pos)
                if selected:
                    self.parent_menu.close()
            else:
                self.parent_menu.close()
                self.action.trigger()
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.scroll_area:
            QApplication.sendEvent(self.scroll_area.viewport(), event)
        else:
            super().wheelEvent(event)


class ScrollableMenuSeparator(QFrame):
    """A 1px styled separator inside the scrollable context menu."""

    def __init__(self, scroll_area: QScrollArea) -> None:
        super().__init__()
        self.scroll_area = scroll_area
        self.setFixedHeight(1)
        self.setStyleSheet("background-color: #E2E8F0; margin: 3px 6px;")

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.scroll_area:
            QApplication.sendEvent(self.scroll_area.viewport(), event)
        else:
            super().wheelEvent(event)


def create_scrollable_action_widget(
    parent_menu: QMenu,
    actions: list[Optional[QAction]],
    max_height: int = 250,
    min_width: int = 260,
) -> QWidgetAction:
    """Create a QWidgetAction containing a scrollable container of actions."""
    scroll = QScrollArea(parent_menu)
    scroll.setWidgetResizable(True)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    scroll.setMinimumWidth(min_width)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("""
        QScrollArea {
            border: none;
            background: transparent;
        }
        QScrollBar:vertical {
            border: none;
            background: transparent;
            width: 6px;
            margin: 2px 2px 2px 0px;
        }
        QScrollBar::handle:vertical {
            background: #CBD5E1;
            min-height: 24px;
            border-radius: 3px;
        }
        QScrollBar::handle:vertical:hover {
            background: #94A3B8;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)

    for act in actions:
        if act is None or act.isSeparator():
            layout.addWidget(ScrollableMenuSeparator(scroll))
        else:
            layout.addWidget(ScrollableMenuRow(act, parent_menu, scroll))

    scroll.setWidget(container)

    # Dynamic height calculation capped at max_height
    calculated_height = len(actions) * 29 + 6
    target_height = min(max_height, calculated_height)
    scroll.setFixedHeight(target_height)

    widget_action = QWidgetAction(parent_menu)
    widget_action.setDefaultWidget(scroll)
    # Store inner actions list for introspection and testing
    widget_action.inner_actions = actions  # type: ignore[attr-defined]
    return widget_action
