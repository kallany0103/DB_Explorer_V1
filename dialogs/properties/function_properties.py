# dialogs/properties/function_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QTableView, QHeaderView, QMessageBox, QLabel
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from .base_properties import BasePropertiesDialog
from . import pg_queries

class FunctionPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, func_signature, parent=None):
        super().__init__(item_data, func_signature, parent)
        self.func_signature = func_signature
        self.setWindowTitle(f"Function Properties - {self.func_signature}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.func_signature)
        self.owner_combo = QComboBox()
        self.language_edit = QLineEdit()
        self.language_edit.setReadOnly(True)
        self.return_type_edit = QLineEdit()
        self.return_type_edit.setReadOnly(True)
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(80)
        
        gen_layout.addRow("Signature:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Language:", self.language_edit)
        gen_layout.addRow("Return Type:", self.return_type_edit)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. Definition Tab
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        self.definition_display = QTextEdit()
        self.definition_display.setReadOnly(True)
        self.definition_display.setStyleSheet("font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 10pt;")
        def_layout.addWidget(self.definition_display)
        self.tab_widget.addTab(self.definition_tab, "Definition")

        # 3. Security Tab (Postgres only)
        if self.db_type == 'postgres':
            self.security_tab = QWidget()
            sec_layout = QVBoxLayout(self.security_tab)
            self.security_model = QStandardItemModel()
            self.security_model.setHorizontalHeaderLabels(["Grantee", "Privileges", "Grantor"])
            self.security_view = QTableView()
            self.security_view.setModel(self.security_model)
            self.security_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            sec_layout.addWidget(self.security_view)
            self.tab_widget.addTab(self.security_tab, "Security")

        # 4. SQL Tab
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
            cursor.execute(pg_queries.GET_FUNCTION_DETAILS, (self.schema_name, self.func_signature))
            res = cursor.fetchone()
            if res:
                owner, language, return_type, args, definition, comment = res
                self.language_edit.setText(language)
                self.return_type_edit.setText(return_type)
                self.definition_display.setPlainText(definition or "")
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner
                self.original_comment = comment or ""

            # Fetch roles
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Fetch Security
            cursor.execute(pg_queries.GET_FUNCTION_PRIVILEGES, (self.schema_name, self.func_signature))
            for row in cursor.fetchall():
                items = [QStandardItem(str(c)) for c in row]
                self.security_model.appendRow(items)

            # 3. Generate SQL
            self._generate_sql(cursor)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load function properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self, cursor):
        # Retrieve full DDL using pg_get_functiondef
        try:
            # We need the OID to use pg_get_functiondef conveniently, or cast the signature
            # Using regprocedure cast is safer
            cursor.execute("SELECT pg_get_functiondef(%s::regprocedure)", (f'"{self.schema_name}"."{self.func_signature}"',))
            res = cursor.fetchone()
            if res:
                self.sql_display.setText(res[0] + ";")
            else:
                self.sql_display.setText(f"-- Could not generate DDL for {self.func_signature}")
        except Exception as e:
            self.sql_display.setText(f"-- Error generating DDL: {e}")

    def save_properties(self):
        # For now, we only support basic metadata updates if implemented
        self.accept()
