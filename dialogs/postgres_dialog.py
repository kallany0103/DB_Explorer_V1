# dialogs/postgres_dialog.py

import psycopg2
from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

class PostgresConnectionDialog(QDialog):
    def __init__(self, parent=None, is_editing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit PostgreSQL Connection" if is_editing else "New PostgreSQL Connection")
        # Set default initial size (optional)
        self.resize(500, 300)
        
        # make dialog resizable
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.db_input = QLineEdit()
        self.user_input = QLineEdit()

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Database:", self.db_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self.testConnection)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def testConnection(self):
        try:
            conn = psycopg2.connect(
                host=self.host_input.text(),
                port=int(self.port_input.text()),
                database=self.db_input.text(),
                user=self.user_input.text(),
                password=self.password_input.text()
            )
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Connection name is required.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "host": self.host_input.text(),
            "port": self.port_input.text(),
            "database": self.db_input.text(),
            "user": self.user_input.text(),
            "password": self.password_input.text()
        }