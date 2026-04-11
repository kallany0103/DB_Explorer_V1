# widgets/connection_manager/context_menus/schema_menus.py
"""Right-click menus for the Schema Tree (bottom QTreeView).

Covers: tables, views, sequences, functions, languages, extensions,
schema nodes, group nodes (Tables/Views/Functions/etc.), schemas_root,
FDW nodes, foreign servers, and user mappings.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

from widgets.connection_manager.menu_style import apply_menu_style
from widgets.connection_manager.context_menus._helpers import action, stub, submenu


class SchemaMenuBuilder:
    """Builds context menus for the Schema Tree."""

    def __init__(self, manager):
        self.manager = manager

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

        is_table_or_view    = table_name is not None
        is_schema           = schema_name is not None and not is_table_or_view
        is_sequence         = table_type == "SEQUENCE"
        is_function         = table_type == "FUNCTION"
        is_trigger_function = table_type == "TRIGGER FUNCTION"
        is_language         = table_type == "LANGUAGE"
        is_extension        = table_type == "EXTENSION"

        if node_type == "schema_group":
            self._schema_group_menu(menu, item, item_data, index)
        elif is_table_or_view:
            self._table_menu(menu, item, item_data, db_type)
        elif is_sequence:
            self._sequence_menu(menu, item, item_data)
        elif is_function or is_trigger_function:
            self._function_menu(menu, item, item_data, table_type)
        elif is_language:
            self._language_menu(menu, item, item_data)
        elif is_extension:
            self._extension_menu(menu, item, item_data)
        elif is_schema:
            self._schema_node_menu(menu, item, item_data, db_type, schema_name)
        elif node_type == "language_root":
            self._language_root_menu(menu, item_data, index)
        elif node_type == "extension_root":
            self._extension_root_menu(menu, item_data, index)
        elif node_type == "schemas_root":
            self._schemas_root_menu(menu, item_data)
        elif node_type == "fdw_root":
            self._fdw_root_menu(menu, item_data, db_type, index)
        elif node_type == "fdw":
            self._fdw_menu(menu, item_data, index)
        elif node_type == "foreign_server":
            self._foreign_server_menu(menu, item_data)
        elif node_type == "user_mapping":
            self._user_mapping_menu(menu, item_data)

        if not menu.isEmpty():
            menu.exec(self.manager.schema_tree.viewport().mapToGlobal(position))

    # =========================================================================
    # Table / View
    # =========================================================================

    def _table_menu(self, menu, item, item_data, db_type):
        display_name = item.text()
        table_type   = item_data.get("table_type", "TABLE").upper()
        is_view      = "VIEW" in table_type
        label        = "View" if is_view else "Table"

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

        act = action(self.manager, "Properties...", "mdi.tune", shortcut="Alt+Shift+E")
        act.triggered.connect(
            lambda: self.manager.connection_actions.show_table_properties(item_data, display_name)
        )
        menu.addAction(act)

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

        menu.addSeparator()
        if db_type in ("postgres", "sqlite"):
            if is_view:
                # Right-clicking a View → only offer Create View
                act = action(self.manager, "Create View...", "mdi.eye-plus-outline")
                act.triggered.connect(
                    lambda: self.manager.connection_actions.open_create_view_template(item_data)
                )
                menu.addAction(act)
            else:
                # Right-clicking a Table → only offer Create Table
                act = action(self.manager, "Create Table...", "mdi.table-plus")
                act.triggered.connect(
                    lambda: self.manager.connection_actions.open_create_table_template(item_data)
                )
                menu.addAction(act)

        menu.addSeparator()
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

    # =========================================================================
    # Schema node  (e.g. "public")
    # =========================================================================

    def _schema_node_menu(self, menu, item, item_data, db_type, schema_name):
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
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.schema_loader.load_postgres_schema(item_data.get("conn_data"))
        )
        menu.addAction(act)

        act = action(self.manager, "Restore...", "mdi.restore")
        act.triggered.connect(stub("restore_schema"))
        menu.addAction(act)

        act = action(self.manager, "Backup...", "mdi.backup-restore")
        act.triggered.connect(stub("backup_schema"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "CREATE Script", "mdi.script-text-outline")
        act.triggered.connect(stub("create_script_schema"))
        menu.addAction(act)

        act = action(self.manager, "ERD for Schema", "fa6s.sitemap")
        act.triggered.connect(
            lambda: self.manager.generate_erd_for_item(item_data, f"Schema: {schema_name}")
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Maintenance...", "mdi.wrench-outline")
        act.triggered.connect(stub("maintenance_schema"))
        menu.addAction(act)

        act = action(self.manager, "Grant Wizard...", "mdi.account-key-outline")
        act.triggered.connect(stub("grant_wizard_schema"))
        menu.addAction(act)

        act = action(self.manager, "Search Objects...", "mdi.magnify", shortcut="Alt+Shift+S")
        act.triggered.connect(stub("search_schema"))
        menu.addAction(act)

        if db_type == "postgres":
            act = action(self.manager, "Import Foreign Schema...", "mdi.database-import")
            act.triggered.connect(
                lambda: self.manager.connection_actions.import_foreign_schema_dialog(item_data)
            )
            menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "PSQL Tool", "mdi.console")
        act.triggered.connect(stub("psql_tool_schema"))
        menu.addAction(act)

        act = action(self.manager, "Query Tool", "mdi.database-search", shortcut="Alt+Shift+Q")
        act.triggered.connect(stub("query_tool_schema"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Properties...", "mdi.tune", shortcut="Alt+Shift+E")
        act.triggered.connect(stub("properties_schema"))
        menu.addAction(act)

    # =========================================================================
    # Schemas root  ("Schemas" group node)
    # =========================================================================

    def _schemas_root_menu(self, menu, item_data):
        create_sub = submenu(menu, "Create", "mdi.plus-circle-outline")

        # *** WIRED — opens the Create Schema dialog ***
        act = action(self.manager, "Schema...", "mdi.folder-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.open_create_schema_dialog(item_data)
        )
        create_sub.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(stub("drop_schemas_root"))
        menu.addAction(act)

        act = action(self.manager, "Drop (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_schemas_root_cascade"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.schema_loader.load_postgres_schema(item_data.get("conn_data"))
        )
        menu.addAction(act)

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
                lambda: self.manager.script_generator.open_create_function_template(item_data)
            ),
            "Trigger Functions": (
                "Create Trigger Function...", "mdi.lightning-bolt-outline",
                lambda: self.manager.script_generator.open_create_trigger_function_template(item_data)
            ),
        }
        _stubbed = {
            "Materialized Views":   ("Create Materialized View...", "mdi.eye-settings-outline"),
            "Procedures":           ("Create Procedure...",          "mdi.cog-play-outline"),
            "Sequences":            ("Create Sequence...",           "mdi.numeric-1-box-multiple-outline"),
            "Aggregates":           ("Create Aggregate...",          "mdi.sigma"),
            "Collations":           ("Create Collation...",          "mdi.sort-alphabetical-ascending"),
            "Domains":              ("Create Domain...",             "mdi.shape-outline"),
            "Types":                ("Create Type...",               "mdi.code-braces"),
            "Operators":            ("Create Operator...",           "mdi.math-compass"),
            "Rules":                ("Create Rule...",               "mdi.format-list-checks"),
            "Triggers":             ("Create Trigger...",            "mdi.lightning-bolt-outline"),
            "Foreign Tables":       ("Create Foreign Table...",      "mdi.table-network"),
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
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.table_details_loader.load_tables_on_expand(index)
        )
        menu.addAction(act)

    # =========================================================================
    # Sequence
    # =========================================================================

    def _sequence_menu(self, menu, item, item_data):
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
        act.triggered.connect(stub("drop_sequence_cascade"))
        menu.addAction(act)

    # =========================================================================
    # Function / Trigger Function
    # =========================================================================

    def _function_menu(self, menu, item, item_data, table_type):
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
        act.triggered.connect(stub(f"drop_{label.lower()}_cascade"))
        menu.addAction(act)

    # =========================================================================
    # Language
    # =========================================================================

    def _language_menu(self, menu, item, item_data):
        display_name = item.text()

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
        act.triggered.connect(stub("drop_language_cascade"))
        menu.addAction(act)

    # =========================================================================
    # Extension (individual item)
    # =========================================================================

    def _extension_menu(self, menu, item, item_data):
        display_name = item.text()

        act = action(self.manager, "Drop Extension", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_extension(item_data, display_name)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Extension (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_extension(item_data, display_name, cascade=True)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.schema_loader.load_postgres_schema(item_data.get("conn_data"))
        )
        menu.addAction(act)

    # =========================================================================
    # language_root
    # =========================================================================

    def _language_root_menu(self, menu, item_data, index):
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.table_details_loader.load_tables_on_expand(index)
        )
        menu.addAction(act)

    # =========================================================================
    # extension_root
    # =========================================================================

    def _extension_root_menu(self, menu, item_data, index):
        act = action(self.manager, "Create Extension...", "mdi.puzzle-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.create_extension_dialog(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.table_details_loader.load_tables_on_expand(index)
        )
        menu.addAction(act)

    # =========================================================================
    # FDW root
    # =========================================================================

    def _fdw_root_menu(self, menu, item_data, db_type, index):
        if db_type == "postgres":
            act = action(self.manager, "Create postgres_fdw Extension", "mdi.puzzle-plus-outline")
            act.triggered.connect(
                lambda: self.manager.connection_actions.execute_simple_sql(
                    item_data, "CREATE EXTENSION IF NOT EXISTS postgres_fdw;"
                )
            )
            menu.addAction(act)
            menu.addSeparator()

        act = action(self.manager, "Create Foreign Data Wrapper...", "mdi.database-link-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.create_fdw_template(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.table_details_loader.load_tables_on_expand(index)
        )
        menu.addAction(act)

    # =========================================================================
    # FDW node
    # =========================================================================

    def _fdw_menu(self, menu, item_data, index):
        fdw_name = item_data.get("fdw_name", "")
        lbl = "Create Foreign Server (Postgres)..." if fdw_name == "postgres_fdw" else "Create Foreign Server..."

        act = action(self.manager, lbl, "mdi.server-plus")
        act.triggered.connect(
            lambda: self.manager.connection_actions.create_foreign_server_template(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop Foreign Data Wrapper", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_fdw(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Foreign Data Wrapper (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_fdw_cascade"))
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Refresh...", "mdi.refresh", shortcut="F5")
        act.triggered.connect(
            lambda: self.manager.table_details_loader.load_tables_on_expand(index)
        )
        menu.addAction(act)

    # =========================================================================
    # Foreign Server
    # =========================================================================

    def _foreign_server_menu(self, menu, item_data):
        act = action(self.manager, "Create User Mapping...", "mdi.account-plus-outline")
        act.triggered.connect(
            lambda: self.manager.connection_actions.create_user_mapping_template(item_data)
        )
        menu.addAction(act)

        menu.addSeparator()
        act = action(self.manager, "Drop Foreign Server", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_foreign_server(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop Foreign Server (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_foreign_server_cascade"))
        menu.addAction(act)

    # =========================================================================
    # User Mapping
    # =========================================================================

    def _user_mapping_menu(self, menu, item_data):
        act = action(self.manager, "Drop User Mapping", "mdi.delete-outline", shortcut="Alt+Shift+D")
        act.triggered.connect(
            lambda: self.manager.connection_actions.drop_user_mapping(item_data)
        )
        menu.addAction(act)

        act = action(self.manager, "Drop User Mapping (Cascade)", "mdi.delete-sweep-outline")
        act.triggered.connect(stub("drop_user_mapping_cascade"))
        menu.addAction(act)
