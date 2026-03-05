"""ConnectionManager runtime implementation.

Package-native implementation used as the primary ConnectionManager entrypoint.
"""

import datetime

import qtawesome as qta
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QWidget, QMessageBox

import db
from widgets.erd.widget import ERDWidget
from widgets.connection_manager.tree_helpers import TreeHelpers
from widgets.connection_manager.ui import ConnectionUI
from widgets.connection_manager.schema_loaders import SchemaLoader
from widgets.connection_manager.table_details import TableDetailsLoader
from widgets.connection_manager.scripting import ScriptGenerator
from widgets.connection_manager.actions import ConnectionActions
from widgets.connection_manager.dialogs import ConnectionDialogs
from widgets.connection_manager.context_menus import ContextMenuHandler


class ConnectionManager(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.status_message_label = main_window.status_message_label
        self.thread_pool = main_window.thread_pool
        self.notification_manager = main_window.notification_manager

        self.tree_helpers = TreeHelpers(self)
        self.connection_ui = ConnectionUI(self)
        self.schema_loader = SchemaLoader(self)
        self.table_details_loader = TableDetailsLoader(self)
        self.script_generator = ScriptGenerator(self)
        self.connection_actions = ConnectionActions(self)
        self.connection_dialogs = ConnectionDialogs(self)
        self.context_menu_handler = ContextMenuHandler(self)

        self.erd_icon_key = "fa6s.sitemap"
        self.erd_icon_fallback_key = "fa5s.project-diagram"

        self.init_ui()
        self.load_data()

    def _get_erd_tab_icon(self):
        for icon_key in (self.erd_icon_key, self.erd_icon_fallback_key):
            try:
                return qta.icon(icon_key)
            except Exception:
                continue
        return qta.icon("fa5s.project-diagram")

    def _build_erd_tab_title(self, display_name, schema_name, table_name):
        if schema_name and table_name:
            return f"ERD - {schema_name}.{table_name}"
        if table_name:
            return f"ERD - {table_name}"
        if schema_name:
            return f"ERD - {schema_name}"
        if display_name:
            return f"ERD - {display_name}"
        return "ERD"

    def init_ui(self):
        self.connection_ui.init_ui()

    def _apply_schema_header_style(self):
        self.connection_ui.apply_schema_header_style()

    def add_tab(self):
        return self.main_window.add_tab()

    def execute_query(self, *args, **kwargs):
        return self.main_window.execute_query(*args, **kwargs)

    def refresh_all_comboboxes(self):
        self.main_window.refresh_all_comboboxes()

    def generate_erd(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        display_name = item.text()
        self.generate_erd_for_item(item_data, display_name)

    def generate_erd_for_item(self, item_data, display_name):
        try:
            if not item_data or not isinstance(item_data, dict):
                QMessageBox.warning(self, "Error", "Invalid item data for ERD generation.")
                return

            db_type_val = (item_data.get("db_type") or item_data.get("type") or item_data.get("code") or "").upper()
            schema_name = item_data.get("schema_name")
            table_name = item_data.get("table_name")
            conn_info = item_data.get("conn_data") or item_data

            if "POSTGRES" in db_type_val:
                full_schema = db.get_postgres_schema(conn_info, schema_name=schema_name)
            elif "SQLITE" in db_type_val:
                full_schema = db.get_sqlite_schema(conn_info)
            else:
                QMessageBox.warning(self, "Not Supported", f"ERD generation is not supported for {db_type_val or 'unknown type'}")
                return

            if not full_schema:
                QMessageBox.warning(self, "No Data", "Could not retrieve schema data for ERD.")
                return

            filtered_schema = full_schema
            if table_name:
                target_full_name = f"{schema_name}.{table_name}" if schema_name and "POSTGRES" in db_type_val else table_name
                if target_full_name in full_schema:
                    related_tables = {target_full_name}
                    for fk in full_schema[target_full_name].get("foreign_keys", []):
                        related_tables.add(fk["table"])
                    for t_name, t_info in full_schema.items():
                        for fk in t_info.get("foreign_keys", []):
                            if fk["table"] == target_full_name:
                                related_tables.add(t_name)
                    filtered_schema = {name: info for name, info in full_schema.items() if name in related_tables}

            if not filtered_schema:
                QMessageBox.warning(self, "No Data", "No related tables found for ERD.")
                return

            erd_widget = ERDWidget(filtered_schema)
            tab_title = self._build_erd_tab_title(display_name, schema_name, table_name)
            index = self.tab_widget.addTab(erd_widget, tab_title)
            self.tab_widget.setTabIcon(index, self._get_erd_tab_icon())
            self.tab_widget.setCurrentIndex(index)
            self.main_window.renumber_tabs()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate ERD: {exc}")

    def show_error_popup(self, msg):
        QMessageBox.critical(self, "Error", msg)

    def _get_current_schema_item_data(self):
        index = self.schema_tree.currentIndex()
        if not index.isValid():
            return None, None, None
        item = self.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        return item, item_data, item.text() if item else None

    def _create_table_from_menu(self):
        _, item_data, _ = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_create_table_template(item_data)
        else:
            QMessageBox.warning(self, "Warning", "Please select a schema or table in the Database Schema tree first.")

    def _create_view_from_menu(self):
        _, item_data, _ = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_create_view_template(item_data)
        else:
            QMessageBox.warning(self, "Warning", "Please select a schema or table in the Database Schema tree first.")

    def _query_tool_from_menu(self):
        _, item_data, name = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_query_tool_for_table(item_data, name)
        else:
            self.add_tab()

    def _delete_object_from_menu(self):
        _, item_data, name = self._get_current_schema_item_data()
        if item_data and item_data.get("table_name"):
            self.connection_actions.delete_table(item_data, name)
        else:
            QMessageBox.warning(self, "Warning", "Please select a table or view to delete.")

    def _properties_object_from_menu(self):
        _, item_data, name = self._get_current_schema_item_data()
        if item_data and item_data.get("table_name"):
            self.connection_actions.show_table_properties(item_data, name)
        else:
            QMessageBox.warning(self, "Warning", "Please select a table or view to view properties.")

    def eventFilter(self, obj, event):
        if self.tree_helpers.handle_event_filter(obj, event):
            return True
        return super().eventFilter(obj, event)

    def refresh_object_explorer(self):
        self._save_tree_expansion_state()
        self.load_data()
        self._restore_tree_expansion_state()
        self.status.showMessage("Object Explorer refreshed.", 3000)

    def toggle_explorer_search(self):
        self.tree_helpers.toggle_explorer_search()

    def filter_object_explorer(self, text):
        self.tree_helpers.filter_object_explorer(text)

    def load_data(self):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Object Explorer"])

        hierarchical_data = db.get_hierarchy_data()
        for connection_type_data in hierarchical_data:
            code = connection_type_data["code"]
            connection_type_item = QStandardItem(connection_type_data["name"])
            connection_type_item.setData(code, Qt.ItemDataRole.UserRole)
            connection_type_item.setData(connection_type_data["id"], Qt.ItemDataRole.UserRole + 1)
            self._set_tree_item_icon(connection_type_item, level="TYPE", code=code)

            for connection_group_data in connection_type_data["usf_connection_groups"]:
                connection_group_item = QStandardItem(connection_group_data["name"])
                connection_group_item.setData(connection_group_data["id"], Qt.ItemDataRole.UserRole + 1)
                self._set_tree_item_icon(connection_group_item, level="GROUP")

                for connection_data in connection_group_data["usf_connections"]:
                    connection_item = QStandardItem(connection_data["short_name"])
                    connection_data["db_type"] = code.lower()
                    connection_item.setData(connection_data, Qt.ItemDataRole.UserRole)
                    self._set_tree_item_icon(connection_item, level="CONNECTION", code=code)
                    connection_group_item.appendRow(connection_item)

                connection_type_item.appendRow(connection_group_item)

            self.model.appendRow(connection_type_item)

    def _set_tree_item_icon(self, item, level, code=""):
        self.tree_helpers.set_tree_item_icon(item, level, code)

    def _save_tree_expansion_state(self):
        self.tree_helpers.save_tree_expansion_state()

    def _restore_tree_expansion_state(self):
        self.tree_helpers.restore_tree_expansion_state()

    def delete_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        connection_id = conn_data.get("id")
        reply = QMessageBox.question(
            self,
            "Delete Connection",
            "Are you sure you want to delete this connection?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection(connection_id)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Failed to delete connection:\n{exc}")

    def item_clicked(self, proxy_index):
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
        if not item:
            return

        depth = self.get_item_depth(item)
        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        if depth != 3:
            return

        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return

        parent_group = item.parent()
        if not parent_group:
            return

        connection_type = parent_group.parent()
        if not connection_type:
            return

        connection_type_name = connection_type.text().lower()
        if "postgres" in connection_type_name and conn_data.get("host"):
            self.status.showMessage(f"Loading schema for {conn_data.get('name')}...", 3000)
            self.load_postgres_schema(conn_data)
        elif "sqlite" in connection_type_name and conn_data.get("db_path"):
            self.status.showMessage(f"Loading schema for {conn_data.get('name')}...", 3000)
            self.load_sqlite_schema(conn_data)
        elif "csv" in connection_type_name and conn_data.get("db_path"):
            self.status.showMessage(f"Loading CSV folder for {conn_data.get('name')}...", 3000)
            self.load_csv_schema(conn_data)
        elif "servicenow" in connection_type_name:
            self.status.showMessage(f"Loading ServiceNow schema for {conn_data.get('name')}...", 3000)
            self.load_servicenow_schema(conn_data)
        elif "oracle" in connection_type_name:
            self.status.showMessage("Oracle connections are not currently supported.", 5000)
            QMessageBox.information(self, "Not Supported", "Connecting to Oracle databases is not supported in this version.")
        else:
            self.status.showMessage("Unknown connection type.", 3000)

    def item_double_clicked(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
        if not item:
            return
        if self.get_item_depth(item) == 3:
            self.add_tab()

    def schema_item_double_clicked(self, index: QModelIndex):
        item = self.schema_model.itemFromIndex(index)
        if not item:
            return
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        table_name = item_data.get("table_name")
        if table_name:
            self.connection_actions.query_table_rows(item_data, item.text(), limit=None, execute_now=True)

    def get_item_depth(self, item):
        return self.tree_helpers.get_item_depth(item)

    def show_context_menu(self, pos):
        self.context_menu_handler.show_context_menu(pos)

    def load_sqlite_schema(self, conn_data):
        self.schema_loader.load_sqlite_schema(conn_data)

    def load_postgres_schema(self, conn_data):
        self.schema_loader.load_postgres_schema(conn_data)

    def show_schema_context_menu(self, position):
        self.context_menu_handler.show_schema_context_menu(position)

    def update_schema_context(self, schema_name, schema_type, table_count):
        self.schema_loader.update_schema_context(schema_name, schema_type, table_count)

    def load_csv_schema(self, conn_data):
        self.schema_loader.load_csv_schema(conn_data)

    def load_servicenow_schema(self, conn_data):
        self.schema_loader.load_servicenow_schema(conn_data)

    def handle_process_started(self, process_id, data):
        self.status.showMessage(f"Export Started: {data.get('details', 'Processing...')}", 3000)
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_started(process_id, data)

    def handle_process_finished(self, process_id, message, time_taken, row_count):
        self.status.showMessage(f"Export Finished: {message} ({time_taken:.2f}s)", 5000)
        QMessageBox.information(self, "Export Complete", message)
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_finished(process_id, message, time_taken, row_count)

    def handle_process_error(self, process_id, error_message):
        self.status.showMessage(f"Export Failed: {error_message}", 5000)
        QMessageBox.critical(self, "Export Error", f"Export failed:\n{error_message}")
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_error(process_id, error_message)
