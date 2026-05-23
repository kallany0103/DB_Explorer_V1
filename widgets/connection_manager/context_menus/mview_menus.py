# widgets/connection_manager/context_menus/mview_menus.py
"""Modular context menu builder for Materialized Views."""

from widgets.connection_manager.context_menus._helpers import action, submenu

class MaterializedViewMenuBuilder:
    def __init__(self, manager):
        self.manager = manager

    def build_menu(self, menu, item, item_data):
        display_name = item.text()
        
        # View/Edit Data submenu
        view_sub = submenu(menu, "View/Edit Data", "mdi.table-eye")
        
        act = action(self.manager, "All Rows", "mdi.table-row")
        act.triggered.connect(
            lambda: self.manager.connection_actions.query_table_rows(
                item_data, display_name, limit=None, execute_now=True
            )
        )
        view_sub.addAction(act)

        act = action(self.manager, "First 100 Rows", "mdi.table-row")
        act.triggered.connect(
            lambda: self.manager.connection_actions.query_table_rows(
                item_data, display_name, limit=100, execute_now=True
            )
        )
        view_sub.addAction(act)

        act = action(self.manager, "Last 100 Rows", "mdi.table-row")
        act.triggered.connect(
            lambda: self.manager.connection_actions.query_table_rows(
                item_data, display_name, limit=100, order="desc", execute_now=True
            )
        )
        view_sub.addAction(act)

        act = action(self.manager, "Count Rows", "mdi.counter")
        act.triggered.connect(
            lambda: self.manager.connection_actions.count_table_rows(item_data, display_name)
        )
        view_sub.addAction(act)

        menu.addSeparator()
        
        # Refresh View logic
        act = action(self.manager, "Refresh View", "mdi.refresh")
        act.triggered.connect(
            lambda: self.manager.connection_actions.refresh_materialized_view(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, "Refresh View (Concurrently)", "mdi.refresh-circle")
        act.triggered.connect(
            lambda: self.manager.connection_actions.refresh_materialized_view(item_data, display_name, concurrently=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        
        act = action(self.manager, "Export Data...", "mdi.export")
        act.triggered.connect(
            lambda: self.manager.connection_actions.export_schema_table_rows(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_table_as_create(item_data, display_name)
        )
        scripts_sub.addAction(act)

        act = action(self.manager, "SELECT Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_table_as_select(item_data, display_name)
        )
        scripts_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "ERD for Materialized View", "fa6s.sitemap")
        act.triggered.connect(
            lambda: self.manager.generate_erd_for_item(item_data, f"M-View: {display_name}")
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Backup...", "mdi.backup-restore")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_backup_dialog(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()

        act = action(self.manager, "Drop Materialized View", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, display_name) # delete_table update handles this
        )
        menu.addAction(act)

        act = action(self.manager, "Drop (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, display_name, cascade=True)
        )
        menu.addAction(act)
