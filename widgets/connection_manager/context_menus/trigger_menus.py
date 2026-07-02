# widgets/connection_manager/context_menus/trigger_menus.py
"""Modular context menu builder for Triggers."""

from functools import partial
from widgets.connection_manager.context_menus._helpers import action, add_properties_statistics_actions, stub, submenu

class TriggerMenuBuilder:
    def __init__(self, manager):
        self.manager = manager

    def build_group_menu(self, menu, item, item_data, index):
        """Context menu for the 'Triggers (N)' group folder under a table."""

        # Create submenu
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")
        act = action(self.manager, "Trigger...", "mdi.lightning-bolt-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_trigger_dialog(item_data)
        )
        create_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh", "mdi.refresh", shortcut="F5")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=False))
        menu.addAction(act)
        
        act = action(self.manager, "Reset Tree", "mdi.arrow-collapse-all")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=True))
        menu.addAction(act)

        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+S")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_search_objects_dialog(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "USQL Tool", "mdi.console")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_usql_tool(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(
                item_data, item_data.get("table_name", "Triggers")
            )
        )
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, item.text())

    def build_menu(self, menu, item, item_data):
        display_name = item_data.get('trigger_name')
        table_name = item_data.get('table_name')
        enabled_status = item_data.get('tgenabled')

        # Enable/Disable toggle action
        if enabled_status == 'D':
            act = action(self.manager, "Enable Trigger", "mdi.lightning-bolt")
            act.triggered.connect(
                lambda: self.manager.connection_actions.enable_trigger(item_data, display_name, enable=True)
            )
        else:
            act = action(self.manager, "Disable Trigger", "mdi.lightning-bolt-outline")
            act.triggered.connect(
                lambda: self.manager.connection_actions.enable_trigger(item_data, display_name, enable=False)
            )
        menu.addAction(act)

        menu.addSeparator()

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, table_name)
        )
        menu.addAction(act)

        menu.addSeparator()

        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_trigger_as_create(item_data, display_name)
        )
        scripts_sub.addAction(act)

        act = action(self.manager, "DROP Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_trigger_as_drop(item_data, display_name)
        )
        scripts_sub.addAction(act)

        menu.addSeparator()

        # Properties & Statistics (using the helper)
        add_properties_statistics_actions(menu, self.manager, item_data, display_name)

        menu.addSeparator()

        act = action(self.manager, "Drop Trigger", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_trigger(item_data, display_name)
        )
        menu.addAction(act)
