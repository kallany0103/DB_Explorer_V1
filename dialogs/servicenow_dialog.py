# dialogs/servicenow_dialog.py
import os
from PySide6.QtWidgets import QLineEdit, QMessageBox, QApplication
from ui.components import PasswordBox
from dialogs.base_connection_dialog import BaseConnectionDialog
import db

class ServiceNowConnectionDialog(BaseConnectionDialog):
    def __init__(self, parent=None, conn_data=None, type_id=None, group_id=None):
        super().__init__(
            parent=parent, 
            conn_data=conn_data,
            type_id=type_id, 
            group_id=group_id, 
            title="ServiceNow", 
            subtitle="Import data from ServiceNow by URL and User.",
            fixed_size=(560, 480)
        )

    def setup_inputs(self):
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.instance_url_input = QLineEdit()
        self.instance_url_input.setPlaceholderText("e.g. https://dev12345.service-now.com")

        self.user_input = QLineEdit()
        self.password_input = PasswordBox()

        self.form.addRow("Connection Name:", self.name_input)
        self.form.addRow("Short Name:", self.short_name_input)
        self.form.addRow("Instance URL:", self.instance_url_input)
        self.form.addRow("User:", self.user_input)
        self.form.addRow("Password:", self.password_input)
        
        if not (self.is_editing or not self.group_id):
            self.setFixedSize(560, 420)

        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.instance_url_input.setText(self.conn_data.get("instance_url", ""))
            self.user_input.setText(self.conn_data.get("user", ""))
            self.password_input.setText(self.conn_data.get("password", ""))

    def test_connection_impl(self):
        conn_data = self.getData()
        if not conn_data.get("instance_url"):
            QMessageBox.warning(self, "Validation", "Please provide an instance URL.")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        QApplication.processEvents()

        try:
            conn = db.create_servicenow_connection(conn_data)
            if conn:
                QMessageBox.information(self, "Success", "Connection successful!")
                conn.close()
            else:
                # Capture the potential error if possible, but create_servicenow_connection returns None
                QMessageBox.critical(self, "Error", "Failed to connect to ServiceNow. Please check your credentials and instance URL.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")

    def save_connection_impl(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return
        if not self.instance_url_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide an instance URL.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "instance_url": self.instance_url_input.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "connection_group_id": self.group_combo.currentData(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }
