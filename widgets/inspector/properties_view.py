# widgets/inspector/properties_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QTabWidget, QToolButton
)
from PySide6.QtCore import QSize, Qt
from .tabs.columns_tab import ColumnsTab
from .tabs.constraints_tab import ConstraintsTab
from .tabs.sql_tab import SqlTab
import qtawesome as qta
from ui.icons import get_icon, get_database_icon
from workers.inspector_workers import InspectorWorker
from ui.components import IconButton
from .properties_ui import (
    CollapsibleCard, CollectionCard, HIDDEN_PROPERTY_KEYS, PROPERTY_LABELS
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
        header_frame.setObjectName("propertiesHeaderFrame")
        header_frame.setStyleSheet("""
            QFrame#propertiesHeaderFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e2e8f0;
            }
            QFrame#propertiesHeaderFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("border: none; background: transparent;")
        header_layout.addWidget(self.icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.header_label = QLabel("Properties")
        self.header_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827; border: none; background: transparent;")
        self.sub_label = QLabel("Select an object to view properties")
        self.sub_label.setStyleSheet("font-size: 11px; color: #6b7280; border: none; background: transparent;")
        text_layout.addWidget(self.header_label)
        text_layout.addWidget(self.sub_label)
        header_layout.addLayout(text_layout)
        
        header_layout.addStretch()
        

        
        self.refresh_btn = IconButton(get_icon('msc.refresh', color='#6b7280'), tooltip="Refresh")
        self.refresh_btn.clicked.connect(self.refresh_properties)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(header_frame)
        
        self.loading_icon = QToolButton()
        self.loading_icon.setIcon(
            qta.icon(
                "ph.spinner-fill",
                color="#3b82f6",
                animation=qta.Spin(self.loading_icon)
            )
        )
        self.loading_icon.setIconSize(QSize(100, 100))
        self.loading_icon.setStyleSheet("border: none; background: transparent;")
        
        self.progress_container = QWidget()
        progress_layout = QVBoxLayout(self.progress_container)
        progress_layout.addStretch()
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(self.loading_icon)
        h_layout.addStretch()
        progress_layout.addLayout(h_layout)
        progress_layout.addStretch()
        
        layout.addWidget(self.progress_container)
        self.progress_container.setVisible(False)
        
        self.setObjectName("propertiesWorkbench")

        self.scroll = QScrollArea()
        self.scroll.setObjectName("propertiesScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        self.container = QWidget()
        self.container.setObjectName("propertiesContainer")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    @property
    def progress(self):
        """Backward-compatible alias for progress_container."""
        return self.progress_container

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for card in self.findChildren(CollectionCard):
            card._update_table_geometry()
        for sql_tab in self.findChildren(SqlTab):
            sql_tab._update_editor_geometry()

    def refresh_properties(self):
        if self.item_data:
            self.update_view(self.item_data, self.obj_name, force_refresh=True)

    def show_empty_state(self, message="Select an object to view properties"):
        """Show an empty state without the loading spinner."""
        self.item_data = None
        self.obj_name = None
        self.header_label.setText("Properties")
        self.sub_label.setText(message)
        self.icon_label.setPixmap(
            get_icon('msc.package', color='#94a3b8').pixmap(24, 24)
        )
        self._clear_container()
        self.loading_icon.setVisible(False)
        self.progress_container.setVisible(True)
        self.scroll.setVisible(False)

    def show_loading(self, message="Loading..."):
        """Show the spinner with a message — used when the inspector is loading data."""
        self.item_data = None
        self.obj_name = None
        self.header_label.setText("Properties")
        self.sub_label.setText(message)
        self.icon_label.setPixmap(
            get_icon('msc.package', color='#94a3b8').pixmap(24, 24)
        )
        self._clear_container()
        self.loading_icon.setVisible(True)
        self.progress_container.setVisible(True)
        self.scroll.setVisible(False)

    def update_view(self, item_data, obj_name, force_refresh=False):
        if not force_refresh and self.item_data == item_data and self.obj_name == obj_name:
            return
            
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(obj_name)
        
        obj_type = item_data.get('type', 'Unknown')
        table_type = str(item_data.get('table_type', '')).upper()
        group_name = item_data.get('group_name')

        if "MATERIALIZED" in table_type and group_name != "Materialized Views":
            obj_type = "materialized_view"
        elif "TRIGGER" in table_type and group_name != "Trigger Functions":
            obj_type = "trigger_function"
        elif "FUNCTION" in table_type and group_name != "Functions":
            obj_type = "function"
        elif "SEQUENCE" in table_type and group_name != "Sequences":
            obj_type = "sequence"
        elif "VIEW" in table_type and group_name != "Views" and "MATERIALIZED" not in table_type:
            obj_type = "view"
        elif item_data.get('table_name') and obj_type in ("schema_group", "group"):
            obj_type = "table"
        if not group_name and obj_type.endswith('_root'):
            if obj_type == 'schemas_root':
                group_name = "Schemas"
            elif obj_type == 'tables_root':
                group_name = "Tables"
            elif obj_type == 'views_root':
                group_name = "Views"
            elif obj_type == 'functions_root':
                group_name = "Functions"
            elif obj_type == 'fdw_root':
                group_name = "Foreign Data Wrappers"
            elif obj_type == 'extension_root':
                group_name = "Extensions"
            elif obj_type == 'language_root':
                group_name = "Languages"

        icon_color = '#6366f1'
        icon_name = 'msc.package'
        if obj_type in ('materialized_view', 'matview') or group_name == 'Materialized Views':
            icon_name, icon_color = 'msc.eye', '#0284c7'
        elif obj_type == 'trigger_function' or group_name == 'Trigger Functions':
            icon_name, icon_color = 'msc.symbol-method', '#f59e0b'
        elif obj_type == 'table' or group_name == 'Tables':
            icon_name, icon_color = 'msc.table', '#3b82f6'
        elif obj_type == 'view' or group_name == 'Views':
            icon_name, icon_color = 'msc.eye', '#10b981'
        elif obj_type == 'schema' or obj_type == 'schemas_root' or group_name == 'Schemas':
            icon_name, icon_color = 'msc.folder-library', '#f59e0b'
        elif obj_type == 'connection':
            icon_name, icon_color = None, None
            self.icon_label.setPixmap(get_database_icon(item_data).pixmap(24, 24))
        elif obj_type == 'function' or group_name == 'Functions':
            icon_name, icon_color = 'msc.symbol-method', '#ec4899'
        elif obj_type == 'sequence' or group_name == 'Sequences':
            icon_name, icon_color = 'msc.symbol-numeric', '#8b5cf6'
        elif obj_type in ('fdw', 'fdw_root') or group_name in ('Foreign Data Wrappers', 'FDW'):
            icon_name, icon_color = 'msc.plug', '#0ea5e9'
        elif obj_type in ('language', 'language_root') or group_name in ('Languages', 'Java'):
            icon_name, icon_color = 'msc.code', '#8b5cf6'
        elif obj_type == 'trigger' or group_name == 'Triggers':
            tgenabled = item_data.get('tgenabled')
            if tgenabled == 'D':
                icon_name, icon_color = 'msc.zap', '#9fa6b2'
            else:
                icon_name, icon_color = 'msc.zap', '#f59e0b'
        elif group_name or obj_type in ('group', 'schema_group'):
            icon_name, icon_color = 'msc.folder', '#94a3b8'

        if icon_name:
            self.icon_label.setPixmap(get_icon(icon_name, color=icon_color).pixmap(24, 24))

        conn_data = item_data.get('conn_data') or {}
        db_name = conn_data.get('database') or item_data.get('database')
        schema_name = item_data.get('schema_name')

        if obj_type.endswith('_root'):
            clean_group = group_name or obj_type.replace('_root', '').capitalize()
            self.sub_label.setText(f"Collection • {clean_group}")
        elif obj_type in ('group', 'schema_group', 'oracle_schema_group') or (group_name and not item_data.get('table_name')):
            target = group_name or "Collection"
            sub = f"Collection • {target}"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type == 'schema':
            sub = "Schema"
            if db_name:
                sub += f" • Database: {db_name}"
            self.sub_label.setText(sub)
        elif obj_type in ('materialized_view', 'matview'):
            sub = "Materialized View"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type == 'trigger_function':
            sub = "Trigger Function"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type == 'function':
            sub = "Function"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type == 'fdw':
            self.sub_label.setText("Foreign Data Wrapper")
        elif obj_type == 'language':
            self.sub_label.setText("Language")
        elif obj_type == 'table':
            sub = "Table"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type == 'view':
            sub = "View"
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        elif obj_type != 'Unknown':
            sub = obj_type.replace('_', ' ').capitalize()
            if schema_name:
                sub += f" • Schema: {schema_name}"
            self.sub_label.setText(sub)
        else:
            self.sub_label.setText(group_name or "Object")
        
        # Save the current inner tab index before clearing
        for i in range(self.container_layout.count()):
            widget = self.container_layout.itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                self._last_inner_tab_index = widget.currentIndex()
                break

        self._clear_container()
        
        if not item_data:
            return
        
        self.loading_icon.setVisible(True)
        self.progress_container.setVisible(True)
        self.scroll.setVisible(False)
        worker = InspectorWorker(item_data, obj_name, task_type="properties")
        worker.signals.finished.connect(self._on_data_loaded)
        worker.signals.error.connect(self._on_load_error)
        self.main_window.thread_pool.start(worker)

    def _on_data_loaded(self, data):
        self.progress_container.setVisible(False)
        self.scroll.setVisible(True)
        self._clear_container()
        
        if data.get("type") == "group":
            self._display_group(data)
        else:
            self._display_object(data)

    def _on_load_error(self, error_msg):
        self.progress_container.setVisible(False)
        self.scroll.setVisible(True)
        self.container_layout.addWidget(QLabel(f"Error: {error_msg}"))

    def _display_group(self, data):
        group_name = data.get("group_name", "Collection")
        group_widget = QWidget()
        group_layout = QVBoxLayout(group_widget)
        group_layout.setContentsMargins(16, 16, 16, 16)
        group_layout.setSpacing(12)

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        card = CollectionCard(group_name, columns, rows)
        group_layout.addWidget(card)
        group_layout.addStretch()
        self.container_layout.addWidget(group_widget)

    def _display_object(self, data):
        obj_type = self.item_data.get('type', 'Unknown')
        table_type = str(self.item_data.get('table_type', '')).upper()
        group_name = self.item_data.get('group_name')

        if "MATERIALIZED" in table_type and group_name != "Materialized Views":
            obj_type = "materialized_view"
        elif "TRIGGER" in table_type and group_name != "Trigger Functions":
            obj_type = "trigger_function"
        elif "FUNCTION" in table_type and group_name != "Functions":
            obj_type = "function"
        elif "SEQUENCE" in table_type and group_name != "Sequences":
            obj_type = "sequence"
        elif "VIEW" in table_type and group_name != "Views" and "MATERIALIZED" not in table_type:
            obj_type = "view"
        elif self.item_data.get('table_name') and obj_type in ("schema_group", "group"):
            obj_type = "table"

        details = data.get("details", {})
        columns = data.get("columns", [])
        sql = data.get("sql", "")

        # If data has no properties, columns, or SQL
        if not details and not columns and not sql:
            self._display_empty_object()
            return

        is_matview = (
            obj_type in ('materialized_view', 'matview')
            or "MATERIALIZED" in table_type
            or details.get("Object type") == "Materialized view"
        )
        is_view = (
            obj_type == 'view'
            or ("VIEW" in table_type and not is_matview)
            or details.get("Object type") == "View"
        )

        if is_matview or is_view:
            self._display_materialized_view_with_tabs(data)
        elif obj_type == 'table':
            self._display_table_with_tabs(data)
        elif obj_type == 'schema':
            self._display_schema_with_tabs(data)
        else:
            self._display_object_with_tabs(data)

    def _display_materialized_view_with_tabs(self, data):
        tab_widget = QTabWidget()
        tab_widget.setObjectName("explain_tabs")

        # General Tab
        general_tab = self._create_general_tab(data)
        tab_widget.addTab(general_tab, "General")

        # Columns Tab (read-only)
        if data.get("columns"):
            columns_tab = self._create_columns_tab(data)
            tab_widget.addTab(columns_tab, "Columns")

        # SQL Tab
        if data.get("sql"):
            sql_tab = self._create_sql_tab(data)
            tab_widget.addTab(sql_tab, "SQL")

        self.container_layout.addWidget(tab_widget)

        if hasattr(self, '_last_inner_tab_index') and self._last_inner_tab_index < tab_widget.count():
            tab_widget.setCurrentIndex(self._last_inner_tab_index)

    def _display_empty_object(self):
        empty_widget = QWidget()
        layout = QVBoxLayout(empty_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("propertyCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 36, 24, 36)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(get_icon('msc.info', color='#94a3b8').pixmap(36, 36))
        icon_label.setStyleSheet("border: none; background: transparent;")
        card_layout.addWidget(icon_label)

        title = QLabel(f"No properties available for '{self.obj_name}'")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 11pt; font-weight: 600; color: #334155; border: none; background: transparent;")
        card_layout.addWidget(title)

        sub = QLabel("The database did not return any metadata or properties for this object.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("font-size: 9pt; color: #64748b; border: none; background: transparent;")
        card_layout.addWidget(sub)

        layout.addWidget(card)
        layout.addStretch()
        self.container_layout.addWidget(empty_widget)

    def _display_table_with_tabs(self, data):
        tab_widget = QTabWidget()
        tab_widget.setObjectName("explain_tabs")
        
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

    def _display_schema_with_tabs(self, data):
        tab_widget = QTabWidget()
        tab_widget.setObjectName("explain_tabs")

        # General Tab
        general_tab = self._create_general_tab(data)
        tab_widget.addTab(general_tab, "General")

        # Tables Tab (if schema contains tables)
        tables_data = data.get("tables", {})
        if tables_data.get("rows"):
            tables_tab = QWidget()
            t_layout = QVBoxLayout(tables_tab)
            t_layout.setContentsMargins(16, 16, 16, 16)
            t_layout.setSpacing(12)
            t_card = CollectionCard("Tables", tables_data.get("columns", []), tables_data.get("rows", []))
            t_layout.addWidget(t_card)
            t_layout.addStretch()
            tab_widget.addTab(tables_tab, "Tables")

        # SQL Tab
        if data.get("sql"):
            sql_tab = self._create_sql_tab(data)
            tab_widget.addTab(sql_tab, "SQL")

        self.container_layout.addWidget(tab_widget)

        if hasattr(self, '_last_inner_tab_index') and self._last_inner_tab_index < tab_widget.count():
            tab_widget.setCurrentIndex(self._last_inner_tab_index)

    def _display_object_with_tabs(self, data):
        tab_widget = QTabWidget()
        tab_widget.setObjectName("explain_tabs")

        general_tab = self._create_general_tab(data)
        tab_widget.addTab(general_tab, "General")

        obj_type = self.item_data.get('type', '')
        if obj_type != 'connection' and data.get("sql"):
            sql_tab = self._create_sql_tab(data)
            tab_widget.addTab(sql_tab, "SQL")

        self.container_layout.addWidget(tab_widget)

        if hasattr(self, '_last_inner_tab_index') and self._last_inner_tab_index < tab_widget.count():
            tab_widget.setCurrentIndex(self._last_inner_tab_index)

    def _create_general_tab(self, data):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        
        details = data.get("details", {})
        gen = CollapsibleCard("General")
        gen.add_row("Name", self.obj_name)
        for k, v in details.items():
            if k in HIDDEN_PROPERTY_KEYS or k.lower() == "name":
                continue
            label = PROPERTY_LABELS.get(k, k.replace("_", " ").capitalize())
            gen.add_row(label, v)
        layout.addWidget(gen)
        layout.addStretch()
        return widget

    def _create_columns_tab(self, data):
        return ColumnsTab(data, self)

    def _create_constraints_tab(self, data):
        return ConstraintsTab(data)

    def _create_sql_tab(self, data):
        return SqlTab(data, self)

    def _display_object_with_cards(self, data):
        self._display_object_with_tabs(data)

    def _clear_container(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
