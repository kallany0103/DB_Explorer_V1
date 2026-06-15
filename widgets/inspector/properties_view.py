# widgets/inspector/properties_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QScrollArea, 
    QFormLayout, QFrame, QTableView, QHeaderView, QAbstractItemView,
    QSizePolicy, QCheckBox, QPushButton, QProgressBar, QTabWidget,
    QStyledItemDelegate, QComboBox, QMessageBox, QToolButton
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont
import qtawesome as qta
from dialogs.properties import pg_queries
from workers.inspector_workers import InspectorWorker
import db

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
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setStyleSheet("""
            QTableView {
                border: none;
                background-color: white;
                alternate-background-color: #f8fafc;
                outline: none;
            }
            QTableView::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f1f5f9;
                color: #1e293b;
            }
            QTableView::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
            }
            QTableView::item:hover:!selected {
                background-color: #f0f9ff;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 600;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #64748b;
            }
        """)
        self.verticalHeader().setDefaultSectionSize(36)

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
        elif obj_type == 'trigger':
            tgenabled = item_data.get('tgenabled')
            if tgenabled == 'D':
                icon_name, icon_color = 'mdi.lightning-bolt-outline', '#9fa6b2'
            else:
                icon_name, icon_color = 'mdi.lightning-bolt', '#f59e0b'
        
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
        obj_type = self.item_data.get('type', 'Unknown')
        
        # Use tabbed interface for tables
        if obj_type == 'table':
            self._display_table_with_tabs(data)
        else:
            self._display_object_with_cards(data)

    def _display_table_with_tabs(self, data):
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e5e7eb; background: white; border-radius: 4px; }
            QTabBar::tab { 
                background: #f3f4f6; color: #374151; padding: 8px 16px; 
                border: 1px solid #e5e7eb; border-bottom: none; 
                margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: white; color: #111827; border-bottom: 2px solid #3b82f6; }
            QTabBar::tab:hover:!selected { background: #e5e7eb; }
        """)
        
        # General Tab
        general_tab = self._create_general_tab(data)
        tab_widget.addTab(general_tab, "General")
        
        # Columns Tab
        columns_tab = self._create_columns_tab(data)
        tab_widget.addTab(columns_tab, "Columns")
        
        # Constraints Tab
        constraints_tab = self._create_constraints_tab(data)
        tab_widget.addTab(constraints_tab, "Constraints")
        
        # SQL Tab
        if data.get("sql"):
            sql_tab = self._create_sql_tab(data)
            tab_widget.addTab(sql_tab, "SQL")
        
        self.container_layout.addWidget(tab_widget)
        self.container_layout.addStretch()

    def _create_general_tab(self, data):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        details = data.get("details", {})
        gen = CollapsibleCard("General")
        gen.add_row("Name", self.obj_name)
        for k, v in details.items():
            if k in HIDDEN_PROPERTY_KEYS:
                continue
            label = PROPERTY_LABELS.get(k, k.replace("_", " ").capitalize())
            gen.add_row(label, v)
        layout.addWidget(gen)
        layout.addStretch()
        return widget

    def _create_columns_tab(self, data):
        widget = QWidget()
        widget.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
            }
            QPushButton {
                border: 1px solid #e2e8f0;
                border-radius: 5px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
                background-color: white;
                color: #374151;
            }
            QPushButton:hover { background-color: #f0f9ff; border-color: #bfdbfe; color: #1e40af; }
            QPushButton#saveBtn {
                background-color: #3b82f6;
                color: white;
                border: none;
            }
            QPushButton#saveBtn:hover { background-color: #2563eb; }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 6, 10, 6)
        toolbar_layout.setSpacing(6)

        col_count_label = QLabel()
        col_count_label.setStyleSheet("color: #64748b; font-size: 11px; background: transparent; border: none;")
        toolbar_layout.addWidget(col_count_label)
        toolbar_layout.addStretch()

        add_col_btn = QPushButton(" Add Column")
        add_col_btn.setIcon(qta.icon('mdi.table-column-plus-after', color='#10b981'))
        add_col_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_col_btn.setFixedHeight(28)

        save_btn = QPushButton(" Save Changes")
        save_btn.setObjectName("saveBtn")
        save_btn.setIcon(qta.icon('mdi.content-save-outline', color='white'))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFixedHeight(28)

        toolbar_layout.addWidget(add_col_btn)
        toolbar_layout.addWidget(save_btn)
        layout.addWidget(toolbar)

        # ── Table ─────────────────────────────────────────────────────────────
        self.columns_table = PropertyTable()
        self.columns_table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.columns_table.horizontalHeader().setStretchLastSection(False)

        self.columns_model = QStandardItemModel()
        self.columns_model.setHorizontalHeaderLabels(["Name", "Data Type", "PK", "Not Null", "Default", "Comment", ""])
        self.original_columns_data = data.get("columns", [])

        for col in self.original_columns_data:
            self._append_column_row(col.get("name", ""),
                                    col.get("data_type", ""),
                                    col.get("is_pk", False),
                                    not col.get("nullable", True),
                                    col.get("default_value") or "",
                                    col.get("comment") or "",
                                    orig_name=col.get("name", ""))

        self.columns_table.setModel(self.columns_model)
        self.columns_table.setItemDelegateForColumn(1, DataTypeDelegate(self.columns_table))

        # Column sizing
        hh = self.columns_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)        # Name
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Type
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);  self.columns_table.setColumnWidth(2, 40)  # PK
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed);  self.columns_table.setColumnWidth(3, 60)  # Not Null
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Default
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # Comment
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed);  self.columns_table.setColumnWidth(6, 36)  # Delete

        # Attach delete widgets
        for row in range(self.columns_model.rowCount()):
            self.columns_table.setIndexWidget(
                self.columns_model.index(row, 6),
                self._make_delete_btn(row)
            )

        layout.addWidget(self.columns_table)

        # Update counter label
        def _update_count():
            n = self.columns_model.rowCount()
            col_count_label.setText(f"{n} column{'s' if n != 1 else ''}")
        self.columns_model.rowsInserted.connect(_update_count)
        self.columns_model.rowsRemoved.connect(_update_count)
        _update_count()

        add_col_btn.clicked.connect(self._add_column)
        save_btn.clicked.connect(self._save_column_changes)

        return widget

    def _make_delete_btn(self, row):
        """Return a flat red trash icon button that removes its row from the model."""
        btn = QToolButton()
        btn.setIcon(qta.icon('mdi.trash-can-outline', color='#cbd5e1'))
        btn.setFixedSize(28, 28)
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QToolButton { border: none; border-radius: 4px; background: transparent; }
            QToolButton:hover { background-color: #fee2e2; icon-color: #ef4444; }
        """)
        btn.setProperty("target_row", row)

        def _delete():
            # Find the button's current row by matching via loop (handles re-indexing)
            for r in range(self.columns_model.rowCount()):
                w = self.columns_table.indexWidget(self.columns_model.index(r, 6))
                if w is btn:
                    self.columns_model.removeRow(r)
                    # Refresh delete-button row properties for rows below
                    break
        btn.clicked.connect(_delete)
        return btn

    def _append_column_row(self, name, data_type, is_pk, not_null, default_val, comment, orig_name=None):
        """Build and append one column row to self.columns_model. Returns the row index."""
        name_item = QStandardItem(name)
        name_item.setData(orig_name if orig_name is not None else "", Qt.ItemDataRole.UserRole)

        type_item = QStandardItem(data_type)

        pk_item = QStandardItem()
        pk_item.setCheckable(True)
        pk_item.setEditable(False)
        pk_item.setCheckState(Qt.CheckState.Checked if is_pk else Qt.CheckState.Unchecked)
        pk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        nn_item = QStandardItem()
        nn_item.setCheckable(True)
        nn_item.setEditable(False)
        nn_item.setCheckState(Qt.CheckState.Checked if not_null else Qt.CheckState.Unchecked)
        nn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        default_item = QStandardItem(str(default_val) if default_val else "")
        comment_item = QStandardItem(str(comment) if comment else "")
        action_item  = QStandardItem()  # placeholder for the delete button column
        action_item.setEditable(False)

        self.columns_model.appendRow([name_item, type_item, pk_item, nn_item, default_item, comment_item, action_item])
        return self.columns_model.rowCount() - 1

    def _add_column(self):
        row = self._append_column_row("new_column", "integer", False, False, "", "", orig_name="")
        if hasattr(self, 'columns_table'):
            self.columns_table.setIndexWidget(
                self.columns_model.index(row, 6),
                self._make_delete_btn(row)
            )
            self.columns_table.scrollToBottom()

    def _save_column_changes(self):
        conn_data = self.item_data.get('conn_data') or self.item_data
        pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
        try:
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to database:\n{e}")
            return

        schema_name = self.item_data.get('schema_name', 'public')
        table_name = self.obj_name

        alter_statements = []
        new_pk_columns = []
        old_pk_columns = [col['name'] for col in self.original_columns_data if col.get('is_pk')]

        # Build a set of original column names for drop detection
        orig_names_set = {col['name'] for col in self.original_columns_data}
        orig_by_name   = {col['name']: col for col in self.original_columns_data}

        # Columns still present in the grid (tracked by UserRole original name)
        grid_orig_names = set()

        for row in range(self.columns_model.rowCount()):
            name       = self.columns_model.item(row, 0).text().strip()
            data_type  = self.columns_model.item(row, 1).text().strip()
            is_pk      = self.columns_model.item(row, 2).checkState() == Qt.CheckState.Checked
            not_null   = self.columns_model.item(row, 3).checkState() == Qt.CheckState.Checked
            default_val = self.columns_model.item(row, 4).text().strip()
            comment    = self.columns_model.item(row, 5).text().strip()
            orig_name  = self.columns_model.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""

            if is_pk:
                new_pk_columns.append(name)

            if orig_name and orig_name in orig_names_set:
                # Existing column – diff against original
                grid_orig_names.add(orig_name)
                orig = orig_by_name[orig_name]

                if name != orig_name:
                    alter_statements.append(
                        f'ALTER TABLE "{schema_name}"."{table_name}" RENAME COLUMN "{orig_name}" TO "{name}";')

                if data_type != orig.get('data_type', ''):
                    alter_statements.append(
                        f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" TYPE {data_type} USING "{name}"::{data_type};')

                if not_null != (not orig.get('nullable', True)):
                    action = "SET NOT NULL" if not_null else "DROP NOT NULL"
                    alter_statements.append(
                        f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" {action};')

                orig_default = str(orig.get('default_value', '')) if orig.get('default_value') else ""
                if default_val != orig_default:
                    if default_val:
                        alter_statements.append(
                            f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" SET DEFAULT {default_val};')
                    else:
                        alter_statements.append(
                            f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" DROP DEFAULT;')

                orig_comment = str(orig.get('comment', '')) if orig.get('comment') else ""
                if comment != orig_comment:
                    alter_statements.append(
                        f"COMMENT ON COLUMN \"{schema_name}\".\"{table_name}\".\"{name}\" IS '{comment}';")
            else:
                # New column (orig_name is empty or not in original set)
                if not name:
                    continue
                stmt = f'ALTER TABLE "{schema_name}"."{table_name}" ADD COLUMN "{name}" {data_type}'
                if not_null:
                    stmt += " NOT NULL"
                if default_val:
                    stmt += f" DEFAULT {default_val}"
                stmt += ";"
                alter_statements.append(stmt)
                if comment:
                    alter_statements.append(
                        f"COMMENT ON COLUMN \"{schema_name}\".\"{table_name}\".\"{name}\" IS '{comment}';")

        # Columns that existed originally but are no longer in the grid → DROP
        dropped_cols = orig_names_set - grid_orig_names
        for col_name in dropped_cols:
            alter_statements.append(
                f'ALTER TABLE "{schema_name}"."{table_name}" DROP COLUMN "{col_name}";')

        # PK constraint changes
        if sorted(new_pk_columns) != sorted(old_pk_columns):
            cursor.execute("""
                SELECT conname FROM pg_constraint
                WHERE contype = 'p'
                  AND conrelid = (
                      SELECT oid FROM pg_class
                      WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
                        AND relname = %s
                  )
            """, (schema_name, table_name))
            pk_res = cursor.fetchone()
            if pk_res:
                alter_statements.append(
                    f'ALTER TABLE "{schema_name}"."{table_name}" DROP CONSTRAINT "{pk_res[0]}";')
            if new_pk_columns:
                pk_cols_str = ", ".join([f'"{c}"' for c in new_pk_columns])
                alter_statements.append(
                    f'ALTER TABLE "{schema_name}"."{table_name}" ADD PRIMARY KEY ({pk_cols_str});')

        if not alter_statements:
            QMessageBox.information(self, "No Changes", "No column changes detected.")
            conn.close()
            return

        try:
            for stmt in alter_statements:
                cursor.execute(stmt)
            conn.commit()
            QMessageBox.information(self, "Success", "Table columns updated successfully.")
            self.refresh_properties()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Execution Error",
                                 f"Failed to execute changes:\n{e}\n\nTransaction rolled back.")
        finally:
            conn.close()


    def _create_constraints_tab(self, data):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        table = PropertyTable()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Name", "Type", "Definition"])
        
        constraints = data.get("constraints", [])
        for cons in constraints:
            items = [QStandardItem(str(cons.get("name", ""))),
                     QStandardItem(str(cons.get("type", ""))),
                     QStandardItem(str(cons.get("definition", "")))]
            model.appendRow(items)
        
        table.setModel(model)
        table.resizeColumnsToContents()
        layout.addWidget(table)
        return widget

    def _create_sql_tab(self, data):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(data["sql"])
        editor.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10pt; border: 1px solid #e5e7eb; background: #f9fafb; border-radius: 4px; padding: 8px;")
        editor.setMinimumHeight(200)
        layout.addWidget(editor)
        return widget

    def _display_object_with_cards(self, data):
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
