# dialogs/preferences_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, QLabel, QCheckBox
)
from PySide6.QtCore import Qt

class PreferencesDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(500)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        # Postgres Binary Path
        self.pg_bin_edit = QLineEdit()
        self.pg_bin_edit.setText(getattr(self.main_window, "pg_bin_path", ""))
        self.pg_bin_edit.setPlaceholderText("Path to PostgreSQL bin directory (e.g. C:\\Program Files\\PostgreSQL\\15\\bin)")
        
        pg_bin_btn = QPushButton("Browse...")
        pg_bin_btn.clicked.connect(self.browse_pg_bin)
        
        pg_bin_layout = QHBoxLayout()
        pg_bin_layout.addWidget(self.pg_bin_edit)
        pg_bin_layout.addWidget(pg_bin_btn)
        
        form_layout.addRow("PostgreSQL Binary Path:", pg_bin_layout)
        
        # Help text
        help_label = QLabel("Specify the directory containing pg_dump and pg_restore.")
        help_label.setStyleSheet("color: gray; font-size: 8pt;")
        form_layout.addRow("", help_label)
        
        # Use WSL
        self.use_wsl_check = QCheckBox("Use WSL for PostgreSQL tools")
        self.use_wsl_check.setChecked(getattr(self.main_window, "use_wsl", False))
        form_layout.addRow("", self.use_wsl_check)
        
        wsl_help = QLabel("Check this if your Postgres tools are installed in Linux (WSL).")
        wsl_help.setStyleSheet("color: gray; font-size: 8pt;")
        form_layout.addRow("", wsl_help)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def browse_pg_bin(self):
        directory = QFileDialog.getExistingDirectory(self, "Select PostgreSQL Bin Directory", self.pg_bin_edit.text())
        if directory:
            self.pg_bin_edit.setText(directory)

    def get_settings(self):
        return {
            "pg_bin_path": self.pg_bin_edit.text().strip(),
            "use_wsl": self.use_wsl_check.isChecked()
        }
