from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, 
    QLineEdit, QComboBox, QTextEdit, QTableWidget, QHeaderView, 
    QAbstractItemView, QHBoxLayout, QPushButton, QDialogButtonBox, 
    QTableWidgetItem, QMessageBox, QLabel
)
from PySide6.QtCore import Qt

class CreateTableDialog(QDialog):
    def __init__(self, parent=None, schemas=None, current_user="postgres", db_type="postgres"):
        super().__init__(parent)
        self.setWindowTitle(f"Create Table ({db_type.capitalize()})")
        self.resize(650, 520)
        self.db_type = db_type
        
        from PySide6.QtCore import Qt
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        
        # Apply style from parent/manager
        if hasattr(parent, '_get_dialog_style'):
            self.setStyleSheet(parent._get_dialog_style() + """
                QTabWidget::pane { border: 1px solid #d1d5db; border-radius: 4px; top: -1px; background: white; }
                QTabBar::tab { background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
                QTabBar::tab:selected { background: white; border-bottom-color: white; font-weight: 600; }
                QTableWidget { border: 1px solid #d1d5db; gridline-color: #f3f4f6; }
                QHeaderView::section { background-color: #f9fafb; padding: 4px; border: none; border-bottom: 1px solid #d1d5db; border-right: 1px solid #d1d5db; color: #4b5563; font-weight: 600; }
            """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 18)
        main_layout.setSpacing(14)

        # Header
        title_lbl = QLabel("Create Table")
        title_lbl.setObjectName("dialogTitle")
        subtitle_lbl = QLabel(f"Define a new table in the <b>{db_type}</b> database.")
        subtitle_lbl.setObjectName("dialogSubtitle")
        subtitle_lbl.setTextFormat(Qt.TextFormat.RichText)

        main_layout.addWidget(title_lbl)
        main_layout.addWidget(subtitle_lbl)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # --- Tab 1: General (Name, Owner, Schema) ---
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        gen_layout.setContentsMargins(15, 15, 15, 15)
        gen_layout.setSpacing(10)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("table_name")
        self.owner_input = QLineEdit(current_user)
        self.schema_combo = QComboBox()
        self.schema_combo.setEditable(True)
        
        if schemas:
            self.schema_combo.addItems(schemas)
        else:
            self.schema_combo.addItem("public" if db_type == 'postgres' else "main")
            
        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("Optional description")
        self.comment_input.setMaximumHeight(80)

        gen_layout.addRow("Name:", self.name_input)
        
        if self.db_type == 'postgres':
            gen_layout.addRow("Owner:", self.owner_input)
            gen_layout.addRow("Schema:", self.schema_combo)
        
        gen_layout.addRow("Comment:", self.comment_input)
        
        self.tabs.addTab(self.general_tab, "General")

        # --- Tab 2: Columns ---
        self.columns_tab = QWidget()
        col_layout = QVBoxLayout(self.columns_tab)
        col_layout.setContentsMargins(15, 15, 15, 15)
        
        self.col_table = QTableWidget(0, 3)
        self.col_table.setHorizontalHeaderLabels(["Name", "Data Type", "Primary Key?"])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.col_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.col_table.setAlternatingRowColors(True)
        self.col_table.setStyleSheet("alternate-background-color: #f9fafb;")
        
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
        
        default_id_type = "SERIAL" if self.db_type == 'postgres' else "INTEGER"
        self.add_column_row("id", default_id_type, True)
        
        self.tabs.addTab(self.columns_tab, "Columns")

        # --- Footer Buttons ---
        footer_btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Create")
        self.save_btn.setObjectName("primaryButton")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        
        footer_btn_layout.addStretch()
        footer_btn_layout.addWidget(self.cancel_btn)
        footer_btn_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(footer_btn_layout)
        
        self.save_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn.clicked.connect(self.reject)

    def add_column_row(self, name="", type="", is_pk=False):
        row = self.col_table.rowCount()
        self.col_table.insertRow(row)
        
        if not type:
            type = "VARCHAR" if self.db_type == 'postgres' else "TEXT"

        self.col_table.setItem(row, 0, QTableWidgetItem(name))
        self.col_table.setItem(row, 1, QTableWidgetItem(type))
        
        pk_item = QTableWidgetItem()
        pk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        pk_item.setCheckState(Qt.CheckState.Checked if is_pk else Qt.CheckState.Unchecked)
        pk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.col_table.setItem(row, 2, pk_item)

    def remove_column_row(self):
        current_row = self.col_table.currentRow()
        if current_row >= 0:
            self.col_table.removeRow(current_row)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Error", "Table Name is required!")
            return
        
        # Check if at least one column is defined
        has_cols = False
        for r in range(self.col_table.rowCount()):
            if self.col_table.item(r, 0) and self.col_table.item(r, 0).text().strip():
                has_cols = True
                break
        
        if not has_cols:
            QMessageBox.warning(self, "Error", "At least one column name is required!")
            return

        self.accept()

    def get_sql_data(self):
        columns = []
        for r in range(self.col_table.rowCount()):
            name_item = self.col_table.item(r, 0)
            type_item = self.col_table.item(r, 1)
            pk_item = self.col_table.item(r, 2)
            
            if name_item:
                name = name_item.text().strip()
                dtype = type_item.text().strip() if type_item else ""
                is_pk = pk_item.checkState() == Qt.CheckState.Checked if pk_item else False
                if name:
                    columns.append({"name": name, "type": dtype, "pk": is_pk})
                
        return {
            "name": self.name_input.text().strip(),
            "owner": self.owner_input.text().strip(),
            "schema": self.schema_combo.currentText(),
            "columns": columns
        }

