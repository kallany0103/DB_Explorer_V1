import datetime
import os
import time
import uuid

import db
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
)

from dialogs import (
    CreateTableDialog, 
    CreateViewDialog, 
    ExportDialog, 
    TablePropertiesDialog,
    SearchObjectsDialog,
    DatabaseStatisticsDialog,
)
from widgets.backup_and_restore.backup.dialog import BackupDialog
from widgets.backup_and_restore.restore.dialog import RestoreDialog
from workers.signals import ProcessSignals, QuerySignals, emit_process_started
from workers.workers import (
    RunnableExportFromModel, 
    RunnableQuery, 
    RunnableSqliteBackup, 
    RunnableSqliteRestore
)
from workers.process_worker import ProcessWorker
from widgets.backup_and_restore.backup.engine import BackupEngine
from widgets.backup_and_restore.restore.engine import RestoreEngine


class ConnectionActions:
    def __init__(self, manager):
        self.manager = manager
        self.backup_engine = BackupEngine(self.manager.main_window)
        self.restore_engine = RestoreEngine(self.manager.main_window)

    def count_table_rows(self, item_data, table_name):
        if not item_data:
            return

        conn_data = dict(item_data.get('conn_data', {}))
        db_type = item_data.get('db_type')
        conn_data['code'] = (conn_data.get('code') or db_type or '').upper()

        if db_type == 'postgres':
            schema = item_data.get("schema_name", "public")
            schema_quoted = f'"{schema}"'
            query = f'SELECT COUNT(*) FROM {schema_quoted}.{table_name};'
        elif db_type == 'csv':
            query = f'SELECT COUNT(*) FROM [{table_name}]'
        else:
            query = f'SELECT COUNT(*) FROM "{table_name}";'

        self.manager.status_message_label.setText(f"Counting rows for {table_name}...")

        current_tab = self.manager.tab_widget.currentWidget()
        if not current_tab:
            self.manager.add_tab()
            current_tab = self.manager.tab_widget.currentWidget()

        signals = QuerySignals()
        runnable = RunnableQuery(conn_data, query, signals)

        results_manager = self.manager.main_window.results_manager
        signals.finished.connect(
            lambda cd, q, res, cols, specs, rc, et, isq: results_manager.handle_query_result(
                current_tab, cd, q, res, cols, specs, rc, et, isq
            )
        )
        signals.error.connect(self.handle_count_error)
        self.manager.thread_pool.start(runnable)

    def handle_count_error(self, error_message):
        self.manager.status.showMessage(f"Error: {error_message}", 5000)
        self.manager.show_error_popup(f"Failed to count rows:\n{error_message}")
        self.manager.status_message_label.setText("Failed to count rows.")


    def open_query_tool_for_table(self, item_data, table_name):
        if not item_data:
            return

        conn_data = item_data.get("conn_data")
        new_tab = self.manager.add_tab()

        query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        for i in range(db_combo_box.count()):
            data = db_combo_box.itemData(i)
            if data and data.get('id') == conn_data.get('id'):
                db_combo_box.setCurrentIndex(i)
                break

        query_editor.clear()
        query_editor.setFocus()
        self.manager.tab_widget.setCurrentWidget(new_tab)

    def query_table_rows(self, item_data, table_name, limit=None, execute_now=True, order=None):
        if not item_data:
            return

        new_tab = self.manager.add_tab()
        new_tab.table_name = table_name

        query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        conn_data = item_data.get('conn_data', {})
        for i in range(db_combo_box.count()):
            data = db_combo_box.itemData(i)
            if data and data.get('id') == conn_data.get('id'):
                db_combo_box.setCurrentIndex(i)
                break

        conn_data = dict(conn_data)
        if item_data.get('db_type') == 'csv':
            conn_data['table_name'] = item_data.get('table_name')

        conn_data['code'] = (conn_data.get('code') or item_data.get('db_type') or '').upper()

        code = conn_data.get('code')
        if code == 'POSTGRES':
            schema = item_data.get("schema_name", "public")
            schema_quoted = f'"{schema}"'
            new_tab.table_name = f'{schema_quoted}.{table_name}'
            query = f'SELECT * FROM {schema_quoted}.{table_name};'
        elif code == 'SQLITE':
            new_tab.table_name = f'{table_name}'
            query = f'SELECT * FROM {table_name};'
        elif code == 'CSV':
            new_tab.table_name = f'[{table_name}]'
            query = f'SELECT * FROM {table_name};'
        elif code == 'SERVICENOW':
            new_tab.table_name = table_name
            query = f'SELECT * FROM {table_name}'
        else:
            self.manager.show_info(f"Unsupported db_type: {code}")
            return

        if order or limit:
            query = query.rstrip(';')

            if order:
                query += f" ORDER BY 1 {order.upper()}"
            if limit:
                query += f" LIMIT {limit}"

            query += ";"

        query_editor.setPlainText(query)

        if execute_now:
            self.manager.tab_widget.setCurrentWidget(new_tab)
            self.manager.execute_query(conn_data, query)

    def _notify_deletion_success(self, object_name, object_type, sql, conn_data):
        """Standard notification after successful deletion of an object."""
        self.manager.status.showMessage(f"{object_type} '{object_name}' deleted.", 4000)
        self.manager.status_message_label.setText(f"{object_type} '{object_name}' deleted.")

        current_tab = self.manager.tab_widget.currentWidget()
        if not current_tab:
            self.manager.add_tab()
            current_tab = self.manager.tab_widget.currentWidget()

        if current_tab:
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QStackedWidget
            message_view = current_tab.findChild(QPlainTextEdit, "message_view")
            if not message_view:
                message_view = current_tab.findChild(QTextEdit, "message_view")
            results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")

            if message_view and results_stack:
                results_stack.setCurrentIndex(1)
                msg = f"{sql}\n\nQuery returned successfully."
                message_view.setPlainText(msg)

                # Focus the message view
                from PySide6.QtWidgets import QWidget
                header = current_tab.findChild(QWidget, "resultsHeader")
                if header:
                    from PySide6.QtWidgets import QPushButton
                    buttons = header.findChildren(QPushButton)
                    if len(buttons) >= 2:
                        buttons[0].setChecked(False)
                        buttons[1].setChecked(True)

        # Refresh both trees
        self.manager.refresh_object_explorer()
        if conn_data and conn_data.get('db_type') == 'postgres':
            self.manager.schema_loader.load_postgres_schema(conn_data)

    def show_table_properties(self, item_data, table_name):
        if not item_data:
            return

        dialog = TablePropertiesDialog(item_data, table_name, self.manager)
        dialog.show()

    def delete_table(self, item_data, table_name, cascade=False):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')
        table_type = item_data.get('table_type', 'TABLE').upper()
        real_table_name = item_data.get('table_name', table_name)

        is_view = "VIEW" in table_type
        is_mview = "MATERIALIZED VIEW" in table_type
        
        if is_mview:
            object_type = "Materialized View"
        elif is_view:
            object_type = "View"
        else:
            object_type = "Table"
        
        confirm_msg = f"Are you sure you want to delete {object_type.lower()} '{table_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            f'Confirm Delete {object_type}',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            conn = None
            sql = ""
            if db_type == 'postgres':
                conn = db.create_postgres_connection(conn_data)
                schema_quoted = f'"{schema_name}"' if schema_name else ""
                full_name = f'{schema_quoted}."{real_table_name}"' if schema_quoted else f'"{real_table_name}"'
                if is_mview:
                    drop_cmd = "DROP MATERIALIZED VIEW"
                elif is_view:
                    drop_cmd = "DROP VIEW"
                else:
                    drop_cmd = "DROP TABLE"
                    
                cascade_cmd = " CASCADE" if cascade else ""
                sql = f"{drop_cmd} {full_name}{cascade_cmd};"
            elif db_type == 'sqlite':
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
                drop_cmd = "DROP VIEW" if is_view else "DROP TABLE"
                sql = f'{drop_cmd} "{real_table_name}";'
            elif db_type == 'csv':
                folder_path = conn_data.get("db_path")
                file_path = os.path.join(folder_path, real_table_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self._notify_deletion_success(table_name, object_type, f"OS.REMOVE(\"{file_path}\")", conn_data)
                    return
                raise Exception(f"File not found: {file_path}")

            if conn and sql:
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                conn.close()

                self._notify_deletion_success(table_name, object_type, sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete {object_type.lower()}:\n{e}")

    def delete_schema(self, item_data, schema_name, cascade=False):
        """Perform DROP SCHEMA or DROP SCHEMA CASCADE on a PostgreSQL connection."""
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if db_type != 'postgres':
            QMessageBox.warning(self.manager, "Not Supported", "Drop Schema is only supported for PostgreSQL.")
            return

        confirm_msg = f"Are you sure you want to delete schema '{schema_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL objects within the schema (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Schema',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP SCHEMA "{schema_name}"{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(schema_name, "Schema", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete schema:\n{e}")


    def delete_sequence(self, item_data, sequence_name, cascade=False):
        """Perform DROP SEQUENCE or DROP SEQUENCE CASCADE on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')

        confirm_msg = f"Are you sure you want to delete sequence '{sequence_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Sequence',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            schema_quoted = f'"{schema_name}"' if schema_name else ""
            full_name = f'{schema_quoted}."{sequence_name}"' if schema_quoted else f'"{sequence_name}"'
            sql = f'DROP SEQUENCE {full_name}{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(sequence_name, "Sequence", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete sequence:\n{e}")

    def delete_function(self, item_data, function_name, cascade=False):
        """Perform DROP FUNCTION or DROP FUNCTION CASCADE on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')
        table_type = item_data.get('table_type', 'FUNCTION').upper()
        label = table_type.lower().capitalize()

        confirm_msg = f"Are you sure you want to delete {label.lower()} '{function_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            f'Confirm Delete {label}',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            schema_quoted = f'"{schema_name}"' if schema_name else ""
            full_name = f'{schema_quoted}."{function_name}"' if schema_quoted else f'"{function_name}"'
            sql = f'DROP FUNCTION {full_name}{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(function_name, label, sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete {label.lower()}:\n{e}")

    def delete_language(self, item_data, language_name, cascade=False):
        """Perform DROP LANGUAGE or DROP LANGUAGE CASCADE on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')

        confirm_msg = f"Are you sure you want to delete language '{language_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Language',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP LANGUAGE "{language_name}"{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(language_name, "Language", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete language:\n{e}")

    def drop_extension(self, item_data, extension_name, cascade=False):
        """Perform DROP EXTENSION or DROP EXTENSION CASCADE on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')

        confirm_msg = f"Are you sure you want to delete extension '{extension_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Extension',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP EXTENSION "{extension_name}"{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(extension_name, "Extension", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete extension:\n{e}")

    def drop_fdw(self, item_data, cascade=False):
        """Perform DROP FOREIGN DATA WRAPPER on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        fdw_name = item_data.get('fdw_name')

        confirm_msg = f"Are you sure you want to delete Foreign Data Wrapper '{fdw_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete FDW',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP FOREIGN DATA WRAPPER "{fdw_name}"{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(fdw_name, "Foreign Data Wrapper", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete FDW:\n{e}")

    def drop_foreign_server(self, item_data, cascade=False):
        """Perform DROP SERVER on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        server_name = item_data.get('server_name')

        confirm_msg = f"Are you sure you want to delete Foreign Server '{server_name}'?"
        if cascade:
            confirm_msg += "\n\nThis will also delete ALL dependent objects (CASCADE)."
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Foreign Server',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP SERVER "{server_name}"{" CASCADE" if cascade else ""};'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(server_name, "Foreign Server", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete foreign server:\n{e}")

    def drop_user_mapping(self, item_data, cascade=False):
        """Perform DROP USER MAPPING on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        user_name = item_data.get('user_name')
        server_name = item_data.get('server_name')

        confirm_msg = f"Are you sure you want to delete user mapping for '{user_name}' on server '{server_name}'?"
        confirm_msg += "\n\nThis action cannot be undone."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete User Mapping',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            sql = f'DROP USER MAPPING FOR "{user_name}" SERVER "{server_name}";'
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            self._notify_deletion_success(f"{user_name} on {server_name}", "User Mapping", sql, conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete user mapping:\n{e}")



    def _notify_creation_success(self, object_name, object_type, conn_data):
        """Standard notification after successful creation of an object."""
        self.manager.status.showMessage(f"{object_type} '{object_name}' created.", 4000)
        self.manager.status_message_label.setText(f"{object_type} '{object_name}' created.")

        current_tab = self.manager.tab_widget.currentWidget()
        if not current_tab:
            self.manager.add_tab()
            current_tab = self.manager.tab_widget.currentWidget()

        if current_tab:
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QStackedWidget
            message_view = current_tab.findChild(QPlainTextEdit, "message_view")
            if not message_view:
                message_view = current_tab.findChild(QTextEdit, "message_view")
            results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")

            if message_view and results_stack:
                results_stack.setCurrentIndex(1)
                msg = f"CREATE {object_type.upper()}\n\nQuery returned successfully."
                message_view.setPlainText(msg)

                # Focus the message view
                from PySide6.QtWidgets import QWidget
                header = current_tab.findChild(QWidget, "resultsHeader")
                if header:
                    from PySide6.QtWidgets import QPushButton
                    buttons = header.findChildren(QPushButton)
                    if len(buttons) >= 2:
                        buttons[0].setChecked(False)
                        buttons[1].setChecked(True)

        # Refresh both trees
        self.manager.refresh_object_explorer()
        if conn_data and conn_data.get('db_type') == 'postgres':
            self.manager.schema_loader.load_postgres_schema(conn_data)

    def open_create_table_template(self, item_data, table_name=None):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if not conn_data:
            QMessageBox.critical(self.manager, "Error", "Connection data is missing!")
            return

        if db_type == 'postgres':
            try:
                conn = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY nspname")
                schemas = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT current_user")
                current_user = cursor.fetchone()[0]
                conn.close()

                dialog = CreateTableDialog(self.manager, schemas, current_user, db_type="postgres")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_sql_data()

                    cols_sql = []
                    pk_cols = []
                    for col in data['columns']:
                        col_def = f'"{col["name"]}" {col["type"]}'
                        cols_sql.append(col_def)
                        if col['pk']:
                            pk_cols.append(f'"{col["name"]}"')

                    if pk_cols:
                        cols_sql.append(f'PRIMARY KEY ({", ".join(pk_cols)})')

                    sql = f'CREATE TABLE "{data["schema"]}"."{data["name"]}" (\n    {", ".join(cols_sql)}\n);'

                    conn = db.create_postgres_connection(conn_data)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    self._notify_creation_success(data["name"], "Table", conn_data)

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create table:\n{e}")


        elif db_type == 'sqlite':
            try:
                dialog = CreateTableDialog(self.manager, schemas=None, current_user="", db_type="sqlite")

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_sql_data()

                    cols_sql = []
                    for col in data['columns']:
                        pk = "PRIMARY KEY" if col['pk'] else ""
                        cols_sql.append(f'"{col["name"]}" {col["type"]} {pk}')

                    sql = f'CREATE TABLE "{data["name"]}" (\n    {", ".join(cols_sql)}\n);'

                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    if not conn:
                        raise Exception("Could not open SQLite database file.")

                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    self._notify_creation_success(data["name"], "Table", conn_data)

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create SQLite table:\n{e}")

        else:
            QMessageBox.warning(self.manager, "Not Supported", f"Interactive table creation is not supported for {db_type} yet.")

    def open_create_view_template(self, item_data):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if not conn_data:
            QMessageBox.critical(self.manager, "Error", "Connection data is missing!")
            return

        if db_type == 'postgres':
            try:
                conn = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY nspname")
                schemas = [row[0] for row in cursor.fetchall()]
                conn.close()

                dialog = CreateViewDialog(self.manager, schemas, db_type="postgres")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE OR REPLACE VIEW "{data["schema"]}"."{data["name"]}" AS\n{data["definition"]};'

                    conn = db.create_postgres_connection(conn_data)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    self._notify_creation_success(data["name"], "View", conn_data)

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create Postgres view:\n{e}")

        elif db_type == 'sqlite':
            try:
                dialog = CreateViewDialog(self.manager, schemas=None, db_type="sqlite")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE VIEW "{data["name"]}" AS\n{data["definition"]};'

                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    self._notify_creation_success(data["name"], "View", conn_data)

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create SQLite view:\n{e}")

        else:
            QMessageBox.warning(self.manager, "Not Supported", f"Interactive view creation is not supported for {db_type} yet.")


    def open_create_materialized_view_dialog(self, item_data):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if db_type != 'postgres' or not conn_data:
            QMessageBox.warning(self.manager, "Not Supported", "Materialized Views are only supported for PostgreSQL.")
            return

        try:
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY nspname")
            schemas = [row[0] for row in cursor.fetchall()]
            conn.close()

            from dialogs.create_materialized_view_dialog import CreateMaterializedViewDialog
            dialog = CreateMaterializedViewDialog(self.manager, schemas, db_type="postgres")
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                no_data = " WITH NO DATA" if data.get("with_no_data") else ""
                sql = f'CREATE MATERIALIZED VIEW "{data["schema"]}"."{data["name"]}" AS\n{data["definition"]}{no_data};'

                conn = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                conn.close()

                self._notify_creation_success(data["name"], "Materialized View", conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to create Materialized View:\n{e}")

    def refresh_materialized_view(self, item_data, name, concurrently=False):
        if not item_data:
            return

        conn_data = item_data.get('conn_data')
        schema = item_data.get('schema_name', 'public')
        
        try:
            concurrent_str = " CONCURRENTLY" if concurrently else ""
            sql = f'REFRESH MATERIALIZED VIEW{concurrent_str} "{schema}"."{name}";'
            
            self.manager.status.showMessage(f"Refreshing materialized view '{name}'...", 4000)
            
            conn = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()
            
            self.manager.status.showMessage(f"Materialized view '{name}' refreshed successfully.", 4000)
            
            # Show in messages tab
            self._notify_generic_success(name, "Materialized View Refreshed", sql)
            
        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to refresh materialized view:\n{e}")

    def _notify_generic_success(self, object_name, operation, sql):
        """Generic notification for successful operations in the Messages tab."""
        current_tab = self.manager.tab_widget.currentWidget()
        if not current_tab:
            new_tab = self.manager.add_tab()
            current_tab = new_tab

        if current_tab:
            message_view = current_tab.findChild(QPlainTextEdit, "message_view")
            if not message_view:
                message_view = current_tab.findChild(QTextEdit, "message_view")
            results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")

            if message_view and results_stack:
                results_stack.setCurrentIndex(1)
                msg = f"{sql}\n\n{operation} successfully."
                message_view.setPlainText(msg)
                
                # Switch tab buttons style (internal convenience)
                from PySide6.QtWidgets import QWidget
                header = current_tab.findChild(QWidget, "resultsHeader")
                if header:
                    from PySide6.QtWidgets import QPushButton
                    buttons = header.findChildren(QPushButton)
                    if len(buttons) >= 2:
                        buttons[0].setChecked(False)
                        buttons[1].setChecked(True)

    def export_schema_table_rows(self, item_data, table_name):
        if not item_data:
            return

        dialog = ExportDialog(self.manager, f"{table_name}_export.csv")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        export_options = dialog.get_options()
        if not export_options['filename']:
            QMessageBox.warning(self.manager, "No Filename", "Export cancelled. No filename specified.")
            return

        conn_data = item_data['conn_data']
        conn_data['code'] = (conn_data.get('code') or item_data.get('db_type') or '').upper()

        code = conn_data.get('code')

        if code == 'POSTGRES':
            schema_name = item_data.get('schema_name', 'public')
            schema_quoted = f'"{schema_name}"'
            query = f'SELECT * FROM {schema_quoted}.{table_name}'
            object_name = f"{schema_name}.{table_name}"
        else:
            query = f'SELECT * FROM "{table_name}"'
            object_name = table_name

        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]

        def on_data_fetched_for_export(_conn_data, _query, results, columns, _column_specs, row_count, _elapsed_time, _is_select_query):
            self.manager.status_message_label.setText("Data fetched. Starting export process...")
            model = QStandardItemModel()
            model.setColumnCount(len(columns))
            model.setRowCount(len(results))
            model.setHorizontalHeaderLabels(columns)

            for row_idx, row in enumerate(results):
                for col_idx, cell in enumerate(row):
                    model.setItem(row_idx, col_idx, QStandardItem(str(cell)))

            if export_options["delimiter"] == ',':
                export_options["delimiter"] = None

            conn_name = conn_data.get("short_name", conn_data.get("name", "Unknown"))
            conn_id = conn_data.get("id")

            initial_data = {
                "pid": short_id,
                "type": "Export Data",
                "status": "Running",
                "server": conn_name,
                "object": object_name,
                "time_taken": "...",
                "start_time": datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
                "details": f"Exporting {row_count} rows to {os.path.basename(export_options['filename'])}",
                "_conn_id": conn_id,
            }

            signals = ProcessSignals()
            signals.started.connect(self.manager.handle_process_started)
            signals.finished.connect(self.manager.handle_process_finished)
            signals.error.connect(self.manager.handle_process_error)

            self.manager.thread_pool.start(
                RunnableExportFromModel(short_id, model, export_options, signals)
            )

            emit_process_started(signals, short_id, initial_data)

        self.manager.status_message_label.setText(f"Fetching data from {table_name} for export...")

        query_signals = QuerySignals()
        query_runnable = RunnableQuery(conn_data, query, query_signals)

        query_signals.finished.connect(on_data_fetched_for_export)
        query_signals.error.connect(
            lambda conn, q, rc, et, err: self.manager.show_error_popup(
                f"Failed to fetch data for export:\n{err}"
            )
        )

        self.manager.thread_pool.start(query_runnable)

    # =========================================================================
    # Create Schema (PostgreSQL)
    # =========================================================================

    def open_create_schema_dialog(self, item_data):
        """Open a pgAdmin-style dialog to CREATE SCHEMA on a PostgreSQL connection."""
        if not item_data:
            return

        conn_data = item_data.get("conn_data")
        db_type   = item_data.get("db_type", "")

        if db_type != "postgres" or not conn_data:
            QMessageBox.warning(
                self.manager,
                "Not Supported",
                "Create Schema is only supported for PostgreSQL connections.",
            )
            return

        # --- Fetch existing users/roles for the Owner dropdown ---
        existing_roles = []
        cur_user       = ""
        try:
            conn   = db.create_postgres_connection(conn_data)
            cursor = conn.cursor()
            
            # Get current user for defaulting the owner
            cursor.execute("SELECT current_user;")
            cur_user = cursor.fetchone()[0]
            
            # Get all login roles
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolcanlogin ORDER BY rolname;"
            )
            existing_roles = [row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception:
            pass  # Owner field will just be an empty text input or standard dropdown

        # ==================================================================
        # Build dialog
        # ==================================================================
        dialog = QDialog(self.manager)
        dialog.setWindowTitle("Create Schema")
        dialog.setFixedSize(460, 260)
        dialog.setWindowFlags(
            dialog.windowFlags()
            & ~dialog.windowFlags()
            | 0  # reset
        )
        from PySide6.QtCore import Qt
        dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        dialog.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        # --- Widgets ---
        title_lbl = QLabel("Create Schema")
        title_lbl.setObjectName("dialogTitle")

        subtitle_lbl = QLabel(
            f"Create a new schema in <b>{conn_data.get('name', 'database')}</b>."
        )
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        name_input = QLineEdit()
        name_input.setPlaceholderText("my_schema")

        owner_input = QComboBox() if existing_roles else QLineEdit()
        if existing_roles:
            owner_input.addItem("")          # empty = no AUTHORIZATION clause
            owner_input.addItems(existing_roles)
            owner_input.setEditable(True)
            
            # Default to current user if available
            if cur_user and cur_user in existing_roles:
                owner_input.setCurrentText(cur_user)
        else:
            owner_input.setPlaceholderText("(optional) owner role")
            if cur_user:
                owner_input.setText(cur_user)

        if_not_exists_chk = QCheckBox("IF NOT EXISTS  (skip if schema already exists)")

        save_btn   = QPushButton("Create")
        save_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")

        # --- Layout ---
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Name:",  name_input)
        form.addRow("Owner:", owner_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)
        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)
        main_layout.addLayout(form)
        main_layout.addWidget(if_not_exists_chk)
        main_layout.addStretch()
        main_layout.addLayout(btn_row)

        cancel_btn.clicked.connect(dialog.reject)

        def _on_create():
            schema_name = name_input.text().strip()
            if not schema_name:
                QMessageBox.warning(dialog, "Missing Info", "Schema name is required.")
                return

            if isinstance(owner_input, QComboBox):
                owner = owner_input.currentText().strip()
            else:
                owner = owner_input.text().strip()

            if_ne = if_not_exists_chk.isChecked()

            # Build SQL
            clause  = "IF NOT EXISTS " if if_ne else ""
            auth    = f" AUTHORIZATION \"{owner}\"" if owner else ""
            sql     = f'CREATE SCHEMA {clause}"{schema_name}"{auth};'

            try:
                conn   = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                conn.close()

                dialog.accept()

                self.manager.status.showMessage(
                    f"Schema '{schema_name}' created successfully.", 4000
                )
                self.manager.status_message_label.setText(
                    f"Schema '{schema_name}' created."
                )

                # Reload the schema tree
                self.manager.schema_loader.load_postgres_schema(conn_data)

            except Exception as exc:
                QMessageBox.critical(
                    dialog, "Error", f"Failed to create schema:\n{exc}"
                )

        save_btn.clicked.connect(_on_create)
        name_input.returnPressed.connect(_on_create)
        dialog.exec()

    # =========================================================================
    # --- SEARCH & STATISTICS ---
    # =========================================================================

    def open_search_objects_dialog(self, item_data):
        if not item_data:
            return
        conn_data = item_data.get('conn_data')
        dialog = SearchObjectsDialog(self.manager, conn_data, parent=self.manager)
        dialog.show()

    def fetch_search_results(self, conn_data, query_text):
        """Executes a consolidated PostgreSQL search query across system catalogs."""
        conn = db.create_postgres_connection(conn_data)
        if not conn:
            raise Exception("Failed to establish PostgreSQL connection.")
            
        cursor = conn.cursor()
        
        # We use a UNION ALL query to fetch everything in one pass and sort server-side.
        sql = """
        SELECT schema, name, type FROM (
            -- Tables, Views, Sequences, Indexes, Foreign Tables
            SELECT 
                n.nspname AS schema,
                c.relname AS name,
                CASE c.relkind
                    WHEN 'r' THEN 'Table'
                    WHEN 'v' THEN 'View'
                    WHEN 'f' THEN 'Foreign Table'
                    WHEN 'i' THEN 'Index'
                    WHEN 'S' THEN 'Sequence'
                    WHEN 'm' THEN 'Materialized View'
                    ELSE 'Other'
                END AS type
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT LIKE 'pg_%%' 
            AND n.nspname != 'information_schema'
            
            UNION ALL
            
            -- Functions
            SELECT 
                n.nspname AS schema,
                p.proname || '(' || COALESCE(pg_get_function_arguments(p.oid), '') || ')' AS name,
                'Function' AS type
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname NOT LIKE 'pg_%%' 
            AND n.nspname != 'information_schema'
        ) sub
        WHERE name ILIKE %s
        ORDER BY schema, name
        """
        
        try:
            search_pattern = f"%{query_text}%"
            cursor.execute(sql, (search_pattern,))
            results = list(cursor.fetchall())
            
            # DEBUG logging for diagnosing "tuple index out of range"
            if results:
                print(f"DEBUG: Search returned {len(results)} rows.")
                print(f"DEBUG: Sample row (0): {results[0]} (Type: {type(results[0])}, Len: {len(results[0])})")
            
            return results
        except Exception as e:
            print(f"Database search query error: {e}")
            raise
        finally:
            conn.close()

    def open_database_statistics_dialog(self, conn_data):
        """Opens the database statistics dialog."""
        dialog = DatabaseStatisticsDialog(self.manager, conn_data, parent=self.manager)
        dialog.exec()

    def fetch_database_statistics(self, conn_data):
        """Fetches counts and size summary for the database."""
        conn = db.create_postgres_connection(conn_data)
        if not conn:
            return {}
            
        cursor = conn.cursor()
        
        stats = {}
        
        # DB Size
        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
        size_row = cursor.fetchone()
        stats['db_size'] = size_row[0] if size_row else "Unknown"
        
        # Counts
        cursor.execute("""
        SELECT 
            (SELECT count(*) FROM pg_namespace WHERE nspname NOT LIKE 'pg_%%' AND nspname != 'information_schema') as schema_count,
            (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema' AND c.relkind = 'r') as table_count,
            (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema' AND c.relkind = 'v') as view_count,
            (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema' AND c.relkind = 'i') as index_count,
            (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema') as function_count,
            (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema' AND c.relkind = 'S') as sequence_count,
            (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as active_sessions;
        """)
        row = cursor.fetchone()
        if row:
            stats.update({
                'schema_count': row[0],
                'table_count': row[1],
                'view_count': row[2],
                'index_count': row[3],
                'function_count': row[4],
                'sequence_count': row[5],
                'active_sessions': row[6]
            })
        else:
            stats.update({k: 0 for k in ['schema_count', 'table_count', 'view_count', 'index_count', 'function_count', 'sequence_count', 'active_sessions']})
        
        conn.close()
        return stats

    def navigate_to_object(self, schema, name, obj_type):
        """
        Navigates to the specified object in the Schema Tree.
        This handles expanding nodes to reveal the target.
        """
        tree = self.manager.schema_tree
        model = self.manager.schema_model
        
        if not tree or not model:
            return

        # 1. Find the "Schemas" root node
        schemas_root = None
        for i in range(model.rowCount()):
            item = model.item(i)
            if item and item.text() == "Schemas":
                schemas_root = item
                break
        
        if not schemas_root:
            return
        
        # Expand "Schemas"
        tree.expand(schemas_root.index())
        
        # 2. Find the specific Schema
        schema_item = None
        for i in range(schemas_root.rowCount()):
            item = schemas_root.child(i)
            if item and item.text() == schema:
                schema_item = item
                break
        
        if not schema_item:
            return
        
        # Expand Schema
        tree.expand(schema_item.index())
        
        # 3. Handle object groups (if it's not a root-level object)
        # We need to map object type to the group name (Tables, Views, etc.)
        group_map = {
            "Table": "Tables",
            "View": "Views",
            "Materialized View": "Views",
            "Foreign Table": "Foreign Tables",
            "Function": "Functions",
            "Sequence": "Sequences",
            "Trigger Function": "Trigger Functions",
        }
        
        target_group = group_map.get(obj_type)
        if not target_group:
            return

        # Check if we need to load children (if they are still "Loading...")
        if schema_item.rowCount() == 1 and schema_item.child(0).text() == "Loading...":
            self.manager.schema_loader.load_tables_on_expand(schema_item.index())

        # Find the group node
        group_node = None
        for i in range(schema_item.rowCount()):
            item = schema_item.child(i)
            if item and item.text() == target_group:
                group_node = item
                break
        
        if not group_node:
            return
            
        # Expand group
        tree.expand(group_node.index())
        
        # Check if group needs loading
        if group_node.rowCount() == 1 and group_node.child(0).text() == "Loading...":
            self.manager.schema_loader.load_tables_on_expand(group_node.index())

        # 4. Find the object itself
        target_name = name
        
        target_item = None
        for i in range(group_node.rowCount()):
            item = group_node.child(i)
            if item and item.text() == target_name:
                target_item = item
                break
        
        if target_item:
            tree.setCurrentIndex(target_item.index())
            tree.scrollTo(target_item.index())
            self.manager.main_window.activateWindow()
    def open_backup_dialog(self, item_data):
        if not item_data:
            return
            
        db_type = item_data.get("db_type")
        if db_type not in ("postgres", "sqlite"):
            QMessageBox.information(self.manager.main_window, "Not Supported", f"Backup is currently only supported for PostgreSQL and SQLite. (Database type: {db_type})")
            return
            
        dialog = BackupDialog(self.manager.main_window, item_data)
        if dialog.exec():
            options = dialog.get_options()
            conn_data = item_data.get("conn_data", {})

            if db_type == "postgres":
                # Build command
                binary = self.backup_engine.get_pg_binary("pg_dump")
                
                # Handle granularity (database, schema, table)
                granularity = options.get("object_type", "database")
                object_name = options.get("display_name") or item_data.get("table_name") or item_data.get("schema_name")
                schema_name = item_data.get("schema_name")
                
                args = self.backup_engine.build_pg_dump_args(
                    conn_data, 
                    options["filename"],
                    format=options.get("format", "custom"),
                    granularity=granularity,
                    object_name=object_name,
                    schema_name=schema_name,
                    options=options
                )
                
                # Start Worker
                metadata = {
                    "pid": "BACKUP",
                    "type": "Backup Database",
                    "status": "Running",
                    "server": conn_data.get("short_name", "Unknown"),
                    "object": object_name or conn_data.get("database"),
                    "details": f"Backing up to {os.path.basename(options['filename'])}",
                    "_conn_id": conn_data.get("id")
                }
                
                # Environment for password handling
                env = self.backup_engine.get_pg_environment(conn_data)
                
                worker = ProcessWorker(binary, args, metadata=metadata, env=env)
                
                # Connect signals
                worker.signals.started.connect(self.manager.main_window.handle_process_started)
                worker.signals.output.connect(self.manager.main_window.handle_process_output)
                worker.signals.finished.connect(self.manager.main_window.handle_process_finished)
                worker.signals.error.connect(self.manager.main_window.handle_process_error)
                
                # Add to main window so it doesn't get GC'd
                if not hasattr(self.manager.main_window, "_active_processes"):
                    self.manager.main_window._active_processes = {}
                self.manager.main_window._active_processes[worker.process_id] = worker
                
                worker.run()
            
            elif db_type == "sqlite":
                db_path = conn_data.get("db_path")
                if not db_path:
                    QMessageBox.critical(self.manager.main_window, "Error", "SQLite database path not found.")
                    return
                
                process_id = f"BACKUP_SQLITE_{int(time.time())}"
                metadata = {
                    "pid": process_id,
                    "type": "Backup SQLite",
                    "status": "Running",
                    "server": os.path.basename(db_path),
                    "object": "Full Database",
                    "details": f"Copying to {os.path.basename(options['filename'])}",
                }
                
                from workers.signals import ProcessSignals
                signals = ProcessSignals()
                signals.started.connect(self.manager.main_window.handle_process_started)
                signals.finished.connect(self.manager.main_window.handle_process_finished)
                signals.error.connect(self.manager.main_window.handle_process_error)
                
                worker = RunnableSqliteBackup(process_id, db_path, options["filename"], signals)
                
                # Fake a "started" signal for the UI
                from workers.signals import emit_process_started
                emit_process_started(signals, process_id, metadata)
                
                self.manager.main_window.thread_pool.start(worker)

    def open_restore_dialog(self, item_data):
        if not item_data:
            return
            
        db_type = item_data.get("db_type")
        if db_type not in ("postgres", "sqlite"):
            QMessageBox.information(self.manager.main_window, "Not Supported", f"Restore is currently only supported for PostgreSQL and SQLite. (Database type: {db_type})")
            return
            
        dialog = RestoreDialog(self.manager.main_window, item_data)
        if dialog.exec():
            options = dialog.get_options()
            # Use the target connection selected in the dialog, or fall back to the item's connection
            conn_data = options.get("target_conn_data") or item_data.get("conn_data", {})
            
            if not conn_data:
                 QMessageBox.critical(self.manager.main_window, "Error", "No target connection found for restore.")
                 return

            if db_type == "postgres":
                # Build command
                binary = self.restore_engine.get_pg_binary("pg_restore")
                
                args = self.restore_engine.build_pg_restore_args(
                    conn_data, 
                    options["filename"],
                    format=options.get("format", "custom"),
                    options=options
                )
                
                # Start Worker
                metadata = {
                    "pid": "RESTORE",
                    "type": "Restore Database",
                    "status": "Running",
                    "server": conn_data.get("short_name", "Unknown"),
                    "object": item_data.get("table_name") or item_data.get("schema_name") or conn_data.get("database"),
                    "details": f"Restoring from {os.path.basename(options['filename'])}",
                    "_conn_id": conn_data.get("id")
                }
                
                # Environment for password handling
                env = self.restore_engine.get_pg_environment(conn_data)
                
                worker = ProcessWorker(binary, args, metadata=metadata, env=env)
                
                # Connect signals
                worker.signals.started.connect(self.manager.main_window.handle_process_started)
                worker.signals.output.connect(self.manager.main_window.handle_process_output)
                worker.signals.finished.connect(self.manager.main_window.handle_process_finished)
                worker.signals.error.connect(self.manager.main_window.handle_process_error)
                
                # Add to main window so it doesn't get GC'd
                if not hasattr(self.manager.main_window, "_active_processes"):
                    self.manager.main_window._active_processes = {}
                self.manager.main_window._active_processes[worker.process_id] = worker
                
                worker.run()

            elif db_type == "sqlite":
                db_path = conn_data.get("db_path")
                if not db_path:
                    QMessageBox.critical(self.manager.main_window, "Error", "SQLite database path not found.")
                    return
                
                process_id = f"RESTORE_SQLITE_{int(time.time())}"
                metadata = {
                    "pid": process_id,
                    "type": "Restore SQLite",
                    "status": "Running",
                    "server": os.path.basename(db_path),
                    "object": "Full Database",
                    "details": f"Restoring from {os.path.basename(options['filename'])}",
                }
                
                from workers.signals import ProcessSignals
                signals = ProcessSignals()
                signals.started.connect(self.manager.main_window.handle_process_started)
                signals.finished.connect(self.manager.main_window.handle_process_finished)
                signals.error.connect(self.manager.main_window.handle_process_error)
                
                worker = RunnableSqliteRestore(process_id, options["filename"], db_path, signals)
                
                # Fake a "started" signal for the UI
                from workers.signals import emit_process_started
                emit_process_started(signals, process_id, metadata)
                
                self.manager.main_window.thread_pool.start(worker)
