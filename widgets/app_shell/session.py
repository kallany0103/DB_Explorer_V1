import json
import os


from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QWidget

from ui.feature_flags import (
    CONNECTOR_FEATURE_KEYS,
    is_feature_enabled,
    normalize_feature_flags,
)
from widgets.worksheet.code_editor import CodeEditor


def save_main_window_session(main_window, session_file):
    should_restore = bool(getattr(main_window, "restore_session_on_startup", True))
    if should_restore:
        main_window.connection_manager._save_tree_expansion_state()
        main_window.connection_manager._save_schema_tree_expansion_state()
    else:
        main_window.connection_manager._saved_tree_paths = []
        main_window.connection_manager._saved_selection_name = None
        main_window.connection_manager._schema_states = {}
    
    is_maximized = bool(
        getattr(main_window, "_is_maximized", False)
        or main_window.isMaximized()
        or main_window.isFullScreen()
    )
    pre_geom = getattr(main_window, "_pre_max_geometry", None)
    if is_maximized and pre_geom is not None:
        normal = pre_geom
    else:
        normal = main_window.normalGeometry()
    window_rect = [normal.x(), normal.y(), normal.width(), normal.height()]

    session_data = {
        "is_maximized": is_maximized,
        "window_geometry": main_window.saveGeometry().toBase64().data().decode(),
        "window_state": main_window.saveState().toBase64().data().decode(),
        "window_rect": window_rect,
        "pg_bin_path": getattr(main_window, "pg_bin_path", ""),
        "oracle_bin_path": getattr(main_window, "oracle_bin_path", ""),
        "use_wsl": getattr(main_window, "use_wsl", False),
        "wsl_distro": getattr(main_window, "wsl_distro", None),
        "theme": getattr(main_window, "theme", "Grey (Default)"),
        "default_connection_id": getattr(main_window, "default_connection_id", None),
        "confirm_tab_close": getattr(main_window, "confirm_tab_close", True),
        "restore_session_on_startup": should_restore,
        "editor_font_family": getattr(main_window, "editor_font_family", "Consolas"),
        "editor_font_size": getattr(main_window, "editor_font_size", 10),
        "editor_tab_size": getattr(main_window, "editor_tab_size", 4),
        "editor_word_wrap": getattr(main_window, "editor_word_wrap", False),
        "editor_line_numbers": getattr(main_window, "editor_line_numbers", True),
        "editor_auto_uppercase": getattr(main_window, "editor_auto_uppercase", True),
        "editor_autocomplete": getattr(main_window, "editor_autocomplete", True),
        "editor_highlight_line": getattr(main_window, "editor_highlight_line", True),
        "editor_keyword_casing": getattr(main_window, "editor_keyword_casing", "UPPERCASE"),
        "editor_identifier_casing": getattr(main_window, "editor_identifier_casing", "Preserve (As-is)"),
        "editor_auto_close_chars": getattr(main_window, "editor_auto_close_chars", True),
        "editor_auto_indent": getattr(main_window, "editor_auto_indent", True),
        "query_timeout_sec": getattr(main_window, "query_timeout_sec", 300),
        "default_row_limit": getattr(main_window, "default_row_limit", "No Limit"),
        "grid_null_text": getattr(main_window, "grid_null_text", "NULL"),
        "grid_datetime_format": getattr(main_window, "grid_datetime_format", "YYYY-MM-DD HH:mm:ss"),
        "grid_page_size": getattr(main_window, "grid_page_size", "100"),
        "grid_show_row_numbers": getattr(main_window, "grid_show_row_numbers", True),
        "grid_copy_headers": getattr(main_window, "grid_copy_headers", True),
        "ai_provider": getattr(main_window, "ai_provider", "OpenAI"),
        "ai_model": getattr(main_window, "ai_model", ""),
        "ai_api_key": getattr(main_window, "ai_api_key", ""),
        "ai_base_url": getattr(main_window, "ai_base_url", ""),
        "feature_flags": normalize_feature_flags(getattr(main_window, "feature_flags", None)),
        "saved_tree_paths": list(getattr(main_window.connection_manager, "_saved_tree_paths", [])) if should_restore else [],
        "saved_selection_name": getattr(main_window.connection_manager, "_saved_selection_name", None) if should_restore else None,
        "schema_states": getattr(main_window.connection_manager, "_schema_states", {}) if should_restore else {},
        "tabs": [],
    }

    if should_restore:
        for i in range(main_window.tab_widget.count()):
            tab = main_window.tab_widget.widget(i)
            tab_type = "worksheet"
            if tab.__class__.__name__ == "PropertiesWorkbench":
                tab_type = "properties"
            elif tab.__class__.__name__ == "StatisticsWorkbench":
                tab_type = "statistics"
            elif tab.__class__.__name__ == "ERDWidget":
                tab_type = "erd"
            elif tab.__class__.__name__ == "DashboardWidget":
                tab_type = "dashboard"
            elif tab.__class__.__name__ == "PSQLToolWidget":
                tab_type = "psql"
            elif tab.__class__.__name__ == "SQLPlusToolWidget":
                tab_type = "sqlplus"

            tab_data = {
                "title": main_window.tab_widget.tabText(i),
                "tab_type": tab_type,
            }

            if tab_type == "worksheet":
                editor = tab.findChild(CodeEditor, "query_editor")
                db_combo = tab.findChild(QComboBox, "db_combo_box")
                tab_data["sql_content"] = editor.toPlainText() if editor else ""
                tab_data["selected_connection_index"] = db_combo.currentIndex() if db_combo else 0
                tab_data["current_limit"] = getattr(tab, "current_limit", 0)
                tab_data["current_offset"] = getattr(tab, "current_offset", 0)
            elif tab_type in ("properties", "statistics"):
                # Try to save current object context
                tab_data["item_data"] = getattr(tab, "item_data", None)
                tab_data["obj_name"] = getattr(tab, "obj_name", None)
            elif tab_type in ("psql", "sqlplus"):
                c = getattr(tab, "_conn", {}) or {}
                tab_data["conn_id"] = c.get("id")
                tab_data["conn_name"] = c.get("name") or c.get("short_name") or ""
                tab_data["conn_host"] = c.get("host") or ""
                tab_data["database"] = (
                    getattr(tab, "_current_db", "")
                    or c.get("database")
                    or c.get("service_name")
                    or ""
                )

            session_data["tabs"].append(tab_data)

        session_data["active_tab_index"] = main_window.tab_widget.currentIndex()

    try:
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=4)
    except Exception as e:
        print(f"Error saving session: {e}")


def _find_connection_for_restore(conn_id, name="", host=""):
    try:
        import db
        hierarchical_data = db.get_hierarchy_data()
        for ctype in hierarchical_data:
            for group in ctype.get("usf_connection_groups", []):
                for conn in group.get("usf_connections", []):
                    if conn_id is not None and str(conn.get("id")) == str(conn_id):
                        return conn
                    if name and (conn.get("name") == name or conn.get("short_name") == name):
                        return conn
                    if host and conn.get("host") == host:
                        return conn
    except Exception as e:
        print(f"Error finding connection for restore: {e}")
    return None


def restore_main_window_session(main_window, session_file):
    if not os.path.exists(session_file):
        # First launch: no saved session — apply VS Code standard default geometry
        # (1200×800, centered on the primary screen).
        screen = (
            main_window.screen().availableGeometry()
            if main_window.screen()
            else QApplication.primaryScreen().availableGeometry()
        )
        default_w, default_h = 1200, 800
        x = screen.x() + (screen.width() - default_w) // 2
        y = screen.y() + (screen.height() - default_h) // 2
        main_window.setGeometry(x, y, default_w, default_h)
        main_window.add_tab()
        return

    try:
        with open(session_file, "r") as f:
            session_data = json.load(f)

        if session_data.get("window_rect"):
            x, y, w, h = session_data["window_rect"]
            main_window.setGeometry(x, y, w, h)
        elif "window_geometry" in session_data and hasattr(main_window, "restoreGeometry"):
            main_window.restoreGeometry(QByteArray.fromBase64(session_data["window_geometry"].encode()))
        if "window_state" in session_data and hasattr(main_window, "restoreState"):
            main_window.restoreState(QByteArray.fromBase64(session_data["window_state"].encode()))

        # Ensure window is visible on at least one screen and fully clamped
        window_rect = main_window.frameGeometry()
        intersecting_screen = None
        max_area = 0
        for screen in QApplication.screens():
            intersect = screen.availableGeometry().intersected(window_rect)
            area = intersect.width() * intersect.height()
            if area > max_area:
                max_area = area
                intersecting_screen = screen

        if not intersecting_screen or max_area == 0:
            # Completely off-screen, center it on the primary screen
            screen_geom = QApplication.primaryScreen().availableGeometry()
            default_w, default_h = 1200, 800
            x = screen_geom.x() + (screen_geom.width() - default_w) // 2
            y = screen_geom.y() + (screen_geom.height() - default_h) // 2
            main_window.setGeometry(x, y, default_w, default_h)
        else:
            screen_geom = intersecting_screen.availableGeometry()
            new_x = window_rect.x()
            new_y = window_rect.y()
            new_w = window_rect.width()
            new_h = window_rect.height()
            
            if new_w > screen_geom.width():
                new_w = screen_geom.width()
            if new_h > screen_geom.height():
                new_h = screen_geom.height()
                
            main_window.resize(new_w, new_h)
            
            if new_y < screen_geom.top():
                new_y = screen_geom.top()
            elif new_y + new_h > screen_geom.bottom():
                new_y = max(screen_geom.top(), screen_geom.bottom() - new_h)
                
            if new_x < screen_geom.left():
                new_x = screen_geom.left()
            elif new_x + new_w > screen_geom.right():
                new_x = max(screen_geom.left(), screen_geom.right() - new_w)
                
            main_window.move(new_x, new_y)

        if session_data.get("is_maximized"):
            main_window._pre_max_geometry = main_window.geometry()
            target_screen = (
                QApplication.screenAt(main_window.geometry().center())
                or intersecting_screen
                or QApplication.primaryScreen()
            )
            avail = target_screen.availableGeometry()
            if avail == target_screen.geometry():
                avail.setHeight(avail.height() - 1)
            main_window.setGeometry(avail)
            main_window._is_maximized = True
            if hasattr(main_window, "maximize_action"):
                main_window.maximize_action.setText("Restore")
            if hasattr(main_window, "_title_bar"):
                main_window._title_bar.update_maximize_button()
        else:
            main_window._is_maximized = False
            if hasattr(main_window, "maximize_action"):
                main_window.maximize_action.setText("Maximize")
            if hasattr(main_window, "_title_bar"):
                main_window._title_bar.update_maximize_button()
  
        main_window.pg_bin_path = session_data.get("pg_bin_path", "")
        main_window.oracle_bin_path = session_data.get("oracle_bin_path", "")
        main_window.use_wsl = session_data.get("use_wsl", False)
        main_window.wsl_distro = session_data.get("wsl_distro", None)
        main_window.theme = session_data.get("theme", "Grey (Default)")
        main_window.default_connection_id = session_data.get("default_connection_id", None)
        main_window.confirm_tab_close = session_data.get("confirm_tab_close", True)
        main_window.restore_session_on_startup = session_data.get("restore_session_on_startup", True)
        main_window.editor_font_family = session_data.get("editor_font_family", "Consolas")
        main_window.editor_font_size = session_data.get("editor_font_size", 10)
        main_window.editor_tab_size = session_data.get("editor_tab_size", 4)
        main_window.editor_word_wrap = session_data.get("editor_word_wrap", False)
        main_window.editor_line_numbers = session_data.get("editor_line_numbers", True)
        main_window.editor_auto_uppercase = session_data.get("editor_auto_uppercase", True)
        main_window.editor_autocomplete = session_data.get("editor_autocomplete", True)
        main_window.editor_highlight_line = session_data.get("editor_highlight_line", True)
        main_window.editor_keyword_casing = session_data.get("editor_keyword_casing", "UPPERCASE")
        main_window.editor_identifier_casing = session_data.get("editor_identifier_casing", "Preserve (As-is)")
        main_window.editor_auto_close_chars = session_data.get("editor_auto_close_chars", True)
        main_window.editor_auto_indent = session_data.get("editor_auto_indent", True)
        main_window.query_timeout_sec = session_data.get("query_timeout_sec", 300)
        main_window.default_row_limit = session_data.get("default_row_limit", "No Limit")
        main_window.grid_null_text = session_data.get("grid_null_text", "NULL")
        main_window.grid_datetime_format = session_data.get("grid_datetime_format", "YYYY-MM-DD HH:mm:ss")
        main_window.grid_page_size = session_data.get("grid_page_size", "100")
        main_window.grid_show_row_numbers = session_data.get("grid_show_row_numbers", True)
        main_window.grid_copy_headers = session_data.get("grid_copy_headers", True)
        main_window.ai_provider = session_data.get("ai_provider", "OpenAI")
        main_window.ai_model = session_data.get("ai_model", "")
        main_window.ai_api_key = session_data.get("ai_api_key", "")
        main_window.ai_base_url = session_data.get("ai_base_url", "")
        main_window.feature_flags = normalize_feature_flags(session_data.get("feature_flags"))

        if any(not main_window.feature_flags.get(key, True) for key in CONNECTOR_FEATURE_KEYS):
            main_window.connection_manager.load_data()

        should_restore = bool(main_window.restore_session_on_startup)

        if should_restore:
            main_window.connection_manager._saved_tree_paths = [tuple(p) for p in session_data.get("saved_tree_paths", [])]
            main_window.connection_manager._saved_selection_name = session_data.get("saved_selection_name", None)
            
            # Convert schema_states paths back to tuples and keys to int
            raw_schema_states = session_data.get("schema_states", {})
            processed_schema_states = {}
            for conn_id, state in raw_schema_states.items():
                try:
                    # Connection IDs are integers in DB but JSON makes them strings
                    parsed_conn_id = int(conn_id)
                except ValueError:
                    parsed_conn_id = conn_id
                    
                processed_state = {"paths": [], "selection": None}
                if "paths" in state:
                    processed_state["paths"] = [tuple(p) for p in state["paths"]]
                if "selection" in state and state["selection"] is not None:
                    processed_state["selection"] = tuple(state["selection"])
                processed_schema_states[parsed_conn_id] = processed_state
            
            main_window.connection_manager._schema_states = processed_schema_states
            main_window.connection_manager._restore_tree_expansion_state()

            # Trigger selection to load schema for the previously active connection
            selected_indexes = main_window.connection_manager.tree.selectionModel().selectedIndexes()
            if selected_indexes:
                main_window.connection_manager.item_clicked(selected_indexes[0])
        else:
            main_window.connection_manager._saved_tree_paths = []
            main_window.connection_manager._saved_selection_name = None
            main_window.connection_manager._schema_states = {}
            if hasattr(main_window, "connection_manager"):
                cm = main_window.connection_manager
                if hasattr(cm, "tree") and cm.tree:
                    cm.tree.collapseAll()
                    if cm.tree.selectionModel():
                        cm.tree.selectionModel().clearSelection()
                if hasattr(cm, "schema_tree") and cm.schema_tree:
                    cm.schema_tree.collapseAll()
                    if cm.schema_tree.selectionModel():
                        cm.schema_tree.selectionModel().clearSelection()
                if hasattr(cm, "schema_model") and cm.schema_model:
                    cm.schema_model.clear()
                    cm.schema_model.setHorizontalHeaderLabels(["Database Schema"])

        tabs = session_data.get("tabs", [])
        if not tabs or not should_restore:
            main_window.add_tab()
            if hasattr(main_window, "apply_feature_flags"):
                main_window.apply_feature_flags(refresh_connections=False)
            return

        for tab_data in tabs:
            QApplication.processEvents()  # keep splash responsive between restored tabs
            tab_type = tab_data.get("tab_type", "worksheet")
            
            if tab_type == "properties":
                if not is_feature_enabled(main_window, "object_inspector"):
                    continue
                main_window.add_properties_tab()
                current_tab = main_window.tab_widget.widget(main_window.tab_widget.count() - 1)
                item_data = tab_data.get("item_data")
                obj_name = tab_data.get("obj_name")
                if item_data and obj_name:
                    current_tab.update_view(item_data, obj_name)
            elif tab_type == "statistics":
                if not is_feature_enabled(main_window, "object_inspector"):
                    continue
                main_window.add_statistics_tab()
                current_tab = main_window.tab_widget.widget(main_window.tab_widget.count() - 1)
                item_data = tab_data.get("item_data")
                obj_name = tab_data.get("obj_name")
                if item_data and obj_name:
                    current_tab.update_view(item_data, obj_name)
            elif tab_type == "erd":
                if not is_feature_enabled(main_window, "erd_designer"):
                    continue
                main_window.add_erd_tab()
            elif tab_type == "dashboard":
                if not is_feature_enabled(main_window, "workspace_dashboard"):
                    continue
                main_window.add_dashboard_tab()
            elif tab_type == "psql":
                if not is_feature_enabled(main_window, "native_terminals"):
                    continue
                conn = _find_connection_for_restore(
                    tab_data.get("conn_id"),
                    tab_data.get("conn_name", ""),
                    tab_data.get("conn_host", ""),
                )
                if conn:
                    conn_copy = dict(conn)
                    if tab_data.get("database"):
                        conn_copy["database"] = tab_data["database"]
                        conn_copy["db"] = tab_data["database"]
                    from widgets.psql_tool.terminal_widget import open_psql_tool
                    open_psql_tool(conn_copy, getattr(main_window, "connection_manager", None))
            elif tab_type == "sqlplus":
                if not is_feature_enabled(main_window, "native_terminals"):
                    continue
                conn = _find_connection_for_restore(
                    tab_data.get("conn_id"),
                    tab_data.get("conn_name", ""),
                    tab_data.get("conn_host", ""),
                )
                if conn:
                    conn_copy = dict(conn)
                    if tab_data.get("database"):
                        conn_copy["service_name"] = tab_data["database"]
                        conn_copy["database"] = tab_data["database"]
                    from widgets.sqlplus_tool.terminal_widget import open_sqlplus_tool
                    open_sqlplus_tool(conn_copy, getattr(main_window, "connection_manager", None))
            else:
                main_window.add_tab()
                current_tab_index = main_window.tab_widget.count() - 1
                current_tab = main_window.tab_widget.widget(current_tab_index)

                editor = current_tab.findChild(CodeEditor, "query_editor")
                if editor:
                    editor.setPlainText(tab_data.get("sql_content", ""))

                db_combo = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo:
                    db_combo.blockSignals(True)
                    db_combo.setCurrentIndex(tab_data.get("selected_connection_index", 0))
                    db_combo.blockSignals(False)

                current_tab.current_limit = int(tab_data.get("current_limit", 0) or 0)
                current_tab.current_offset = tab_data.get("current_offset", 0)
                # --- Sync UI to restored state ---
                limit_val = current_tab.current_limit
                offset_val = current_tab.current_offset
                
                # 1. Sync Worksheet Limit Dropdown
                rows_limit_combo = current_tab.findChild(QWidget, "rows_limit_combo")
                if rows_limit_combo:
                    rows_limit_combo.blockSignals(True)
                    limit_str = str(limit_val) if limit_val > 0 else "No Limit"
                    rows_limit_combo.setCurrentText(limit_str)
                    rows_limit_combo.blockSignals(False)

                # 2. Sync Results View Label
                rows_info_label = current_tab.findChild(QLabel, "rows_info_label")
                if rows_info_label:
                    if limit_val > 0:
                        rows_info_label.setText(f"Limit: {limit_val} | Offset: {offset_val}")
                    else:
                        rows_info_label.setText("No Limit")

        if main_window.tab_widget.count() == 0:
            main_window.add_tab()

        # Apply restored editor preferences to all restored worksheet tabs
        if hasattr(main_window, "_apply_editor_preferences_to_all_tabs"):
            main_window._apply_editor_preferences_to_all_tabs()

        if hasattr(main_window, "apply_feature_flags"):
            main_window.apply_feature_flags(refresh_connections=False)

        active_idx = session_data.get("active_tab_index")
        if active_idx is not None and 0 <= active_idx < main_window.tab_widget.count():
            main_window.tab_widget.setCurrentIndex(active_idx)

    except Exception as e:
        print(f"Error restoring session: {e}")
        main_window.add_tab()