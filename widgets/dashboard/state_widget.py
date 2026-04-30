from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, 
                                QTableWidget, QTableWidgetItem, QHeaderView, 
                                QFrame, QSplitter)
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, Slot
import db

class StateWorkerSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)

class StateWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = StateWorkerSignals()

    @Slot()
    def run(self):
        try:
            state = db.get_postgres_state_details(self.conn_data)
            self.signals.finished.emit(state)
        except Exception as e:
            self.signals.error.emit(str(e))

class StateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Sessions Table
        self.sessions_frame = self.create_table_frame("Sessions / Activity")
        self.sessions_table = self.sessions_frame.table
        self.splitter.addWidget(self.sessions_frame)

        # 2. Locks Table
        self.locks_frame = self.create_table_frame("Locks")
        self.locks_table = self.locks_frame.table
        self.splitter.addWidget(self.locks_frame)

        # 3. Prepared Transactions Table
        self.prepared_frame = self.create_table_frame("Prepared Transactions")
        self.prepared_table = self.prepared_frame.table
        self.splitter.addWidget(self.prepared_frame)

        layout.addWidget(self.splitter)
        
        # Set initial sizes
        self.splitter.setSizes([400, 200, 100])

    def create_table_frame(self, title):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: none;
            }
        """)
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(10, 10, 10, 10)
        
        header = QLabel(title)
        header.setStyleSheet("color: #111827; font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        flay.addWidget(header)
        
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                color: #1f2937;
                gridline-color: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                selection-background-color: #e5edff;
                selection-color: #2563eb;
                alternate-background-color: #f9fafb;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                color: #4b5563;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #d1d5db;
                border-right: 1px solid #d1d5db;
                font-weight: bold;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f1f1;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 20px;
                border-radius: 5px;
            }
        """)
        
        flay.addWidget(table)
        frame.table = table
        return frame

    def update_state(self, state_data):
        self._fill_table(self.sessions_table, state_data.get("sessions", {}))
        self._fill_table(self.locks_table, state_data.get("locks", {}))
        self._fill_table(self.prepared_table, state_data.get("prepared", {}))

    def _fill_table(self, table, data_dict):
        columns = data_dict.get("columns", [])
        data = data_dict.get("data", [])
        
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([c.replace("_", " ").title() for c in columns])
        
        table.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value) if value is not None else "")
                table.setItem(row_idx, col_idx, item)
        
        # Adjust column widths if it's the first time or if data is small
        if table.rowCount() > 0:
            header = table.horizontalHeader()
            for i in range(len(columns)):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                if header.sectionSize(i) > 300:
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                    header.resizeSection(i, 300)
