from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QStackedWidget, QProgressDialog
from PySide6.QtCore import QObject, QRunnable, Signal, Qt, QTimer
from workers.connection_workers import ImportConnectionsWorker
from widgets.worksheet.editor_actions import FindReplaceDialog
import re
import os
import json
from db.db_retrieval import get_hierarchy_data
from db.db_modifications import add_connection
from db.db_connections import DB_FILE, get_downloads_dir
import sqlite3
    

def open_sql_file(main_window):
    file_name, _ = QFileDialog.getOpenFileName(
        main_window, 
        "Open File", 
        "", 
        "Supported Files (*.sql *.erd);;SQL Files (*.sql);;ERD Files (*.erd);;All Files (*)"
    )
    if not file_name:
        return

    if file_name.endswith('.erd'):
        main_window.add_erd_tab()
        current_tab = main_window.tab_widget.currentWidget()
        if hasattr(current_tab, "load_erd_file"):
            current_tab.load_erd_file(file_name)
        main_window.status.showMessage(f"ERD File opened: {file_name}", 3000)
    else:
        editor = main_window._get_current_editor()

        if not editor:
            current_tab = main_window.tab_widget.currentWidget()
            if not current_tab:
                main_window.add_tab()
                current_tab = main_window.tab_widget.currentWidget()
            editor_stack = current_tab.findChild(QStackedWidget, "editor_stack")
            if editor_stack and editor_stack.currentIndex() != 0:
                editor_stack.setCurrentIndex(0)
                query_view_btn = current_tab.findChild(QPushButton, "Query")
                history_view_btn = current_tab.findChild(QPushButton, "Query History")
                if query_view_btn:
                    query_view_btn.setChecked(True)
                if history_view_btn:
                    history_view_btn.setChecked(False)

            editor = main_window._get_current_editor()
            if not editor:
                QMessageBox.warning(main_window, "Error", "Could not find a query editor to open the file into.")
                return

        try:
            with open(file_name, "r", encoding="utf-8") as f:
                content = f.read()
                editor.setPlainText(content)
                editor.current_file_path = file_name
                main_window.status.showMessage(f"File opened: {file_name}", 3000)
        except Exception as e:
            QMessageBox.critical(main_window, "Error", f"Could not read file:\n{e}")

def _get_default_sql_filename(main_window, content):
    """Helper to determine the default filename from tab or content."""
    current_tab = main_window.tab_widget.currentWidget()
    default_filename = "query"
    
    if hasattr(current_tab, 'table_name') and current_tab.table_name:
        default_filename = current_tab.table_name
    else:
        table_match = re.search(r'(?i)(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([a-zA-Z0-9_\.\"\'\[\]\.]+)', content)
        if table_match:
            table_name = table_match.group(1).strip()
            # Clean up quotes and take the last part of a multipart name (schema.table)
            table_name = table_name.strip('\"\'[]').split('.')[-1]
            if table_name:
                default_filename = table_name

    # Ensure no extension in name for base
    if default_filename.lower().endswith('.sql'):
        default_filename = default_filename[:-4]
        
    return f"{default_filename}.sql"

def save_sql_file(main_window):
    """Save to the current file path, or fallback to Save As if not set."""
    editor = main_window._get_current_editor()
    if not editor:
        return

    content = editor.toPlainText()
    save_path = getattr(editor, 'current_file_path', None)

    if not save_path:
        save_sql_file_as(main_window)
        return

    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        main_window.status.showMessage(f"File saved: {save_path}", 5000)
    except Exception:
        save_sql_file_as(main_window)


def save_sql_file_as(main_window):
    """Manual save with name change possibility."""
    editor = main_window._get_current_editor()
    if not editor:
        QMessageBox.warning(main_window, "Error", "No active query editor to save from.")
        return

    content = editor.toPlainText()
    
    # Check if there's an existing path to suggest
    default_path = getattr(editor, 'current_file_path', None)
    if not default_path:
        filename = _get_default_sql_filename(main_window, content)
        desktop_path = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        default_path = os.path.join(desktop_path, filename)

    file_name, _ = QFileDialog.getSaveFileName(
        main_window,
        "Save SQL File As",
        default_path,
        "SQL Files (*.sql);;All Files (*)",
    )

    if file_name:
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(content)
            editor.current_file_path = file_name
            main_window.status.showMessage(f"File saved: {file_name}", 3000)
        except Exception as e:
            QMessageBox.critical(main_window, "Error", f"Could not save file:\n{e}")


def open_find_dialog(main_window, replace=False):
    editor = main_window._get_current_editor()
    if not editor:
        return

    if not hasattr(main_window, "find_replace_dialog"):
        main_window.find_replace_dialog = FindReplaceDialog(main_window)
        main_window.find_replace_dialog.find_next.connect(lambda t, c, w: on_find_next(main_window, t, c, w))
        main_window.find_replace_dialog.find_previous.connect(lambda t, c, w: on_find_prev(main_window, t, c, w))
        main_window.find_replace_dialog.replace.connect(lambda t, r, c, w: on_replace(main_window, t, r, c, w))
        main_window.find_replace_dialog.replace_all.connect(lambda t, r, c, w: on_replace_all(main_window, t, r, c, w))

    cursor = editor.textCursor()
    if cursor.hasSelection():
        main_window.find_replace_dialog.set_find_text(cursor.selectedText())

    main_window.find_replace_dialog.show()
    main_window.find_replace_dialog.raise_()
    main_window.find_replace_dialog.activateWindow()

    if replace:
        main_window.find_replace_dialog.replace_input.setFocus()
    else:
        main_window.find_replace_dialog.find_input.setFocus()


def on_find_next(main_window, text, case, whole):
    editor = main_window._get_current_editor()
    if editor:
        found = editor.find(text, case, whole, True)
        if not found:
            main_window.status.showMessage(f"Text '{text}' not found.", 2000)


def on_find_prev(main_window, text, case, whole):
    editor = main_window._get_current_editor()
    if editor:
        found = editor.find(text, case, whole, False)
        if not found:
            main_window.status.showMessage(f"Text '{text}' not found.", 2000)


def on_replace(main_window, target, replacement, case, whole):
    editor = main_window._get_current_editor()
    if editor:
        editor.replace_curr(target, replacement, case, whole)


def on_replace_all(main_window, target, replacement, case, whole):
    editor = main_window._get_current_editor()
    if editor:
        count = editor.replace_all(target, replacement, case, whole)
        main_window.status.showMessage(f"Replaced {count} occurrences.", 3000)


def export_connections(main_window):
    
    file_name, _ = QFileDialog.getSaveFileName(
        main_window,
        "Export Connections",
        os.path.join(get_downloads_dir(), "connections.json"),
        "JSON Files (*.json);;All Files (*)",
    )
    if not file_name:
        return

    try:
        data = get_hierarchy_data()
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        main_window.status.showMessage(f"Connections exported to: {file_name}", 5000)
        QMessageBox.information(main_window, "Success", f"Connections successfully exported to:\n{file_name}")
    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"Failed to export connections:\n{e}")

def import_connections(main_window):
    file_name, _ = QFileDialog.getOpenFileName(
        main_window,
        "Import Connections",
        "",
        "JSON Files (*.json);;All Files (*)",
    )
    if not file_name:
        return

    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        progress = QProgressDialog("Importing connections...", "Cancel", 0, 0, main_window)
        progress.setWindowTitle("Importing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()

        worker = ImportConnectionsWorker(data)
        main_window._active_import_worker = worker # Prevent GC crash

        def on_finished(hierarchy_data):
            progress.accept()
            main_window._active_import_worker = None

            def _step1_rebuild():
                cm = getattr(main_window, 'connection_manager', None)
                if not cm:
                    main_window.status.showMessage("Connections imported successfully.", 5000)
                    QMessageBox.information(main_window, "Success", "Connections imported successfully.")
                    return
            
                cm._save_tree_expansion_state()
                tree = cm.tree
                tree.setUpdatesEnabled(False)
                try:
                    cm.load_data(hierarchical_data=hierarchy_data)
                    cm._restore_tree_expansion_state()
                finally:
                    tree.setUpdatesEnabled(True)
                main_window.status.showMessage("Connections imported successfully.", 5000)
                QMessageBox.information(main_window, "Success", "Connections imported successfully.")
                
                QTimer.singleShot(0, cm.refresh_all_comboboxes)

            QTimer.singleShot(0, _step1_rebuild)

        def on_error(err_msg):
            progress.accept()
            QMessageBox.critical(main_window, "Error", f"Failed to import connections:\n{err_msg}")
            main_window._active_import_worker = None

        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        
        main_window.thread_pool.start(worker)

    except Exception as e:
        QMessageBox.critical(main_window, "Error", f"Failed to read file:\n{e}")
