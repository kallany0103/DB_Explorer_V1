# widgets/inspector/statistics_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication
)
from PySide6.QtCore import Qt
from dialogs.statistics.stats_tab import StatisticsTab
from dialogs.properties import pg_queries
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
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.header_label = QLabel("Statistics")
        self.header_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1f2937;")
        layout.addWidget(self.header_label)
        
        self.sub_label = QLabel("Select an object from the tree to view its statistics")
        self.sub_label.setStyleSheet("color: #6b7280; font-size: 10pt;")
        layout.addWidget(self.sub_label)
        
        self.stats_view = StatisticsTab()
        layout.addWidget(self.stats_view)

    def update_view(self, item_data, obj_name):
        self.item_data = item_data
        self.obj_name = obj_name
        self.header_label.setText(f"Statistics - {obj_name}")
        
        db_type = item_data.get('db_type')
        if db_type != 'postgres':
            self.sub_label.setText("Statistics are currently only available for PostgreSQL")
            return

        self.sub_label.setText(f"Type: {item_data.get('type', 'Unknown').capitalize()}")
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        conn = None
        try:
            # For schema items, conn_data is a sub-dict. For connection items, it's the item_data itself.
            conn_data = item_data.get('conn_data') or item_data
            pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()

            obj_type = item_data.get('type')
            table_type = item_data.get('table_type', '').upper()
            schema_name = item_data.get('schema_name', 'public')

            if obj_type == 'connection':
                db_name = conn_data.get('database')
                if db_name:
                    self.stats_view.load_stats(cursor, pg_queries.GET_DATABASE_STATS, (db_name,))
                else:
                    self.sub_label.setText("Database name not found for statistics.")
            elif obj_type == 'table' or 'TABLE' in table_type or 'VIEW' in table_type:
                self.stats_view.load_stats(cursor, pg_queries.GET_TABLE_SIZE_STATS, (schema_name, obj_name))
                self.stats_view.load_stats(cursor, pg_queries.GET_TABLE_STATS, (schema_name, obj_name), append=True)
            elif obj_type == 'schema' or item_data.get('group_name') == 'Schemas':
                self.stats_view.load_stats(cursor, pg_queries.GET_SCHEMA_STATS, (obj_name, obj_name, obj_name))
            elif 'FUNCTION' in table_type:
                func_name = obj_name.split('(')[0]
                self.stats_view.load_stats(cursor, pg_queries.GET_FUNCTION_STATS, (schema_name, func_name))
            elif 'SEQUENCE' in table_type:
                self.stats_view.load_stats(cursor, pg_queries.GET_SEQUENCE_STATS, (schema_name, obj_name))

        except Exception as e:
            self.sub_label.setText(f"Error loading statistics: {e}")
        finally:
            if conn:
                conn.close()
            QApplication.restoreOverrideCursor()
