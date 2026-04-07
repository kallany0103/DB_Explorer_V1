# dialogs/oracle_dialog.py

import os
import oracledb
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout, QMessageBox, QLabel, QComboBox, QInputDialog, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import db
from db.db_retrieval import get_groups_by_type

class OracleConnectionDialog(QDialog):
    def __init__(self, parent=None, is_editing=False, type_id=None, group_id=None):
        super().__init__(parent)
        self.type_id = type_id
        self.group_id = group_id
        self.setWindowTitle("Edit Oracle Connection" if is_editing else "New Oracle Connection")
        self.setFixedSize(560, 480)
        
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        header_title = QLabel("Oracle Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Configure connection using DSN (TNS or Easy Connect).")
        header_subtitle.setObjectName("dialogSubtitle")

        self.name_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_password_toggle(self.password_input)
        
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. host:port/service_name or TNS name")

        # Group Selection
        self.group_combo = QComboBox()
        self.new_group_btn = QPushButton("New Group")
        self.new_group_btn.setObjectName("secondaryButton")
        self.new_group_btn.setFixedWidth(110)
        self.new_group_btn.clicked.connect(self._create_new_group)
        
        group_layout = QHBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.addWidget(self.group_combo)
        group_layout.addWidget(self.new_group_btn)

        if self.type_id:
            self._populate_groups()

        if self.group_id:
            index = self.group_combo.findData(self.group_id)
            if index >= 0:
                self.group_combo.setCurrentIndex(index)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        
        # Show group selection if editing (to allow transfer) OR if no group was pre-selected
        self.group_row_widget = QWidget()
        self.group_row_widget.setMinimumHeight(38)
        self.group_row_layout = QHBoxLayout(self.group_row_widget)
        self.group_row_layout.setContentsMargins(0, 2, 0, 2)
        self.group_row_layout.addLayout(group_layout)
        
        form.addRow("Group:", self.group_row_widget)
        
        should_show_group = is_editing or not self.group_id
        if not should_show_group:
            self.group_row_widget.hide()
            label = form.labelForField(self.group_row_widget)
            if label:
                label.hide()
            self.setFixedSize(560, 420) # Compact height when group is hidden
        form.addRow("Connection Name:", self.name_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)
        form.addRow("DSN:", self.dsn_input)

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
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1f2937; }
            QLabel#dialogSubtitle { color: #6b7280; margin-bottom: 8px; }
            QLineEdit, QComboBox {
                min-height: 30px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding: 3px 8px;
                color: #1f2937;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox {
                padding-right: 25px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
            QPushButton {
                min-height: 32px;
                padding: 2px 14px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                color: #1f2937;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #e3e8f2; }
            QPushButton:pressed { background-color: #d7deeb; }
            QPushButton#primaryButton { border: 1px solid #006cbe; background-color: #0078d4; color: #ffffff; font-weight: 600; }
            QPushButton#primaryButton:hover { background-color: #006cbe; }
            QPushButton#primaryButton:pressed { background-color: #005a9e; }
            """
        )

    def _populate_groups(self):
        self.group_combo.clear()
        groups = get_groups_by_type(self.type_id)
        for g in groups:
            self.group_combo.addItem(g["name"], g["id"])
            
    def _create_new_group(self):
        name, ok = QInputDialog.getText(self, "New Group", "Enter group name:")
        if ok and name.strip():
            try:
                db.add_connection_group(name.strip(), self.type_id)
                self._populate_groups()
                index = self.group_combo.findText(name.strip())
                if index >= 0:
                    self.group_combo.setCurrentIndex(index)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create group: {e}")

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
        if self.group_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
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