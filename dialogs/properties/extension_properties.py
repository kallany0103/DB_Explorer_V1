# dialogs/properties/extension_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QMessageBox
)
from .base_properties import BasePropertiesDialog
from . import pg_queries

class ExtensionPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, ext_name, parent=None):
        super().__init__(item_data, ext_name, parent)
        self.ext_name = ext_name
        self.setWindowTitle(f"Extension Properties - {self.ext_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.ext_name)
        self.owner_combo = QComboBox()
        self.version_edit = QLineEdit()
        self.version_edit.setReadOnly(True)
        self.schema_edit = QLineEdit()
        self.schema_edit.setReadOnly(True)
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(100)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Version:", self.version_edit)
        gen_layout.addRow("Schema:", self.schema_edit)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        if self.db_type != 'postgres':
            return

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Fetch Details
            cursor.execute(pg_queries.GET_EXTENSION_DETAILS, (self.ext_name,))
            res = cursor.fetchone()
            if res:
                name, version, schema, owner, comment = res
                self.version_edit.setText(version)
                self.schema_edit.setText(schema)
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner

            # Fetch roles
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Generate SQL
            self._generate_sql()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load extension properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self):
        sql = f"-- Extension: {self.ext_name}\n\n"
        sql += f"CREATE EXTENSION IF NOT EXISTS {self.ext_name}\n"
        sql += f"    SCHEMA {self.schema_edit.text()}\n"
        sql += f"    VERSION \"{self.version_edit.text()}\";\n"
        
        if self.comment_edit.toPlainText().strip():
            comment = self.comment_edit.toPlainText().strip().replace("'", "''")
            sql += f"\nCOMMENT ON EXTENSION {self.ext_name} IS '{comment}';"
            
        self.sql_display.setText(sql)

    def save_properties(self):
        self.accept()
