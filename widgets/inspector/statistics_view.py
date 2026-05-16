# widgets/inspector/statistics_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QProgressBar, QFrame, QPushButton
)
from PySide6.QtCore import Qt
from dialogs.statistics.stats_tab import StatisticsTab
from workers.inspector_workers import InspectorWorker
import qtawesome as qta
import db

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
        header_frame.setStyleSheet("background-color: white; border-bottom: 1px solid #e5e7eb;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(qta.icon('mdi.chart-bar', color='#3b82f6').pixmap(24, 24))
        header_layout.addWidget(self.icon_label)
        
        text_layout = QVBoxLayout()
        self.header_label = QLabel("Statistics")
        self.header_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")
        self.sub_label = QLabel("Select an object to view statistics")
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
        
        layout.addWidget(header_frame)
        
        # Content
        self.content_container = QWidget()
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        
        self.stats_view = StatisticsTab()
        self.content_layout.addWidget(self.stats_view)
        
        layout.addWidget(self.content_container)

    def update_view(self, item_data, obj_name):
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(f"Statistics - {obj_name}")
        
        db_type = item_data.get('db_type')
        if db_type != 'postgres':
            self.sub_label.setText("Statistics are only available for PostgreSQL")
            return

        self.sub_label.setText(f"Type: {item_data.get('type', 'Unknown').capitalize()}")
        
        self.progress.setVisible(True)
        self.stats_view.clear_stats()
        
        worker = InspectorWorker(item_data, obj_name, task_type="statistics")
        worker.signals.finished.connect(self._on_stats_loaded)
        worker.signals.error.connect(self._on_load_error)
        self.main_window.thread_pool.start(worker)

    def _on_stats_loaded(self, data):
        self.progress.setVisible(False)
        stats_results = data.get("stats", [])
        
        first = True
        for result in stats_results:
            # We need to manually populate the stats_view since load_stats is designed for sync execution
            # but we can simulate it or update StatisticsTab to handle raw data
            self._populate_stats_tab(result, append=not first)
            first = False

    def _on_load_error(self, error_msg):
        self.progress.setVisible(False)
        self.sub_label.setText(f"Error: {error_msg}")

    def _populate_stats_tab(self, result, append=False):
        # Accessing private or internal methods of StatisticsTab if needed, 
        # but let's assume we can pass data to it.
        # Looking at StatisticsTab.load_stats, it takes a cursor. 
        # I'll update StatisticsTab to handle raw data.
        self.stats_view.display_data(result["columns"], result["rows"], append=append)
