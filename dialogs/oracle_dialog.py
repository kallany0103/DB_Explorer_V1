# dialogs/oracle_dialog.py

import os
import oracledb
from PySide6.QtWidgets import QLineEdit, QMessageBox
from ui.components import PasswordBox
from dialogs.base_connection_dialog import BaseConnectionDialog
import oracledb

class OracleConnectionDialog(BaseConnectionDialog):
    def __init__(self, parent=None, is_editing=False, type_id=None, group_id=None):
        super().__init__(
            parent=parent, 
            is_editing=is_editing, 
            type_id=type_id, 
            group_id=group_id, 
            title="Oracle", 
            subtitle="Configure connection using DSN (TNS or Easy Connect).",
            fixed_size=(560, 480)
        )
    def setup_inputs(self):
        self.name_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. host:port/service_name or TNS name")

        self.form.addRow("Connection Name:", self.name_input)
        self.form.addRow("User:", self.user_input)
        self.form.addRow("Password:", self.password_input)
        self.form.addRow("DSN:", self.dsn_input)
        
        if not (self.is_editing or not self.group_id):
            self.setFixedSize(560, 420)

    def test_connection_impl(self):
        try:
            conn = oracledb.connect(
                user=self.user_input.text(),
                password=self.password_input.text(),
                dsn=self.dsn_input.text()
            )
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def save_connection_impl(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "dsn": self.dsn_input.text(),
            "connection_group_id": self.group_combo.currentData()
        }