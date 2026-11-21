from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt
from ui.icons import AppIcons, get_icon

def build_main_window_actions(main_window):
    main_window.open_file_action = QAction(get_icon(AppIcons.OPEN_FILE), "Open File", main_window)
    main_window.open_file_action.setShortcut("Ctrl+O")
    main_window.open_file_action.triggered.connect(main_window.open_sql_file)

    main_window.save_action = QAction(get_icon(AppIcons.SAVE), "Save", main_window)
    main_window.save_action.setShortcut("Ctrl+S")
    main_window.save_action.triggered.connect(main_window.save_sql_file)

    main_window.save_as_action = QAction(get_icon(AppIcons.SAVE), "Save As", main_window)
    main_window.save_as_action.setShortcut("Ctrl+Shift+S")
    main_window.save_as_action.triggered.connect(main_window.save_sql_file_as)

    main_window.export_connections_action = QAction(get_icon("msc.export"), "Export Connections", main_window)
    main_window.export_connections_action.triggered.connect(main_window.export_connections)

    main_window.import_connections_action = QAction(get_icon("msc.cloud-download"), "Import Connections", main_window)
    main_window.import_connections_action.triggered.connect(main_window.import_connections)

    main_window.exit_action = QAction(get_icon("msc.sign-out"), "Exit", main_window)
    main_window.exit_action.setShortcut("Ctrl+Q")
    main_window.exit_action.triggered.connect(main_window.close)

    main_window.close_tab_action = QAction(get_icon("msc.close"), "Close", main_window)
    main_window.close_tab_action.setShortcut("Ctrl+W")
    main_window.close_tab_action.triggered.connect(main_window.close_current_tab)

    main_window.close_all_tabs_action = QAction(get_icon("msc.close-all"), "Close All", main_window)
    main_window.close_all_tabs_action.setShortcut("Ctrl+Shift+W")
    main_window.close_all_tabs_action.triggered.connect(main_window.close_all_tabs)

    main_window.execute_action = QAction(get_icon(AppIcons.EXECUTE), "Execute", main_window)
    main_window.execute_action.setShortcuts(["Ctrl+Enter", "Ctrl+RETURN"])
    main_window.execute_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.execute_action.triggered.connect(main_window.execute_query)

    main_window.execute_new_tab_action = QAction(get_icon(AppIcons.EXECUTE_NEW_TAB), "Execute in New Output Tab", main_window)
    main_window.execute_new_tab_action.setShortcuts(["Ctrl+Shift+Enter", "Ctrl+Shift+RETURN"])
    main_window.execute_new_tab_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.execute_new_tab_action.triggered.connect(main_window.execute_query_in_new_output_tab)

    main_window.execute_usql_action = QAction(get_icon("msc.terminal"), "Execute SQL via psql", main_window)
    main_window.execute_usql_action.triggered.connect(lambda: main_window.execute_via_native_cli("psql"))
    main_window.execute_usql_action.setEnabled(False)

    main_window.execute_sqlplus_action = QAction(get_icon("msc.terminal"), "Execute SQL via SQL*Plus", main_window)
    main_window.execute_sqlplus_action.triggered.connect(lambda: main_window.execute_via_native_cli("sqlplus"))
    main_window.execute_sqlplus_action.setEnabled(False)

    main_window.explain_action = QAction(get_icon("msc.graph"), "Explain", main_window)
    main_window.explain_action.setShortcut("Ctrl+E")
    main_window.explain_action.triggered.connect(main_window.explain_query)

    main_window.explain_analyze_action = QAction(get_icon("msc.graph"), "Explain Analyze", main_window)
    main_window.explain_analyze_action.triggered.connect(main_window.explain_query)

    main_window.explain_plan_action = QAction(get_icon("msc.graph"), "Explain (Plan)", main_window)
    main_window.explain_plan_action.triggered.connect(main_window.explain_plan_query)

    main_window.optimize_action = QAction(
        get_icon(AppIcons.OPTIMIZE_QUERY), "Optimize SQL", main_window
    )
    main_window.optimize_action.setShortcut("Ctrl+Alt+O")
    main_window.optimize_action.setToolTip("Optimize SQL (Ctrl+Alt+O)")
    main_window.optimize_action.triggered.connect(main_window.optimize_query)

    main_window.describe_object_action = QAction(
        get_icon(AppIcons.DESCRIBE_OBJECT), "Describe", main_window
    )
    main_window.describe_object_action.setToolTip("Describe Table or Schema (F4)")
    main_window.describe_object_action.setShortcut("F4")
    main_window.describe_object_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.describe_object_action.triggered.connect(main_window.describe_object)

    main_window.quick_describe_action = QAction(
        get_icon(AppIcons.QUICK_DESCRIBE), "Quick Describe", main_window
    )
    main_window.quick_describe_action.setToolTip("Quick Describe (Ctrl+D)")
    main_window.quick_describe_action.setShortcut("Ctrl+D")
    main_window.quick_describe_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.quick_describe_action.triggered.connect(main_window.quick_describe)

    main_window.describe_query_action = QAction(
        get_icon(AppIcons.DESCRIBE_QUERY), "Describe (parse) select query", main_window
    )
    main_window.describe_query_action.setToolTip("Describe (parse) select query (Shift+F4)")
    main_window.describe_query_action.setShortcut("Shift+F4")
    main_window.describe_query_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.describe_query_action.triggered.connect(main_window.describe_query)

    main_window.change_password_action = QAction(get_icon("msc.key"), "Change Password", main_window)
    main_window.change_password_action.triggered.connect(main_window.change_password)

    main_window.cancel_action = QAction(get_icon(AppIcons.CANCEL), "Cancel", main_window)
    main_window.cancel_action.setShortcut("Alt+End")
    main_window.cancel_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.cancel_action.triggered.connect(main_window.cancel_current_query)
    main_window.cancel_action.setEnabled(False)

    main_window.undo_action = QAction(get_icon(AppIcons.UNDO), "Undo", main_window)
    main_window.undo_action.setShortcut("Ctrl+Z")
    main_window.undo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.undo_action.triggered.connect(main_window.undo_text)

    main_window.redo_action = QAction(get_icon(AppIcons.REDO), "Redo", main_window)
    main_window.redo_action.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
    main_window.redo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.redo_action.triggered.connect(main_window.redo_text)

    main_window.cut_action = QAction(get_icon(AppIcons.CUT), "Cut", main_window)
    main_window.cut_action.setShortcut("Ctrl+X")
    main_window.cut_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.cut_action.triggered.connect(main_window.cut_text)

    main_window.copy_action = QAction(get_icon(AppIcons.COPY), "Copy", main_window)
    main_window.copy_action.setShortcut("Ctrl+C")
    main_window.copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.copy_action.triggered.connect(main_window.copy_text)

    main_window.paste_action = QAction(get_icon(AppIcons.PASTE), "Paste", main_window)
    main_window.paste_action.setShortcut("Ctrl+V")
    main_window.paste_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.paste_action.triggered.connect(main_window.paste_text)

    main_window.select_all_action = QAction(get_icon(AppIcons.SELECT_ALL), "Select ALL", main_window)
    main_window.select_all_action.setShortcut("Ctrl+A")
    main_window.select_all_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    main_window.select_all_action.triggered.connect(main_window.select_all_text)

    main_window.clear_all_action = QAction(get_icon(AppIcons.CLEAR_ALL), "Clear All", main_window)
    main_window.clear_all_action.setShortcut("F7")
    main_window.clear_all_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.clear_all_action.triggered.connect(main_window.clear_query_text)

    main_window.goto_line_action = QAction(get_icon(AppIcons.GOTO_LINE), "Goto Line", main_window)
    main_window.goto_line_action.setShortcut("Ctrl+G")
    main_window.goto_line_action.triggered.connect(main_window.goto_line)

    main_window.comment_block_action = QAction(get_icon(AppIcons.COMMENT), "Comment Block", main_window)
    main_window.comment_block_action.setShortcut("Ctrl+/")
    main_window.comment_block_action.triggered.connect(main_window.comment_block)

    main_window.uncomment_block_action = QAction(get_icon(AppIcons.UNCOMMENT), "Uncomment Block", main_window)
    main_window.uncomment_block_action.setShortcut("Ctrl+Shift+/")
    main_window.uncomment_block_action.triggered.connect(main_window.uncomment_block)

    main_window.upper_case_action = QAction(get_icon(AppIcons.UPPERCASE), "Upper Case", main_window)
    main_window.upper_case_action.setShortcut("Ctrl+Shift+U")
    main_window.upper_case_action.triggered.connect(main_window.upper_case_text)

    main_window.lower_case_action = QAction(get_icon(AppIcons.LOWERCASE), "Lower Case", main_window)
    main_window.lower_case_action.setShortcut("Ctrl+Shift+L")
    main_window.lower_case_action.triggered.connect(main_window.lower_case_text)

    main_window.initial_caps_action = QAction(
        get_icon(AppIcons.INITIAL_CAPS), "Initial Caps", main_window
    )
    main_window.initial_caps_action.setShortcut("Ctrl+I")
    main_window.initial_caps_action.triggered.connect(main_window.initial_caps_text)

    main_window.query_tool_action = QAction(get_icon("msc.file-code"), "Query Tool", main_window)
    main_window.query_tool_action.setShortcut("Ctrl+T")
    main_window.query_tool_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.query_tool_action.triggered.connect(main_window.add_tab)

    main_window.reset_layout_action = QAction(get_icon("msc.layout"), "Reset Layout", main_window)
    main_window.preferences_action = QAction(get_icon(AppIcons.SETTINGS), "Settings...", main_window)
    main_window.preferences_action.setShortcut("Ctrl+,")
    main_window.preferences_action.triggered.connect(main_window.show_preferences)

    main_window.restore_action = QAction(get_icon("msc.history"), "Restore Layout", main_window)
    # Removed setShortcut("Ctrl+Shift+L") to prevent conflict with lowercase action
    main_window.reset_layout_action.triggered.connect(main_window.reset_layout)
    
    main_window.properties_tool_action = QAction(get_icon("msc.settings"), "Properties", main_window)
    main_window.properties_tool_action.triggered.connect(main_window.add_properties_tab)
    
    main_window.statistics_tool_action = QAction(get_icon("msc.graph"), "Statistics", main_window)
    main_window.statistics_tool_action.triggered.connect(main_window.add_statistics_tab)

    main_window.schema_diff_tool_action = QAction(get_icon("msc.diff", color="#0284c7"), "Schema Compare & Diff Tool...", main_window)
    main_window.schema_diff_tool_action.triggered.connect(lambda: main_window.connection_manager.connection_actions.open_schema_diff_dialog())

    main_window.dashboard_action = QAction(get_icon("msc.dashboard"), "Dashboard", main_window)
    main_window.dashboard_action.setIconVisibleInMenu(True)
    main_window.dashboard_action.triggered.connect(main_window.reset_to_dashboard)

    main_window.refresh_action = QAction(get_icon(AppIcons.REFRESH), "Refresh Explorer", main_window)
    main_window.refresh_action.setShortcuts(["F5", "Ctrl+R"])
    main_window.refresh_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.refresh_action.triggered.connect(main_window.refresh_object_explorer)

    main_window.minimize_action = QAction(get_icon("msc.chrome-minimize"), "Minimize", main_window)
    main_window.minimize_action.setShortcut("Ctrl+M")
    main_window.minimize_action.triggered.connect(main_window.showMinimized)

    main_window.maximize_action = QAction(get_icon("msc.chrome-maximize"), "Maximize", main_window)
    main_window.maximize_action.setShortcut("F11")
    main_window.maximize_action.triggered.connect(main_window.toggle_maximize)

    main_window.sqlite_help_action = QAction(QIcon("assets/sqlite.svg"), "SQLite Website", main_window)
    main_window.sqlite_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.sqlite.org/"))

    main_window.postgres_help_action = QAction(QIcon("assets/postgresql.svg"), "PostgreSQL Website", main_window)
    main_window.postgres_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.postgresql.org/"))

    main_window.oracle_help_action = QAction(QIcon("assets/oracle.svg"), "Oracle Website", main_window)
    main_window.oracle_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.oracle.com/database/"))

    main_window.about_action = QAction("About", main_window)
    main_window.about_action.triggered.connect(main_window.show_about_dialog)

    main_window.release_notes_action = QAction(
        get_icon("msc.book"),
        "Release Notes",
        main_window,
    )
    main_window.release_notes_action.triggered.connect(main_window.show_release_notes_dialog)

    main_window.technical_docs_action = QAction(
        get_icon("msc.mortar-board"),
        "Technical Documentation",
        main_window,
    )
    main_window.technical_docs_action.triggered.connect(main_window.show_technical_docs)

    main_window.format_sql_action = QAction(
        get_icon(AppIcons.FORMAT_SQL), "Format SQL", main_window
    )
    main_window.format_sql_action.setShortcut("Ctrl+Shift+F")
    main_window.format_sql_action.triggered.connect(main_window.format_sql_text)

    main_window.clear_query_action = QAction(get_icon("msc.clear-all"), "Clear Query", main_window)
    main_window.clear_query_action.setShortcuts(["Ctrl+Shift+C"]) # Removed F7 to prevent conflict with clear_all_action
    main_window.clear_query_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_window.clear_query_action.triggered.connect(main_window.clear_query_text)

    main_window.find_action = QAction(get_icon(AppIcons.FIND), "Find...", main_window)
    main_window.find_action.setShortcut("Ctrl+F")
    main_window.find_action.triggered.connect(lambda: main_window.open_find_dialog(False))

    main_window.replace_action = QAction(get_icon(AppIcons.REPLACE), "Replace...", main_window)
    main_window.replace_action.setShortcut("Ctrl+H")
    main_window.replace_action.triggered.connect(lambda: main_window.open_find_dialog(True))

    main_window.create_table_action = QAction(get_icon(AppIcons.TABLE), "Table...", main_window)
    main_window.create_table_action.triggered.connect(main_window._create_table_from_menu)

    main_window.create_view_action = QAction(get_icon(AppIcons.VIEW), "View...", main_window)
    main_window.create_view_action.triggered.connect(main_window._create_view_from_menu)

    main_window.delete_object_action = QAction(QIcon("assets/trash.svg"), "Delete/Drop...", main_window)

    main_window.query_tool_obj_action = QAction(QIcon("assets/sql_sheet_plus.svg"), "Query Tool", main_window)
    main_window.query_tool_obj_action.triggered.connect(main_window._query_tool_from_menu)
