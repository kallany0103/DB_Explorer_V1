# dialogs/sqlite_dialog.py

import sqlite3 as sqlite
from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QFileDialog, QMessageBox
from ui.components import SecondaryButton
from dialogs.base_connection_dialog import BaseConnectionDialog

class SQLiteConnectionDialog(BaseConnectionDialog):
    def __init__(self, parent=None, conn_data=None, type_id=None, group_id=None):
        super().__init__(
            parent=parent, 
            conn_data=conn_data,
            type_id=type_id, 
            group_id=group_id, 
            title="SQLite", 
            subtitle="Configure connection details for your local database.",
            fixed_size=(560, 420)
        )

    def setup_inputs(self):

        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.path_input = QLineEdit()
        self.browse_btn = SecondaryButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.browse_file)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        self.form.addRow("Connection Name:", self.name_input)
        self.form.addRow("Short Name:", self.short_name_input)
        self.form.addRow("Database Path:", path_layout)
        
        if not (self.is_editing or not self.group_id):
            self.setFixedSize(560, 360)

        if self.is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))




    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select SQLite Database", "", "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*)")
        if file_path:
            self.path_input.setText(file_path)

    def test_connection_impl(self):
        path = self.path_input.text()
        if not path:
            QMessageBox.warning(self, "Test", "Please provide a database path.")
            return
        try:
            conn = sqlite.connect(path)
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def save_connection_impl(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Connection name is required.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Database path is required.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "db_path": self.path_input.text(),
            "connection_group_id": self.group_combo.currentData(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }