# dialogs/csv_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QLabel, QApplication
)
from PySide6.QtCore import Qt
import db


class CSVDataSourceDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)

        self.conn_data = conn_data
        is_editing = conn_data is not None

        self.setWindowTitle(
            "Edit New Data Source" if is_editing else "New Data Source"
        )
        self.setFixedSize(560, 340)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        header_title = QLabel("CSV Data Source")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Import and query CSV files as virtual tables."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        main_layout.addWidget(header_title)
        main_layout.addWidget(header_subtitle)

        # Form
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        # Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Sales Data CSV")
        form_layout.addRow("Connection Name:", self.name_input)

        # Short name
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("e.g., sales_csv")
        form_layout.addRow("Short Name:", self.short_name_input)

        # Path
        path_container = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to folder containing CSV files")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_csv)

        path_container.addWidget(self.path_input)
        path_container.addWidget(browse_btn)

        form_layout.addRow("CSV Folder Path:", path_container)

        main_layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.save_btn)

        main_layout.addLayout(button_layout)

        # Fill edit data
        if is_editing:
            self.name_input.setText(conn_data.get("name", ""))
            self.short_name_input.setText(conn_data.get("short_name", ""))
            self.path_input.setText(conn_data.get("db_path", ""))

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

    # ---------------- Actions ----------------

    def _browse_csv(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select CSV Folder"
        )
        if folder_path:
            self.path_input.setText(folder_path)

    def _test_connection(self):
        path = self.path_input.text().strip()

        if not path:
            QMessageBox.warning(self, "Validation", "Please select a CSV folder.")
            return

        try:
            conn = db.create_csv_connection({
                "db_path": path
            })

            if conn:
                QMessageBox.information(self, "Success", "Connection successful!")
                conn.close()
            else:
                QMessageBox.critical(self, "Error", "Failed to connect to CSV.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")

    def _on_save(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return

        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please select a CSV folder.")
            return

        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "db_path": self.path_input.text().strip(),
            "code": "CSV"
        }