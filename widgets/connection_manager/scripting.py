import sqlite3 as sqlite
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QComboBox, QPlainTextEdit
from widgets.worksheet.code_editor import CodeEditor
from ui.components import LoadingOverlay, ToastNotification
from workers.connection_workers import TableScriptWorker
import db
from db.oracle_utils import (
    generate_oracle_table_ddl,
    generate_oracle_insert_script,
    generate_oracle_update_script,
)
from db.postgres_utils import (
    generate_postgres_table_ddl,
    generate_postgres_insert_script,
    generate_postgres_update_script,
)


class ScriptGenerator:
    def __init__(self, manager):
        self.manager = manager
        self._active_workers: set = set()

    def open_script_in_editor(self, item_data, sql):
        if not item_data:
            return

        conn_data = item_data.get("conn_data")
        new_tab = self.manager.add_tab()
        if not new_tab:
            return

        query_editor = new_tab.findChild(CodeEditor, "query_editor")
        if not query_editor:
            query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")

        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        if db_combo_box and conn_data:
            for i in range(db_combo_box.count()):
                data = db_combo_box.itemData(i)
                if data and data.get('id') == conn_data.get('id'):
                    db_combo_box.setCurrentIndex(i)
                    break

        if query_editor:
            query_editor.setPlainText(sql)
            query_editor.setFocus()

        self.manager.tab_widget.setCurrentWidget(new_tab)

    def _run_script_task_async(self, item_data, action_name, target_name, task_fn, *args, **kwargs):
        if not item_data:
            return

        conn_data = item_data.get("conn_data")
        if conn_data and isinstance(conn_data, dict) and str(conn_data.get("host", "")).strip().lower() == "localhost":
            conn_data = dict(conn_data)
            conn_data["host"] = "127.0.0.1"
            item_data = dict(item_data)
            item_data["conn_data"] = conn_data
        new_tab = self.manager.add_tab()
        if not new_tab:
            return

        query_editor = new_tab.findChild(CodeEditor, "query_editor")
        if not query_editor:
            query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")

        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")
        if db_combo_box and conn_data:
            for i in range(db_combo_box.count()):
                data = db_combo_box.itemData(i)
                if data and data.get("id") == conn_data.get("id"):
                    db_combo_box.setCurrentIndex(i)
                    break

        self.manager.tab_widget.setCurrentWidget(new_tab)

        overlay = LoadingOverlay(new_tab, label=f"Generating {action_name} for {target_name}…")
        overlay.show_overlay()

        worker = TableScriptWorker(task_fn, *args, **kwargs)
        self._active_workers.add(worker)

        def on_finished(sql_text: str):
            self._active_workers.discard(worker)
            try:
                overlay.hide_overlay()
                overlay.deleteLater()
            except RuntimeError:
                pass
            try:
                if query_editor:
                    query_editor.setPlainText(sql_text)
                    query_editor.setFocus()
            except RuntimeError:
                pass

        def on_error(err_msg: str):
            self._active_workers.discard(worker)
            try:
                overlay.hide_overlay()
                overlay.deleteLater()
            except RuntimeError:
                pass
            try:
                ToastNotification.show_toast(
                    self.manager,
                    f"Could not generate {action_name}: {err_msg}",
                    kind="error",
                )
            except RuntimeError:
                pass

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)

        thread_pool = getattr(self.manager, "thread_pool", None) or QThreadPool.globalInstance()
        thread_pool.start(worker)

    def script_table_as_create(self, item_data, table_name):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')

        if db_type == 'oracle':
            schema_name = item_data.get('schema_name') or conn_data.get('user', '')
            obj_type = item_data.get('table_type', 'TABLE')
            self._run_script_task_async(
                item_data,
                "CREATE script",
                table_name,
                generate_oracle_table_ddl,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
                obj_type=obj_type,
            )
            return

        if db_type == 'postgres':
            schema_name = item_data.get('schema_name') or 'public'
            obj_type = item_data.get('table_type', 'TABLE')
            self._run_script_task_async(
                item_data,
                "CREATE script",
                table_name,
                generate_postgres_table_ddl,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
                obj_type=obj_type,
            )
            return

        sql_script = ""

        if db_type == 'sqlite':
            try:
                conn = sqlite.connect(conn_data.get('db_path'))
                cursor = conn.cursor()
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                row = cursor.fetchone()
                if row:
                    sql_script = row[0] + ";"
                conn.close()
            except Exception as e:
                ToastNotification.show_toast(self.manager, f"Could not generate SQLite script: {e}", kind="error")
                return

        if sql_script:
            self.open_script_in_editor(item_data, sql_script)

    def script_table_as_insert(self, item_data, table_name):
        if not item_data:
            return
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data') or {}
        schema_name = item_data.get('schema_name') or (conn_data.get('user', '') if db_type == 'oracle' else 'public')

        if db_type == 'oracle':
            self._run_script_task_async(
                item_data,
                "INSERT script",
                table_name,
                generate_oracle_insert_script,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
            )
            return

        if db_type == 'postgres':
            self._run_script_task_async(
                item_data,
                "INSERT script",
                table_name,
                generate_postgres_insert_script,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
            )
            return

        sql = f'INSERT INTO {table_name} (\n    -- column1, column2, ...\n)\nVALUES (\n    -- value1, value2, ...\n);'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_update(self, item_data, table_name):
        if not item_data:
            return
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data') or {}
        schema_name = item_data.get('schema_name') or (conn_data.get('user', '') if db_type == 'oracle' else 'public')

        if db_type == 'oracle':
            self._run_script_task_async(
                item_data,
                "UPDATE script",
                table_name,
                generate_oracle_update_script,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
            )
            return

        if db_type == 'postgres':
            self._run_script_task_async(
                item_data,
                "UPDATE script",
                table_name,
                generate_postgres_update_script,
                conn_data,
                schema_name=schema_name,
                table_name=table_name,
            )
            return

        sql = f'UPDATE {table_name}\nSET \n    -- column1 = value1,\n    -- column2 = value2\nWHERE <condition>;'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_delete(self, item_data, table_name):
        if not item_data:
            return
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data') or {}
        schema_name = item_data.get('schema_name') or (conn_data.get('user', '') if db_type == 'oracle' else 'public')
        if db_type in ('postgres', 'oracle') and schema_name:
            sql = f'DELETE FROM {schema_name}.{table_name}\nWHERE <condition>;'
        else:
            sql = f'DELETE FROM {table_name}\nWHERE <condition>;'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_select(self, item_data, table_name):
        if not item_data:
            return
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data') or {}
        schema_name = item_data.get('schema_name') or (conn_data.get('user', '') if db_type == 'oracle' else 'public')
        if db_type in ('postgres', 'oracle') and schema_name:
            sql = f'SELECT * FROM {schema_name}.{table_name};'
        else:
            sql = f'SELECT * FROM {table_name};'
        self.open_script_in_editor(item_data, sql)

    def script_sequence_as_create(self, item_data, seq_name):
        conn_data = item_data.get('conn_data')
        try:
            conn = db.get_pooled_postgres_connection(
                conn_data,
                application_name=f"Universal SQL Client (Scripting) - {conn_data.get('database', 'postgres')}",
                use_pool=True
            )
            if not conn:
                raise Exception("Failed to establish database connection")
            cursor = conn.cursor()
            schema_name = item_data.get('schema_name', 'public')
            cursor.execute(
                "SELECT 'CREATE SEQUENCE ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || ';' FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = %s AND n.nspname = %s;",
                (seq_name, schema_name),
            )
            res = cursor.fetchone()
            if res:
                self.open_script_in_editor(item_data, res[0])
            db.return_pooled_postgres_connection(conn_data, conn=conn)
        except Exception as e:
            ToastNotification.show_toast(self.manager, f"Failed to script sequence: {e}", kind="error")

    def script_function_as_create(self, item_data, func_name):
        conn_data = item_data.get('conn_data')
        try:
            conn = db.get_pooled_postgres_connection(
                conn_data,
                application_name=f"Universal SQL Client (Scripting) - {conn_data.get('database', 'postgres')}",
                use_pool=True
            )
            if not conn:
                raise Exception("Failed to establish database connection")
            cursor = conn.cursor()
            schema = item_data.get('schema_name')
            query = """
                SELECT pg_get_functiondef(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = %s
                AND p.proname || '(' || pg_get_function_arguments(p.oid) || ')' = %s;
            """
            cursor.execute(query, (schema, func_name))
            res = cursor.fetchone()
            if res:
                sql = res[0]
                if not sql.strip().upper().startswith("CREATE OR REPLACE"):
                    sql = sql.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION")
                self.open_script_in_editor(item_data, sql + ";")
            else:
                ToastNotification.show_toast(self.manager, "Could not find function definition.", kind="warning")
            db.return_pooled_postgres_connection(conn_data, conn=conn)
        except Exception as e:
            ToastNotification.show_toast(self.manager, f"Failed to script function: {e}", kind="error")

    def script_language_as_create(self, item_data, lan_name):
        sql = f"""-- Create Language Script
-- Note: Most standard languages (plpgsql) are already installed.
CREATE LANGUAGE {lan_name};"""
        self.open_script_in_editor(item_data, sql)

    def open_create_function_template(self, item_data):
        schema = item_data.get('schema_name', 'public')
        sql = f"""-- Create Function Template
CREATE OR REPLACE FUNCTION {schema}.new_function(param1 integer, param2 text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    -- Your logic here
END;
$$;"""
        self.open_script_in_editor(item_data, sql)

    def open_create_trigger_function_template(self, item_data):
        schema = item_data.get('schema_name', 'public')
        sql = f"""-- Create Trigger Function Template
CREATE OR REPLACE FUNCTION {schema}.new_trigger_function()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Your trigger logic here (e.g., NEW.field := value;)
    RETURN NEW;
END;
$$;"""
        self.open_script_in_editor(item_data, sql)

    def script_schema_as_create(self, item_data, schema_name):
        sql = f"-- Create Schema Script\nCREATE SCHEMA IF NOT EXISTS \"{schema_name}\";"
        self.open_script_in_editor(item_data, sql)

    def script_extension_as_create(self, item_data, ext_name):
        sql = f"-- Create Extension Script\nCREATE EXTENSION IF NOT EXISTS \"{ext_name}\";"
        self.open_script_in_editor(item_data, sql)

    def script_fdw_as_create(self, item_data, fdw_name):
        sql = f"-- Create Foreign Data Wrapper Script\nCREATE FOREIGN DATA WRAPPER \"{fdw_name}\";"
        self.open_script_in_editor(item_data, sql)

    def script_server_as_create(self, item_data, server_name):
        sql = f"-- Create Foreign Server Script\nCREATE SERVER \"{server_name}\"\n    FOREIGN DATA WRAPPER <fdw_name>\n    OPTIONS (host 'localhost', port '5432', dbname 'database');"
        self.open_script_in_editor(item_data, sql)

    def script_user_mapping_as_create(self, item_data, user_name):
        sql = f"-- Create User Mapping Script\nCREATE USER MAPPING FOR \"{user_name}\"\n    SERVER <server_name>\n    OPTIONS (user 'username', password 'password');"
        self.open_script_in_editor(item_data, sql)

    def script_database_as_create(self, item_data, db_name):
        sql = f"-- Create Database Script\nCREATE DATABASE \"{db_name}\"\n    WITH \n    OWNER = postgres\n    ENCODING = 'UTF8'\n    CONNECTION LIMIT = -1;"
        self.open_script_in_editor(item_data, sql)

    def script_trigger_as_create(self, item_data, trigger_name):
        """Generate CREATE TRIGGER script from the trigger definition stored in item_data."""
        trigger_def = item_data.get("trigger_def", "")
        if not trigger_def:
            ToastNotification.show_toast(self.manager, "Trigger definition not found.", kind="warning")
            return

        # The trigger_def from pg_get_triggerdef already contains the full CREATE TRIGGER statement
        # We just need to ensure it's properly formatted
        sql = f"-- Trigger: {trigger_name}\n\n{trigger_def};"
        self.open_script_in_editor(item_data, sql)

    def script_trigger_as_drop(self, item_data, trigger_name):
        """Generate DROP TRIGGER script."""
        schema_name = item_data.get('schema_name', 'public')
        table_name = item_data.get('table_name', '')
        sql = f"-- Drop Trigger: {trigger_name}\n\nDROP TRIGGER {trigger_name} ON {schema_name}.{table_name};"
        self.open_script_in_editor(item_data, sql)
