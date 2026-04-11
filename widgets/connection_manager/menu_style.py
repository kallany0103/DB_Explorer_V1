# widgets/connection_manager/menu_style.py
"""Shared pgAdmin-style stylesheet for QMenu context menus."""

CONTEXT_MENU_STYLE = """
QMenu {
    background-color: #ffffff;
    border: 1px solid #c8cdd3;
    border-radius: 0px;
    padding: 3px 0px;
    font-size: 9pt;
    font-family: "Segoe UI", sans-serif;
    color: #1f2937;
}
QMenu::item {
    padding: 5px 32px 5px 22px;
    min-width: 200px;
}
QMenu::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}
QMenu::item:disabled {
    color: #9ca3af;
    background-color: transparent;
}
QMenu::separator {
    height: 1px;
    background-color: #e5e7eb;
    margin: 3px 0px;
}
QMenu::icon {
    padding-left: 6px;
    width: 16px;
    height: 16px;
}
QMenu::right-arrow {
    image: none;
    width: 8px;
    height: 8px;
    padding-right: 4px;
}
"""


def apply_menu_style(menu):
    """Apply the shared pgAdmin-style stylesheet to a QMenu and all its submenus."""
    menu.setStyleSheet(CONTEXT_MENU_STYLE)
