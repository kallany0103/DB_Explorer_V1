import os
import sqlite3 as sqlite

import psycopg2
# from PyQt6.QtCore import Qt
# from PyQt6.QtGui import QStandardItem, QIcon
# from PyQt6.QtWidgets import QHeaderView

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import QHeaderView
import qtawesome as qta

import db


class SchemaLoader:
    def __init__(self, manager):
        self.manager = manager

    def _prepare_schema_tree(self):
        self.manager._save_schema_tree_expansion_state()
        self.manager.schema_model.clear()
        self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        self.manager.schema_tree.setColumnWidth(0, 200)
        self.manager.schema_tree.setColumnWidth(1, 100)

        header = self.manager.schema_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.manager._apply_schema_header_style()

    def _connect_expand_handler(self):
        if hasattr(self.manager, '_expanded_connection'):
            try:
                self.manager.schema_tree.expanded.disconnect(
                    self.manager._expanded_connection)
            except TypeError:
                pass
        self.manager._expanded_connection = self.manager.schema_tree.expanded.connect(
            self.manager.table_details_loader.load_tables_on_expand)

    def populate_sqlite_schema(self, data):
        conn_data = data.get("conn_data", {})
        rows = data.get("rows", [])

        self._prepare_schema_tree()

        for name, type_str in rows:
            name_item = QStandardItem(name)
            name_item.setEditable(False)
            if type_str == 'table':
                self.manager._set_tree_item_icon(name_item, level="TABLE")
            else:
                self.manager._set_tree_item_icon(name_item, level="VIEW")

            item_data = {
                'db_type': 'sqlite',
                'conn_data': conn_data,
                'table_name': name
            }
            name_item.setData(item_data, Qt.ItemDataRole.UserRole)

            type_item = QStandardItem(type_str.capitalize())
            type_item.setEditable(False)

            if type_str in ['table', 'view']:
                name_item.appendRow(QStandardItem("Loading..."))

            self.manager.schema_model.appendRow([name_item, type_item])

        self._connect_expand_handler()
        self.manager._restore_schema_tree_expansion_state()

    def load_sqlite_schema(self, conn_data):
        db_path = conn_data.get("db_path")
        if not db_path or not os.path.exists(db_path):
            self.manager.status.showMessage(
                f"Error: SQLite DB path not found: {db_path}", 5000)
            return
        try:
            conn = sqlite.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name;")
            rows = cursor.fetchall()
            conn.close()
            self.populate_sqlite_schema({
                "conn_data": conn_data,
                "rows": rows,
            })

        except Exception as e:
            self.manager.status.showMessage(f"Error loading SQLite schema: {e}", 5000)

    def populate_postgres_schema(self, data):
        conn_data = data.get("conn_data", {})
        schemas = data.get("schemas", [])

        self._prepare_schema_tree()

        if hasattr(self.manager, "pg_conn") and self.manager.pg_conn and not self.manager.pg_conn.closed:
            try:
                self.manager.pg_conn.close()
            except Exception:
                pass

        self.manager.pg_conn = psycopg2.connect(
            host=conn_data["host"],
            database=conn_data["database"],
            user=conn_data["user"],
            password=conn_data["password"],
            port=int(conn_data["port"]),
        )
        self.manager.pg_conn.autocommit = True

        schemas_root = QStandardItem("Schemas")
        schemas_root.setEditable(False)
        self.manager._set_tree_item_icon(schemas_root, level="GROUP_SCHEMAS")
        schemas_root.setData({'db_type': 'postgres', 'type': 'schemas_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)

        for schema_name in schemas:
            schema_item = QStandardItem(schema_name)
            schema_item.setEditable(False)
            self.manager._set_tree_item_icon(schema_item, level="SCHEMA")
            schema_item.setData({'db_type': 'postgres', 'schema_name': schema_name,
                                 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
            schema_item.appendRow(QStandardItem("Loading..."))
            type_item = QStandardItem("Schema")
            type_item.setEditable(False)
            schemas_root.appendRow([schema_item, type_item])

        schemas_type_item = QStandardItem("Group")
        schemas_type_item.setEditable(False)
        self.manager.schema_model.appendRow([schemas_root, schemas_type_item])

        fdw_root = QStandardItem("Foreign Data Wrappers")
        fdw_root.setEditable(False)
        self.manager._set_tree_item_icon(fdw_root, level="FDW_ROOT")
        fdw_root.setData({'db_type': 'postgres', 'type': 'fdw_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
        fdw_root.appendRow(QStandardItem("Loading..."))

        fdw_type_item = QStandardItem("Group")
        fdw_type_item.setEditable(False)
        self.manager.schema_model.appendRow([fdw_root, fdw_type_item])

        ext_root = QStandardItem("Extensions")
        ext_root.setEditable(False)
        self.manager._set_tree_item_icon(ext_root, level="EXTENSION_ROOT")
        ext_root.setData({'db_type': 'postgres', 'type': 'extension_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
        ext_root.appendRow(QStandardItem("Loading..."))

        ext_type_item = QStandardItem("Group")
        ext_type_item.setEditable(False)
        self.manager.schema_model.appendRow([ext_root, ext_type_item])

        lang_root = QStandardItem("Languages")
        lang_root.setEditable(False)
        self.manager._set_tree_item_icon(lang_root, level="LANGUAGE_ROOT")
        lang_root.setData({'db_type': 'postgres', 'type': 'language_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
        lang_root.appendRow(QStandardItem("Loading..."))

        lang_type_item = QStandardItem("Group")
        lang_type_item.setEditable(False)
        self.manager.schema_model.appendRow([lang_root, lang_type_item])

        self._connect_expand_handler()
        self.manager._restore_schema_tree_expansion_state()

    def load_postgres_schema(self, conn_data):
        pg_conn = None
        try:
            pg_conn = psycopg2.connect(
                host=conn_data["host"],
                database=conn_data["database"],
                user=conn_data["user"],
                password=conn_data["password"],
                port=int(conn_data["port"]),
            )
            cursor = pg_conn.cursor()
            cursor.execute(
                "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%%' AND nspname != 'information_schema' ORDER BY nspname;")
            schemas = [row[0] for row in cursor.fetchall()]
            pg_conn.close()
            self.populate_postgres_schema({
                "conn_data": conn_data,
                "schemas": schemas,
            })
        except Exception as e:
            self.manager.status.showMessage(f"Error loading schemas: {e}", 5000)
            if hasattr(self.manager, 'pg_conn') and self.manager.pg_conn:
                self.manager.pg_conn.close()
        finally:
            if pg_conn:
                try:
                    pg_conn.close()
                except Exception:
                    pass

    def update_schema_context(self, schema_name, schema_type, table_count):
        if not hasattr(self.manager.main_window, 'schema_model') or not hasattr(self.manager.main_window, 'schema_tree'):
            return

        self.manager.main_window.schema_model.clear()
        self.manager.main_window.schema_model.setHorizontalHeaderLabels(["Database Schema"])

        root = self.manager.main_window.schema_model.invisibleRootItem()

        name_item = QStandardItem(f"Name : {schema_name}")
        type_item = QStandardItem(f"Type : {schema_type}")
        table_item = QStandardItem(f"Tables : {table_count}")

        name_item.setEditable(False)
        type_item.setEditable(False)
        table_item.setEditable(False)

        root.appendRow(name_item)
        root.appendRow(type_item)
        root.appendRow(table_item)

        self.manager.main_window.schema_tree.expandAll()

    def load_csv_schema(self, conn_data):
        folder_path = conn_data.get("db_path")
        if not folder_path or not os.path.exists(folder_path):
            self.manager.status.showMessage(f"CSV folder not found: {folder_path}", 5000)
            return

        try:
            csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]
            self.populate_csv_schema({
                "conn_data": conn_data,
                "files": csv_files,
            })

        except Exception as e:
            self.manager.status.showMessage(f"Error loading CSV folder: {e}", 5000)

    def populate_csv_schema(self, data):
        conn_data = data.get("conn_data", {})
        csv_files = data.get("files", [])

        self._prepare_schema_tree()

        for file_name in csv_files:
            display_name, _ = os.path.splitext(file_name)
            table_item = QStandardItem(qta.icon("mdi.table", color="#4CAF50"), display_name)
            table_item.setEditable(False)
            table_item.setData({
                'db_type': 'csv',
                'table_name': file_name,
                'conn_data': conn_data
            }, Qt.ItemDataRole.UserRole)
            table_item.appendRow(QStandardItem("Loading..."))

            type_item = QStandardItem("Table")
            type_item.setEditable(False)

            self.manager.schema_model.appendRow([table_item, type_item])
            
        self.manager._restore_schema_tree_expansion_state()

    def populate_servicenow_schema(self, data):
        """UI-only: render the ServiceNow table list emitted by ServiceNowSchemaWorker."""
        try:
            conn_data = data.get("conn_data", {})
            tables = data.get("tables", [])

            if not tables:
                self.manager.status.showMessage("No tables found or access restricted.", 5000)
                return

            self._prepare_schema_tree()
            for table_name in tables:
                table_item = QStandardItem(qta.icon("mdi.table", color="#4CAF50"), table_name)
                table_item.setEditable(False)
                table_item.setData({
                    'db_type': 'servicenow',
                    'table_name': table_name,
                    'conn_data': conn_data,
                }, Qt.ItemDataRole.UserRole)
                table_item.appendRow(QStandardItem("Loading..."))

                type_item = QStandardItem("Table")
                type_item.setEditable(False)
                self.manager.schema_model.appendRow([table_item, type_item])

            self._connect_expand_handler()
            self.manager._restore_schema_tree_expansion_state()

        except Exception as e:
            self.manager.status.showMessage(f"Error loading ServiceNow schema: {e}", 5000)

