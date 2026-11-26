# ui/menu_style.py
"""Shared modern Fluent-style stylesheet and helpers for QMenu context menus."""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu
from shiboken6 import isValid

CONTEXT_MENU_STYLE = """
QMenu {
    background-color: #ffffff;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 6px 4px;
    font-size: 9pt;
    font-family: "Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1f2937;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
    min-width: 170px;
    border-radius: 5px;
    margin: 2px 4px;
}
QMenu::item:selected {
    background-color: #EEF4FA;
    color: #1E293B;
    border-radius: 5px;
}
QMenu::item:checked {
    background-color: #EFF6FF;
    color: #0369A1;
    font-weight: 600;
    border-radius: 5px;
}
QMenu::item:checked:selected {
    background-color: #E0F2FE;
    color: #0369A1;
}
QMenu::item:disabled {
    color: #9ca3af;
    background-color: transparent;
}
QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 6px;
}
QMenu::indicator:unchecked {
    image: none;
    background: transparent;
    border: none;
}
QMenu::indicator:checked {
    image: url(assets/menu-check.svg);
}
QMenu::separator {
    height: 1px;
    background-color: #E2E8F0;
    margin: 4px 8px;
}
QMenu::icon {
    padding-left: 4px;
    width: 16px;
    height: 16px;
}
QMenu::right-arrow {
    image: url(assets/chevron-right.svg);
    width: 10px;
    height: 10px;
    margin-right: 6px;
}
"""


DROPDOWN_MENU_STYLE = CONTEXT_MENU_STYLE.replace(
    "padding: 6px 24px 6px 10px;\n    min-width: 170px;",
    "padding: 5px 14px 5px 6px;\n    min-width: 0px;",
)


def apply_win11_rounded_corners(menu: QMenu) -> None:
    """Request modern DWM rounded corners on Windows 11.
    
    NOTE: Calling menu.winId() forces premature native HWND creation for the menu
    and its entire parent widget hierarchy (e.g. WorksheetToolbar), promoting child
    widgets to top-level native QWidgetWindows and breaking Qt layout geometry.
    Modern rounded corners for QMenu are handled via QSS border-radius and WA_TranslucentBackground.
    """
    return


def apply_menu_style(menu: QMenu, compact: bool = False) -> None:
    """Apply the shared modern Fluent-style stylesheet and transparency flags to a QMenu and all submenus."""
    try:
        if not isValid(menu):
            return
    except Exception:
        return

    menu.setWindowFlags(
        menu.windowFlags()
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    menu.setStyleSheet(DROPDOWN_MENU_STYLE if compact else CONTEXT_MENU_STYLE)
    apply_win11_rounded_corners(menu)

    def _on_about_to_show():
        try:
            if not isValid(menu):
                return
            apply_win11_rounded_corners(menu)
            for act in menu.actions():
                sub = act.menu()
                if sub and isValid(sub) and not sub.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground):
                    apply_menu_style(sub, compact=compact)
        except (RuntimeError, Exception):
            pass

    try:
        menu.aboutToShow.connect(_on_about_to_show)
    except (RuntimeError, Exception):
        pass
