# widgets/connection_manager/context_menus/explorer_menus.py
"""Right-click menus for the Object Explorer tree (top QTreeView).

Covers depth 1 (Connection Type), 2 (Group), 3 (Connection), ≥4 (Object).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

from widgets.connection_manager.menu_style import apply_menu_style
from widgets.connection_manager.context_menus._helpers import action, stub, submenu


class ExplorerMenuBuilder:
    """Builds context menus for the Object Explorer tree."""

    def __init__(self, manager):
        self.manager = manager

    # =========================================================================
    # Entry point
    # =========================================================================

    def show(self, pos):
        proxy_index = self.manager.tree.indexAt(pos)
        if not proxy_index.isValid():
            return

        source_index = self.manager.proxy_model.mapToSource(proxy_index)
        item = self.manager.model.itemFromIndex(source_index)
        depth = self.manager.get_item_depth(item)

        menu = QMenu()
        apply_menu_style(menu)

        if depth == 1:
            self._type_menu(menu, item)
        elif depth == 2:
            self._group_menu(menu, item)
        elif depth == 3:
            self._connection_menu(menu, item)
        elif depth >= 4:
            self._object_menu(menu, item)

        if not menu.isEmpty():
            menu.exec(self.manager.tree.viewport().mapToGlobal(pos))

    # =========================================================================
    # Depth 1 : Connection Type  (e.g. POSTGRES, SQLITE)
    # =========================================================================

    def _type_menu(self, menu, item):
        act = action(self.manager, "New Connection Group", "mdi.folder-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_dialogs.add_connection_group(item)
        )
        menu.addAction(act)

        menu.addSeparator()

        act = action(self.manager, "Edit Connection Type", "mdi.pencil-outline")
        act.triggered.connect(
            lambda: self.manager.connection_dialogs.edit_connection_type(item)
        )
        menu.addAction(act)

        act = action(self.manager, "Delete Connection Type", "mdi.delete-outline")
        act.triggered.connect(
            lambda: self.manager.connection_dialogs.delete_connection_type(item)
        )
        menu.addAction(act)

    # =========================================================================
    # Depth 2 : Connection Group
    # =========================================================================

    def _group_menu(self, menu, item):
        parent_item = item.parent()
        code = parent_item.data(Qt.ItemDataRole.UserRole) if parent_item else None

        if code == "POSTGRES":
            act = action(self.manager, "New PostgreSQL Connection", "mdi.database-plus")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.add_postgres_connection(item)
            )
            menu.addAction(act)
        elif code == "SQLITE":
            act = action(self.manager, "New SQLite Connection", "mdi.database-plus")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.add_sqlite_connection(item)
            )
            menu.addAction(act)
        elif code in ("ORACLE_FA", "ORACLE_DB"):
            act = action(self.manager, "New Oracle Connection", "mdi.database-plus")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.add_oracle_connection(item)
            )
            menu.addAction(act)
        elif code == "CSV":
            act = action(self.manager, "New CSV Connection", "mdi.file-delimited-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.add_csv_connection(item)
            )
            menu.addAction(act)
        elif code == "SERVICENOW":
            act = action(self.manager, "New ServiceNow Connection", "mdi.cloud-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.add_servicenow_connection(item)
            )
            menu.addAction(act)

        menu.addSeparator()

        act = action(self.manager, "Edit Connection Group", "mdi.pencil-outline")
        act.triggered.connect(
            lambda: self.manager.connection_dialogs.edit_connection_group(item)
        )
        menu.addAction(act)

        act = action(self.manager, "Delete Connection Group", "mdi.delete-outline")
        act.triggered.connect(
            lambda: self.manager.connection_dialogs.delete_connection_group(item)
        )
        menu.addAction(act)

    # =========================================================================
    # Depth 3 : Individual Connection (server / file)
    # =========================================================================

    def _connection_menu(self, menu, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)

        if conn_data:
            act = action(self.manager, "View Details", "mdi.information-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.show_connection_details(item)
            )
            menu.addAction(act)
            menu.addSeparator()

        parent_item = item.parent()
        grandparent_item = parent_item.parent() if parent_item else None
        code = grandparent_item.data(Qt.ItemDataRole.UserRole) if grandparent_item else None

        if code == "SQLITE" and conn_data and conn_data.get("db_path"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.edit_connection(item)
            )
            menu.addAction(act)
        elif code == "POSTGRES" and conn_data and conn_data.get("host"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.edit_pg_connection(item)
            )
            menu.addAction(act)
        elif code in ("ORACLE_FA", "ORACLE_DB"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.edit_oracle_connection(item)
            )
            menu.addAction(act)
        elif code == "CSV" and conn_data and conn_data.get("db_path"):
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.edit_csv_connection(item)
            )
            menu.addAction(act)
        elif code == "SERVICENOW":
            act = action(self.manager, "Edit Connection", "mdi.pencil-outline")
            act.triggered.connect(
                lambda: self.manager.connection_dialogs.edit_servicenow_connection(item)
            )
            menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(conn_data, item.text())
            if conn_data else None
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(lambda: self.manager.refresh_object_explorer())
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "ERD for Database", "fa6s.sitemap")
        act.triggered.connect(lambda: self.manager.generate_erd(item))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Delete Connection", "mdi.delete-outline")
        act.triggered.connect(lambda: self.manager.delete_connection(item))
        menu.addAction(act)

    # =========================================================================
    # Depth ≥ 4 : Table / object node inside the explorer tree
    # =========================================================================

    def _object_menu(self, menu, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not (item_data and isinstance(item_data, dict)):
            return

        table_type = item_data.get("table_type", "TABLE")
        is_view = "VIEW" in str(table_type).upper()
        object_label = "View" if is_view else "Table"

        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")
        if is_view:
            act = action(self.manager, "View...", "mdi.eye-plus-outline")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_create_view_template(item_data)
            )
            create_sub.addAction(act)
        else:
            act = action(self.manager, "Table...", "mdi.table-plus")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_create_table_template(item_data)
            )
            create_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, item.text())
        )
        menu.addAction(act)

        act = action(self.manager, "Drop (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, item.text(), cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(lambda: self.manager.refresh_object_explorer())
        menu.addAction(act)

        act = action(self.manager, "Restore...", "mdi.restore")
        act.triggered.connect(stub("restore"))
        menu.addAction(act)

        act = action(self.manager, "Backup...", "mdi.backup-restore")
        act.triggered.connect(stub("backup"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_table_as_create(item_data, item.text())
        )
        menu.addAction(act)

        act = action(self.manager, f"ERD for {object_label}", "fa6s.sitemap")
        act.triggered.connect(
            lambda: self.manager.generate_erd_for_item(item_data, item.text())
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Maintenance...", "mdi.wrench-outline")
        act.triggered.connect(stub("maintenance"))
        menu.addAction(act)

        act = action(self.manager, "Grant Wizard...", "mdi.account-key-outline")
        act.triggered.connect(stub("grant_wizard"))
        menu.addAction(act)

        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+S")
        act.triggered.connect(stub("search_objects"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "PSQL Tool", "mdi.console")
        act.triggered.connect(stub("psql_tool"))
        menu.addAction(act)

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item.text())
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Properties...", "mdi.tune", shortcut="Alt+Shift+E")
        act.triggered.connect(stub("properties"))
        menu.addAction(act)
