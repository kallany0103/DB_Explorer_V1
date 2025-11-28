# dialogs/csv_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton,
    QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
import os


class CSVConnectionDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)
        self.conn_data = conn_data
        is_editing = self.conn_data is not None

        self.setWindowTitle("Edit CSV Connection" if is_editing else "New CSV Connection")
        self.resize(500, 250)

        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)

        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.folder_input = QLineEdit()

        form = QFormLayout()
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("CSV Folder Path:", self.folder_input)

        # Choose folder only (no create CSV)
        self.folder_btn = QPushButton("Select Folder")
        self.folder_btn.clicked.connect(self.selectFolder)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.folder_btn)
        form.addRow("", path_layout)

        # Populate when editing
        if is_editing:
            self.name_input.setText(self.conn_data.get("name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name", ""))
            self.folder_input.setText(self.conn_data.get("folder_path", ""))

        # Save/Cancel buttons
        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select CSV Folder")
        if folder:
            self.folder_input.setText(folder)

    def saveConnection(self):
        name = self.name_input.text().strip()
        short = self.short_name_input.text().strip()
        folder = self.folder_input.text().strip()

        if not name or not short or not folder:
            QMessageBox.warning(self, "Missing Info", "All fields are required.")
            return

        if not os.path.isdir(folder):
            QMessageBox.warning(self, "Invalid Folder", "Folder does not exist.")
            return

        self.accept()

    def getData(self):
        return {
            "name": self.name_input.text(),
            "short_name": self.short_name_input.text(),
            "db_path": self.folder_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None
        }
