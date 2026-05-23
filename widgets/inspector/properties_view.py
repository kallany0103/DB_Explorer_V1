# widgets/inspector/properties_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QScrollArea, 
    QFormLayout, QFrame, QTableView, QHeaderView, QAbstractItemView,
    QSizePolicy, QCheckBox, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
import qtawesome as qta
from dialogs.properties import pg_queries
from workers.inspector_workers import InspectorWorker
import db

HIDDEN_PROPERTY_KEYS = frozenset({
    "oid", "relkind", "reltablespace", "nspname", "sql", "schema_name",
})

PROPERTY_LABELS = {
    "owner": "Owner",
    "comment": "Comment",
    "rows_estimated": "Estimated rows",
    "is_partitioned": "Partitioned",
}


class CollapsibleCard(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("propertyCard")
        self.setStyleSheet("""
            QFrame#propertyCard { background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px; }
            QLabel#cardHeader {
                background-color: #f3f4f6; color: #111827; font-weight: 600; font-size: 10pt;
                padding: 8px 12px; border-top-left-radius: 8px; border-top-right-radius: 8px;
                border-bottom: 1px solid #e5e7eb;
            }
            QLabel#cardHeader[active="true"] { background-color: #e0f2fe; color: #0369a1; border-bottom: 1px solid #bae6fd; }
        """)
        
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
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setStyleSheet("""
            QTableView { border: 1px solid #e5e7eb; background-color: white; alternate-background-color: #f9fafb; gridline-color: #f3f4f6; border-radius: 4px; }
            QHeaderView::section { background-color: #f3f4f6; padding: 8px; border: none; border-right: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; }
        """)

class PropertiesWorkbench(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.item_data = None
        self.obj_name = None
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar-like header
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: white; border-bottom: 1px solid #e5e7eb;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.icon_label = QLabel()
        header_layout.addWidget(self.icon_label)
        
        text_layout = QVBoxLayout()
        self.header_label = QLabel("Properties")
        self.header_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")
        self.sub_label = QLabel("Select an object to view properties")
        self.sub_label.setStyleSheet("font-size: 11px; color: #6b7280;")
        text_layout.addWidget(self.header_label)
        text_layout.addWidget(self.sub_label)
        header_layout.addLayout(text_layout)
        
        header_layout.addStretch()
        
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(100)
        self.progress.setVisible(False)
        header_layout.addWidget(self.progress)
        
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(qta.icon('mdi.refresh', color='#6b7280'))
        self.refresh_btn.setFlat(True)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_properties)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(header_frame)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: #f8fafc;")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(15, 15, 15, 15)
        self.container_layout.setSpacing(0)
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh_properties(self):
        if self.item_data:
            self.update_view(self.item_data, self.obj_name)

    def update_view(self, item_data, obj_name):
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(obj_name)
        
        obj_type = item_data.get('type', 'Unknown')
        group_name = item_data.get('group_name')
        if not group_name and obj_type.endswith('_root'):
            if obj_type == 'schemas_root': group_name = "Schemas"
            elif obj_type == 'fdw_root': group_name = "Foreign Data Wrappers"
            elif obj_type == 'extension_root': group_name = "Extensions"
            elif obj_type == 'language_root': group_name = "Languages"

        icon_color = '#6366f1'
        icon_name = 'mdi.cube-outline'
        if obj_type == 'table': icon_name, icon_color = 'mdi.table', '#3b82f6'
        elif obj_type == 'view': icon_name, icon_color = 'mdi.eye', '#10b981'
        elif obj_type == 'schema': icon_name, icon_color = 'mdi.folder-table', '#f59e0b'
        elif obj_type == 'connection': icon_name, icon_color = 'mdi.database', '#6366f1'
        elif obj_type == 'function': icon_name, icon_color = 'mdi.function', '#ec4899'
        elif obj_type == 'sequence': icon_name, icon_color = 'mdi.numeric', '#8b5cf6'
        
        if group_name: icon_name, icon_color = 'mdi.folder-outline', '#94a3b8'
        self.icon_label.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(24, 24))
        self.sub_label.setText(f"{obj_type.capitalize() if not group_name else 'Collection'}")
        
        self._clear_container()
        
        if not item_data: return
        
        self.progress.setVisible(True)
        worker = InspectorWorker(item_data, obj_name, task_type="properties")
        worker.signals.finished.connect(self._on_data_loaded)
        worker.signals.error.connect(self._on_load_error)
        self.main_window.thread_pool.start(worker)

    def _on_data_loaded(self, data):
        self.progress.setVisible(False)
        self._clear_container()
        
        if data.get("type") == "group":
            self._display_group(data)
        else:
            self._display_object(data)

    def _on_load_error(self, error_msg):
        self.progress.setVisible(False)
        self.container_layout.addWidget(QLabel(f"Error: {error_msg}"))

    def _display_group(self, data):
        group_name = data.get("group_name", "Collection")
        # Toolbar
        coll_toolbar = QFrame()
        coll_toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #e5e7eb; padding: 2px;")
        coll_layout = QHBoxLayout(coll_toolbar)
        coll_layout.setContentsMargins(5, 5, 5, 5)
        for icon_name, color in [('mdi.delete-outline', '#94a3b8'), ('mdi.delete-sweep-outline', '#94a3b8')]:
            btn = QPushButton(); btn.setIcon(qta.icon(icon_name, color=color)); btn.setFixedSize(28, 28); btn.setFlat(True); coll_layout.addWidget(btn)
        coll_layout.addStretch()
        from PySide6.QtWidgets import QLineEdit
        search = QLineEdit(); search.setPlaceholderText("Search..."); search.setFixedWidth(200); coll_layout.addWidget(search)
        self.container_layout.addWidget(coll_toolbar)

        table = PropertyTable()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(data.get("columns", []))
        for row in data.get("rows", []):
            items = []
            for val in row:
                if isinstance(val, bool):
                    item = QStandardItem(); item.setIcon(qta.icon('mdi.check-bold' if val else 'mdi.close-thick', color='#10b981' if val else '#ef4444')); item.setText("Yes" if val else "No")
                else: item = QStandardItem(str(val) if val is not None else "")
                items.append(item)
            model.appendRow(items)
        table.setModel(model)
        self.container_layout.addWidget(table)
        
        search.textChanged.connect(lambda t: [table.setRowHidden(r, not any(t.lower() in model.item(r, c).text().lower() for c in range(model.columnCount()))) for r in range(model.rowCount())])
        table.resizeColumnsToContents()

    def _display_object(self, data):
        details = data.get("details", {})
        gen = CollapsibleCard("General")
        gen.add_row("Name", self.obj_name)
        for k, v in details.items():
            if k in HIDDEN_PROPERTY_KEYS:
                continue
            label = PROPERTY_LABELS.get(k, k.replace("_", " ").capitalize())
            gen.add_row(label, v)
        self.container_layout.addWidget(gen)
        
        if data.get("sql"):
            sql_card = CollapsibleCard("SQL")
            editor = QTextEdit(); editor.setReadOnly(True); editor.setPlainText(data["sql"]); editor.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10pt; border: none; background: #f9fafb;"); editor.setMinimumHeight(200); sql_card.content_layout.addWidget(editor)
            self.container_layout.addWidget(sql_card)
        self.container_layout.addStretch()

    def _clear_container(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
