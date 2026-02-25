
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt

class CSVConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit CSV Connection" if conn_data else "New CSV Connection")
        self.resize(560, 340)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self._apply_styles()
        self.conn_data = conn_data

        header_title = QLabel("CSV Folder Connection")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Choose the folder location that contains your CSV files.")
        header_subtitle.setObjectName("dialogSubtitle")

        # main outlet
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        # 1. Name Input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Connection Name (e.g. Sales Data)")
        form_layout.addRow("Name:", self.name_input)

        # 2. Short Name Input 
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("Short identifier (e.g. Sales_CSV)")
        form_layout.addRow("Short Name:", self.short_name_input)

        # 3. Location Input (Folder Path)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select the folder containing CSV files")
        
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.clicked.connect(self.browse_folder)


        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        form_layout.addRow("Location:", path_layout)

        self.save_btn = QPushButton("Update" if self.conn_data else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.validate_and_accept)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(form_layout)
        layout.addLayout(button_layout)

        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))
# {mitayan}
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
# {mitayan}
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Location")
        if folder:
            self.path_input.setText(folder)

    def validate_and_accept(self):
        # 
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Connection Name is required.")
            return
        if not self.short_name_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Short Name is required.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Location path is required.")
            return
        
        self.accept()

    def getData(self):
       
        return {
            "id": self.conn_data.get("id") if self.conn_data else None,
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(), 
            "db_path": self.path_input.text().strip(),
            "code": "CSV"
            # "host": None, 
            # "port": None, 
            # "database": None, 
            # "user": None, 
            # "password": None,
            # "dsn": None
        }