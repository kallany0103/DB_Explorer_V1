import datetime

from PyQt6.QtWidgets import (
    QApplication,
    QMessageBox,
    QComboBox,
    QTreeView,
    QTextEdit,
    QStackedWidget,
    QPlainTextEdit,
    QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QBrush, QColor

import db


def save_query_to_history(manager, conn_data, query, status, rows, duration):
    conn_id = conn_data.get("id") if conn_data else None
    if not conn_id:
        return
    try:
        db.save_query_history(conn_id, query, status, rows, duration)
    except Exception as error:
        manager.status.showMessage(f"Could not save query to history: {error}", 4000)


def load_connection_history(manager, target_tab):
    history_list_view = target_tab.findChild(QTreeView, "history_list_view")
    history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
    db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")

    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Connection History"])
    history_list_view.setModel(model)
    history_details_view.clear()
    history_list_view.expandAll()
    history_list_view.setUniformRowHeights(False)
    history_list_view.setItemsExpandable(False)

    conn_data = db_combo_box.currentData()
    if not conn_data:
        return

    conn_id = conn_data.get("id")
    try:
        history = db.get_query_history(conn_id)
        for row in history:
            history_id, query, ts, status, rows, duration = row
            clean_query = " ".join(query.split())
            short_query = clean_query[:90] + ("..." if len(clean_query) > 90 else "")
            dt = datetime.datetime.fromisoformat(ts)
            status_text = (status or "Unknown").upper()
            display_text = f"{short_query}\n{dt.strftime('%Y-%m-%d %H:%M:%S')}  |  {status_text}  |  {duration:.3f}s"

            item = QStandardItem(display_text)
            item.setData(
                {
                    "id": history_id,
                    "query": query,
                    "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": status,
                    "rows": rows,
                    "duration": f"{duration:.3f} sec",
                },
                Qt.ItemDataRole.UserRole,
            )
            item.setEditable(False)
            item.setToolTip(query)

            if status_text == "SUCCESS":
                item.setForeground(QBrush(QColor("#1f7a1f")))
            elif status_text == "FAILURE":
                item.setForeground(QBrush(QColor("#b42318")))

            model.appendRow(item)

        if model.rowCount() > 0:
            first_index = model.index(0, 0)
            history_list_view.setCurrentIndex(first_index)
            display_history_details(manager, first_index, target_tab)
    except Exception as error:
        QMessageBox.critical(manager.main_window, "Error", f"Failed to load query history:\n{error}")


def display_history_details(manager, index, target_tab):
    history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
    if not index.isValid() or not history_details_view:
        return

    data = index.model().itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
    details_text = (
        f"Timestamp : {data['timestamp']}\n"
        f"Status    : {data['status']}\n"
        f"Duration  : {data['duration']}\n"
        f"Rows      : {data['rows']}\n\n"
        f"-- Query -----------------------------------------------------------\n"
        f"{data['query']}"
    )
    history_details_view.setPlainText(details_text)


def get_selected_history_item(manager, target_tab):
    history_list_view = target_tab.findChild(QTreeView, "history_list_view")
    selected_indexes = history_list_view.selectionModel().selectedIndexes()
    if not selected_indexes:
        QMessageBox.information(manager.main_window, "No Selection", "Please select a history item first.")
        return None

    item = selected_indexes[0].model().itemFromIndex(selected_indexes[0])
    return item.data(Qt.ItemDataRole.UserRole)


def copy_history_query(manager, target_tab):
    history_data = get_selected_history_item(manager, target_tab)
    if history_data:
        QApplication.clipboard().setText(history_data["query"])
        manager.main_window.status_message_label.setText("Query copied to clipboard.")


def copy_history_to_editor(manager, target_tab):
    history_data = get_selected_history_item(manager, target_tab)
    if history_data:
        editor_stack = target_tab.findChild(QStackedWidget, "editor_stack")
        query_editor = target_tab.findChild(QPlainTextEdit, "query_editor")
        if not query_editor:
            QMessageBox.warning(manager.main_window, "Editor Not Found", "Could not locate the query editor in this tab.")
            return

        query_editor.setPlainText(history_data["query"])
        if editor_stack:
            editor_stack.setCurrentIndex(0)

        query_view_btn = target_tab.findChild(QPushButton, "query_view_btn")
        history_view_btn = target_tab.findChild(QPushButton, "history_view_btn")
        if query_view_btn:
            query_view_btn.setChecked(True)
        if history_view_btn:
            history_view_btn.setChecked(False)

        manager.main_window.status_message_label.setText("Query copied to editor.")


def remove_selected_history(manager, target_tab):
    history_data = get_selected_history_item(manager, target_tab)
    if not history_data:
        return

    history_id = history_data["id"]
    reply = QMessageBox.question(
        manager.main_window,
        "Remove History",
        "Are you sure you want to remove the selected query history?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        try:
            db.delete_history(history_id)
            load_connection_history(manager, target_tab)
            target_tab.findChild(QTextEdit, "history_details_view").clear()
        except Exception as error:
            QMessageBox.critical(manager.main_window, "Error", f"Failed to remove history item:\n{error}")


def remove_all_history_for_connection(manager, target_tab):
    db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
    conn_data = db_combo_box.currentData()
    if not conn_data:
        QMessageBox.warning(manager.main_window, "No Connection", "Please select a connection first.")
        return

    conn_id = conn_data.get("id")
    conn_name = db_combo_box.currentText()
    reply = QMessageBox.question(
        manager.main_window,
        "Remove All History",
        f"Are you sure you want to remove all history for the connection:\n'{conn_name}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        try:
            db.delete_all_history(conn_id)
            load_connection_history(manager, target_tab)
        except Exception as error:
            QMessageBox.critical(manager.main_window, "Error", f"Failed to clear history for this connection:\n{error}")
