from PySide6.QtWidgets import (
    QApplication, QAbstractScrollArea, QCheckBox, QComboBox,
    QPushButton, QLineEdit, QToolButton, QMenu,
    QTableView, QHeaderView, QAbstractItemView, QWidget, QHBoxLayout, QLabel,
    QDialog, QVBoxLayout, QProgressBar, QStyle, QStyledItemDelegate, QSizePolicy
)
from PySide6.QtGui import (
    QIcon, QAction, QActionGroup, QPainter, QColor, QPainterPath, QFont, QPixmap, QPen, QGuiApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRectF, QSize, QEvent
from typing import Optional
import qtawesome as qta
import qtawesome.iconic_font
from ui.menu_style import apply_menu_style
from ui.icons import get_icon, AppIcons

# Guard against Qt console spam when qtawesome is queried with uninitialized/zero size
_orig_char_icon_pixmap = qtawesome.iconic_font.CharIconEngine.pixmap


def _safe_char_icon_pixmap(self, size, mode, state):
    if size.width() <= 0 or size.height() <= 0:
        return QPixmap()
    return _orig_char_icon_pixmap(self, size, mode, state)


qtawesome.iconic_font.CharIconEngine.pixmap = _safe_char_icon_pixmap

# Prevent QComboBox from cycling options on mouse wheel scroll when scrolling forms
_orig_qcombobox_wheel_event = QComboBox.wheelEvent


def _safe_combobox_wheel_event(self, event):
    event.ignore()
    parent = self.parentWidget()
    while parent:
        if isinstance(parent, QAbstractScrollArea):
            QApplication.sendEvent(parent.viewport(), event)
            break
        parent = parent.parentWidget()


QComboBox.wheelEvent = _safe_combobox_wheel_event


class LoadingOverlay(QWidget):

    def __init__(self, parent=None, label: str = ""):
        super().__init__(parent)
        self._label_text = label
        if parent:
            parent.installEventFilter(self)

        # Make the widget cover the entire parent and block mouse events behind it
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()

        h_layout = QHBoxLayout()
        h_layout.addStretch()

        self.loading_icon = QToolButton(self)
        self.loading_icon.setIcon(
            qta.icon(
                "ph.spinner-fill",
                color="#3b82f6",
                animation=qta.Spin(self.loading_icon)
            )
        )
        self.loading_icon.setIconSize(QSize(64, 64))
        self.loading_icon.setStyleSheet("border: none; background: transparent;")
        h_layout.addWidget(self.loading_icon)
        h_layout.addStretch()

        layout.addLayout(h_layout)

        self._label = None
        if self._label_text:
            self._label = QLabel(self._label_text, self)
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._label.setStyleSheet(
                "color: #64748b; font-size: 13px; font-weight: 500; margin-top: 12px;"
            )
            layout.addWidget(self._label)

        layout.addStretch()

        self.hide()

    def set_label(self, text: str) -> None:
        """Update or set the text label displayed beneath the spinner."""
        self._label_text = text
        if self._label is None and text:
            layout = self.layout()
            self._label = QLabel(text, self)
            self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._label.setStyleSheet(
                "color: #64748b; font-size: 13px; font-weight: 500; margin-top: 12px;"
            )
            layout.insertWidget(layout.count() - 1, self._label)
        elif self._label is not None:
            self._label.setText(text)

    def show_overlay(self):
        """Show the overlay and center it over parent."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()

    def hide_overlay(self):
        """Stop and hide the overlay."""
        self.hide()

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(self.parent().rect())
            if self.isVisible():
                self.raise_()
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        # Clean semi-transparent background consistent with properties & statistics view
        painter.fillRect(self.rect(), QColor(248, 250, 252, 215))
        painter.end()



class LoadingButton:

    def start_loading(self, text=None):
        self._original_text = self.text()
        self._original_icon = self.icon()

        if text is None:
            text = "Testing" if self._original_text else ""

        # Lock width during loading so button never jumps or shifts position in layout
        self._had_fixed_width = (self.minimumWidth() == self.maximumWidth() and self.minimumWidth() > 0)
        self._orig_min_width = self.minimumWidth()
        self._orig_max_width = self.maximumWidth()
        if not self._had_fixed_width:
            current_w = max(self.width(), self.sizeHint().width())
            self.setFixedWidth(current_w)

        self._loading_base_text = text
        self.setText(text)
        self.setProperty("loading", True)
        self._progress_value = 0.0
        self._dot_tick = 0
        self.setEnabled(False)
        if text or self._original_text:
            self.setIcon(QIcon())
        self.style().unpolish(self)
        self.style().polish(self)

        # ── Progress bar overlay ──────────────────────────────────────
        bar_h = 3
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(bar_h)
        self._progress_bar.setGeometry(2, max(0, self.height() - bar_h - 2), max(1, self.width() - 4), bar_h)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: transparent;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0284c7,
                    stop:0.5 #38bdf8,
                    stop:1 #0284c7
                );
                border-radius: 1px;
            }
        """)
        self._progress_bar.show()
        self._progress_bar.raise_()

        # ── Progress tick timer (30 ms) ───────────────────────────────
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(30)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_timer.start()

    # ── Progress animation ────────────────────────────────────────────
    def _tick_progress(self):
        v = self._progress_value
        if v < 70:
            v += 1.4          # fast start
        elif v < 85:
            v += 0.35         # medium
        elif v < 93:
            v += 0.08         # slow
        else:
            v += 0.015        # creep — never reaches 100 on its own
        self._progress_value = min(v, 99.0)
        pb = getattr(self, '_progress_bar', None)
        if pb:
            bar_h = 3
            pb.setGeometry(2, max(0, self.height() - bar_h - 2), max(1, self.width() - 4), bar_h)
            pb.setValue(int(self._progress_value))

        self._dot_tick = getattr(self, '_dot_tick', 0) + 1
        dots = "." * ((self._dot_tick // 10) % 4)
        base = getattr(self, '_loading_base_text', '').rstrip('.')
        if base:
            self.setText(f"{base}{dots}")

    # ── Stop ──────────────────────────────────────────────────────────
    def stop_loading(self):
        # Stop progress timer
        t = getattr(self, '_progress_timer', None)
        if t:
            t.stop()
            t.deleteLater()
            self._progress_timer = None

        # Flash bar to 100%, then remove after brief pause
        pb = getattr(self, '_progress_bar', None)
        if pb:
            pb.setValue(100)
            QTimer.singleShot(220, self._remove_progress_bar)

        self.setProperty("loading", False)
        self.setEnabled(True)
        self.setText(getattr(self, '_original_text', self.text()))
        self.setIcon(getattr(self, '_original_icon', QIcon()))
        self.style().unpolish(self)
        self.style().polish(self)

        # Restore original width constraint if button wasn't explicitly fixed-width
        if not getattr(self, '_had_fixed_width', False):
            self.setMinimumWidth(getattr(self, '_orig_min_width', 0))
            self.setMaximumWidth(getattr(self, '_orig_max_width', 16777215))

    def _remove_progress_bar(self):
        pb = getattr(self, '_progress_bar', None)
        if pb:
            pb.hide()
            pb.deleteLater()
            self._progress_bar = None


class SecondaryButton(QPushButton, LoadingButton):
    """
    A standard/secondary button used across the application.
    Features a white background with a light border and hover effects.
    """
    def __init__(self, text_or_icon, text: Optional[str] = None, parent=None):
        if isinstance(text_or_icon, QIcon):
            super().__init__(text_or_icon, text if text else "", parent)
        else:
            super().__init__(text_or_icon, parent)
            
        self.setStyleSheet("""
            QPushButton {
                min-height: 26px;
                padding: 4px 12px;
                border: 1px solid #c4c9d4;
                border-radius: 4px;
                background-color: #ffffff;
                color: #1f2937;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #f4f7fb;
                border-color: #b8c2cf;
            }
            QPushButton:pressed {
                background-color: #e9eef5;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QPushButton[loading="true"],
            QPushButton[loading="true"]:disabled {
                background-color: #f0f7ff;
                color: #0284c7;
                border-color: #93c5fd;
            }
        """)


class CompactButton(SecondaryButton):
    """
    A compact secondary button suited for header bars and toolbars (26-28px height).
    Features smaller padding and font size to fit neatly within 32-36px headers without clipping.
    """
    def __init__(self, text_or_icon, text: Optional[str] = None, parent=None):
        super().__init__(text_or_icon, text, parent)
        self.setStyleSheet("""
            QPushButton {
                min-height: 20px;
                max-height: 24px;
                padding: 2px 8px;
                border: 1px solid #c4c9d4;
                border-radius: 4px;
                background-color: #ffffff;
                color: #1f2937;
                font-size: 8.5pt;
            }
            QPushButton:hover {
                background-color: #f4f7fb;
                border-color: #b8c2cf;
            }
            QPushButton:pressed {
                background-color: #e9eef5;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QPushButton[loading="true"],
            QPushButton[loading="true"]:disabled {
                background-color: #f0f7ff;
                color: #0284c7;
                border-color: #93c5fd;
            }
        """)


class PrimaryButton(QPushButton, LoadingButton):
    """
    A primary action button, typically blue, used for main actions like 'Save', 'Execute', etc.
    """
    def __init__(self, text_or_icon, text: Optional[str] = None, parent=None):
        if isinstance(text_or_icon, QIcon):
            super().__init__(text_or_icon, text if text else "", parent)
        else:
            super().__init__(text_or_icon, parent)
            
        self.setStyleSheet("""
            QPushButton {
                min-height: 26px;
                padding: 4px 12px;
                border: 1px solid #006cbe;
                border-radius: 4px;
                background-color: #0078d4;
                color: #ffffff;
                font-weight: 600;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #006cbe;
                border-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QPushButton[loading="true"],
            QPushButton[loading="true"]:disabled {
                background-color: #f0f7ff;
                color: #0284c7;
                border-color: #93c5fd;
            }
        """)


class PrimaryIconButton(PrimaryButton):
    """
    A primary (blue) icon-only button with a squarer look.
    Uses spinning msc.loading animation during loading instead of a progress bar overlay.
    """
    def __init__(self, icon: QIcon, tooltip: str = "", parent=None):
        super().__init__(icon, "", parent)
        self._initial_icon = icon
        if tooltip:
            self.setToolTip(tooltip)

        self.setStyleSheet("""
            QPushButton {
                min-height: 22px;
                min-width: 22px;
                padding: 2px;
                border: 1px solid #006cbe;
                border-radius: 4px;
                background-color: #0078d4;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #006cbe;
                border-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QPushButton[loading="true"],
            QPushButton[loading="true"]:disabled {
                background-color: #0284c7;
                border-color: #0369a1;
            }
        """)

    def start_loading(self, text=None):
        self._orig_icon = self.icon()
        self._orig_tooltip = self.toolTip()
        self.setProperty("loading", True)
        self.setEnabled(False)
        self.setIcon(qta.icon('msc.loading', color='white', animation=qta.Spin(self)))
        self.style().unpolish(self)
        self.style().polish(self)

    def stop_loading(self):
        self.setProperty("loading", False)
        self.setEnabled(True)
        if hasattr(self, '_orig_icon') and self._orig_icon:
            self.setIcon(self._orig_icon)
        elif hasattr(self, '_initial_icon') and self._initial_icon:
            self.setIcon(self._initial_icon)
        if hasattr(self, '_orig_tooltip') and self._orig_tooltip:
            self.setToolTip(self._orig_tooltip)
        self.style().unpolish(self)
        self.style().polish(self)


class IconButton(SecondaryButton):
    """
    An icon-only button or a button where the icon is the primary visual element.
    Inherits from SecondaryButton but adjusts padding for a squarer look.
    Uses spinning msc.loading animation during loading instead of a progress bar overlay.
    """
    def __init__(self, icon: QIcon, tooltip: str = "", parent=None):
        super().__init__(icon, "", parent)
        self._initial_icon = icon
        if tooltip:
            self.setToolTip(tooltip)
        
        # Override style to make it more suitable for icons
        self.setStyleSheet("""
            QPushButton {
                min-height: 22px;
                min-width: 22px;
                padding: 2px;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                background-color: #f9fafb;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
            }
            QPushButton:pressed {
                background-color: #e5e7eb;
            }
            QPushButton[loading="true"],
            QPushButton[loading="true"]:disabled {
                background-color: #f0f7ff;
                border-color: #93c5fd;
            }
        """)

    def start_loading(self, text=None):
        self._orig_icon = self.icon()
        self._orig_tooltip = self.toolTip()
        self.setProperty("loading", True)
        self.setEnabled(False)
        self.setIcon(qta.icon('msc.loading', color='#0284c7', animation=qta.Spin(self)))
        self.style().unpolish(self)
        self.style().polish(self)

    def stop_loading(self):
        self.setProperty("loading", False)
        self.setEnabled(True)
        if hasattr(self, '_orig_icon') and self._orig_icon:
            self.setIcon(self._orig_icon)
        elif hasattr(self, '_initial_icon') and self._initial_icon:
            self.setIcon(self._initial_icon)
        if hasattr(self, '_orig_tooltip') and self._orig_tooltip:
            self.setToolTip(self._orig_tooltip)
        self.style().unpolish(self)
        self.style().polish(self)


class SearchBox(QLineEdit):
    """
    A standard search input field with a leading magnifying glass icon.
    """
    def __init__(self, placeholder: str = "Search...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        
        # Add search icon using qtawesome to ensure proper scaling
        search_icon = get_icon(AppIcons.SEARCH, color="#8B929B", scale_factor=0.8)
        self.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        
        # Add padding to left so text doesn't hit icon
        self.setStyleSheet("""
            QLineEdit {
                padding-left: 2px;
                border: 1px solid #c4c9d4;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
        """)
            

class PasswordBox(QLineEdit):
    """
    A standard password input field that manages its own visibility toggle (eye icon).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        
        self._eye_icon = get_icon("msc.eye", color="#8B929B", scale_factor=0.7)
        self._eye_off_icon = get_icon("msc.eye-closed", color="#8B929B", scale_factor=0.7)
        self._password_visible = False
        
        self._password_action = self.addAction(
            self._eye_icon,
            QLineEdit.ActionPosition.TrailingPosition
        )
        self._password_action.triggered.connect(self._toggle_visibility)
        

        
    def _toggle_visibility(self):
        self._password_visible = not self._password_visible
        self.setEchoMode(
            QLineEdit.EchoMode.Normal if self._password_visible else QLineEdit.EchoMode.Password
        )
        self._password_action.setIcon(self._eye_off_icon if self._password_visible else self._eye_icon)


class ActionToolButton(QToolButton):
    """
    A ToolButton that acts as a dropdown menu, styled consistently 
    with the application's secondary buttons. Used for 'Edit', 'Explain', etc.
    """
    itemTriggered = Signal(str)

    def __init__(self, text, icon=None, parent=None):
        super().__init__(parent)
        self._menu = QMenu(self)
        apply_menu_style(self._menu)
        self.setMenu(self._menu)
        self.setFixedHeight(28)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.clicked.connect(self.showMenu)
        if text:
            super().setText(text)
        if icon:
            self.setIcon(icon)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._update_style()

    def _update_style(self):
        is_icon_only = self.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly or not self.text()
        pad_left = 0 if is_icon_only else 8
        pad_right = 16 if is_icon_only else 24
        self.setStyleSheet(f"""
            QToolButton {{
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
                padding: 0px {pad_right}px 0px {pad_left}px;
                font-size: 9pt;
            }}
            QToolButton:hover {{
                background-color: #e8e8e8;
                border-color: #9c9c9c;
            }}
            QToolButton:pressed {{
                background-color: #dcdcdc;
            }}
            QToolButton::menu-button {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border: none;
            }}
            QToolButton::menu-button:hover, QToolButton::menu-button:open {{
                background-color: #dcdcdc;
                border-radius: 3px;
            }}
            QToolButton::menu-arrow {{
                image: url(assets/toolbar-chevron-down.svg);
                width: 10px;
                height: 10px;
                subcontrol-position: center center;
            }}
        """)

    def setToolButtonStyle(self, style):
        super().setToolButtonStyle(style)
        self._update_style()

    def setText(self, text):
        super().setText(text)
        self._update_style()
        
    def addItems(self, items):
        for item in items:
            self.addItem(item)
            
    def addItem(self, text, icon=None, data=None):
        action = QAction(text, self)
        if icon:
            action.setIcon(icon)
        if data:
            action.setData(data)
        
        action.triggered.connect(lambda checked=False, t=text: self._on_action_triggered(t))
        self._menu.addAction(action)
        return action
        
    def _on_action_triggered(self, text):
        self.itemTriggered.emit(text)

    def getMenu(self):
        return self._menu


class DropdownToolButton(ActionToolButton):
    """
    A ToolButton that acts like a QComboBox, updating its display text
    when an item is selected from its dropdown menu.
    Supports an optional prefix that is displayed but not part of the underlying value.
    """
    def __init__(self, default_text, icon=None, prefix="", parent=None):
        super().__init__(default_text, icon, parent)
        self._prefix = prefix
        self._action_group = QActionGroup(self)
        self._action_group.setExclusive(True)
        self.itemTriggered.connect(self.setCurrentText)

    def addItem(self, text, icon=None, data=None):
        action = super().addItem(text, icon=icon, data=data)
        action.setCheckable(True)
        self._action_group.addAction(action)
        if text == self.currentText():
            action.setChecked(True)
        return action

    def currentText(self):
        text = self.text()
        if self._prefix and text.startswith(self._prefix):
            return text[len(self._prefix):]
        return text

    def setCurrentText(self, text):
        if self._prefix and not text.startswith(self._prefix):
            self.setText(f"{self._prefix}{text}")
        else:
            self.setText(text)
        target = self.currentText()
        for action in self._menu.actions():
            if action.text() == target:
                action.setChecked(True)
                break


class NavigationTabButton(QPushButton):
    """
    A checkable button used in navigation headers (e.g., Query, Output, Messages).
    Typically placed inside a QButtonGroup to act like tabs.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #B8BEC6;
                padding: 5px 15px;
                min-width: 80px;
                font-size: 9pt;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ECEFF3;
            }
            QPushButton:checked {
                background-color: #E2E8F0;
                color: #1F2937;
                border: 1px solid #B8BEC6;
                border-bottom: 2px solid #60A5FA;
                padding: 5px 15px 4px 15px;
                font-weight: 500;
            }
        """)


class ToolbarActionButton(QToolButton):
    """
    A standard tool button for main toolbars (e.g., Open, Save, Execute).
    Uses icon + text underneath or beside.
    """
    def __init__(self, text=None, icon=None, parent=None):
        super().__init__(parent)
        if text:
            self.setText(text)
        if icon:
            self.setIcon(icon)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setFixedSize(32, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._update_style()

    def setPopupMode(self, mode):
        super().setPopupMode(mode)
        self._update_style()

    def _update_style(self):
        pad_right = 16 if self.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup else 0
        self.setStyleSheet(f"""
            QToolButton {{
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
                padding: 0px {pad_right}px 0px 0px;
                font-size: 9pt;
            }}
            QToolButton:hover, QToolButton[hovered="true"] {{
                background-color: #e8e8e8;
                border-color: #9c9c9c;
            }}
            QToolButton:pressed {{
                background-color: #dcdcdc;
            }}
            QToolButton::menu-button {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border: none;
            }}
            QToolButton::menu-button:hover, QToolButton::menu-button:open {{
                background-color: #dcdcdc;
                border-radius: 3px;
            }}
            QToolButton::menu-arrow {{
                image: url(assets/toolbar-chevron-down.svg);
                width: 10px;
                height: 10px;
                subcontrol-position: center center;
            }}
        """)

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


class DangerButton(QPushButton):
    """
    A button for destructive actions like Delete, Drop, Remove.
    Features a red aesthetic.
    """
    def __init__(self, text_or_icon, text=None, parent=None):
        if isinstance(text_or_icon, QIcon):
            super().__init__(text_or_icon, text if text else "", parent)
        else:
            super().__init__(text_or_icon, parent)
            
        self.setStyleSheet("""
            QPushButton {
                min-height: 26px;
                padding: 4px 12px;
                border: 1px solid #dc2626;
                border-radius: 4px;
                background-color: #ef4444;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
            QPushButton:pressed {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #fca5a5;
                border-color: #fca5a5;
            }
        """)


class LinkButton(QPushButton):
    """
    A flat button that looks like a hyperlink.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #006cbe;
                text-align: left;
            }
            QPushButton:hover {
                text-decoration: underline;
                color: #005a9e;
            }
            QPushButton:pressed {
                color: #004578;
            }
        """)


class PropertyTable(QTableView):
    """
    A read-only table view styled for property sheets and statistics tabs.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propertyTable")
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.horizontalHeader().setHighlightSections(False)
        self.verticalHeader().setDefaultSectionSize(28)

# ── Toast Notification ────────────────────────────────────────────────────────

_TOAST_STYLES = {
    "success": {
        "bg":         "#ECEFF3",
        "border":     "#B8BEC6",
        "icon":       "msc.check",
        "icon_color": "#16a34a",
    },
    "error": {
        "bg":         "#ECEFF3",
        "border":     "#B8BEC6",
        "icon":       "msc.error",
        "icon_color": "#dc2626",
    },
    "info": {
        "bg":         "#ECEFF3",
        "border":     "#B8BEC6",
        "icon":       "msc.info",
        "icon_color": "#2563eb",
    },
    "warning": {
        "bg":         "#ECEFF3",
        "border":     "#B8BEC6",
        "icon":       "msc.warning",
        "icon_color": "#d97706",
    },
}

_TOAST_MARGIN   = 18    # px from window edge
_TOAST_DURATION = 3000  # ms before auto-dismiss


class ToastNotification(QWidget):
    _active_toasts: list["ToastNotification"] = []

    def __init__(self, parent: QWidget, message: str,
                 kind: str = "success", duration: int = _TOAST_DURATION):
        top = parent.window() if parent else parent
        super().__init__(top, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        ToastNotification._active_toasts.append(self)

        style = _TOAST_STYLES.get(kind, _TOAST_STYLES["info"])
        self._bg     = style["bg"]
        self._border = style["border"]
        effective_duration = 5000 if (kind == "error" and duration == _TOAST_DURATION) else duration

        # Constrain width so toast never stretches indefinitely or overflows the parent window
        parent_w = top.width() if top else 600
        max_toast_w = min(480, max(280, parent_w - (2 * _TOAST_MARGIN)))
        self.setMaximumWidth(max_toast_w)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setPixmap(get_icon(style["icon"], color=style["icon_color"]).pixmap(16, 16))
        icon_lbl.setFixedWidth(20)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI Variable", 10))
        msg_lbl.setStyleSheet("color: #1f2937; background: transparent; line-height: 1.3;")
        msg_lbl.setWordWrap(True)
        msg_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        msg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
                padding: 0;
                margin: 0;
            }
            QPushButton:hover {
                color: #1e293b;
                background: #e2e8f0;
                border-radius: 9px;
            }
        """)
        close_btn.clicked.connect(self.close)

        layout.addWidget(icon_lbl)
        layout.addWidget(msg_lbl, 1)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.adjustSize()
        if self.width() < 260:
            self.setMinimumWidth(260)

        self._reposition()

        # Follow parent moves/resizes
        if top:
            top.installEventFilter(self)

        # Slide-in animation within bottom margin
        anim_offset = max(6, _TOAST_MARGIN - 6)
        self._anim_in = QPropertyAnimation(self, b"pos", self)
        self._anim_in.setDuration(240)
        self._anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim_in.setStartValue(QPoint(self.x(), self.y() + anim_offset))
        self._anim_in.setEndValue(self.pos())

        # Auto-dismiss
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(effective_duration)
        self._timer.timeout.connect(self._slide_out)

        self.show()
        self._anim_in.start()
        self._timer.start()

    def eventFilter(self, obj, event):
        if obj == self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._reposition()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
        parent = self.parent()
        if parent:
            try:
                parent.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def _reposition(self):
        parent = self.parent()
        if not parent:
            return

        tl = parent.mapToGlobal(parent.rect().topLeft())
        parent_x = tl.x()
        parent_y = tl.y()
        parent_w = parent.width()
        parent_h = parent.height()

        target_x = parent_x + parent_w - self.width() - _TOAST_MARGIN
        target_y = parent_y + parent_h - self.height() - _TOAST_MARGIN

        # Strictly clamp within parent window bounds
        min_x = parent_x + _TOAST_MARGIN
        max_x = max(min_x, parent_x + parent_w - self.width() - _TOAST_MARGIN)
        min_y = parent_y + _TOAST_MARGIN
        max_y = max(min_y, parent_y + parent_h - self.height() - _TOAST_MARGIN)

        clamped_x = max(min_x, min(target_x, max_x))
        clamped_y = max(min_y, min(target_y, max_y))

        # Strictly clamp within screen boundaries as well
        screen = parent.screen() or QGuiApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            clamped_x = max(
                screen_geo.left() + _TOAST_MARGIN,
                min(clamped_x, screen_geo.right() - self.width() - _TOAST_MARGIN),
            )
            clamped_y = max(
                screen_geo.top() + _TOAST_MARGIN,
                min(clamped_y, screen_geo.bottom() - self.height() - _TOAST_MARGIN),
            )

        self.move(int(clamped_x), int(clamped_y))

    def _slide_out(self):
        anim_offset = max(6, _TOAST_MARGIN - 6)
        self._anim_out = QPropertyAnimation(self, b"pos", self)
        self._anim_out.setDuration(200)
        self._anim_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim_out.setEndValue(QPoint(self.x(), self.y() + anim_offset))
        self._anim_out.finished.connect(self.close)
        self._anim_out.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.fillPath(path, QColor(self._bg))
        painter.setPen(QPen(QColor(self._border), 1))
        painter.drawPath(path)

    @classmethod
    def show_toast(cls, parent: QWidget, message: str,
                   kind: str = "success", duration: int = _TOAST_DURATION):
        """Create and show a toast. Returns the widget instance."""
        return cls(parent, message, kind=kind, duration=duration)

    @classmethod
    def dismiss_all(cls):
        """Dismiss all currently active toast notifications immediately."""
        for toast in list(cls._active_toasts):
            try:
                toast.close()
            except Exception:
                pass
        cls._active_toasts.clear()


# ── Confirmation Dialog ───────────────────────────────────────────────────────

class ConfirmDialog(QDialog):
    """
    A modern, sleek confirmation dialog matching the application design system.
    Replaces standard OS QMessageBox with themed styling, icon badges, and action buttons.
    """

    def __init__(
        self,
        title: str = "Confirm Action",
        message: str = "Are you sure you want to proceed?",
        confirm_text: str = "Delete",
        cancel_text: str = "Cancel",
        kind: str = "danger",
        parent: Optional[QWidget] = None,
    ):
        top = parent.window() if parent else None
        super().__init__(top)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(20)

        # Content row: Icon badge + Text
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Badge styling based on kind
        if kind == "danger":
            icon_name = "msc.trash"
            icon_color = "#dc2626"
            bg_color = "#fee2e2"
            border_color = "#fecaca"
        elif kind == "warning":
            icon_name = "msc.warning"
            icon_color = "#d97706"
            bg_color = "#fef3c7"
            border_color = "#fde68a"
        else:
            icon_name = "msc.question"
            icon_color = "#2563eb"
            bg_color = "#eff6ff"
            border_color = "#bfdbfe"

        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 20px;
            }}
        """)
        icon_label.setPixmap(get_icon(icon_name, color=icon_color).pixmap(18, 18))
        content_layout.addWidget(icon_label)

        # Text column (Title + Message)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI Variable", 11, QFont.Weight.DemiBold))
        title_lbl.setStyleSheet("color: #111827; background: transparent;")
        text_layout.addWidget(title_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 9))
        msg_lbl.setStyleSheet("color: #4b5563; background: transparent; line-height: 1.4;")
        msg_lbl.setWordWrap(True)
        text_layout.addWidget(msg_lbl)

        content_layout.addLayout(text_layout)
        layout.addLayout(content_layout)

        # Button row: Cancel + Confirm (Delete/Action)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self._cancel_btn = SecondaryButton(cancel_text)
        self._cancel_btn.setMinimumWidth(80)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        if kind == "danger":
            self._confirm_btn = DangerButton(confirm_text)
        else:
            self._confirm_btn = PrimaryButton(confirm_text)
        self._confirm_btn.setMinimumWidth(80)
        self._confirm_btn.setDefault(True)
        self._confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._confirm_btn)

        layout.addLayout(btn_layout)

    @classmethod
    def confirm(
        cls,
        parent: Optional[QWidget] = None,
        title: str = "Confirm Action",
        message: str = "Are you sure you want to proceed?",
        confirm_text: str = "Delete",
        cancel_text: str = "Cancel",
        kind: str = "danger",
    ) -> bool:
        """Helper to show the dialog modally and return True if accepted."""
        dlg = cls(
            title=title,
            message=message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            kind=kind,
            parent=parent,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted


class ToggleSwitch(QCheckBox):
    """Compact pill toggle switch compatible with standard QCheckBox APIs."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 22)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        checked = self.isChecked()
        hovered = self.underMouse()

        if not self.isEnabled():
            track_color = QColor("#E2E8F0")
        elif checked:
            track_color = QColor("#0369A1" if hovered else "#0284C7")
        else:
            track_color = QColor("#94A3B8" if hovered else "#CBD5E1")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)

        thumb_d = rect.height() - 4.0
        thumb_y = rect.y() + 2.0
        thumb_x = (rect.right() - thumb_d - 2.0) if checked else (rect.x() + 2.0)

        painter.setPen(QPen(QColor(0, 0, 0, 20), 0.75))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, thumb_d, thumb_d))
        painter.end()


class SettingsCategoryDelegate(QStyledItemDelegate):
    """Paints modern sidebar category items with clean pill selection and matching icon tint."""

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), 34))

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(option.rect).adjusted(2.0, 1.0, -2.0, -1.0)
        pill_path = QPainterPath()
        pill_path.addRoundedRect(rect, 6.0, 6.0)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#E0F2FE"))
            painter.drawPath(pill_path)
        elif is_hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F1F5F9"))
            painter.drawPath(pill_path)

        icon_name = index.data(Qt.ItemDataRole.UserRole + 1)
        if is_selected and icon_name:
            icon = get_icon(icon_name, color="#0284C7")
        else:
            icon = index.data(Qt.ItemDataRole.DecorationRole)

        text_left = rect.left() + 10.0
        if isinstance(icon, QIcon) and not icon.isNull():
            icon_rect = QRectF(rect.left() + 10.0, rect.center().y() - 8.0, 16.0, 16.0).toRect()
            icon.paint(painter, icon_rect)
            text_left = rect.left() + 34.0

        font = QFont(option.font)
        font.setPointSizeF(9.5)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor("#0369A1" if is_selected else "#334155"))

        is_modified = bool(index.data(Qt.ItemDataRole.UserRole))
        right_pad = 20.0 if is_modified else 8.0
        text_rect = QRectF(text_left, rect.top(), rect.right() - text_left - right_pad, rect.height())
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
        )

        if is_modified:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#0284C7"))
            dot_d = 6.0
            painter.drawEllipse(QRectF(rect.right() - 14.0, rect.center().y() - dot_d / 2.0, dot_d, dot_d))
        painter.restore()
