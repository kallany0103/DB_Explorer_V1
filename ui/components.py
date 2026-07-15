from PySide6.QtWidgets import QPushButton, QLineEdit
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt
from typing import Optional
import os

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
        
        # Add search icon
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        icon_path = os.path.join(assets_dir, "search.svg")
        if os.path.exists(icon_path):
            self.addAction(QIcon(icon_path), QLineEdit.ActionPosition.LeadingPosition)
            

class PasswordBox(QLineEdit):
    """
    A standard password input field that manages its own visibility toggle (eye icon).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        self._eye_icon = QIcon(os.path.join(assets_dir, "eye.svg"))
        self._eye_off_icon = QIcon(os.path.join(assets_dir, "eye-off.svg"))
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
    """
    def __init__(self, default_text, icon=None, parent=None):
        super().__init__(default_text, icon, parent)
        self.itemTriggered.connect(self.setText)
        
    def currentText(self):
        return self.text()
        
    def setCurrentText(self, text):
        self.setText(text)


