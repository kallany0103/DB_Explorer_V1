import sqlite3 as sqlite

import psycopg2
#from PyQt6.QtWidgets import QComboBox, QPlainTextEdit, QMessageBox
from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QMessageBox
from widgets.worksheet.code_editor import CodeEditor


class ScriptGenerator:
    def __init__(self, manager):
        self.manager = manager

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

    def script_table_as_create(self, item_data, table_name):
        if not item_data:
            return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
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
                QMessageBox.critical(self.manager, "Error", f"Could not generate SQLite script: {e}")
                return

        elif db_type == 'postgres':
            schema_name = item_data.get('schema_name', 'public')
            try:
                conn = psycopg2.connect(
                    host=conn_data.get("host"),
                    port=conn_data.get("port"),
                    database=conn_data.get("database"),
                    user=conn_data.get("user"),
                    password=conn_data.get("password")
                )
                cursor = conn.cursor()

                # Get relkind to distinguish table/view/mview
                cursor.execute(
                    "SELECT c.relkind, c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s;",
                    (schema_name, table_name)
                )
                res = cursor.fetchone()
                if not res:
                    raise Exception(f"Object '{schema_name}.{table_name}' not found.")
                relkind, oid = res

                if relkind == 'r': # Table
                    cursor.execute(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                        """,
                        (schema_name, table_name),
                    )
                    cols = cursor.fetchall()

                    col_defs = []
                    for col_name, dtype, nullable, default in cols:
                        null_str = " NOT NULL" if nullable == "NO" else ""
                        def_str = f' DEFAULT {default}' if default else ""
                        col_defs.append(f'    {col_name} {dtype}{null_str}{def_str}')

                    cursor.execute(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                          AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_schema = %s AND tc.table_name = %s;
                        """,
                        (schema_name, table_name),
                    )
                    pk_cols = [r[0] for r in cursor.fetchall()]

                    if pk_cols:
                        pk_names = ", ".join([f'{c}' for c in pk_cols])
                        col_defs.append(f'    CONSTRAINT {table_name}_pkey PRIMARY KEY ({pk_names})')

                    sql_script = f'-- Table: {schema_name}.{table_name}\n\n'
                    sql_script += f'CREATE TABLE {schema_name}.{table_name} (\n' + ",\n".join(col_defs) + "\n);"

                elif relkind in ('v', 'm'): # View or Materialized View
                    obj_type = "VIEW" if relkind == 'v' else "MATERIALIZED VIEW"
                    cursor.execute("SELECT pg_get_viewdef(%s);", (oid,))
                    view_def = cursor.fetchone()[0]
                    sql_script = f'-- {obj_type.title()}: {schema_name}.{table_name}\n\n'
                    sql_script += f'CREATE {obj_type} {schema_name}.{table_name} AS\n{view_def}'
                    if not sql_script.strip().endswith(';'):
                        sql_script += ';'

                # Indexes (applicable to tables and mviews)
                if relkind in ('r', 'm'):
                    cursor.execute(
                        "SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s;",
                        (schema_name, table_name),
                    )
                    idxs = cursor.fetchall()
                    if idxs:
                        sql_script += "\n\n" + "\n".join([r[0] + ";" for r in idxs])

                conn.close()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Could not generate Postgres script: {e}")
                return

        if sql_script:
            self.open_script_in_editor(item_data, sql_script)

    def script_table_as_insert(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
            sql = f'INSERT INTO {schema_name}.{table_name} (\n    -- column1, column2, ...\n)\nVALUES (\n    -- value1, value2, ...\n);'
        else:
            sql = f'INSERT INTO {table_name} (\n    -- column1, column2, ...\n)\nVALUES (\n    -- value1, value2, ...\n);'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_update(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
            sql = f'UPDATE {schema_name}.{table_name}nSET \n    -- column1 = value1,\n    -- column2 = value2\nWHERE <condition>;'
        else:
            sql = f'UPDATE {table_name}\nSET \n    -- column1 = value1,\n    -- column2 = value2\nWHERE <condition>;'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_delete(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
            sql = f'DELETE FROM {schema_name}.{table_name}\nWHERE <condition>;'
        else:
            sql = f'DELETE FROM {table_name}\nWHERE <condition>;'
        self.open_script_in_editor(item_data, sql)

    def script_table_as_select(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
            sql = f'SELECT * FROM {schema_name}.{table_name};'
        else:
            sql = f'SELECT * FROM {table_name};'
        self.open_script_in_editor(item_data, sql)

    def script_sequence_as_create(self, item_data, seq_name):
        conn_data = item_data.get('conn_data')
        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
            cursor = conn.cursor()
            schema_name = item_data.get('schema_name', 'public')
            cursor.execute(
                "SELECT 'CREATE SEQUENCE ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname) || ';' FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = %s AND n.nspname = %s;",
                (seq_name, schema_name),
            )
            res = cursor.fetchone()
            if res:
                self.open_script_in_editor(item_data, res[0])
            conn.close()
        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to script sequence:\n{e}")

    def script_function_as_create(self, item_data, func_name):
        conn_data = item_data.get('conn_data')
        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
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
                QMessageBox.warning(self.manager, "Warning", "Could not find function definition.")
            conn.close()
        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to script function:\n{e}")

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
