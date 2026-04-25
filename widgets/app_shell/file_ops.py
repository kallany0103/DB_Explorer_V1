#from PyQt6.QtCore import QDir
#from PyQt6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QStackedWidget
from PySide6.QtCore import QDir
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QStackedWidget

from widgets.worksheet.editor_actions import FindReplaceDialog
import re
import os


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
    """Auto-save using table name without dialog if possible."""
    editor = main_window._get_current_editor()
    if not editor:
        return

    content = editor.toPlainText()
    filename = _get_default_sql_filename(main_window, content)
    
    # Save to Desktop directory
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    save_path = os.path.join(desktop_path, filename)
    
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        main_window.status.showMessage(f"Auto-saved to Desktop: {filename}", 5000)
    except Exception as e:
        # Fallback to Save As if direct save fails
        save_sql_file_as(main_window)


def save_sql_file_as(main_window):
    """Manual save with name change possibility."""
    editor = main_window._get_current_editor()
    if not editor:
        QMessageBox.warning(main_window, "Error", "No active query editor to save from.")
        return

    content = editor.toPlainText()
    filename = _get_default_sql_filename(main_window, content)
    
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
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
