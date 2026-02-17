import sys
import os
import time
import datetime
import re
import pandas as pd
import sqlparse
import sqlite3 as sqlite
import psycopg2
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableView, QMessageBox,
    QMenu, QComboBox, QLineEdit, QToolButton, QStackedWidget, QTextEdit,
    QLabel, QPushButton, QApplication, QHeaderView, QAbstractItemView, QPlainTextEdit,
    QDialog, QFileDialog, QButtonGroup, QSizePolicy, QFormLayout, QSpinBox, QDialogButtonBox, QFrame, QTreeView, QGroupBox, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QObject, QTimer, QSize, QSortFilterProxyModel, pyqtSignal, QEvent
)
from PyQt6.QtGui import (
    QAction, QColor, QBrush, QStandardItemModel, QStandardItem, QMovie, QFont, QIcon, QKeySequence, QShortcut
)

import db
from code_editor import CodeEditor
from .explain_visualizer import ExplainVisualizer
from .results_view import ResultsManager
from workers import RunnableQuery, RunnableExportFromModel, QuerySignals
from dialogs import ExportDialog

class WorksheetManager(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.thread_pool = main_window.thread_pool
        self.status_message_label = main_window.status_message_label
        self.cancel_action = main_window.cancel_action
        self.open_file_action = main_window.open_file_action
        self.save_as_action = main_window.save_as_action
        self.execute_action = main_window.execute_action
        
        # Initialize helpers
        self.results_manager = ResultsManager(main_window)
        
        # State
        self.tab_timers = {}
        self.running_queries = {}
        self.QUERY_TIMEOUT = 300000

    def _get_current_editor(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab: return None
        return current_tab.findChild(CodeEditor, "query_editor")

    def create_vertical_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #D3D3D3;")
        return line

    def format_sql_text(self):
        editor = self._get_current_editor()
        if not editor:
            QMessageBox.warning(self, "Warning", "No active query editor found.")
            return

        cursor = editor.textCursor()
        
        if cursor.hasSelection():
            raw_sql = cursor.selectedText()
            raw_sql = raw_sql.replace('\u2029', '\n') 
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
                keyword_case='upper',   
                identifier_case=None,   
                strip_comments=False,   
                indent_width=1,         
                comma_first=False       
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

            self.status.showMessage("SQL formatted successfully.", 3000)

        except ImportError:
             QMessageBox.critical(self, "Error", "Library 'sqlparse' is missing.\\nPlease run: pip install sqlparse")
        except Exception as e:
            QMessageBox.warning(self, "Formatting Error", f"Error: {e}")


    def clear_query_text(self):
        editor = self._get_current_editor()
        if editor:
            if editor.toPlainText().strip():
                reply = QMessageBox.question(
                    self, "Clear Query", 
                    "Are you sure you want to clear the editor?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            editor.clear()
            editor.setFocus()
            editor.setFocus()
            self.status.showMessage("Editor cleared.", 3000)


    def undo_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.undo()

    def redo_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.redo()

    def cut_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.cut()

    def copy_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.copy()

    def paste_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.paste()

    def delete_text(self):
        editor = self._get_current_editor()
        if editor:
            editor.textCursor().removeSelectedText()


    def open_limit_offset_dialog(self, tab_content):
        """Opens a dialog to set Limit and Offset like pgAdmin."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Query Options")
        dialog.setFixedSize(300, 150)
        
        layout = QFormLayout(dialog)

        # Limit Input
        limit_spin = QSpinBox()
        limit_spin.setRange(0, 999999999) # 0 means no limit (logic handled below)
        limit_spin.setValue(getattr(tab_content, 'current_limit', 1000))
        limit_spin.setSpecialValueText("No Limit") # If value is 0
        layout.addRow("Rows Limit:", limit_spin)

        # Offset Input
        offset_spin = QSpinBox()
        offset_spin.setRange(0, 999999999)
        offset_spin.setValue(getattr(tab_content, 'current_offset', 0))
        layout.addRow("Start Row (Offset):", offset_spin)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update values in tab object
            new_limit = limit_spin.value()
            new_offset = offset_spin.value()
            
            tab_content.current_limit = new_limit if new_limit > 0 else None
            tab_content.current_offset = new_offset
            
            # Refresh Display Label (Optional immediate update)
            rows_info_label = tab_content.findChild(QLabel, "rows_info_label")
            if rows_info_label:
                limit_text = str(new_limit) if new_limit > 0 else "All"
                rows_info_label.setText(f"Settings: Limit {limit_text}, Offset {new_offset}")

            # Execute Query with new settings
            self.execute_query()

    def close_tab(self, index):
        if index < 0:
            index = self.tab_widget.currentIndex()
        if index >= 0 and self.tab_widget.count() > 0:
            widget = self.tab_widget.widget(index)
            if widget:
                self.tab_widget.removeTab(index)
                widget.deleteLater()
            
            if self.tab_widget.count() == 0:
                self.add_tab()
            
            self.renumber_tabs()


    def add_tab(self):
        tab_content = QWidget(self.tab_widget)
        # --- Initialize tab specific limit and offset settings ---
        tab_content.current_limit = 1000  # Default Limit
        tab_content.current_offset = 0    # Default Offset
        tab_content.current_page = 1
        tab_content.has_more_pages = True
        layout = QVBoxLayout(tab_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        font = QFont()
        font.setBold(True)
        # 1. Database Selection Combo Box
        db_combo_box = QComboBox()
        db_combo_box.setObjectName("db_combo_box")
        layout.addWidget(db_combo_box)
        self.load_joined_connections(db_combo_box)
        db_combo_box.currentIndexChanged.connect(lambda: self.refresh_processes_view())

        # 2. Tab-specific Toolbar (Top)
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("tab_toolbar")
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)
        toolbar_layout.setSpacing(5)

        # --- Group A: File Actions ---
        btn_style = (
            "QToolButton, QPushButton, QComboBox { "
            "padding: 1px 8px; border: 1px solid #cccccc; "
            "background-color: #ffffff; border-radius: 4px; "
            "font-size: 9pt; color: #333333; "
            "} "
            "QToolButton:hover, QPushButton:hover, QComboBox:hover { "
            "background-color: #f0f2f5; border-color: #adb5bd; "
            "} "
            "QToolButton:pressed, QPushButton:pressed, QComboBox:on { "
            "background-color: #e8eaed; "
            "} "
            "QComboBox::drop-down { "
            "border: none; border-left: 1px solid #dddfe2; "
            "width: 24px; "
            "border-top-right-radius: 4px; "
            "border-bottom-right-radius: 4px; "
            "} "
            "QComboBox::drop-down:hover { "
            "background-color: #e4e6e9; "
            "} "
            "QComboBox::down-arrow { "
            "image: url(assets/chevron-down.svg); "
            "width: 10px; height: 10px; "
            "} "
        )
        
        open_btn = QToolButton()
        open_btn.setDefaultAction(self.open_file_action)
        open_btn.setIconSize(QSize(16, 16))
        open_btn.setFixedHeight(26)
        open_btn.setMinimumWidth(26)
        open_btn.setToolTip("Open SQL File")
        open_btn.setStyleSheet(btn_style)
        toolbar_layout.addWidget(open_btn)

        save_btn = QToolButton()
        save_btn.setDefaultAction(self.save_as_action)
        save_btn.setIconSize(QSize(16, 16))
        save_btn.setFixedHeight(26)
        save_btn.setMinimumWidth(26)
        save_btn.setToolTip("Save SQL File")
        save_btn.setStyleSheet(btn_style)
        toolbar_layout.addWidget(save_btn)
        
        toolbar_layout.addWidget(self.create_vertical_separator())

        # --- Group B: Execution & Edit Actions ---
        exec_btn = QToolButton()
        exec_btn.setDefaultAction(self.execute_action)
        exec_btn.setIconSize(QSize(16, 16))
        exec_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        exec_btn.setFixedHeight(26)
        exec_btn.setStyleSheet(btn_style)
        toolbar_layout.addWidget(exec_btn)
        cancel_btn = QToolButton()
        cancel_btn.setDefaultAction(self.cancel_action)
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        cancel_btn.setFixedHeight(26)
        cancel_btn.setStyleSheet(btn_style)
        toolbar_layout.addWidget(cancel_btn)

# {siam}
        # --- Explain Combo (Replaces Split Button) ---
        explain_combo = QComboBox()
        explain_combo.setFixedHeight(26)
        explain_combo.setFixedWidth(135)
        explain_combo.setStyleSheet(btn_style)
        
        # Items
        explain_combo.addItem(QIcon("assets/explain_icon.png"), "Explain Analyze")
        explain_combo.addItem(QIcon("assets/explain_icon.png"), "Explain (Plan)")
        
        def on_explain_activated(index):
            if index == 0:
                self.explain_query()
            else:
                self.explain_plan_query()
        
        explain_combo.activated.connect(on_explain_activated)
        toolbar_layout.addWidget(explain_combo)
# {siam}

        # --- Edit Button (Replaces ComboBox) ---
        edit_btn = QToolButton()
        edit_btn.setText("Edit")
        edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        edit_btn.setFixedHeight(26)
        edit_btn.setFixedWidth(85)
        edit_btn.setStyleSheet(btn_style + """
            QToolButton::menu-indicator {
                border-left: 1px solid #dddfe2;
                width: 20px;
                image: url(assets/chevron-down.svg);
                subcontrol-origin: padding;
                subcontrol-position: right center;
                margin-left: 4px;
            }
        """)
        edit_btn.setToolTip("Edit Operations")
        edit_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        edit_menu = QMenu(self)
        edit_menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #cccccc; }
            QMenu::item { padding: 5px 20px 5px 10px; min-width: 250px; }
            QMenu::item:selected { background-color: #f0f2f5; color: #333333; }
            QMenu::separator { height: 1px; background: #eeeeee; margin: 2px 0px; }
        """)

        # Helper to add actions
        def add_menu_action(text, shortcut=None, icon=None, func=None):
            action = QAction(text, self)
            if icon: 
                action.setIcon(QIcon(icon))
                action.setIconVisibleInMenu(False)
            if shortcut: action.setShortcut(QKeySequence(shortcut))
            if func: action.triggered.connect(func)
            edit_menu.addAction(action)
            return action

        def go_to_line():
            editor = self._get_current_editor()
            if editor:
                line, ok = QInputDialog.getInt(self, "Go to Line", "Line Number:", 1, 1, editor.blockCount())
                if ok:
                    cursor = editor.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line - 1)
                    editor.setTextCursor(cursor)
                    editor.centerCursor()

        # Actions matching original functionality
        add_menu_action("Find", "Ctrl+F", "assets/search.svg", lambda: self.open_find_dialog(False))
        add_menu_action("Replace", "Ctrl+Alt+F", "assets/refresh.svg", lambda: self.open_find_dialog(True))
        add_menu_action("Go to Line/Column", "Ctrl+L", None, go_to_line)
        edit_menu.addSeparator() 
        add_menu_action("Indent Selection", "Tab", None, lambda: self._get_current_editor() and self._get_current_editor().indent_selection())
        add_menu_action("Unindent Selection", "Shift+Tab", None, lambda: self._get_current_editor() and self._get_current_editor().unindent_selection())
        add_menu_action("Toggle Comment", "Ctrl+/", None, lambda: self._get_current_editor() and self._get_current_editor().toggle_comment())
        add_menu_action("Toggle Case of Selected Text", "Ctrl+Shift+U", None, lambda: self._get_current_editor() and self._get_current_editor().toggle_case())
        edit_menu.addSeparator()
        add_menu_action("Clear Query", "Ctrl+Alt+L", "assets/delete_icon.png", self.clear_query_text)
        add_menu_action("Format SQL", "Ctrl+K", "assets/format_icon.png", self.format_sql_text)

        edit_btn.setMenu(edit_menu)
        toolbar_layout.addWidget(edit_btn)
        
        # Shortcuts are already handled by the QActions in the menu if properly set, 
        # but adding QShortcuts for current tab to ensure they work even when menu is closed.
        # Actually QActions in a menu on a QMainWindow/Widget usually work as global shortcuts.
        
        # Ensure shortcuts work globally for this tab/window
        QShortcut(QKeySequence("Ctrl+F"), tab_content, lambda: self.open_find_dialog(False))
        QShortcut(QKeySequence("Ctrl+Alt+F"), tab_content, lambda: self.open_find_dialog(True))
        QShortcut(QKeySequence("Ctrl+L"), tab_content, go_to_line)
        QShortcut(QKeySequence("Ctrl+/"), tab_content, lambda: self._get_current_editor() and self._get_current_editor().toggle_comment())
        QShortcut(QKeySequence("Ctrl+Shift+U"), tab_content, lambda: self._get_current_editor() and self._get_current_editor().toggle_case())
        QShortcut(QKeySequence("Ctrl+Alt+L"), tab_content, self.clear_query_text)
        QShortcut(QKeySequence("Ctrl+K"), tab_content, self.format_sql_text)
       
        
        # --- Limit ComboBox (Top Toolbar) ---
        toolbar_layout.addWidget(self.create_vertical_separator())
        rows_label = QLabel("Limit:")
        toolbar_layout.addWidget(rows_label)

        rows_limit_combo = QComboBox()
        rows_limit_combo.setObjectName("rows_limit_combo")
        rows_limit_combo.setEditable(False)
        rows_limit_combo.addItems(["No Limit", "1000", "500", "100"])
        rows_limit_combo.setCurrentText("No Limit")
        rows_limit_combo.setFixedWidth(90)
        rows_limit_combo.setFixedHeight(26)
        rows_limit_combo.setStyleSheet(btn_style)

        # When limit changes, reset offset/page and refresh
        def on_limit_change():
            text = rows_limit_combo.currentText().strip()
            if text.lower() == "no limit":
                tab_content.current_limit = 0
            else:
                try:
                    tab_content.current_limit = int(text)
                except ValueError:
                    tab_content.current_limit = 0 # Default to no limit on invalid input

            tab_content.current_page = 1
            tab_content.current_offset = 0
            # Also update the page label in UI
            page_label_widget = tab_content.findChild(QLabel, "page_label")
            if page_label_widget:
                page_label_widget.setText("Page 1")
            
            # Re-execute query with new limit/offset
            self.execute_query()

        # Connect limit change
        rows_limit_combo.currentIndexChanged.connect(on_limit_change)

        toolbar_layout.addWidget(rows_limit_combo)
        
        toolbar_layout.addWidget(self.create_vertical_separator())
        toolbar_layout.addStretch() 
        layout.addWidget(toolbar_widget)
        layout.setStretchFactor(toolbar_widget, 0)

        # 3. Main Splitter (Editor vs Results)
        main_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        main_vertical_splitter.setObjectName("tab_vertical_splitter")
        main_vertical_splitter.setHandleWidth(0) 
        layout.addWidget(main_vertical_splitter)
        layout.setStretchFactor(main_vertical_splitter, 1)

        # ----------------- Editor Container -----------------
        editor_container = QWidget()
        editor_container.setMinimumHeight(30)
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        editor_header = QWidget()
        editor_header.setObjectName("editorHeader")
        editor_header_layout = QHBoxLayout(editor_header)
        editor_header_layout.setContentsMargins(5, 2, 5, 0)
        editor_header_layout.setSpacing(2)

        query_view_btn = QPushButton("Query")
        history_view_btn = QPushButton("Query History")
        query_view_btn.setMinimumWidth(100)
        history_view_btn.setMinimumWidth(150)
        query_view_btn.setCheckable(True)
        history_view_btn.setCheckable(True)
        query_view_btn.setChecked(True)

        editor_header_layout.addWidget(query_view_btn)
        editor_header_layout.addWidget(history_view_btn)
        editor_header_layout.addStretch()
        editor_layout.addWidget(editor_header)

        # --- Editor toggle button group ---
        editor_button_group = QButtonGroup(self)
        editor_button_group.setExclusive(True)
        editor_button_group.addButton(query_view_btn, 0)
        editor_button_group.addButton(history_view_btn, 1)

        editor_stack = QStackedWidget()
        editor_stack.setObjectName("editor_stack")

        text_edit = CodeEditor()
        text_edit.setPlaceholderText("Write your SQL query here...")
        text_edit.setObjectName("query_editor")
        # text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        text_edit.customContextMenuRequested.connect(
            lambda pos, editor=text_edit: self.show_editor_context_menu(pos, editor)
        )
        editor_stack.addWidget(text_edit)

        history_widget = QSplitter(Qt.Orientation.Horizontal)
        history_widget.setHandleWidth(0)
        history_list_view = QTreeView()
        history_list_view.setObjectName("history_list_view")
        history_list_view.setHeaderHidden(True)
        history_list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        history_details_group = QGroupBox("Query Details")
        history_details_layout = QVBoxLayout(history_details_group)
        history_details_view = QTextEdit()
        history_details_view.setObjectName("history_details_view")
        history_details_view.setReadOnly(True)
        history_details_layout.addWidget(history_details_view)

        history_button_layout = QHBoxLayout()
        copy_history_btn = QPushButton("Copy")
        copy_to_edit_btn = QPushButton("Copy to Edit Query")
        remove_history_btn = QPushButton("Remove")
        remove_all_history_btn = QPushButton("Remove All")
    
        history_button_layout.addStretch()
        history_button_layout.addWidget(copy_history_btn)
        history_button_layout.addWidget(copy_to_edit_btn)
        history_button_layout.addWidget(remove_history_btn)
        history_button_layout.addWidget(remove_all_history_btn)
        history_details_layout.addLayout(history_button_layout)

        history_widget.addWidget(history_list_view)
        history_widget.addWidget(history_details_group)
        history_widget.setSizes([400, 400])
        editor_stack.addWidget(history_widget)

        editor_layout.addWidget(editor_stack)
        editor_layout.setStretchFactor(editor_stack, 1)
        main_vertical_splitter.addWidget(editor_container)

        # --- Editor switching logic ---
        def switch_editor_view(index):
            editor_stack.setCurrentIndex(index)
            if index == 1:
              self.load_connection_history(tab_content)

        query_view_btn.clicked.connect(lambda: switch_editor_view(0))
        history_view_btn.clicked.connect(lambda: switch_editor_view(1))

        db_combo_box.currentIndexChanged.connect(
          lambda: editor_stack.currentIndex() == 1 and self.load_connection_history(tab_content)
        )
        history_list_view.clicked.connect(lambda index: self.display_history_details(index, tab_content))
    
        copy_history_btn.clicked.connect(lambda: self.copy_history_query(tab_content))
        copy_to_edit_btn.clicked.connect(lambda: self.copy_history_to_editor(tab_content))
        remove_history_btn.clicked.connect(lambda: self.remove_selected_history(tab_content))
        remove_all_history_btn.clicked.connect(lambda: self.remove_all_history_for_connection(tab_content))

        # ----------------- Results Container -----------------
        results_container = QWidget()
        results_container.setMinimumHeight(30)
        results_layout = QVBoxLayout(results_container)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        # ---------------------------------------------------------
        # 1. Results Header (Buttons Only)
        # ---------------------------------------------------------
        results_header = QWidget()
        results_header.setObjectName("resultsHeader")
        results_header_layout = QHBoxLayout(results_header)
        results_header_layout.setContentsMargins(5, 2, 5, 0)
        results_header_layout.setSpacing(2)

        output_btn = QPushButton("Output")
        message_btn = QPushButton("Messages")
        notification_btn = QPushButton("Notifications")
        process_btn = QPushButton("Processes")

        output_btn.setMinimumWidth(100)
        message_btn.setMinimumWidth(100)
        notification_btn.setMinimumWidth(120)
        process_btn.setMinimumWidth(100)

        output_btn.setCheckable(True)
        message_btn.setCheckable(True)
        notification_btn.setCheckable(True)
        process_btn.setCheckable(True)
        output_btn.setChecked(True)

        explain_btn = QPushButton("Explain")
        explain_btn.setMinimumWidth(100)
        explain_btn.setCheckable(True)

        results_header_layout.addWidget(output_btn)
        results_header_layout.addWidget(message_btn)
        results_header_layout.addWidget(notification_btn)
        results_header_layout.addWidget(process_btn)
        results_header_layout.addWidget(explain_btn)
        results_header_layout.addStretch()
        
        results_layout.addWidget(results_header)
        # results_info_layout.addStretch()

        # ---------------------------------------------------------
        # 2. Results Info Bar (Showing Rows & Pagination) - BELOW Buttons
        # ---------------------------------------------------------
        results_info_bar = QWidget()
        results_info_bar.setObjectName("resultsInfoBar")
        results_info_layout = QHBoxLayout(results_info_bar)
        results_info_layout.setContentsMargins(5, 2, 5, 2)
        results_info_layout.setSpacing(5)
        # results_info_layout.addStretch()

        
        add_row_btn = QPushButton()
        add_row_btn.setIcon(QIcon("assets/row-plus.svg"))
        add_row_btn.setIconSize(QSize(16, 16))
        add_row_btn.setFixedSize(32, 32)
        add_row_btn.setToolTip("Add new row")
        add_row_btn.clicked.connect(self.add_empty_row)

        save_row_btn = QPushButton()
        save_row_btn.setIcon(QIcon("assets/save.svg"))
        save_row_btn.setIconSize(QSize(16, 16))
        save_row_btn.setFixedSize(32, 32)
        save_row_btn.setToolTip("Save new row")
        results_info_layout.addWidget(add_row_btn)
        results_info_layout.addWidget(save_row_btn)
        # footer_layout.addWidget(cancel_row_btn)
        save_row_btn.clicked.connect(self.save_new_row)

        # --- COPY / PASTE BUTTONS (pgAdmin style) ---
        copy_btn = QToolButton()
        copy_btn.setIcon(QIcon("assets/copy.svg")) 
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.setFixedSize(32, 32)
        copy_btn.setToolTip("Copy selected cells (Ctrl+C)")
        copy_btn.clicked.connect(
         lambda: self.copy_result_with_header(table_view)
         )
        copy_btn.clicked.connect(self.copy_current_result_table)

        paste_btn = QToolButton()
        paste_btn.setIcon(QIcon("assets/paste.svg")) 
        paste_btn.setIconSize(QSize(16, 16))
        paste_btn.setFixedSize(32, 32)
        paste_btn.setToolTip("Paste to editor")
        paste_btn.clicked.connect(self.paste_to_editor)

        # --- New: Delete Row Button 
        delete_row_btn = QPushButton()
        delete_row_btn.setIcon(QIcon("assets/trash.svg")) 
        delete_row_btn.setIconSize(QSize(16, 16))
        delete_row_btn.setFixedSize(32, 32)
        delete_row_btn.setToolTip("Delete selected row(s)")
        delete_row_btn.setObjectName("delete_row_btn") 

        delete_row_btn.clicked.connect(self.delete_selected_row) 

        results_info_layout.addWidget(delete_row_btn)


        results_info_layout.addWidget(copy_btn)
        results_info_layout.addWidget(paste_btn)


        download_btn = QPushButton()
        download_btn.setIcon(QIcon("assets/export.svg"))
        download_btn.setIconSize(QSize(16, 16))
        download_btn.setFixedSize(32, 32)
        download_btn.setToolTip("Download query result")
        download_btn.clicked.connect(lambda: self.download_result(tab_content))
        results_info_layout.addWidget(download_btn)

        search_box = QLineEdit()
        search_box.setPlaceholderText("Search...")
        icon_path = "assets/search.svg" 
        
        if os.path.exists(icon_path):
            search_icon = QIcon(icon_path)
            search_box.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        search_box.setFixedHeight(28)
        search_box.setFixedWidth(180)
        search_box.setObjectName("table_search_box")
        search_box.hide()  # Initially Hidden
        search_box.installEventFilter(self)
        
        # Search Button (Compact/Small)
        table_search_btn = QToolButton()
        table_search_btn.setObjectName("table_search_btn")
        table_search_btn.setIcon(QIcon(icon_path if os.path.exists(icon_path) else ""))
        table_search_btn.setFixedSize(32, 32)
        table_search_btn.setToolTip("Search in Results")
        table_search_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QToolButton:hover {
                background-color: #f0f2f5;
                border: 1px solid #adb5bd;
            }
        """)
        table_search_btn.clicked.connect(self.toggle_table_search)
        
        def on_search_text_changed(text):
            current_table = tab_content.findChild(QTableView, "results_table")
            if current_table:
                current_model = current_table.model()
                if isinstance(current_model, QSortFilterProxyModel):
                    current_model.setFilterFixedString(text)

        search_box.textChanged.connect(on_search_text_changed)
        results_info_layout.addWidget(search_box)
        results_info_layout.addWidget(table_search_btn)



        results_info_layout.addStretch()
    

        # Info Label (e.g., "Showing rows 1 - 1000")
        rows_info_label = QLabel("Showing Rows")
        rows_info_label.setObjectName("rows_info_label")
        rows_info_label.setFont(font)
        results_info_layout.addWidget(rows_info_label)

        # Edit Button (Pencil Icon)
        rows_setting_btn = QToolButton()
        rows_setting_btn.setIcon(QIcon("assets/list-details.svg"))
        rows_setting_btn.setIconSize(QSize(16, 16))
        rows_setting_btn.setFixedSize(32, 32)
        rows_setting_btn.setToolTip("Edit Limit/Offset")
        rows_setting_btn.clicked.connect(lambda: self.open_limit_offset_dialog(tab_content))
        results_info_layout.addWidget(rows_setting_btn)

        # results_info_layout.addStretch() # Separate info from pagination controls

        # ===== PAGINATION UI =====
        arrow_font = QFont("Segoe UI", 15, QFont.Weight.Bold)

        # Prev button
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(38, 28)
        prev_btn.setFont(arrow_font)
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.setEnabled(True) # Initially disabled
        prev_btn.setObjectName("prev_btn")

        # Page label
        page_label = QLabel("Page 1")
        page_label.setMinimumWidth(60)
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setFont(QFont("Segoe UI", 9))
        page_label.setObjectName("page_label")

        # Next button
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(38, 28)
        next_btn.setFont(arrow_font)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setEnabled(True) # Initially disabled until results load
        next_btn.setObjectName("next_btn")

        results_info_layout.addWidget(prev_btn)
        results_info_layout.addWidget(page_label)
        results_info_layout.addWidget(next_btn)
        
        results_layout.addWidget(results_info_bar)

        # --- Pagination Logic ---



        def update_page_ui(tab):
            page_label.setText(f"Page {tab.current_page}")
            
            # Prev
            prev_btn.setEnabled(tab.current_page > 1)
            
            limit = getattr(tab, 'current_limit', 0)
            offset = getattr(tab, 'current_offset', 0)
            
            if limit and limit > 0:
                rows_info_label.setText(f"Limit: {limit} | Offset: {offset}")
            else:
                rows_info_label.setText("No Limit") # No limit set


        
        def go_prev():
            tab = self.tab_widget.currentWidget()
            if not tab or tab.current_page <= 1:
              return
            tab.current_page -= 1
            tab.current_offset -= (tab.current_page - 1) * tab.current_limit
            # if tab_content.current_offset < 0:
            #    tab_content.current_offset = 0
            update_page_ui(tab)
            self.execute_query()

        def go_next():
            tab = self.tab_widget.currentWidget()
            if not tab.has_more_pages:
               return
            tab.current_page += 1
            tab.current_offset = (tab.current_page - 1) * tab.current_limit
            update_page_ui(tab)
            self.execute_query()

        prev_btn.clicked.connect(go_prev)
        next_btn.clicked.connect(go_next)

        # ---------------------------------------------------------

        results_button_group = QButtonGroup(self)
        results_button_group.setExclusive(True)
        results_button_group.addButton(output_btn, 0)
        results_button_group.addButton(message_btn, 1)
        results_button_group.addButton(notification_btn, 2)
        results_button_group.addButton(process_btn, 3)
        results_button_group.addButton(explain_btn, 5)

        results_stack = QStackedWidget()
        results_stack.setObjectName("results_stacked_widget")

        # Page 0: Table View
        table_view = QTableView()
        table_view.setObjectName("results_table")
        table_view.setAlternatingRowColors(True)
        table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table_view.customContextMenuRequested.connect(self.show_results_context_menu)
        table_view.setEditTriggers(
         QAbstractItemView.EditTrigger.DoubleClicked |
         QAbstractItemView.EditTrigger.SelectedClicked
          )
        results_stack.addWidget(table_view)
       
        # Page 1: Message View
        message_view = QTextEdit()
        message_view.setObjectName("message_view")
        message_view.setReadOnly(True)
        results_stack.addWidget(message_view)

        # Page 2: Notification View
        notification_view = QLabel("Notifications will appear here.")
        notification_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_stack.addWidget(notification_view)

        # Page 3: Processes View
        processes_view = QTableView()
        processes_view.setObjectName("processes_view")
        processes_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        processes_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        processes_view.setAlternatingRowColors(True)
        processes_view.horizontalHeader().setStretchLastSection(True)
        results_stack.addWidget(processes_view)
        
        # Page 4: Spinner / Loading
        spinner_overlay_widget = QWidget()
        spinner_layout = QHBoxLayout(spinner_overlay_widget)
        spinner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_movie = QMovie("assets/spinner.gif")
        spinner_label = QLabel()
        spinner_label.setObjectName("spinner_label")

        if not spinner_movie.isValid():
            spinner_label.setText("Loading...")
        else:
            spinner_label.setMovie(spinner_movie)
            spinner_movie.setScaledSize(QSize(32, 32))
            
        loading_text_label = QLabel("Waiting for query to complete...")
        font = QFont()
        font.setPointSize(10)
        loading_text_label.setFont(font)
        loading_text_label.setStyleSheet("color: #555;")
        spinner_layout.addWidget(spinner_label)
        spinner_layout.addWidget(loading_text_label)
        results_stack.addWidget(spinner_overlay_widget)

        explain_visualizer = ExplainVisualizer()
        results_stack.addWidget(explain_visualizer)      # Index 5

        results_layout.addWidget(results_stack)
        results_layout.setStretchFactor(results_stack, 1)

        tab_status_label = QLabel("Ready")
        tab_status_label.setObjectName("tab_status_label")
        results_layout.addWidget(tab_status_label)
        results_layout.setStretchFactor(tab_status_label, 0)

        def switch_results_view(index):
           results_stack.setCurrentIndex(index)
           if index == 0:
              results_info_bar.show()
           else:
               results_info_bar.hide()
           

        output_btn.clicked.connect(lambda: switch_results_view(0))
        message_btn.clicked.connect(lambda: switch_results_view(1))
        notification_btn.clicked.connect(lambda: switch_results_view(2))
        process_btn.clicked.connect(lambda: switch_results_view(3))
        explain_btn.clicked.connect(lambda: switch_results_view(5))

        main_vertical_splitter.addWidget(results_container)
        
        # --- Configure splitter behavior AFTER adding widgets ---
        main_vertical_splitter.setSizes([400, 400])
        main_vertical_splitter.setStretchFactor(0, 1)
        main_vertical_splitter.setStretchFactor(1, 1)

        tab_content.setLayout(layout)
        index = self.tab_widget.addTab(
            tab_content, f"Worksheet {self.tab_widget.count() + 1}"
        )
        self.tab_widget.setCurrentIndex(index)
        self.renumber_tabs()
        self._initialize_processes_model(tab_content)
        return tab_content




    def show_editor_context_menu(self, pos, editor):
        """
        Displays a pgAdmin-style context menu for the Query Editor
        with Cut, Copy, Paste, and Select All.
        """
        menu = QMenu(self)
        
        # Style the menu to match your application theme
        menu.setStyleSheet("""
            QMenu { background-color: #ffffff; border: 1px solid #cccccc; }
            QMenu::item { padding: 5px 25px 5px 25px; font-size: 10pt; color: #333333; }
            QMenu::item:selected { background-color: #e8eaed; color: #000000; }
            QMenu::icon { padding-left: 5px; }
            QMenu::separator { height: 1px; background: #eeeeee; margin: 4px 0px; }
        """)

        # --- Undo / Redo ---
        undo_action = QAction(QIcon("assets/undo.svg"), "Undo", self)
        undo_action.setIconVisibleInMenu(False)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(editor.undo)
        undo_action.setEnabled(editor.document().isUndoAvailable())
        menu.addAction(undo_action)
        
        redo_action = QAction(QIcon("assets/redo.svg"), "Redo", self)
        redo_action.setIconVisibleInMenu(False)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(editor.redo)
        redo_action.setEnabled(editor.document().isRedoAvailable())
        menu.addAction(redo_action)
        
        menu.addSeparator()
        
        # --- Cut ---
        cut_action = QAction("Cut", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(editor.cut)
        # Disable Cut if no text is selected
        cut_action.setEnabled(editor.textCursor().hasSelection())
        menu.addAction(cut_action)
        
        # --- Copy ---
        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(editor.copy)
        # Disable Copy if no text is selected
        copy_action.setEnabled(editor.textCursor().hasSelection())
        menu.addAction(copy_action)
        
        # --- Paste ---
        paste_action = QAction(QIcon("assets/paste.svg"), "Paste", self)
        paste_action.setIconVisibleInMenu(False)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(editor.paste)
        # Disable Paste if clipboard is empty
        clipboard = QApplication.clipboard()
        paste_action.setEnabled(clipboard.mimeData().hasText())
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # --- Select All ---
        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(editor.selectAll)
        menu.addAction(select_all_action)
        
        # --- Format SQL (Optional, since you have the function) ---
        menu.addSeparator()
        format_action = QAction(QIcon("assets/format_icon.png"), "Format SQL", self)
        format_action.setIconVisibleInMenu(False)
        format_action.setShortcut("Ctrl+Shift+F")
        format_action.triggered.connect(self.format_sql_text)
        menu.addAction(format_action)

        # Show the menu
        menu.exec(editor.mapToGlobal(pos))




    def explain_plan_query(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return

        # Get query editor and DB info
        query_editor = current_tab.findChild(CodeEditor, "query_editor")
        if not query_editor:
             query_editor = current_tab.findChild(QPlainTextEdit, "query_editor")
        
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        index = db_combo_box.currentIndex()
        conn_data = db_combo_box.itemData(index)

        if not conn_data.get("host"): # Simple check for Postgres
             self.show_info("Explain is only supported for PostgreSQL connections.")
             return

        # Extract query under cursor
        cursor = query_editor.textCursor()
        cursor_pos = cursor.position()
        full_text = query_editor.toPlainText()
        queries = full_text.split(";")

        selected_query = ""
        start = 0
        for q in queries:
            end = start + len(q)
            if start <= cursor_pos <= end:
                selected_query = q.strip()
                break
            start = end + 1  # for semicolon

        if not selected_query:
            self.show_info("Please select a query to explain.")
            return
        
        # Explain Only (No Analyze)
        query_upper = selected_query.upper().strip()
        if query_upper.startswith("EXPLAIN"):
            explain_query = selected_query
        elif query_upper.startswith("SELECT") or query_upper.startswith("INSERT") or query_upper.startswith("UPDATE") or query_upper.startswith("DELETE"):
            explain_query = f"EXPLAIN (FORMAT JSON, COSTS, VERBOSE) {selected_query}"
        else:
            self.show_info("Please select a valid query to explain.")
            return

        # Show results stack page with spinner
        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        spinner_label = results_stack.findChild(QLabel, "spinner_label")
        results_stack.setCurrentIndex(4) # Spinner index
        if spinner_label and spinner_label.movie():
              spinner_label.movie().start()
              spinner_label.show()
        
        # Set up timers
        tab_status_label = current_tab.findChild(QLabel, "tab_status_label")
        progress_timer = QTimer(self)
        start_time = time.time()
        timeout_timer = QTimer(self)
        timeout_timer.setSingleShot(True)
        self.tab_timers[current_tab] = {
            "timer": progress_timer,
            "start_time": start_time,
            "timeout_timer": timeout_timer
        }
        progress_timer.timeout.connect(partial(self.update_timer_label, tab_status_label, current_tab))
        progress_timer.start(100)

        # Run query asynchronously
        signals = QuerySignals()
        runnable = RunnableQuery(conn_data, explain_query, signals)
        signals.finished.connect(partial(self.handle_query_result, current_tab))
        signals.error.connect(partial(self.handle_query_error, current_tab))
        timeout_timer.timeout.connect(partial(self.handle_query_timeout, current_tab, runnable))
        self.running_queries[current_tab] = runnable
        self.cancel_action.setEnabled(True)
        self.thread_pool.start(runnable)
        timeout_timer.start(self.QUERY_TIMEOUT)

        self.status_message_label.setText("Executing Explain Plan...")
# {siam}


    def explain_query(self):
      current_tab = self.tab_widget.currentWidget()
      if not current_tab:
        return

      # Get query editor and DB info
      query_editor = current_tab.findChild(CodeEditor, "query_editor")
      if not query_editor:
         query_editor = current_tab.findChild(QPlainTextEdit, "query_editor")
      
      db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
      index = db_combo_box.currentIndex()
      conn_data = db_combo_box.itemData(index)

      if not conn_data.get("host"): # Simple check for Postgres
           self.show_info("Explain Analyze is only supported for PostgreSQL connections.")
           return

      # Extract query under cursor
      cursor = query_editor.textCursor()
      cursor_pos = cursor.position()
      full_text = query_editor.toPlainText()
      queries = full_text.split(";")

      selected_query = ""
      start = 0
      for q in queries:
          end = start + len(q)
          if start <= cursor_pos <= end:
              selected_query = q.strip()
              break
          start = end + 1  # for semicolon

      if not selected_query:
          self.show_info("Please select a query to explain.")
          return
      
      # If query already starts with EXPLAIN, use it as-is
      # Otherwise, wrap SELECT queries with EXPLAIN
      query_upper = selected_query.upper().strip()
      if query_upper.startswith("EXPLAIN"):
          explain_query = selected_query
      elif query_upper.startswith("SELECT"):
          explain_query = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {selected_query}"
      else:
          self.show_info("Please select a SELECT query to explain.")
          return

      # Show results stack page with spinner
      results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
      spinner_label = results_stack.findChild(QLabel, "spinner_label")
      results_stack.setCurrentIndex(4) # Spinner index
      if spinner_label and spinner_label.movie():
            spinner_label.movie().start()
            spinner_label.show()
      
      # Set up timers
      tab_status_label = current_tab.findChild(QLabel, "tab_status_label")
      progress_timer = QTimer(self)
      start_time = time.time()
      timeout_timer = QTimer(self)
      timeout_timer.setSingleShot(True)
      self.tab_timers[current_tab] = {
          "timer": progress_timer,
          "start_time": start_time,
          "timeout_timer": timeout_timer
      }
      progress_timer.timeout.connect(partial(self.update_timer_label, tab_status_label, current_tab))
      progress_timer.start(100)

      # Run query asynchronously
      signals = QuerySignals()
      runnable = RunnableQuery(conn_data, explain_query, signals)
      signals.finished.connect(partial(self.handle_query_result, current_tab))
      signals.error.connect(partial(self.handle_query_error, current_tab))
      timeout_timer.timeout.connect(partial(self.handle_query_timeout, current_tab, runnable))
      self.running_queries[current_tab] = runnable
      self.cancel_action.setEnabled(True)
      self.thread_pool.start(runnable)
      timeout_timer.start(self.QUERY_TIMEOUT)

      self.status_message_label.setText("Executing Explain Analyze...")

    def execute_query(self, conn_data=None, query=None):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return

        # If conn_data or query not provided, try to get from current editor
        if conn_data is None or query is None:
            query_editor = current_tab.findChild(CodeEditor, "query_editor")
            if not query_editor:
                query_editor = current_tab.findChild(QPlainTextEdit, "query_editor")
            
            db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
            index = db_combo_box.currentIndex()
            conn_data = db_combo_box.itemData(index)

            # Extract query under cursor
            cursor = query_editor.textCursor()
            cursor_pos = cursor.position()
            full_text = query_editor.toPlainText()
            queries = full_text.split(";")

            selected_query = ""
            start = 0
            for q in queries:
                end = start + len(q)
                if start <= cursor_pos <= end:
                    selected_query = q.strip()
                    break
                start = end + 1  # for semicolon

            query = selected_query

        # if not query or not query.strip().upper().startswith("SELECT "):
        if not query or not query.strip():
                self.show_info("Please enter a valid query.")
                return

        # ---------------------------------------------------------
        # --- Apply Row Limit AND Offset Logic from Tab Attributes ---
        # ---------------------------------------------------------
        
        query = query.strip()
        # has_semicolon = query.endswith(";")
        query = query.rstrip(";")
        # if has_semicolon:
        #    query += ";"
        # Get stored values (default to 1000 and 0 if not set)
        limit = getattr(current_tab, 'current_limit', 1000)
        offset = getattr(current_tab, 'current_offset', 0)
        # tab = self.tab_widget.currentWidget()

        # limit = tab.current_limit
        # offset = tab.current_offset

        # if limit > 0:
        #    query = query.rstrip(";")
        #    query += f" LIMIT {limit} OFFSET {offset}"

        if query.upper().startswith("SELECT") and limit > 0:
          if "LIMIT" not in query.upper():
             query += f" LIMIT {limit}"
          if offset > 0 and "OFFSET" not in query.upper():
             query += f" OFFSET {offset}"

        query += ";"

        # query = query.strip().rstrip(";")

        # if has_semicolon:
        #    query += ";"

        
        # Show spinner and reset results view
        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        if results_stack:
            results_stack.setCurrentIndex(4)
            spinner_label = results_stack.findChild(QLabel, "spinner_label")
            if spinner_label and spinner_label.movie():
                spinner_label.movie().start()
                spinner_label.show()

        # Set up timers
        tab_status_label = current_tab.findChild(QLabel, "tab_status_label")
        progress_timer = QTimer(self)
        start_time = time.time()
        timeout_timer = QTimer(self)
        timeout_timer.setSingleShot(True)
        self.tab_timers[current_tab] = {
            "timer": progress_timer,
            "start_time": start_time,
            "timeout_timer": timeout_timer
        }
        progress_timer.timeout.connect(partial(self.update_timer_label, tab_status_label, current_tab))
        progress_timer.start(100)

        # Run query asynchronously
        signals = QuerySignals()
        runnable = RunnableQuery(conn_data, query, signals)
        signals.finished.connect(partial(self.handle_query_result, current_tab))
        signals.error.connect(partial(self.handle_query_error, current_tab))
        timeout_timer.timeout.connect(partial(self.handle_query_timeout, current_tab, runnable))
        self.running_queries[current_tab] = runnable
        self.cancel_action.setEnabled(True)
        self.thread_pool.start(runnable)
        timeout_timer.start(self.QUERY_TIMEOUT)
        self.status_message_label.setText("Executing query...")

    def update_timer_label(self, label, tab):
        if not label or tab not in self.tab_timers: return
        elapsed = time.time() - self.tab_timers[tab]["start_time"]
        label.setText(f"Running... {elapsed:.1f} sec")




    def show_error_popup(self, error_text, parent=None):
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle("Query Error")
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText("Query execution failed")
        msg_box.setInformativeText(error_text)  # detailed error
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def handle_query_error(self, current_tab, conn_data, query, row_count, elapsed_time, error_message):
        if current_tab in self.tab_timers:
            self.tab_timers[current_tab]["timer"].stop()
            self.tab_timers[current_tab]["timeout_timer"].stop()
            del self.tab_timers[current_tab]

        self.save_query_to_history(
            conn_data, query, "Failure", row_count, elapsed_time)
        
        message_view = current_tab.findChild(QTextEdit, "message_view")
        tab_status_label = current_tab.findChild(QLabel, "tab_status_label")

        #message_view.setText(f"Error:\n\n{error_message}")
        if message_view:
            previous_text = message_view.toPlainText()
            if previous_text:
              message_view.append("\n" + "-"*50 + "\n")  # Optional separator
            message_view.append(f"Error:\n\n{error_message}")
            message_view.verticalScrollBar().setValue(message_view.verticalScrollBar().maximum())

        # --- Switch to Messages Tab on Error ---
        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        if results_stack:
            results_stack.setCurrentIndex(1) # Index 1 is Messages
            header = current_tab.findChild(QWidget, "resultsHeader")
            if header:
                buttons = header.findChildren(QPushButton)
                if len(buttons) >= 2:
                    buttons[0].setChecked(False) # Output
                    buttons[1].setChecked(True)  # Messages
            
            results_info_bar = current_tab.findChild(QWidget, "resultsInfoBar")
            if results_info_bar:
                results_info_bar.hide()

        #tab_status_label.setText(f"Error: {error_message}")
        self.status_message_label.setText("Error occurred")
        self.stop_spinner(current_tab, success=False)

        # --- Show popup ---
        self.show_error_popup(error_message, parent=current_tab)

        if current_tab in self.running_queries:
            del self.running_queries[current_tab]
        if not self.running_queries:
            self.cancel_action.setEnabled(False)



    def handle_query_timeout(self, tab, runnable):
        if self.running_queries.get(tab) is runnable:
            runnable.cancel()
            error_message = f"Error: Query Timed Out after {self.QUERY_TIMEOUT / 1000} seconds."
            tab.findChild(QTextEdit, "message_view").setText(error_message)
            tab.findChild(QLabel, "tab_status_label").setText(error_message)
            self.stop_spinner(tab, success=False)
            if tab in self.tab_timers:
                self.tab_timers[tab]["timer"].stop()
                del self.tab_timers[tab]
            if tab in self.running_queries:
                del self.running_queries[tab]
            if not self.running_queries:
                self.cancel_action.setEnabled(False)
            self.status_message_label.setText("Error occurred")
            QMessageBox.warning(self, "Query Timeout", f"The query was stopped as it exceeded {self.QUERY_TIMEOUT / 1000}s.")

    def cancel_current_query(self):
        current_tab = self.tab_widget.currentWidget()
        runnable = self.running_queries.get(current_tab)
        if runnable:
            runnable.cancel()
            if current_tab in self.tab_timers:
                self.tab_timers[current_tab]["timer"].stop()
                self.tab_timers[current_tab]["timeout_timer"].stop()
                del self.tab_timers[current_tab]
            cancel_message = "Query cancelled by user."
            current_tab.findChild(QTextEdit, "message_view").setText(cancel_message)
            current_tab.findChild(QLabel, "tab_status_label").setText(cancel_message)
            self.stop_spinner(current_tab, success=False)
            self.status_message_label.setText("Query Cancelled")
            if current_tab in self.running_queries:
                del self.running_queries[current_tab]
            if not self.running_queries:
                self.cancel_action.setEnabled(False)


    def save_query_to_history(self, conn_data, query, status, rows, duration):
        self.results_manager.save_query_to_history(conn_data, query, status, rows, duration)

    def load_connection_history(self, target_tab):
        self.results_manager.load_connection_history(target_tab)

    def display_history_details(self, index, target_tab):
        self.results_manager.display_history_details(index, target_tab)

    def _get_selected_history_item(self, target_tab):
        return self.results_manager._get_selected_history_item(target_tab)

    def copy_history_query(self, target_tab):
        self.results_manager.copy_history_query(target_tab)

    def copy_history_to_editor(self, target_tab):
        self.results_manager.copy_history_to_editor(target_tab)

    def remove_selected_history(self, target_tab):
        self.results_manager.remove_selected_history(target_tab)

    def remove_all_history_for_connection(self, target_tab):
        self.results_manager.remove_all_history_for_connection(target_tab)

    # --- Delegated Result Methods ---

    def handle_query_result(self, target_tab, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
        if target_tab in self.tab_timers:
            self.tab_timers[target_tab]["timer"].stop()
            self.tab_timers[target_tab]["timeout_timer"].stop()
            del self.tab_timers[target_tab]

        self.results_manager.handle_query_result(target_tab, conn_data, query, results, columns, row_count, elapsed_time, is_select_query)

    def copy_current_result_table(self):
        self.results_manager.copy_current_result_table()

    def copy_result_with_header(self, table_view):
        self.results_manager.copy_result_with_header(table_view)

    def paste_to_editor(self):
        self.results_manager.paste_to_editor()

    def download_result(self, tab_content):
        self.results_manager.download_result(tab_content)

    def add_empty_row(self):
        self.results_manager.add_empty_row()

    def save_new_row(self):
        self.results_manager.save_new_row()

    def delete_selected_row(self):
        self.results_manager.delete_selected_row()

    def toggle_table_search(self):
        self.results_manager.toggle_table_search()

    def show_results_context_menu(self, position):
        self.results_manager.show_results_context_menu(position)

    def renumber_tabs(self):
        for i in range(self.tab_widget.count()):
            current_text = self.tab_widget.tabText(i)
            # Only renumber if it's a default "Query X" name
            if current_text.startswith("Query ") or current_text == "New Tab":
                self.tab_widget.setTabText(i, f"Query {i+1}")

    def eventFilter(self, obj, event):
        if obj.objectName() == "table_search_box" and event.type() == QEvent.Type.FocusOut:
            obj.hide()
            parent_tab = obj.parent()
            if parent_tab:
                search_btn = parent_tab.findChild(QToolButton, "table_search_btn")
                if search_btn:
                    search_btn.show()
        return super().eventFilter(obj, event)

    def refresh_all_comboboxes(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            combo = tab.findChild(QComboBox, "db_combo_box")
            if combo:
                self.load_joined_connections(combo)

    def _initialize_processes_model(self, tab_content):
        self.results_manager._initialize_processes_model(tab_content)

    def stop_spinner(self, target_tab, success=True, target_index=0):
        self.results_manager.stop_spinner(target_tab, success, target_index)

    def show_info(self, text, parent=None):
        if parent is None:
            current_tab = self.tab_widget.currentWidget()
            parent = current_tab if current_tab else self.main_window
        QMessageBox.information(parent, "Information", text)

    def refresh_processes_view(self):
        self.results_manager.refresh_processes_view()

    def load_joined_connections(self, combo_box):
        try:
            current_data = combo_box.currentData()
            combo_box.clear()
            connections = db.get_all_connections_from_db()
            for connection in connections:
                conn_data = {key: connection[key] for key in connection if key != 'display_name'}
                combo_box.addItem(connection["display_name"], conn_data)

            if current_data:
                for i in range(combo_box.count()):
                    item_data = combo_box.itemData(i)
                    if item_data and item_data.get('id') == current_data.get('id'):
                        combo_box.setCurrentIndex(i)
                        break
        except Exception as e:
            print(f"Error refreshing combobox: {e}")