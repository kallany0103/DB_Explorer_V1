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
from ui.components import PrimaryButton, SecondaryButton, IconButton
from .properties_ui import (
    DataTypeDelegate, CollapsibleCard, PropertyTable,
    HIDDEN_PROPERTY_KEYS, PROPERTY_LABELS
)



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
        
        from PySide6.QtGui import QMovie
        from PySide6.QtCore import QSize
        self.progress = QLabel()
        movie = QMovie("assets/spinner.gif")
        if movie.isValid():
            movie.setScaledSize(QSize(20, 20))
            self.progress.setMovie(movie)
            movie.start()
        else:
            self.progress.setText("Loading...")
        self.progress.setVisible(False)
        header_layout.addWidget(self.progress)
        
        self.refresh_btn = IconButton(qta.icon('mdi.refresh', color='#6b7280'), tooltip="Refresh")
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
            self.update_view(self.item_data, self.obj_name, force_refresh=True)

    def update_view(self, item_data, obj_name, force_refresh=False):
        if not force_refresh and self.item_data == item_data and self.obj_name == obj_name:
            return
            
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
        
        # Save the current inner tab index before clearing
        for i in range(self.container_layout.count()):
            widget = self.container_layout.itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                self._last_inner_tab_index = widget.currentIndex()
                break

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
            btn = IconButton(qta.icon(icon_name, color=color))
            btn.setFixedSize(28, 28)
            coll_layout.addWidget(btn)
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
            QTabWidget::pane { 
                border: 1px solid #e5e7eb; 
                background: white; 
                border-radius: 6px; 
                top: -1px;
            }
            QTabBar::tab { 
                background: transparent; 
                color: #64748b; 
                padding: 10px 20px; 
                border: 1px solid transparent; 
                border-bottom: 2px solid transparent; 
                margin-right: 4px; 
                font-weight: 500; 
                font-size: 13px; 
            }
            QTabBar::tab:selected { 
                color: #3b82f6; 
                border-bottom: 2px solid #3b82f6; 
            }
            QTabBar::tab:hover:!selected { 
                color: #1e293b; 
                border-bottom: 2px solid #cbd5e1; 
            }
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

        if hasattr(self, '_last_inner_tab_index') and self._last_inner_tab_index < tab_widget.count():
            tab_widget.setCurrentIndex(self._last_inner_tab_index)

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
        from .tabs.columns_tab import ColumnsTab
        return ColumnsTab(data, self)

    def _create_constraints_tab(self, data):
        from .tabs.constraints_tab import ConstraintsTab
        return ConstraintsTab(data)

    def _create_sql_tab(self, data):
        from .tabs.sql_tab import SqlTab
        return SqlTab(data)

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
