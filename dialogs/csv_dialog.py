
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QPushButton, QHBoxLayout, QFileDialog, QMessageBox
)

class CSVConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)
        self.setWindowTitle("CSV Connection")
        self.setMinimumWidth(450)
        self.conn_data = conn_data

        # মেইন লেআউট
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # 1. Name Input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Connection Name (e.g. Sales Data)")
        form_layout.addRow("Name:", self.name_input)

        # 2. Short Name Input (আপনার রিকোয়ারমেন্ট অনুযায়ী যোগ করা হলো)
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("Short identifier (e.g. Sales_CSV)")
        form_layout.addRow("Short Name:", self.short_name_input)

        # 3. Location Input (Folder Path)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select the folder containing CSV files")
        
        # ব্রাউজ বাটন
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)

        # পাথ ইনপুট এবং ব্রাউজ বাটন একসাথে রাখার জন্য লেআউট
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        # লেবেলের নাম 'Location' দেওয়া হলো
        form_layout.addRow("Location:", path_layout)

        # বাটন বক্স (OK / Cancel)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)

        # লেআউটে ফর্ম এবং বাটন যোগ করা
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

        # এডিট মোড হলে আগের ডাটা লোড করা
        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.path_input.setText(self.conn_data.get("db_path", ""))

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Location")
        if folder:
            self.path_input.setText(folder)

    def validate_and_accept(self):
        # ভ্যালিডেশন
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
        """
        রিটার্ন করা ডাটা অবজেক্টে এখন ইউজার দেওয়া Short Name থাকবে।
        """
        return {
            "id": self.conn_data.get("id") if self.conn_data else None,
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(), # ইনপুট থেকে নেওয়া হচ্ছে
            "db_path": self.path_input.text().strip(), # লোকেশন
            "code": "CSV",
            # বাকি ফিল্ডগুলো নাল
            "host": None, 
            "port": None, 
            "database": None, 
            "user": None, 
            "password": None,
            "dsn": None
        }