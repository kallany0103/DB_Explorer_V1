# widgets/connection_manager/context_menus/_helpers.py
"""Shared helper functions for all context menu builders."""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu
import qtawesome as qta

from widgets.connection_manager.menu_style import apply_menu_style


def action(parent, label, icon_key=None, shortcut=None, enabled=True):
    """Create a QAction with optional icon and shortcut hint text."""
    act = QAction(label, parent)
    if icon_key:
        try:
            act.setIcon(qta.icon(icon_key, color="#4b5563"))
        except Exception:
            pass
    if shortcut:
        act.setShortcutVisibleInContextMenu(True)
        try:
            act.setShortcut(QKeySequence(shortcut))
        except Exception:
            pass
    act.setEnabled(enabled)
    return act


def stub(*_):
    """No-op placeholder for unimplemented menu items."""
    return lambda: None


def add_properties_statistics_actions(menu, manager, item_data, obj_name):
    """Add Properties/Statistics items that open or refresh inspector workbench tabs."""
    act = action(manager, "Properties...", "mdi.tune", shortcut="Alt+Shift+E")
    act.triggered.connect(
        lambda _checked=False, data=item_data, name=obj_name: manager.open_properties_workbench(data, name)
    )
    menu.addAction(act)

    act = action(manager, "Statistics...", "mdi.chart-bar", shortcut="Alt+Shift+S")
    act.triggered.connect(
        lambda _checked=False, data=item_data, name=obj_name: manager.open_statistics_workbench(data, name)
    )
    menu.addAction(act)


def submenu(parent_menu, label, icon_key=None):
    """Create and attach a styled sub-menu, returning it."""
    sub = QMenu(label, parent_menu)
    apply_menu_style(sub)
    if icon_key:
        try:
            sub.setIcon(qta.icon(icon_key, color="#4b5563"))
        except Exception:
            pass
    parent_menu.addMenu(sub)
    return sub
