# widgets/connection_manager/context_menus/schema_menus.py
"""Right-click menus for the Schema Tree (bottom QTreeView).

Covers: tables, views, sequences, functions, languages, extensions,
schema nodes, group nodes (Tables/Views/Functions/etc.), schemas_root,
FDW nodes, foreign servers, and user mappings.
"""

from functools import partial
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

from widgets.connection_manager.menu_style import apply_menu_style
from widgets.connection_manager.context_menus._helpers import (
    action,
    add_properties_statistics_actions,
    stub,
    submenu,
)
from widgets.connection_manager.context_menus.mview_menus import MaterializedViewMenuBuilder
from widgets.connection_manager.context_menus.trigger_menus import TriggerMenuBuilder
from widgets.usql_tool.terminal_widget import open_usql_tool

class SchemaMenuBuilder:
    """Builds context menus for the Schema Tree."""

    def __init__(self, manager):
        self.manager = manager
        self.mview_builder = MaterializedViewMenuBuilder(manager)
        self.trigger_builder = TriggerMenuBuilder(manager)

    # =========================================================================
    # Entry point
    # =========================================================================

    def show(self, position):
        index = self.manager.schema_tree.indexAt(position)
        if not index.isValid():
            return

        item = self.manager.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        menu = QMenu()
        apply_menu_style(menu)

        db_type        = item_data.get("db_type")
        table_name     = item_data.get("table_name")
        schema_name    = item_data.get("schema_name")
        table_type     = item_data.get("table_type", "").upper()
        node_type      = item_data.get("type", "")

        is_trigger          = node_type == "trigger"
        is_triggers_group   = node_type == "triggers_group"
        is_table_or_view    = table_name is not None and not is_trigger and not is_triggers_group
        is_schema           = schema_name is not None and not is_table_or_view and not is_trigger and not is_triggers_group
        is_sequence         = table_type == "SEQUENCE"
        is_function         = table_type == "FUNCTION"
        is_trigger_function = table_type == "TRIGGER FUNCTION"
        is_language         = table_type == "LANGUAGE"
        is_extension        = table_type == "EXTENSION"

        if node_type == "schema_group":
            self._schema_group_menu(menu, item, item_data, index)
        elif is_triggers_group:
            self.trigger_builder.build_group_menu(menu, item, item_data, index)
        elif table_type == "MATERIALIZED VIEW":
            self.mview_builder.build_menu(menu, item, item_data)
        elif is_table_or_view:
            self._table_menu(menu, item, item_data, db_type, index)
        elif is_sequence:
            self._sequence_menu(menu, item, item_data, index)
        elif is_function or is_trigger_function:
            self._function_menu(menu, item, item_data, table_type, index)
        elif is_language:
            self._language_menu(menu, item, item_data, index)
        elif is_extension:
            self._extension_menu(menu, item, item_data, index)
        elif is_schema:
            self._schema_node_menu(menu, item, item_data, db_type, schema_name, index)
        elif node_type == "language_root":
            self._language_root_menu(menu, item_data, index)
        elif node_type == "extension_root":
            self._extension_root_menu(menu, item_data, index)
        elif node_type == "schemas_root":
            self._schemas_root_menu(menu, item_data, index)
        elif node_type == "fdw_root":
            self._fdw_root_menu(menu, item_data, db_type, index)
        elif node_type == "fdw":
            self._fdw_menu(menu, item_data, index)
        elif node_type == "foreign_server":
            self._foreign_server_menu(menu, item_data, index)
        elif node_type == "user_mapping":
            self._user_mapping_menu(menu, item_data, index)
        elif node_type == "indexes_group":
            self._indexes_group_menu(menu, item, item_data, index)
        elif node_type == "index":
            self._index_menu(menu, item, item_data, index)
        elif node_type == "constraints_group":
            self._constraints_group_menu(menu, item, item_data, index)
        elif node_type == "constraint":
            self._constraint_menu(menu, item, item_data, index)
        elif node_type == "columns_group":
            self._columns_group_menu(menu, item, item_data, index)
        elif node_type == "column":
            self._column_menu(menu, item, item_data, index)
        elif is_trigger:
            self.trigger_builder.build_menu(menu, item, item_data)
        elif node_type == "policies_group":
            self._policies_group_menu(menu, item, item_data, index)
        elif node_type == "policy":
            self._policy_menu(menu, item, item_data, index)
        else:
            # Fallback
            menu.addAction(action(self.manager, f"Properties for {item.text()}"))

        if not menu.isEmpty():
            menu.exec(self.manager.schema_tree.viewport().mapToGlobal(position))

    # =========================================================================
    # Shared helpers
    # =========================================================================

    def _add_refresh_actions(self, menu, index):
        """Append a separator then Refresh / Reset Tree to *menu*."""
        menu.addSeparator()
        act = action(self.manager, "Refresh", "mdi.refresh", shortcut="F5")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, False))
        menu.addAction(act)
        act = action(self.manager, "Reset Tree", "mdi.arrow-collapse-all")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, True))
        menu.addAction(act)

    # =========================================================================
    # Table details (Columns, Constraints, Indexes)
    # =========================================================================

    def _columns_group_menu(self, menu, item, item_data, index):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")
        act = action(self.manager, "Column...", "mdi.table-column-plus-after")
        act.triggered.connect(stub("create_column"))
        create_sub.addAction(act)
        
        self._add_refresh_actions(menu, index)

    def _column_menu(self, menu, item, item_data, index):
        act = action(self.manager, "Drop Column", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(stub("drop_column"))
        menu.addAction(act)

        act = action(self.manager, "Drop Column (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_column_cascade"))
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, item.text())

    def _constraints_group_menu(self, menu, item, item_data, index):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")
        
        act = action(self.manager, "Primary Key...", "mdi.key-outline")
        act.triggered.connect(stub("create_pk"))
        create_sub.addAction(act)
        
        act = action(self.manager, "Foreign Key...", "mdi.key-link")
        act.triggered.connect(stub("create_fk"))
        create_sub.addAction(act)
        
        act = action(self.manager, "Check...", "mdi.check-network-outline")
        act.triggered.connect(stub("create_check"))
        create_sub.addAction(act)
        
        act = action(self.manager, "Unique...", "mdi.fingerprint")
        act.triggered.connect(stub("create_unique"))
        create_sub.addAction(act)
        
        act = action(self.manager, "Exclude...", "mdi.minus-circle-outline")
        act.triggered.connect(stub("create_exclude"))
        create_sub.addAction(act)

        self._add_refresh_actions(menu, index)

    def _constraint_menu(self, menu, item, item_data, index):
        act = action(self.manager, "Drop Constraint", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(stub("drop_constraint"))
        menu.addAction(act)

        act = action(self.manager, "Drop Constraint (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_constraint_cascade"))
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, item.text())

    def _indexes_group_menu(self, menu, item, item_data, index):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")
        act = action(self.manager, "Index...", "mdi.sort-alphabetical-ascending")
        act.triggered.connect(stub("create_index"))
        create_sub.addAction(act)

        self._add_refresh_actions(menu, index)

    def _index_menu(self, menu, item, item_data, index):
        act = action(self.manager, "Drop Index", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(stub("drop_index"))
        menu.addAction(act)

        act = action(self.manager, "Drop Index (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_index_cascade"))
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, item.text())

    # =========================================================================
    # Table / View
    # =========================================================================

    def _table_menu(self, menu, item, item_data, db_type, index):
        display_name = item.text()
        table_type   = item_data.get("table_type", "TABLE").upper()
        is_view      = "VIEW" in table_type
        label        = "View" if is_view else "Table"
        hide_pg_style_actions = str(db_type or "").lower() in ("csv", "servicenow")

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
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Export Rows...", "mdi.export")
        act.triggered.connect(
            lambda: self.manager.connection_actions.export_schema_table_rows(item_data, display_name)
        )
        menu.addAction(act)

        if not hide_pg_style_actions:
            act = action(self.manager, "Backup...", "mdi.backup-restore")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_backup_dialog(item_data)
            )
            menu.addAction(act)

            act = action(self.manager, "Restore...", "mdi.database-import")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_restore_dialog(item_data)
            )
            menu.addAction(act)

            menu.addSeparator()
            security_sub = submenu(menu, "Security", "mdi.shield-lock-outline")
            
            act = action(self.manager, "Enable Row Level Security", "mdi.shield-check-outline")
            act.triggered.connect(lambda: self.manager.connection_actions.enable_rls(item_data, True))
            security_sub.addAction(act)

            act = action(self.manager, "Disable Row Level Security", "mdi.shield-remove-outline")
            act.triggered.connect(lambda: self.manager.connection_actions.enable_rls(item_data, False))
            security_sub.addAction(act)

            security_sub.addSeparator()

            act = action(self.manager, "Force Row Level Security", "mdi.shield-alert-outline")
            act.triggered.connect(lambda: self.manager.connection_actions.force_rls(item_data, True))
            security_sub.addAction(act)

            act = action(self.manager, "No Force Row Level Security", "mdi.shield-outline")
            act.triggered.connect(lambda: self.manager.connection_actions.force_rls(item_data, False))
            security_sub.addAction(act)

            menu.addSeparator()
            add_properties_statistics_actions(menu, self.manager, item_data, display_name)

            menu.addSeparator()
            act = action(self.manager, f"ERD for {label}", "fa6s.sitemap")
            act.triggered.connect(
                lambda: self.manager.generate_erd_for_item(item_data, display_name)
            )
            menu.addAction(act)

            menu.addSeparator()
            scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
            for lbl, fn in [
                ("CREATE Script", lambda: self.manager.script_generator.script_table_as_create(item_data, display_name)),
                ("INSERT Script", lambda: self.manager.script_generator.script_table_as_insert(item_data, display_name)),
                ("UPDATE Script", lambda: self.manager.script_generator.script_table_as_update(item_data, display_name)),
                ("DELETE Script", lambda: self.manager.script_generator.script_table_as_delete(item_data, display_name)),
                ("SELECT Script", lambda: self.manager.script_generator.script_table_as_select(item_data, display_name)),
            ]:
                a = action(self.manager, lbl, "mdi.script-text-outline")
                a.triggered.connect(fn)
                scripts_sub.addAction(a)

        if not is_view:
            menu.addSeparator()
            act = action(self.manager, "Truncate", "mdi.eraser")
            act.triggered.connect(
                lambda: self.manager.connection_actions.truncate_table(item_data, display_name)
            )
            menu.addAction(act)

            act = action(self.manager, "Truncate (Cascade)", "mdi.eraser-variant")
            act.triggered.connect(
                lambda: self.manager.connection_actions.truncate_table(item_data, display_name, cascade=True)
            )
            menu.addAction(act)

        act = action(self.manager, f"Drop {label}", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, f"Drop {label} (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_table(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        if hide_pg_style_actions:
            menu.addSeparator()
            add_properties_statistics_actions(menu, self.manager, item_data, display_name)

        self._add_refresh_actions(menu, index)

    # =========================================================================
    # Schema node  (e.g. "public")
    # =========================================================================

    def _schema_node_menu(self, menu, item, item_data, db_type, schema_name, index):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")

        act = action(self.manager, "Table...", "mdi.table-plus")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_table_template(item_data)
        )
        create_sub.addAction(act)

        act = action(self.manager, "View...", "mdi.eye-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_view_template(item_data)
        )
        create_sub.addAction(act)

        act = action(self.manager, "Index...", "mdi.database-arrow-up-outline")
        act.triggered.connect(stub("create_index"))
        create_sub.addAction(act)

        act = action(self.manager, "Schema...", "mdi.folder-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_schema_dialog(item_data)
        )
        create_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_schema(item_data, schema_name)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_schema(item_data, schema_name, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh", "mdi.refresh", shortcut="F5")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=False))
        menu.addAction(act)
        
        act = action(self.manager, "Reset Tree", "mdi.arrow-collapse-all")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=True))
        menu.addAction(act)

        act = action(self.manager, "Backup...", "mdi.backup-restore")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_backup_dialog(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Restore...", "mdi.database-import")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_restore_dialog(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_schema_as_create(item_data, schema_name)
        )
        menu.addAction(act)

        act = action(self.manager, "ERD for Schema", "fa6s.sitemap")
        act.triggered.connect(
            lambda: self.manager.generate_erd_for_item(item_data, f"Schema: {schema_name}")
        )
        menu.addAction(act)

        menu.addSeparator()

        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+F")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_search_objects_dialog(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "USQL Tool", "mdi.console")
        act.triggered.connect(lambda: open_usql_tool(item_data.get("conn_data") or item_data, self.manager))
        menu.addAction(act)

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, schema_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, schema_name)

    # =========================================================================
    # Schemas root  ("Schemas" group node)
    # =========================================================================

    def _schemas_root_menu(self, menu, item_data, index):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")

        # *** WIRED — opens the Create Schema dialog ***
        act = action(self.manager, "Schema...", "mdi.folder-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_schema_dialog(item_data)
        )
        create_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+F")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_search_objects_dialog(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item_data.get("conn_data", {}).get("database") or "Schemas")
        )
        menu.addAction(act)

        db_type = item_data.get("db_type", "")
        if str(db_type).lower() not in ("csv", "servicenow"):
            menu.addSeparator()
            act = action(self.manager, "Backup...", "mdi.backup-restore")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_backup_dialog(item_data)
            )
            menu.addAction(act)

            act = action(self.manager, "Restore...", "mdi.database-import")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_restore_dialog(item_data)
            )
            menu.addAction(act)

        menu.addSeparator()
        conn = item_data.get("conn_data") or {}
        add_properties_statistics_actions(
            menu, self.manager, item_data, conn.get("database") or "Schemas"
        )

    # =========================================================================
    # Schema group node  (Tables, Views, Functions, Sequences, etc.)
    # =========================================================================

    def _schema_group_menu(self, menu, item, item_data, index):
        group = item_data.get("group_name", "")

        # --- Type-specific Create action ---
        _wired = {
            "Tables": (
                "Create Table...", "mdi.table-plus",
                lambda: self.manager.connection_actions.open_create_table_template(item_data)
            ),
            "Views": (
                "Create View...", "mdi.eye-plus-outline",
                lambda: self.manager.connection_actions.open_create_view_template(item_data)
            ),
            "Functions": (
                "Create Function...", "mdi.function-variant",
                lambda: self.manager.connection_actions.open_create_function_dialog(item_data)
            ),
            "Trigger Functions": (
                "Create Trigger Function...", "mdi.lightning-bolt-outline",
                lambda: self.manager.connection_actions.open_create_trigger_function_dialog(item_data)
            ),
            "Sequences": (
                "Create Sequence...", "mdi.numeric-1-box-multiple-outline",
                lambda: self.manager.connection_actions.open_create_sequence_dialog(item_data)
            ),
            "Foreign Tables": (
                "Create Foreign Table...", "mdi.table-network",
                lambda: self.manager.connection_actions.open_create_foreign_table_dialog(item_data)
            ),
            "Materialized Views": (
                "Create Materialized View...", "mdi.eye-settings-outline",
                lambda: self.manager.connection_actions.open_create_materialized_view_dialog(item_data)
            ),
        }
        _stubbed = {
            "Procedures":           ("Create Procedure...",          "mdi.cog-play-outline"),
            "Aggregates":           ("Create Aggregate...",          "mdi.sigma"),
            "Collations":           ("Create Collation...",          "mdi.sort-alphabetical-ascending"),
            "Domains":              ("Create Domain...",             "mdi.shape-outline"),
            "Types":                ("Create Type...",               "mdi.code-braces"),
            "Operators":            ("Create Operator...",           "mdi.math-compass"),
            "Rules":                ("Create Rule...",               "mdi.format-list-checks"),
            "Triggers":             ("Create Trigger...",            "mdi.lightning-bolt-outline"),
        }

        if group in _wired:
            lbl, icon, fn = _wired[group]
            act = action(self.manager, lbl, icon)
            act.triggered.connect(fn)
            menu.addAction(act)
        elif group in _stubbed:
            lbl, icon = _stubbed[group]
            act = action(self.manager, lbl, icon)
            act.triggered.connect(stub(f"create_{group.lower()}"))
            menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item_data.get("group_name") or item.text())
        )
        menu.addAction(act)

        db_type = item_data.get("db_type", "")
        if str(db_type).lower() not in ("csv", "servicenow"):
            menu.addSeparator()
            act = action(self.manager, "Backup...", "mdi.backup-restore")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_backup_dialog(item_data)
            )
            menu.addAction(act)

            act = action(self.manager, "Restore...", "mdi.database-import")
            act.triggered.connect(
                lambda: self.manager.connection_actions.open_restore_dialog(item_data)
            )
            menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(
            menu, self.manager, item_data, item_data.get("group_name") or item.text()
        )

    # =========================================================================
    # Sequence
    # =========================================================================

    def _sequence_menu(self, menu, item, item_data, index):
        display_name = item.text()

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_sequence_as_create(item_data, display_name)
        )
        scripts_sub.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, "Drop Sequence", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_sequence(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Sequence (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_sequence(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, display_name)

    # =========================================================================
    # Function / Trigger Function
    # =========================================================================

    def _function_menu(self, menu, item, item_data, table_type, index):
        display_name = item.text()
        label = table_type.lower().capitalize()

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_function_as_create(item_data, display_name)
        )
        scripts_sub.addAction(act)
        
        menu.addSeparator()
        act = action(self.manager, f"Drop {label}", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_function(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, f"Drop {label} (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_function(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, display_name)


    # =========================================================================
    # Language
    # =========================================================================

    def _language_menu(self, menu, item, item_data, index):
        display_name = item.text()

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        scripts_sub = submenu(menu, "Scripts", "mdi.script-text-outline")
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_language_as_create(item_data, display_name)
        )
        scripts_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop Language", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_language(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Language (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.delete_language(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, display_name)

    # =========================================================================
    # Extension (individual item)
    # =========================================================================

    def _extension_menu(self, menu, item, item_data, index):
        display_name = item.text()

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, display_name)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop Extension", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_extension(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, "DROP Extension (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_extension(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_extension_as_create(item_data, display_name)
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, display_name)

    # =========================================================================
    # language_root
    # =========================================================================

    def _language_root_menu(self, menu, item_data, index):
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, "Languages")
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, "Languages")

    # =========================================================================
    # extension_root
    # =========================================================================

    def _extension_root_menu(self, menu, item_data, index):
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, "Extensions")
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, "Extensions")

    # =========================================================================
    # FDW root
    # =========================================================================

    def _fdw_root_menu(self, menu, item_data, db_type, index):

        menu.addSeparator()
        act = action(self.manager, "Refresh", "mdi.refresh", shortcut="F5")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=False))
        menu.addAction(act)
        
        act = action(self.manager, "Reset Tree", "mdi.arrow-collapse-all")
        act.triggered.connect(partial(self.manager.refresh_schema_tree_item, index, collapse=True))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, "Foreign Data Wrappers")
        )
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(menu, self.manager, item_data, "Foreign Data Wrappers")

    # =========================================================================
    # FDW node
    # =========================================================================

    def _fdw_menu(self, menu, item_data, index):
        fdw_name = item_data.get("fdw_name", "")

        menu.addSeparator()
        act = action(self.manager, "Drop Foreign Data Wrapper", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_fdw(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Foreign Data Wrapper (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_fdw(item_data, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_fdw_as_create(item_data, fdw_name)
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item_data.get("fdw_name", "Foreign Data Wrapper"))
        )
        menu.addAction(act)

        menu.addSeparator()
        add_properties_statistics_actions(
            menu, self.manager, item_data, item_data.get("fdw_name", "Foreign Data Wrapper")
        )

    # =========================================================================
    # Foreign Server
    # =========================================================================

    def _foreign_server_menu(self, menu, item_data, index):

        menu.addSeparator()
        act = action(self.manager, "Drop Foreign Server", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_foreign_server(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Foreign Server (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_foreign_server(item_data, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_server_as_create(item_data, item_data.get("server_name", ""))
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item_data.get("server_name", "Foreign Server"))
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(
            menu, self.manager, item_data, item_data.get("server_name", "Foreign Server")
        )

    # =========================================================================
    # User Mapping
    # =========================================================================

    def _user_mapping_menu(self, menu, item_data, index):
        act = action(self.manager, "Drop User Mapping", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_user_mapping(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop User Mapping (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_user_mapping(item_data, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(
            lambda: self.manager.script_generator.script_user_mapping_as_create(item_data, item_data.get("user_name", ""))
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_query_tool_for_table(item_data, item_data.get("user_name", "User Mapping"))
        )
        menu.addAction(act)

        self._add_refresh_actions(menu, index)

        menu.addSeparator()
        add_properties_statistics_actions(
            menu, self.manager, item_data, item_data.get("user_name", "User Mapping")
        )
