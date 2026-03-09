from PyQt6.QtGui import QAction, QIcon
import qtawesome as qta


def build_main_window_actions(main_window):
    main_window.open_file_action = QAction(qta.icon("mdi.folder", color="#333333"), "Open File", main_window)
    main_window.open_file_action.setShortcut("Ctrl+O")
    main_window.open_file_action.triggered.connect(main_window.open_sql_file)

    main_window.save_action = QAction("Save", main_window)
    main_window.save_action.setShortcut("Ctrl+S")
    main_window.save_action.triggered.connect(main_window.save_sql_file)

    main_window.save_as_action = QAction(qta.icon("mdi.save", color="#333333"), "Save As", main_window)
    main_window.save_as_action.setShortcut("Ctrl+Shift+S")
    main_window.save_as_action.triggered.connect(main_window.save_sql_file_as)

    main_window.exit_action = QAction(QIcon("assets/exit.svg"), "Exit", main_window)
    main_window.exit_action.setShortcut("Ctrl+Q")
    main_window.exit_action.triggered.connect(main_window.close)

    main_window.close_tab_action = QAction("Close", main_window)
    main_window.close_tab_action.setShortcut("Ctrl+W")
    main_window.close_tab_action.triggered.connect(main_window.close_current_tab)

    main_window.close_all_tabs_action = QAction("Close All", main_window)
    main_window.close_all_tabs_action.setShortcut("Ctrl+Shift+W")
    main_window.close_all_tabs_action.triggered.connect(main_window.close_all_tabs)

    main_window.execute_action = QAction(QIcon("assets/execute_icon.png"), "Execute", main_window)
    main_window.execute_action.setShortcuts(["Ctrl+Enter", "Ctrl+RETURN"])
    main_window.execute_action.triggered.connect(main_window.execute_query)

    main_window.execute_new_tab_action = QAction(QIcon("assets/execute_icon.png"), "Execute in New Output Tab", main_window)
    main_window.execute_new_tab_action.setShortcut("Ctrl+Shift+Enter")
    main_window.execute_new_tab_action.triggered.connect(main_window.execute_query_in_new_output_tab)

    main_window.explain_action = QAction(QIcon("assets/explain_icon.png"), "Explain", main_window)
    main_window.explain_action.setShortcut("Ctrl+E")
    main_window.explain_action.triggered.connect(main_window.explain_query)

    main_window.explain_analyze_action = QAction("Explain Analyze", main_window)
    main_window.explain_analyze_action.triggered.connect(main_window.explain_query)

    main_window.explain_plan_action = QAction("Explain (Plan)", main_window)
    main_window.explain_plan_action.triggered.connect(main_window.explain_plan_query)

    main_window.cancel_action = QAction(QIcon("assets/cancel_icon.png"), "Cancel", main_window)
    main_window.cancel_action.triggered.connect(main_window.cancel_current_query)
    main_window.cancel_action.setEnabled(False)

    main_window.undo_action = QAction(QIcon("assets/undo.svg"), "Undo", main_window)
    main_window.undo_action.setShortcut("Ctrl+Z")
    main_window.undo_action.triggered.connect(main_window.undo_text)

    main_window.redo_action = QAction(QIcon("assets/redo.svg"), "Redo", main_window)
    main_window.redo_action.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
    main_window.redo_action.triggered.connect(main_window.redo_text)

    main_window.cut_action = QAction(QIcon("assets/cut.svg"), "Cut", main_window)
    main_window.cut_action.setShortcut("Ctrl+X")
    main_window.cut_action.triggered.connect(main_window.cut_text)

    main_window.copy_action = QAction(QIcon("assets/copy.svg"), "Copy", main_window)
    main_window.copy_action.setShortcut("Ctrl+C")
    main_window.copy_action.triggered.connect(main_window.copy_text)

    main_window.paste_action = QAction(QIcon("assets/paste.svg"), "Paste", main_window)
    main_window.paste_action.setShortcut("Ctrl+V")
    main_window.paste_action.triggered.connect(main_window.paste_text)

    main_window.select_all_action = QAction(QIcon("assets/select_all.svg"), "Select ALL", main_window)
    main_window.select_all_action.setShortcut("Ctrl+A")
    main_window.select_all_action.triggered.connect(main_window.select_all_text)

    main_window.clear_all_action = QAction(QIcon("assets/trash.svg"), "Clear All", main_window)
    main_window.clear_all_action.setShortcut("F7")
    main_window.clear_all_action.triggered.connect(main_window.clear_query_text)

    main_window.goto_line_action = QAction(QIcon("assets/goto_line.svg"), "Goto Line", main_window)
    main_window.goto_line_action.setShortcut("Ctrl+G")
    main_window.goto_line_action.triggered.connect(main_window.goto_line)

    main_window.comment_block_action = QAction(QIcon("assets/comment.svg"), "Comment Block", main_window)
    main_window.comment_block_action.setShortcut("Ctrl+B")
    main_window.comment_block_action.triggered.connect(main_window.comment_block)

    main_window.uncomment_block_action = QAction(QIcon("assets/uncomment.svg"), "Uncomment Block", main_window)
    main_window.uncomment_block_action.setShortcut("Ctrl+Shift+B")
    main_window.uncomment_block_action.triggered.connect(main_window.uncomment_block)

    main_window.upper_case_action = QAction(QIcon("assets/uppercase.svg"), "Upper Case", main_window)
    main_window.upper_case_action.setShortcut("Ctrl+U")
    main_window.upper_case_action.triggered.connect(main_window.upper_case_text)

    main_window.lower_case_action = QAction(QIcon("assets/lowercase.svg"), "Lower Case", main_window)
    main_window.lower_case_action.setShortcut("Ctrl+L")
    main_window.lower_case_action.triggered.connect(main_window.lower_case_text)

    main_window.initial_caps_action = QAction("Initial Caps", main_window)
    main_window.initial_caps_action.setShortcut("Ctrl+I")
    main_window.initial_caps_action.triggered.connect(main_window.initial_caps_text)

    main_window.query_tool_action = QAction(QIcon("assets/sql_sheet_plus.svg"), "Query Tool", main_window)
    main_window.query_tool_action.setShortcut("Ctrl+T")
    main_window.query_tool_action.triggered.connect(main_window.add_tab)

    main_window.restore_action = QAction("Restore Layout", main_window)
    main_window.restore_action.triggered.connect(main_window.restore_tool)

    main_window.refresh_action = QAction("Refresh Explorer", main_window)
    main_window.refresh_action.triggered.connect(main_window.refresh_object_explorer)

    main_window.minimize_action = QAction("Minimize", main_window)
    main_window.minimize_action.setShortcut("Ctrl+M")
    main_window.minimize_action.triggered.connect(main_window.showMinimized)

    main_window.zoom_action = QAction("Zoom", main_window)
    main_window.zoom_action.triggered.connect(main_window.toggle_maximize)

    main_window.sqlite_help_action = QAction("SQLite Website", main_window)
    main_window.sqlite_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.sqlite.org/"))

    main_window.postgres_help_action = QAction("PostgreSQL Website", main_window)
    main_window.postgres_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.postgresql.org/"))

    main_window.oracle_help_action = QAction("Oracle Website", main_window)
    main_window.oracle_help_action.triggered.connect(lambda: main_window.open_help_url("https://www.oracle.com/database/"))

    main_window.about_action = QAction("About", main_window)
    main_window.about_action.triggered.connect(main_window.show_about_dialog)

    main_window.format_sql_action = QAction(QIcon("assets/format_icon.png"), "Format SQL", main_window)
    main_window.format_sql_action.setShortcut("Ctrl+Shift+F")
    main_window.format_sql_action.triggered.connect(main_window.format_sql_text)

    main_window.clear_query_action = QAction(QIcon("assets/delete_icon.png"), "Clear Query", main_window)
    main_window.clear_query_action.setShortcut("Ctrl+Shift+c")
    main_window.clear_query_action.triggered.connect(main_window.clear_query_text)

    main_window.create_table_action = QAction(QIcon("assets/table.svg"), "Table...", main_window)
    main_window.create_table_action.triggered.connect(main_window._create_table_from_menu)

    main_window.create_view_action = QAction(QIcon("assets/eye.svg"), "View...", main_window)
    main_window.create_view_action.triggered.connect(main_window._create_view_from_menu)

    main_window.delete_object_action = QAction(QIcon("assets/trash.svg"), "Delete/Drop...", main_window)

    main_window.query_tool_obj_action = QAction(QIcon("assets/sql_sheet_plus.svg"), "Query Tool", main_window)
    main_window.query_tool_obj_action.triggered.connect(main_window._query_tool_from_menu)
