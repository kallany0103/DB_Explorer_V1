# widgets/connection_manager/context_menus/explorer_menus.py
"""Modular context menu builder for the Object Explorer (top QTreeView)."""

from PySide6.QtCore import Qt
from widgets.connection_manager.context_menus._helpers import action, stub, submenu

class ExplorerMenuBuilder:
    def __init__(self, manager):
        self.manager = manager

    def show(self, pos):
        proxy_index = self.manager.tree.indexAt(pos)
        if not proxy_index.isValid():
            return

        source_index = self.manager.proxy_model.mapToSource(proxy_index)
        item = self.manager.model.itemFromIndex(source_index)
        depth = self.manager.get_item_depth(item)
        
        from PySide6.QtWidgets import QMenu
        from widgets.connection_manager.menu_style import apply_menu_style
        menu = QMenu()
        apply_menu_style(menu)

        if depth == 1:
            self._connection_type_menu(menu, item)
        elif depth == 2:
            self._connection_group_menu(menu, item)
        elif depth == 3:
            self._connection_menu(menu, item, source_index)
        elif depth >= 4:
            self._object_menu(menu, item, source_index)

        if not menu.isEmpty():
            menu.exec(self.manager.tree.viewport().mapToGlobal(pos))

    def _connection_type_menu(self, menu, item):
        act = action(self.manager, "New Connection Group", "mdi.folder-plus-outline")
        act.triggered.connect(lambda: self.manager.connection_dialogs.add_connection_group(item))
        menu.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Edit Connection Type", "mdi.pencil-outline")
        act.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection_type(item))
        menu.addAction(act)
        
        act = action(self.manager, "Delete Connection Type", "mdi.delete-outline")
        act.triggered.connect(lambda: self.manager.connection_dialogs.delete_connection_type(item))
        menu.addAction(act)

    def _connection_group_menu(self, menu, item):
        parent_item = item.parent()
        code = parent_item.data(Qt.ItemDataRole.UserRole) if parent_item else None

        if code == 'POSTGRES':
            act = action(self.manager, "New PostgreSQL Connection", "mdi.database-plus")
            act.triggered.connect(lambda: self.manager.connection_dialogs.add_postgres_connection(item))
            menu.addAction(act)
        elif code == 'SQLITE':
            act = action(self.manager, "New SQLite Connection", "mdi.database-plus")
            act.triggered.connect(lambda: self.manager.connection_dialogs.add_sqlite_connection(item))
            menu.addAction(act)
        elif code in ['ORACLE_FA', 'ORACLE_DB']:
            act = action(self.manager, "New Oracle Connection", "mdi.database-plus")
            act.triggered.connect(lambda: self.manager.connection_dialogs.add_oracle_connection(item))
            menu.addAction(act)
        elif code == 'CSV':
            act = action(self.manager, "New CSV Connection", "mdi.file-plus-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.add_csv_connection(item))
            menu.addAction(act)
        elif code == 'SERVICENOW':
            act = action(self.manager, "New ServiceNow Connection", "mdi.cloud-plus-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.add_servicenow_connection(item))
            menu.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Edit Connection Group", "mdi.folder-edit-outline")
        act.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection_group(item))
        menu.addAction(act)
        
        act = action(self.manager, "Delete Connection Group", "mdi.folder-remove-outline")
        act.triggered.connect(lambda: self.manager.connection_dialogs.delete_connection_group(item))
        menu.addAction(act)

    def _connection_menu(self, menu, item, index):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(lambda: self.manager.connection_actions.open_query_tool(item))
        menu.addAction(act)
        
        menu.addSeparator()
        
        # Search Objects Dialog
        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+F")
        act.triggered.connect(lambda: self.manager.connection_actions.open_search_objects_dialog(conn_data))
        menu.addAction(act)
        
        menu.addSeparator()
        
        act = action(self.manager, "ERD for Database", "fa6s.sitemap")
        act.triggered.connect(lambda: self.manager.generate_erd(item))
        menu.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Properties...", "mdi.tune", shortcut="Alt+Shift+E")
        act.triggered.connect(lambda: self.manager.connection_dialogs.show_connection_details(item))
        menu.addAction(act)

        parent_item = item.parent()
        grandparent_item = parent_item.parent() if parent_item else None
        code = grandparent_item.data(Qt.ItemDataRole.UserRole) if grandparent_item else None
        if code == 'SQLITE' and conn_data and conn_data.get("db_path"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.edit_connection(item))
            menu.addAction(act)
        elif code == 'POSTGRES' and conn_data and conn_data.get("host"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.edit_pg_connection(item))
            menu.addAction(act)
        elif code in ['ORACLE_FA', 'ORACLE_DB']:
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.edit_oracle_connection(item))
            menu.addAction(act)
        elif code == 'CSV' and conn_data and conn_data.get("db_path"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.edit_csv_connection(item))
            menu.addAction(act)
        elif code == 'SERVICENOW':
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(lambda: self.manager.connection_dialogs.edit_servicenow_connection(item))
            menu.addAction(act)
        
        menu.addSeparator()
        
        # Refresh Logic (Targeted)
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(lambda: self.manager.refresh_object_explorer(index))
        menu.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Delete Connection", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(lambda: self.manager.delete_connection(item))
        menu.addAction(act)

    def _object_menu(self, menu, item, index):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data: return
        
        display_name = item.text()
        table_type = item_data.get('table_type', 'TABLE').upper()
        is_view = "VIEW" in table_type
        
        # View/Edit Data submenu
        view_sub = submenu(menu, "View/Edit Data", "mdi.table-eye")
        
        act = action(self.manager, "All Rows", "mdi.table-row")
        act.triggered.connect(lambda: self.manager.connection_actions.query_table_rows(item_data, display_name, limit=None, execute_now=True))
        view_sub.addAction(act)
        
        act = action(self.manager, "First 100 Rows", "mdi.table-row")
        act.triggered.connect(lambda: self.manager.connection_actions.query_table_rows(item_data, display_name, limit=100, execute_now=True))
        view_sub.addAction(act)
        
        act = action(self.manager, "Count Rows", "mdi.counter")
        act.triggered.connect(lambda: self.manager.connection_actions.count_table_rows(item_data, display_name))
        view_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name))
        menu.addAction(act)

        menu.addSeparator()
        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(lambda: self.manager.script_generator.script_table_as_create(item_data, display_name))
        scripts_sub.addAction(act)
        
        act = action(self.manager, "SELECT Script", "mdi.script-text-outline")
        act.triggered.connect(lambda: self.manager.script_generator.script_table_as_select(item_data, display_name))
        scripts_sub.addAction(act)

        menu.addSeparator()
        if not is_view:
            act = action(self.manager, "Truncate", "mdi.eraser")
            act.triggered.connect(lambda: self.manager.connection_actions.truncate_table(item_data, display_name))
            menu.addAction(act)

        act = action(self.manager, "Drop", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(lambda: self.manager.connection_actions.delete_table(item_data, display_name))
        menu.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(lambda: self.manager.refresh_object_explorer(index))
        menu.addAction(act)
