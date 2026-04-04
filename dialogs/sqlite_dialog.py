# dialogs/sqlite_dialog.py

import sqlite3 as sqlite
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QLabel
)
from PySide6.QtCore import Qt

class SQLiteConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)
        self.conn_data = conn_data
        is_editing = self.conn_data is not None

        self.setWindowTitle("Edit SQLite Connection" if is_editing else "New SQLite Connection")
        self.resize(560, 360)
        
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

        header_title = QLabel("SQLite Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Select an existing database file or create a new one.")
        header_subtitle.setObjectName("dialogSubtitle")
        
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.path_input = QLineEdit()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Database Path:", self.path_input)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self.browseFile)

        self.create_btn = QPushButton("Create New DB")
        self.create_btn.setObjectName("secondaryButton")
        self.create_btn.clicked.connect(self.createNewDatabase)
        # Hide the create button if editing existing connection
        if is_editing:
            self.create_btn.hide()

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.browse_btn)
        path_layout.addWidget(self.create_btn)
        form.addRow("", path_layout)

        if is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.saveConnection)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
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

    def browseFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SQLite DB", "", "SQLite Database (*.db *.sqlite *.sqlite3)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def createNewDatabase(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New SQLite DB", "", "SQLite Database (*.db *.sqlite *.sqlite3)"
        )
        if file_path:
            try:
                conn = sqlite.connect(file_path)
                conn.close()
                self.path_input.setText(file_path)
                QMessageBox.information(
                    self, "Success", f"Database created successfully at:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create database:\n{e}")

    def saveConnection(self):
        if not self.name_input.text().strip() or not self.short_name_input.text().strip() or not self.path_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Both fields are required.")
            return
        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "db_path": self.path_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }