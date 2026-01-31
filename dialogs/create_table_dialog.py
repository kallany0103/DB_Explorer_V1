from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QTextEdit, QTableWidget, QHeaderView, 
    QAbstractItemView, QHBoxLayout, QPushButton, QDialogButtonBox, 
    QTableWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt

class CreateTableDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create Table ({db_type})")
        self.resize(600, 450)
        self.db_type = db_type
        
        # Layouts
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Owner, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_input = QLineEdit()
        self.owner_input = QLineEdit(current_user) # Default to current user
        self.schema_combo = QComboBox()
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        self.comment_input = QTextEdit()
        self.comment_input.setMaximumHeight(60)

        gen_layout.addRow("Name:", self.name_input)
        
        # Hide Owner and Schema for SQLite as they aren't typically used/needed for simple creation
        if self.db_type == 'postgres':
            gen_layout.addRow("Owner:", self.owner_input)
            gen_layout.addRow("Schema:", self.schema_combo)
        
        gen_layout.addRow("Comment:", self.comment_input)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Columns (Simple Column Editor) ---
        self.columns_tab = QWidget()
        col_layout = QVBoxLayout(self.columns_tab)
        
        self.col_table = QTableWidget(0, 3) # Rows, Cols
        self.col_table.setHorizontalHeaderLabels(["Name", "Data Type", "Primary Key?"])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.col_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Buttons for columns
        btn_layout = QHBoxLayout()
        add_col_btn = QPushButton("Add Column")
        add_col_btn.clicked.connect(lambda: self.add_column_row())
        remove_col_btn = QPushButton("Remove Column")
        remove_col_btn.clicked.connect(self.remove_column_row)
        
        btn_layout.addWidget(add_col_btn)
        btn_layout.addWidget(remove_col_btn)
        btn_layout.addStretch()

        col_layout.addLayout(btn_layout)
        col_layout.addWidget(self.col_table)
        
        # Add a default 'id' column
        # Postgres uses SERIAL, SQLite usually uses INTEGER (which becomes auto-increment if PK)
        default_id_type = "SERIAL" if self.db_type == 'postgres' else "INTEGER"
        self.add_column_row("id", default_id_type, True)
        
        self.tabs.addTab(self.columns_tab, "Columns")

        # --- Dialog Buttons (OK/Cancel) ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def add_column_row(self, name="", type="", is_pk=False):
        row = self.col_table.rowCount()
        self.col_table.insertRow(row)
        
        # Default type if empty
        if not type:
            type = "VARCHAR" if self.db_type == 'postgres' else "TEXT"

        # Name Item
        self.col_table.setItem(row, 0, QTableWidgetItem(name))
        
        # Type Item (editable)
        self.col_table.setItem(row, 1, QTableWidgetItem(type))
        
        # PK Checkbox
        pk_item = QTableWidgetItem()
        pk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        pk_item.setCheckState(Qt.CheckState.Checked if is_pk else Qt.CheckState.Unchecked)
        self.col_table.setItem(row, 2, pk_item)

    def remove_column_row(self):
        current_row = self.col_table.currentRow()
        if current_row >= 0:
            self.col_table.removeRow(current_row)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Table Name is required!")
            return
        self.accept()

    def get_sql_data(self):
        """Returns a dictionary with the table definition data"""
        columns = []
        for r in range(self.col_table.rowCount()):
            name = self.col_table.item(r, 0).text()
            dtype = self.col_table.item(r, 1).text()
            is_pk = self.col_table.item(r, 2).checkState() == Qt.CheckState.Checked
            if name:
                columns.append({"name": name, "type": dtype, "pk": is_pk})
                
        return {
            "name": self.name_input.text().strip(),
            "owner": self.owner_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "columns": columns
        }
