# dialogs/servicenow_dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout,
    QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QComboBox, QInputDialog, QWidget, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import db
from db.db_retrieval import get_groups_by_type


class ServiceNowConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None, type_id=None, group_id=None):
        super().__init__(parent)
        self.conn_data = conn_data
        self.type_id = type_id
        self.group_id = group_id
        is_editing = self.conn_data is not None

        self.setWindowTitle(
            "Edit ServiceNow Connection" if is_editing else "New ServiceNow Connection"
        )
        self.setFixedSize(560, 480) # Increased height
        self.setSizeGripEnabled(True)

        self._init_ui()

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

    def _init_ui(self):
        self._apply_styles()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        header_title = QLabel("ServiceNow Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Import data from ServiceNow by URL and User.")
        header_subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

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

        # Show group selection if editing (to allow transfer) OR if no group was pre-selected
        self.group_row_widget = QWidget()
        self.group_row_widget.setMinimumHeight(42)
        self.group_row_layout = QHBoxLayout(self.group_row_widget)
        self.group_row_layout.setContentsMargins(0, 2, 0, 2)
        self.group_row_layout.addLayout(group_layout)
        
        form.addRow("Group:", self.group_row_widget)
        
        is_editing = self.conn_data is not None
        should_show_group = is_editing or not self.group_id
        if not should_show_group:
            self.group_row_widget.hide()
            label = form.labelForField(self.group_row_widget)
            if label:
                label.hide()
            self.setFixedSize(560, 420) # Compact height when group is hidden

        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.instance_url_input = QLineEdit()
        self.instance_url_input.setPlaceholderText("e.g. https://dev12345.service-now.com")

        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_password_toggle(self.password_input)

        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Instance URL:", self.instance_url_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)
        layout.addLayout(form)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Update" if self.conn_data else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        layout.addLayout(button_layout)

        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.instance_url_input.setText(self.conn_data.get("instance_url", ""))
            self.user_input.setText(self.conn_data.get("user", ""))
            self.password_input.setText(self.conn_data.get("password", ""))

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
                # Capture the potential error if possible, but create_servicenow_connection returns None
                QMessageBox.critical(self, "Error", "Failed to connect to ServiceNow. Please check your credentials and instance URL.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")
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
        if self.group_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
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
