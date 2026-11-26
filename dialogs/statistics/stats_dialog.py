# dialogs/statistics/stats_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
import db
from .stats_tab import StatisticsTab
import workers.inspector_stats as inspector_stats
from ui.components import SecondaryButton




class ObjectStatisticsDialog(QDialog):
    def __init__(self, item_data, obj_name, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.obj_name = obj_name
        self.manager = parent 
        conn_data = item_data.get('conn_data') or {}
        self.db_type = (item_data.get('db_type') or conn_data.get('db_type') or '').lower()
        if not self.db_type:
            code = str(conn_data.get("code") or item_data.get("code") or "").upper()
            if "SQLITE" in code or conn_data.get("db_path"):
                self.db_type = "sqlite"
            elif "ORACLE" in code:
                self.db_type = "oracle"
            else:
                self.db_type = "postgres"
        self.schema_name = item_data.get('schema_name', 'public')
        
        self.setWindowTitle(f"Statistics - {self.obj_name}")
        self.resize(600, 500)
        self.setStyleSheet(self.manager._get_dialog_style())

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.stats_view = StatisticsTab()
        layout.addWidget(self.stats_view)
        
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = SecondaryButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def load_data(self):
        if self.db_type not in ('postgres', 'sqlite'):
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        conn = None
        try:
            conn = self.manager.connection_actions.get_connection(self.item_data)
            if not conn and self.db_type == 'sqlite':
                conn_data = self.item_data.get('conn_data') or self.item_data
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
            if not conn:
                raise ConnectionError(f"Failed to connect to {self.db_type} database.")
            cursor = conn.cursor()

            result = inspector_stats.fetch_statistics_results(cursor, self.item_data, self.obj_name)
            first = True
            for item in result.get("stats", []):
                self.stats_view.display_data(item["columns"], item["rows"], append=not first)
                first = False
            if not result.get("stats"):
                self.stats_view.display_data([], [])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load statistics:\n{e}")
        finally:
            if conn:
                conn.close()
            QApplication.restoreOverrideCursor()
