"""ConnectionManager runtime implementation.

Package-native implementation used as the primary ConnectionManager entrypoint.
"""

import traceback
from PySide6.QtCore import Qt, QModelIndex, QTimer
from ui.icons import get_icon
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
)
from ui.components import ToastNotification
from ui.feature_flags import import_feature_symbol, is_connection_type_enabled

import db
from widgets.connection_manager.tree_helpers import TreeHelpers
from widgets.connection_manager.ui import ConnectionUI
from widgets.connection_manager.schema_loaders import SchemaLoader
from widgets.connection_manager.table_details import TableDetailsLoader
from widgets.connection_manager.scripting import ScriptGenerator
from widgets.connection_manager.actions import ConnectionActions
from widgets.connection_manager.dialogs import ConnectionDialogs
from widgets.connection_manager.context_menus import ContextMenuHandler
from widgets.connection_manager.spinner import ConnectionSpinner
from workers.connection_workers import (
    CsvSchemaWorker,
    OracleSchemaWorker,
    PostgresSchemaWorker,
    ServiceNowSchemaWorker,
    SQLiteSchemaWorker,
    ERDSchemaFetchWorker,
    UDSSchemaWorker,
)

ERDWidget = import_feature_symbol("erd_designer", "widgets.erd.widget", "ERDWidget")




class ConnectionManager(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.status_message_label = main_window.status_message_label
        self.thread_pool = main_window.thread_pool

        self.tree_helpers = TreeHelpers(self)

        self.connection_ui = ConnectionUI(self)
        self.schema_loader = SchemaLoader(self)
        self.table_details_loader = TableDetailsLoader(self)
        self.script_generator = ScriptGenerator(self)
        self.connection_actions = ConnectionActions(self)
        self.connection_dialogs = ConnectionDialogs(self)
        self.context_menu_handler = ContextMenuHandler(self)
        self._spinner = ConnectionSpinner(self)
        self._schema_spinner = ConnectionSpinner(self)
        self._active_schema_workers = []
        self._schema_load_token = 0
        self.active_postgres_conn = None
        self._schema_states = {}
        self._current_conn_id = None
        self._skip_expansion_restore = False

        self.init_ui()
        self.load_data()

    def _get_erd_tab_icon(self):
        return get_icon("msc.type-hierarchy")

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
        if ERDWidget is None or not self.main_window.is_feature_enabled("erd_designer"):
            return
        if not item_data or not isinstance(item_data, dict):
            ToastNotification.show_toast(self, "Invalid item data for ERD generation.", kind="warning")
            return

        # Phase 1 — open the tab instantly with a loading overlay
        schema_name = item_data.get("schema_name")
        table_name  = item_data.get("table_name")
        erd_widget  = ERDWidget({}, loading=True, conn_data=item_data)
        erd_widget._drop_item_data_resolver = self._get_selected_schema_item_data
        tab_title   = self._build_erd_tab_title(display_name, schema_name, table_name)
        index = self.tab_widget.addTab(erd_widget, tab_title)
        self.tab_widget.setTabIcon(index, self._get_erd_tab_icon())
        self.tab_widget.setCurrentIndex(index)
        self.main_window.renumber_tabs()
        QApplication.processEvents()  # flush paint queue so loading overlay renders before worker starts

        # Phase 2 — fetch schema in background; populate widget when done
        worker = ERDSchemaFetchWorker(item_data)
        worker.signals.finished.connect(erd_widget.populate)
        worker.signals.error.connect(erd_widget.show_load_error)
        self.thread_pool.start(worker)

    def show_error_popup(self, msg):
        ToastNotification.show_toast(self, msg, kind="error")

    def _get_current_schema_item_data(self):
        index = self.schema_tree.currentIndex()
        if not index.isValid():
            return None, None, None
        item = self.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        return item, item_data, item.text() if item else None

    def prepare_inspector_item_data(self, item_data, obj_name):
        """Normalize tree UserRole payloads for inspector workbench workers."""
        data = dict(item_data)

        table_type = (data.get("table_type") or "").upper()
        if data.get("table_name"):
            if "TRIGGER" in table_type:
                data["type"] = "trigger_function"
            elif "FUNCTION" in table_type:
                data["type"] = "function"
            elif "SEQUENCE" in table_type:
                data["type"] = "sequence"
            elif "MATERIALIZED" in table_type:
                data["type"] = "materialized_view"
            elif "VIEW" in table_type:
                data["type"] = "view"
            else:
                data["type"] = "table"
            return data

        if data.get("group_name"):
            data["type"] = "schema_group" if data.get("schema_name") else "group"
            return data

        if data.get("type"):
            return data

        if data.get("schema_name"):
            data["type"] = "schema"
        elif (
            data.get("conn_data")
            or data.get("host")
            or data.get("database")
            or data.get("db_type")
            or data.get("instance_url")
            or data.get("db_path")
        ):
            data["type"] = "connection"
            data.setdefault("name", obj_name)
        return data

    def open_properties_workbench(self, item_data, obj_name):
        self.main_window.show_properties_workbench(item_data, obj_name)

    def open_statistics_workbench(self, item_data, obj_name):
        self.main_window.show_statistics_workbench(item_data, obj_name)

    def describe_object(self, item_data, obj_name):
        conn_data = (
            item_data.get("conn_data")
            or item_data.get("connection")
            or (item_data if isinstance(item_data, dict) else None)
        )
        schema_name = item_data.get("schema_name") if isinstance(item_data, dict) else None
        target = f'"{schema_name}"."{obj_name}"' if schema_name and "." not in str(obj_name) else obj_name
        self.main_window.describe_object(target=target, conn_data=conn_data)

    def quick_describe_object(self, item_data, obj_name):
        conn_data = (
            item_data.get("conn_data")
            or item_data.get("connection")
            or (item_data if isinstance(item_data, dict) else None)
        )
        schema_name = item_data.get("schema_name") if isinstance(item_data, dict) else None
        target = f'"{schema_name}"."{obj_name}"' if schema_name and "." not in str(obj_name) else obj_name
        self.main_window.quick_describe(target=target, conn_data=conn_data)

    def _get_selected_schema_item_data(self) -> dict | None:
        """Return the UserRole data dict for the currently selected schema-tree item."""
        _, item_data, _ = self._get_current_schema_item_data()
        return item_data

    def _create_table_from_menu(self):
        _, item_data, _ = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_create_table_template(item_data)
        else:
            ToastNotification.show_toast(self, "Please select a schema or table in the Database Schema tree first.", kind="warning")

    def _create_view_from_menu(self):
        _, item_data, _ = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_create_view_template(item_data)
        else:
            ToastNotification.show_toast(self, "Please select a schema or table in the Database Schema tree first.", kind="warning")

    def _query_tool_from_menu(self):
        _, item_data, _name = self._get_current_schema_item_data()
        if item_data:
            self.connection_actions.open_query_tool(item_data)
        else:
            self.add_tab()

    def _delete_object_from_menu(self):
        _, item_data, name = self._get_current_schema_item_data()
        if item_data and item_data.get("table_name"):
            self.connection_actions.delete_table(item_data, name)
        else:
            ToastNotification.show_toast(self, "Please select a table or view to delete.", kind="warning")

    def _properties_object_from_menu(self):
        _, item_data, name = self._get_current_schema_item_data()
        if item_data:
            self.open_properties_workbench(item_data, name)
        else:
            ToastNotification.show_toast(self, "Please select an object in the Database Schema tree first.", kind="warning")

    def eventFilter(self, obj, event):
        if self.tree_helpers.handle_event_filter(obj, event):
            return True
        return super().eventFilter(obj, event)

    def refresh_object_explorer(self, index=None, collapse=False):
        """Scoped refresh: reloads only the connection or table subtree.
        
        Args:
            index: QModelIndex of the item to refresh. If None, refreshes current selection.
                   - Depth 3 (connection): reloads that connection's schema
                   - Depth >= 4 (table/object): reloads that table's details
            collapse: if True, collapses the tree node after refresh
        """
        try:
            # Determine which index to use
            if index is None:
                current_index = self.tree.currentIndex()
                if not current_index.isValid():
                    return
                proxy_index = current_index
            else:
                proxy_index = index
            
            # Check if index is from proxy model, if not, use it directly
            if proxy_index.model() == self.proxy_model:
                source_index = self.proxy_model.mapToSource(proxy_index)
            else:
                source_index = proxy_index
            
            item = self.model.itemFromIndex(source_index)
            if not item:
                return
            
            depth = self.get_item_depth(item)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            
            if depth == 4 and item_data and (item_data.get("type") == "data_source" or item.data(Qt.ItemDataRole.UserRole + 2) == "DATA_SOURCE"):
                self._skip_expansion_restore = collapse
                self.item_clicked(
                    self.proxy_model.mapFromSource(self.model.indexFromItem(item)),
                    skip_restore=collapse,
                )
                self.status.showMessage(f"Data Source '{item.text()}' refreshed.", 3000)
            elif depth == 3 and item_data:
                # Connection-level refresh: reload schema for this connection only
                self._refresh_connection_subtree(item, item_data, collapse=collapse)
            elif depth >= 4 and item_data:
                # Table-level refresh: reload details for this table only
                self._refresh_table_subtree(item, item_data, collapse=collapse)
            else:
                # Fallback: full refresh for unsupported levels
                self._full_refresh(collapse=collapse)
                
        except Exception as e:
            self.status.showMessage(f"Error refreshing explorer: {e}", 5000)
            traceback.print_exc()
    
    def _refresh_connection_subtree(self, item, conn_data, collapse=False):
        """Refresh schema for a specific connection.

        collapse=False  → pgAdmin style: reload and restore expansion state.
        collapse=True   → reset: reload then collapseAll().
        """
        conn_id = conn_data.get("id")
        if not conn_id:
            return

        conn_name = item.text()

        self._skip_expansion_restore = collapse
        self.item_clicked(
            self.proxy_model.mapFromSource(self.model.indexFromItem(item)),
            skip_restore=collapse,
        )

        self.status.showMessage(f"Connection '{conn_name}' refreshed.", 3000)
    
    def _refresh_table_subtree(self, item, item_data, collapse=False):
        """Refresh details for a specific table."""
        table_name = item_data.get('table_name')
        if not table_name:
            return

        self._skip_expansion_restore = collapse
        self._spinner.start(item)

        schema_index = self._find_schema_item_by_data(item_data)
        if schema_index and schema_index.isValid():
            schema_item = self.schema_model.itemFromIndex(schema_index)
            if schema_item:
                self._schema_spinner.start(schema_item)
                QApplication.processEvents()

            if collapse:
                self.schema_tree.collapse(schema_index)

            self.table_details_loader.load_tables_on_expand(schema_index, force=True)

            if schema_item:
                self._schema_spinner.stop()

            if collapse:
                schema_index = self._find_schema_item_by_data(item_data)
                if schema_index and schema_index.isValid():
                    self.schema_tree.collapse(schema_index)

        self._spinner.stop()

        if collapse:
            QTimer.singleShot(500, lambda: setattr(self, '_skip_expansion_restore', False))

        self.status.showMessage(f"Table '{table_name}' refreshed.", 3000)
    
    def _find_schema_item_by_data(self, target_data):
        """Find the schema tree item matching the given data."""
        def search_items(parent_index):
            for row in range(self.schema_model.rowCount(parent_index)):
                index = self.schema_model.index(row, 0, parent_index)
                item = self.schema_model.itemFromIndex(index)
                if item:
                    item_data = item.data(Qt.ItemDataRole.UserRole)
                    if item_data and item_data.get('table_name') == target_data.get('table_name'):
                        # Check if it's the same connection
                        if item_data.get('conn_data', {}).get('id') == target_data.get('conn_data', {}).get('id'):
                            return index
                    # Search children
                    child_result = search_items(index)
                    if child_result:
                        return child_result
            return None
        
        return search_items(QModelIndex())
    
    def _full_refresh(self, collapse=False):
        """Full refresh fallback - reloads entire Object Explorer."""
        self._save_tree_expansion_state()
        self._save_schema_tree_expansion_state(self._current_conn_id)
        
        if collapse:
            self.tree.collapseAll()
            self.schema_tree.collapseAll()
        
        self.load_data()
        self._restore_tree_expansion_state()
        self._restore_schema_tree_expansion_state(self._current_conn_id)
        
        current_index = self.tree.currentIndex()
        if current_index.isValid():
            self.item_clicked(current_index)
                
        self.status.showMessage("Object Explorer refreshed.", 3000)
    
    def refresh_schema_tree_item(self, index, collapse=False):
        """Scoped refresh for schema tree items."""
        if not index or not index.isValid():
            return

        item = self.schema_model.itemFromIndex(index)
        if not item:
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        display_name = item.text()
        node_type = item_data.get('type', '')

        # Spinner helper (sync ops: shows one frame; better than nothing)
        def _spin_and_reload(target_index, target_item):
            self._schema_spinner.start(target_item)
            QApplication.processEvents()
            self.table_details_loader.load_tables_on_expand(target_index, force=True)
            self._schema_spinner.stop()

        _GROUPS_THAT_REFRESH_PARENT = (
            'schema_group', 
            'columns_group', 
            'constraints_group', 
            'indexes_group', 
            'triggers_group', 
            'policies_group'
        )

        if node_type in _GROUPS_THAT_REFRESH_PARENT:
            parent_index = index.parent()
            if parent_index and parent_index.isValid():
                parent_item = self.schema_model.itemFromIndex(parent_index)
                if parent_item:
                    parent_data = parent_item.data(Qt.ItemDataRole.UserRole)
                    if parent_data:
                        self._skip_expansion_restore = collapse
                        _spin_and_reload(parent_index, parent_item)
                        if collapse:
                            QTimer.singleShot(300, lambda: self.schema_tree.collapse(parent_index) if parent_index.isValid() else None)
                            QTimer.singleShot(600, lambda: setattr(self, '_skip_expansion_restore', False))
                        self.status.showMessage(f"Parent '{parent_item.text()}' refreshed.", 3000)
                        return

        self._skip_expansion_restore = collapse
        _spin_and_reload(index, item)

        if collapse and node_type not in _GROUPS_THAT_REFRESH_PARENT:
            QTimer.singleShot(300, lambda: self.schema_tree.collapse(index) if index.isValid() else None)
            QTimer.singleShot(600, lambda: setattr(self, '_skip_expansion_restore', False))

        table_name = item_data.get('table_name', '')
        if table_name:
            self.status.showMessage(f"Table '{display_name}' refreshed.", 3000)
        elif node_type == 'schema':
            self.status.showMessage(f"Schema '{display_name}' refreshed.", 3000)
        elif node_type == 'schema_group':
            self.status.showMessage(f"Group '{display_name}' refreshed.", 3000)
        else:
            self.status.showMessage(f"Item '{display_name}' refreshed.", 3000)

    def toggle_explorer_search(self):
        self.tree_helpers.toggle_explorer_search()

    def hide_explorer_search(self):
        self.tree_helpers.hide_explorer_search()

    def filter_object_explorer(self, text):
        self.tree_helpers.filter_object_explorer(text)

    def filter_schema_tree(self, text: str):
        self.tree_helpers.filter_schema_tree(text)

    def toggle_schema_search(self):
        self.tree_helpers.toggle_schema_search()

    def show_schema_search(self):
        self.tree_helpers.show_schema_search()

    def hide_schema_search(self):
        self.tree_helpers.hide_schema_search()

    def load_data(self, hierarchical_data=None):
        # Detach the proxy model for the entire build so zero proxy events fire
        # during construction. Reattaching at the end does a single O(n) scan of
        # the completed model — far cheaper than blockSignals + invalidate() which
        # still walks every node with recursive filtering enabled.
        self.proxy_model.setSourceModel(None)
        try:
            self.model.clear()
            self.model.setHorizontalHeaderLabels(["Object Explorer"])

            if hierarchical_data is None:
                hierarchical_data = db.get_hierarchy_data()

            root_items = []
            for connection_type_data in hierarchical_data:
                code = connection_type_data["code"]
                if not is_connection_type_enabled(self.main_window, code):
                    continue
                connection_type_item = QStandardItem(connection_type_data["name"])
                connection_type_item.setData(code, Qt.ItemDataRole.UserRole)
                connection_type_item.setData(connection_type_data["id"], Qt.ItemDataRole.UserRole + 1)
                self._set_tree_item_icon(connection_type_item, level="TYPE", code=code)

                for connection_group_data in connection_type_data["usf_connection_groups"]:
                    connection_group_item = QStandardItem(connection_group_data["name"])
                    connection_group_item.setData(connection_group_data["id"], Qt.ItemDataRole.UserRole + 1)
                    self._set_tree_item_icon(connection_group_item, level="GROUP")

                    conn_items = []
                    for connection_data in connection_group_data["usf_connections"]:
                        connection_item = QStandardItem(connection_data["short_name"])
                        connection_data["db_type"] = code.lower()

                        # Full connection object
                        connection_item.setData(connection_data, Qt.ItemDataRole.UserRole)

                        # Connection ID (FK for data sources)
                        connection_item.setData(
                            connection_data["id"],
                            Qt.ItemDataRole.UserRole + 1
                        )

                        # Node type
                        connection_item.setData(
                            "CONNECTION",
                            Qt.ItemDataRole.UserRole + 2
                        )

                        self._set_tree_item_icon(
                            connection_item,
                            level="CONNECTION",
                            code="POSTGRES" if (code == "UDS" or connection_data.get("db_type") == "uds") else code
                        )

                        conn_items.append(connection_item)

                    if conn_items:
                        connection_group_item.appendRows(conn_items)
                    connection_type_item.appendRow(connection_group_item)

                root_items.append(connection_type_item)

            # Batch-append all root items in one call, then reconnect proxy
            if root_items:
                self.model.invisibleRootItem().appendRows(root_items)

        finally:
            # Reconnect proxy — single clean scan of the completed model
            self.proxy_model.setSourceModel(self.model)

    def _set_tree_item_icon(self, item, level, code=""):
        self.tree_helpers.set_tree_item_icon(item, level, code)

    def _save_tree_expansion_state(self):
        self.tree_helpers.save_tree_expansion_state()

    def _restore_tree_expansion_state(self):
        self.tree_helpers.restore_tree_expansion_state()

    def _save_schema_tree_expansion_state(self, conn_id=None):
        if self._skip_expansion_restore:
            return
        target_id = conn_id or self._current_conn_id
        if target_id:
            self.tree_helpers.save_schema_tree_expansion_state(target_id)

    def _restore_schema_tree_expansion_state(self, conn_id=None):
        if self._skip_expansion_restore:
            return
        target_id = conn_id or self._current_conn_id
        if target_id:
            self.tree_helpers.restore_schema_tree_expansion_state(target_id)

    def delete_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        connection_id = conn_data.get("id")
        conn_name = conn_data.get("name", "this connection")

        from ui.components import ConfirmDialog, ToastNotification
        confirmed = ConfirmDialog.confirm(
            parent=self,
            title="Delete Connection",
            message=f"Are you sure you want to delete '{conn_name}'?\nThis action cannot be undone.",
            confirm_text="Delete",
            cancel_text="Cancel",
            kind="danger",
        )
        if not confirmed:
            return

        try:
            db.delete_connection(connection_id)
            self._save_tree_expansion_state()
            self.load_data()
            self._restore_tree_expansion_state()
            self.refresh_all_comboboxes()
            ToastNotification.show_toast(self, f"'{conn_name}' deleted successfully!", kind="success")
        except Exception as exc:
            ToastNotification.show_toast(self, f"Failed to delete connection: {exc}", kind="error")

    def item_clicked(self, proxy_index, skip_restore=False):
        self._schema_load_token += 1
        ToastNotification.dismiss_all()

        # Cancel all in-flight schema workers.  Deactivate the guard flag so
        # any signals already sitting in Qt's event queue are silently dropped
        # at delivery time (disconnect() alone does not remove queued signals).
        for old_worker in list(self._active_schema_workers):
            if hasattr(old_worker, "_signal_guard"):
                old_worker._signal_guard[0] = False
            if hasattr(old_worker, "cancel"):
                old_worker.cancel()
            setattr(old_worker, "_canceled", True)
            try:
                old_worker.signals.finished.disconnect()
            except Exception:
                pass
            try:
                old_worker.signals.error.disconnect()
            except Exception:
                pass
        self._active_schema_workers.clear()

        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
        depth = self.get_item_depth(item)
        
        # Save state for the PREVIOUS connection before switching
        if self._current_conn_id:
            self._save_schema_tree_expansion_state(self._current_conn_id)
        
        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        if hasattr(self, "schema_status_label"):
            self.schema_status_label.setText("")
        self._default_schema_status = ""
        if depth != 3:
            self._current_conn_id = None
            return

        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            self._current_conn_id = None
            return
            
        new_conn_id = conn_data.get("id")
        
        # Always clear saved selection when clicking a database
        if hasattr(self, '_schema_states') and new_conn_id in self._schema_states:
            self._schema_states[new_conn_id]['selection'] = None
                
        self._current_conn_id = new_conn_id

        parent_group = item.parent()
        if not parent_group:
            return

        connection_type = parent_group.parent()
        if not connection_type:
            return

        connection_type_name = connection_type.text().lower() if connection_type else ""
        db_type = str(conn_data.get("db_type") or "").lower()
        conn_name = item.text()
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.add_connection_notification(conn_name)

        if "unified" in connection_type_name or "uds" in connection_type_name or db_type == "uds":
            self.active_postgres_conn = conn_data
            self.status.showMessage(f"Loading Unified Data Sources for {conn_name}...", 3000)
            worker = UDSSchemaWorker(conn_data)
            self._start_schema_load(item, worker, self.schema_loader.populate_uds_schema, skip_restore=skip_restore)
        elif ("postgres" in connection_type_name or db_type in ("postgres", "postgresql")) and (conn_data.get("host") or conn_data.get("dsn")):
            self.active_postgres_conn = conn_data
            self.status.showMessage(f"Loading schema for {conn_data.get('name')}...", 3000)
            worker = PostgresSchemaWorker(conn_data)
            self._start_schema_load(item, worker, self.schema_loader.populate_postgres_schema, skip_restore=skip_restore)
        elif ("sqlite" in connection_type_name or db_type == "sqlite") and conn_data.get("db_path"):
            self.status.showMessage(f"Loading schema for {conn_data.get('name')}...", 3000)
            worker = SQLiteSchemaWorker(conn_data)
            self._start_schema_load(item, worker, self.schema_loader.populate_sqlite_schema, skip_restore=skip_restore)
        elif ("csv" in connection_type_name or db_type == "csv") and conn_data.get("db_path"):
            self.status.showMessage(f"Loading CSV folder for {conn_name}...", 3000)
            worker = CsvSchemaWorker(conn_data)
            self._start_schema_load(item, worker, self.schema_loader.populate_csv_schema, skip_restore=skip_restore)
        elif "servicenow" in connection_type_name or db_type == "servicenow":
            self.status.showMessage(f"Loading ServiceNow schema for {conn_name}...", 3000)
            worker = ServiceNowSchemaWorker(conn_data)
            self._start_schema_load(item, worker, self.schema_loader.populate_servicenow_schema, skip_restore=skip_restore)
        elif "oracle" in connection_type_name or "oracle" in db_type:
            self.status.showMessage(f"Loading Oracle schema for {conn_name}...", 3000)
            worker = OracleSchemaWorker(conn_data)
            self._start_schema_load(
                item, worker, self.schema_loader.populate_oracle_schema,
                skip_restore=skip_restore
            )
        else:
            self.status.showMessage("Unknown connection type.", 3000)

    def _start_schema_load(self, item, worker, populate_fn, skip_restore=False):
        self._schema_load_token += 1
        current_token = self._schema_load_token
        target_conn_id = self._current_conn_id
        self._spinner.start(item)
        self._active_schema_workers.append(worker)

        # Guard flag checked at delivery time — survives already-queued signals
        # because Qt QueuedConnection delivers even after disconnect() is called.
        guard = [True]  # list cell so inner lambdas can mutate it
        worker._signal_guard = guard

        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        if hasattr(self, "schema_status_label"):
            self.schema_status_label.setText("")
        self._default_schema_status = ""
        loading_item = QStandardItem("Loading schema...")
        loading_item.setEditable(False)
        self.schema_model.appendRow(loading_item)
        self._schema_spinner.start(loading_item)

        def _remove_worker():
            if worker in self._active_schema_workers:
                self._active_schema_workers.remove(worker)

        def on_finished(data):
            if not guard[0]:
                return  # cancelled — drop even if already in Qt event queue
            _remove_worker()
            if current_token != self._schema_load_token or (
                target_conn_id and self._current_conn_id != target_conn_id
            ):
                return
            self._spinner.stop()
            self._schema_spinner.stop()
            self.schema_tree.repaint()
            try:
                populate_fn(data, skip_restore=skip_restore)
                if skip_restore:
                    self.schema_tree.collapseAll()
            except Exception as exc:
                self.status.showMessage(f"Error populating schema: {exc}", 5000)
                self.show_error_popup(f"Failed to populate schema:\n{exc}")
            finally:
                self._skip_expansion_restore = False

        def on_error(message):
            if not guard[0]:
                return  # cancelled — drop even if already in Qt event queue
            _remove_worker()
            if current_token != self._schema_load_token or (
                target_conn_id and self._current_conn_id != target_conn_id
            ):
                return  # Drop stale errors from previous connection attempts
            self._spinner.stop()
            self._schema_spinner.stop()
            self.schema_model.clear()
            self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            err_icon = get_icon("msc.debug-disconnect", color="#EF4444")
            err_item = QStandardItem(err_icon, "Cannot connect to instance")
            err_item.setToolTip(message)
            err_item.setEditable(False)
            type_item = QStandardItem("Offline / Error")
            type_item.setEditable(False)
            self.schema_model.appendRow([err_item, type_item])
            if hasattr(self, "schema_status_label"):
                self.schema_status_label.setText("Disconnected")
            self.status.showMessage(f"Error loading schema: {message}", 5000)

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        self.thread_pool.start(worker)

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
        if not item_data or not isinstance(item_data, dict):
            if item.rowCount() > 0:
                if self.schema_tree.isExpanded(index):
                    self.schema_tree.collapse(index)
                else:
                    self.schema_tree.expand(index)
            return

        table_name = item_data.get("table_name")
        table_type = (item_data.get("table_type") or "").upper()
        node_type = (item_data.get("type") or "").lower()
        obj_name = table_name or item.text()

        # Programmable objects (Packages, Procedures, Functions, Triggers, Types)
        programmable_types = {
            "PACKAGE",
            "PACKAGE BODY",
            "PROCEDURE",
            "FUNCTION",
            "TRIGGER",
            "TRIGGER FUNCTION",
            "TYPE",
            "TYPE BODY",
            "JAVA SOURCE",
            "JAVA CLASS",
        }
        if table_type in programmable_types or node_type in (
            "package",
            "procedure",
            "function",
            "trigger",
            "type",
            "java",
        ):
            eff_type = table_type if table_type in programmable_types else node_type.upper()
            self.script_generator.script_object_source(item_data, obj_name, eff_type)
            return

        # Sequences: generate CREATE SEQUENCE script
        if table_type == "SEQUENCE" or node_type == "sequence":
            self.script_generator.script_sequence_as_create(item_data, obj_name)
            return

        # Tabular objects (Table, View, Materialized View, etc.)
        tabular_types = {
            "TABLE",
            "VIEW",
            "MATERIALIZED VIEW",
            "EXTERNAL TABLE",
            "FOREIGN TABLE",
            "SYSTEM TABLE",
            "LOCAL TEMPORARY",
            "GLOBAL TEMPORARY",
            "SYNONYM",
        }
        if table_name and (table_type in tabular_types or not table_type or node_type in ("table", "view")):
            self.connection_actions.query_table_rows(item_data, item.text(), limit=None, execute_now=True)
            return

        # Folder / Group / Schema / Expandable container nodes: toggle expand / collapse
        if item.rowCount() > 0:
            if self.schema_tree.isExpanded(index):
                self.schema_tree.collapse(index)
            else:
                self.schema_tree.expand(index)

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
        ToastNotification.dismiss_all()
        # Cancel any in-flight workers before starting a new load
        for old_worker in list(self._active_schema_workers):
            if hasattr(old_worker, "_signal_guard"):
                old_worker._signal_guard[0] = False
            if hasattr(old_worker, "cancel"):
                old_worker.cancel()
            setattr(old_worker, "_canceled", True)
            try:
                old_worker.signals.finished.disconnect()
            except Exception:
                pass
            try:
                old_worker.signals.error.disconnect()
            except Exception:
                pass
        self._active_schema_workers.clear()
        if conn_data:
            self._current_conn_id = conn_data.get("id")
        worker = ServiceNowSchemaWorker(conn_data)
        self._start_schema_load(None, worker, self.schema_loader.populate_servicenow_schema)

    def handle_process_started(self, process_id, data):
        self.status.showMessage(f"Export Started: {data.get('details', 'Processing...')}", 3000)
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_started(process_id, data)

    def handle_process_finished(self, process_id, message, time_taken, row_count):
        self.status.showMessage(f"Export Finished: {message} ({time_taken:.2f}s)", 5000)
        ToastNotification.show_toast(self, message, kind="success")
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_finished(process_id, message, time_taken, row_count)

    def handle_process_error(self, process_id, error_message):
        self.status.showMessage(f"Export Failed: {error_message}", 5000)
        ToastNotification.show_toast(self, f"Export failed: {error_message}", kind="error")
        if hasattr(self.main_window, "results_manager"):
            self.main_window.results_manager.handle_process_error(process_id, error_message)

    def _get_dialog_style(self):
        return """
            QDialog {
                background-color: #f6f8fb;
            }
            QLabel#dialogTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
            }
            QLabel#dialogSubtitle {
                color: #6b7280;
                margin-bottom: 8px;
            }
            QLineEdit {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding: 3px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                min-height: 28px;
                padding: 2px 14px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton:pressed {
                background-color: #d7deeb;
            }
            QPushButton#primaryButton {
                border: 1px solid #006cbe;
                background-color: #0078d4;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #006cbe;
            }
            QPushButton#primaryButton:pressed {
                background-color: #005a9e;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                padding: 4px;
                border: none;
                border-bottom: 1px solid #d1d5db;
                border-right: 1px solid #d1d5db;
                color: #4b5563;
                font-weight: 600;
            }
            """

    def add_connection_flow(self):
        self.connection_dialogs.add_new_connection_flow()
