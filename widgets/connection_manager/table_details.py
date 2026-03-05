import re

import db
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QIcon


class TableDetailsLoader:
    def __init__(self, manager):
        self.manager = manager

    def load_tables_on_expand(self, index):
        item = self.manager.schema_model.itemFromIndex(index)

        if not item or (item.rowCount() > 0 and item.child(0).text() != "Loading..."):
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        db_type = item_data.get('db_type')

        if db_type == 'postgres':
            schema_name = item_data.get('schema_name')
            table_name = item_data.get('table_name')

            if table_name and schema_name:
                self.load_postgres_table_details(item, item_data)
            elif schema_name and item_data.get('type') != 'schema_group':
                item.removeRows(0, item.rowCount())
                try:
                    cursor = self.manager.pg_conn.cursor()

                    groups = [
                        ("Functions", "Group", "Functions"),
                        ("Trigger Functions", "Group", "Trigger Functions"),
                        ("Sequences", "Group", "Sequences")
                    ]
                    for g_name, g_type, internal_group_name in groups:
                        group_item = QStandardItem(g_name)
                        group_item.setEditable(False)
                        self.manager._set_tree_item_icon(group_item, level="SCHEMA")

                        group_data = item_data.copy()
                        group_data['type'] = 'schema_group'
                        group_data['group_name'] = internal_group_name
                        group_item.setData(group_data, Qt.ItemDataRole.UserRole)
                        group_item.appendRow(QStandardItem("Loading..."))

                        type_item = QStandardItem(g_type)
                        type_item.setEditable(False)
                        item.appendRow([group_item, type_item])

                    cursor.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s ORDER BY table_type, table_name;", (schema_name,))
                    tables = cursor.fetchall()
                    for (table_name, table_type) in tables:
                        icon_path = "assets/table_icon.png" if "TABLE" in table_type else "assets/view_icon.png"
                        table_item = QStandardItem(QIcon(icon_path), table_name)
                        table_item.setEditable(False)

                        table_data = item_data.copy()
                        table_data['table_name'] = table_name
                        table_data['table_type'] = table_type
                        table_item.setData(table_data, Qt.ItemDataRole.UserRole)

                        if "TABLE" in table_type or "VIEW" in table_type:
                            table_item.appendRow(QStandardItem("Loading..."))

                        if "TABLE" in table_type and "FOREIGN" not in table_type:
                            self.manager._set_tree_item_icon(table_item, level="TABLE")
                            type_text = "Table"
                        elif "VIEW" in table_type:
                            self.manager._set_tree_item_icon(table_item, level="VIEW")
                            type_text = "View"
                        elif "FOREIGN" in table_type:
                            self.manager._set_tree_item_icon(table_item, level="FOREIGN_TABLE")
                            type_text = "Foreign Table"
                        else:
                            type_text = table_type.title()

                        type_item = QStandardItem(type_text)
                        type_item.setEditable(False)

                        item.appendRow([table_item, type_item])

                except Exception as e:
                    self.manager.status.showMessage(f"Error expanding schema: {e}", 5000)
                    item.appendRow(QStandardItem(f"Error: {e}"))

            elif item_data.get('type') == 'fdw_root':
                item.removeRows(0, item.rowCount())
                try:
                    cursor = self.manager.pg_conn.cursor()
                    cursor.execute("SELECT fdwname FROM pg_foreign_data_wrapper ORDER BY fdwname;")
                    for (fdw_name,) in cursor.fetchall():
                        fdw_item = QStandardItem(fdw_name)
                        fdw_item.setEditable(False)
                        self.manager._set_tree_item_icon(fdw_item, level="FDW")

                        fdw_data = item_data.copy()
                        fdw_data['type'] = 'fdw'
                        fdw_data['fdw_name'] = fdw_name
                        fdw_item.setData(fdw_data, Qt.ItemDataRole.UserRole)
                        fdw_item.appendRow(QStandardItem("Loading..."))

                        type_item = QStandardItem("Foreign Data Wrapper")
                        type_item.setEditable(False)
                        item.appendRow([fdw_item, type_item])
                except Exception as e:
                    self.manager.status.showMessage(f"Error loading FDWs: {e}", 5000)

            elif item_data.get('type') == 'fdw':
                item.removeRows(0, item.rowCount())
                fdw_name = item_data.get('fdw_name')
                try:
                    cursor = self.manager.pg_conn.cursor()
                    cursor.execute("""
                        SELECT srvname
                        FROM pg_foreign_server
                        WHERE srvfdw = (SELECT oid FROM pg_foreign_data_wrapper WHERE fdwname = %s)
                        ORDER BY srvname;
                    """, (fdw_name,))
                    for (srv_name,) in cursor.fetchall():
                        srv_item = QStandardItem(srv_name)
                        srv_item.setEditable(False)
                        self.manager._set_tree_item_icon(srv_item, level="SERVER")

                        srv_data = item_data.copy()
                        srv_data['type'] = 'foreign_server'
                        srv_data['server_name'] = srv_name
                        srv_item.setData(srv_data, Qt.ItemDataRole.UserRole)
                        srv_item.appendRow(QStandardItem("Loading..."))

                        type_item = QStandardItem("Foreign Server")
                        type_item.setEditable(False)
                        item.appendRow([srv_item, type_item])
                except Exception as e:
                    self.manager.status.showMessage(f"Error loading Foreign Servers: {e}", 5000)

            elif item_data.get('type') == 'foreign_server':
                item.removeRows(0, item.rowCount())
                srv_name = item_data.get('server_name')
                try:
                    cursor = self.manager.pg_conn.cursor()
                    cursor.execute("""
                        SELECT umuser::regrole::text
                        FROM pg_user_mapping
                        WHERE umserver = (SELECT oid FROM pg_foreign_server WHERE srvname = %s)
                        ORDER BY 1;
                    """, (srv_name,))
                    for (user_name,) in cursor.fetchall():
                        um_item = QStandardItem(user_name)
                        um_item.setEditable(False)
                        self.manager._set_tree_item_icon(um_item, level="USER")

                        um_data = item_data.copy()
                        um_data['type'] = 'user_mapping'
                        um_data['user_name'] = user_name
                        um_item.setData(um_data, Qt.ItemDataRole.UserRole)

                        type_item = QStandardItem("User Mapping")
                        type_item.setEditable(False)
                        item.appendRow([um_item, type_item])
                except Exception as e:
                    self.manager.status.showMessage(f"Error loading User Mappings: {e}", 5000)

            elif item_data.get('type') == 'extension_root':
                item.removeRows(0, item.rowCount())
                try:
                    cursor = self.manager.pg_conn.cursor()
                    cursor.execute("SELECT extname FROM pg_extension ORDER BY extname;")
                    for (ext_name,) in cursor.fetchall():
                        ext_item = QStandardItem(ext_name)
                        ext_item.setEditable(False)
                        self.manager._set_tree_item_icon(ext_item, level="EXTENSION")

                        ext_data = item_data.copy()
                        ext_data['type'] = 'extension'
                        ext_data['table_type'] = 'EXTENSION'
                        ext_data['ext_name'] = ext_name
                        ext_item.setData(ext_data, Qt.ItemDataRole.UserRole)

                        type_item = QStandardItem("Extension")
                        type_item.setEditable(False)
                        item.appendRow([ext_item, type_item])
                except Exception as e:
                    self.manager.status.showMessage(f"Error loading Extensions: {e}", 5000)

            elif item_data.get('type') == 'language_root':
                item.removeRows(0, item.rowCount())
                try:
                    cursor = self.manager.pg_conn.cursor()
                    cursor.execute("SELECT lanname FROM pg_language ORDER BY lanname;")
                    for (lan_name,) in cursor.fetchall():
                        lan_item = QStandardItem(lan_name)
                        lan_item.setEditable(False)
                        self.manager._set_tree_item_icon(lan_item, level="LANGUAGE")

                        lan_data = item_data.copy()
                        lan_data['type'] = 'language'
                        lan_data['table_type'] = 'LANGUAGE'
                        lan_data['lan_name'] = lan_name
                        lan_item.setData(lan_data, Qt.ItemDataRole.UserRole)

                        type_item = QStandardItem("Language")
                        type_item.setEditable(False)
                        item.appendRow([lan_item, type_item])
                except Exception as e:
                    self.manager.status.showMessage(f"Error loading Languages: {e}", 5000)

            elif item_data.get('type') == 'schema_group':
                item.removeRows(0, item.rowCount())
                group_name = item_data.get('group_name')
                schema_name = item_data.get('schema_name')
                try:
                    cursor = self.manager.pg_conn.cursor()
                    if group_name == "Sequences":
                        cursor.execute("SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relkind = 'S' ORDER BY relname;", (schema_name,))
                        for (seq_name,) in cursor.fetchall():
                            seq_item = QStandardItem(seq_name)
                            seq_item.setEditable(False)
                            self.manager._set_tree_item_icon(seq_item, level="SEQUENCE")

                            seq_data = item_data.copy()
                            seq_data['table_name'] = seq_name
                            seq_data['table_type'] = 'SEQUENCE'
                            seq_item.setData(seq_data, Qt.ItemDataRole.UserRole)

                            type_item = QStandardItem("Sequence")
                            type_item.setEditable(False)
                            item.appendRow([seq_item, type_item])

                    elif group_name == "Functions":
                        cursor.execute("""
                            SELECT p.proname || '(' || pg_get_function_arguments(p.oid) || ')'
                            FROM pg_proc p
                            JOIN pg_namespace n ON n.oid = p.pronamespace
                            WHERE n.nspname = %s
                            AND p.prorettype != 'trigger'::regtype
                            ORDER BY 1;
                        """, (schema_name,))
                        for (func_name,) in cursor.fetchall():
                            func_item = QStandardItem(func_name)
                            func_item.setEditable(False)
                            self.manager._set_tree_item_icon(func_item, level="FUNCTION")

                            func_data = item_data.copy()
                            func_data['table_name'] = func_name
                            func_data['table_type'] = 'FUNCTION'
                            func_item.setData(func_data, Qt.ItemDataRole.UserRole)

                            type_item = QStandardItem("Function")
                            type_item.setEditable(False)
                            item.appendRow([func_item, type_item])

                    elif group_name == "Trigger Functions":
                        cursor.execute("""
                            SELECT p.proname || '(' || pg_get_function_arguments(p.oid) || ')'
                            FROM pg_proc p
                            JOIN pg_namespace n ON n.oid = p.pronamespace
                            WHERE n.nspname = %s
                            AND p.prorettype = 'trigger'::regtype
                            ORDER BY 1;
                        """, (schema_name,))
                        for (func_name,) in cursor.fetchall():
                            func_item = QStandardItem(func_name)
                            func_item.setEditable(False)
                            self.manager._set_tree_item_icon(func_item, level="TRIGGER_FUNCTION")

                            func_data = item_data.copy()
                            func_data['table_name'] = func_name
                            func_data['table_type'] = 'TRIGGER FUNCTION'
                            func_item.setData(func_data, Qt.ItemDataRole.UserRole)

                            type_item = QStandardItem("Trigger Function")
                            type_item.setEditable(False)
                            item.appendRow([func_item, type_item])

                except Exception as e:
                    self.manager.status.showMessage(f"Error loading {group_name}: {e}", 5000)

        elif db_type == 'sqlite':
            self.load_sqlite_table_details(item, item_data)
        elif db_type == 'csv':
            self.load_cdata_table_details(item, item_data)
        elif db_type == 'servicenow':
            self.load_servicenow_table_details(item, item_data)

    def load_servicenow_table_details(self, table_item, item_data):
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return

        table_item.removeRows(0, table_item.rowCount())

        table_name = item_data.get('table_name')
        conn_data = item_data.get('conn_data')

        if not table_name or not conn_data:
            return

        conn = None
        try:
            conn = db.create_servicenow_connection(conn_data)
            cursor = conn.cursor()

            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
            except Exception:
                cursor.execute(f"SELECT * FROM {table_name} WHERE 1=0")

            columns_info = cursor.description

            column_items = []
            if columns_info:
                for col in columns_info:
                    col_name = col[0]
                    desc = f"{col_name}"
                    col_item = QStandardItem(desc)
                    col_item.setEditable(False)
                    column_items.append(col_item)

            columns_folder = QStandardItem(f"Columns ({len(column_items)})")
            columns_folder.setEditable(False)

            if not column_items:
                columns_folder.appendRow(QStandardItem("No columns found"))
            else:
                for item in column_items:
                    columns_folder.appendRow(item)

            table_item.appendRow(columns_folder)

            conn.close()

        except Exception as e:
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.manager.status.showMessage(f"Error loading ServiceNow details: {e}", 5000)

    def load_sqlite_table_details(self, table_item, item_data):
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return

        table_item.removeRows(0, table_item.rowCount())

        table_name = item_data.get('table_name')
        conn_data = item_data.get('conn_data')
        if not table_name or not conn_data:
            return

        conn = None
        try:
            conn = db.create_sqlite_connection(conn_data["db_path"])
            cursor = conn.cursor()

            column_items = []
            constraint_items = []
            index_items = []
            pk_cols = []

            cursor.execute(f'PRAGMA table_info("{table_name}");')
            columns = cursor.fetchall()

            if columns:
                for col in columns:
                    cid, name, type, notnull, dflt_value, pk = col

                    desc = f"{name} ({type})"
                    if notnull:
                        desc += " [NOT NULL]"
                    col_item = QStandardItem(desc)
                    col_item.setEditable(False)
                    column_items.append(col_item)

                    if pk > 0:
                        pk_cols.append(name)

            if pk_cols:
                pk_desc = f"[PK] ({', '.join(pk_cols)})"
                pk_item = QStandardItem(pk_desc)
                pk_item.setEditable(False)
                constraint_items.append(pk_item)

            cursor.execute(f'PRAGMA index_list("{table_name}");')
            indexes = cursor.fetchall()

            if indexes:
                for idx in indexes:
                    seq, name, unique, origin, partial = idx

                    if name.startswith("sqlite_autoindex_"):
                        continue

                    cursor.execute(f'PRAGMA index_info("{name}");')
                    idx_cols = cursor.fetchall()
                    col_names = ", ".join([c[2] for c in idx_cols])

                    desc = f"{name} ({col_names})"

                    if origin == 'c':
                        desc += " [UNIQUE]"
                        u_item = QStandardItem(desc)
                        u_item.setEditable(False)
                        constraint_items.append(u_item)
                    elif origin == 'i':
                        if unique:
                            desc += " [UNIQUE]"
                        idx_item = QStandardItem(desc)
                        idx_item.setEditable(False)
                        index_items.append(idx_item)

            cursor.execute(f'PRAGMA foreign_key_list("{table_name}");')
            fks = cursor.fetchall()

            if fks:
                fk_groups = {}
                for id, seq, table, from_col, to_col, on_update, on_delete, match in fks:
                    if id not in fk_groups:
                        fk_groups[id] = {
                            'from_cols': [],
                            'to_cols': [],
                            'table': table,
                            'rules': f"ON UPDATE {on_update} ON DELETE {on_delete}"
                        }
                    fk_groups[id]['from_cols'].append(from_col)
                    fk_groups[id]['to_cols'].append(to_col)

                for id, data in fk_groups.items():
                    from_str = ", ".join(data['from_cols'])
                    to_str = ", ".join(data['to_cols'])
                    desc = f"[FK] ({from_str}) -> {data['table']}({to_str})"
                    desc += f" [{data['rules']}]"
                    fk_item = QStandardItem(desc)
                    fk_item.setEditable(False)
                    constraint_items.append(fk_item)

            columns_folder = QStandardItem(f"Columns ({len(column_items)})")
            columns_folder.setEditable(False)
            if not column_items:
                columns_folder.appendRow(QStandardItem("No columns found"))
            else:
                for item in column_items:
                    columns_folder.appendRow(item)

            constraints_folder = QStandardItem(f"Constraints ({len(constraint_items)})")
            constraints_folder.setEditable(False)
            if not constraint_items:
                constraints_folder.appendRow(QStandardItem("No constraints found"))
            else:
                for item in constraint_items:
                    constraints_folder.appendRow(item)

            indexes_folder = QStandardItem(f"Indexes ({len(index_items)})")
            indexes_folder.setEditable(False)
            if not index_items:
                indexes_folder.appendRow(QStandardItem("No indexes"))
            else:
                for item in index_items:
                    indexes_folder.appendRow(item)

            table_item.appendRow(columns_folder)
            table_item.appendRow(constraints_folder)
            table_item.appendRow(indexes_folder)

        except Exception as e:
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.manager.status.showMessage(f"Error loading table details: {e}", 5000)
        finally:
            if conn:
                conn.close()

    def load_postgres_table_details(self, table_item, item_data):
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return

        table_item.removeRows(0, table_item.rowCount())

        schema_name = item_data.get('schema_name')
        table_name = item_data.get('table_name')
        if not table_name or not schema_name or not hasattr(self.manager, 'pg_conn') or self.manager.pg_conn.closed:
            if not hasattr(self.manager, 'pg_conn') or self.manager.pg_conn.closed:
                self.manager.status.showMessage("Connection lost. Please reload schema.", 5000)
            table_item.appendRow(QStandardItem("Error: Connection unavailable"))
            return

        try:
            cursor = self.manager.pg_conn.cursor()

            col_query = """
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.is_nullable,
                c.column_default,
                CASE
                    WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'PRIMARY KEY' THEN 'YES'
                    ELSE 'NO'
                END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu
              ON c.table_schema = kcu.table_schema
              AND c.table_name = kcu.table_name
              AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
              AND kcu.table_schema = tc.table_schema
              AND kcu.table_name = tc.table_name
              AND tc.constraint_type = 'PRIMARY KEY'
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position;
            """
            cursor.execute(col_query, (schema_name, table_name))
            columns = cursor.fetchall()

            columns_folder = QStandardItem(f"Columns ({len(columns)})")
            columns_folder.setEditable(False)

            for col in columns:
                name, dtype, char_max, is_nullable, default, is_pk = col
                desc = f"{name} ({dtype}"
                if char_max:
                    desc += f"[{char_max}]"
                desc += ")"
                if is_pk == 'YES':
                    desc += " [PK]"
                if is_nullable == 'NO':
                    desc += " [NOT NULL]"

                if default:
                    desc += f" [default: {str(default)}]"

                col_item = QStandardItem(desc)
                col_item.setEditable(False)
                self.manager._set_tree_item_icon(col_item, level="COLUMN")
                columns_folder.appendRow(col_item)
            table_item.appendRow(columns_folder)

            con_query = """
            SELECT
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = %s AND tc.table_name = %s
            ORDER BY tc.constraint_type, tc.constraint_name;
            """
            cursor.execute(con_query, (schema_name, table_name))
            constraints = cursor.fetchall()

            con_map = {}
            for name, type, col in constraints:
                if name not in con_map:
                    con_map[name] = {'type': type, 'cols': []}
                con_map[name]['cols'].append(col)

            constraints_folder = QStandardItem(f"Constraints ({len(con_map)})")
            constraints_folder.setEditable(False)

            if not con_map:
                constraints_folder.appendRow(QStandardItem("No constraints"))
            else:
                for name, data in con_map.items():
                    cols_str = ", ".join(data['cols'])
                    desc = f"{name} [{data['type']}] ({cols_str})"
                    con_item = QStandardItem(desc)
                    con_item.setEditable(False)
                    constraints_folder.appendRow(con_item)
            table_item.appendRow(constraints_folder)

            idx_query = "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s;"
            cursor.execute(idx_query, (schema_name, table_name))
            indexes = cursor.fetchall()

            user_indexes = []
            for name, definition in indexes:
                if name in con_map:
                    continue
                user_indexes.append((name, definition))

            indexes_folder = QStandardItem(f"Indexes ({len(user_indexes)})")
            indexes_folder.setEditable(False)

            if not user_indexes:
                indexes_folder.appendRow(QStandardItem("No indexes"))
            else:
                for name, definition in user_indexes:
                    match = re.search(r'USING \w+ \((.*)\)', definition)
                    cols_str = match.group(1) if match else "..."

                    desc = f"{name} ({cols_str})"
                    idx_item = QStandardItem(desc)
                    idx_item.setEditable(False)
                    indexes_folder.appendRow(idx_item)

            table_item.appendRow(indexes_folder)

        except Exception as e:
            if hasattr(self.manager, 'pg_conn') and self.manager.pg_conn:
                self.manager.pg_conn.rollback()
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.manager.status.showMessage(f"Error loading table details: {e}", 5000)

    def load_cdata_table_details(self, item, item_data):
        if item.rowCount() > 0 and item.child(0).text() != "Loading...":
            return

        if item.rowCount() == 1 and item.child(0).text() == "Loading...":
            item.removeRow(0)

        conn_data = item_data.get('conn_data')
        table_name = item_data.get('table_name')

        if not conn_data or not table_name:
            self.manager.status.showMessage("Connection or table data is missing for CData.", 5000)
            return

        try:
            column_item = QStandardItem("column_name TEXT")
            column_item.setIcon(QIcon("assets/column_icon.png"))
            column_item.setEditable(False)
            item.appendRow(column_item)

            self.manager.status.showMessage(f"Attempted to load details for CData table: {table_name}", 3000)

        except Exception as e:
            self.manager.status.showMessage(f"Error loading CData table details: {e}", 5000)
