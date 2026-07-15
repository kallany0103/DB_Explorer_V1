from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, 
    QFrame, QTableView, QHeaderView, QAbstractItemView,
    QCheckBox, QStyledItemDelegate, QComboBox
)
from PySide6.QtCore import Qt

class DataTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_types = [
            "integer", "bigint", "smallint", "boolean", "character varying", "character",
            "text", "date", "timestamp", "timestamp without time zone", "timestamp with time zone",
            "time", "time without time zone", "numeric", "double precision", "real",
            "json", "jsonb", "uuid", "bytea", "serial", "bigserial", "smallserial"
        ]

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.data_types)
        editor.setEditable(True)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.ItemDataRole.EditRole)


HIDDEN_PROPERTY_KEYS = frozenset({
    "oid", "relkind", "reltablespace", "nspname", "sql", "schema_name",
})

PROPERTY_LABELS = {
    "owner": "Owner",
    "comment": "Comment",
    "rows_estimated": "Estimated rows",
    "is_partitioned": "Partitioned",
    "table_name": "Table",
    "function_name": "Trigger Function",
    "status": "Status",
    "timing": "Timing",
    "events": "Events",
    "level": "Level",
}


class CollapsibleCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("propertyCard")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.header = QLabel(title)
        self.header.setObjectName("cardHeader")
        self.header.setProperty("active", True)
        layout.addWidget(self.header)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 12, 15, 12)
        layout.addWidget(self.content_widget)
        
        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form_layout.setSpacing(10)
        self.content_layout.addLayout(self.form_layout)

    def add_row(self, label_text, value_widget):
        label = QLabel(label_text)
        label.setStyleSheet("color: #4b5563; font-weight: 500;")
        
        if isinstance(value_widget, str):
            val = QLabel(value_widget)
            val.setWordWrap(True)
            val.setMinimumHeight(24)
            val.setStyleSheet("color: #111827; background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 4px; padding: 4px 8px;")
            value_widget = val
        elif isinstance(value_widget, (bool, int)):
            if isinstance(value_widget, bool):
                val = QCheckBox()
                val.setChecked(value_widget)
                val.setEnabled(False)
                value_widget = val
            else:
                val = QLabel(str(value_widget))
                val.setStyleSheet("color: #111827; background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 4px; padding: 4px 8px;")
                value_widget = val
            
        self.form_layout.addRow(label, value_widget)


class PropertyTable(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("propertyTable")
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.verticalHeader().setDefaultSectionSize(28)
