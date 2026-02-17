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
from PyQt6.QtGui import QAction, QIcon, QStandardItemModel, QStandardItem, QFont, QMovie, QDesktopServices, QColor, QBrush, QKeySequence, QShortcut

from PyQt6.QtCore import Qt, QByteArray, QDir, QModelIndex,QSortFilterProxyModel, QSize, QObject, pyqtSignal, QRunnable, QThreadPool, QTimer, QUrl, QEvent
from widgets.find_replace_dialog import FindReplaceDialog
from dialogs import (
    PostgresConnectionDialog, SQLiteConnectionDialog, OracleConnectionDialog,
    ExportDialog, CSVConnectionDialog, ServiceNowConnectionDialog,
    CreateTableDialog, CreateViewDialog
)

from workers import RunnableExport, RunnableExportFromModel, RunnableQuery, ProcessSignals, QuerySignals
from notification_manager import NotificationManager
from table_properties import TablePropertiesDialog
from code_editor import CodeEditor
from widgets.explain_visualizer import ExplainVisualizer
from widgets.erd_diagram import ERDWidget
from widgets.connection_manager import ConnectionManager
from widgets.worksheet import WorksheetManager
from widgets.results_view import ResultsManager
import db




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

        # 1. Initialize Status Bar (needed by managers)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_message_label = QLabel("Ready")
        self.status.addWidget(self.status_message_label)

        # 2. Initialize Tab Widget (needed by managers)
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumWidth(200)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        # 3. Create Actions & Menus (needed by managers)
        self._create_actions()
        self._create_menu()

        # 4. Initialize Notification Manager (needed by ConnectionManager)
        self.notification_manager = NotificationManager(self)

        # 5. --- Initialize Managers ---
        self.connection_manager = ConnectionManager(self)
        self.worksheet_manager = WorksheetManager(self)
        self.results_manager = ResultsManager(self)

        # --- Compatibility Aliases ---
        self.tree = self.connection_manager.tree
        self.model = self.connection_manager.model
        self.proxy_model = self.connection_manager.proxy_model
        self.schema_tree = self.connection_manager.schema_tree
        self.schema_model = self.connection_manager.schema_model

        # --- Layout Setup ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(2)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(self.main_splitter)

        # Add widgets to splitter
        # The ConnectionManager IS the left panel widget
        self.main_splitter.addWidget(self.connection_manager)
        self.main_splitter.addWidget(self.tab_widget)

        # 6. Additional UI for Tab Widget
        add_tab_btn = QPushButton("New")
        add_tab_btn.setObjectName("add_tab_btn")
        add_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_tab_btn.setToolTip("New Worksheet (Alt+Ctrl+S)")
        add_tab_btn.clicked.connect(self.add_tab)
        
        # Integrated Silver/Gray Enterprise Style
        add_tab_btn.setStyleSheet("""
            QPushButton#add_tab_btn { 
                padding: 2px 10px; 
                border: 1px solid #A9A9A9; 
                background-color: #f5f5f5; 
                border-radius: 4px; 
                color: #333333;
                font-weight: bold;
                font-size: 9pt;
                text-align: center;
            }
            QPushButton#add_tab_btn:hover {
                background-color: #e8e8e8;
                border: 1px solid #777777;
            }
            QPushButton#add_tab_btn:pressed {
                background-color: #dcdcdc;
            }
        """)
        self.tab_widget.setCornerWidget(add_tab_btn)

        self.thread_monitor_timer = QTimer()
        self.thread_monitor_timer.timeout.connect(self.update_thread_pool_status)
        self.thread_monitor_timer.start(1000)

        # self.load_data() - Handled by ConnectionManager
        self.restore_session_state()
        self.main_splitter.setSizes([280, 920])
        self._apply_styles()
        self.raise_()
        self.activateWindow()

    # --- DELEGATION TO MANAGERS ---

    def add_tab(self):
        return self.worksheet_manager.add_tab()

    def close_tab(self, index):
        self.worksheet_manager.close_tab(index)

    def renumber_tabs(self):
        self.worksheet_manager.renumber_tabs()


    def load_data(self):
        self.connection_manager.load_data()

    def _create_table_from_menu(self):
        self.connection_manager._create_table_from_menu()

    def _create_view_from_menu(self):
        self.connection_manager._create_view_from_menu()

    def _query_tool_from_menu(self):
        self.connection_manager._query_tool_from_menu()

    def _delete_object_from_menu(self):
        self.connection_manager._delete_object_from_menu()

    def _properties_object_from_menu(self):
        self.connection_manager._properties_object_from_menu()

    def refresh_object_explorer(self):
        self.connection_manager.refresh_object_explorer()

    def execute_query(self, *args, **kwargs):
        return self.worksheet_manager.execute_query(*args, **kwargs)

    def generate_erd(self, item):
        # item is a QStandardItem from ConnectionManager
        item_data = item.data(Qt.ItemDataRole.UserRole)
        display_name = item.text()
        self.generate_erd_for_item(item_data, display_name)

    def generate_erd_for_item(self, item_data, display_name):
        try:
            if not item_data or not isinstance(item_data, dict):
                QMessageBox.warning(self, "Error", "Invalid item data for ERD generation.")
                return

            # Normalize db_type lookup
            db_type_val = (item_data.get('db_type') or item_data.get('type') or item_data.get('code') or '').upper()
            schema_name = item_data.get('schema_name')
            table_name = item_data.get('table_name')
            
            # Connection data might be nested for schema/table nodes
            conn_info = item_data.get('conn_data') or item_data
            
            full_schema = {}
            if 'POSTGRES' in db_type_val:
                # Optimized: If we know the schema name, only fetch that schema
                full_schema = db.get_postgres_schema(conn_info, schema_name=schema_name)
            elif 'SQLITE' in db_type_val:
                # SQLite helper expects the db_path string or a dict containing it
                full_schema = db.get_sqlite_schema(conn_info)
            else:
                QMessageBox.warning(self, "Not Supported", f"ERD generation is not supported for {db_type_val or 'unknown type'}")
                return

            if not full_schema:
                QMessageBox.warning(self, "No Data", "Could not retrieve schema data for ERD.")
                return

            # Apply Filtering for Focused/Filtered View
            filtered_schema = full_schema
            if table_name:
                # Focused ERD Logic: Target table + connected tables (neighbors)
                # Note: target_full_name depends on how get_postgres_schema/get_sqlite_schema keys are built
                # Postgres uses "schema.table", SQLite uses "table"
                target_full_name = f"{schema_name}.{table_name}" if schema_name and 'POSTGRES' in db_type_val else table_name
                
                if target_full_name in full_schema:
                    related_tables = {target_full_name}
                    # 1. Add tables referenced BY the target table (outbound)
                    for fk in full_schema[target_full_name].get('foreign_keys', []):
                        related_tables.add(fk['table'])
                    # 2. Add tables referencing the target table (inbound)
                    for t_name, t_info in full_schema.items():
                        for fk in t_info.get('foreign_keys', []):
                            if fk['table'] == target_full_name:
                                related_tables.add(t_name)
                    
                    filtered_schema = {name: info for name, info in full_schema.items() if name in related_tables}

            if not filtered_schema:
                QMessageBox.warning(self, "No Data", "No related tables found for ERD.")
                return

            erd_widget = ERDWidget(filtered_schema)
            index = self.tab_widget.addTab(erd_widget, f"Worksheet {self.tab_widget.count() + 1}")
            self.tab_widget.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate ERD: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate ERD: {e}")

    def refresh_all_comboboxes(self):
        self.worksheet_manager.refresh_all_comboboxes()


    def load_joined_connections(self, combo_box):
        return self.worksheet_manager.load_joined_connections(combo_box)

    def _create_actions(self):
        self.open_file_action = QAction(QIcon("assets/bright_folder_icon.svg"), "Open File", self)
        self.open_file_action.setIconVisibleInMenu(False)
        self.open_file_action.setShortcut("Ctrl+O")
        self.open_file_action.triggered.connect(self.open_sql_file)
        
        self.save_as_action = QAction(QIcon("assets/bright_save_icon.svg"), "Save As...", self)
        self.save_as_action.setIconVisibleInMenu(False)
        self.save_as_action.setShortcut("Ctrl+S")
        self.save_as_action.triggered.connect(self.save_sql_file_as)
        
        self.exit_action = QAction(QIcon("assets/exit.svg"), "Exit", self)
        self.exit_action.setIconVisibleInMenu(False)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)
        
        self.execute_action = QAction(QIcon("assets/execute_icon.png"), "Execute", self)
        self.execute_action.setIconVisibleInMenu(False)
        self.execute_action.setShortcuts(["Ctrl+Enter","Ctrl+RETURN"])
        self.execute_action.triggered.connect(self.execute_query)
        
        self.explain_action = QAction(QIcon("assets/explain_icon.png"), "Explain", self)
        self.explain_action.setIconVisibleInMenu(False)
        self.explain_action.setShortcut("Ctrl+E")
        self.explain_action.triggered.connect(self.explain_query)
        
        # New actions for Explain/Analyze button{siam}
        self.explain_analyze_action = QAction("Explain Analyze", self)
        self.explain_analyze_action.triggered.connect(self.explain_query) # Reuse existing logic       
        self.explain_plan_action = QAction("Explain (Plan)", self)
        self.explain_plan_action.triggered.connect(self.explain_plan_query)

        self.cancel_action = QAction(QIcon("assets/cancel_icon.png"), "Cancel", self)
        self.cancel_action.setIconVisibleInMenu(False)
        self.cancel_action.triggered.connect(self.cancel_current_query)
        self.cancel_action.setEnabled(False)
        
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_text)
        
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        self.redo_action.triggered.connect(self.redo_text)
        
        self.cut_action = QAction("Cut", self)
        self.cut_action.setShortcut("Ctrl+X")
        self.cut_action.triggered.connect(self.cut_text)
        
        self.copy_action = QAction("Copy", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.triggered.connect(self.copy_text)
        
        self.paste_action = QAction("Paste", self)
        self.paste_action.setShortcut("Ctrl+V")
        self.paste_action.triggered.connect(self.paste_text)
        
        self.delete_action = QAction("Delete", self)
        self.delete_action.triggered.connect(self.delete_text)
        
        self.query_tool_action = QAction(QIcon("assets/sql_sheet_plus.svg"), "Query Tool", self)
        self.query_tool_action.setIconVisibleInMenu(False)
        self.query_tool_action.setShortcut("Ctrl+T")
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
        self.format_sql_action.setIconVisibleInMenu(False)
        self.format_sql_action.setShortcut("Ctrl+Shift+F")
        self.format_sql_action.triggered.connect(self.format_sql_text)

        self.clear_query_action = QAction(QIcon("assets/delete_icon.png"), "Clear Query", self)
        self.clear_query_action.setIconVisibleInMenu(False)
        self.clear_query_action.setShortcut("Ctrl+Shift+c")
        self.clear_query_action.triggered.connect(self.clear_query_text)

        # Object Menu Actions
        self.create_table_action = QAction(QIcon("assets/table.svg"), "Table...", self)
        self.create_table_action.setIconVisibleInMenu(False)
        self.create_table_action.triggered.connect(self._create_table_from_menu)
        
        self.create_view_action = QAction(QIcon("assets/eye.svg"), "View...", self)
        self.create_view_action.setIconVisibleInMenu(False)
        self.create_view_action.triggered.connect(self._create_view_from_menu)

        self.delete_object_action = QAction(QIcon("assets/trash.svg"), "Delete/Drop...", self)
        self.delete_object_action.setIconVisibleInMenu(False)
        self.delete_object_action.triggered.connect(self._delete_object_from_menu)
        
        self.properties_object_action = QAction(QIcon("assets/settings.svg"), "Properties...", self)
        self.properties_object_action.setIconVisibleInMenu(False)
        self.properties_object_action.triggered.connect(self._properties_object_from_menu)

        self.query_tool_obj_action = QAction(QIcon("assets/sql_sheet_plus.svg"), "Query Tool", self)
        self.query_tool_obj_action.setIconVisibleInMenu(False)
        self.query_tool_obj_action.triggered.connect(self._query_tool_from_menu)


    def _create_menu(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.open_file_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
    
        file_menu.addAction(self.exit_action)
        
        object_menu = menubar.addMenu("&Object")
        create_menu = object_menu.addMenu("Create")
        create_menu.addAction(self.create_table_action)
        create_menu.addAction(self.create_view_action)
        object_menu.addAction(self.query_tool_obj_action)
        object_menu.addAction(self.refresh_action)
        # object_menu.addSeparator()
        object_menu.addAction(self.delete_object_action)


        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
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



    def open_find_dialog(self, replace=False):
        editor = self._get_current_editor()
        if not editor:
            return
            
        if not hasattr(self, 'find_replace_dialog'):
            self.find_replace_dialog = FindReplaceDialog(self)
            self.find_replace_dialog.find_next.connect(lambda t, c, w: self._on_find_next(t, c, w))
            self.find_replace_dialog.find_previous.connect(lambda t, c, w: self._on_find_prev(t, c, w))
            self.find_replace_dialog.replace.connect(lambda t, r, c, w: self._on_replace(t, r, c, w))
            self.find_replace_dialog.replace_all.connect(lambda t, r, c, w: self._on_replace_all(t, r, c, w))
            
        cursor = editor.textCursor()
        if cursor.hasSelection():
            self.find_replace_dialog.set_find_text(cursor.selectedText())
            
        self.find_replace_dialog.show()
        self.find_replace_dialog.raise_()
        self.find_replace_dialog.activateWindow()
        
        if replace:
            self.find_replace_dialog.replace_input.setFocus()
        else:
            self.find_replace_dialog.find_input.setFocus()

    def _on_find_next(self, text, case, whole):
        editor = self._get_current_editor()
        if editor:
            found = editor.find(text, case, whole, True)
            if not found:
                self.status.showMessage(f"Text '{text}' not found.", 2000)

    def _on_find_prev(self, text, case, whole):
        editor = self._get_current_editor()
        if editor:
            found = editor.find(text, case, whole, False)
            if not found:
                self.status.showMessage(f"Text '{text}' not found.", 2000)

    def _on_replace(self, target, replacement, case, whole):
        editor = self._get_current_editor()
        if editor:
            editor.replace_curr(target, replacement, case, whole)

    def _on_replace_all(self, target, replacement, case, whole):
        editor = self._get_current_editor()
        if editor:
            count = editor.replace_all(target, replacement, case, whole)
            self.status.showMessage(f"Replaced {count} occurrences.", 3000)


# {siam}
    # --- New Handler Methods for Menu Actions ---km

    def format_sql_text(self):
        self.worksheet_manager.format_sql_text()

    def clear_query_text(self):
        self.worksheet_manager.clear_query_text()

    def show_about_dialog(self):
        QMessageBox.about(self, "About SQL Client", "<b>SQL Client Application</b><p>Version 1.0.0</p><p>This is a versatile SQL client designed to connect to and manage multiple database systems including PostgreSQL and SQLite.</p><p><b>Features:</b></p><ul><li>Object Explorer for database schemas</li><li>Multi-tab query editor with syntax highlighting</li><li>Query history per connection</li><li>Asynchronous query execution to keep the UI responsive</li></ul><p>Developed to provide a simple and effective tool for database management.</p>")

    def _get_current_editor(self):
        return self.worksheet_manager._get_current_editor()

    def undo_text(self):
        self.worksheet_manager.undo_text()

    def redo_text(self):
        self.worksheet_manager.redo_text()

    def cut_text(self):
        self.worksheet_manager.cut_text()

    def copy_text(self):
        self.worksheet_manager.copy_text()

    def paste_text(self):
        self.worksheet_manager.paste_text()

    def delete_text(self):
        self.worksheet_manager.delete_text()

    def explain_query(self):
        self.worksheet_manager.explain_query()

    def explain_plan_query(self):
        self.worksheet_manager.explain_plan_query()

    def cancel_current_query(self):
        self.worksheet_manager.cancel_current_query()





    # --- Object Menu Handlers ---


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
        self.setStyleSheet(f"""
        QSplitter::handle {{ background: #e0e0e0; border: none; }}
        QMainWindow, QToolBar, QStatusBar {{ background-color: {primary_color}; color: {text_color_on_primary}; }}
        QTreeView {{ background-color: white; alternate-background-color: {alternate_row_color}; border: 1px solid {border_color}; outline: none; }}
        QTreeView::item {{ border: none; }}
        QTreeView::item:selected, QTreeView::item:selected:active, QTreeView::item:selected:!active {{ background-color: #f0f0f0; color: black; border: none; outline: none; }}
        QTableView {{ alternate-background-color: {alternate_row_color}; background-color: white; gridline-color: #a9a9a9; border: 1px solid {border_color}; font-family: Arial, sans-serif; font-size: 9pt;}}
        QTableView::item {{ padding: 4px; }}
        QTableView::item:selected {{ background-color: {selection_color}; color: white; }}
        QHeaderView::section {{
            background-color: #A9A9A9;
            color: #ffffff;
            padding: 4px;
            border: none;
            border-right: 1px solid #d3d3d3;
            border-bottom: 1px solid #A9A9A9;
            font-weight: bold;
            font-size: 10pt;
        }}
        QHeaderView::section:disabled {{
            color: #ffffff;
        }}
        
        QTreeView QHeaderView::section {{
            background-color: #A9A9A9;
            color: #ffffff;
            font-weight: bold;
        }}
        
        #objectExplorerLabel {{
            font-size: 10pt;
            font-weight: bold;
            color: #ffffff;
            background-color: #A9A9A9;
            border: none;
            padding: 0;
        }}
        
        #objectExplorerLabel:disabled {{
            color: #ffffff;
        }}
        
        #objectExplorerHeader {{
            background-color: #A9A9A9;
            border-bottom: 1px solid #777777;
        }}

        QMenuBar {{
            background-color: {primary_color};
            border: none;
        }}

        QMenuBar::item {{
            background: transparent;
            padding: 4px 12px;
            margin: 0px;
        }}

        QMenuBar::item:selected {{
        background-color: {selection_color};
        color: white;
        }}

        QMenuBar::separator {{
        width: 0px;
        background: transparent;
        }}

        
        QTableView QTableCornerButton::section {{ background-color: {header_color}; border: 1px solid {border_color}; }}
        #resultsHeader QPushButton, #editorHeader QPushButton {{ background-color: #ffffff; border: 1px solid {border_color}; padding: 5px 15px; font-size: 9pt; }}
        #resultsHeader QPushButton:hover, #editorHeader QPushButton:hover {{ background-color: {primary_color}; }}
        #resultsHeader QPushButton:checked, #editorHeader QPushButton:checked {{ background-color: {selection_color}; border-bottom: 1px solid {selection_color}; font-weight: bold; color: white; }}
        #resultsHeader, #editorHeader {{ background-color: {alternate_row_color}; padding-bottom: -1px; }}
        #messageView, #history_details_view, QTextEdit {{ font-family: Consolas, monospace; font-size: 10pt; background-color: white; border: 1px solid {border_color}; }}
        #tab_status_label {{ padding: 3px 5px; background-color: {alternate_row_color}; border-top: 1px solid {border_color}; }}
        QGroupBox {{ font-size: 9pt; font-weight: bold; color: {text_color_on_primary}; }}
        QTabWidget::pane {{ border-top: 1px solid {border_color}; }}
        QTabBar::tab {{ background: #E0E0E0; border: 1px solid {border_color}; padding: 5px 10px; border-bottom: none; }}
        QTabBar::tab:selected {{ background: {selection_color}; color: white; }}
        QComboBox {{ border: 1px solid {border_color}; padding: 2px; background-color: white; }}
        
        /* Premium Search Bar Styling */
        QLineEdit#table_search_box {{
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 14px;
            padding: 2px 10px 2px 30px;
            font-size: 9pt;
            color: #333333;
        }}
        QLineEdit#table_search_box:hover {{
            border: 1px solid #adb5bd;
        }}
        QLineEdit#table_search_box:focus {{
            border: 1px solid #2196F3;
            background-color: #ffffff;
        }}
    """)
        

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
            