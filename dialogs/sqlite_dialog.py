# dialogs/sqlite_dialog.py

import sqlite3 as sqlite
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QLabel, QComboBox, QInputDialog, QWidget
)
from PySide6.QtCore import Qt
import db
from db.db_retrieval import get_groups_by_type

class SQLiteConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None, type_id=None, group_id=None):
        super().__init__(parent)
        self.conn_data = conn_data
        self.type_id = type_id
        self.group_id = group_id
        is_editing = self.conn_data is not None

        self.setWindowTitle("Edit SQLite Connection" if is_editing else "New SQLite Connection")
        self.setFixedSize(560, 420)
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        header_title = QLabel("SQLite Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Configure connection details for your local database.")
        header_subtitle.setObjectName("dialogSubtitle")

        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.path_input = QLineEdit()
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.browse_file)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

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
            self.setFixedSize(560, 360) # Compact height when group is hidden
            
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Database Path:", path_layout)

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

        if is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))

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

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select SQLite Database", "", "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*)")
        if file_path:
            self.path_input.setText(file_path)

    def testConnection(self):
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

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Connection name is required.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Database path is required.")
            return
        if self.group_combo.currentIndex() == -1:
            QMessageBox.warning(self, "Missing Info", "Please select or create a group.")
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