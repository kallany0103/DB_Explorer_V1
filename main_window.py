# main_window.py
import sys
import os
import json
import time
import datetime
import psycopg2
import sqlparse
import cdata.csv as mod
import cdata.servicenow 
import sqlite3 as sqlite # This can be removed if not used elsewhere directly
from functools import partial
import uuid
import pandas as pd, time, os, re
from table_properties import TablePropertiesDialog
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QTabWidget,
    QSplitter, QLineEdit, QTextEdit, QComboBox, QTableView,QTableWidget,QTableWidgetItem, QHeaderView, QVBoxLayout, QWidget, QStatusBar, QToolBar, QFileDialog,
    QSizePolicy, QPushButton,QToolButton, QInputDialog, QMessageBox, QMenu, QAbstractItemView, QDialog, QFormLayout, QHBoxLayout,
    QStackedWidget, QSpinBox,QLabel,QFrame, QGroupBox,QCheckBox,QStyle,QDialogButtonBox, QPlainTextEdit, QButtonGroup
)

from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtGui import QAction, QIcon, QStandardItemModel, QStandardItem, QFont, QMovie, QDesktopServices, QColor, QBrush
from PyQt6.QtCore import Qt, QDir, QModelIndex,QSortFilterProxyModel, QSize, QObject, pyqtSignal, QRunnable, QThreadPool, QTimer, QUrl, QByteArray
from dialogs.postgres_dialog import PostgresConnectionDialog
from dialogs.sqlite_dialog import SQLiteConnectionDialog
from dialogs.oracle_dialog import OracleConnectionDialog
from dialogs.export_dialog import ExportDialog
from dialogs.csv_dialog import CSVConnectionDialog
from dialogs.servicenow_dialog import ServiceNowConnectionDialog
from workers import RunnableExport, RunnableExportFromModel, RunnableQuery, ProcessSignals, QuerySignals
from notification_manager import NotificationManager
from code_editor import CodeEditor
from widgets.explain_visualizer import ExplainVisualizer
import db


class CreateTableDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create Table ({db_type})")
        self.resize(600, 450)
        self.db_type = db_type
        
        # Layouts
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Owner, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_input = QLineEdit()
        self.owner_input = QLineEdit(current_user) # Default to current user
        self.schema_combo = QComboBox()
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        self.comment_input = QTextEdit()
        self.comment_input.setMaximumHeight(60)

        gen_layout.addRow("Name:", self.name_input)
        
        # Hide Owner and Schema for SQLite as they aren't typically used/needed for simple creation
        if self.db_type == 'postgres':
            gen_layout.addRow("Owner:", self.owner_input)
            gen_layout.addRow("Schema:", self.schema_combo)
        
        gen_layout.addRow("Comment:", self.comment_input)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Columns (Simple Column Editor) ---
        self.columns_tab = QWidget()
        col_layout = QVBoxLayout(self.columns_tab)
        
        self.col_table = QTableWidget(0, 3) # Rows, Cols
        self.col_table.setHorizontalHeaderLabels(["Name", "Data Type", "Primary Key?"])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.col_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Buttons for columns
        btn_layout = QHBoxLayout()
        add_col_btn = QPushButton("Add Column")
        add_col_btn.clicked.connect(lambda: self.add_column_row())
        remove_col_btn = QPushButton("Remove Column")
        remove_col_btn.clicked.connect(self.remove_column_row)
        
        btn_layout.addWidget(add_col_btn)
        btn_layout.addWidget(remove_col_btn)
        btn_layout.addStretch()

        col_layout.addLayout(btn_layout)
        col_layout.addWidget(self.col_table)
        
        # Add a default 'id' column
        # Postgres uses SERIAL, SQLite usually uses INTEGER (which becomes auto-increment if PK)
        default_id_type = "SERIAL" if self.db_type == 'postgres' else "INTEGER"
        self.add_column_row("id", default_id_type, True)
        
        self.tabs.addTab(self.columns_tab, "Columns")

        # --- Dialog Buttons (OK/Cancel) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def add_column_row(self, name="", type="", is_pk=False):
        row = self.col_table.rowCount()
        self.col_table.insertRow(row)
        
        # Default type if empty
        if not type:
            type = "VARCHAR" if self.db_type == 'postgres' else "TEXT"

        # Name Item
        self.col_table.setItem(row, 0, QTableWidgetItem(name))
        
        # Type Item (editable)
        self.col_table.setItem(row, 1, QTableWidgetItem(type))
        
        # PK Checkbox
        pk_item = QTableWidgetItem()
        pk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        pk_item.setCheckState(Qt.CheckState.Checked if is_pk else Qt.CheckState.Unchecked)
        self.col_table.setItem(row, 2, pk_item)

    def remove_column_row(self):
        current_row = self.col_table.currentRow()
        if current_row >= 0:
            self.col_table.removeRow(current_row)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Table Name is required!")
            return
        self.accept()

    def get_sql_data(self):
        """Returns a dictionary with the table definition data"""
        columns = []
        for r in range(self.col_table.rowCount()):
            name = self.col_table.item(r, 0).text()
            dtype = self.col_table.item(r, 1).text()
            is_pk = self.col_table.item(r, 2).checkState() == Qt.CheckState.Checked
            if name:
                columns.append({"name": name, "type": dtype, "pk": is_pk})
                
        return {
            "name": self.name_input.text().strip(),
            "owner": self.owner_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "columns": columns
        }

class CreateViewDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create View ({db_type})")
        self.resize(600, 500)
        self.db_type = db_type
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_input = QLineEdit()
        self.schema_combo = QComboBox()
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        gen_layout.addRow("Name:", self.name_input)
        if self.db_type == 'postgres':
            gen_layout.addRow("Schema:", self.schema_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Definition (SQL query) ---
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        
        def_layout.addWidget(QLabel("View Definition (SQL SELECT statement):"))
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("SELECT * FROM some_table ...")
        # Set a monospace font for the editor
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.sql_editor.setFont(font)
        
        def_layout.addWidget(self.sql_editor)
        self.tabs.addTab(self.definition_tab, "Definition")

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "View Name is required!")
            return
        if not self.sql_editor.toPlainText().strip():
            QMessageBox.warning(self, "Error", "SQL Definition is required!")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "sql": self.sql_editor.toPlainText().strip()
        }

class MainWindow(QMainWindow):
    QUERY_TIMEOUT = 360000
    def __init__(self):
        super().__init__()
        self.SESSION_FILE = "session_state.json"
        
        self.setWindowTitle("Universal SQL Client")
        self.setGeometry(100, 100, 1200, 800)

        self.thread_pool = QThreadPool.globalInstance()
        self.tab_timers = {}
        self.running_queries = {}
        self._saved_tree_paths = []

        self._create_actions()
        self._create_menu()
        self._create_centered_toolbar()

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_message_label = QLabel("Ready")
        self.status.addWidget(self.status_message_label)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.tree = QTreeView()
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.clicked.connect(self.item_clicked)
        self.tree.doubleClicked.connect(self.item_double_clicked)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Object Explorer'])
        self.tree.setModel(self.model)
        
        self.tree.setHeaderHidden(True)

        # --- Create Object Explorer Header (Query Tool Button) ---
        object_explorer_header = QWidget()
        object_explorer_header.setObjectName("objectExplorerHeader")
        object_explorer_header_layout = QHBoxLayout(object_explorer_header)
        object_explorer_header_layout.setContentsMargins(5, 0, 2, 0)
        object_explorer_header_layout.setSpacing(4)

        object_explorer_label = QLabel("Object Explorer")
        
        object_explorer_header_layout.addWidget(object_explorer_label)
        object_explorer_header_layout.addStretch()

        self.explorer_query_tool_btn = QToolButton()
        self.explorer_query_tool_btn.setDefaultAction(self.query_tool_action) 
        self.explorer_query_tool_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.explorer_query_tool_btn.setToolTip("Open new query tool")
        self.explorer_query_tool_btn.setIconSize(QSize(20, 20))
        
        object_explorer_header_layout.addWidget(self.explorer_query_tool_btn)
        
        self.left_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_vertical_splitter.addWidget(self.tree)

        self.schema_tree = QTreeView()
        self.schema_model = QStandardItemModel()
        self.schema_model.setHorizontalHeaderLabels(["Database Schema"])
        self.schema_tree.setModel(self.schema_model)
        self.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.schema_tree.customContextMenuRequested.connect(self.show_schema_context_menu)
        self.left_vertical_splitter.addWidget(self.schema_tree)

        self.left_vertical_splitter.setSizes([240, 360])
        
        left_layout.addWidget(object_explorer_header) 
        left_layout.addWidget(self.left_vertical_splitter)
        self.main_splitter.addWidget(left_panel)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        add_tab_btn = QPushButton("New")
        add_tab_btn.setIcon(QIcon("assets/sheet-plus.svg"))  # or .svg
        add_tab_btn.setIconSize(QSize(20, 22))
        add_tab_btn.clicked.connect(self.add_tab)
        self.tab_widget.setCornerWidget(add_tab_btn)
        self.main_splitter.addWidget(self.tab_widget)

        self.thread_monitor_timer = QTimer()
        self.thread_monitor_timer.timeout.connect(self.update_thread_pool_status)
        self.thread_monitor_timer.start(1000)

        self.load_data()
        self.restore_session_state()
        self.main_splitter.setSizes([280, 920])
        self.notification_manager = NotificationManager(self)
        self._apply_styles()

    def _create_actions(self):
        style = QApplication.style()
        open_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        save_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        
        self.open_file_action = QAction(open_icon, "Open File", self)
        self.open_file_action.triggered.connect(self.open_sql_file)
        
        self.save_as_action = QAction(save_icon, "Save As...", self)
        self.save_as_action.triggered.connect(self.save_sql_file_as)
        
        self.exit_action = QAction(QIcon("assets/exit.svg"), "Exit", self)
        self.exit_action.triggered.connect(self.close)
        self.execute_action = QAction(QIcon("assets/execute_icon.png"), "Execute", self)
        self.execute_action.triggered.connect(self.execute_query)
        self.explain_action = QAction(QIcon("assets/explain_icon.png"), "Explain", self)
        self.explain_action.triggered.connect(self.explain_query)
        
        # New actions for Explain/Analyze button{siam}
        self.explain_analyze_action = QAction(QIcon("assets/explain_icon.png"), "Explain Analyze", self)
        self.explain_analyze_action.triggered.connect(self.explain_query) # Reuse existing logic       
        self.explain_plan_action = QAction(QIcon("assets/explain_icon.png"), "Explain (Plan)", self)
        self.explain_plan_action.triggered.connect(self.explain_plan_query)



        self.cancel_action = QAction(QIcon("assets/cancel_icon.png"), "Cancel", self)
        self.cancel_action.triggered.connect(self.cancel_current_query)
        self.cancel_action.setEnabled(False)
        self.undo_action = QAction("Undo", self)
        self.undo_action.triggered.connect(self.undo_text)
        self.redo_action = QAction("Redo", self)
        self.redo_action.triggered.connect(self.redo_text)
        self.cut_action = QAction("Cut", self)
        self.cut_action.triggered.connect(self.cut_text)
        self.copy_action = QAction("Copy", self)
        self.copy_action.triggered.connect(self.copy_text)
        self.paste_action = QAction("Paste", self)
        self.paste_action.triggered.connect(self.paste_text)
        self.delete_action = QAction("Delete", self)
        self.delete_action.triggered.connect(self.delete_text)
        
        self.query_tool_action = QAction(QIcon("assets/sql_icon.png"), "Query Tool", self)
        self.query_tool_action.triggered.connect(self.add_tab)
        
        self.restore_action = QAction("Restore Layout", self)
        self.restore_action.triggered.connect(self.restore_tool)
        self.refresh_action = QAction("Refresh Explorer", self)
        self.refresh_action.triggered.connect(self.refresh_object_explorer)
        self.minimize_action = QAction("Minimize", self)
        self.minimize_action.triggered.connect(self.showMinimized)
        self.zoom_action = QAction("Zoom", self)
        self.zoom_action.triggered.connect(self.toggle_maximize)
        self.sqlite_help_action = QAction("SQLite Website", self)
        self.sqlite_help_action.triggered.connect(
            lambda: self.open_help_url("https://www.sqlite.org/"))
        self.postgres_help_action = QAction("PostgreSQL Website", self)
        self.postgres_help_action.triggered.connect(
            lambda: self.open_help_url("https://www.postgresql.org/"))
        self.oracle_help_action = QAction("Oracle Website", self)
        self.oracle_help_action.triggered.connect(
            lambda: self.open_help_url("https://www.oracle.com/database/"))
        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about_dialog)
        self.format_sql_action = QAction(QIcon("assets/format_icon.png"), "Format SQL", self)
        self.format_sql_action.setShortcut("Ctrl+Shift+F")
        self.format_sql_action.triggered.connect(self.format_sql_text)

        self.clear_query_action = QAction(QIcon("assets/delete_icon.png"), "Clear Query", self)
        self.clear_query_action.setShortcut("Ctrl+Shift+c")
        self.clear_query_action.triggered.connect(self.clear_query_text)

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.open_file_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addAction(self.delete_action)
        actions_menu = menubar.addMenu("&Actions")
        actions_menu.addAction(self.execute_action)
        actions_menu.addAction(self.explain_action)
        actions_menu.addAction(self.cancel_action)
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.query_tool_action)
        tools_menu.addAction(self.refresh_action)
        tools_menu.addAction(self.restore_action)
        window_menu = menubar.addMenu("&Window")
        window_menu.addAction(self.minimize_action)
        window_menu.addAction(self.zoom_action)
        window_menu.addSeparator()
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        window_menu.addAction(close_action)
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.sqlite_help_action)
        help_menu.addAction(self.postgres_help_action)
        help_menu.addAction(self.oracle_help_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

    def _create_centered_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon) 
        toolbar.setIconSize(QSize(16, 16)) 
        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(left_spacer)
        
        # --- Existing Actions ---
        # toolbar.addAction(self.open_file_action)
        # toolbar.addAction(self.save_as_action)
        toolbar.addAction(self.exit_action)
        toolbar.addSeparator() # Separator for clearer UI
       # toolbar.addAction(self.execute_action)
        # toolbar.addAction(self.cancel_action)
        toolbar.addSeparator()


        toolbar.addWidget(right_spacer)
        self.addToolBar(toolbar)

    def open_sql_file(self):
        editor = self._get_current_editor()
        
        if not editor:
            current_tab = self.tab_widget.currentWidget()
            if not current_tab:
                self.add_tab()
                current_tab = self.tab_widget.currentWidget()
           
            editor_stack = current_tab.findChild(QStackedWidget, "editor_stack")
            if editor_stack and editor_stack.currentIndex() != 0:
                editor_stack.setCurrentIndex(0)
                query_view_btn = current_tab.findChild(QPushButton, "Query")
                history_view_btn = current_tab.findChild(QPushButton, "Query History")
                if query_view_btn: query_view_btn.setChecked(True)
                if history_view_btn: history_view_btn.setChecked(False)

            editor = self._get_current_editor()
            if not editor: 
                QMessageBox.warning(self, "Error", "Could not find a query editor to open the file into.")
                return

        file_name, _ = QFileDialog.getOpenFileName(self, "Open SQL File", "", "SQL Files (*.sql);;All Files (*)")
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    editor.setPlainText(content)
                    self.status.showMessage(f"File opened: {file_name}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not read file:\n{e}")

    def save_sql_file_as(self):
        editor = self._get_current_editor()
        if not editor:
            QMessageBox.warning(self, "Error", "No active query editor to save from.")
            return

        content = editor.toPlainText()
        default_dir = QDir.homePath()
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, 
            "Save SQL File As", 
            default_dir,
            "SQL Files (*.sql);;All Files (*)"
        )
        
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status.showMessage(f"File saved: {file_name}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")


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
             QMessageBox.critical(self, "Error", "Library 'sqlparse' is missing.\nPlease run: pip install sqlparse")
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
            self.status.showMessage("Editor cleared.", 3000)

#
    # --- New Handler Methods for Menu Actions ---km

    def show_about_dialog(self):
        QMessageBox.about(self, "About SQL Client", "<b>SQL Client Application</b><p>Version 1.0.0</p><p>This is a versatile SQL client designed to connect to and manage multiple database systems including PostgreSQL and SQLite.</p><p><b>Features:</b></p><ul><li>Object Explorer for database schemas</li><li>Multi-tab query editor with syntax highlighting</li><li>Query history per connection</li><li>Asynchronous query execution to keep the UI responsive</li></ul><p>Developed to provide a simple and effective tool for database management.</p>")

    def _get_current_editor(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return None
        editor_stack = current_tab.findChild(QStackedWidget, "editor_stack")
        if editor_stack and editor_stack.currentIndex() == 0:
            return current_tab.findChild(CodeEditor, "query_editor")
        return None

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

    def restore_tool(self):
        self.main_splitter.setSizes([280, 920])
        self.left_vertical_splitter.setSizes([240, 360])
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            tab_splitter = current_tab.findChild(
                QSplitter, "tab_vertical_splitter")
            if tab_splitter:
                tab_splitter.setSizes([300, 300])
        self.status.showMessage("Layout restored to defaults.", 3000)

    def refresh_object_explorer(self):
        self._save_tree_expansion_state()
        self.load_data()
        self._restore_tree_expansion_state()
        self.status.showMessage("Object Explorer refreshed.", 3000)

    def update_schema_context(self, schema_name, schema_type, table_count):
        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Database Schema"])

        root = self.schema_model.invisibleRootItem()

        name_item = QStandardItem(f"Name : {schema_name}")
        type_item = QStandardItem(f"Type : {schema_type}")
        table_item = QStandardItem(f"Tables : {table_count}")

        name_item.setEditable(False)
        type_item.setEditable(False)
        table_item.setEditable(False)

        root.appendRow(name_item)
        root.appendRow(type_item)
        root.appendRow(table_item)

        self.schema_tree.expandAll()


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def open_help_url(self, url_string):
        if not QDesktopServices.openUrl(QUrl(url_string)):
            QMessageBox.warning(
                self, "Open URL", f"Could not open URL: {url_string}")
            
            
    def update_thread_pool_status(self):
         active = self.thread_pool.activeThreadCount()
         max_threads = self.thread_pool.maxThreadCount()
         self.status.showMessage(f"ThreadPool: {active} active of {max_threads}", 3000)
   

    def _apply_styles(self):
        primary_color, header_color, selection_color = "#D3D3D3", "#A9A9A9", "#A9A9A9"
        text_color_on_primary, alternate_row_color, border_color = "#000000", "#f0f0f0", "#A9A9A9"
        self.setStyleSheet(f"""QMainWindow, QToolBar, QStatusBar {{ background-color: {primary_color}; color: {text_color_on_primary}; }} QTreeView {{ background-color: white; alternate-background-color: {alternate_row_color}; border: 1px solid {border_color}; }} QTableView {{ alternate-background-color: {alternate_row_color}; background-color: white; gridline-color: #a9a9a9; border: 1px solid {border_color}; font-family: Arial, sans-serif; font-size: 9pt;}} QTableView::item {{ padding: 4px; }} QTableView::item:selected {{ background-color: {selection_color}; color: white; }} QHeaderView::section {{ background-color: {header_color}; color: white; padding: 4px; border: none; border-right: 1px solid #d3d3d3; border-bottom: 1px solid {border_color}; font-weight: bold; font-size: 9pt;  }} QTableView QTableCornerButton::section {{ background-color: {header_color}; border: 1px solid {border_color}; }} #resultsHeader QPushButton, #editorHeader QPushButton {{ background-color: #ffffff; border: 1px solid {border_color}; padding: 5px 15px; font-size: 9pt; }} #resultsHeader QPushButton:hover, #editorHeader QPushButton:hover {{ background-color: {primary_color}; }} #resultsHeader QPushButton:checked, #editorHeader QPushButton:checked {{ background-color: {selection_color}; border-bottom: 1px solid {selection_color}; font-weight: bold; color: white; }} #resultsHeader, #editorHeader {{ background-color: {alternate_row_color}; padding-bottom: -1px; }} #messageView, #history_details_view, QTextEdit {{ font-family: Consolas, monospace; font-size: 10pt; background-color: white; border: 1px solid {border_color}; }} #tab_status_label {{ padding: 3px 5px; background-color: {alternate_row_color}; border-top: 1px solid {border_color}; }} QGroupBox {{ font-size: 9pt; font-weight: bold; color: {text_color_on_primary}; }} QTabWidget::pane {{ border-top: 1px solid {border_color}; }} QTabBar::tab {{ background: #E0E0E0; border: 1px solid {border_color}; padding: 5px 10px; border-bottom: none; }} QTabBar::tab:selected {{ background: {selection_color}; color: white; }} QComboBox {{ border: 1px solid {border_color}; padding: 2px; background-color: white; }}""")

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
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(5)

        # --- Group A: File Actions ---
        open_btn = QToolButton()
        open_btn.setDefaultAction(self.open_file_action)
        open_btn.setToolTip("Open SQL File")
        toolbar_layout.addWidget(open_btn)

        save_btn = QToolButton()
        save_btn.setDefaultAction(self.save_as_action)
        save_btn.setToolTip("Save SQL File")
        toolbar_layout.addWidget(save_btn)
        
        toolbar_layout.addWidget(self.create_vertical_separator())

        # --- Group B: Execution & Edit Actions ---
        exec_btn = QToolButton()
        exec_btn.setDefaultAction(self.execute_action)
        exec_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar_layout.addWidget(exec_btn)
# {siam}
        # --- Explain Split Button ---
        explain_btn = QToolButton()
        explain_btn.setDefaultAction(self.explain_analyze_action) # Analyze by default
        explain_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        explain_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        explain_menu = QMenu(explain_btn)
        explain_menu.addAction(self.explain_analyze_action)
        explain_menu.addAction(self.explain_plan_action)
        explain_btn.setMenu(explain_menu)
        toolbar_layout.addWidget(explain_btn)
# {siam}
        cancel_btn = QToolButton()
        cancel_btn.setDefaultAction(self.cancel_action)
        cancel_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar_layout.addWidget(cancel_btn)

        edit_button = QToolButton()
        edit_button.setText("Edit")
        edit_button.setToolTip("Edit Query")
        edit_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        edit_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup) 
        edit_menu = QMenu(edit_button)
        edit_menu.addAction(self.format_sql_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.clear_query_action)
        edit_button.setMenu(edit_menu)
        toolbar_layout.addWidget(edit_button)
       
        
        # --- Limit ComboBox (Top Toolbar) ---
        toolbar_layout.addWidget(self.create_vertical_separator())
        rows_label = QLabel("Limit:")
        toolbar_layout.addWidget(rows_label)

        rows_limit_combo = QComboBox()
        rows_limit_combo.setObjectName("rows_limit_combo")
        rows_limit_combo.setEditable(True)
        rows_limit_combo.addItems(["No Limit", "1000", "500", "100"])
        rows_limit_combo.setCurrentText("No Limit")
        rows_limit_combo.setFixedWidth(90)

        # When limit changes, reset offset/page and refresh
        def on_limit_change():
            text = rows_limit_combo.currentText().strip()
            if text.lower() == 1000:
               tab_content.current_limit = 0
            else:
               try:
                tab_content.current_limit = int(text)
               except ValueError:
                tab_content.current_limit ="No Limit"

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
        rows_limit_combo.lineEdit().returnPressed.connect(on_limit_change)

        toolbar_layout.addWidget(rows_limit_combo)
        
        toolbar_layout.addWidget(self.create_vertical_separator())
        toolbar_layout.addStretch() 
        layout.addWidget(toolbar_widget)

        # 3. Main Splitter (Editor vs Results)
        main_vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        main_vertical_splitter.setObjectName("tab_vertical_splitter")
        layout.addWidget(main_vertical_splitter)

        # ----------------- Editor Container -----------------
        editor_container = QWidget()
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
        text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        editor_stack.addWidget(text_edit)

        history_widget = QSplitter(Qt.Orientation.Horizontal)
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

        
        add_row_btn = QPushButton("≡+")
        add_row_btn.setFixedSize(30, 30)
        add_row_btn.setToolTip("Add new row")
        add_row_btn.clicked.connect(self.add_empty_row)
        save_row_btn = QPushButton("💾")
        save_row_btn.setFixedSize(30, 30)
        save_row_btn.setToolTip("Save new row")
        results_info_layout.addWidget(add_row_btn)
        results_info_layout.addWidget(save_row_btn)
        # footer_layout.addWidget(cancel_row_btn)
        save_row_btn.clicked.connect(self.save_new_row)

        # --- COPY / PASTE BUTTONS (pgAdmin style) ---
        copy_btn = QToolButton()
        copy_btn.setText("Copy")
        copy_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        copy_btn.setToolTip("Copy selected cells (Ctrl+C)")
        # # copy_btn.clicked.connect(
        #  lambda: self.copy_result_selection(table_view)
        # )
        copy_btn.clicked.connect(
         lambda: self.copy_result_with_header(table_view)
         )
        copy_btn.clicked.connect(self.copy_current_result_table)

        paste_btn = QToolButton()
        paste_btn.setText("Paste")
        paste_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        paste_btn.setToolTip("")
        paste_btn.clicked.connect(self.paste_to_editor)

        # --- New: Delete Row Button 
        delete_row_btn = QPushButton("🗑️") 
        delete_row_btn.setFixedSize(30, 30)
        delete_row_btn.setToolTip("Delete selected row(s)")
        delete_row_btn.setObjectName("delete_row_btn") 

        delete_row_btn.clicked.connect(self.delete_selected_row) 

        results_info_layout.addWidget(delete_row_btn)


        results_info_layout.addWidget(copy_btn)
        results_info_layout.addWidget(paste_btn)


        download_btn = QPushButton()
        download_btn.setIcon(QIcon("assets/download_icon.png"))  # or .svg
        download_btn.setIconSize(QSize(20, 22))
        download_btn.setToolTip("Download query result")
        download_btn.clicked.connect(lambda: self.download_result(tab_content))
        results_info_layout.addWidget(download_btn)

        search_box = QLineEdit()
        search_box.setPlaceholderText("Search / Filter results...")
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "search.svg") 
        
        if os.path.exists(icon_path):
            search_icon = QIcon(icon_path)
            
            search_box.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        search_box.setFixedWidth(200)
        search_box.setObjectName("table_search_box")
        
        
        def on_search_text_changed(text):
            
            current_table = tab_content.findChild(QTableView, "results_table")
            if current_table:
                current_model = current_table.model()
               
                if isinstance(current_model, QSortFilterProxyModel):
                    current_model.setFilterFixedString(text)

        search_box.textChanged.connect(on_search_text_changed)
        results_info_layout.addWidget(search_box)



        results_info_layout.addStretch()
    

        # Info Label (e.g., "Showing rows 1 - 1000")
        rows_info_label = QLabel("Showing Rows")
        rows_info_label.setObjectName("rows_info_label")
        rows_info_label.setFont(font)
        results_info_layout.addWidget(rows_info_label)

        # Edit Button (Pencil Icon)
        rows_setting_btn = QToolButton()
        rows_setting_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
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
        def update_page_label(self, tab, row_count):

            next_btn = tab.findChild(QPushButton, "next_btn")
            prev_btn = tab.findChild(QPushButton, "prev_btn")
            page_label = tab.findChild(QLabel, "page_label")
    
            current_limit = getattr(tab, 'current_limit', 0)
            current_page = getattr(tab, 'current_page', 1)
            if page_label:
               page_label.setText(f"Page {current_page}")

            if next_btn:
        # If the query returned fewer rows than the limit, 
        # it means we have reached the last page of results.
               if current_limit > 0 and row_count < current_limit:
                  next_btn.setEnabled(False)
               elif current_limit > 0:
            # If we returned the full limit, there might be a next page.
                   next_btn.setEnabled(True)
               else:
            # No limit applied (Limit: All), so disable next page.
                   next_btn.setEnabled(False)

            if prev_btn:
        # Disable previous button if on the first page
               prev_btn.setEnabled(current_page > 1)
            # page_label.setText(f"Page {tab_content.current_page}")
            # prev_btn.setEnabled(tab_content.current_page > 1)


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

        def change_page(direction,tab):
            limit = getattr(tab, 'current_limit', 0)

            # If no limit is set, do nothing
            if not limit or limit <= 0:
                return 

            if direction == "next":
                tab.current_page += 1
                tab.current_offset += limit
            elif direction == "prev":
                if tab.current_page > 1:
                    tab.current_page -= 1
                    # Offset 
                    tab.current_offset = max(0, tab.current_offset - limit)

            # 1. UI 
            update_page_ui()
            self.execute_query()
        
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

        tab_status_label = QLabel("Ready")
        tab_status_label.setObjectName("tab_status_label")
        results_layout.addWidget(tab_status_label)

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
        main_vertical_splitter.setSizes([300, 300])

        tab_content.setLayout(layout)
        index = self.tab_widget.addTab(
            tab_content, f"Worksheet {self.tab_widget.count() + 1}"
        )
        self.tab_widget.setCurrentIndex(index)
        self.renumber_tabs()
        self._initialize_processes_model(tab_content)
        return tab_content
    
    def copy_current_result_table(self):
        tab = self.tab_widget.currentWidget()
        if not tab:
           return

        table_view = tab.findChild(QTableView, "results_table")
        if not table_view:
           return

        self.copy_result_with_header(table_view)


    def copy_result_with_header(self, table_view: QTableView):
        model = table_view.model()
        sel = table_view.selectionModel()

        if not model or not sel:
           return

        rows = []

        selected_rows = sel.selectedRows()
        selected_indexes = sel.selectedIndexes()

    # ---------- ROW SELECTION (pgAdmin default) ----------
        if selected_rows:
           columns = range(model.columnCount())

        # Header
           header = [
               str(model.headerData(col, Qt.Orientation.Horizontal) or "")
               for col in columns
            ]
           rows.append("\t".join(header))

        # Data
           for r in selected_rows:
               row = r.row()
               row_data = [
                str(model.index(row, col).data() or "")
                for col in columns
            ]
               rows.append("\t".join(row_data))

    # ---------- CELL SELECTION ----------
        elif selected_indexes:
            selected_indexes = sorted(
             selected_indexes, key=lambda x: (x.row(), x.column())
           )

            columns = sorted({i.column() for i in selected_indexes})

            header = [
            str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            for col in columns
        ]
            rows.append("\t".join(header))

            current_row = selected_indexes[0].row()
            row_data = []

            for idx in selected_indexes:
                if idx.row() != current_row:
                  rows.append("\t".join(row_data))
                  row_data = []
                  current_row = idx.row()

                row_data.append(str(idx.data() or ""))

            rows.append("\t".join(row_data))

        else:
           return

    # 🔥 THIS LINE IS THE MAGIC
        QApplication.clipboard().setText("\n".join(rows))


    def paste_to_editor(self):
        editor = self._get_current_editor()
        if editor:
           editor.paste()


    def delete_selected_row(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return

        table_name = getattr(current_tab, 'table_name', None)
        
        if not table_name:
            QMessageBox.warning(self, "Warning", "Cannot determine table name. Please run a SELECT query first.")
            return

        table_view = current_tab.findChild(QTableView, "results_table")
        if not table_view:
            return
        model = table_view.model()
        selection_model = table_view.selectionModel()
        proxy_rows = selection_model.selectedRows()

        selected_rows = []
        
        
        if isinstance(model, QSortFilterProxyModel):
            source_model = model.sourceModel()
            for proxy_index in proxy_rows:
               
                source_index = model.mapToSource(proxy_index)
                selected_rows.append(source_index)
           
            model = source_model 
        else:
            selected_rows = proxy_rows

        selection_model = table_view.selectionModel()
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            indexes = selection_model.selectedIndexes()
            rows_set = set(index.row() for index in indexes)
            model = table_view.model()
            selected_rows = [model.index(r, 0) for r in rows_set]

        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select a row to delete.")
            return

        reply = QMessageBox.question(
            self, 
            'Confirm Deletion',
            f"Are you sure you want to delete {len(selected_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.critical(self, "Error", "No active database connection found.")
            return

        db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
        model = table_view.model()
        deleted_count = 0
        errors = []

        conn = None
        try:
            
            if db_code == 'POSTGRES':
                conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
            elif 'SQLITE' in str(db_code):
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
            elif 'SERVICENOW' in str(db_code):
                conn = db.create_servicenow_connection(conn_data)
            
            if not conn:
                QMessageBox.critical(self, "Error", "Could not create database connection.")
                return

            cursor = conn.cursor()

            for index in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
                row_idx = index.row()
                
                item = model.item(row_idx, 0) 
                if not item: continue
                
                item_data = item.data(Qt.ItemDataRole.UserRole)
                pk_col = item_data.get("pk_col")
                pk_val = item_data.get("pk_val")

                if not pk_col or pk_val is None:
                    errors.append(f"Row {row_idx + 1}: No Primary Key found. Cannot delete safely.")
                    continue

                try:
                    sql = ""
                    if db_code == 'POSTGRES':
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = %s'
                        cursor.execute(sql, (pk_val,))
                    elif 'SQLITE' in str(db_code):
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = ?'
                        cursor.execute(sql, (pk_val,))
                    elif 'SERVICENOW' in str(db_code):
                        sql = f"DELETE FROM {table_name} WHERE {pk_col} = '{pk_val}'"
                        cursor.execute(sql)
                    
                    
                    model.removeRow(row_idx)
                    deleted_count += 1

                except Exception as inner_e:
                    errors.append(f"Row {row_idx + 1} Error: {str(inner_e)}")

            conn.commit()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))
            if conn: conn.close()
            return

        
        if deleted_count > 0:
            self.status.showMessage(f"Successfully deleted {deleted_count} row(s).", 3000)
            QMessageBox.information(self, "Success", f"Successfully deleted {deleted_count} row(s).")
            
        
        if errors:
            QMessageBox.warning(self, "Deletion Errors", "\n".join(errors[:5]))


    def model_to_dataframe(self, model):
        rows = model.rowCount()
        cols = model.columnCount()

        headers = [
           model.headerData(c, Qt.Orientation.Horizontal)
           for c in range(cols)
        ]

        data = []
        for r in range(rows):
           row = []
           for c in range(cols):
              index = model.index(r, c)
              row.append(model.data(index))
           data.append(row)

        return pd.DataFrame(data, columns=headers)

    def download_result(self, tab_content):
        table = tab_content.findChild(QTableView, "results_table")
        if not table or not table.model():
           QMessageBox.warning(self, "No Data", "No result data to download")
           return

        model = table.model()
        df = self.model_to_dataframe(model)

        if df.empty:
           QMessageBox.warning(self, "No Data", "Result is empty")
           return

        file_path, selected_filter = QFileDialog.getSaveFileName(
           self,
           "Download Result",
           "query_result",
           "CSV (*.csv);;Excel (*.xlsx)"
           )

        if not file_path:
           return

        try:
           if file_path.endswith(".csv"):
              df.to_csv(file_path, index=False)
           elif file_path.endswith(".xlsx"):
              df.to_excel(file_path, index=False)

           QMessageBox.information(
              self,
              "Success",
              f"Result downloaded successfully:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


    

    # Helper function for separator
    def create_vertical_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line


    def close_tab(self, index):
        tab = self.tab_widget.widget(index)
        if tab in self.running_queries:
            self.running_queries[tab].cancel()
            del self.running_queries[tab]
            if not self.running_queries:
                self.cancel_action.setEnabled(False)
        if tab in self.tab_timers:
            self.tab_timers[tab]["timer"].stop()
            if "timeout_timer" in self.tab_timers[tab]:
                self.tab_timers[tab]["timeout_timer"].stop()
            del self.tab_timers[tab]
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)
            self.renumber_tabs()
        else:
            self.status.showMessage("Must keep at least one tab", 3000)

    def renumber_tabs(self):
        for i in range(self.tab_widget.count()):
            self.tab_widget.setTabText(i, f"Worksheet {i + 1}")

    def add_empty_row(self):
        tab = self.tab_widget.currentWidget()
        if not tab: return

        table = tab.findChild(QTableView, "results_table")
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()
        

        if not model:
           return

        row = model.rowCount()
        model.insertRow(row)
        
        # --- NEW: new row index tracking ---
        tab.new_row_index = row 
        # ----------------------------------------

        table.scrollToBottom()
        table.setCurrentIndex(model.index(row, 0))
        table.edit(model.index(row, 0))

    def get_insert_data(self, model, row):
        values = []
        for col in range(model.columnCount()):
           item = model.item(row, col)
           values.append(item.text() if item else None)
        return values
    
    def save_new_row(self):
        """
        Handles saving BOTH new rows (INSERT) and modified cells (UPDATE).
        """
        tab = self.tab_widget.currentWidget()
        if not tab: return
        
        saved_any = False
        db_combo_box = tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        
        table = tab.findChild(QTableView, "results_table")
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()

        # ---------------------------------------------------------
        # PART 1: Handle INSERT (New Rows)
        # ---------------------------------------------------------
        if hasattr(tab, "new_row_index"):
            if not hasattr(tab, "table_name") or not hasattr(tab, "column_names"):
                 QMessageBox.warning(self, "Error", "Table context missing.")
            else:
                row_idx = tab.new_row_index
                values = []
                for col_idx in range(model.columnCount()):
                    item = model.item(row_idx, col_idx)
                    val = item.text() if item else None
                    if val == '': val = None
                    values.append(val)

                cols_str = ", ".join([f'"{c}"' for c in tab.column_names])
                db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
                
                sql = ""
                conn = None

                try:
                    if db_code == 'POSTGRES':
                        placeholders = ", ".join(["%s"] * len(values))
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                        
                    elif 'SQLITE' in str(db_code): 
                        placeholders = ", ".join(["?"] * len(values))
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    

                    elif 'SERVICENOW' in str(db_code):
                        placeholders = ", ".join(["?"] * len(values))
                        # ServiceNow-
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_servicenow_connection(conn_data)
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute(sql, values)
                        conn.commit()
                        conn.close()
                        del tab.new_row_index
                        saved_any = True
                        
                except Exception as e:
                    QMessageBox.critical(self, "Insert Error", f"Failed to insert row:\n{str(e)}")

        # ---------------------------------------------------------
        # PART 2: Handle UPDATE (Modified Cells)
        # ---------------------------------------------------------
        if hasattr(tab, "modified_coords") and tab.modified_coords:
            updates_count = 0
            errors = []
            
            coords_to_process = list(tab.modified_coords)
            
            db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
            conn = None
            
            try:
                if db_code == 'POSTGRES':
                    conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                elif 'SQLITE' in str(db_code):
                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                
                elif 'SERVICENOW' in str(db_code):
                    conn = db.create_servicenow_connection(conn_data)
                if conn:
                    cursor = conn.cursor()
                    
                    for row, col in coords_to_process:
                        item = model.item(row, col)
                        if not item: continue
                        
                        edit_data = item.data(Qt.ItemDataRole.UserRole)
                        pk_col = edit_data.get("pk_col")
                        pk_val = edit_data.get("pk_val")
                        col_name = edit_data.get("col_name")
                        new_val = item.text()
                        
                        val_to_update = None if new_val == '' else new_val

                        if not pk_col or pk_val is None:
                            if 'SERVICENOW' in str(db_code):
                                # fallback: 
                                pass
                            errors.append(f"Missing PK for column {col_name}")
                            continue

                        if db_code == 'POSTGRES':
                             sql = f'UPDATE {tab.table_name} SET "{col_name}" = %s WHERE "{pk_col}" = %s'
                        elif 'SQLITE' in str(db_code):
                             sql = f'UPDATE {tab.table_name} SET "{col_name}" = ? WHERE "{pk_col}" = ?'
                        else:
                            continue

                        try:
                            cursor.execute(sql, (val_to_update, pk_val))
                            
                            # Success: Update original value and clear background
                            edit_data['orig_val'] = new_val
                            item.setData(edit_data, Qt.ItemDataRole.UserRole)
                            item.setBackground(QColor(Qt.GlobalColor.white))
                            
                            if (row, col) in tab.modified_coords:
                                tab.modified_coords.remove((row, col))
                                
                            updates_count += 1
                        except Exception as inner_e:
                            errors.append(str(inner_e))

                    conn.commit()
                    conn.close()
                    
                    if updates_count > 0:
                        saved_any = True

            except Exception as e:
                 QMessageBox.critical(self, "Connection Error", f"Failed to connect for updates:\n{str(e)}")

            if errors:
                QMessageBox.warning(self, "Update Warnings", f"Some updates failed:\n" + "\n".join(errors[:5]))

        # ---------------------------------------------------------
        # Final Feedback
        # ---------------------------------------------------------
        if saved_any:
            self.status.showMessage("Changes saved successfully!", 3000)
            QMessageBox.information(self, "Success", "Changes saved successfully!")
        elif not hasattr(tab, "new_row_index") and (not hasattr(tab, "modified_coords") or not tab.modified_coords):
            self.status.showMessage("No changes to save.", 3000)


    def load_data(self):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Object Explorer"])
        
       
        hierarchical_data = db.get_hierarchy_data()

        for connection_type_data in hierarchical_data:
            # --- LEVEL 1: Connection Type (e.g., PostgreSQL, Oracle) ---
            code = connection_type_data['code']
            connection_type_item = QStandardItem(connection_type_data['name'])
            connection_type_item.setData(code, Qt.ItemDataRole.UserRole)
            connection_type_item.setData(connection_type_data['id'], Qt.ItemDataRole.UserRole + 1)
            
            # Icon set for root type
            self._set_tree_item_icon(connection_type_item, level="TYPE", code=code)

            for connection_group_data in connection_type_data['usf_connection_groups']:
                # --- LEVEL 2: Connection Group (e.g., Production, Dev) ---
                connection_group_item = QStandardItem(connection_group_data['name'])
                connection_group_item.setData(connection_group_data['id'], Qt.ItemDataRole.UserRole + 1)
                
                # Icon set for group
                self._set_tree_item_icon(connection_group_item, level="GROUP")

                for connection_data in connection_group_data['usf_connections']:
                    # --- LEVEL 3: Individual Connection ---
                    connection_item = QStandardItem(connection_data['short_name'])
                    connection_item.setData(connection_data, Qt.ItemDataRole.UserRole)

                    # Icon set for specific connection
                    self._set_tree_item_icon(connection_item, level="CONNECTION", code=code)
                    
                   
                    connection_group_item.appendRow(connection_item)

                
                connection_type_item.appendRow(connection_group_item)
            
            
            self.model.appendRow(connection_type_item)

    def _set_tree_item_icon(self, item, level, code=""):
        """
        Applies icons based on the connection type code and level.
        """
        
        if level == "GROUP":
            item.setIcon(QIcon("assets/folder-open.svg")) 
            return
        
        if level == "SCHEMA":
            item.setIcon(QIcon("assets/schema.svg")) 
            return

       
        if level == "TABLE":
            item.setIcon(QIcon("assets/table.svg"))
            return
        if level == "VIEW":
            item.setIcon(QIcon("assets/view_icon.png"))
            return
    
        if level == "COLUMN":
            item.setIcon(QIcon("assets/column_icon.png"))
            return

        icon_map = {
            "POSTGRES": "assets/postgresql.svg",
            "SQLITE": "assets/sqlite.svg",
            "ORACLE_DB": "assets/oracle.svg",
            "ORACLE_FA": "assets/oracle_fusion.svg",
            "SERVICENOW": "assets/servicenow.svg",
            "CSV": "assets/csv.svg"
        }

        icon_path = icon_map.get(code, "assets/database.svg")
        
       
        item.setIcon(QIcon(icon_path))
  

    def _save_tree_expansion_state(self):
        saved_paths = []
        model = self.model
        tree = self.tree
        
        # Depth 1: Connection Type ( PostgreSQL, SQLite)
        for row in range(model.rowCount()):
            type_index = model.index(row, 0)
            if tree.isExpanded(type_index):
                type_name = type_index.data(Qt.ItemDataRole.DisplayRole)
                
                saved_paths.append((type_name, None))

                # Depth 2: Connection Group (store group name)
                for group_row in range(model.rowCount(type_index)):
                    group_index = model.index(group_row, 0, type_index)
                    if tree.isExpanded(group_index):
                        group_name = group_index.data(Qt.ItemDataRole.DisplayRole)
                        # if group connection expand 
                        saved_paths.append((type_name, group_name))
        
        self._saved_tree_paths = saved_paths

    def _restore_tree_expansion_state(self):
        if not hasattr(self, '_saved_tree_paths') or not self._saved_tree_paths:
            return

        model = self.model
        tree = self.tree

        for row in range(model.rowCount()): # Depth 1: Connection Type
            type_index = model.index(row, 0)
            type_name = type_index.data(Qt.ItemDataRole.DisplayRole)
            
            if (type_name, None) in self._saved_tree_paths:
                tree.expand(type_index)
            
            for group_row in range(model.rowCount(type_index)): # Depth 2: Connection Group
                group_index = model.index(group_row, 0, type_index)
                group_name = group_index.data(Qt.ItemDataRole.DisplayRole)
                
                if (type_name, group_name) in self._saved_tree_paths:
                    tree.expand(group_index)

        self._saved_tree_paths = []

    def delete_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        connection_id = conn_data.get("id")
        reply = QMessageBox.question(self, "Delete Connection", "Are you sure you want to delete this connection?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection(connection_id)
                
                
                self._save_tree_expansion_state()   
                self.load_data()                   
                self._restore_tree_expansion_state() 
               

                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete connection:\n{e}")


    def item_clicked(self, index):
        item = self.model.itemFromIndex(index)
        if not item:
            return
            
        depth = self.get_item_depth(item)
        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        if depth == 3:
            conn_data = item.data(Qt.ItemDataRole.UserRole)
            if not conn_data:
                return
            parent_group = item.parent()
            if not parent_group:
                return
            connection_type = parent_group.parent()
            if not connection_type:
                return
            connection_type_name = connection_type.text().lower()
            if "postgres" in connection_type_name and conn_data.get("host"):
                self.status.showMessage(
                    f"Loading schema for {conn_data.get('name')}...", 3000)
                self.load_postgres_schema(conn_data)
            elif "sqlite" in connection_type_name and conn_data.get("db_path"):
                self.status.showMessage(
                    f"Loading schema for {conn_data.get('name')}...", 3000)
                self.load_sqlite_schema(conn_data)
                
            elif "csv" in connection_type_name and conn_data.get("db_path"):
                # ← NEW: CSV support using CData
                self.status.showMessage(
                   f"Loading CSV folder for {conn_data.get('name')}...", 3000)
                self.load_csv_schema(conn_data)

            elif "servicenow" in connection_type_name:
                self.status.showMessage(
                   f"Loading ServiceNow schema for {conn_data.get('name')}...", 3000
                )
                self.load_servicenow_schema(conn_data)
        
            elif "oracle" in connection_type_name:
                self.status.showMessage(
                    "Oracle connections are not currently supported.", 5000)
                QMessageBox.information(
                    self, "Not Supported", "Connecting to Oracle databases is not supported in this version.")
            else:
                self.status.showMessage("Unknown connection type.", 3000)


    def item_double_clicked(self, index: QModelIndex):
        #item_text = index.data(Qt.ItemDataRole.DisplayRole)
        item = self.model.itemFromIndex(index)
        depth = self.get_item_depth(item)
        
        if depth == 3:
            print(f"Double-clicked on: {item.text()}")
            # Place your custom logic here

    def get_item_depth(self, item):
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        return depth + 1
    
    
    def show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        if not index.isValid(): return
        item = self.model.itemFromIndex(index)
        depth = self.get_item_depth(item)
        menu = QMenu()
        if depth == 1:
            add_connection_group = QAction("Add Group", self)
            add_connection_group.triggered.connect(lambda: self.add_connection_group(item))
            menu.addAction(add_connection_group)
        
        elif depth == 2:  # Subcategory level
            parent_item = item.parent()
            code = parent_item.data(Qt.ItemDataRole.UserRole) if parent_item else None
            
            if code == 'POSTGRES':
               add_pg_action = QAction("New PostgreSQL Connection", self)
               add_pg_action.triggered.connect(lambda: self.add_postgres_connection(item))
               menu.addAction(add_pg_action)
            elif code == 'SQLITE':
               add_sqlite_action = QAction("New SQLite Connection", self)
               add_sqlite_action.triggered.connect(lambda: self.add_sqlite_connection(item))
               menu.addAction(add_sqlite_action)
            elif code in ['ORACLE_FA', 'ORACLE_DB']:
               add_oracle_action = QAction("New Oracle Connection", self)
               add_oracle_action.triggered.connect(lambda: self.add_oracle_connection(item))
               menu.addAction(add_oracle_action)
               
            elif code == 'CSV':
               add_sqlite_action = QAction("New CSV Connection", self)
               add_sqlite_action.triggered.connect(lambda: self.add_csv_connection(item))
               menu.addAction(add_sqlite_action)
               
            elif code == 'SERVICENOW':
               add_sn_action = QAction("New ServiceNow Connection", self)
               add_sn_action.triggered.connect(lambda: self.add_servicenow_connection(item))
               menu.addAction(add_sn_action)


        elif depth == 3:
            conn_data = item.data(Qt.ItemDataRole.UserRole)
            if conn_data:
                view_details_action = QAction("View details", self)
                view_details_action.triggered.connect(
                    lambda: self.show_connection_details(item))
                menu.addAction(view_details_action)
                menu.addSeparator()
            
                
            # Get the connection type code from grandparent
            parent_item = item.parent()
            grandparent_item = parent_item.parent() if parent_item else None
            code = grandparent_item.data(Qt.ItemDataRole.UserRole) if grandparent_item else None
            # Edit connection action based on type
            if code == 'SQLITE' and conn_data.get("db_path"):
               edit_action = QAction("Edit Connection", self)
               edit_action.triggered.connect(lambda: self.edit_connection(item))
               menu.addAction(edit_action)
            elif code == 'POSTGRES' and conn_data.get("host"):
               edit_action = QAction("Edit Connection", self)
               edit_action.triggered.connect(lambda: self.edit_pg_connection(item))
               menu.addAction(edit_action)
            elif code in ['ORACLE_FA', 'ORACLE_DB']:
               edit_action = QAction("Edit Connection", self)
               edit_action.triggered.connect(lambda: self.edit_oracle_connection(item))
               menu.addAction(edit_action)  
               
            elif code == 'CSV' and conn_data.get("db_path"):
               edit_action = QAction("Edit Connection", self)
               edit_action.triggered.connect(lambda: self.edit_csv_connection(item))
               menu.addAction(edit_action)  
            
            elif code == 'SERVICENOW':
                edit_action = QAction("Edit Connection", self)
                edit_action.triggered.connect(lambda: self.edit_servicenow_connection(item))
                menu.addAction(edit_action)
               
            delete_action = QAction("Delete Connection", self)
            delete_action.triggered.connect(lambda: self.delete_connection(item))
            menu.addAction(delete_action)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def show_connection_details(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            QMessageBox.warning(self, "Error", "Could not retrieve connection data.")
            return
      
        parent = item.parent()
        grandparent = parent.parent() if parent else None
        code = grandparent.data(Qt.ItemDataRole.UserRole) if grandparent else None

        details_title = f"Connection Details: {conn_data.get('name')}"

        if conn_data.get("host"):
            details_text = (
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> PostgreSQL<br>"
                f"<b>Host:</b> {conn_data.get('host', 'N/A')}<br>"
                f"<b>Port:</b> {conn_data.get('port', 'N/A')}<br>"
                f"<b>Database:</b> {conn_data.get('database', 'N/A')}<br>"
                f"<b>User:</b> {conn_data.get('user', 'N/A')}"
            )
        elif conn_data.get("db_path"):
          
            if  code == 'CSV':
                db_type_str = "CSV"
                path_label = "Folder Path"
            else:
                # Default to SQLite if not CSV
                db_type_str = "SQLite"
                path_label = "Database Path"
          
            details_text = (
              
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> {db_type_str}<br>"
                f"<b>{path_label}:</b> {conn_data.get('db_path', 'N/A')}"
            #   f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
            #   f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
            #   f"<b>Type:</b> SQLite<br>"
            #   f"<b>Database Path:</b> {conn_data.get('db_path', 'N/A')}"
            )
          
        elif conn_data.get("instance_url"):
            details_text = (
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> ServiceNow<br>"
                f"<b>Instance URL:</b> {conn_data.get('instance_url', 'N/A')}<br>"
                f"<b>User:</b> {conn_data.get('user', 'N/A')}"
            ) 
        else:
            details_text = "Could not determine connection type or details."

        msg = QMessageBox(self)
        msg.setWindowTitle(details_title)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)

        label = QLabel(details_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMinimumSize(400, 200)
        msg.layout().addWidget(label, 0, 1)

        msg.exec()


    def add_connection_group(self, parent_item):
        name, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if ok and name:
            parent_id = parent_item.data(Qt.ItemDataRole.UserRole+1)
            try:
                db.add_connection_group(name, parent_id)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add group:\n{e}")

    def add_postgres_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = PostgresConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save PostgreSQL connection:\n{e}")

    def add_sqlite_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = SQLiteConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save SQLite connection:\n{e}")
                
                
    def add_oracle_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = OracleConnectionDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
               db.add_connection(data, connection_group_id)
               self._save_tree_expansion_state()
               self.load_data()
               self._restore_tree_expansion_state()
               self.refresh_all_comboboxes()
            except Exception as e:
               QMessageBox.critical(self, "Error", f"Failed to save Oracle connection:\n{e}")


    def edit_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if conn_data and conn_data.get("db_path"):
            dialog = SQLiteConnectionDialog(self, conn_data=conn_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.getData()
                try:
                    db.update_connection(new_data)
                    self._save_tree_expansion_state()
                    self.load_data()
                    self._restore_tree_expansion_state()
                    self.refresh_all_comboboxes()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to update SQLite connection:\n{e}")

    def edit_pg_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data: return
        dialog = PostgresConnectionDialog(self, is_editing=True)
        dialog.name_input.setText(conn_data.get("name", ""))
        dialog.short_name_input.setText(conn_data.get("short_name", ""))
        dialog.host_input.setText(conn_data.get("host", ""))
        dialog.port_input.setText(str(conn_data.get("port", "")))
        dialog.db_input.setText(conn_data.get("database", ""))
        dialog.user_input.setText(conn_data.get("user", ""))
        dialog.password_input.setText(conn_data.get("password", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            new_data["id"] = conn_data.get("id") # Make sure to pass the ID for update
            try:
                db.update_connection(new_data)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state() 
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update PostgreSQL connection:\n{e}")
                
    
    def edit_oracle_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
           return
        dialog = OracleConnectionDialog(self, is_editing=True)
        dialog.name_input.setText(conn_data.get("name", ""))
        dialog.user_input.setText(conn_data.get("user", ""))
        dialog.password_input.setText(conn_data.get("password", ""))
        dialog.dsn_input.setText(conn_data.get("dsn", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            new_data["id"] = conn_data.get("id")  # pass ID for update
            try:
              db.update_connection(new_data)
              self._save_tree_expansion_state()
              self.load_data()
              self._restore_tree_expansion_state()
              self.refresh_all_comboboxes()
            except Exception as e:
               QMessageBox.critical(self, "Error", f"Failed to update Oracle connection:\n{e}")
    
    
    
    def add_servicenow_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = ServiceNowConnectionDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(
                   self,
                   "Error",
                   f"Failed to save ServiceNow connection:\n{e}"
                )

    
    def edit_servicenow_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
           return

        dialog = ServiceNowConnectionDialog(self, conn_data=conn_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                db.update_connection(new_data)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to update ServiceNow connection:\n{e}"
                )

    
    def delete_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        connection_id = conn_data.get("id")
        reply = QMessageBox.question(self, "Delete Connection", "Are you sure you want to delete this connection?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection(connection_id)
                self.load_data()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete connection:\n{e}")

    def refresh_all_comboboxes(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            combo_box = tab.findChild(QComboBox, "db_combo_box")
            if combo_box:
                self.load_joined_connections(combo_box)

    def load_joined_connections(self, combo_box):
        try:
            current_data = combo_box.currentData()
            combo_box.clear()
            connections = db.get_all_connections_from_db()
            for connection in connections:
                # The data for the combobox is now the full connection dictionary
                conn_data = {key: connection[key] for key in connection if key != 'display_name'}
                combo_box.addItem(connection["display_name"], conn_data)

            if current_data:
                for i in range(combo_box.count()):
                    if combo_box.itemData(i) and combo_box.itemData(i)['id'] == current_data['id']:
                        combo_box.setCurrentIndex(i)
                        break
        except Exception as e:
            self.status.showMessage(f"Error loading connections: {e}", 4000)
            
            
    def add_csv_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)

        dialog = CSVConnectionDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()
                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save CSV connection:\n{e}")
                
                
    def edit_csv_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)

        # Only allow editing if folder_path exists (CSV connection)
        if not conn_data or not conn_data.get("db_path"):
            QMessageBox.warning(self, "Invalid", "This is not a CSV connection.")
            return

        dialog = CSVConnectionDialog(self, conn_data=conn_data)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                db.update_connection(new_data)
                self._save_tree_expansion_state()
                self.load_data()
                self._restore_tree_expansion_state()

                self.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update CSV connection:\n{e}")

    def show_info(self, message: str):
       QMessageBox.information(self, "Info", message)

# {siam}
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


    def handle_query_result(self, target_tab, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
        
        # Stop timers
        if target_tab in self.tab_timers:
            self.tab_timers[target_tab]["timer"].stop()
            self.tab_timers[target_tab]["timeout_timer"].stop()
            del self.tab_timers[target_tab]

        self.save_query_to_history(conn_data, query, "Success", row_count, elapsed_time)

        # Get widgets
        table_view = target_tab.findChild(QTableView, "results_table")
        message_view = target_tab.findChild(QTextEdit, "message_view")
        tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
        rows_info_label = target_tab.findChild(QLabel, "rows_info_label")
        
        # Access Result Stack
        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        results_info_bar = target_tab.findChild(QWidget, "resultsInfoBar")

        if message_view:
            message_view.clear()

        if is_select_query:
             # Check for Explain Analyze Result
            if query.upper().strip().startswith("EXPLAIN (ANALYZE,"):
                try:
                    # Result is usually [[json_data]]
                    if results and len(results) > 0 and len(results[0]) > 0:
                        json_data = results[0][0]
                        # Get visualizer
                        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
                        explain_visualizer = results_stack.findChild(ExplainVisualizer)
                        if explain_visualizer:
                            explain_visualizer.load_plan(json_data)
                        
                        self.stop_spinner(target_tab, success=True, target_index=5) # Explain tab
                        
                        msg = f"Explain Analyze executed successfully.\nTime: {elapsed_time:.2f} sec"
                        status = f"Explain Analyze executed | Time: {elapsed_time:.2f} sec"
                        
                        # Update message view and status
                        if message_view:
                            previous_text = message_view.toPlainText()
                            if previous_text: message_view.append("\n" + "-"*50 + "\n")
                            message_view.append(msg)
                        if tab_status_label: tab_status_label.setText(status)
                        self.status_message_label.setText("Ready")

                        # Cleanup
                        if target_tab in self.running_queries: del self.running_queries[target_tab]
                        if not self.running_queries: self.cancel_action.setEnabled(False)
                        return
                except Exception as e:
                    print(f"Error parsing explain result: {e}")
                    # Fall through to normal display if parsing fails


        # --- Robust Query Type Detection ---
        match_query = re.sub(r'--.*?\n|/\*.*?\*/', '', query, flags=re.DOTALL).strip().upper()
        first_word = match_query.split()[0] if match_query.split() else ""
        
        q_type_parsed = ""
        parsed = sqlparse.parse(query)
        if parsed:
            for statement in parsed:
                t = statement.get_type().upper()
                if t != 'UNKNOWN':
                    q_type_parsed = t
                    break
        
        q_type = q_type_parsed if q_type_parsed and q_type_parsed != 'UNKNOWN' else first_word
        
        # Structural commands (DDL)
        is_structural = q_type in ["CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COMMENT", "RENAME"]
        
        # SELECT check
        is_select = q_type == "SELECT" or first_word == "SELECT"
        
        # --- DECIDE WHICH TAB TO OPEN ---
        final_tab_index = 0 # Default to Output

        # Condition: If it is NOT structural AND (it is Select OR has columns) -> Show Output Tab (0)
        if not is_structural and (is_select or (columns and len(columns) > 0)):
            final_tab_index = 0
            
            target_tab.column_names = columns
            target_tab.modified_coords = set() 

            # Extract table name logic
            match = re.search(r"FROM\s+([\"\[\]\w\.]+)", query, re.IGNORECASE)
            if match:
                extracted_table = match.group(1)
                target_tab.table_name = extracted_table.replace('"', '').replace('[', '').replace(']', '')
                if "." in target_tab.table_name:
                    parts = target_tab.table_name.split('.')
                    target_tab.schema_name = parts[0]
                    target_tab.real_table_name = parts[1]
                else:
                    target_tab.real_table_name = target_tab.table_name
            else:
                if hasattr(target_tab, 'table_name'): del target_tab.table_name

            # Row count logic
            current_offset = getattr(target_tab, 'current_offset', 0)
            if rows_info_label:
                if row_count > 0:
                    start_row = current_offset + 1
                    end_row = current_offset + row_count
                    rows_info_label.setText(f"Showing rows {start_row} - {end_row}")
                else:
                    rows_info_label.setText("No rows returned")
            
            page_label = target_tab.findChild(QLabel, "page_label")
            if page_label:
                self.update_page_label(target_tab, row_count)

            # Populate Model
            model = QStandardItemModel(table_view)
            model.setColumnCount(len(columns))
            model.setRowCount(len(results))
            
            meta_columns = None
            pk_indices = [] 
            if hasattr(target_tab, 'real_table_name'):
                meta_columns = self.get_table_column_metadata(conn_data, target_tab.real_table_name)

            headers = []
            if meta_columns and len(meta_columns) == len(columns):
                for idx, col in enumerate(meta_columns):
                    col_str = str(col)
                    if "[PK]" in col_str:
                        pk_indices.append(idx)
                    if isinstance(col, str):
                        parts = col.split(maxsplit=1)
                        col_name = parts[0]
                        data_type = parts[1] if len(parts) > 1 else ""
                    else:
                        col_name = str(col)
                        data_type = ""
                    headers.append(f"{col_name}\n{data_type}")
            else:
                headers = [f"{col}\n" for col in columns]
                if columns and any(x in columns[0].lower() for x in ['id', 'uuid', 'pk']):
                    pk_indices.append(0)

            for col_idx, header_text in enumerate(headers):
                model.setHeaderData(col_idx, Qt.Orientation.Horizontal, header_text)

            # Fill Data
            for row_idx, row in enumerate(results):
                pk_val = None
                pk_col_name = None
                if pk_indices:
                    pk_idx = pk_indices[0] 
                    pk_val = row[pk_idx]
                    pk_col_name = columns[pk_idx]

                for col_idx, cell in enumerate(row):
                    item = QStandardItem(str(cell))
                    edit_data = {
                        "pk_col": pk_col_name,
                        "pk_val": pk_val,
                        "orig_val": cell,
                        "col_name": columns[col_idx]
                    }
                    item.setData(edit_data, Qt.ItemDataRole.UserRole)
                    model.setItem(row_idx, col_idx, item)

            # Proxy Model
            try: model.itemChanged.disconnect() 
            except: pass
            model.itemChanged.connect(lambda item: self.handle_cell_edit(item, target_tab))

            proxy_model = QSortFilterProxyModel(table_view)
            proxy_model.setSourceModel(model)
            proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            proxy_model.setFilterKeyColumn(-1)
            
            table_view.setModel(proxy_model)
            search_box = target_tab.findChild(QLineEdit, "table_search_box")
            if search_box and search_box.text():
                proxy_model.setFilterFixedString(search_box.text())
            
            msg = f"Query executed successfully.\n\nTotal rows: {row_count}\nTime: {elapsed_time:.2f} sec"
            status = f"Query executed successfully | Total rows: {row_count} | Time: {elapsed_time:.2f} sec"
            
            if results_info_bar: results_info_bar.show()

        else:
            # --- Non-result-set query (DDL/DML) -> Show Messages Tab (1) ---
            final_tab_index = 1
            
            table_view.setModel(QStandardItemModel(table_view))
            should_refresh_tree = False

            if q_type.startswith("INSERT"):
                msg = f"INSERT 0 {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"INSERT 0 {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("UPDATE"):
                msg = f"UPDATE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"UPDATE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("DELETE"):
                msg = f"DELETE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"DELETE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("CREATE"):
                msg = f"CREATE TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"Table Created | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            elif q_type.startswith("DROP"):
                msg = f"DROP TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"DROP success | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            # elif q_type.startswith("ALTER"):
            #     msg = f"ALTER COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"ALTER success | Time: {elapsed_time:.2f} sec"
            #     should_refresh_tree = True
            # elif q_type.startswith("TRUNCATE"):
            #     msg = f"TRUNCATE COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"TRUNCATE success | Time: {elapsed_time:.2f} sec"
            else:
                msg = f"Query executed successfully.\n\nRows affected: {row_count}\nTime: {elapsed_time:.2f} sec"
                status = f"Rows affected: {row_count} | Time: {elapsed_time:.2f} sec"

            if should_refresh_tree:
                self.refresh_object_explorer()

            if results_info_bar: results_info_bar.hide()

        if message_view:
            message_view.append(msg)
            sb = message_view.verticalScrollBar()
            sb.setValue(sb.maximum())

        if tab_status_label:
            tab_status_label.setText(status)

        self.status_message_label.setText("Ready")
        
        # --- CRITICAL FIX: Pass the calculated final_tab_index ---
        self.stop_spinner(target_tab, success=True, target_index=final_tab_index) 

        if target_tab in self.running_queries:
            del self.running_queries[target_tab]
        if not self.running_queries:
            self.cancel_action.setEnabled(False)

    def handle_cell_edit(self, item, tab):
        """
        Track changes locally using coordinates (row, col).
        """
        # 1. Retrieve Context Data
        edit_data = item.data(Qt.ItemDataRole.UserRole)
        if not edit_data:
            return 

        orig_val = edit_data.get("orig_val")
        new_val = item.text()

        # Initialize tracking set if missing
        if not hasattr(tab, "modified_coords"):
            tab.modified_coords = set()

        # 2. Check if value actually changed
        val_changed = str(orig_val) != str(new_val)
        if str(orig_val) == 'None' and new_val == '': val_changed = False

        row, col = item.row(), item.column()

        if val_changed:
            # Change background to indicate unsaved change
            item.setBackground(QColor("#FFFDD0")) 
            # Store Coordinate (Hashable)
            tab.modified_coords.add((row, col))
            self.status.showMessage("Cell modified")
        else:
            # Revert background
            item.setBackground(QColor(Qt.GlobalColor.white))
            if (row, col) in tab.modified_coords:
                tab.modified_coords.remove((row, col))


    def get_table_column_metadata(self, conn_data, table_name):
      """
        Returns a list of column headers with pgAdmin-style info like:
        emp_id [PK] integer, emp_name character varying(100)
        Uses create_postgres_connection() for consistent DB connection handling.
      """
      headers = []
      conn = None
      try:
        # ✅ Use your reusable connection function
        conn = db.create_postgres_connection(
            host=conn_data["host"],
            port=conn_data["port"],
            database=conn_data["database"],
            user=conn_data["user"],
            password=conn_data["password"]
        )
        if not conn:
            print("Failed to establish connection for metadata fetch.")
            return []

        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.attname AS column_name,
                format_type(a.atttypid, a.atttypmod) AS data_type,
                CASE WHEN ct.contype = 'p' THEN '[PK]'
                     WHEN ct.contype = 'f' THEN '[FK]'
                     ELSE ''
                END AS constraint_type
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_constraint ct 
              ON ct.conrelid = c.oid 
             AND a.attnum = ANY(ct.conkey)
            WHERE c.relname = %s 
              AND a.attnum > 0 
              AND NOT a.attisdropped
            ORDER BY a.attnum;
        """, (table_name,))
        rows = cur.fetchall()
        for col, dtype, constraint in rows:
            headers.append(f"{col} {constraint} {dtype}".strip())
      except Exception as e:
        print(f"Metadata fetch error for table '{table_name}': {e}")
      finally:
        if conn:
            conn.close()
      return headers

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

    def stop_spinner(self, target_tab, success=True, target_index=0):
        if not target_tab: return
        stacked_widget = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        if stacked_widget:
            spinner_label = stacked_widget.findChild(QLabel, "spinner_label")
            if spinner_label and spinner_label.movie():
                spinner_label.movie().stop()
            header = target_tab.findChild(QWidget, "resultsHeader")
            buttons = header.findChildren(QPushButton)
            if success:
                stacked_widget.setCurrentIndex(target_index)
                if buttons: 
                    buttons[0].setChecked(target_index == 0) 
                    buttons[1].setChecked(target_index == 1) 
                    buttons[2].setChecked(target_index == 2)
                    buttons[3].setChecked(target_index == 3)
            else:
                stacked_widget.setCurrentIndex(1)
                if buttons: 
                    buttons[0].setChecked(False) 
                    buttons[1].setChecked(True)
                    buttons[2].setChecked(False)
                    buttons[3].setChecked(False)


    def update_page_label(self, target_tab, row_count):
        page_label = target_tab.findChild(QLabel, "page_label")
        if not page_label:
           return

        limit_val = getattr(target_tab, 'current_limit', 1000)
        offset_val = getattr(target_tab, 'current_offset', 0)

        if row_count <= 0 or limit_val == 0:
           page_label.setText("Page 1")
           return

           current_page = (offset_val // limit_val) + 1
           page_label.setText(f"Page {current_page}")



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
        conn_id = conn_data.get("id")
        if not conn_id: return
        try:
            db.save_query_history(conn_id, query, status, rows, duration)
        except Exception as e:
            self.status.showMessage(f"Could not save query to history: {e}", 4000)

    def load_connection_history(self, target_tab):
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Connection History'])
        history_list_view.setModel(model)
        history_details_view.clear()
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        conn_id = conn_data.get("id")
        try:
            history = db.get_query_history(conn_id)
            for row in history:
                history_id, query, ts, status, rows, duration = row
                short_query = ' '.join(query.split())[:70] + ('...' if len(query) > 70 else '')
                dt = datetime.datetime.fromisoformat(ts)
                display_text = f"{short_query}\n{dt.strftime('%Y-%m-%d %H:%M:%S')}"
                item = QStandardItem(display_text)
                item.setData({"id": history_id, "query": query, "timestamp": dt.strftime('%Y-%m-%d %H:%M:%S'), "status": status, "rows": rows, "duration": f"{duration:.3f} sec"}, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load query history:\n{e}")

    def display_history_details(self, index, target_tab):
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        if not index.isValid() or not history_details_view: return
        data = index.model().itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
        details_text = f"Timestamp: {data['timestamp']}\nStatus: {data['status']}\nDuration: {data['duration']}\nRows: {data['rows']}\n\n-- Query --\n{data['query']}"
        history_details_view.setText(details_text)

    def _get_selected_history_item(self, target_tab):
        """Helper to get the selected item's data from the history list."""
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        selected_indexes = history_list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self, "No Selection", "Please select a history item first.")
            return None
        item = selected_indexes[0].model().itemFromIndex(selected_indexes[0])
        return item.data(Qt.ItemDataRole.UserRole)

    def copy_history_query(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            clipboard = QApplication.clipboard()
            clipboard.setText(history_data['query'])
            self.status_message_label.setText("Query copied to clipboard.")

    def copy_history_to_editor(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            editor_stack = target_tab.findChild(QStackedWidget, "editor_stack")
            query_editor = target_tab.findChild(CodeEditor, "query_editor")
            query_editor.setPlainText(history_data['query'])
            
            # Switch back to the query editor view
            editor_stack.setCurrentIndex(0)
            query_view_btn = target_tab.findChild(QPushButton, "Query")
            history_view_btn = target_tab.findChild(QPushButton, "Query History")
            if query_view_btn: query_view_btn.setChecked(True)
            if history_view_btn: history_view_btn.setChecked(False)
            
            self.status_message_label.setText("Query copied to editor.")

    def remove_selected_history(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if not history_data: return
        
        history_id = history_data['id']
        reply = QMessageBox.question(self, "Remove History", "Are you sure you want to remove the selected query history?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_history(history_id)
                self.load_connection_history(target_tab) # Refresh the view
                target_tab.findChild(QTextEdit, "history_details_view").clear()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove history item:\n{e}")


    def remove_all_history_for_connection(self, target_tab):
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.warning(self, "No Connection", "Please select a connection first.")
            return
        conn_id = conn_data.get("id")
        conn_name = db_combo_box.currentText()
        reply = QMessageBox.question(self, "Remove All History", f"Are you sure you want to remove all history for the connection:\n'{conn_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_all_history(conn_id)
                self.load_connection_history(target_tab)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear history for this connection:\n{e}")

    # --- Schema Loading Methods ---

    def load_sqlite_schema(self, conn_data):
        self.schema_model.clear()
        self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
        self.schema_tree.setColumnWidth(0, 200)
        self.schema_tree.setColumnWidth(1, 100)
        
        header = self.schema_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.schema_tree.setStyleSheet("""
            QHeaderView {
             background-color: #a9a9a9;
                                       
            }
            QHeaderView::section {
            border-right: 1px solid #d3d3d3;
            padding: 4px;
            background-color: #a9a9a9;   
            }
           QTreeView {
           gridline-color: #a9a9a9;
           }
""")

        db_path = conn_data.get("db_path")
        if not db_path or not os.path.exists(db_path):
            self.status.showMessage(
                f"Error: SQLite DB path not found: {db_path}", 5000)
            return
        try:
            conn = sqlite.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name;")
            for name, type_str in cursor.fetchall():
                # icon = QIcon(
                #     "assets/table_icon.png") if type_str == 'table' else QIcon("assets/view_icon.png")
                name_item = QStandardItem(name)
                name_item.setEditable(False)
                if type_str == 'table':
                    self._set_tree_item_icon(name_item,level = "TABLE")
                else:
                    self._set_tree_item_icon(name_item,level="VIEW")

                # --- START MODIFICATION ---
                
                # 1. Add table_name to item_data so load_sqlite_table_details can find it
                item_data = {
                    'db_type': 'sqlite', 
                    'conn_data': conn_data, 
                    'table_name': name  # This was missing
                }
                name_item.setData(item_data, Qt.ItemDataRole.UserRole)
                
                type_item = QStandardItem(type_str.capitalize())
                type_item.setEditable(False)
                
                # 2. Add "Loading..." child to tables/views to make them expandable
                if type_str in ['table', 'view']:
                    name_item.appendRow(QStandardItem("Loading..."))

                # --- END MODIFICATION ---

                self.schema_model.appendRow([name_item, type_item])
            conn.close()
            
            if hasattr(self, '_expanded_connection'):
                try:
                    self.schema_tree.expanded.disconnect(
                        self._expanded_connection)
                except TypeError:
                    pass
            
            # --- START MODIFICATION ---
            # 3. Connect the expand signal for this tree
            self._expanded_connection = self.schema_tree.expanded.connect(
                self.load_tables_on_expand)
            # --- END MODIFICATION ---

        except Exception as e:
            self.status.showMessage(f"Error loading SQLite schema: {e}", 5000)

    def load_postgres_schema(self, conn_data):
        try:
            self.schema_model.clear()
            self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            self.pg_conn = psycopg2.connect(host=conn_data["host"], database=conn_data["database"],
                                            user=conn_data["user"], password=conn_data["password"], port=int(conn_data["port"]))
            cursor = self.pg_conn.cursor()
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast') ORDER BY schema_name;")
            for (schema_name,) in cursor.fetchall():
                schema_item = QStandardItem(schema_name)
                # schema_item = QStandardItem(
                #     QIcon("assets/schema_icon.png"), schema_name)
                schema_item.setEditable(False)
                self._set_tree_item_icon(schema_item, level="SCHEMA")
                schema_item.setData({'db_type': 'postgres', 'schema_name': schema_name,
                                    'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
                schema_item.appendRow(QStandardItem("Loading..."))
                type_item = QStandardItem("Schema")
                type_item.setEditable(False)
                self.schema_model.appendRow([schema_item, type_item])
            if hasattr(self, '_expanded_connection'):
                try:
                    self.schema_tree.expanded.disconnect(
                        self._expanded_connection)
                except TypeError:
                    pass
            self._expanded_connection = self.schema_tree.expanded.connect(
                self.load_tables_on_expand)
        except Exception as e:
            self.status.showMessage(f"Error loading schemas: {e}", 5000)
            if hasattr(self, 'pg_conn') and self.pg_conn:
                self.pg_conn.close()
        self.schema_tree.setColumnWidth(0, 200)
        self.schema_tree.setColumnWidth(1, 100)
        header = self.schema_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.schema_tree.setStyleSheet("""
    QHeaderView {
        background-color: #a9a9a9;
                                       
    }
    QHeaderView::section {
        border-right: 1px solid #d3d3d3;
        padding: 4px;
        background-color: #a9a9a9;   
    }
    QTreeView {
        gridline-color: #a9a9a9;
    }
""")
        
        

    def show_schema_context_menu(self, position):
        index = self.schema_tree.indexAt(position)
        if not index.isValid():
            return
        item = self.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        
        if not item_data:
            return

        db_type = item_data.get('db_type')
        table_name = item_data.get('table_name')
        schema_name = item_data.get('schema_name')
        
        is_table_or_view = table_name is not None
        is_schema = schema_name is not None and not is_table_or_view

        menu = QMenu()
        
        if is_table_or_view:
            # --- Table/View Actions ---
            display_name = item.text()
            view_menu = menu.addMenu("View/Edit Data")
            
            query_all_action = QAction("All Rows", self)
            query_all_action.triggered.connect(lambda: self.query_table_rows(
                item_data, display_name, limit=None, execute_now=True))
            view_menu.addAction(query_all_action)
            
            preview_100_action = QAction("First 100 Rows", self)
            preview_100_action.triggered.connect(lambda: self.query_table_rows(
                item_data, display_name, limit=100, execute_now=True))
            view_menu.addAction(preview_100_action)

            last_100_action = QAction("Last 100 Rows", self)
            last_100_action.triggered.connect(lambda: self.query_table_rows(
                item_data, display_name, limit=100, order='desc', execute_now=True))
            view_menu.addAction(last_100_action)

            count_rows_action = QAction("Count Rows", self)
            count_rows_action.triggered.connect(
                lambda: self.count_table_rows(item_data, display_name))
            view_menu.addAction(count_rows_action)
            
            menu.addSeparator()
            query_tool_action = QAction("Query Tool", self)
            query_tool_action.triggered.connect(
                lambda: self.open_query_tool_for_table(item_data, display_name))
            menu.addAction(query_tool_action)
            
            menu.addSeparator()
            export_rows_action = QAction("Export Rows", self)
            export_rows_action.triggered.connect(
                lambda: self.export_schema_table_rows(item_data, display_name))
            menu.addAction(export_rows_action)

            properties_action = QAction("Properties", self)
            properties_action.triggered.connect(
                lambda: self.show_table_properties(item_data, display_name))
            menu.addAction(properties_action)
            
            menu.addSeparator()
            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE script", self)
            create_script_action.triggered.connect(lambda: self.script_table_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)
            
            menu.addSeparator()

            # --- Create Table (Restricted to Table/View nodes as requested) ---
            if db_type in ['postgres', 'sqlite']:
                create_table_action = QAction("Create Table", self)
                create_table_action.triggered.connect(
                    lambda: self.open_create_table_template(item_data))
                menu.addAction(create_table_action)

            # --- Create View (Restricted to Table/View nodes as requested) ---
            if db_type in ['postgres', 'sqlite']:
                create_view_action = QAction("Create View", self)
                create_view_action.triggered.connect(
                    lambda: self.open_create_view_template(item_data))
                menu.addAction(create_view_action)

            menu.addSeparator()
            table_type = item_data.get('table_type', 'TABLE').upper()
            object_type = "View" if "VIEW" in table_type else "Table"
            delete_table_action = QAction(f"Delete {object_type}", self)
            delete_table_action.triggered.connect(
                lambda: self.delete_table(item_data, display_name))
            menu.addAction(delete_table_action)
            
        elif is_schema:
            # --- No creation actions here as requested ---
            pass

        if menu.isEmpty():
            return

        menu.exec(self.schema_tree.viewport().mapToGlobal(position))

    def script_table_as_create(self, item_data, table_name):
        if not item_data: return
        
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        sql_script = ""
        
       
        if db_type == 'sqlite':
            try:
                import sqlite3 as sqlite
                conn = sqlite.connect(conn_data.get('db_path'))
                cursor = conn.cursor()
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                row = cursor.fetchone()
                if row:
                    sql_script = row[0] + ";"
                conn.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not generate SQLite script: {e}")
                return


        elif db_type == 'postgres':
            schema_name = item_data.get('schema_name', 'public')
            try:
                # conn = psycopg2.connect(**db.get_psycopg2_params(conn_data))
                conn = psycopg2.connect(
                    host=conn_data.get("host"),
                    port=conn_data.get("port"),
                    database=conn_data.get("database"),
                    user=conn_data.get("user"),
                    password=conn_data.get("password")
                )
                cursor = conn.cursor()
                
               
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable, column_default 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema_name, table_name))
                cols = cursor.fetchall()
                
                col_defs = []
                for col_name, dtype, nullable, default in cols:
                    null_str = " NOT NULL" if nullable == "NO" else ""
                    def_str = f" DEFAULT {default}" if default else ""
                    col_defs.append(f'    "{col_name}" {dtype}{null_str}{def_str}')
                
                
                cursor.execute("""
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                      ON tc.constraint_name = kcu.constraint_name 
                      AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY' 
                      AND tc.table_schema = %s AND tc.table_name = %s;
                """, (schema_name, table_name))
                pk_cols = [r[0] for r in cursor.fetchall()]
                
                if pk_cols:
                    
                    pk_names = ", ".join([f'"{c}"' for c in pk_cols])
                    col_defs.append(f'    CONSTRAINT "{table_name}_pkey" PRIMARY KEY ({pk_names})')
                
                sql_script = f'-- Table: {schema_name}.{table_name}\n\n'
                sql_script += f'CREATE TABLE "{schema_name}"."{table_name}" (\n' + ",\n".join(col_defs) + "\n);"
                
             
                cursor.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s;", (schema_name, table_name))
                idxs = cursor.fetchall()
                if idxs:
                    sql_script += "\n\n" + "\n".join([r[0] + ";" for r in idxs])
                
                conn.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not generate Postgres script: {e}")
                return

        
        if sql_script:
            new_tab = self.add_tab() 
            
            
            db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")
            for i in range(db_combo_box.count()):
                data = db_combo_box.itemData(i)
                if data and data.get('id') == conn_data.get('id'):
                    db_combo_box.setCurrentIndex(i)
                    break
            
            
            query_editor = new_tab.findChild(CodeEditor, "query_editor")
            if query_editor:
                query_editor.setPlainText(sql_script)
                self.tab_widget.setCurrentWidget(new_tab)

    def delete_table(self, item_data, table_name):
        if not item_data: return
        
        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        schema_name = item_data.get('schema_name')
        table_type = item_data.get('table_type', 'TABLE').upper()
        # Use table_name from item_data if it exists (e.g. for CSV with extension)
        real_table_name = item_data.get('table_name', table_name)
        
        is_view = "VIEW" in table_type
        object_type = "View" if is_view else "Table"
        
        reply = QMessageBox.question(
            self, f'Confirm Delete {object_type}',
            f"Are you sure you want to delete {object_type.lower()} '{table_name}'? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return

        try:
            conn = None
            sql = ""
            if db_type == 'postgres':
                conn = psycopg2.connect(
                    host=conn_data.get("host"),
                    port=conn_data.get("port"),
                    database=conn_data.get("database"),
                    user=conn_data.get("user"),
                    password=conn_data.get("password")
                )
                full_name = f'"{schema_name}"."{real_table_name}"' if schema_name else f'"{real_table_name}"'
                drop_cmd = "DROP VIEW" if is_view else "DROP TABLE"
                sql = f"{drop_cmd} {full_name};"
            elif db_type == 'sqlite':
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
                drop_cmd = "DROP VIEW" if is_view else "DROP TABLE"
                sql = f'{drop_cmd} "{real_table_name}";'
            elif db_type == 'csv':
                folder_path = conn_data.get("db_path")
                file_path = os.path.join(folder_path, real_table_name)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    success_msg = f"CSV file '{table_name}' deleted successfully."
                    self.status.showMessage(success_msg, 5000)
                    QMessageBox.information(self, "Success", success_msg)
                    
                    # Also log to Messages tab if a query tab is open
                    current_tab = self.tab_widget.currentWidget()
                    if current_tab:
                        message_view = current_tab.findChild(QTextEdit, "message_view")
                        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                        if message_view and results_stack:
                            results_stack.setCurrentIndex(1) # Switch to Messages
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            message_view.append(f"[{timestamp}]  OS.REMOVE(\"{file_path}\")")
                            message_view.append(f"  {success_msg}")
                            
                            header = current_tab.findChild(QWidget, "resultsHeader")
                            if header:
                                buttons = header.findChildren(QPushButton)
                                if len(buttons) >= 2:
                                    buttons[0].setChecked(False)
                                    buttons[1].setChecked(True)

                    self.load_csv_schema(conn_data)
                    return
                else:
                    raise Exception(f"File not found: {file_path}")
            
            if conn and sql:
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
                conn.close()
                
                success_msg = f"{object_type} '{table_name}' deleted successfully."
                self.status.showMessage(success_msg, 5000)
                QMessageBox.information(self, "Success", success_msg)
                
                # Also log to Messages tab if a query tab is open
                current_tab = self.tab_widget.currentWidget()
                if current_tab:
                    message_view = current_tab.findChild(QTextEdit, "message_view")
                    results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
                    if message_view and results_stack:
                        results_stack.setCurrentIndex(1) # Switch to Messages
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message_view.append(f"[{timestamp}]  {sql}")
                        message_view.append(f"  {success_msg}")
                        
                        # Set button state in header
                        header = current_tab.findChild(QWidget, "resultsHeader")
                        if header:
                            buttons = header.findChildren(QPushButton)
                            if len(buttons) >= 2:
                                buttons[0].setChecked(False) # Results
                                buttons[1].setChecked(True)  # Messages

                # Refresh schema
                if db_type == 'postgres':
                    self.load_postgres_schema(conn_data)
                elif db_type == 'sqlite':
                    self.load_sqlite_schema(conn_data)
                elif db_type == 'servicenow':
                    self.load_servicenow_schema(conn_data)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete {object_type.lower()}:\n{e}")

    
    def open_create_table_template(self, item_data, table_name=None):
        if not item_data: return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        
        if not conn_data:
            QMessageBox.critical(self, "Error", "Connection data is missing!")
            return
        
        # --- Helper Function to Log Message to View ---
        def log_success_to_view(table_name):
            current_tab = self.tab_widget.currentWidget()
           
            if not current_tab:
                self.add_tab()
                current_tab = self.tab_widget.currentWidget()
            
            if current_tab:
                message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
            
            if message_view and results_stack:
                    results_stack.setCurrentIndex(1)
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message_view.append(f"[{timestamp}]  CREATE TABLE \"{table_name}\"")
                    message_view.append(f"  Table created successfully.")
                    
                    sb = message_view.verticalScrollBar()
                    sb.setValue(sb.maximum())

                    message_view.repaint() 
                    QApplication.processEvents() 
                
                    header = current_tab.findChild(QWidget, "resultsHeader")
                    if header:
                       buttons = header.findChildren(QPushButton)
                       if len(buttons) >= 2:
                          buttons[0].setChecked(False)
                          buttons[1].setChecked(True)
                
                    results_info_bar = current_tab.findChild(QWidget, "resultsInfoBar")
                    if results_info_bar:
                        results_info_bar.hide()
               
                        self.status_message_label.setText(f"Table '{table_name}' created successfully.")
                    else:
                       QMessageBox.information(self, "Success", f"Table '{table_name}' created successfully!")
        

        # --- POSTGRES LOGIC ---
        if db_type == 'postgres':
            valid_keys = ['host', 'port', 'database', 'user', 'password']
            pg_conn_info = {k: v for k, v in conn_data.items() if k in valid_keys}
            
            if 'database' in pg_conn_info:
                pg_conn_info['dbname'] = pg_conn_info.pop('database')

            try:
                conn = psycopg2.connect(**pg_conn_info)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'")
                schemas = [row[0] for row in cursor.fetchall()]
                cursor.execute("SELECT current_user")
                current_user = cursor.fetchone()[0]
                conn.close()

                # Pass db_type="postgres"
                dialog = CreateTableDialog(self, schemas, current_user, db_type="postgres")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_sql_data()
                    
                    cols_sql = []
                    pk_cols = []
                    for col in data['columns']:
                        col_def = f'"{col["name"]}" {col["type"]}'
                        cols_sql.append(col_def)
                        if col['pk']:
                            pk_cols.append(f'"{col["name"]}"')
                    
                    if pk_cols:
                        cols_sql.append(f'PRIMARY KEY ({", ".join(pk_cols)})')
                    
                    sql = f'CREATE TABLE "{data["schema"]}"."{data["name"]}" (\n    {", ".join(cols_sql)}\n);'
                    
                    conn = psycopg2.connect(**pg_conn_info)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()
                    
                    log_success_to_view(data["name"])
                    
                    # --- NEW: Refresh Schema Tree explicitly for Postgres ---
                    self.status.showMessage("Refreshing schema...", 2000)
                    self.load_postgres_schema(conn_data)
                    # --------------------------------------------------------

            except Exception as e:
                QMessageBox.critical(self, "Connection Error", f"Invalid Connection or SQL: {e}")
        
        # --- SQLITE LOGIC ---
        elif db_type == 'sqlite':
            try:
                dialog = CreateTableDialog(self, schemas=None, current_user="", db_type="sqlite")
                
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_sql_data()
                    
                    cols_sql = []
                    for col in data['columns']:
                        pk = "PRIMARY KEY" if col['pk'] else ""
                        cols_sql.append(f'"{col["name"]}" {col["type"]} {pk}')
                    
                    sql = f'CREATE TABLE "{data["name"]}" (\n    {", ".join(cols_sql)}\n);'

                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    if not conn:
                         raise Exception("Could not open SQLite database file.")
                         
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    log_success_to_view(data["name"])

                    # --- NEW: Refresh Schema Tree explicitly for SQLite ---
                    self.status.showMessage("Refreshing schema...", 2000)
                    self.load_sqlite_schema(conn_data)
                    # ----------------------------------------------------

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create SQLite table:\n{e}")

        else:
            QMessageBox.warning(self, "Not Supported", f"Interactive table creation is not supported for {db_type} yet.")

    def open_create_view_template(self, item_data):
        if not item_data: return

        db_type = item_data.get('db_type')
        conn_data = item_data.get('conn_data')
        
        if not conn_data:
            QMessageBox.critical(self, "Error", "Connection data is missing!")
            return

        def log_success_to_view(view_name, sql):
            current_tab = self.tab_widget.currentWidget()
            if not current_tab:
                self.add_tab()
                current_tab = self.tab_widget.currentWidget()
            
            if current_tab:
                message_view = current_tab.findChild(QTextEdit, "message_view")
                results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
            
                if message_view and results_stack:
                    results_stack.setCurrentIndex(1)
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message_view.append(f"[{timestamp}]  {sql}")
                    message_view.append(f"  View '{view_name}' created successfully.")
                    
                    sb = message_view.verticalScrollBar()
                    sb.setValue(sb.maximum())
                    
                    header = current_tab.findChild(QWidget, "resultsHeader")
                    if header:
                       buttons = header.findChildren(QPushButton)
                       if len(buttons) >= 2:
                          buttons[0].setChecked(False)
                          buttons[1].setChecked(True)
                
                self.status_message_label.setText(f"View '{view_name}' created successfully.")

        # POSTGRES
        if db_type == 'postgres':
            valid_keys = ['host', 'port', 'database', 'user', 'password']
            pg_conn_info = {k: v for k, v in conn_data.items() if k in valid_keys}
            if 'database' in pg_conn_info:
                pg_conn_info['dbname'] = pg_conn_info.pop('database')

            try:
                conn = psycopg2.connect(**pg_conn_info)
                cursor = conn.cursor()
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'")
                schemas = [row[0] for row in cursor.fetchall()]
                conn.close()

                dialog = CreateViewDialog(self, schemas, db_type="postgres")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE VIEW "{data["schema"]}"."{data["name"]}" AS\n{data["sql"]};'
                    
                    conn = psycopg2.connect(**pg_conn_info)
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()
                    
                    log_success_to_view(data["name"], sql)
                    self.load_postgres_schema(conn_data)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create Postgres view:\n{e}")

        # SQLITE
        elif db_type == 'sqlite':
            try:
                dialog = CreateViewDialog(self, schemas=None, db_type="sqlite")
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_data()
                    sql = f'CREATE VIEW "{data["name"]}" AS\n{data["sql"]};'

                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    conn.commit()
                    conn.close()

                    log_success_to_view(data["name"], sql)
                    self.load_sqlite_schema(conn_data)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create SQLite view:\n{e}")

        else:
            QMessageBox.warning(self, "Not Supported", f"Interactive view creation is not supported for {db_type} yet.")

    def export_schema_table_rows(self, item_data, table_name):
        if not item_data:
            return

        dialog = ExportDialog(
            self, f"{table_name}_{datetime.datetime.now().strftime('%Y%m%d')}.csv")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        export_options = dialog.get_options()
        if not export_options['filename']:
            QMessageBox.warning(self, "No Filename",
                                "Export cancelled. No filename specified.")
            return

        conn_data = item_data['conn_data']
        
         # 🔹 THIS LINE FIXES THE ERROR
        conn_data['code'] = (conn_data.get('code') or item_data.get('db_type') or '').upper()

        # Construct query
        code = conn_data.get('code')
        
        if code == 'POSTGRES':
            schema_name = item_data.get("schema_name")
            query = f'SELECT * FROM "{schema_name}"."{table_name}"'
            object_name = f"{schema_name}.{table_name}"
        else: # SQLite
            query = f'SELECT * FROM "{table_name}"'
            object_name = table_name

        
        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]


        def on_data_fetched_for_export(
            _conn_data, _query, results, columns, row_count, _elapsed_time, _is_select_query
        ):
           
            self.status_message_label.setText("Data fetched. Starting export process...")
            model = QStandardItemModel()
            model.setColumnCount(len(columns))
            model.setRowCount(len(results))
            model.setHorizontalHeaderLabels(columns)

            for row_idx, row in enumerate(results):
                for col_idx, cell in enumerate(row):
                    model.setItem(row_idx, col_idx, QStandardItem(str(cell)))

            
            if export_options["delimiter"] == ',':
                export_options["delimiter"] = None

            conn_name = conn_data.get("short_name", conn_data.get("name", "Unknown"))
            conn_id = conn_data.get("id")

            initial_data = {
               "pid": short_id,
               "type": "Export Data",
               "status": "Running",
               "server": conn_name,
               "object": object_name, 
               "time_taken": "...",
               "start_time": datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
               "details": f"Exporting {row_count} rows to {os.path.basename(export_options['filename'])}",
               "_conn_id": conn_id
            }

            signals = ProcessSignals()
            signals.started.connect(self.handle_process_started)
            signals.finished.connect(self.handle_process_finished)
            signals.error.connect(self.handle_process_error)
            
            
            self.thread_pool.start(
              RunnableExportFromModel(short_id, model, export_options, signals)
            )
            
            signals.started.emit(short_id, initial_data)

        
        self.status_message_label.setText(f"Fetching data from {table_name} for export...")
        
        query_signals = QuerySignals()
        query_runnable = RunnableQuery(conn_data, query, query_signals)
        
        
        query_signals.finished.connect(on_data_fetched_for_export)
        
        query_signals.error.connect(
             lambda conn, q, rc, et, err: self.show_error_popup(
                 f"Failed to fetch data for export:\n{err}"
             )
        )
        
        self.thread_pool.start(query_runnable)
        
        
    def show_results_context_menu(self, position):
        results_table = self.sender()
        if not results_table or not results_table.model():
          return

        menu = QMenu()
        export_action = QAction("Export Rows", self)
        export_action.triggered.connect(lambda: self.export_result_rows(results_table))
        menu.addAction(export_action)

        menu.exec(results_table.viewport().mapToGlobal(position))

      
    def export_result_rows(self, table_view):
        model = table_view.model()
        if not model:
          QMessageBox.warning(self, "No Data", "No results available to export.")
          return

        dialog = ExportDialog(self, "query_results.csv")
        if dialog.exec() != QDialog.DialogCode.Accepted:
          return

        options = dialog.get_options()
        
        if not options['filename']:
          QMessageBox.warning(self, "No Filename", "Export cancelled. No filename specified.")
          return
        # 🧪 Force an invalid export option to simulate an error
        # options["delimiter"] = None   # invalid delimiter will break df.to_csv()

        # if options["delimiter"] == ',':
        #     options["delimiter"] = None

        # --- Find connection name dynamically ---
        current_tab = self.tab_widget.currentWidget()
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_name = "Unknown"
        conn_id = None # --- MODIFICATION: (Previous change)
        
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
              conn_data = db_combo_box.itemData(index)
              conn_name = conn_data.get("short_name", "Unknown")
              conn_id = conn_data.get("id") # --- MODIFICATION: (Previous change)

        # --- Create Process info ---
        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]
        initial_data = {
           "pid": short_id,
           "type": "Export Data",
           "status": "Running",
           "server": conn_name,
           "object": "Query Results",
           "time_taken": "...",
           "start_time": datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
           "details": f"Exporting to {os.path.basename(options['filename'])}",
           # --- START MODIFICATION (Previous change) ---
           "_conn_id": conn_id
           # --- END MODIFICATION ---
        }

        signals = ProcessSignals()
        signals.started.connect(self.handle_process_started)
        signals.finished.connect(self.handle_process_finished)
        signals.error.connect(self.handle_process_error)
        signals.started.emit(short_id, initial_data)

        self.thread_pool.start(
          RunnableExportFromModel(short_id, model, options, signals)
        )
     
    def _initialize_processes_model(self, tab_content):
        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
          return

        tab_content.processes_model = QStandardItemModel()
        tab_content.processes_model.setHorizontalHeaderLabels(
           ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
       )
        processes_view.setModel(tab_content.processes_model)
        # processes_view.resizeColumnsToContents()

            
    def switch_to_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        header = current_tab.findChild(QWidget, "resultsHeader")
        buttons = header.findChildren(QPushButton)

        if results_stack and len(buttons) >= 4:
          results_stack.setCurrentIndex(3)
          for i, btn in enumerate(buttons[:4]):
            btn.setChecked(i == 3)
    
    
    def get_current_tab_processes_model(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return None, None
        processes_view = current_tab.findChild(QTableView, "processes_view")
        model = getattr(current_tab, "processes_model", None)
        return model, processes_view
    
    def handle_process_started(self, process_id, data):
        # --- START MODIFICATION (Previous change) ---
        target_conn_id = data.get("_conn_id")
        if target_conn_id:
            current_tab = self.tab_widget.currentWidget()
            if current_tab:
                db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo_box:
                    for i in range(db_combo_box.count()):
                        item_data = db_combo_box.itemData(i)
                        if item_data and item_data.get('id') == target_conn_id:
                            # --- Check if index is already selected ---
                            if db_combo_box.currentIndex() != i:
                                db_combo_box.setCurrentIndex(i)
                            else:
                                # If already selected, manually trigger refresh
                                # because currentIndexChanged won't fire
                                self.refresh_processes_view()
                            break
        # --- END MODIFICATION ---

        self.switch_to_processes_view()

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        if target_conn_id:
           cursor.execute("""
            DELETE FROM usf_processes
            WHERE status = 'Running'
              AND server = (
                  SELECT short_name FROM usf_connections WHERE id = ?
               )
          """, (target_conn_id,))

        cursor.execute("""
          INSERT OR REPLACE INTO usf_processes
          (pid, type, status, server, object, time_taken, start_time, end_time, details)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      """, (
          data.get("pid", ""),
          data.get("type", ""),
          "Running",
          data.get("server", ""),
          data.get("object", ""),
          0.0,
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          "",
          data.get("details", "")
      ))
        conn.commit()
        conn.close()

        # refresh_processes_view is now called by the combobox signal
        # OR manually if the combobox was already on the right connection
        if not target_conn_id:
             self.refresh_processes_view()
    # change
    def handle_process_finished(self, process_id, message, time_taken, row_count):
        status = "Successfull" if row_count == 0 else "Successfull"
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        # if "0 rows" in message.lower() or "no data" in message.lower() or "empty" in message.lower():
        #     status = "Warning"
        # else:
        #     status = "Successfull"
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, time_taken = ?, end_time = ?, details = ?
          WHERE pid = ?
     """, (
           status,
          time_taken,
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #   datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()

    def handle_process_error(self, process_id, error_message):
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, end_time = ?, details = ?
          WHERE pid = ?
      """, (
          "Error",
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          error_message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()
    
    
    def refresh_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        selected_server = None
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
            data = db_combo_box.itemData(index)
            # --- Use short_name for filtering ---
            selected_server = data.get("short_name") if data else None

        processes_view = current_tab.findChild(QTableView, "processes_view")
        model = getattr(current_tab, "processes_model", None)
        if not processes_view or not model:
          return

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()

        if selected_server:
          # --- Filter by the selected server (short_name) ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            WHERE server = ?
            ORDER BY start_time DESC
        """, (selected_server,))
        else:
          # --- If no server selected, show all ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            ORDER BY start_time DESC
          """)

        data = cursor.fetchall()
        conn.close()

        model.clear()
        model.setHorizontalHeaderLabels(
          ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
        )

        latest_row_index = 0 

        for row_index, row in enumerate(data):
            items = [QStandardItem(str(col)) for col in row]

            status_text = row[2]  # 3rd column: Status
            brush = None
            if status_text == "Error":
               brush = QBrush(QColor("#BD3020"))      # 🔴 
            elif status_text == "Successfull":
                brush = QBrush(QColor("#28a745"))  # 🟢 Successful
            elif status_text == "Running":
                brush = QBrush(QColor("#ffc107"))      # 🟡 Running
            elif status_text == "Warning":
                brush = QBrush(QColor("#fd7e14"))      # 🟠 Warning
            # elif row_index == latest_row_index:
            #     brush = QBrush(QColor("#d1ecf1"))      # 🔵  (latest row highlight)
            else:
                brush = QBrush(QColor("#ffffff"))      # ⚪  (default white)

        #  Apply background color to all cells of this row
            for item in items:
              item.setBackground(brush)
        # for row in data:
        #   items = [QStandardItem(str(col)) for col in row]
          
        #   # --- MODIFICATION: Color coding rows based on status ---
        #   status_text = row[2] # Status is the 3rd column
        #   if status_text == "Error":
        #       for item in items:
        #           item.setBackground(QBrush(QColor("#d4edda")))
        #   elif status_text == "Error":
        #       for item in items:
        #           item.setBackground(QBrush(QColor("#f8d7da")))
          # --- END MODIFICATION ---

            model.appendRow(items)
        
        # --- MODIFICATION: resizeColumnsToContents moved here ---
        processes_view.resizeColumnsToContents()
        processes_view.horizontalHeader().setStretchLastSection(True)


    def count_table_rows(self, item_data, table_name):
        if not item_data:
            return
        
        conn_data = dict(item_data.get('conn_data', {}))
        db_type = item_data.get('db_type')
        
       
        conn_data['code'] = (conn_data.get('code') or db_type or '').upper()

        if db_type == 'postgres':
             query = f'SELECT COUNT(*) FROM "{item_data.get("schema_name")}"."{table_name}";'
        elif db_type == 'csv':
             
             query = f'SELECT COUNT(*) FROM [{table_name}]'
        else: # SQLite
             query = f'SELECT COUNT(*) FROM "{table_name}";'

        self.status_message_label.setText(f"Counting rows for {table_name}...")
        
        signals = QuerySignals()
        runnable = RunnableQuery(conn_data, query, signals)
        
        signals.finished.connect(self.handle_count_result)
        signals.error.connect(self.handle_count_error)
        self.thread_pool.start(runnable)

    def handle_count_result(self, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
        try:
            if results and len(results[0]) > 0:
                self.notification_manager.show_message(
                    f"Table rows counted: {results[0][0]}")
                self.status_message_label.setText(
                    f"Successfully counted rows in {elapsed_time:.2f} sec.")
            else:
                self.handle_count_error("Could not retrieve count.")
        except Exception as e:
            self.handle_count_error(str(e))

    def handle_count_error(self, error_message):
        self.notification_manager.show_message(
            f"Error: {error_message}", is_error=True)
        self.status_message_label.setText("Failed to count rows.")


    def open_query_tool_for_table(self, item_data, table_name):
      if not item_data:
        return

      conn_data = item_data.get("conn_data")
      new_tab = self.add_tab()

      # Find the editor and connection dropdown
      query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
      db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

      # Select the correct connection in combo box
      for i in range(db_combo_box.count()):
        data = db_combo_box.itemData(i)
        if data and data.get('id') == conn_data.get('id'):
            db_combo_box.setCurrentIndex(i)
            break

      # Keep the editor empty for a fresh Query Tool
      query_editor.clear()

      # Set focus so the user can start typing immediately
      query_editor.setFocus()

      # Make sure the new tab becomes the active one
      self.tab_widget.setCurrentWidget(new_tab)
    
    
    def query_table_rows(self, item_data, table_name, limit=None, execute_now=True, order=None):
        if not item_data:
           return

        new_tab = self.add_tab()
        new_tab.table_name = table_name
        
        query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        # Set the combo box to the right connection
        conn_data = item_data.get('conn_data', {})
        for i in range(db_combo_box.count()):
            data = db_combo_box.itemData(i)
            if data and data.get('id') == conn_data.get('id'):
                db_combo_box.setCurrentIndex(i)
                break

        # Copy and ensure proper keys
        conn_data = dict(conn_data)
        if item_data.get('db_type') == 'csv':
            conn_data['table_name'] = item_data.get('table_name')

        # 🔹 THIS LINE FIXES THE ERROR
        conn_data['code'] = (conn_data.get('code') or item_data.get('db_type') or '').upper()

        # Construct query
        code = conn_data.get('code')
        if code == 'POSTGRES':
           
            schema = item_data.get("schema_name", "public")
            new_tab.table_name = f'"{schema}"."{table_name}"' 
            query = f'SELECT * FROM "{schema}"."{table_name}";'
        elif code == 'SQLITE':
            new_tab.table_name = f'"{table_name}"'
            query = f'SELECT * FROM "{table_name}";'
        elif code == 'CSV':
            new_tab.table_name = f'[{table_name}]'
            query = f'SELECT * FROM "{table_name}";'

        elif code == 'SERVICENOW': 
            new_tab.table_name = table_name
            query = f'SELECT * FROM {table_name}'
        else:
            self.show_info(f"Unsupported db_type: {code}")
            return
        # if code == 'POSTGRES':
        #     query = f'SELECT * FROM "{item_data.get("schema_name")}"."{table_name}";'
        # elif code == 'SQLITE':
        #     query = f'SELECT * FROM "{table_name}";'
        # elif code == 'CSV':
        #     # query = f'SELECT * FROM [{item_data.get("table_name")}]'
        #     query = f'SELECT * FROM "{table_name}";'
        # else:
        #     self.show_info(f"Unsupported db_type: {code}")
        #     return
        
        if order or limit:
            query = query.rstrip(';')  

            if order:
                query += f" ORDER BY 1 {order.upper()}"
            if limit:
                query += f" LIMIT {limit}"
            
            query += ";"  

        # if order:
        #     query += f" ORDER BY 1 {order.upper()}"
        # if limit:
        #     query += f" LIMIT {limit}"

        query_editor.setPlainText(query)

        if execute_now:
            self.tab_widget.setCurrentWidget(new_tab)
            self.execute_query(conn_data, query)
 

    def load_tables_on_expand(self, index: QModelIndex):
        item = self.schema_model.itemFromIndex(index)
        
        if not item or (item.rowCount() > 0 and item.child(0).text() != "Loading..."):
            return

        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        db_type = item_data.get('db_type')

        if db_type == 'postgres':
            # --- Check if we are expanding a Schema OR a Table ---
            schema_name = item_data.get('schema_name')
            table_name = item_data.get('table_name')

            if table_name and schema_name:
                # --- CASE 1: Expanding a POSTGRES TABLE ---
                # This item is a table, load its details
                self.load_postgres_table_details(item, item_data)
            elif schema_name:
                # --- CASE 2: Expanding a POSTGRES SCHEMA ---
                # This is the original logic for expanding a schema to show tables
                item.removeRows(0, item.rowCount()) # "Loading..." 
                try:
                    cursor = self.pg_conn.cursor()
                    cursor.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = %s ORDER BY table_type, table_name;", (schema_name,))
                    tables = cursor.fetchall()
                    for (table_name, table_type) in tables:
                        icon_path = "assets/table_icon.png" if "TABLE" in table_type else "assets/view_icon.png"
                        table_item = QStandardItem(QIcon(icon_path), table_name)
                        table_item.setEditable(False)
                        
                        table_data = item_data.copy() 
                        table_data['table_name'] = table_name
                        table_data['table_type'] = table_type
                        table_item.setData(table_data, Qt.ItemDataRole.UserRole)
                        
                        # Add placeholder to tables/views to make them expandable
                        if "TABLE" in table_type or "VIEW" in table_type:
                           table_item.appendRow(QStandardItem("Loading..."))

                        if "TABLE" in table_type:
                            self._set_tree_item_icon(table_item, level="TABLE")
                            type_text = "Table"
                        elif "VIEW" in table_type:
                            self._set_tree_item_icon(table_item, level="VIEW")
                            type_text = "View"
                        else:
                        
                            type_text = table_type.title() 
                        
                        type_item = QStandardItem(type_text)
                        type_item.setEditable(False)

                        item.appendRow([table_item, type_item])
                       
                except Exception as e:
                    self.status.showMessage(f"Error expanding schema: {e}", 5000)
                    item.appendRow(QStandardItem(f"Error: {e}"))
            # --------------------------------------------------------
        elif db_type == 'sqlite':
            # --- CASE 3: Expanding an SQLITE TABLE ---
            self.load_sqlite_table_details(item, item_data)
            
        elif db_type == 'csv':
            self.load_cdata_table_details(item, item_data)
        elif db_type == 'servicenow':
            self.load_servicenow_table_details(item, item_data)
  
  
    def load_servicenow_table_details(self, table_item, item_data):
        """
        Loads columns for a ServiceNow table.
        """
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return

        table_item.removeRows(0, table_item.rowCount()) # Clear "Loading..."

        table_name = item_data.get('table_name')
        conn_data = item_data.get('conn_data')
        
        if not table_name or not conn_data:
            return

        conn = None
        try:
           
            conn = db.create_servicenow_connection(conn_data)
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
            except:
                # Fallback for some drivers
                cursor.execute(f"SELECT * FROM {table_name} WHERE 1=0")
                
            columns_info = cursor.description
            
            column_items = []
            if columns_info:
                for col in columns_info:
                    col_name = col[0]
                    
                    col_type = str(col[1]) if len(col) > 1 else "Unknown"
                    
                    desc = f"{col_name}"
                    col_item = QStandardItem(desc)
                    col_item.setEditable(False)
                    # col_item.setIcon(QIcon("assets/column_icon.png"))
                    column_items.append(col_item)

            columns_folder = QStandardItem(f"Columns ({len(column_items)})")
            columns_folder.setEditable(False)
            
            if not column_items:
                 columns_folder.appendRow(QStandardItem("No columns found"))
            else:
                for item in column_items:
                    columns_folder.appendRow(item)
            
            
            table_item.appendRow(columns_folder)

            conn.close()

        except Exception as e:
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.status.showMessage(f"Error loading ServiceNow details: {e}", 5000)



    def load_sqlite_table_details(self, table_item, item_data):
        """
        Loads columns, constraints (PK, FK, UNIQUE), and indexes for an SQLite table
        in the correct order (Columns, Constraints, Indexes).
        MODIFIED: Now shows counts in folder names.
        """
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return # Already loaded or not expandable

        table_item.removeRows(0, table_item.rowCount()) # Clear "Loading..."

        table_name = item_data.get('table_name')
        conn_data = item_data.get('conn_data')
        if not table_name or not conn_data:
            return

        conn = None
        try:
            conn = db.create_sqlite_connection(conn_data["db_path"])
            cursor = conn.cursor()

            # --- Lists to hold items before creating folders ---
            column_items = []
            constraint_items = []
            index_items = []
            pk_cols = []

            # --- 1. Get Column Info (and find PKs) ---
            # PRAGMA table_info format: (cid, name, type, notnull, dflt_value, pk)
            cursor.execute(f'PRAGMA table_info("{table_name}");')
            columns = cursor.fetchall()

            if columns:
                for col in columns:
                    cid, name, type, notnull, dflt_value, pk = col
                    
                    # Build column description
                    desc = f"{name} ({type})"
                    if notnull:
                        desc += " [NOT NULL]"
                    col_item = QStandardItem(desc)
                    col_item.setEditable(False)
                    self._set_tree_item_icon(columns_folder, level="FOLDER")
                    column_items.append(col_item)
                    
                    # Collect PK columns for the constraints folder
                    if pk > 0:
                        pk_cols.append(name)
            
            # Add PK to constraints list
            if pk_cols:
                pk_desc = f"[PK] ({', '.join(pk_cols)})"
                pk_item = QStandardItem(pk_desc)
                pk_item.setEditable(False)
                constraint_items.append(pk_item)

            # --- 2. Get Index and Unique Constraint Info ---
            # PRAGMA index_list format: (seq, name, unique, origin, partial)
            cursor.execute(f'PRAGMA index_list("{table_name}");')
            indexes = cursor.fetchall()
            
            if indexes:
                for idx in indexes:
                    seq, name, unique, origin, partial = idx
                    
                    if name.startswith("sqlite_autoindex_"):
                        continue

                    # Get columns for this index
                    cursor.execute(f'PRAGMA index_info("{name}");')
                    idx_cols = cursor.fetchall()
                    col_names = ", ".join([c[2] for c in idx_cols])
                    
                    desc = f"{name} ({col_names})"

                    if origin == 'c': # 'c' = UNIQUE constraint
                        desc += " [UNIQUE]"
                        u_item = QStandardItem(desc)
                        u_item.setEditable(False)
                        constraint_items.append(u_item)
                    elif origin == 'i': # 'i' = user-defined INDEX
                        if unique:
                            desc += " [UNIQUE]"
                        idx_item = QStandardItem(desc)
                        idx_item.setEditable(False)
                        index_items.append(idx_item)
                    # We skip 'pk' origin because we already handled it

            # --- 3. Get Foreign Key Constraints ---
            # PRAGMA foreign_key_list format:
            # (id, seq, table, from, to, on_update, on_delete, match)
            cursor.execute(f'PRAGMA foreign_key_list("{table_name}");')
            fks = cursor.fetchall()

            if fks:
                fk_groups = {}
                for id, seq, table, from_col, to_col, on_update, on_delete, match in fks:
                    if id not in fk_groups:
                        fk_groups[id] = {
                            'from_cols': [],
                            'to_cols': [],
                            'table': table,
                            'rules': f"ON UPDATE {on_update} ON DELETE {on_delete}"
                        }
                    fk_groups[id]['from_cols'].append(from_col)
                    fk_groups[id]['to_cols'].append(to_col)

                for id, data in fk_groups.items():
                    from_str = ", ".join(data['from_cols'])
                    to_str = ", ".join(data['to_cols'])
                    desc = f"[FK] ({from_str}) -> {data['table']}({to_str})"
                    desc += f" [{data['rules']}]"
                    fk_item = QStandardItem(desc)
                    fk_item.setEditable(False)
                    constraint_items.append(fk_item)

            # --- 4. Create Folders with Counts and Populate ---
            
            # Columns Folder
            columns_folder = QStandardItem(f"Columns ({len(column_items)})")
            columns_folder.setEditable(False)
            if not column_items:
                 columns_folder.appendRow(QStandardItem("No columns found"))
            else:
                for item in column_items:
                    columns_folder.appendRow(item)
            
            # Constraints Folder
            constraints_folder = QStandardItem(f"Constraints ({len(constraint_items)})")
            constraints_folder.setEditable(False)
            if not constraint_items:
                constraints_folder.appendRow(QStandardItem("No constraints found"))
            else:
                for item in constraint_items:
                    constraints_folder.appendRow(item)

            # Indexes Folder
            indexes_folder = QStandardItem(f"Indexes ({len(index_items)})")
            indexes_folder.setEditable(False)
            if not index_items:
                indexes_folder.appendRow(QStandardItem("No indexes"))
            else:
                for item in index_items:
                    indexes_folder.appendRow(item)

            # --- 5. Append all folders in the correct order ---
            table_item.appendRow(columns_folder)
            table_item.appendRow(constraints_folder)
            table_item.appendRow(indexes_folder)

        except Exception as e:
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.status.showMessage(f"Error loading table details: {e}", 5000)
        finally:
            if conn:
                conn.close()


    def load_postgres_table_details(self, table_item, item_data):
        """
        Loads columns, indexes, and constraints for a Postgres table.
        MODIFIED: Shows counts in folder names and full default value.
        """
        if not item_data or table_item.rowCount() == 0 or table_item.child(0).text() != "Loading...":
            return # Already loaded

        table_item.removeRows(0, table_item.rowCount()) # Clear "Loading..."

        schema_name = item_data.get('schema_name')
        table_name = item_data.get('table_name')
        if not table_name or not schema_name or not hasattr(self, 'pg_conn') or self.pg_conn.closed:
             if not hasattr(self, 'pg_conn') or self.pg_conn.closed:
                 self.status.showMessage("Connection lost. Please reload schema.", 5000)
             table_item.appendRow(QStandardItem("Error: Connection unavailable"))
             return

        try:
            cursor = self.pg_conn.cursor()

            # --- 1. Add Columns Folder ---
            
            # Query for columns, data type, nullability, defaults, and PK status
            col_query = """
            SELECT 
                c.column_name, 
                c.data_type, 
                c.character_maximum_length,
                c.is_nullable, 
                c.column_default,
                CASE 
                    WHEN kcu.column_name IS NOT NULL AND tc.constraint_type = 'PRIMARY KEY' THEN 'YES'
                    ELSE 'NO' 
                END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN information_schema.key_column_usage kcu
              ON c.table_schema = kcu.table_schema 
              AND c.table_name = kcu.table_name 
              AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc
              ON kcu.constraint_name = tc.constraint_name
              AND kcu.table_schema = tc.table_schema
              AND kcu.table_name = tc.table_name
              AND tc.constraint_type = 'PRIMARY KEY'
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position;
            """
            cursor.execute(col_query, (schema_name, table_name))
            columns = cursor.fetchall()
            
            # --- Create folder AFTER fetching so we have the count ---
            columns_folder = QStandardItem(f"Columns ({len(columns)})")
            columns_folder.setEditable(False)
            
            for col in columns:
                name, dtype, char_max, is_nullable, default, is_pk = col
                desc = f"{name} ({dtype}"
                if char_max:
                    desc += f"[{char_max}]"
                desc += ")"
                if is_pk == 'YES':
                    desc += " [PK]"
                if is_nullable == 'NO':
                    desc += " [NOT NULL]"
                
                if default:
                    desc += f" [default: {str(default)}]"
                
                col_item = QStandardItem(desc)
                col_item.setEditable(False)
                self._set_tree_item_icon(col_item, level="COLUMN")
                columns_folder.appendRow(col_item)
            table_item.appendRow(columns_folder)

            # --- 2. Add Constraints Folder ---
            
            con_query = """
            SELECT 
                tc.constraint_name, 
                tc.constraint_type,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = %s AND tc.table_name = %s
            ORDER BY tc.constraint_type, tc.constraint_name;
            """
            cursor.execute(con_query, (schema_name, table_name))
            constraints = cursor.fetchall()
            
            # Group columns by constraint name
            con_map = {}
            for name, type, col in constraints:
                if name not in con_map:
                    con_map[name] = {'type': type, 'cols': []}
                con_map[name]['cols'].append(col)
            
            # --- Create folder AFTER processing so we have the count ---
            constraints_folder = QStandardItem(f"Constraints ({len(con_map)})")
            constraints_folder.setEditable(False)

            if not con_map:
                constraints_folder.appendRow(QStandardItem("No constraints"))
            else:
                for name, data in con_map.items():
                    cols_str = ", ".join(data['cols'])
                    desc = f"{name} [{data['type']}] ({cols_str})"
                    con_item = QStandardItem(desc)
                    con_item.setEditable(False)
                    constraints_folder.appendRow(con_item)
            table_item.appendRow(constraints_folder)

            # --- 3. Add Indexes Folder ---
            
            # Query pg_indexes (simpler than info_schema for this)
            idx_query = "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s;"
            cursor.execute(idx_query, (schema_name, table_name))
            indexes = cursor.fetchall()

            # --- Filter user-defined indexes BEFORE creating folder ---
            user_indexes = []
            for name, definition in indexes:
                 # Don't show the constraint-based indexes, they are in the other folder
                if name in con_map:
                    continue
                user_indexes.append((name, definition))

            # --- Create folder with the count of *user-defined* indexes ---
            indexes_folder = QStandardItem(f"Indexes ({len(user_indexes)})")
            indexes_folder.setEditable(False)

            if not user_indexes:
                indexes_folder.appendRow(QStandardItem("No indexes"))
            else:
                # Loop through the *filtered* list
                for name, definition in user_indexes:
                     # Clean up definition
                    match = re.search(r'USING \w+ \((.*)\)', definition)
                    cols_str = match.group(1) if match else "..."
                    
                    desc = f"{name} ({cols_str})"
                    idx_item = QStandardItem(desc)
                    idx_item.setEditable(False)
                    indexes_folder.appendRow(idx_item)
            
            table_item.appendRow(indexes_folder)

        except Exception as e:
            if hasattr(self, 'pg_conn') and self.pg_conn:
                self.pg_conn.rollback() # Rollback any failed transaction
            table_item.appendRow(QStandardItem(f"Error: {e}"))
            self.status.showMessage(f"Error loading table details: {e}", 5000)
    

    def load_cdata_table_details(self, item, item_data):
      
        if item.rowCount() > 0 and item.child(0).text() != "Loading...":
           return

  
        if item.rowCount() == 1 and item.child(0).text() == "Loading...":
           item.removeRow(0)

        conn_data = item_data.get('conn_data')
        table_name = item_data.get('table_name')

        if not conn_data or not table_name:
           self.status.showMessage("Connection or table data is missing for CData.", 5000)
           return

  
        try:
      
         column_item = QStandardItem("column_name TEXT")
         column_item.setIcon(QIcon("assets/column_icon.png"))
         column_item.setEditable(False)
         item.appendRow(column_item)
        
         self.status.showMessage(f"Attempted to load details for CData table: {table_name}", 3000)

        except Exception as e:
            self.status.showMessage(f"Error loading CData table details: {e}", 5000)
        
        


    def load_csv_schema(self, conn_data):
        folder_path = conn_data.get("db_path")
        if not folder_path or not os.path.exists(folder_path):
            self.status.showMessage(f"CSV folder not found: {folder_path}", 5000)
            return

        try:
            self.schema_model.clear()
            #self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            self.schema_tree.setColumnWidth(0, 200)
            self.schema_tree.setColumnWidth(1, 100)
        
            header = self.schema_tree.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
            self.schema_tree.setStyleSheet("""
            QHeaderView {
               background-color: #a9a9a9;
                                       
            }
            QHeaderView::section {
               border-right: 1px solid #d3d3d3;
               padding: 4px;
               background-color: #a9a9a9;   
            }
            QTreeView {
               gridline-color: #a9a9a9;
            }
            """)
            # List all CSV files in the folder
            csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.csv')]

            for file_name in csv_files:
                # Remove .csv extension
                display_name, _ = os.path.splitext(file_name)
                table_item = QStandardItem(QIcon("assets/table.svg"), display_name)
                table_item.setEditable(False)
                table_item.setData({
                    'db_type': 'csv',
                    'table_name': file_name,
                    'conn_data': conn_data
                }, Qt.ItemDataRole.UserRole)
                # Add a placeholder for expansion
                table_item.appendRow(QStandardItem("Loading..."))

                type_item = QStandardItem("Table")
                type_item.setEditable(False)

                self.schema_model.appendRow([table_item, type_item])

        except Exception as e:
            self.status.showMessage(f"Error loading CSV folder: {e}", 5000)


    def load_servicenow_schema(self, conn_data):
        try:
            conn = db.create_servicenow_connection(conn_data)
            if not conn:
                self.status.showMessage("Unable to connect to ServiceNow", 5000)
                return

            cursor = conn.cursor()
        
            # --- Fetch tables ---
            # sys_tables may be restricted, so using a known list as fallback
            try:
                cursor.execute("SELECT TableName FROM sys_tables")
                tables = [row[0] for row in cursor.fetchall()]
            except Exception:
                # fallback to common ServiceNow tables
                tables = ['incident', 'task', 'change_request', 'problem', 'change_request']

            if not tables:
                self.status.showMessage("No tables found or access restricted.", 5000)
                return

            self.schema_model.clear()
            self.schema_model.setHorizontalHeaderLabels(["Name", "Type"])
            for table_name in tables:
                table_item = QStandardItem(QIcon("assets/table.svg"), table_name)
                table_item.setEditable(False)
                table_item.setData({
                    'db_type': 'servicenow',
                    'table_name': table_name,
                    'conn_data': conn_data
                }, Qt.ItemDataRole.UserRole)
                table_item.appendRow(QStandardItem("Loading..."))  # expandable placeholder

                type_item = QStandardItem("Table")
                type_item.setEditable(False)
                self.schema_model.appendRow([table_item, type_item])

            conn.close()
        except Exception as e:
            self.status.showMessage(f"Error loading ServiceNow schema: {e}", 5000)
# {siam}
    def closeEvent(self, event):
        """Save session state on close."""
        session_data = {
            "window_geometry": self.saveGeometry().toBase64().data().decode(),
            "window_state": self.saveState().toBase64().data().decode(),
            "tabs": []
        }

        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            editor = tab.findChild(CodeEditor, "query_editor")
            db_combo = tab.findChild(QComboBox, "db_combo_box")
            
            # Find file path (if any was opened/saved) - This is tricky as we don't currently store it on the tab strictly
            # But let's check for 'current_file' attribute if we were to add it, or just content.
            # For now, saving distinct content is the priority. 
            
            tab_data = {
                "title": self.tab_widget.tabText(i),
                "sql_content": editor.toPlainText() if editor else "",
                "selected_connection_index": db_combo.currentIndex() if db_combo else 0,
                 # We might want to store more property if needed
                "current_limit": getattr(tab, 'current_limit', 1000),
                "current_offset": getattr(tab, 'current_offset', 0)
            }
            session_data["tabs"].append(tab_data)

        try:
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=4)
        except Exception as e:
            print(f"Error saving session: {e}")

        event.accept()

    def restore_session_state(self):
        """Restore tabs and connections from saved session."""
        if not os.path.exists(self.SESSION_FILE):
             self.add_tab() # Default behavior
             return

        try:
            with open(self.SESSION_FILE, 'r') as f:
                session_data = json.load(f)

            if "window_geometry" in session_data:
                self.restoreGeometry(QByteArray.fromBase64(session_data["window_geometry"].encode()))
            if "window_state" in session_data:
                self.restoreState(QByteArray.fromBase64(session_data["window_state"].encode()))

            tabs = session_data.get("tabs", [])
            if not tabs:
                self.add_tab()
                return

            for tab_data in tabs:
                self.add_tab()
                current_tab_index = self.tab_widget.count() - 1
                current_tab = self.tab_widget.widget(current_tab_index)
                
                # Restore SQL Content
                editor = current_tab.findChild(CodeEditor, "query_editor")
                if editor:
                    editor.setPlainText(tab_data.get("sql_content", ""))
                
                # Restore Connection
                db_combo = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo:
                    db_combo.setCurrentIndex(tab_data.get("selected_connection_index", 0))

                # Restore Limits
                current_tab.current_limit = tab_data.get("current_limit", 1000)
                current_tab.current_offset = tab_data.get("current_offset", 0)
                
                # Restore Title (Initial add_tab sets default, we override if meaningful)
                # self.tab_widget.setTabText(current_tab_index, tab_data.get("title", "Query"))

        except Exception as e:
            print(f"Error restoring session: {e}")
            self.add_tab() # Fallback
# {siam}
            