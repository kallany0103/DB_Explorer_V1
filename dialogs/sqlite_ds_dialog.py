# dialogs/sqlite_dialog.py

import sqlite3 as sqlite
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QLabel, QWidget
)
from PySide6.QtCore import Qt


class SQLiteDataSourceDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)

        self.conn_data = conn_data
        is_editing = self.conn_data is not None

        self.setWindowTitle(
            "Edit New Data Source" if is_editing else "New Data Source"
        )
        self.setFixedSize(560, 360)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Header
        header_title = QLabel("Configure SQLite database connection")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Configure connection details for your local database."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        # Inputs
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.path_input = QLineEdit()

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setFixedWidth(90)
        self.browse_btn.clicked.connect(self.browse_file)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Database Path:", path_layout)

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

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Fill edit data
        if is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))

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

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            "",
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def testConnection(self):
        path = self.path_input.text().strip()

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

        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "db_path": self.path_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }