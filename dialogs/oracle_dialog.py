# db_explorer/dialogs/oracle_dialog.py

import os
import oracledb
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

class OracleConnectionDialog(QDialog):
    def __init__(self, parent=None, is_editing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit Oracle Connection" if is_editing else "New Oracle Connection")
        self.resize(560, 340)
        
        self.setSizeGripEnabled(True)
        self.setFixedSize(560, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowSystemMenuHint)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        header_title = QLabel("Oracle Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Use DSN format host:port/service_name.")
        header_subtitle.setObjectName("dialogSubtitle")
        
        self.name_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_password_toggle(self.password_input)
        
        # DSN (Data Source Name) is typically host:port/service_name
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g., localhost:1521/XEPDB1")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.addRow("Connection Name:", self.name_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)
        form.addRow("DSN (Host/Port/Service):", self.dsn_input)

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

        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addLayout(form)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f6f8fb;
            }
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
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding: 3px 8px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                min-height: 28px;
                padding: 2px 14px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton:pressed {
                background-color: #d7deeb;
            }
            QPushButton#primaryButton {
                border: 1px solid #006cbe;
                background-color: #0078d4;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #006cbe;
            }
            QPushButton#primaryButton:pressed {
                background-color: #005a9e;
            }
            """
        )

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
            QLineEdit.EchoMode.Normal if self._password_visible else QLineEdit.EchoMode.Password
        )
        self._password_action.setIcon(self._eye_off_icon if self._password_visible else self._eye_icon)

    def testConnection(self):
        user = self.user_input.text()
        pwd = self.password_input.text()
        dsn = self.dsn_input.text()

        if not all([user, pwd, dsn]):
            QMessageBox.warning(self, "Missing Info", "User, Password, and DSN are required.")
            return
            
        try:
            conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Connection name is required.")
            return
        if not all([self.user_input.text(), self.password_input.text(), self.dsn_input.text()]):
            QMessageBox.warning(self, "Missing Info", "User, Password, and DSN are required.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "dsn": self.dsn_input.text()
        }