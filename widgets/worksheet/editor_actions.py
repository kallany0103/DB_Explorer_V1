import sqlparse

from PySide6.QtWidgets import (
    QMessageBox,
    QInputDialog,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QGridLayout,
)
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt, Signal


class FindReplaceDialog(QDialog):
    find_next = Signal(str, bool, bool)
    find_previous = Signal(str, bool, bool)
    replace = Signal(str, str, bool, bool)
    replace_all = Signal(str, str, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(False)
        self.resize(380, 250)
        self._apply_styles()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title/Header
        header_title = QLabel("Find and Replace")
        header_title.setObjectName("dialogTitle")
        layout.addWidget(header_title)

        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(10)
        grid_layout.setHorizontalSpacing(10)

        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        grid_layout.addWidget(self.find_label, 0, 0)
        grid_layout.addWidget(self.find_input, 0, 1)

        self.replace_label = QLabel("Replace with:")
        self.replace_input = QLineEdit()
        grid_layout.addWidget(self.replace_label, 1, 0)
        grid_layout.addWidget(self.replace_input, 1, 1)

        layout.addLayout(grid_layout)

        options_layout = QHBoxLayout()
        self.case_check = QCheckBox("Case Sensitive")
        self.whole_word_check = QCheckBox("Whole Word")
        options_layout.addWidget(self.case_check)
        options_layout.addWidget(self.whole_word_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        btn_layout = QGridLayout()
        btn_layout.setSpacing(8)

        self.btn_find_next = QPushButton("Find Next")
        self.btn_find_prev = QPushButton("Find Previous")
        self.btn_replace = QPushButton("Replace")
        self.btn_replace_all = QPushButton("Replace All")
        
        self.btn_find_next.setObjectName("secondaryButton")
        self.btn_find_prev.setObjectName("secondaryButton")
        self.btn_replace.setObjectName("secondaryButton")
        self.btn_replace_all.setObjectName("secondaryButton")

        btn_layout.addWidget(self.btn_find_next, 0, 0)
        btn_layout.addWidget(self.btn_find_prev, 0, 1)
        btn_layout.addWidget(self.btn_replace, 1, 0)
        btn_layout.addWidget(self.btn_replace_all, 1, 1)

        layout.addLayout(btn_layout)
        
        # Bottom Close Button (matches primary style as it's the main exit)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("primaryButton")
        layout.addWidget(self.btn_close)

        self.btn_find_next.clicked.connect(self.on_find_next)
        self.btn_find_prev.clicked.connect(self.on_find_prev)
        self.btn_replace.clicked.connect(self.on_replace)
        self.btn_replace_all.clicked.connect(self.on_replace_all)
        self.btn_close.clicked.connect(self.close)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f6f8fb;
            }
            QLabel#dialogTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
                margin-bottom: 5px;
            }
            QLabel {
                color: #374151;
                font-size: 9pt;
            }
            QLineEdit {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                background: white;
                padding: 2px 8px;
                color: #1f2937;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QCheckBox {
                color: #374151;
                font-size: 9pt;
            }
            QPushButton {
                min-height: 30px;
                padding: 2px 12px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 4px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton#primaryButton {
                border: 1px solid #006cbe;
                background-color: #0078d4;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #006cbe;
            }
        """)

    def on_find_next(self):
        text = self.find_input.text()
        if text:
            self.find_next.emit(text, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_find_prev(self):
        text = self.find_input.text()
        if text:
            self.find_previous.emit(text, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_replace(self):
        target = self.find_input.text()
        replacement = self.replace_input.text()
        if target:
            self.replace.emit(target, replacement, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def on_replace_all(self):
        target = self.find_input.text()
        replacement = self.replace_input.text()
        if target:
            self.replace_all.emit(target, replacement, self.case_check.isChecked(), self.whole_word_check.isChecked())

    def set_find_text(self, text):
        self.find_input.setText(text)
        self.find_input.selectAll()
        self.find_input.setFocus()


def format_sql_text(manager):
    editor = manager._get_current_editor()
    if not editor:
        QMessageBox.warning(manager, "Warning", "No active query editor found.")
        return

    cursor = editor.textCursor()

    if cursor.hasSelection():
        raw_sql = cursor.selectedText()
        raw_sql = raw_sql.replace("\u2029", "\n")
        mode = "selection"
    else:
        raw_sql = editor.toPlainText()
        mode = "full"

    if not raw_sql.strip():
        return

    try:
        formatted_sql = sqlparse.format(
            raw_sql,
            reindent=True,
            keyword_case="upper",
            identifier_case=None,
            strip_comments=False,
            indent_width=1,
            comma_first=False,
        )

        formatted_sql = formatted_sql.replace("SELECT\n  *", "SELECT  *")
        formatted_sql = formatted_sql.replace("FROM\n  ", "FROM ")
        formatted_sql = formatted_sql.replace(";", "\n;")

        if mode == "selection":
            cursor.beginEditBlock()
            cursor.insertText(formatted_sql)
            cursor.endEditBlock()
        else:
            scroll_pos = editor.verticalScrollBar().value()
            editor.setPlainText(formatted_sql)
            editor.verticalScrollBar().setValue(scroll_pos)
            editor.moveCursor(cursor.MoveOperation.End)

        manager.status.showMessage("SQL formatted successfully.", 3000)

    except ImportError:
        QMessageBox.critical(manager, "Error", "Library 'sqlparse' is missing.\\nPlease run: pip install sqlparse")
    except Exception as error:
        QMessageBox.warning(manager, "Formatting Error", f"Error: {error}")


def clear_query_text(manager):
    editor = manager._get_current_editor()
    if editor:
        if editor.toPlainText().strip():
            reply = QMessageBox.question(
                manager,
                "Clear Query",
                "Are you sure you want to clear the editor?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        editor.clear()
        editor.setFocus()
        editor.setFocus()
        manager.status.showMessage("Editor cleared.", 3000)


def undo_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.undo()


def redo_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.redo()


def cut_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.cut()


def copy_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.copy()


def paste_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.paste()


def delete_text(manager):
    editor = manager._get_current_editor()
    if editor:
        editor.textCursor().removeSelectedText()


def go_to_line(manager):
    editor = manager._get_current_editor()
    if editor:
        line, ok = QInputDialog.getInt(manager, "Go to Line", "Line Number:", 1, 1, editor.blockCount())
        if ok:
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line - 1)
            editor.setTextCursor(cursor)
            editor.centerCursor()
