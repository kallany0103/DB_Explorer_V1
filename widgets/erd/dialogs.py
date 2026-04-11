from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QCheckBox, QDialogButtonBox, QMessageBox, QHeaderView,
    QWidget, QFormLayout
)
from PySide6.QtCore import Qt

class TableDesignerDialog(QDialog):
    def __init__(self, parent=None, table_name="", columns=None):
        super().__init__(parent)
        self.setWindowTitle("Table Designer")
        self.resize(600, 450)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        self.columns = columns or []
        
        layout = QVBoxLayout(self)

        # Table Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Table Name:"))
        self.name_input = QLineEdit(table_name)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        # Columns Table
        self.col_table = QTableWidget(0, 4)
        self.col_table.setHorizontalHeaderLabels(["Column Name", "Type", "PK", "Nullable"])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.col_table)

        # Column Controls
        ctrl_layout = QHBoxLayout()
        add_col_btn = QPushButton("Add Column")
        add_col_btn.clicked.connect(self.add_column_row)
        remove_col_btn = QPushButton("Remove Column")
        remove_col_btn.clicked.connect(self.remove_column_row)
        ctrl_layout.addWidget(add_col_btn)
        ctrl_layout.addWidget(remove_col_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Initialize rows if columns exist
        for col in self.columns:
            self.add_column_row(col)
        
        if not self.columns:
            self.add_column_row({"name": "id", "type": "INTEGER", "pk": True, "nullable": False})

    def add_column_row(self, col_data=None):
        row = self.col_table.rowCount()
        self.col_table.insertRow(row)

        name = QLineEdit(col_data.get("name", "") if col_data else "")
        self.col_table.setCellWidget(row, 0, name)

        type_combo = QComboBox()
        type_combo.setEditable(True)
        types = ["INTEGER", "VARCHAR(255)", "TEXT", "BOOLEAN", "TIMESTAMP", "DECIMAL(10,2)"]
        type_combo.addItems(types)
        if col_data:
            type_val = col_data.get("type", "INTEGER").upper()
            if type_val not in types:
                type_combo.addItem(type_val)
            type_combo.setCurrentText(type_val)
        self.col_table.setCellWidget(row, 1, type_combo)

        pk_check = QCheckBox()
        pk_check.setChecked(col_data.get("pk", False) if col_data else False)
        # Center the checkbox
        pk_widget = QWidget()
        pk_layout = QHBoxLayout(pk_widget)
        pk_layout.addWidget(pk_check)
        pk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pk_layout.setContentsMargins(0, 0, 0, 0)
        self.col_table.setCellWidget(row, 2, pk_widget)

        null_check = QCheckBox()
        null_check.setChecked(col_data.get("nullable", True) if col_data else True)
        null_widget = QWidget()
        null_layout = QHBoxLayout(null_widget)
        null_layout.addWidget(null_check)
        null_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        null_layout.setContentsMargins(0, 0, 0, 0)
        self.col_table.setCellWidget(row, 3, null_widget)

    def remove_column_row(self):
        curr = self.col_table.currentRow()
        if curr >= 0:
            self.col_table.removeRow(curr)

    def get_result(self):
        cols = []
        for r in range(self.col_table.rowCount()):
            name = self.col_table.cellWidget(r, 0).text()
            if not name: continue
            
            c_type = self.col_table.cellWidget(r, 1).currentText()
            
            pk_widget = self.col_table.cellWidget(r, 2)
            pk = pk_widget.findChild(QCheckBox).isChecked()
            
            null_widget = self.col_table.cellWidget(r, 3)
            null = null_widget.findChild(QCheckBox).isChecked()
            
            cols.append({
                "name": name,
                "type": c_type,
                "pk": pk,
                "nullable": null
            })
        
        return self.name_input.text(), cols

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Table name cannot be empty.")
            return
        
        if self.col_table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "Table must have at least one column.")
            return
            
        
        super().accept()

class RelationDesignerDialog(QDialog):
    def __init__(self, parent=None, tables=None):
        super().__init__(parent)
        self.setWindowTitle("Create Relationship")
        self.resize(400, 300)
        
        self.tables = tables or {} # dict of full_name: ERDTableItem
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Source Table
        self.src_table_combo = QComboBox()
        self.src_table_combo.addItems(sorted(self.tables.keys()))
        form.addRow("Source Table:", self.src_table_combo)
        
        # Source Column
        self.src_col_combo = QComboBox()
        form.addRow("Source Column:", self.src_col_combo)
        
        # Target Table
        self.target_table_combo = QComboBox()
        self.target_table_combo.addItems(sorted(self.tables.keys()))
        form.addRow("Target Table:", self.target_table_combo)
        
        # Target Column
        self.target_col_combo = QComboBox()
        form.addRow("Target Column:", self.target_col_combo)
        
        # Relation Type
        self.type_combo = QComboBox()
        # Import here to avoid circular
        from widgets.erd.items.connection_item import ERDConnectionItem
        reltab = ERDConnectionItem.RELATION_TYPES
        for k, v in reltab.items():
            self.type_combo.addItem(v['label'], k)
        form.addRow("Relation Type:", self.type_combo)
        
        layout.addLayout(form)
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        # Signals
        self.src_table_combo.currentTextChanged.connect(self.update_src_cols)
        self.target_table_combo.currentTextChanged.connect(self.update_target_cols)
        
        # Initial population
        self.update_src_cols()
        self.update_target_cols()

    def update_src_cols(self):
        self.src_col_combo.clear()
        tbl_name = self.src_table_combo.currentText()
        if tbl_name in self.tables:
            cols = [c['name'] for c in self.tables[tbl_name].columns]
            self.src_col_combo.addItems(cols)

    def update_target_cols(self):
        self.target_col_combo.clear()
        tbl_name = self.target_table_combo.currentText()
        if tbl_name in self.tables:
            cols = [c['name'] for c in self.tables[tbl_name].columns]
            self.target_col_combo.addItems(cols)

    def get_result(self):
        return {
            "source_table": self.src_table_combo.currentText(),
            "source_col": self.src_col_combo.currentText(),
            "target_table": self.target_table_combo.currentText(),
            "target_col": self.target_col_combo.currentText(),
            "relation_type": self.type_combo.currentData()
        }

    def accept(self):
        res = self.get_result()
        if res['source_table'] == res['target_table']:
            # Self-joins are theoretically possible but let's check if columns are same
            if res['source_col'] == res['target_col']:
                 QMessageBox.warning(self, "Validation Error", "Cannot relate a column to itself.")
                 return
        
        super().accept()
