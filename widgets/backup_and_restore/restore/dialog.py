# widgets/backup_and_restore/restore/dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, 
    QLabel, QComboBox, QCheckBox, QTabWidget, QWidget,
    QFrame, QGroupBox
)
from PySide6.QtCore import Qt, QSize
import qtawesome as qta

class RestoreDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.item_data = item_data or {}
        self.db_type = self.item_data.get("db_type", "postgres")
        self.display_name = self.item_data.get("table_name") or self.item_data.get("schema_name") or self.item_data.get("database") or "restore"
        
        self.setWindowTitle(f"Restore - {self.display_name}")
        self.setMinimumWidth(600)
        self.resize(650, 500)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- 1. General Tab ---
        general_tab = QWidget()
        self.tabs.addTab(general_tab, qta.icon("fa5s.file-alt", color="#555"), "General")
        general_layout = QFormLayout(general_tab)
        general_layout.setContentsMargins(15, 15, 15, 15)
        general_layout.setSpacing(10)
        
        # Filename
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("Select a backup file...")
        browse_btn = QPushButton(qta.icon("fa5s.folder-open"), "")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.filename_edit)
        file_layout.addWidget(browse_btn)
        general_layout.addRow("Filename:", file_layout)
        
        # Format
        if self.db_type == "postgres":
            self.format_combo = QComboBox()
            self.format_combo.addItems(["Custom", "Tar", "Directory"])
            self.format_combo.setCurrentText("Custom")
            general_layout.addRow("Format:", self.format_combo)
            
            self.role_edit = QLineEdit()
            general_layout.addRow("Role Name:", self.role_edit)

        # Target Database (from Group)
        self.target_db_combo = None
        connections = self.item_data.get("connections", [])
        if connections:
            self.target_db_combo = QComboBox()
            for conn in connections:
                self.target_db_combo.addItem(conn.get("short_name", "Unknown"), conn)
            general_layout.addRow("Target Database:", self.target_db_combo)

        # --- 2. Data Options Tab ---
        data_tab = QWidget()
        self.tabs.addTab(data_tab, qta.icon("fa5s.database", color="#555"), "Data Options")
        data_layout = QFormLayout(data_tab)
        data_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.content_combo = QComboBox()
            self.content_combo.addItems(["Both", "Only Data", "Only Schema"])
            data_layout.addRow("Type of objects:", self.content_combo)
            
            data_layout.addRow(QLabel("<b>Do not save:</b>"))
            self.no_owner_check = QCheckBox("Owner")
            self.no_privs_check = QCheckBox("Privileges")
            self.no_tablespaces_check = QCheckBox("Tablespaces")
            
            data_layout.addRow("", self.no_owner_check)
            data_layout.addRow("", self.no_privs_check)
            data_layout.addRow("", self.no_tablespaces_check)

        # --- 3. Query Options Tab ---
        query_tab = QWidget()
        self.tabs.addTab(query_tab, qta.icon("fa5s.terminal", color="#555"), "Query Options")
        query_layout = QFormLayout(query_tab)
        query_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.clean_check = QCheckBox("Clean (Drop objects before restoring)")
            self.single_transaction_check = QCheckBox("Single Transaction")
            self.exit_error_check = QCheckBox("Exit on error")
            
            query_layout.addRow("", self.clean_check)
            query_layout.addRow("", self.single_transaction_check)
            query_layout.addRow("", self.exit_error_check)

        # --- 4. Options Tab ---
        misc_tab = QWidget()
        self.tabs.addTab(misc_tab, qta.icon("fa5s.sliders-h", color="#555"), "Options")
        misc_layout = QFormLayout(misc_tab)
        misc_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.verbose_check = QCheckBox("Verbose messages")
            self.verbose_check.setChecked(True)
            self.no_comments_check = QCheckBox("Do not save comments")
            
            misc_layout.addRow("", self.verbose_check)
            misc_layout.addRow("", self.no_comments_check)
        elif self.db_type == "sqlite":
            misc_layout.addRow(QLabel("SQLite restore replaces the current file."))

        # Footer Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Apply Styles
        self.setStyleSheet("""
            QDialog {
                background-color: #f6f8fb;
            }
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                background: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #eef1f6;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #555;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #d1d5db;
                border-bottom: none;
                color: #1f2937;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding-left: 6px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 15px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                border-radius: 6px;
                color: #1f2937;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton[text="OK"] {
                background-color: #0078d4;
                color: white;
                border: 1px solid #006cbe;
                font-weight: bold;
            }
            QPushButton[text="OK"]:hover {
                background-color: #006cbe;
            }
        """)

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
                "no_tablespaces": self.no_tablespaces_check.isChecked(),
                "clean": self.clean_check.isChecked(),
                "single_transaction": self.single_transaction_check.isChecked(),
                "exit_on_error": self.exit_error_check.isChecked(),
                "verbose": self.verbose_check.isChecked(),
                "no_comments": self.no_comments_check.isChecked(),
            })
            
        return opts
