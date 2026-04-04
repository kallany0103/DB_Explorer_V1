from PySide6.QtWidgets import (
    QMessageBox,
    QToolButton,
)
from PySide6.QtCore import QEvent


def renumber_tabs(manager):
    worksheet_number = 1
    for i in range(manager.tab_widget.count()):
        current_text = manager.tab_widget.tabText(i)
        if current_text.startswith("Worksheet ") or current_text == "New Tab":
            manager.tab_widget.setTabText(i, f"Worksheet {worksheet_number}")
            manager.tab_widget.setTabIcon(i, manager._get_worksheet_tab_icon())
            worksheet_number += 1


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
    QMessageBox.information(parent, "Information", text)
