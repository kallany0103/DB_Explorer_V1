# dialogs/servicenow_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout,
    QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox
)
from PyQt6.QtCore import Qt


class ServiceNowConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)
        self.conn_data = conn_data
        is_editing = self.conn_data is not None

        self.setWindowTitle(
            "Edit ServiceNow Connection" if is_editing else "New ServiceNow Connection"
        )
        self.resize(500, 320)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        # -------- Inputs --------
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.instance_url_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # -------- Form Layout --------
        form = QFormLayout()
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Instance URL:", self.instance_url_input)
        form.addRow("Username:", self.user_input)
        form.addRow("Password:", self.password_input)

        # -------- Buttons --------
        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(button_layout)
        self.setLayout(layout)

        # -------- Load Existing Data --------
        if is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.instance_url_input.setText(self.conn_data.get("instance_url", ""))
            self.user_input.setText(self.conn_data.get("user", ""))
            self.password_input.setText(self.conn_data.get("password", ""))

    def saveConnection(self):
        if not all([
            self.name_input.text().strip(),
            self.short_name_input.text().strip(),
            self.instance_url_input.text().strip(),
            self.user_input.text().strip(),
            self.password_input.text().strip()
        ]):
            QMessageBox.warning(
                self,
                "Missing Info",
                "All fields are required."
            )
            return

        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "instance_url": self.instance_url_input.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }
