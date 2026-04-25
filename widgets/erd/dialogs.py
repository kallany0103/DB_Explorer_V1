from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QComboBox,
    QCheckBox, QMessageBox, QHeaderView,
    QWidget, QFormLayout
)
from PySide6.QtCore import Qt

from widgets.erd.model import DEFAULT_SCHEMA


class TableDesignerDialog(QDialog):
    def __init__(self, parent=None, table_name="", columns=None, schema_name=DEFAULT_SCHEMA, foreign_keys=None, notes=None):
        super().__init__(parent)
        self.setWindowTitle("Entity Designer")
        self.resize(650, 500)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setStyleSheet(self._get_style())

        self.schema_name = schema_name or DEFAULT_SCHEMA
        self.columns = columns or []
        self.foreign_keys = foreign_keys or []
        self.notes = notes or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        form = QFormLayout()
        self.schema_input = QLineEdit(self.schema_name)
        self.schema_input.setPlaceholderText("Schema (default: public)")
        form.addRow("Schema:", self.schema_input)

        self.name_input = QLineEdit(table_name)
        self.name_input.setPlaceholderText("Entity name...")
        form.addRow("Entity Name:", self.name_input)
        layout.addLayout(form)

        self.col_table = QTableWidget(0, 5)
        self.col_table.setHorizontalHeaderLabels(["Column Name", "Type", "PK", "Nullable", "FK"])
        header = self.col_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.col_table.setColumnWidth(0, 220)
        self.col_table.setColumnWidth(1, 220)
        self.col_table.verticalHeader().setDefaultSectionSize(38)
        self.col_table.verticalHeader().setVisible(False)
        self.col_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: white;
                color: #1f2937;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                padding: 4px;
                border: 1px solid #d1d5db;
                font-weight: bold;
                color: #1f2937;
            }
        """)
        layout.addWidget(QLabel("Columns"))
        layout.addWidget(self.col_table, 1)

        ctrl_layout = QHBoxLayout()
        add_col_btn = QPushButton("Add Column")
        add_col_btn.clicked.connect(self.add_column_row)
        remove_col_btn = QPushButton("Remove Column")
        remove_col_btn.clicked.connect(self.remove_column_row)
        ctrl_layout.addWidget(add_col_btn)
        ctrl_layout.addWidget(remove_col_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        for col in self.columns:
            self.add_column_row(col)

        if not self.columns:
            self.add_column_row({"name": "id", "type": "INTEGER", "pk": True, "nullable": False})

    def _get_style(self):
        return """
            QDialog {
                background-color: #f6f8fb;
                color: #1f2937;
            }
            QLabel {
                color: #374151;
            }
            QLineEdit, QComboBox {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding: 4px 8px;
                color: #1f2937;
            }
            QTableWidget QLineEdit, QTableWidget QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                min-height: 26px;
                background-color: white;
                padding: 2px 6px;
                margin: 3px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #d1d5db;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox QAbstractItemView {
                background: white;
                color: #1f2937;
                border: 1px solid #d1d5db;
                selection-background-color: #0078d4;
                selection-color: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078d4;
            }
            QTableWidget QLineEdit:focus, QTableWidget QComboBox:focus {
                border: 1px solid #0078d4;
                background-color: white;
            }
            QCheckBox {
                color: #1f2937;
            }
            QPushButton {
                min-height: 28px;
                padding: 4px 16px;
                border: 1px solid #d1d5db;
                background-color: white;
                color: #374151;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
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
            QPushButton#secondaryButton {
                border: 1px solid #c4c9d4;
                background-color: #ffffff;
                color: #1f2937;
            }
            QPushButton#secondaryButton:hover {
                background-color: #f3f4f6;
            }
        """

    def add_column_row(self, col_data=None):
        row = self.col_table.rowCount()
        self.col_table.insertRow(row)

        name = QLineEdit(col_data.get("name", "") if col_data else "")
        self.col_table.setCellWidget(row, 0, name)

        type_combo = QComboBox()
        type_combo.setEditable(True)
        type_combo.setMinimumContentsLength(14)
        type_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        types = [
            "INTEGER", "VARCHAR(255)", "TEXT", "BOOLEAN", "TIMESTAMP", "DECIMAL(10,2)",
            "SMALLINT", "BIGINT", "SERIAL", "BIGSERIAL",
            "NUMERIC", "REAL", "DOUBLE PRECISION", "FLOAT",
            "DATETIME", "DATE", "TIME", "TIMESTAMPTZ",
            "JSON", "JSONB", "UUID", "BLOB", "BYTEA",
            "CHAR", "VARCHAR"
        ]
        type_combo.addItems(types)
        if col_data:
            type_val = col_data.get("type", "INTEGER").upper()
            if type_val not in types:
                type_combo.addItem(type_val)
            type_combo.setCurrentText(type_val)
        self.col_table.setCellWidget(row, 1, type_combo)

        pk_check = QCheckBox()
        pk_check.setChecked(col_data.get("pk", False) if col_data else False)
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

        fk_check = QCheckBox()
        fk_check.setChecked(col_data.get("fk", False) if col_data else False)
        fk_widget = QWidget()
        fk_layout = QHBoxLayout(fk_widget)
        fk_layout.addWidget(fk_check)
        fk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fk_layout.setContentsMargins(0, 0, 0, 0)
        self.col_table.setCellWidget(row, 4, fk_widget)

        def _on_pk_changed(state):
            if state == Qt.CheckState.Checked.value:
                null_check.setChecked(False)

        pk_check.stateChanged.connect(_on_pk_changed)

    def remove_column_row(self):
        curr = self.col_table.currentRow()
        if curr >= 0:
            self.col_table.removeRow(curr)

    def get_result(self):
        cols = []
        for r in range(self.col_table.rowCount()):
            name = self.col_table.cellWidget(r, 0).text()
            if not name:
                continue

            c_type = self.col_table.cellWidget(r, 1).currentText()

            pk_widget = self.col_table.cellWidget(r, 2)
            pk = pk_widget.findChild(QCheckBox).isChecked()

            null_widget = self.col_table.cellWidget(r, 3)
            null = null_widget.findChild(QCheckBox).isChecked()

            fk_widget = self.col_table.cellWidget(r, 4)
            fk = fk_widget.findChild(QCheckBox).isChecked()

            cols.append({
                "name": name,
                "type": c_type,
                "pk": pk,
                "nullable": null,
                "fk": fk,
            })

        return self.name_input.text(), cols

    def accept(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Entity name cannot be empty.")
            return

        if self.col_table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "Entity must have at least one column.")
            return

        super().accept()


class RelationDesignerDialog(QDialog):
    def __init__(self, parent=None, tables=None):
        super().__init__(parent)
        self.setWindowTitle("Create Relationship")
        self.resize(450, 320)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setStyleSheet(TableDesignerDialog._get_style(self))

        self.tables = tables or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        form = QFormLayout()

        self.src_table_combo = QComboBox()
        self.src_table_combo.addItems(sorted(self.tables.keys()))
        form.addRow("Source Entity:", self.src_table_combo)

        self.src_col_combo = QComboBox()
        form.addRow("Source Column:", self.src_col_combo)

        self.target_table_combo = QComboBox()
        self.target_table_combo.addItems(sorted(self.tables.keys()))
        form.addRow("Target Entity:", self.target_table_combo)

        self.target_col_combo = QComboBox()
        form.addRow("Target Column:", self.target_col_combo)

        self.type_combo = QComboBox()
        from widgets.erd.items.connection_item import ERDConnectionItem
        reltab = ERDConnectionItem.RELATION_TYPES
        for k, v in reltab.items():
            self.type_combo.addItem(v['label'], k)
        form.addRow("Relation Type:", self.type_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Create Relationship")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        self.src_table_combo.currentTextChanged.connect(self.update_src_cols)
        self.target_table_combo.currentTextChanged.connect(self.update_target_cols)

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
        if res['source_table'] == res['target_table'] and res['source_col'] == res['target_col']:
            QMessageBox.warning(self, "Validation Error", "Cannot relate a column to itself.")
            return

        super().accept()
