# dialogs/properties/language_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QMessageBox, QCheckBox
)
from .base_properties import BasePropertiesDialog
from . import pg_queries

class LanguagePropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, lan_name, parent=None):
        super().__init__(item_data, lan_name, parent)
        self.lan_name = lan_name
        self.setWindowTitle(f"Language Properties - {self.lan_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.lan_name)
        self.owner_combo = QComboBox()
        self.is_pl_check = QCheckBox("Procedural Language")
        self.is_pl_check.setEnabled(False)
        self.is_trusted_check = QCheckBox("Trusted")
        self.is_trusted_check.setEnabled(False)
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(100)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("", self.is_pl_check)
        gen_layout.addRow("", self.is_trusted_check)
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
            cursor.execute(pg_queries.GET_LANGUAGE_DETAILS, (self.lan_name,))
            res = cursor.fetchone()
            if res:
                name, owner, is_pl, is_trusted, comment = res
                self.is_pl_check.setChecked(bool(is_pl))
                self.is_trusted_check.setChecked(bool(is_trusted))
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
            QMessageBox.critical(self, "Error", f"Failed to load language properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self):
        sql = f"-- Language: {self.lan_name}\n\n"
        sql += f"CREATE OR REPLACE LANGUAGE {self.lan_name};\n"
        
        if hasattr(self, 'original_owner'):
            sql += f"\nALTER LANGUAGE {self.lan_name} OWNER TO {self.owner_combo.currentText()};"
            
        if self.comment_edit.toPlainText().strip():
            comment = self.comment_edit.toPlainText().strip().replace("'", "''")
            sql += f"\nCOMMENT ON LANGUAGE {self.lan_name} IS '{comment}';"
            
        self.sql_display.setText(sql)

    def save_properties(self):
        self.accept()
