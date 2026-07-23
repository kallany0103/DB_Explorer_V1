from PySide6.QtWidgets import QPushButton, QLineEdit
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt
from typing import Optional
import os
import qtawesome as qta

class SecondaryButton(QPushButton):
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
        """)


class PrimaryButton(QPushButton):
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
        """)


class IconButton(SecondaryButton):
    """
    An icon-only button or a button where the icon is the primary visual element.
    Inherits from SecondaryButton but adjusts padding for a squarer look.
    """
    def __init__(self, icon: QIcon, tooltip: str = "", parent=None):
        super().__init__(icon, "", parent)
        if tooltip:
            self.setToolTip(tooltip)
        
        # Override style to make it more suitable for icons
        self.setStyleSheet("""
            QPushButton {
                min-height: 26px;
                min-width: 26px;
                padding: 4px;
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
        """)


class SearchBox(QLineEdit):
    """
    A standard search input field with a leading magnifying glass icon.
    """
    def __init__(self, placeholder: str = "Search...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        
        # Add search icon using qtawesome to ensure proper scaling
        search_icon = qta.icon("fa5s.search", color="#8B929B", scale_factor=0.8)
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
        
        self._eye_icon = qta.icon("fa5s.eye", color="#8B929B", scale_factor=0.7)
        self._eye_off_icon = qta.icon("fa5s.eye-slash", color="#8B929B", scale_factor=0.7)
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

from PySide6.QtWidgets import QToolButton, QMenu
from PySide6.QtCore import Signal

class ActionToolButton(QToolButton):
    """
    A ToolButton that acts as a dropdown menu, styled consistently 
    with the application's secondary buttons. Used for 'Edit', 'Explain', etc.
    """
    itemTriggered = Signal(str)

    def __init__(self, text, icon=None, parent=None):
        super().__init__(parent)
        self.setText(text)
        if icon:
            self.setIcon(icon)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFixedHeight(30)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
                padding: 4px 12px;
                font-size: 9pt;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
                border-color: #9c9c9c;
            }
            QToolButton:pressed {
                background-color: #dcdcdc;
            }
            QToolButton::menu-indicator {
                subcontrol-position: right center;
                subcontrol-origin: padding;
                left: -4px;
            }
        """)
        
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
        self.itemTriggered.connect(self.setCurrentText)
        
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
            }
            QPushButton:hover {
                background-color: #ECEFF3;
            }
            QPushButton:checked {
                background-color: #8E959E;
                color: #ffffff;
                border-bottom: 1px solid #8E959E;
                font-weight: bold;
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
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setFixedHeight(30)
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid #b9b9b9;
                border-radius: 4px;
                background-color: #ffffff;
                color: #333333;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QToolButton:hover {
                background-color: #e8e8e8;
                border-color: #9c9c9c;
            }
            QToolButton:pressed {
                background-color: #dcdcdc;
            }
        """)


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





