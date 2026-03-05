import os
import sqlite3 as sqlite

import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QIcon
from PyQt6.QtWidgets import QHeaderView

import db


class SchemaLoader:
    def __init__(self, manager):
        self.manager = manager

    def load_sqlite_schema(self, conn_data):
        self.manager.schema_model.clear()
        self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        self.manager.schema_tree.setColumnWidth(0, 200)
        self.manager.schema_tree.setColumnWidth(1, 100)

        header = self.manager.schema_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.manager._apply_schema_header_style()

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
            for name, type_str in cursor.fetchall():
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
            conn.close()

            if hasattr(self.manager, '_expanded_connection'):
                try:
                    self.manager.schema_tree.expanded.disconnect(
                        self.manager._expanded_connection)
                except TypeError:
                    pass

            self.manager._expanded_connection = self.manager.schema_tree.expanded.connect(
                self.manager.table_details_loader.load_tables_on_expand)

        except Exception as e:
            self.manager.status.showMessage(f"Error loading SQLite schema: {e}", 5000)

    def load_postgres_schema(self, conn_data):
        try:
            self.manager.schema_model.clear()
            self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            self.manager.pg_conn = psycopg2.connect(host=conn_data["host"], database=conn_data["database"],
                                                    user=conn_data["user"], password=conn_data["password"], port=int(conn_data["port"]))
            cursor = self.manager.pg_conn.cursor()
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast') ORDER BY schema_name;")

            schemas_root = QStandardItem("Schemas")
            schemas_root.setEditable(False)
            self.manager._set_tree_item_icon(schemas_root, level="GROUP")
            schemas_root.setData({'db_type': 'postgres', 'type': 'schemas_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)

            for (schema_name,) in cursor.fetchall():
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
            if hasattr(self.manager, '_expanded_connection'):
                try:
                    self.manager.schema_tree.expanded.disconnect(
                        self.manager._expanded_connection)
                except TypeError:
                    pass
            self.manager._expanded_connection = self.manager.schema_tree.expanded.connect(
                self.manager.table_details_loader.load_tables_on_expand)
        except Exception as e:
            self.manager.status.showMessage(f"Error loading schemas: {e}", 5000)
            if hasattr(self.manager, 'pg_conn') and self.manager.pg_conn:
                self.manager.pg_conn.close()
        self.manager.schema_tree.setColumnWidth(0, 200)
        self.manager.schema_tree.setColumnWidth(1, 100)
        header = self.manager.schema_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.manager._apply_schema_header_style()

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
            self.manager.schema_model.clear()
            self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            self.manager.schema_tree.setColumnWidth(0, 200)
            self.manager.schema_tree.setColumnWidth(1, 100)

            header = self.manager.schema_tree.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.manager._apply_schema_header_style()
            csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]

            for file_name in csv_files:
                display_name, _ = os.path.splitext(file_name)
                table_item = QStandardItem(QIcon("assets/table.svg"), display_name)
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

        except Exception as e:
            self.manager.status.showMessage(f"Error loading CSV folder: {e}", 5000)

    def load_servicenow_schema(self, conn_data):
        try:
            conn = db.create_servicenow_connection(conn_data)
            if not conn:
                self.manager.status.showMessage("Unable to connect to ServiceNow", 5000)
                return

            cursor = conn.cursor()

            try:
                cursor.execute("SELECT TableName FROM sys_tables")
                tables = [row[0] for row in cursor.fetchall()]
            except Exception:
                tables = ['incident', 'task', 'change_request', 'problem', 'change_request']

            if not tables:
                self.manager.status.showMessage("No tables found or access restricted.", 5000)
                return

            self.manager.schema_model.clear()
            self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            for table_name in tables:
                table_item = QStandardItem(QIcon("assets/table.svg"), table_name)
                table_item.setEditable(False)
                table_item.setData({
                    'db_type': 'servicenow',
                    'table_name': table_name,
                    'conn_data': conn_data
                }, Qt.ItemDataRole.UserRole)
                table_item.appendRow(QStandardItem("Loading..."))

                type_item = QStandardItem("Table")
                type_item.setEditable(False)
                self.manager.schema_model.appendRow([table_item, type_item])

            conn.close()
        except Exception as e:
            self.manager.status.showMessage(f"Error loading ServiceNow schema: {e}", 5000)
