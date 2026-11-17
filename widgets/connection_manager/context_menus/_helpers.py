# widgets/connection_manager/context_menus/_helpers.py
"""Shared helper functions for all context menu builders."""

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu
import qtawesome as qta

from ui.feature_flags import is_feature_enabled
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
    """Add Describe/Properties/Statistics items that open or refresh inspector workbench tabs."""
    desc_act = action(manager, "Describe...", "mdi.information-outline", shortcut="F4")
    desc_act.triggered.connect(
        lambda _checked=False, data=item_data, name=obj_name: manager.describe_object(data, name)
    )
    menu.addAction(desc_act)

    quick_desc_act = action(manager, "Quick Describe...", "fa5s.search-plus", shortcut="Ctrl+D")
    quick_desc_act.triggered.connect(
        lambda _checked=False, data=item_data, name=obj_name: manager.quick_describe_object(data, name)
    )
    menu.addAction(quick_desc_act)

    if is_feature_enabled(manager, "object_inspector"):
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


def standalone_menu(parent, label, icon_key=None):
    """Create a styled QMenu without attaching it to parent's action list."""
    sub = QMenu(label, parent)
    apply_menu_style(sub)
    if icon_key:
        try:
            sub.setIcon(qta.icon(icon_key, color="#4b5563"))
        except Exception:
            pass
    return sub


def submenu(parent_menu, label, icon_key=None):
    """Create and attach a styled sub-menu, returning it."""
    sub = standalone_menu(parent_menu, label, icon_key)
    parent_menu.addMenu(sub)
    return sub


def calculate_smart_menu_pos(anchor_global: QPoint, menu_size: QSize) -> QPoint:
    """Calculate the optimal global position for a context menu to prevent screen overflow.

    Follows OS context menu interaction guidelines:
    - Anchors to the click point / cursor position.
    - If opening downward overflows the screen, flips upward from the anchor point.
    - Clamps horizontally and vertically within available screen bounds with a safe margin.
    """
    screen = QApplication.screenAt(anchor_global) or QApplication.primaryScreen()
    if not screen:
        return anchor_global

    avail = screen.availableGeometry()  # Excludes Windows taskbar
    w, h = menu_size.width(), menu_size.height()
    x, y = anchor_global.x(), anchor_global.y()

    # Vertical collision check
    if y + h > avail.bottom() - 6:
        space_above = anchor_global.y() - avail.top()
        space_below = avail.bottom() - anchor_global.y()
        if space_above >= h:
            # Flip completely upwards so bottom of menu aligns with anchor
            y = anchor_global.y() - h
        elif space_above > space_below:
            # Shift upwards so it stays within top of screen
            y = max(avail.top() + 6, anchor_global.y() - h)
        else:
            # Shift up just enough to stay on screen
            y = avail.bottom() - h - 6

    # Clamp vertically within safe margins
    y = max(avail.top() + 6, min(y, avail.bottom() - h - 6))

    # Horizontal collision check
    if x + w > avail.right() - 6:
        x = max(avail.left() + 6, anchor_global.x() - w)
    else:
        x = max(avail.left() + 6, min(x, avail.right() - w - 6))

    return QPoint(x, y)
