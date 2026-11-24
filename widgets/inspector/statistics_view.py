# widgets/inspector/statistics_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QToolButton
)
from dialogs.statistics.stats_tab import StatisticsTab
from workers.inspector_workers import InspectorWorker
import qtawesome as qta
from ui.icons import get_icon, get_database_icon
from PySide6.QtCore import QSize, QThreadPool
from ui.components import IconButton

class StatisticsWorkbench(QWidget):
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
        
        # Header
        header_frame = QFrame()
        header_frame.setObjectName("statisticsHeaderFrame")
        header_frame.setStyleSheet("""
            QFrame#statisticsHeaderFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e2e8f0;
            }
            QFrame#statisticsHeaderFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("border: none; background: transparent;")
        self.icon_label.setPixmap(get_icon('msc.graph', color='#3b82f6').pixmap(24, 24))
        header_layout.addWidget(self.icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.header_label = QLabel("Statistics")
        self.header_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827; border: none; background: transparent;")
        self.sub_label = QLabel("Select an object to view statistics")
        self.sub_label.setStyleSheet("font-size: 11px; color: #6b7280; border: none; background: transparent;")
        text_layout.addWidget(self.header_label)
        text_layout.addWidget(self.sub_label)
        header_layout.addLayout(text_layout)
        
        header_layout.addStretch()

        
        # Add refresh button to match properties_view
        self.refresh_btn = IconButton(get_icon('msc.refresh', color='#6b7280'), tooltip="Refresh")
        self.refresh_btn.clicked.connect(self.refresh_statistics)
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
        
        # Content
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        
        self.stats_view = StatisticsTab()
        self.content_layout.addWidget(self.stats_view)
        
        layout.addWidget(self.content_container)

    @property
    def progress(self):
        """Backward-compatible alias for progress_container."""
        return self.progress_container

    def refresh_statistics(self, silent=False):
        if self.item_data:
            self.update_view(self.item_data, self.obj_name, force_refresh=True, show_loading=not silent)

    def show_empty_state(self, message="Select an object to view statistics"):
        """Show an empty state without the loading spinner."""
        self.item_data = None
        self.obj_name = None
        self.header_label.setText("Statistics")
        self.sub_label.setText(message)
        self.loading_icon.setVisible(False)
        self.progress_container.setVisible(True)
        self.content_container.setVisible(False)

    def show_loading(self, message="Loading..."):
        """Show the spinner with a message — used when the inspector is loading data."""
        self.item_data = None
        self.obj_name = None
        self.header_label.setText("Statistics")
        self.sub_label.setText(message)
        self.loading_icon.setVisible(True)
        self.progress_container.setVisible(True)
        self.content_container.setVisible(False)

    def update_view(self, item_data, obj_name, force_refresh=False, show_loading=True):
        if not force_refresh and self.item_data == item_data and self.obj_name == obj_name:
            return
            
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(f"Statistics - {obj_name}")

        obj_type = item_data.get('type', 'Unknown')
        group_name = item_data.get('group_name')
        table_type = str(item_data.get('table_type', '')).upper()

        if obj_type == 'connection':
            self.icon_label.setPixmap(get_database_icon(item_data).pixmap(24, 24))
        elif obj_type in ('materialized_view', 'matview') or group_name == 'Materialized Views' or "MATERIALIZED" in table_type:
            self.icon_label.setPixmap(get_icon('msc.eye', color='#0284c7').pixmap(24, 24))
        elif obj_type == 'trigger_function' or group_name == 'Trigger Functions' or "TRIGGER" in table_type:
            self.icon_label.setPixmap(get_icon('msc.symbol-method', color='#f59e0b').pixmap(24, 24))
        elif obj_type == 'table' or group_name == 'Tables' or "TABLE" in table_type:
            self.icon_label.setPixmap(get_icon('msc.table', color='#3b82f6').pixmap(24, 24))
        elif obj_type == 'view' or group_name == 'Views' or "VIEW" in table_type:
            self.icon_label.setPixmap(get_icon('msc.eye', color='#10b981').pixmap(24, 24))
        elif obj_type in ('schema', 'oracle_schema') or group_name == 'Schemas' or obj_type in ('schemas_root', 'oracle_schemas_root'):
            self.icon_label.setPixmap(get_icon('msc.folder-library', color='#f59e0b').pixmap(24, 24))
        elif obj_type in ('function', 'procedure', 'package') or group_name in ('Functions', 'Procedures', 'Packages'):
            self.icon_label.setPixmap(get_icon('msc.symbol-method', color='#ec4899').pixmap(24, 24))
        elif obj_type == 'sequence' or group_name == 'Sequences':
            self.icon_label.setPixmap(get_icon('msc.symbol-numeric', color='#8b5cf6').pixmap(24, 24))
        elif obj_type == 'trigger' or group_name == 'Triggers':
            self.icon_label.setPixmap(get_icon('msc.zap', color='#f59e0b').pixmap(24, 24))
        elif group_name or obj_type in ('group', 'schema_group', 'oracle_schema_group'):
            self.icon_label.setPixmap(get_icon('msc.folder', color='#94a3b8').pixmap(24, 24))
        else:
            self.icon_label.setPixmap(get_database_icon(item_data).pixmap(24, 24))
        
        db_type = (item_data.get('db_type') or '').lower()
        if not db_type:
            conn_data = item_data.get('conn_data') or {}
            db_type = (conn_data.get('db_type') or '').lower()
            if not db_type:
                code = str(conn_data.get("code") or item_data.get("code") or "").upper()
                if "ORACLE" in code:
                    db_type = "oracle"
                elif "POSTGRES" in code:
                    db_type = "postgres"
                elif (
                    conn_data.get('service_name')
                    or conn_data.get('oracle_db_type')
                    or 'oracle' in str(item_data.get('type', '')).lower()
                ):
                    db_type = 'oracle'
                elif conn_data.get('database') or conn_data.get('host'):
                    db_type = 'postgres'

        is_supported = (db_type == 'postgres') or ('oracle' in db_type)
        if not is_supported:
            self.progress_container.setVisible(False)
            self.content_container.setVisible(True)
            self.stats_view.clear_stats()
            self.sub_label.setText("Statistics are only available for PostgreSQL and Oracle")
            return

        self.sub_label.setText(f"Type: {item_data.get('type', 'Unknown').capitalize()}")

        if show_loading:
            self.loading_icon.setVisible(True)
            self.progress_container.setVisible(True)
            self.content_container.setVisible(False)
            self.stats_view.clear_stats()

        worker = InspectorWorker(item_data, obj_name, task_type="statistics")
        worker.signals.finished.connect(self._on_stats_loaded)
        worker.signals.error.connect(self._on_load_error)
        pool = getattr(self.main_window, 'thread_pool', None) or QThreadPool.globalInstance()
        pool.start(worker)

    def _on_stats_loaded(self, data):
        self.progress_container.setVisible(False)
        self.content_container.setVisible(True)
        stats_results = data.get("stats", [])

        if not stats_results:
            self.stats_view.display_data([], [])
            return

        first = True
        for result in stats_results:
            self._populate_stats_tab(result, append=not first)
            first = False

    def _on_load_error(self, error_msg):
        self.progress_container.setVisible(False)
        self.content_container.setVisible(True)
        self.sub_label.setText(f"Error: {error_msg}")
        self.stats_view.clear_stats()
        self.stats_view.display_data(["Error"], [[str(error_msg)]])

    def _populate_stats_tab(self, result, append=False):
        self.stats_view.display_data(result["columns"], result["rows"], append=append)
