import sys
import os
import json
import time
import datetime
import psycopg2
import sqlite3 as sqlite
import cdata.csv as mod
import cdata.servicenow 
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QLineEdit, QToolButton,
    QMenu, QMessageBox, QInputDialog, QAbstractItemView, QHeaderView,
    QComboBox, QPlainTextEdit, QStackedWidget, QTextEdit, QPushButton,
    QLabel, QDialog, QApplication, QStyle, QSplitter, QFrame
)
from PyQt6.QtGui import (
    QStandardItemModel, QStandardItem, QIcon, QAction, QColor, QFont
)
from PyQt6.QtCore import (
    Qt, QModelIndex, QSortFilterProxyModel, QSize, QTimer, QObject, pyqtSignal, QEvent
)
import db
from dialogs import (
    PostgresConnectionDialog, SQLiteConnectionDialog, OracleConnectionDialog,
    CSVConnectionDialog, ServiceNowConnectionDialog,
    CreateTableDialog, CreateViewDialog, ExportDialog
)
from table_properties import TablePropertiesDialog
from code_editor import CodeEditor

from workers.workers import RunnableQuery, RunnableExportFromModel
from workers.signals import ProcessSignals, QuerySignals
import uuid
import re

class ConnectionManager(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        # Proxies to main_window components
        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.status_message_label = main_window.status_message_label
        self.thread_pool = main_window.thread_pool
        self.notification_manager = main_window.notification_manager
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Create Object Explorer Header (Toolbar Group) ---
        object_explorer_header = QWidget()
        object_explorer_header.setFixedHeight(36)
        object_explorer_header.setObjectName("objectExplorerHeader")
        object_explorer_header.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        object_explorer_header.setStyleSheet("""
            #objectExplorerHeader { 
                background-color: #A9A9A9; 
                border: none; 
            }
            QLabel {
                color: white;
                font-weight: bold;
            }
        """)
        object_explorer_header_layout = QHBoxLayout(object_explorer_header)
        object_explorer_header_layout.setContentsMargins(8, 0, 8, 0)
        object_explorer_header_layout.setSpacing(10)

        object_explorer_label = QLabel("Object Explorer")
        object_explorer_label.setObjectName("objectExplorerLabel")
        object_explorer_label.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        object_explorer_label.setStyleSheet("color: white; font-weight: bold; font-size: 10pt;")
        object_explorer_header_layout.addWidget(object_explorer_label)

        self.explorer_search_container = QWidget()
        self.explorer_search_layout = QHBoxLayout(self.explorer_search_container)
        self.explorer_search_layout.setContentsMargins(0, 0, 0, 0)
        self.explorer_search_layout.setSpacing(0)

        self.explorer_search_box = QLineEdit()
        self.explorer_search_box.setPlaceholderText("Filter...")
        self.explorer_search_box.setFixedHeight(24)
        self.explorer_search_box.setObjectName("explorer_search_box")
        self.explorer_search_box.setFixedWidth(120)
        self.explorer_search_box.hide()  # Initially Hidden

        search_icon_path = "assets/search.svg"
        if os.path.exists(search_icon_path):
             self.explorer_search_box.addAction(QIcon(search_icon_path), QLineEdit.ActionPosition.LeadingPosition)
             
        self.explorer_search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #A9A9A9;
                border-radius: 4px;
                padding-left: 2px;
                background-color: #ffffff;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
        """)
        self.explorer_search_box.textChanged.connect(self.filter_object_explorer)
        self.explorer_search_box.installEventFilter(self)

        self.explorer_search_btn = QToolButton()
        self.explorer_search_btn.setIcon(QIcon(search_icon_path if os.path.exists(search_icon_path) else ""))
        self.explorer_search_btn.setFixedSize(26, 26)
        self.explorer_search_btn.setIconSize(QSize(16, 16))
        self.explorer_search_btn.setToolTip("Search Connections")
        self.explorer_search_btn.setStyleSheet("""
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
        self.explorer_search_btn.clicked.connect(self.toggle_explorer_search)

        self.explorer_search_layout.addWidget(self.explorer_search_box)
        self.explorer_search_layout.addWidget(self.explorer_search_btn)
        
        object_explorer_header_layout.addStretch()
        object_explorer_header_layout.addWidget(self.explorer_search_container)
        
        # Trees
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setHandleWidth(0)
        self.vertical_splitter.setStyleSheet("QSplitter { border: none; margin: 0; padding: 0; }")

        self.tree = QTreeView()
        self.tree.setFrameShape(QFrame.Shape.NoFrame)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.clicked.connect(self.item_clicked)
        self.tree.doubleClicked.connect(self.item_double_clicked)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(15)
        
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Object Explorer'])
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tree.setModel(self.proxy_model)
        self.tree.setStyleSheet("QTreeView { border: none; margin: 0; padding: 0; background-color: white; }")
        
        self.vertical_splitter.addWidget(self.tree)

        self.schema_tree = QTreeView()
        self.schema_tree.setFrameShape(QFrame.Shape.NoFrame)
        self.schema_model = QStandardItemModel()
        self.schema_model.setHorizontalHeaderLabels(["Database Schema"])
        self.schema_tree.setModel(self.schema_model)
        self.schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.schema_tree.customContextMenuRequested.connect(self.show_schema_context_menu)
        self.schema_tree.doubleClicked.connect(self.schema_item_double_clicked)
        self.schema_tree.setIndentation(15)
        
        self.vertical_splitter.addWidget(self.schema_tree)
        self.vertical_splitter.setSizes([240, 360])

        layout.addWidget(object_explorer_header)
        layout.addWidget(self.vertical_splitter)

    # Proxy methods for main_window
    def add_tab(self):
        return self.main_window.add_tab()

    def execute_query(self, *args, **kwargs):
        return self.main_window.execute_query(*args, **kwargs)

    def refresh_all_comboboxes(self):
        self.main_window.refresh_all_comboboxes()

    def generate_erd(self, item):
        self.main_window.generate_erd(item)

    def generate_erd_for_item(self, item_data, display_name):
        self.main_window.generate_erd_for_item(item_data, display_name)

    def show_error_popup(self, msg):
        QMessageBox.critical(self, "Error", msg)

    def _get_current_schema_item_data(self):
        index = self.schema_tree.currentIndex()
        if not index.isValid():
            return None, None, None
        item = self.schema_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        return item, item_data, item.text() if item else None

    def _create_table_from_menu(self):
        item, item_data, name = self._get_current_schema_item_data()
        if item_data:
            self.open_create_table_template(item_data)
        else:
            QMessageBox.warning(self, "Warning", "Please select a schema or table in the Database Schema tree first.")

    def _create_view_from_menu(self):
        item, item_data, name = self._get_current_schema_item_data()
        if item_data:
            self.open_create_view_template(item_data)
        else:
            QMessageBox.warning(self, "Warning", "Please select a schema or table in the Database Schema tree first.")

    def _query_tool_from_menu(self):
        item, item_data, name = self._get_current_schema_item_data()
        if item_data:
            self.open_query_tool_for_table(item_data, name)
        else:
            self.add_tab()

    def _delete_object_from_menu(self):
        item, item_data, name = self._get_current_schema_item_data()
        if item_data and item_data.get('table_name'):
             self.delete_table(item_data, name)
        else:
            QMessageBox.warning(self, "Warning", "Please select a table or view to delete.")

    def _properties_object_from_menu(self):
        item, item_data, name = self._get_current_schema_item_data()
        if item_data and item_data.get('table_name'):
             self.show_table_properties(item_data, name)
        else:
            QMessageBox.warning(self, "Warning", "Please select a table or view to view properties.")

    def eventFilter(self, obj, event):
        if obj.objectName() == "explorer_search_box" and event.type() == QEvent.Type.FocusOut:
            obj.hide()
            self.explorer_search_btn.show()
        return super().eventFilter(obj, event)

    def refresh_object_explorer(self):
        self._save_tree_expansion_state()
        self.load_data()
        self._restore_tree_expansion_state()
        self.status.showMessage("Object Explorer refreshed.", 3000)




    def toggle_explorer_search(self):
        """Show/expand the search box and hide the button."""
        self.explorer_search_btn.hide()
        self.explorer_search_box.show()
        self.explorer_search_box.setFocus()

    def filter_object_explorer(self, text):
        self.proxy_model.setFilterFixedString(text)
        if text:
            self.tree.expandAll()
        else:
            self.tree.collapseAll()

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
                    
                    # Ensure db_type is present for downstream tools like ERD
                    connection_data['db_type'] = code.lower()
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
        
        if level == "FDW_ROOT" or level == "FDW" or level == "SERVER" or level == "FOREIGN_TABLE":
            # Using existing icons or falling back to folder/table
            if level == "FDW_ROOT":
                item.setIcon(QIcon("assets/server.svg"))
            elif level == "FDW":
                item.setIcon(QIcon("assets/plug.svg"))
            elif level == "SERVER":
                item.setIcon(QIcon("assets/database.svg"))
            elif level == "FOREIGN_TABLE":
                item.setIcon(QIcon("assets/table.svg")) # Maybe find a better one later
            elif level == "USER":
                item.setIcon(QIcon("assets/plus.svg"))
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


    def item_clicked(self, proxy_index):
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
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


    def item_double_clicked(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
        if not item:
            return
            
        depth = self.get_item_depth(item)
        if depth == 3:
            # Double-clicking a connection opens a new Query Tool (tab)
            self.add_tab()

    def schema_item_double_clicked(self, index: QModelIndex):
        item = self.schema_model.itemFromIndex(index)
        if not item:
            return
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        table_name = item_data.get('table_name')
        if table_name:
            # Double-clicking a table/view queries all rows
            self.query_table_rows(item_data, item.text(), limit=None, execute_now=True)

    def get_item_depth(self, item):
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        return depth + 1


    def show_context_menu(self, pos):
        proxy_index = self.tree.indexAt(pos)
        if not proxy_index.isValid(): return
        source_index = self.proxy_model.mapToSource(proxy_index)
        item = self.model.itemFromIndex(source_index)
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

            menu.addSeparator()
            erd_action = QAction("Generate ERD", self)
            erd_action.triggered.connect(lambda: self.generate_erd(item))
            menu.addAction(erd_action)
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
            QHeaderView::section {
                border-right: 1px solid #d3d3d3;
                padding: 4px;
                background-color: #a9a9a9;   
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

            # --- ADD FDW NODE ---
            fdw_root = QStandardItem("Foreign Data Wrappers")
            fdw_root.setEditable(False)
            self._set_tree_item_icon(fdw_root, level="FDW_ROOT")
            fdw_root.setData({'db_type': 'postgres', 'type': 'fdw_root', 'conn_data': conn_data}, Qt.ItemDataRole.UserRole)
            fdw_root.appendRow(QStandardItem("Loading..."))
            
            fdw_type_item = QStandardItem("Group")
            fdw_type_item.setEditable(False)
            self.schema_model.appendRow([fdw_root, fdw_type_item])
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
            QHeaderView::section {
                border-right: 1px solid #d3d3d3;
                padding: 4px;
                background-color: #a9a9a9;   
            }
        """)
        
        

    def _open_script_in_editor(self, item_data, sql):
        if not item_data:
            return

        conn_data = item_data.get("conn_data")
        new_tab = self.add_tab()
        if not new_tab:
            return

        # Find the editor and connection dropdown
        query_editor = new_tab.findChild(CodeEditor, "query_editor")
        if not query_editor:
            query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
        
        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        # Select the correct connection in combo box
        if db_combo_box and conn_data:
            for i in range(db_combo_box.count()):
                data = db_combo_box.itemData(i)
                if data and data.get('id') == conn_data.get('id'):
                    db_combo_box.setCurrentIndex(i)
                    break

        if query_editor:
            query_editor.setPlainText(sql)
            query_editor.setFocus()

        # Make sure the new tab becomes the active one
        self.tab_widget.setCurrentWidget(new_tab)

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
            erd_action = QAction("Generate ERD", self)
            erd_action.triggered.connect(
                lambda: self.generate_erd_for_item(item_data, display_name))
            menu.addAction(erd_action)
            
            menu.addSeparator()
            scripts_menu = menu.addMenu("Scripts")
            create_script_action = QAction("CREATE Script", self)
            create_script_action.triggered.connect(lambda: self.script_table_as_create(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            create_script_action = QAction("INSERT Script", self)
            create_script_action.triggered.connect(lambda: self.script_table_as_insert(item_data, display_name))
            scripts_menu.addAction(create_script_action)

            create_script_action = QAction("DELETE Script", self)
            create_script_action.triggered.connect(lambda: self.script_table_as_delete(item_data, display_name))
            scripts_menu.addAction(create_script_action)
            create_script_action = QAction("UPDATE Script", self)
            create_script_action.triggered.connect(lambda: self.script_table_as_update(item_data, display_name))
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
            # --- Schema Actions ---
            if db_type == 'postgres':
                import_fdw_action = QAction("Import Foreign Schema...", self)
                import_fdw_action.triggered.connect(lambda: self.import_foreign_schema_dialog(item_data))
                menu.addAction(import_fdw_action)
                
                erd_action = QAction("Generate ERD", self)
                erd_action.triggered.connect(
                    lambda: self.generate_erd_for_item(item_data, f"Schema: {schema_name}"))
                menu.addAction(erd_action)
                
                menu.addSeparator()

        elif item_data.get('type') == 'fdw_root':
            # --- Foreign Data Wrappers Root ---
            create_fdw_action = QAction("Create Foreign Data Wrapper...", self)
            create_fdw_action.triggered.connect(lambda: self.create_fdw_template(item_data))
            menu.addAction(create_fdw_action)

        elif item_data.get('type') == 'fdw':
            # --- Individual FDW ---
            create_srv_action = QAction("Create Foreign Server...", self)
            create_srv_action.triggered.connect(lambda: self.create_foreign_server_template(item_data))
            menu.addAction(create_srv_action)
            
            menu.addSeparator()
            drop_fdw_action = QAction("Drop Foreign Data Wrapper", self)
            drop_fdw_action.triggered.connect(lambda: self.drop_fdw(item_data))
            menu.addAction(drop_fdw_action)

        elif item_data.get('type') == 'foreign_server':
            # --- Foreign Server ---
            create_um_action = QAction("Create User Mapping...", self)
            create_um_action.triggered.connect(lambda: self.create_user_mapping_template(item_data))
            menu.addAction(create_um_action)
            
            menu.addSeparator()
            drop_srv_action = QAction("Drop Foreign Server", self)
            drop_srv_action.triggered.connect(lambda: self.drop_foreign_server(item_data))
            menu.addAction(drop_srv_action)

        elif item_data.get('type') == 'user_mapping':
            # --- User Mapping ---
            drop_um_action = QAction("Drop User Mapping", self)
            drop_um_action.triggered.connect(lambda: self.drop_user_mapping(item_data))
            menu.addAction(drop_um_action)

        if menu.isEmpty():
            return

        menu.exec(self.schema_tree.viewport().mapToGlobal(position))

    def show_table_properties(self, item_data, table_name):
        if not item_data:
            return
        
        dialog = TablePropertiesDialog(item_data, table_name, self)
        dialog.show()

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
            self._open_script_in_editor(item_data, sql_script)



    def script_table_as_insert(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
             sql = f'INSERT INTO "{schema_name}"."{table_name}" (\n    -- column1, column2, ...\n)\nVALUES (\n    -- value1, value2, ...\n);'
        else:
             sql = f'INSERT INTO "{table_name}" (\n    -- column1, column2, ...\n)\nVALUES (\n    -- value1, value2, ...\n);'
        self._open_script_in_editor(item_data, sql)

    def script_table_as_update(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
             sql = f'UPDATE "{schema_name}"."{table_name}"\nSET \n    -- column1 = value1,\n    -- column2 = value2\nWHERE <condition>;'
        else:
             sql = f'UPDATE "{table_name}"\nSET \n    -- column1 = value1,\n    -- column2 = value2\nWHERE <condition>;'
        self._open_script_in_editor(item_data, sql)

    def script_table_as_delete(self, item_data, table_name):
        schema_name = item_data.get('schema_name', 'public')
        db_type = item_data.get('db_type')
        if db_type == 'postgres':
            sql = f'DELETE FROM "{schema_name}"."{table_name}"\nWHERE <condition>;'
        else:
            sql = f'DELETE FROM "{table_name}"\nWHERE <condition>;'
        self._open_script_in_editor(item_data, sql)


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
        
        # Get the current active tab to display results in
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            # No tab open, create one first
            self.add_tab()
            current_tab = self.tab_widget.currentWidget()
        
        signals = QuerySignals()
        runnable = RunnableQuery(conn_data, query, signals)
        
        # Route to ResultsManager.handle_query_result like a normal query
        results_manager = self.main_window.results_manager
        signals.finished.connect(
            lambda cd, q, res, cols, rc, et, isq: results_manager.handle_query_result(
                current_tab, cd, q, res, cols, rc, et, isq))
        signals.error.connect(self.handle_count_error)
        self.thread_pool.start(runnable)

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

                        if "TABLE" in table_type and "FOREIGN" not in table_type:
                            self._set_tree_item_icon(table_item, level="TABLE")
                            type_text = "Table"
                        elif "VIEW" in table_type:
                            self._set_tree_item_icon(table_item, level="VIEW")
                            type_text = "View"
                        elif "FOREIGN" in table_type:
                            self._set_tree_item_icon(table_item, level="FOREIGN_TABLE")
                            type_text = "Foreign Table"
                        else:
                            type_text = table_type.title() 
                        
                        type_item = QStandardItem(type_text)
                        type_item.setEditable(False)

                        item.appendRow([table_item, type_item])
                       
                except Exception as e:
                    self.status.showMessage(f"Error expanding schema: {e}", 5000)
                    item.appendRow(QStandardItem(f"Error: {e}"))
            
            elif item_data.get('type') == 'fdw_root':
                # --- CASE 2.1: Expanding FDW ROOT ---
                item.removeRows(0, item.rowCount())
                try:
                    cursor = self.pg_conn.cursor()
                    cursor.execute("SELECT fdwname FROM pg_foreign_data_wrapper ORDER BY fdwname;")
                    for (fdw_name,) in cursor.fetchall():
                        fdw_item = QStandardItem(fdw_name)
                        fdw_item.setEditable(False)
                        self._set_tree_item_icon(fdw_item, level="FDW")
                        
                        fdw_data = item_data.copy()
                        fdw_data['type'] = 'fdw'
                        fdw_data['fdw_name'] = fdw_name
                        fdw_item.setData(fdw_data, Qt.ItemDataRole.UserRole)
                        fdw_item.appendRow(QStandardItem("Loading..."))
                        
                        type_item = QStandardItem("Foreign Data Wrapper")
                        type_item.setEditable(False)
                        item.appendRow([fdw_item, type_item])
                except Exception as e:
                    self.status.showMessage(f"Error loading FDWs: {e}", 5000)

            elif item_data.get('type') == 'fdw':
                # --- CASE 2.2: Expanding FDW -> show Foreign Servers ---
                item.removeRows(0, item.rowCount())
                fdw_name = item_data.get('fdw_name')
                try:
                    cursor = self.pg_conn.cursor()
                    cursor.execute("""
                        SELECT srvname 
                        FROM pg_foreign_server 
                        WHERE srvfdw = (SELECT oid FROM pg_foreign_data_wrapper WHERE fdwname = %s)
                        ORDER BY srvname;
                    """, (fdw_name,))
                    for (srv_name,) in cursor.fetchall():
                        srv_item = QStandardItem(srv_name)
                        srv_item.setEditable(False)
                        self._set_tree_item_icon(srv_item, level="SERVER")
                        
                        srv_data = item_data.copy()
                        srv_data['type'] = 'foreign_server'
                        srv_data['server_name'] = srv_name
                        srv_item.setData(srv_data, Qt.ItemDataRole.UserRole)
                        srv_item.appendRow(QStandardItem("Loading..."))
                        
                        type_item = QStandardItem("Foreign Server")
                        type_item.setEditable(False)
                        item.appendRow([srv_item, type_item])
                except Exception as e:
                    self.status.showMessage(f"Error loading Foreign Servers: {e}", 5000)

            elif item_data.get('type') == 'foreign_server':
                # --- CASE 2.3: Expanding Foreign Server -> show User Mappings ---
                item.removeRows(0, item.rowCount())
                srv_name = item_data.get('server_name')
                try:
                    cursor = self.pg_conn.cursor()
                    cursor.execute("""
                        SELECT umuser::regrole::text 
                        FROM pg_user_mapping 
                        WHERE umserver = (SELECT oid FROM pg_foreign_server WHERE srvname = %s)
                        ORDER BY 1;
                    """, (srv_name,))
                    for (user_name,) in cursor.fetchall():
                        um_item = QStandardItem(user_name)
                        um_item.setEditable(False)
                        self._set_tree_item_icon(um_item, level="USER") # Need to add USER icon maybe
                        
                        um_data = item_data.copy()
                        um_data['type'] = 'user_mapping'
                        um_data['user_name'] = user_name
                        um_item.setData(um_data, Qt.ItemDataRole.UserRole)
                        
                        type_item = QStandardItem("User Mapping")
                        type_item.setEditable(False)
                        item.appendRow([um_item, type_item])
                except Exception as e:
                    self.status.showMessage(f"Error loading User Mappings: {e}", 5000)
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
                QHeaderView::section {
                    border-right: 1px solid #d3d3d3;
                    padding: 4px;
                    background-color: #a9a9a9;   
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
    # --- Postgres FDW Management Helpers ---

    def create_fdw_template(self, item_data):
        sql = "CREATE FOREIGN DATA WRAPPER fdw_name\n    HANDLER handler_function\n    VALIDATOR validator_function;"
        self._open_script_in_editor(item_data, sql)

    def create_foreign_server_template(self, item_data):
        fdw_name = item_data.get('fdw_name', 'fdw_name')
        sql = f"CREATE SERVER server_name\n    FOREIGN DATA WRAPPER {fdw_name}\n    OPTIONS (host '127.0.0.1', port '5432', dbname 'remote_db');"
        self._open_script_in_editor(item_data, sql)

    def create_user_mapping_template(self, item_data):
        srv_name = item_data.get('server_name', 'server_name')
        sql = f"CREATE USER MAPPING FOR current_user\n    SERVER {srv_name}\n    OPTIONS (user 'remote_user', password 'password');"
        self._open_script_in_editor(item_data, sql)

    def import_foreign_schema_dialog(self, item_data):
        schema_name = item_data.get('schema_name', 'public')
        sql = f"IMPORT FOREIGN SCHEMA remote_schema\n    FROM SERVER foreign_server\n    INTO {schema_name};"
        self._open_script_in_editor(item_data, sql)

    def drop_fdw(self, item_data):
        fdw_name = item_data.get('fdw_name')
        if QMessageBox.question(self, "Drop FDW", f"Are you sure you want to drop Foreign Data Wrapper '{fdw_name}'?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._execute_simple_sql(item_data, f"DROP FOREIGN DATA WRAPPER {fdw_name} CASCADE;")

    def drop_foreign_server(self, item_data):
        srv_name = item_data.get('server_name')
        if QMessageBox.question(self, "Drop Server", f"Are you sure you want to drop Foreign Server '{srv_name}'?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._execute_simple_sql(item_data, f"DROP SERVER {srv_name} CASCADE;")

    def drop_user_mapping(self, item_data):
        user_name = item_data.get('user_name')
        srv_name = item_data.get('server_name')
        if QMessageBox.question(self, "Drop User Mapping", f"Are you sure you want to drop User Mapping for '{user_name}' on server '{srv_name}'?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._execute_simple_sql(item_data, f"DROP USER MAPPING FOR \"{user_name}\" SERVER {srv_name};")

    def _execute_simple_sql(self, item_data, sql):
        conn_data = item_data.get('conn_data')
        try:
            conn = psycopg2.connect(
                host=conn_data.get("host"),
                port=conn_data.get("port"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password")
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(sql)
            self.status.showMessage("Operation successful.", 3000)
            self.refresh_object_explorer()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "SQL Error", str(e))