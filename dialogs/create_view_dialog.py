from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QLabel, QPlainTextEdit, QDialogButtonBox, 
    QMessageBox
)
from PyQt6.QtGui import QFont

class CreateViewDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create View ({db_type})")
        self.resize(600, 500)
        self.db_type = db_type
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_input = QLineEdit()
        self.schema_combo = QComboBox()
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        gen_layout.addRow("Name:", self.name_input)
        if self.db_type == 'postgres':
            gen_layout.addRow("Schema:", self.schema_combo)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Definition (SQL query) ---
        self.definition_tab = QWidget()
        def_layout = QVBoxLayout(self.definition_tab)
        
        def_layout.addWidget(QLabel("View Definition (SQL SELECT statement):"))
        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("SELECT * FROM some_table ...")
        # Set a monospace font for the editor
        font = QFont("Consolas", 10)
        if not font.fixedPitch():
            font = QFont("Courier New", 10)
        self.sql_editor.setFont(font)
        
        def_layout.addWidget(self.sql_editor)
        self.tabs.addTab(self.definition_tab, "Definition")

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "View Name is required!")
            return
        if not self.sql_editor.toPlainText().strip():
            QMessageBox.warning(self, "Error", "SQL Definition is required!")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "sql": self.sql_editor.toPlainText().strip()
        }
