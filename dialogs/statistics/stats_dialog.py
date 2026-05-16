# dialogs/statistics/stats_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from .stats_tab import StatisticsTab
from dialogs.properties import pg_queries

class ObjectStatisticsDialog(QDialog):
    def __init__(self, item_data, obj_name, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.obj_name = obj_name
        # The manager is often passed as the parent in this app
        self.manager = parent 
        self.db_type = item_data.get('db_type', 'postgres')
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
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def load_data(self):
        if self.db_type != 'postgres':
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        conn = None
        try:
            conn = self.manager.connection_actions.get_connection(self.item_data)
            cursor = conn.cursor()

            obj_type = self.item_data.get('type')
            table_type = self.item_data.get('table_type', '').upper()

            if obj_type == 'table' or 'TABLE' in table_type or 'VIEW' in table_type or 'MATERIALIZED VIEW' in table_type:
                self.stats_view.load_stats(cursor, pg_queries.GET_TABLE_SIZE_STATS, (self.schema_name, self.obj_name))
                self.stats_view.load_stats(cursor, pg_queries.GET_TABLE_STATS, (self.schema_name, self.obj_name), append=True)
            elif obj_type == 'schema' or self.item_data.get('group_name') == 'Schemas':
                self.stats_view.load_stats(cursor, pg_queries.GET_SCHEMA_STATS, (self.obj_name, self.obj_name, self.obj_name))
            elif 'FUNCTION' in table_type:
                func_name = self.obj_name.split('(')[0]
                self.stats_view.load_stats(cursor, pg_queries.GET_FUNCTION_STATS, (self.schema_name, func_name))
            elif 'SEQUENCE' in table_type:
                self.stats_view.load_stats(cursor, pg_queries.GET_SEQUENCE_STATS, (self.schema_name, self.obj_name))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load statistics:\n{e}")
        finally:
            if conn:
                conn.close()
            QApplication.restoreOverrideCursor()
