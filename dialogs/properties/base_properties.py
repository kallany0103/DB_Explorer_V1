# dialogs/properties/base_properties.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QHBoxLayout, 
    QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt
import db
from ui.components import PrimaryButton, SecondaryButton

class BasePropertiesDialog(QDialog):
    def __init__(self, item_data, object_name, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.object_name = object_name
        self.conn_data = self.item_data.get('conn_data')
        self.db_type = self.item_data.get('db_type')
        self.schema_name = self.item_data.get('schema_name')

        self.setWindowTitle(f"Properties - {self.object_name}")
        self.setMinimumSize(850, 600)
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = PrimaryButton("OK")
        save_btn.clicked.connect(self.save_properties)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        self.main_layout.addLayout(btn_layout)

    def init_tabs(self):
        """To be implemented by subclasses."""
        pass

    def load_data(self):
        """To be implemented by subclasses. Should use a single connection."""
        pass

    def save_properties(self):
        """To be implemented by subclasses."""
        self.accept()

    def get_connection(self):
        """Returns a database connection based on db_type."""
        if self.db_type == 'postgres':
            pg_conn_data = {key: self.conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
            return db.create_postgres_connection(**pg_conn_data)
        elif self.db_type == 'sqlite':
            return db.create_sqlite_connection(self.conn_data.get('db_path'))
        return None

    def _create_sql_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.sql_display = QTextEdit()
        self.sql_display.setReadOnly(True)
        # Apply monospace font for SQL
        self.sql_display.setStyleSheet("font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 10pt;")
        layout.addWidget(self.sql_display)
        return widget
