# from PyQt6.QtCore import Qt
# from PyQt6.QtGui import QAction
# from PyQt6.QtWidgets import QMenu

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


class ContextMenuHandler:
    def __init__(self, manager):
        self.manager = manager

    def show_context_menu(self, pos):
        proxy_index = self.manager.tree.indexAt(pos)
        if not proxy_index.isValid():
            return
        source_index = self.manager.proxy_model.mapToSource(proxy_index)
        item = self.manager.model.itemFromIndex(source_index)
        depth = self.manager.get_item_depth(item)
        menu = QMenu()
        if depth == 1:
            add_connection_group = QAction("New Connection Group", self.manager)
            add_connection_group.triggered.connect(lambda: self.manager.connection_dialogs.add_connection_group(item))
            menu.addAction(add_connection_group)
            
            menu.addSeparator()
            
            edit_type_action = QAction("Edit Connection Type", self.manager)
            edit_type_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection_type(item))
            menu.addAction(edit_type_action)
            
            delete_type_action = QAction("Delete Connection Type", self.manager)
            delete_type_action.triggered.connect(lambda: self.manager.connection_dialogs.delete_connection_type(item))
            menu.addAction(delete_type_action)

        elif depth == 2:
            parent_item = item.parent()
            code = parent_item.data(Qt.ItemDataRole.UserRole) if parent_item else None

            if code == 'POSTGRES':
                add_pg_action = QAction("New PostgreSQL Connection", self.manager)
                add_pg_action.triggered.connect(lambda: self.manager.connection_dialogs.add_postgres_connection(item))
                menu.addAction(add_pg_action)
            elif code == 'SQLITE':
                add_sqlite_action = QAction("New SQLite Connection", self.manager)
                add_sqlite_action.triggered.connect(lambda: self.manager.connection_dialogs.add_sqlite_connection(item))
                menu.addAction(add_sqlite_action)
            elif code in ['ORACLE_FA', 'ORACLE_DB']:
                add_oracle_action = QAction("New Oracle Connection", self.manager)
                add_oracle_action.triggered.connect(lambda: self.manager.connection_dialogs.add_oracle_connection(item))
                menu.addAction(add_oracle_action)
            elif code == 'CSV':
                add_csv_action = QAction("New CSV Connection", self.manager)
                add_csv_action.triggered.connect(lambda: self.manager.connection_dialogs.add_csv_connection(item))
                menu.addAction(add_csv_action)
            elif code == 'SERVICENOW':
                add_sn_action = QAction("New ServiceNow Connection", self.manager)
                add_sn_action.triggered.connect(lambda: self.manager.connection_dialogs.add_servicenow_connection(item))
                menu.addAction(add_sn_action)
            
            menu.addSeparator()
            
            edit_group_action = QAction("Edit Connection Group", self.manager)
            edit_group_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection_group(item))
            menu.addAction(edit_group_action)
            
            delete_group_action = QAction("Delete Connection Group", self.manager)
            delete_group_action.triggered.connect(lambda: self.manager.connection_dialogs.delete_connection_group(item))
            menu.addAction(delete_group_action)

        elif depth == 3:
            conn_data = item.data(Qt.ItemDataRole.UserRole)
            if conn_data:
                view_details_action = QAction("View details", self.manager)
                view_details_action.triggered.connect(lambda: self.manager.connection_dialogs.show_connection_details(item))
                menu.addAction(view_details_action)
                menu.addSeparator()

            parent_item = item.parent()
            grandparent_item = parent_item.parent() if parent_item else None
            code = grandparent_item.data(Qt.ItemDataRole.UserRole) if grandparent_item else None
            if code == 'SQLITE' and conn_data.get("db_path"):
                edit_action = QAction("Edit Connection", self.manager)
                edit_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection(item))
                menu.addAction(edit_action)
            elif code == 'POSTGRES' and conn_data.get("host"):
                edit_action = QAction("Edit Connection", self.manager)
                edit_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_pg_connection(item))
                menu.addAction(edit_action)
            elif code in ['ORACLE_FA', 'ORACLE_DB']:
                edit_action = QAction("Edit Connection", self.manager)
                edit_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_oracle_connection(item))
                menu.addAction(edit_action)
            elif code == 'CSV' and conn_data.get("db_path"):
                edit_action = QAction("Edit Connection", self.manager)
                edit_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_csv_connection(item))
                menu.addAction(edit_action)
            elif code == 'SERVICENOW':
                edit_action = QAction("Edit Connection", self.manager)
                edit_action.triggered.connect(lambda: self.manager.connection_dialogs.edit_servicenow_connection(item))
                menu.addAction(edit_action)

            delete_action = QAction("Delete Connection", self.manager)
            delete_action.triggered.connect(lambda: self.manager.delete_connection(item))
            menu.addAction(delete_action)

            menu.addSeparator()
            erd_action = QAction("ERD for Database", self.manager)
            erd_action.triggered.connect(lambda: self.manager.generate_erd(item))
            menu.addAction(erd_action)

        elif depth >= 4:
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and isinstance(item_data, dict):
                table_type = item_data.get('table_type', 'TABLE')

                script_menu = menu.addMenu("Script Table as")

                select_action = QAction("SELECT", self.manager)
                select_action.triggered.connect(lambda: self.manager.script_generator.script_table_as_select(item_data, item.text()))
                script_menu.addAction(select_action)

                menu.addSeparator()

                del_text = "Delete View" if "VIEW" in str(table_type).upper() else "Delete Table"
                drop_action = QAction(del_text, self.manager)
                drop_action.triggered.connect(lambda: self.manager.connection_actions.delete_table(item_data, item.text()))
                menu.addAction(drop_action)

        menu.exec(self.manager.tree.viewport().mapToGlobal(pos))

    def show_schema_context_menu(self, position):
        index = self.manager.schema_tree.indexAt(position)
        if not index.isValid():
            return
        item = self.manager.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)

        if not item_data:
            return

        db_type = item_data.get('db_type')
        table_name = item_data.get('table_name')
        schema_name = item_data.get('schema_name')

        is_table_or_view = table_name is not None
        is_schema = schema_name is not None and not is_table_or_view

        table_type = item_data.get('table_type', '').upper()
        is_sequence = table_type == 'SEQUENCE'
        is_function = table_type == 'FUNCTION'
        is_trigger_function = table_type == 'TRIGGER FUNCTION'
        is_language = table_type == 'LANGUAGE'
        is_extension = table_type == 'EXTENSION'

        menu = QMenu()

        if is_table_or_view:
            display_name = item.text()
            view_menu = menu.addMenu("View/Edit Data")

            query_all_action = QAction("All Rows", self.manager)
            query_all_action.triggered.connect(lambda: self.manager.connection_actions.query_table_rows(item_data, display_name, limit=None, execute_now=True))
            view_menu.addAction(query_all_action)

            preview_100_action = QAction("First 100 Rows", self.manager)
            preview_100_action.triggered.connect(lambda: self.manager.connection_actions.query_table_rows(item_data, display_name, limit=100, execute_now=True))
            view_menu.addAction(preview_100_action)

            last_100_action = QAction("Last 100 Rows", self.manager)
            last_100_action.triggered.connect(lambda: self.manager.connection_actions.query_table_rows(item_data, display_name, limit=100, order='desc', execute_now=True))
            view_menu.addAction(last_100_action)

            count_rows_action = QAction("Count Rows", self.manager)
            count_rows_action.triggered.connect(lambda: self.manager.connection_actions.count_table_rows(item_data, display_name))
            view_menu.addAction(count_rows_action)

            menu.addSeparator()
            query_tool_action = QAction("Query Tool", self.manager)
            query_tool_action.triggered.connect(lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name))
            menu.addAction(query_tool_action)

            menu.addSeparator()
            export_rows_action = QAction("Export Rows", self.manager)
            export_rows_action.triggered.connect(lambda: self.manager.connection_actions.export_schema_table_rows(item_data, display_name))
            menu.addAction(export_rows_action)

            properties_action = QAction("Properties", self.manager)
            properties_action.triggered.connect(lambda: self.manager.connection_actions.show_table_properties(item_data, display_name))
            menu.addAction(properties_action)

            menu.addSeparator()
            erd_action = QAction("ERD for Table", self.manager)
            erd_action.triggered.connect(lambda: self.manager.generate_erd_for_item(item_data, display_name))
            menu.addAction(erd_action)

            menu.addSeparator()
            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_table_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            create_script_action = QAction("INSERT Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_table_as_insert(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            create_script_action = QAction("DELETE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_table_as_delete(item_data, display_name))
            scripts_menu.addAction(create_script_action)
            create_script_action = QAction("UPDATE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_table_as_update(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            menu.addSeparator()

            if db_type in ['postgres', 'sqlite']:
                create_table_action = QAction("Create Table", self.manager)
                create_table_action.triggered.connect(lambda: self.manager.connection_actions.open_create_table_template(item_data))
                menu.addAction(create_table_action)

            if db_type in ['postgres', 'sqlite']:
                create_view_action = QAction("Create View", self.manager)
                create_view_action.triggered.connect(lambda: self.manager.connection_actions.open_create_view_template(item_data))
                menu.addAction(create_view_action)

            menu.addSeparator()
            table_type = item_data.get('table_type', 'TABLE').upper()
            object_type = "View" if "VIEW" in table_type else "Table"
            delete_table_action = QAction(f"Delete {object_type}", self.manager)
            delete_table_action.triggered.connect(lambda: self.manager.connection_actions.delete_table(item_data, display_name))
            menu.addAction(delete_table_action)

        elif is_sequence:
            display_name = item.text()

            query_tool_action = QAction("Query Tool", self.manager)
            query_tool_action.triggered.connect(lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name))
            menu.addAction(query_tool_action)

            menu.addSeparator()
            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_sequence_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            menu.addSeparator()
            delete_seq_action = QAction("Delete Sequence", self.manager)
            delete_seq_action.triggered.connect(lambda: self.manager.connection_actions.delete_sequence(item_data, display_name))
            menu.addAction(delete_seq_action)

        elif is_function or is_trigger_function:
            display_name = item.text()

            query_tool_action = QAction("Query Tool", self.manager)
            query_tool_action.triggered.connect(lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name))
            menu.addAction(query_tool_action)

            menu.addSeparator()
            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_function_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            menu.addSeparator()
            delete_func_action = QAction(f"Drop {table_type.lower().capitalize()}", self.manager)
            delete_func_action.triggered.connect(lambda: self.manager.connection_actions.delete_function(item_data, display_name))
            menu.addAction(delete_func_action)

        elif is_language:
            display_name = item.text()

            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE Script", self.manager)
            create_script_action.triggered.connect(lambda: self.manager.script_generator.script_language_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            menu.addSeparator()
            delete_lang_action = QAction("Drop Language", self.manager)
            delete_lang_action.triggered.connect(lambda: self.manager.connection_actions.delete_language(item_data, display_name))
            menu.addAction(delete_lang_action)

        elif is_extension:
            display_name = item.text()

            menu.addSeparator()
            drop_ext_action = QAction("Drop Extension", self.manager)
            drop_ext_action.triggered.connect(lambda: self.manager.connection_actions.drop_extension(item_data, display_name))
            menu.addAction(drop_ext_action)

            drop_ext_cascade_action = QAction("Drop Extension (CASCADE)", self.manager)
            drop_ext_cascade_action.triggered.connect(lambda: self.manager.connection_actions.drop_extension(item_data, display_name, cascade=True))
            menu.addAction(drop_ext_cascade_action)

            menu.addSeparator()
            refresh_action = QAction("Refresh", self.manager)
            refresh_action.triggered.connect(lambda: self.manager.schema_loader.load_postgres_schema(item_data.get('conn_data')))
            menu.addAction(refresh_action)

        elif is_schema:
            if db_type == 'postgres':
                import_fdw_action = QAction("Import Foreign Schema...", self.manager)
                import_fdw_action.triggered.connect(lambda: self.manager.connection_actions.import_foreign_schema_dialog(item_data))
                menu.addAction(import_fdw_action)

                erd_action = QAction("ERD for Schema", self.manager)
                erd_action.triggered.connect(lambda: self.manager.generate_erd_for_item(item_data, f"Schema: {schema_name}"))
                menu.addAction(erd_action)

                menu.addSeparator()

        elif item_data.get('type') == 'schema_group':
            group_name = item_data.get('group_name')
            if group_name == "Functions":
                create_func_action = QAction("Create Function...", self.manager)
                create_func_action.triggered.connect(lambda: self.manager.script_generator.open_create_function_template(item_data))
                menu.addAction(create_func_action)
            elif group_name == "Trigger Functions":
                create_trig_func_action = QAction("Create Trigger Function...", self.manager)
                create_trig_func_action.triggered.connect(lambda: self.manager.script_generator.open_create_trigger_function_template(item_data))
                menu.addAction(create_trig_func_action)

            menu.addSeparator()
            refresh_group_action = QAction("Refresh", self.manager)
            refresh_group_action.triggered.connect(lambda: self.manager.table_details_loader.load_tables_on_expand(index))
            menu.addAction(refresh_group_action)

        elif item_data.get('type') == 'language_root':
            refresh_group_action = QAction("Refresh", self.manager)
            refresh_group_action.triggered.connect(lambda: self.manager.table_details_loader.load_tables_on_expand(index))
            menu.addAction(refresh_group_action)

        elif item_data.get('type') == 'extension_root':
            create_ext_action = QAction("Create Extension...", self.manager)
            create_ext_action.triggered.connect(lambda: self.manager.connection_actions.create_extension_dialog(item_data))
            menu.addAction(create_ext_action)

            menu.addSeparator()
            refresh_group_action = QAction("Refresh", self.manager)
            refresh_group_action.triggered.connect(lambda: self.manager.table_details_loader.load_tables_on_expand(index))
            menu.addAction(refresh_group_action)

        elif item_data.get('type') == 'schemas_root':
            refresh_action = QAction("Refresh", self.manager)
            refresh_action.triggered.connect(lambda: self.manager.schema_loader.load_postgres_schema(item_data.get('conn_data')))
            menu.addAction(refresh_action)

        elif item_data.get('type') == 'fdw_root':
            if db_type == 'postgres':
                create_pgfdw_action = QAction("Create postgres_fdw Extension", self.manager)
                create_pgfdw_action.triggered.connect(lambda: self.manager.connection_actions.execute_simple_sql(item_data, "CREATE EXTENSION IF NOT EXISTS postgres_fdw;"))
                menu.addAction(create_pgfdw_action)
                menu.addSeparator()

            create_fdw_action = QAction("Create Foreign Data Wrapper...", self.manager)
            create_fdw_action.triggered.connect(lambda: self.manager.connection_actions.create_fdw_template(item_data))
            menu.addAction(create_fdw_action)

            menu.addSeparator()
            refresh_group_action = QAction("Refresh", self.manager)
            refresh_group_action.triggered.connect(lambda: self.manager.table_details_loader.load_tables_on_expand(index))
            menu.addAction(refresh_group_action)

        elif item_data.get('type') == 'fdw':
            fdw_name = item_data.get('fdw_name', '')
            if fdw_name == 'postgres_fdw':
                create_srv_action = QAction("Create Foreign Server (Postgres)...", self.manager)
            else:
                create_srv_action = QAction("Create Foreign Server...", self.manager)

            create_srv_action.triggered.connect(lambda: self.manager.connection_actions.create_foreign_server_template(item_data))
            menu.addAction(create_srv_action)

            menu.addSeparator()
            drop_fdw_action = QAction("Drop Foreign Data Wrapper", self.manager)
            drop_fdw_action.triggered.connect(lambda: self.manager.connection_actions.drop_fdw(item_data))
            menu.addAction(drop_fdw_action)

            menu.addSeparator()
            refresh_action = QAction("Refresh", self.manager)
            refresh_action.triggered.connect(lambda: self.manager.table_details_loader.load_tables_on_expand(index))
            menu.addAction(refresh_action)

        elif item_data.get('type') == 'foreign_server':
            create_um_action = QAction("Create User Mapping...", self.manager)
            create_um_action.triggered.connect(lambda: self.manager.connection_actions.create_user_mapping_template(item_data))
            menu.addAction(create_um_action)

            menu.addSeparator()
            drop_srv_action = QAction("Drop Foreign Server", self.manager)
            drop_srv_action.triggered.connect(lambda: self.manager.connection_actions.drop_foreign_server(item_data))
            menu.addAction(drop_srv_action)

        elif item_data.get('type') == 'user_mapping':
            drop_um_action = QAction("Drop User Mapping", self.manager)
            drop_um_action.triggered.connect(lambda: self.manager.connection_actions.drop_user_mapping(item_data))
            menu.addAction(drop_um_action)

        if menu.isEmpty():
            return

        menu.exec(self.manager.schema_tree.viewport().mapToGlobal(position))
