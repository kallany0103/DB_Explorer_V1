# dialogs/servicenow_dialog.py

import os
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout,
    QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon


class ServiceNowDataSourceDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)

        self.conn_data = conn_data
        is_editing = conn_data is not None

        self.setWindowTitle(
            "Edit New Data Source" if is_editing else "New Data Source"
        )
        self.setFixedSize(560, 420)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        # Header
        header_title = QLabel("Configure ServiceNow connection")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Import data from ServiceNow by URL and user credentials."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        # Inputs
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()

        self.instance_url_input = QLineEdit()
        self.instance_url_input.setPlaceholderText(
            "e.g. https://dev12345.service-now.com"
        )

        self.user_input = QLineEdit()

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_password_toggle(self.password_input)

        # Form rows
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Instance URL:", self.instance_url_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Fill edit data
        if is_editing:
            self.name_input.setText(conn_data.get("name", ""))
            self.short_name_input.setText(conn_data.get("short_name", ""))
            self.instance_url_input.setText(conn_data.get("instance_url", ""))
            self.user_input.setText(conn_data.get("user", ""))
            self.password_input.setText(conn_data.get("password", ""))

    # ---------------- UI ----------------

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f6f8fb; }

            QLabel#dialogTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
            }

            QLabel#dialogSubtitle {
                color: #6b7280;
                margin-bottom: 8px;
            }

            QLineEdit {
                min-height: 30px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                background: white;
            }

            QLineEdit:focus {
                border: 1px solid #0078d4;
            }

            QPushButton {
                min-height: 32px;
                padding: 4px 14px;
                border-radius: 6px;
                background-color: #eef1f6;
                border: 1px solid #c4c9d4;
            }

            QPushButton#primaryButton {
                background-color: #0078d4;
                color: white;
                font-weight: 600;
            }
        """)

    # ---------------- Password toggle ----------------

    def _setup_password_toggle(self, password_field):
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

        self._eye_icon = QIcon(os.path.join(assets_dir, "eye.svg"))
        self._eye_off_icon = QIcon(os.path.join(assets_dir, "eye-off.svg"))

        self._password_visible = False

        self._password_action = password_field.addAction(
            self._eye_icon,
            QLineEdit.ActionPosition.TrailingPosition
        )

        self._password_action.triggered.connect(self._toggle_password_visibility)

    def _toggle_password_visibility(self):
        self._password_visible = not self._password_visible
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if self._password_visible
            else QLineEdit.EchoMode.Password
        )

        self._password_action.setIcon(
            self._eye_off_icon if self._password_visible else self._eye_icon
        )

    # ---------------- Actions ----------------

    def _test_connection(self):
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
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to connect to ServiceNow."
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")

    def _on_save(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return

        if not self.instance_url_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide an instance URL.")
            return

        self.accept()

    # ---------------- Data ----------------

    def getData(self):
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "instance_url": self.instance_url_input.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }