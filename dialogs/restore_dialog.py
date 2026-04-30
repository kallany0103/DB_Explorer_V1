# dialogs/restore_dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, 
    QLabel, QComboBox, QCheckBox, QTabWidget, QWidget
)
from PySide6.QtCore import Qt

class RestoreDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.item_data = item_data or {}
        self.db_type = self.item_data.get("db_type", "postgres")
        self.display_name = self.item_data.get("table_name") or self.item_data.get("schema_name") or self.item_data.get("database") or "restore"
        
        self.setWindowTitle(f"Restore - {self.display_name}")
        self.setMinimumWidth(550)
        self.resize(600, 450)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- General Tab ---
        general_tab = QWidget()
        self.tabs.addTab(general_tab, "General")
        general_layout = QFormLayout(general_tab)
        
        # Input File
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Select a backup file...")
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.filename_edit)
        file_layout.addWidget(browse_btn)
        general_layout.addRow("Filename:", file_layout)
        
        # Target Database (if opened from Group)
        self.target_db_combo = None
        connections = self.item_data.get("connections", [])
        if connections:
            self.target_db_combo = QComboBox()
            for conn in connections:
                # Store the whole conn_data in itemData
                self.target_db_combo.addItem(conn.get("short_name", "Unknown"), conn)
            general_layout.addRow("Target Database:", self.target_db_combo)
        
        # Format (Postgres Specific)
        if self.db_type == "postgres":
            self.format_combo = QComboBox()
            self.format_combo.addItems(["Custom", "Tar", "Directory"]) # pg_restore doesn't handle plain SQL files (those are piped to psql)
            self.format_combo.setCurrentText("Custom")
            general_layout.addRow("Format:", self.format_combo)
            
            self.role_edit = QLineEdit()
            general_layout.addRow("Role Name:", self.role_edit)
        
        # --- Options Tab ---
        options_tab = QWidget()
        self.tabs.addTab(options_tab, "Options")
        options_layout = QFormLayout(options_tab)
        
        if self.db_type == "postgres":
            # Type of objects
            self.content_combo = QComboBox()
            self.content_combo.addItems(["Only Data", "Only Schema", "Both"])
            self.content_combo.setCurrentText("Both")
            options_layout.addRow("Type of objects:", self.content_combo)
            
            self.no_owner_check = QCheckBox("Don't save owner")
            self.no_privs_check = QCheckBox("Don't save privileges")
            self.clean_check = QCheckBox("Clean (Drop objects before restoring)")
            self.exit_error_check = QCheckBox("Exit on error")
            
            options_layout.addRow("", self.no_owner_check)
            options_layout.addRow("", self.no_privs_check)
            options_layout.addRow("", self.clean_check)
            options_layout.addRow("", self.exit_error_check)
            
        elif self.db_type == "sqlite":
            options_layout.addRow(QLabel("SQLite restore replaces the current file."))
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def browse_file(self):
        file_filter = "Backup Files (*.backup *.sql *.tar);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select Backup File", self.filename_edit.text(), file_filter)
        if path:
            self.filename_edit.setText(path)

    def handle_accept(self):
        path = self.filename_edit.text().strip()
        if not path:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No File", "Please select a backup file to restore.")
            return
        if not os.path.exists(path):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "File Not Found", f"The selected file does not exist:\n{path}")
            return
        self.accept()

    def get_options(self):
        opts = {
            "filename": self.filename_edit.text(),
            "db_type": self.db_type,
        }
        
        if self.target_db_combo:
            index = self.target_db_combo.currentIndex()
            if index >= 0:
                opts["target_conn_data"] = self.target_db_combo.itemData(index)
        
        if self.db_type == "postgres":
            opts.update({
                "format": self.format_combo.currentText().lower(),
                "role": self.role_edit.text().strip(),
                "content": self.content_combo.currentText(),
                "no_owner": self.no_owner_check.isChecked(),
                "no_privileges": self.no_privs_check.isChecked(),
                "clean": self.clean_check.isChecked(),
                "exit_on_error": self.exit_error_check.isChecked(),
            })
            
        return opts
