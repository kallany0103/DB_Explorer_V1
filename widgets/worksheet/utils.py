from PySide6.QtWidgets import (
    QToolButton,
)
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QTabBar
from ui.components import ToastNotification


def renumber_tabs(manager):
    all_worksheet_indices = []
    worksheet_number = 0
    for i in range(manager.tab_widget.count()):
        widget = manager.tab_widget.widget(i)
        if getattr(widget, 'is_worksheet', False):
            worksheet_number += 1
            all_worksheet_indices.append(i)
            current_text = manager.tab_widget.tabText(i)
            # Only rename auto-named tabs; leave custom (renamed) names alone.
            if current_text.startswith("Worksheet ") or current_text == "New Tab":
                manager.tab_widget.setTabText(i, f"Worksheet {worksheet_number}")
                manager.tab_widget.setTabIcon(i, manager._get_worksheet_tab_icon())

    # Hide the close button when only one worksheet remains so users
    # get a clear visual signal that the last tab cannot be closed.
    tab_bar = manager.tab_widget.tabBar()
    only_one = len(all_worksheet_indices) == 1
    for i in all_worksheet_indices:
        btn = tab_bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
        if btn:
            btn.setVisible(not only_one)


def handle_event_filter(obj, event):
    if obj.objectName() == "table_search_box" and event.type() == QEvent.Type.FocusOut:
        obj.hide()
        parent_tab = obj.parent()
        if parent_tab:
            search_btn = parent_tab.findChild(QToolButton, "table_search_btn")
            if search_btn:
                search_btn.show()
        return True
    return False


def show_info(manager, text, parent=None):
    if parent is None:
        current_tab = manager.tab_widget.currentWidget()
        parent = current_tab if current_tab else manager.main_window
    ToastNotification.show_toast(parent, text, kind="info")
