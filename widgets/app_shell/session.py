import json
import os


from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QWidget

from widgets.worksheet.code_editor import CodeEditor


def save_main_window_session(main_window, session_file):
    main_window.connection_manager._save_tree_expansion_state()
    main_window.connection_manager._save_schema_tree_expansion_state()
    
    # On a frameless window (custom title bar) Qt enters WindowFullScreen on
    # maximize, so saveGeometry() would persist a full-screen rect and restore
    # the app full-screen on next launch. Save the normal geometry instead.
    window_rect = None
    if main_window.isMaximized() or main_window.isFullScreen():
        normal = main_window.normalGeometry()
        window_rect = [normal.x(), normal.y(), normal.width(), normal.height()]

    session_data = {
        "window_geometry": main_window.saveGeometry().toBase64().data().decode(),
        "window_state": main_window.saveState().toBase64().data().decode(),
        "window_rect": window_rect,
        "pg_bin_path": getattr(main_window, "pg_bin_path", ""),
        "use_wsl": getattr(main_window, "use_wsl", False),
        "theme": getattr(main_window, "theme", "Grey (Default)"),
        "saved_tree_paths": list(getattr(main_window.connection_manager, "_saved_tree_paths", [])),
        "saved_selection_name": getattr(main_window.connection_manager, "_saved_selection_name", None),
        "schema_states": getattr(main_window.connection_manager, "_schema_states", {}),
        "tabs": [],
    }

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

        session_data["tabs"].append(tab_data)

    try:
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=4)
    except Exception as e:
        print(f"Error saving session: {e}")


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
        elif "window_geometry" in session_data:
            main_window.restoreGeometry(QByteArray.fromBase64(session_data["window_geometry"].encode()))
        if "window_state" in session_data:
            main_window.restoreState(QByteArray.fromBase64(session_data["window_state"].encode()))
  
        main_window.pg_bin_path = session_data.get("pg_bin_path", "")
        main_window.use_wsl = session_data.get("use_wsl", False)
        main_window.theme = session_data.get("theme", "Grey (Default)")

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

        tabs = session_data.get("tabs", [])
        if not tabs:
            main_window.add_tab()
            return

        for tab_data in tabs:
            QApplication.processEvents()  # keep splash responsive between restored tabs
            tab_type = tab_data.get("tab_type", "worksheet")
            
            if tab_type == "properties":
                main_window.add_properties_tab()
                current_tab = main_window.tab_widget.widget(main_window.tab_widget.count() - 1)
                item_data = tab_data.get("item_data")
                obj_name = tab_data.get("obj_name")
                if item_data and obj_name:
                    current_tab.update_view(item_data, obj_name)
            elif tab_type == "statistics":
                main_window.add_statistics_tab()
                current_tab = main_window.tab_widget.widget(main_window.tab_widget.count() - 1)
                item_data = tab_data.get("item_data")
                obj_name = tab_data.get("obj_name")
                if item_data and obj_name:
                    current_tab.update_view(item_data, obj_name)
            elif tab_type == "erd":
                main_window.add_erd_tab()
            elif tab_type == "dashboard":
                main_window.add_dashboard_tab()
            else:
                main_window.add_tab()
                current_tab_index = main_window.tab_widget.count() - 1
                current_tab = main_window.tab_widget.widget(current_tab_index)

                editor = current_tab.findChild(CodeEditor, "query_editor")
                if editor:
                    editor.setPlainText(tab_data.get("sql_content", ""))

                db_combo = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo:
                    db_combo.setCurrentIndex(tab_data.get("selected_connection_index", 0))

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

        # Removed redundant session sanitization loop from the end of restore


    except Exception as e:
        print(f"Error restoring session: {e}")
        main_window.add_tab()