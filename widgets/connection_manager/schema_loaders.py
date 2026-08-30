import os
import sqlite3 as sqlite
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QColor, QFontMetrics
from PySide6.QtWidgets import QHeaderView, QStyledItemDelegate, QStyle, QApplication
import qtawesome as qta

import db


class TypeColumnDelegate(QStyledItemDelegate):
    """Custom delegate for Column 1 of schema tree to render default text color with a right-aligned status dot light."""

    def paint(self, painter, option, index):
        item_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if item_text == "Data Source":
            self.initStyleOption(option, index)
            style = option.widget.style() if option.widget else QApplication.style()
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)

            is_healthy = index.data(Qt.ItemDataRole.UserRole + 3)
            if is_healthy is None:
                is_healthy = True
            dot_color = QColor("#10b981") if is_healthy else QColor("#ef4444")

            painter.save()
            painter.setFont(option.font)
            fm = QFontMetrics(option.font)
            text_width = fm.horizontalAdvance("Data Source")

            painter.setPen(dot_color)
            dot_x = option.rect.left() + text_width + 10
            dot_y = option.rect.top() + (option.rect.height() // 2) + (fm.ascent() // 2) - 1
            painter.drawText(dot_x, dot_y, "●")
            painter.restore()
        else:
            super().paint(painter, option, index)


def _create_loading_item(manager):
    item = QStandardItem("Loading...")
    item.setEditable(False)
    manager._spinner.start(item)
    return item


class SchemaLoader:
    def __init__(self, manager):
        self.manager = manager

    def _prepare_schema_tree(self):
        self.manager.schema_model.clear()
        self.manager.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        self.manager.schema_tree.setColumnWidth(0, 200)
        self.manager.schema_tree.setColumnWidth(1, 100)
        self.manager.schema_tree.setItemDelegateForColumn(1, TypeColumnDelegate(self.manager.schema_tree))

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

    def populate_sqlite_schema(self, data, skip_restore=False):
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
                name_item.appendRow(_create_loading_item(self.manager))

            self.manager.schema_model.appendRow([name_item, type_item])

        self._connect_expand_handler()
        if not skip_restore:
            self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

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

    def populate_postgres_schema(self, data, skip_restore=False):
        conn_data = data.get("conn_data", {})
        schemas = data.get("schemas", [])

        self._prepare_schema_tree()

        if hasattr(self.manager, "pg_conn") and self.manager.pg_conn and not self.manager.pg_conn.closed:
            try:
                self.manager.pg_conn.close()
            except Exception:
                pass

        self.manager.pg_conn = db.get_pooled_postgres_connection(
            conn_data,
            application_name=f"Universal SQL Client (Object Explorer) - {conn_data.get('database', 'postgres')}",
            use_pool=True
        )
        if self.manager.pg_conn:
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
                                 'type': 'schema', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
            schema_item.appendRow(_create_loading_item(self.manager))
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
        fdw_root.appendRow(_create_loading_item(self.manager))

        fdw_type_item = QStandardItem("Group")
        fdw_type_item.setEditable(False)
        self.manager.schema_model.appendRow([fdw_root, fdw_type_item])

        ext_root = QStandardItem("Extensions")
        ext_root.setEditable(False)
        self.manager._set_tree_item_icon(ext_root, level="EXTENSION_ROOT")
        ext_root.setData({'db_type': 'postgres', 'type': 'extension_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
        ext_root.appendRow(_create_loading_item(self.manager))

        ext_type_item = QStandardItem("Group")
        ext_type_item.setEditable(False)
        self.manager.schema_model.appendRow([ext_root, ext_type_item])

        lang_root = QStandardItem("Languages")
        lang_root.setEditable(False)
        self.manager._set_tree_item_icon(lang_root, level="LANGUAGE_ROOT")
        lang_root.setData({'db_type': 'postgres', 'type': 'language_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
        lang_root.appendRow(_create_loading_item(self.manager))

        lang_type_item = QStandardItem("Group")
        lang_type_item.setEditable(False)
        self.manager.schema_model.appendRow([lang_root, lang_type_item])

        self._connect_expand_handler()
        if not skip_restore:
            self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

    def populate_uds_schema(self, data, skip_restore=False):
        conn_data = data.get("conn_data", {})
        data_sources = data.get("data_sources", [])

        self._prepare_schema_tree()

        if hasattr(self.manager, "pg_conn") and self.manager.pg_conn and not self.manager.pg_conn.closed:
            try:
                self.manager.pg_conn.close()
            except Exception:
                pass

        try:
            self.manager.pg_conn = db.get_pooled_postgres_connection(
                conn_data,
                application_name=f"Universal SQL Client (UDS Schema) - {conn_data.get('database', 'postgres')}",
                use_pool=True
            )
            if self.manager.pg_conn:
                self.manager.pg_conn.autocommit = True
        except Exception as e:
            print(f"Warning: could not establish pooled postgres connection for UDS schema: {e}")

        for entry in data_sources:
            ds_data = entry.get("ds_data", {})
            server_info = entry.get("server_info", {})
            foreign_tables = entry.get("foreign_tables", [])

            raw_health = ds_data.get("is_healthy")
            if raw_health in (False, 0, "0", "false", "False"):
                is_healthy = False
            else:
                source_type = (ds_data.get("source_type") or "POSTGRES").upper()
                if source_type == "SQLITE":
                    db_path = ds_data.get("db_path") or ds_data.get("file_path")
                    is_healthy = bool(db_path and os.path.exists(db_path))
                else:
                    is_healthy = True

            ds_name = ds_data.get("name") or ds_data.get("display_name") or ds_data.get("short_name") or ds_data.get("source_name") or "Data Source"
            ds_item = QStandardItem(ds_name)
            ds_item.setEditable(False)
            self.manager._set_tree_item_icon(
                ds_item,
                level="DATA_SOURCE",
                code=ds_data.get("source_type", "POSTGRES")
            )
            ds_item_data = dict(ds_data)
            ds_item_data["type"] = "data_source"
            ds_item_data["conn_data"] = conn_data
            ds_item_data["is_healthy"] = is_healthy
            ds_item.setData(ds_item_data, Qt.ItemDataRole.UserRole)
            ds_item.setData(ds_data.get("id"), Qt.ItemDataRole.UserRole + 1)
            ds_item.setData("DATA_SOURCE", Qt.ItemDataRole.UserRole + 2)

            # 1. Foreign Server item
            server_name = server_info.get("server_name") or ds_data.get("server_name") or ds_data.get("short_name") or "Foreign Server"
            srv_item = QStandardItem(server_name)
            srv_item.setEditable(False)
            self.manager._set_tree_item_icon(srv_item, level="SERVER")

            srv_data = {
                'db_type': 'postgres',
                'type': 'foreign_server',
                'server_name': server_name,
                'fdw_name': server_info.get('fdw_name', 'postgres_fdw'),
                'conn_data': conn_data,
                'ds_data': ds_data
            }
            srv_item.setData(srv_data, Qt.ItemDataRole.UserRole)

            user_mappings = server_info.get("user_mappings", [])
            if user_mappings:
                for um_name in user_mappings:
                    um_item = QStandardItem(um_name)
                    um_item.setEditable(False)
                    self.manager._set_tree_item_icon(um_item, level="USER")
                    um_data = {
                        'db_type': 'postgres',
                        'type': 'user_mapping',
                        'user_name': um_name,
                        'server_name': server_name,
                        'conn_data': conn_data,
                        'ds_data': ds_data
                    }
                    um_item.setData(um_data, Qt.ItemDataRole.UserRole)
                    um_type_item = QStandardItem("User Mapping")
                    um_type_item.setEditable(False)
                    srv_item.appendRow([um_item, um_type_item])

            srv_type_item = QStandardItem("Foreign Server")
            srv_type_item.setEditable(False)
            ds_item.appendRow([srv_item, srv_type_item])

            # 2. Foreign Tables Group
            ft_root = QStandardItem("Foreign Tables")
            ft_root.setEditable(False)
            self.manager._set_tree_item_icon(ft_root, level="GROUP_FOREIGN_TABLES")
            ft_root_data = {
                'db_type': 'postgres',
                'type': 'schema_group',
                'group_name': 'Foreign Tables',
                'schema_name': ds_data.get('schema_name') or 'public',
                'server_name': server_name,
                'conn_data': conn_data,
                'ds_data': ds_data
            }
            ft_root.setData(ft_root_data, Qt.ItemDataRole.UserRole)

            for ft in foreign_tables:
                ft_name = ft.get("table_name")
                if ft_name in ("emp_ft", "epm_f", "epm_foreign"):
                    continue
                ft_schema = ft.get("schema_name", "public")

                table_item = QStandardItem(ft_name)
                table_item.setEditable(False)
                self.manager._set_tree_item_icon(table_item, level="FOREIGN_TABLE")

                is_sqlite = (ds_data.get('source_type') or '').upper() == 'SQLITE'
                table_data = {
                    'db_type': 'sqlite' if is_sqlite else 'postgres',
                    'type': 'table',
                    'table_name': ft_name,
                    'schema_name': ft_schema,
                    'db_path': ds_data.get('db_path') or ds_data.get('file_path'),
                    'table_type': 'Foreign Tables',
                    'conn_data': conn_data,
                    'ds_data': ds_data
                }
                table_item.setData(table_data, Qt.ItemDataRole.UserRole)
                table_item.appendRow(_create_loading_item(self.manager))

                type_item = QStandardItem("Foreign Table")
                type_item.setEditable(False)
                ft_root.appendRow([table_item, type_item])

            ft_type_item = QStandardItem("Group")
            ft_type_item.setEditable(False)
            ds_item.appendRow([ft_root, ft_type_item])

            ds_type_item = QStandardItem("Data Source")
            ds_type_item.setEditable(False)
            ds_type_item.setData(is_healthy, Qt.ItemDataRole.UserRole + 3)
            self.manager.schema_model.appendRow([ds_item, ds_type_item])

            if ds_item.index().isValid():
                self.manager.schema_tree.setExpanded(ds_item.index(), True)
            if ft_root.index().isValid():
                self.manager.schema_tree.setExpanded(ft_root.index(), True)

        # 3. Add Unified Views root node
        unified_views = data.get("unified_views", [])
        uv_label = f"Unified Views ({len(unified_views)})" if unified_views else "Unified Views"
        uv_root = QStandardItem(uv_label)
        uv_root.setEditable(False)
        self.manager._set_tree_item_icon(uv_root, level="GROUP_VIEWS")
        uv_root_data = {
            'db_type': 'postgres',
            'type': 'unified_views_root',
            'group_name': 'Unified Views',
            'conn_data': conn_data
        }
        uv_root.setData(uv_root_data, Qt.ItemDataRole.UserRole)

        for uv in unified_views:
            v_name = uv.get("view_name")
            v_schema = uv.get("schema_name", "public")

            view_item = QStandardItem(v_name)
            view_item.setEditable(False)
            self.manager._set_tree_item_icon(view_item, level="VIEW")

            view_data = {
                'db_type': 'postgres',
                'type': 'table',
                'table_name': v_name,
                'schema_name': v_schema,
                'table_type': 'VIEW',
                'conn_data': conn_data
            }
            view_item.setData(view_data, Qt.ItemDataRole.UserRole)
            view_item.appendRow(_create_loading_item(self.manager))

            v_type_item = QStandardItem("Unified View")
            v_type_item.setEditable(False)
            uv_root.appendRow([view_item, v_type_item])

        uv_type_item = QStandardItem("Views Group")
        uv_type_item.setEditable(False)
        self.manager.schema_model.appendRow([uv_root, uv_type_item])

        self._connect_expand_handler()
        if not skip_restore:
            self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

    # Alias for backwards compatibility
    populate_uds_datasource_schema = populate_uds_schema

    def load_postgres_schema(self, conn_data):
        pg_conn = None
        try:
            pg_conn = db.get_pooled_postgres_connection(
                conn_data,
                application_name=f"Universal SQL Client (Schema Loader) - {conn_data.get('database', 'postgres')}",
                use_pool=True
            )
            if not pg_conn:
                raise Exception("Failed to establish connection")
            cursor = pg_conn.cursor()
            cursor.execute(
                "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%%' AND nspname != 'information_schema' ORDER BY nspname;")
            schemas = [row[0] for row in cursor.fetchall()]
            db.return_pooled_postgres_connection(conn_data, conn=pg_conn)
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

    def populate_csv_schema(self, data, skip_restore=False):
        conn_data = data.get("conn_data", {})
        csv_files = data.get("files", [])

        self._prepare_schema_tree()

        for file_name in csv_files:
            display_name, _ = os.path.splitext(file_name)
            table_item = QStandardItem(qta.icon("mdi.table", color="#4CAF50"), display_name)
            table_item.setEditable(False)
            table_item.setData({
                'db_type': 'csv',
                'type': 'table',
                'table_name': file_name,
                'conn_data': conn_data
            }, Qt.ItemDataRole.UserRole)
            table_item.appendRow(_create_loading_item(self.manager))

            type_item = QStandardItem("Table")
            type_item.setEditable(False)

            self.manager.schema_model.appendRow([table_item, type_item])
            
        if not skip_restore:
            self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

    def populate_servicenow_schema(self, data, skip_restore=False):
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
                table_item.appendRow(_create_loading_item(self.manager))

                type_item = QStandardItem("Table")
                type_item.setEditable(False)
                self.manager.schema_model.appendRow([table_item, type_item])

            self._connect_expand_handler()
            if not skip_restore:
                self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

        except Exception as e:
            self.manager.status.showMessage(f"Error loading ServiceNow schema: {e}", 5000)

    def populate_oracle_schema(self, data, skip_restore=False):
        """UI-only: render the Oracle schema list emitted by OracleSchemaWorker.

        Builds a hierarchical tree::

            Schemas
              ├── SCOTT       (oracle_schema node, lazy-loaded on expand)
              │   ├── Tables
              │   ├── Views
              │   ├── Materialized Views
              │   ├── Procedures
              │   ├── Functions
              │   └── Sequences
              └── HR
                  └── ...
        """
        try:
            conn_data = data.get("conn_data", {})
            schemas = data.get("schemas", [])
            self._prepare_schema_tree()

            schemas_root = QStandardItem("Schemas")
            schemas_root.setEditable(False)
            self.manager._set_tree_item_icon(schemas_root, level="GROUP_SCHEMAS")
            schemas_root.setData(
                {
                    'db_type': 'oracle',
                    'type': 'oracle_schemas_root',
                    'conn_data': conn_data,
                },
                Qt.ItemDataRole.UserRole,
            )

            for owner in schemas:
                schema_item = QStandardItem(owner)
                schema_item.setEditable(False)
                self.manager._set_tree_item_icon(schema_item, level="SCHEMA")
                schema_item.setData(
                    {
                        'db_type': 'oracle',
                        'type': 'oracle_schema',
                        'schema_name': owner,
                        'conn_data': conn_data,
                    },
                    Qt.ItemDataRole.UserRole,
                )
                schema_item.appendRow(_create_loading_item(self.manager))

                type_item = QStandardItem("Schema")
                type_item.setEditable(False)
                schemas_root.appendRow([schema_item, type_item])

            schemas_type_item = QStandardItem("Group")
            schemas_type_item.setEditable(False)
            self.manager.schema_model.appendRow([schemas_root, schemas_type_item])

            # Public Database Links root
            pub_dblinks_root = QStandardItem("Public Database Links")
            pub_dblinks_root.setEditable(False)
            self.manager._set_tree_item_icon(pub_dblinks_root, level="FDW_ROOT")
            pub_dblinks_root.setData(
                {'db_type': 'oracle', 'type': 'oracle_public_dblinks_root', 'conn_data': conn_data},
                Qt.ItemDataRole.UserRole
            )
            pub_dblinks_root.appendRow(_create_loading_item(self.manager))
            pub_dblinks_type = QStandardItem("Group")
            pub_dblinks_type.setEditable(False)
            self.manager.schema_model.appendRow([pub_dblinks_root, pub_dblinks_type])

            # Public Synonyms root
            pub_synonyms_root = QStandardItem("Public Synonyms")
            pub_synonyms_root.setEditable(False)
            self.manager._set_tree_item_icon(pub_synonyms_root, level="EXTENSION_ROOT")
            pub_synonyms_root.setData(
                {'db_type': 'oracle', 'type': 'oracle_public_synonyms_root', 'conn_data': conn_data},
                Qt.ItemDataRole.UserRole
            )
            pub_synonyms_root.appendRow(_create_loading_item(self.manager))
            pub_synonyms_type = QStandardItem("Group")
            pub_synonyms_type.setEditable(False)
            self.manager.schema_model.appendRow([pub_synonyms_root, pub_synonyms_type])

            self._connect_expand_handler()
            if not skip_restore:
                self.manager._restore_schema_tree_expansion_state(conn_data.get("id"))

        except Exception as e:
            self.manager.status.showMessage(f"Error loading Oracle schema: {e}", 5000)
