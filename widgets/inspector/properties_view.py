# widgets/inspector/properties_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLabel, QScrollArea, QFormLayout
)
from PySide6.QtCore import Qt
import qtawesome as qta
from dialogs.properties import pg_queries
import db

class PropertiesWorkbench(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.item_data = None
        self.obj_name = None
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.header_label = QLabel("Properties")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1f2937;")
        layout.addWidget(self.header_label)
        
        self.sub_label = QLabel("Select an object from the tree to view its properties")
        self.sub_label.setStyleSheet("color: #6b7280; font-size: 10pt;")
        layout.addWidget(self.sub_label)
        
        # Details area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.details_widget = QWidget()
        self.details_layout = QVBoxLayout(self.details_widget)
        
        self.form_layout = QFormLayout()
        self.details_layout.addLayout(self.form_layout)
        
        self.sql_display = QTextEdit()
        self.sql_display.setReadOnly(True)
        self.sql_display.setStyleSheet("font-family: 'Consolas', monospace; background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 4px;")
        self.details_layout.addWidget(QLabel("DDL / Definition:"))
        self.details_layout.addWidget(self.sql_display)
        
        self.scroll.setWidget(self.details_widget)
        layout.addWidget(self.scroll)

    def update_view(self, item_data, obj_name):
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(f"Properties - {obj_name}")
        self.sub_label.setText(f"Type: {item_data.get('type', 'Unknown').capitalize()}")
        
        # Clear form
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.sql_display.clear()
        
        if not item_data:
            return

        db_type = item_data.get('db_type')
        if item_data.get('type') == 'connection':
            self._load_connection_data()
        elif db_type == 'postgres':
            self._load_postgres_data()
        elif db_type == 'sqlite':
            self._load_sqlite_data()

    def _load_connection_data(self):
        data = self.item_data
        self.form_layout.addRow("Connection Name:", QLabel(data.get('name', '')))
        self.form_layout.addRow("DB Type:", QLabel(data.get('db_type', '').capitalize()))
        
        if data.get('db_type') == 'postgres':
            self.form_layout.addRow("Host:", QLabel(data.get('host', '')))
            self.form_layout.addRow("Port:", QLabel(str(data.get('port', ''))))
            self.form_layout.addRow("Database:", QLabel(data.get('database', '')))
            self.form_layout.addRow("User:", QLabel(data.get('user', '')))
        elif data.get('db_type') == 'sqlite':
            self.form_layout.addRow("DB Path:", QLabel(data.get('db_path', '')))
            
        self.sql_display.setText(f"-- Connection Configuration for {self.obj_name}\n"
                                f"-- Selected via Object Explorer")

    def _load_postgres_data(self):
        conn = None
        try:
            conn_data = self.item_data.get('conn_data') or self.item_data
            pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            
            obj_type = self.item_data.get('type')
            schema_name = self.item_data.get('schema_name', 'public')
            
            if obj_type == 'table':
                # Simplified DDL fetch
                cursor.execute("SELECT pg_get_tabledef(%s, %s)", (schema_name, self.obj_name))
                res = cursor.fetchone()
                if res:
                    self.sql_display.setText(res[0])
            elif obj_type == 'schema':
                self.sql_display.setText(f"CREATE SCHEMA {self.obj_name};")
            
        except Exception as e:
            self.sql_display.setText(f"-- Error loading properties: {e}")
        finally:
            if conn:
                conn.close()

    def _load_sqlite_data(self):
        # Simplified SQLite DDL
        try:
            db_path = self.item_data.get('conn_data', {}).get('db_path')
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE name = ?", (self.obj_name,))
            res = cursor.fetchone()
            if res:
                self.sql_display.setText(res[0])
            conn.close()
        except Exception as e:
            self.sql_display.setText(f"-- Error: {e}")
