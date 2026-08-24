import os
import oracledb
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel
)
from PySide6.QtCore import Qt
from ui.components import PasswordBox


class OracleDataSourceDialog(QDialog):
    def __init__(self, parent=None, is_editing=False, conn_data=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Edit New Data Source" if is_editing else "New Data Source"
        )
        self.setFixedSize(560, 420)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Header
        header_title = QLabel("Configure Oracle database connection")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Configure connection using DSN (TNS or Easy Connect)."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        # Inputs
        self.name_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()

        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText(
            "e.g. host:port/service_name or TNS name"
        )

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        form.addRow("Connection Name:", self.name_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)
        form.addRow("DSN:", self.dsn_input)

        # Buttons
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self.testConnection)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addLayout(form)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        if conn_data:
            self.name_input.setText(conn_data.get("name", ""))
            self.user_input.setText(conn_data.get("user", ""))
            self.password_input.setText(conn_data.get("password", ""))
            self.dsn_input.setText(conn_data.get("dsn", ""))

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

    def testConnection(self):
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

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return

        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "dsn": self.dsn_input.text()
        }