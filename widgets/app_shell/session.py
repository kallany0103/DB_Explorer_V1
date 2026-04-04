import json
import os

# from PyQt6.QtCore import QByteArray
# from PyQt6.QtWidgets import QComboBox

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QComboBox

from widgets.worksheet.code_editor import CodeEditor


def save_main_window_session(main_window, session_file):
    session_data = {
        "window_geometry": main_window.saveGeometry().toBase64().data().decode(),
        "window_state": main_window.saveState().toBase64().data().decode(),
        "tabs": [],
    }

    for i in range(main_window.tab_widget.count()):
        tab = main_window.tab_widget.widget(i)
        editor = tab.findChild(CodeEditor, "query_editor")
        db_combo = tab.findChild(QComboBox, "db_combo_box")

        tab_data = {
            "title": main_window.tab_widget.tabText(i),
            "sql_content": editor.toPlainText() if editor else "",
            "selected_connection_index": db_combo.currentIndex() if db_combo else 0,
            "current_limit": getattr(tab, "current_limit", 0),
            "current_offset": getattr(tab, "current_offset", 0),
        }
        session_data["tabs"].append(tab_data)

    try:
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=4)
    except Exception as e:
        print(f"Error saving session: {e}")


def restore_main_window_session(main_window, session_file):
    if not os.path.exists(session_file):
        main_window.add_tab()
        return

    try:
        with open(session_file, "r") as f:
            session_data = json.load(f)

        if "window_geometry" in session_data:
            main_window.restoreGeometry(QByteArray.fromBase64(session_data["window_geometry"].encode()))
        if "window_state" in session_data:
            main_window.restoreState(QByteArray.fromBase64(session_data["window_state"].encode()))

        tabs = session_data.get("tabs", [])
        if not tabs:
            main_window.add_tab()
            return

        for tab_data in tabs:
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

        try:
            with open(session_file, "w") as f:
                sanitized = {
                    "window_geometry": main_window.saveGeometry().toBase64().data().decode(),
                    "window_state": main_window.saveState().toBase64().data().decode(),
                    "tabs": [],
                }
                for i in range(main_window.tab_widget.count()):
                    tab = main_window.tab_widget.widget(i)
                    editor = tab.findChild(CodeEditor, "query_editor")
                    db_combo = tab.findChild(QComboBox, "db_combo_box")
                    sanitized["tabs"].append(
                        {
                            "title": main_window.tab_widget.tabText(i),
                            "sql_content": editor.toPlainText() if editor else "",
                            "selected_connection_index": db_combo.currentIndex() if db_combo else 0,
                            "current_limit": getattr(tab, "current_limit", 0),
                            "current_offset": getattr(tab, "current_offset", 0),
                        }
                    )
                json.dump(sanitized, f, indent=4)
        except Exception:
            pass

    except Exception as e:
        print(f"Error restoring session: {e}")
        main_window.add_tab()
