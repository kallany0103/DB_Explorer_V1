import datetime
import os
import uuid

import db
import psycopg2
# from PyQt6.QtGui import QStandardItemModel, QStandardItem
# from PyQt6.QtWidgets import (
#     QApplication,
#     QComboBox,
#     QDialog,
#     QInputDialog,
#     QMessageBox,
#     QPushButton,
#     QPlainTextEdit,
#     QStackedWidget,
#     QTextEdit,
#     QWidget,
# )

from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStackedWidget,
    QTextEdit,
    QWidget,
)

from dialogs import CreateTableDialog, CreateViewDialog, ExportDialog, TablePropertiesDialog
from workers.signals import ProcessSignals, QuerySignals, emit_process_started
from workers.workers import RunnableExportFromModel, RunnableQuery


class ConnectionActions:
    def __init__(self, manager):
        self.manager = manager

    def count_table_rows(self, item_data, table_name):
        if not item_data:
            return

        conn_data = dict(item_data.get('conn_data', {}))
        db_type = item_data.get('db_type')
        conn_data['code'] = (conn_data.get('code') or db_type or '').upper()

        if db_type == 'postgres':
            query = f'SELECT COUNT(*) FROM "{item_data.get("schema_name")}"."{table_name}";'
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
            lambda cd, q, res, cols, rc, et, isq: results_manager.handle_query_result(
                current_tab, cd, q, res, cols, rc, et, isq
            )
        )
        signals.error.connect(self.handle_count_error)
        self.manager.thread_pool.start(runnable)

    def handle_count_error(self, error_message):
        self.manager.notification_manager.show_message(
            f"Error: {error_message}", is_error=True)
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
            new_tab.table_name = f'"{schema}"."{table_name}"'
            query = f'SELECT * FROM "{schema}"."{table_name}";'
        elif code == 'SQLITE':
            new_tab.table_name = f'"{table_name}"'
            query = f'SELECT * FROM "{table_name}";'
        elif code == 'CSV':
            new_tab.table_name = f'[{table_name}]'
            query = f'SELECT * FROM "{table_name}";'
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

    def create_fdw_template(self, item_data):
        sql = "CREATE FOREIGN DATA WRAPPER fdw_name\n    HANDLER handler_function\n    VALIDATOR validator_function;"
        self.manager.script_generator.open_script_in_editor(item_data, sql)

    def create_foreign_server_template(self, item_data):
        fdw_name = item_data.get('fdw_name', 'fdw_name')
        sql = f"CREATE SERVER server_name\n    FOREIGN DATA WRAPPER {fdw_name}\n    OPTIONS (host '127.0.0.1', port '5432', dbname 'remote_db');"
        self.manager.script_generator.open_script_in_editor(item_data, sql)

    def create_user_mapping_template(self, item_data):
        srv_name = item_data.get('server_name', 'server_name')
        sql = f"CREATE USER MAPPING FOR current_user\n    SERVER {srv_name}\n    OPTIONS (user 'remote_user', password 'password');"
        self.manager.script_generator.open_script_in_editor(item_data, sql)

    def import_foreign_schema_dialog(self, item_data):
        schema_name = item_data.get('schema_name', 'public')
        sql = f"IMPORT FOREIGN SCHEMA remote_schema\n    FROM SERVER foreign_server\n    INTO \"{schema_name}\";"
        self.manager.script_generator.open_script_in_editor(item_data, sql)

    def show_table_properties(self, item_data, table_name):
        if not item_data:
            return

        dialog = TablePropertiesDialog(item_data, table_name, self.manager)
        dialog.show()

    def execute_simple_sql(self, item_data, sql):
        conn_data = item_data.get('conn_data')
        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(sql)
            self.manager.status.showMessage("Operation successful.", 3000)
            self.manager.refresh_object_explorer()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self.manager, "SQL Error", str(e))

    def delete_table(self, item_data, table_name):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')
        table_type = item_data.get('table_type', 'TABLE').upper()
        real_table_name = item_data.get('table_name', table_name)

        is_view = "VIEW" in table_type
        object_type = "View" if is_view else "Table"

        reply = QMessageBox.question(
            self.manager,
            f'Confirm Delete {object_type}',
            f"Are you sure you want to delete {object_type.lower()} '{table_name}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            conn = None
            sql = ""
            if db_type == 'postgres':
                conn = db.create_postgres_connection(conn_data)
                full_name = f'"{schema_name}"."{real_table_name}"' if schema_name else f'"{real_table_name}"'
                drop_cmd = "DROP VIEW" if is_view else "DROP TABLE"
                sql = f"{drop_cmd} {full_name};"
            elif db_type == 'sqlite':
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
                drop_cmd = "DROP VIEW" if is_view else "DROP TABLE"
                sql = f'{drop_cmd} "{real_table_name}";'
            elif db_type == 'csv':
                folder_path = conn_data.get("db_path")
                file_path = os.path.join(folder_path, real_table_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    success_msg = f"CSV file '{table_name}' deleted successfully."
                    self.manager.status.showMessage(success_msg, 5000)
                    QMessageBox.information(self.manager, "Success", success_msg)

                    current_tab = self.manager.tab_widget.currentWidget()
                    if current_tab:
                        message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                        if not message_view:
                            message_view = current_tab.findChild(QTextEdit, "message_view")
                        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                        if message_view and results_stack:
                            results_stack.setCurrentIndex(1)
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            msg = f'[{timestamp}]  OS.REMOVE("{file_path}")'
                            message_view.appendPlainText(msg) if hasattr(message_view, 'appendPlainText') else message_view.append(msg)
                            message_view.appendPlainText(f"  {success_msg}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  {success_msg}")

                            header = current_tab.findChild(QWidget, "resultsHeader")
                            if header:
                                buttons = header.findChildren(QPushButton)
                                if len(buttons) >= 2:
                                    buttons[0].setChecked(False)
                                    buttons[1].setChecked(True)

                    self.manager.refresh_object_explorer()
                    return
                raise Exception(f"File not found: {file_path}")

            if conn and sql:
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                conn.close()

                success_msg = f"{object_type} '{table_name}' deleted successfully."
                self.manager.status.showMessage(success_msg, 5000)
                QMessageBox.information(self.manager, "Success", success_msg)

                current_tab = self.manager.tab_widget.currentWidget()
                if current_tab:
                    message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                    if not message_view:
                        message_view = current_tab.findChild(QTextEdit, "message_view")
                    results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                    if message_view and results_stack:
                        results_stack.setCurrentIndex(1)
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message_view.appendPlainText(f"[{timestamp}]  {sql}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"[{timestamp}]  {sql}")
                        message_view.appendPlainText(f"  {success_msg}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  {success_msg}")

                        header = current_tab.findChild(QWidget, "resultsHeader")
                        if header:
                            buttons = header.findChildren(QPushButton)
                            if len(buttons) >= 2:
                                buttons[0].setChecked(False)
                                buttons[1].setChecked(True)

                self.manager.refresh_object_explorer()

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete {object_type.lower()}:\n{e}")

    def open_create_table_template(self, item_data, table_name=None):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if not conn_data:
            QMessageBox.critical(self.manager, "Error", "Connection data is missing!")
            return

        def log_success_to_view(created_table_name):
            current_tab = self.manager.tab_widget.currentWidget()

            if not current_tab:
                self.manager.add_tab()
                current_tab = self.manager.tab_widget.currentWidget()

            if current_tab:
                message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                if not message_view:
                    message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
            else:
                message_view = None
                results_stack = None

            if message_view and results_stack:
                results_stack.setCurrentIndex(1)

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                msg = f'[{timestamp}]  CREATE TABLE "{created_table_name}"'
                message_view.appendPlainText(msg) if hasattr(message_view, 'appendPlainText') else message_view.append(msg)
                msg2 = "  Table created successfully."
                message_view.appendPlainText(msg2) if hasattr(message_view, 'appendPlainText') else message_view.append(msg2)

                sb = message_view.verticalScrollBar()
                sb.setValue(sb.maximum())

                message_view.repaint()
                QApplication.processEvents()

                header = current_tab.findChild(QWidget, "resultsHeader")
                if header:
                    buttons = header.findChildren(QPushButton)
                    if len(buttons) >= 2:
                        buttons[0].setChecked(False)
                        buttons[1].setChecked(True)

                results_info_bar = current_tab.findChild(QWidget, "resultsInfoBar")
                if results_info_bar:
                    results_info_bar.hide()
                    self.manager.status_message_label.setText(f"Table '{created_table_name}' created successfully.")
                else:
                    QMessageBox.information(self.manager, "Success", f"Table '{created_table_name}' created successfully!")

        if db_type == 'postgres':
            try:
                conn = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'")
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

                    log_success_to_view(data["name"])

                    self.manager.status.showMessage("Refreshing schema...", 2000)
                    self.manager.refresh_object_explorer()

            except Exception as e:
                QMessageBox.critical(self.manager, "Connection Error", f"Invalid Connection or SQL: {e}")

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

                    log_success_to_view(data["name"])

                    self.manager.status.showMessage("Refreshing schema...", 2000)
                    self.manager.refresh_object_explorer()

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

        def log_success_to_view(view_name, sql):
            current_tab = self.manager.tab_widget.currentWidget()
            if not current_tab:
                self.manager.add_tab()
                current_tab = self.manager.tab_widget.currentWidget()

            if current_tab:
                message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                if not message_view:
                    message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
            else:
                message_view = None
                results_stack = None

            if message_view and results_stack:
                results_stack.setCurrentIndex(1)
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message_view.appendPlainText(f"[{timestamp}]  {sql}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"[{timestamp}]  {sql}")
                message_view.appendPlainText(f"  View '{view_name}' created successfully.") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  View '{view_name}' created successfully.")

                sb = message_view.verticalScrollBar()
                sb.setValue(sb.maximum())

                header = current_tab.findChild(QWidget, "resultsHeader")
                if header:
                    buttons = header.findChildren(QPushButton)
                    if len(buttons) >= 2:
                        buttons[0].setChecked(False)
                        buttons[1].setChecked(True)

                self.manager.status_message_label.setText(f"View '{view_name}' created successfully.")

        if db_type == 'postgres':
            try:
                conn = db.create_postgres_connection(conn_data)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'")
                schemas = [row[0] for row in cursor.fetchall()]
                conn.close()

                dialog = CreateViewDialog(self.manager, schemas)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE OR REPLACE VIEW "{data["schema"]}"."{data["name"]}" AS\n{data["definition"]};'

                    conn = db.create_postgres_connection(conn_data)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    log_success_to_view(data["name"], sql)
                    self.manager.refresh_object_explorer()

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create Postgres view:\n{e}")

        elif db_type == 'sqlite':
            try:
                dialog = CreateViewDialog(self.manager, schemas=None)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE VIEW "{data["name"]}" AS\n{data["definition"]};'

                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    log_success_to_view(data["name"], sql)
                    self.manager.refresh_object_explorer()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create SQLite view:\n{e}")

        else:
            QMessageBox.warning(self.manager, "Not Supported", f"Interactive view creation is not supported for {db_type} yet.")

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
            schema_name = item_data.get("schema_name", "public")
            query = f'SELECT * FROM "{schema_name}"."{table_name}"'
            object_name = f"{schema_name}.{table_name}"
        else:
            query = f'SELECT * FROM "{table_name}"'
            object_name = table_name

        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]

        def on_data_fetched_for_export(_conn_data, _query, results, columns, row_count, _elapsed_time, _is_select_query):
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

    def drop_fdw(self, item_data):
        fdw_name = item_data.get('fdw_name')
        if QMessageBox.question(
            self.manager,
            "Drop FDW",
            f"Are you sure you want to drop Foreign Data Wrapper '{fdw_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.execute_simple_sql(item_data, f"DROP FOREIGN DATA WRAPPER {fdw_name} CASCADE;")

    def drop_foreign_server(self, item_data):
        srv_name = item_data.get('server_name')
        if QMessageBox.question(
            self.manager,
            "Drop Server",
            f"Are you sure you want to drop Foreign Server '{srv_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.execute_simple_sql(item_data, f"DROP SERVER {srv_name} CASCADE;")

    def drop_user_mapping(self, item_data):
        user_name = item_data.get('user_name')
        srv_name = item_data.get('server_name')
        if QMessageBox.question(
            self.manager,
            "Drop User Mapping",
            f"Are you sure you want to drop User Mapping for '{user_name}' on server '{srv_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.execute_simple_sql(item_data, f'DROP USER MAPPING FOR "{user_name}" SERVER {srv_name};')

    def delete_sequence(self, item_data, seq_name):
        if not item_data:
            return
        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')

        reply = QMessageBox.question(
            self.manager,
            'Confirm Delete Sequence',
            f"Are you sure you want to delete sequence '{seq_name}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
            full_name = f'"{schema_name}"."{seq_name}"' if schema_name else f'"{seq_name}"'
            sql = f"DROP SEQUENCE {full_name};"

            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            conn.close()

            success_msg = f"Sequence '{seq_name}' deleted successfully."
            self.manager.status.showMessage(success_msg, 5000)

            current_tab = self.manager.tab_widget.currentWidget()
            if current_tab:
                message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                if not message_view:
                    message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                if message_view and results_stack:
                    results_stack.setCurrentIndex(1)
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message_view.appendPlainText(f"[{timestamp}]  {sql}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"[{timestamp}]  {sql}")
                    message_view.appendPlainText(f"  {success_msg}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  {success_msg}")

            self.manager.load_postgres_schema(conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete sequence:\n{e}")

    def delete_function(self, item_data, func_name):
        schema = item_data.get('schema_name')
        msg = f"Are you sure you want to drop function {schema}.{func_name}?"
        if QMessageBox.question(
            self.manager,
            "Drop Function",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            sql = f"DROP FUNCTION {schema}.{func_name} CASCADE;"
            self.execute_simple_sql(item_data, sql)

    def delete_language(self, item_data, lan_name):
        msg = f"Are you sure you want to drop language {lan_name}?"
        if QMessageBox.question(
            self.manager,
            "Drop Language",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            sql = f"DROP LANGUAGE {lan_name} CASCADE;"
            self.execute_simple_sql(item_data, sql)

    def drop_extension(self, item_data, ext_name, cascade=False):
        if not item_data:
            return
        conn_data = item_data.get('conn_data')

        msg = f"Are you sure you want to drop extension '{ext_name}'?"
        if cascade:
            msg += "\nThis will also drop all objects that depend on it."

        reply = QMessageBox.question(
            self.manager,
            'Confirm Drop Extension',
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.No:
            return

        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
            cursor = conn.cursor()
            sql = f'DROP EXTENSION "{ext_name}"'
            if cascade:
                sql += " CASCADE"
            sql += ";"

            cursor.execute(sql)
            conn.commit()
            conn.close()

            success_msg = f"Extension '{ext_name}' dropped successfully."
            self.manager.status.showMessage(success_msg, 5000)

            current_tab = self.manager.tab_widget.currentWidget()
            if current_tab:
                message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                if not message_view:
                    message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                if message_view and results_stack:
                    results_stack.setCurrentIndex(1)
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message_view.appendPlainText(f"[{timestamp}]  {sql}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"[{timestamp}]  {sql}")
                    message_view.appendPlainText(f"  {success_msg}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  {success_msg}")

            self.manager.load_postgres_schema(conn_data)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to drop extension:\n{e}")

    def create_extension_dialog(self, item_data):
        if not item_data:
            return
        conn_data = item_data.get('conn_data')

        ext_name, ok = QInputDialog.getText(self.manager, "Create Extension", "Extension name:")
        if ok and ext_name:
            try:
                conn = psycopg2.connect(
                    host=conn_data.get("host"),
                    port=conn_data.get("port"),
                    database=conn_data.get("database"),
                    user=conn_data.get("user"),
                    password=conn_data.get("password")
                )
                cursor = conn.cursor()
                sql = f'CREATE EXTENSION "{ext_name}";'
                cursor.execute(sql)
                conn.commit()
                conn.close()

                success_msg = f"Extension '{ext_name}' created successfully."
                self.manager.status.showMessage(success_msg, 5000)

                current_tab = self.manager.tab_widget.currentWidget()
                if current_tab:
                    message_view = current_tab.findChild(QPlainTextEdit, "message_view")
                    if not message_view:
                        message_view = current_tab.findChild(QTextEdit, "message_view")
                    results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                    if message_view and results_stack:
                        results_stack.setCurrentIndex(1)
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message_view.appendPlainText(f"[{timestamp}]  {sql}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"[{timestamp}]  {sql}")
                        message_view.appendPlainText(f"  {success_msg}") if hasattr(message_view, 'appendPlainText') else message_view.append(f"  {success_msg}")

                self.manager.load_postgres_schema(conn_data)

            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to create extension:\n{e}")
