from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, 
                                QTableWidget, QTableWidgetItem, QHeaderView, 
                                QFrame, QSplitter, QLineEdit, QCheckBox, 
                                QPushButton, QAbstractItemView, QMessageBox,QHBoxLayout,
                                QPlainTextEdit)
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, Slot
import qtawesome as qta
import db
from db.db_modifications import terminate_postgres_backend, cancel_postgres_backend

class StateWorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(object)

class StateWorker(QRunnable):
    def __init__(self, conn_data, active_only=False):
        super().__init__()
        self.conn_data = conn_data
        self.active_only = active_only
        self.signals = StateWorkerSignals()

    @Slot()
    def run(self):
        try:
            state = db.get_postgres_state_details(self.conn_data, self.active_only)
            try:
                self.signals.finished.emit(state)
            except RuntimeError:
                pass 
        except Exception as e:
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass

class DetailsPanel(QFrame):
    def __init__(self, data_dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QLabel {
                font-weight: 600;
                color: #334155;
                border: none;
                background: transparent;
            }
            QLineEdit, QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 6px;
                color: #0f172a;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header with Tab-like appearance
        tab_header = QFrame()
        tab_header.setFixedHeight(35)
        tab_header.setStyleSheet("background: transparent; border: none; border-bottom: 2px solid #3b82f6;")
        th_lay = QHBoxLayout(tab_header)
        th_lay.setContentsMargins(0, 0, 0, 0)
        lbl_tab = QLabel("Details")
        lbl_tab.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 14px; padding: 0 10px;")
        th_lay.addWidget(lbl_tab)
        th_lay.addStretch()
        layout.addWidget(tab_header)
        
        # Grid-like form
        form_container = QWidget()
        form_lay = QVBoxLayout(form_container)
        form_lay.setContentsMargins(0, 10, 0, 0)
        form_lay.setSpacing(10)
        
        def create_field(label_text, value):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(140)
            edit = QLineEdit(str(value) if value is not None else "")
            edit.setReadOnly(True)
            row.addWidget(lbl)
            row.addWidget(edit)
            return row

        form_lay.addLayout(create_field("Backend type", data_dict.get("Backend type")))
        form_lay.addLayout(create_field("Query started at", data_dict.get("Query start")))
        form_lay.addLayout(create_field("Last state changed at", data_dict.get("State change")))
        
        sql_lbl = QLabel("SQL")
        form_lay.addWidget(sql_lbl)
        
        self.sql_view = QPlainTextEdit()
        self.sql_view.setPlainText(data_dict.get("SQL", ""))
        self.sql_view.setReadOnly(True)
        self.sql_view.setMinimumHeight(150)
        form_lay.addWidget(self.sql_view)
        
        layout.addWidget(form_container)
        layout.addStretch()

class TableFrame(QFrame):
    def __init__(self, title, has_checkbox=False, parent=None):
        super().__init__(parent)
        self.setObjectName("TableFrame")
        self.setStyleSheet("#TableFrame { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; }")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.header = QFrame()
        self.header.setFixedHeight(45)
        self.header.setStyleSheet("QFrame { background-color: #f9fafb; border: none; border-bottom: 1px solid #e5e7eb; border-top-left-radius: 6px; border-top-right-radius: 6px; }")
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(12, 0, 12, 0)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")
        h_lay.addWidget(self.title_label)
        h_lay.addStretch()

        if has_checkbox:
            self.checkbox = QCheckBox("Active sessions only")
            self.checkbox.setStyleSheet("font-size: 13px; color: #4b5563;")
            h_lay.addWidget(self.checkbox)
            h_lay.addSpacing(15)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(200)
        self.search_input.setStyleSheet("QLineEdit { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1f2937; }")
        h_lay.addWidget(self.search_input)

        self.layout.addWidget(self.header)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #e5e7eb; border: none; font-size: 13px; }
            QHeaderView::section { background-color: #f8f9fa; color: #000000; padding: 10px; border: none; border-right: 1px solid #d1d5db; border-bottom: 2px solid #d1d5db; font-weight: 600; font-size: 11px; text-transform: uppercase; }
        """)
        
        self.layout.addWidget(self.table)

class StateWidget(QWidget):
    # Signal to request manual refresh from parent
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn_data = None
        self.expanded_pids = set()
        self.last_state_data = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.setSpacing(5)

        # Top Toolbar for State-specific refresh
        self.toolbar = QFrame()
        self.toolbar.setFixedHeight(30)
        self.toolbar.setStyleSheet("background-color: transparent; border: none;")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar_layout.addStretch()
        
        self.auto_refresh_cb = QCheckBox("Auto-refresh")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.setStyleSheet("font-size: 12px; color: #475569;")
        toolbar_layout.addWidget(self.auto_refresh_cb)
        
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(qta.icon('mdi.refresh'))
        self.refresh_btn.setToolTip("Refresh Sessions")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setStyleSheet("""
            QPushButton { border: 1px solid #e2e8f0; border-radius: 4px; background: white; }
            QPushButton:hover { background: #f1f5f9; }
        """)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        toolbar_layout.addWidget(self.refresh_btn)
        
        layout.addWidget(self.toolbar)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #e5e7eb; }")
        
        self.sessions_frame = TableFrame("Sessions", has_checkbox=True)
        self.sessions_table = self.sessions_frame.table
        self.active_checkbox = self.sessions_frame.checkbox
        self.sessions_frame.search_input.textChanged.connect(self._on_search)
        self.splitter.addWidget(self.sessions_frame)

        self.locks_frame = TableFrame("Locks")
        self.locks_table = self.locks_frame.table
        self.locks_frame.search_input.textChanged.connect(self._on_search)
        self.splitter.addWidget(self.locks_frame)

        # self.prepared_frame = TableFrame("Prepared Transactions")
        # self.prepared_table = self.prepared_frame.table
        # self.prepared_frame.search_input.textChanged.connect(self._on_search)
        # self.splitter.addWidget(self.prepared_frame)

        layout.addWidget(self.splitter)
        self.splitter.setSizes([400, 250, 150])

    def _on_search(self):
        # Trigger refresh to apply filters properly across expanded rows
        if self.last_state_data:
            self.update_state(self.last_state_data)

    def update_state(self, state_data):
        self.last_state_data = state_data
        self.sessions_table.setUpdatesEnabled(False)
        try:
            self._fill_table(self.sessions_table, state_data.get("sessions", {}), is_sessions=True)
            self._fill_table(self.locks_table, state_data.get("locks", {}))
            # self._fill_table(self.prepared_table, state_data.get("prepared", {}))
        finally:
            self.sessions_table.setUpdatesEnabled(True)

    def _fill_table(self, table, data_dict, is_sessions=False):
        columns = data_dict.get("columns", [])
        data = data_dict.get("data", [])
        
        detail_cols = ["Backend type", "Query start", "State change", "SQL"]
        display_cols = [i for i, c in enumerate(columns) if c not in detail_cols]
        
        header_labels = []
        offset = 0
        if is_sessions:
            header_labels = ["Terminate", "Cancel", "Details"]
            offset = 3
        
        for idx in display_cols:
            header_labels.append(columns[idx])
        
        # Preserve scroll
        v_scroll = table.verticalScrollBar().value()
        h_scroll = table.horizontalScrollBar().value()
        
        search_text = ""
        parent_frame = table.parent()
        if parent_frame:
            search_input = parent_frame.findChild(QLineEdit)
            if search_input:
                search_text = search_input.text().lower()

        table.setRowCount(0)
        table.setColumnCount(len(header_labels))
        table.setHorizontalHeaderLabels(header_labels)
        
        # Pre-process expanded PIDs to ensure they are all ints
        expanded_pids_int = {int(p) for p in self.expanded_pids}

        for row_data in data:
            if not row_data: continue
            pid = int(row_data[0]) if row_data[0] is not None else None
            
            # Check filter
            if search_text:
                match = False
                for val in row_data:
                    if val is not None and search_text in str(val).lower():
                        match = True
                        break
                if not match: continue

            row_idx = table.rowCount()
            table.insertRow(row_idx)
            
            row_map = {columns[i]: row_data[i] for i in range(len(columns))}
            
            if is_sessions and pid is not None:
                # Actions
                self._add_action_btn(table, row_idx, 0, 'fa5s.times', "#ef4444", "Terminate", pid, self.handle_terminate)
                self._add_action_btn(table, row_idx, 1, 'fa5s.stop', "#1f2937", "Cancel", pid, self.handle_cancel)
                
                is_expanded = pid in expanded_pids_int
                icon = 'fa5s.chevron-down' if is_expanded else 'fa5s.chevron-right'
                self._add_action_btn(table, row_idx, 2, icon, "#64748b", "Details", pid, self.toggle_details)
                
                # Data
                for i, col_idx in enumerate(display_cols):
                    val = row_data[col_idx]
                    table.setItem(row_idx, i + offset, QTableWidgetItem(str(val) if val is not None else ""))
                
                if is_expanded:
                    det_idx = table.rowCount()
                    table.insertRow(det_idx)
                    panel = DetailsPanel(row_map)
                    table.setCellWidget(det_idx, 0, panel)
                    table.setSpan(det_idx, 0, 1, table.columnCount())
                    table.setRowHeight(det_idx, 400)
            else:
                for i, col_idx in enumerate(display_cols):
                    val = row_data[col_idx]
                    table.setItem(row_idx, i + offset, QTableWidgetItem(str(val) if val is not None else ""))

        # Widths
        header = table.horizontalHeader()
        if is_sessions:
            header.resizeSection(0, 70)
            header.resizeSection(1, 60)
            header.resizeSection(2, 60)
            for i in range(3, table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        else:
            for i in range(table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        table.verticalScrollBar().setValue(v_scroll)
        table.horizontalScrollBar().setValue(h_scroll)

    def _add_action_btn(self, table, row, col, icon_name, color, tooltip, pid, callback):
        btn = QPushButton()
        btn.setIcon(qta.icon(icon_name, color=color))
        btn.setToolTip(tooltip)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet("QPushButton { border: none; background: transparent; } QPushButton:hover { background: #f1f5f9; border-radius: 4px; }")
        # Use pid=pid to ensure the value is captured correctly
        btn.clicked.connect(lambda checked=False, p=pid: callback(p))
        
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(btn)
        table.setCellWidget(row, col, w)

    def toggle_details(self, pid):
        if pid in self.expanded_pids:
            self.expanded_pids.remove(pid)
        else:
            self.expanded_pids.add(pid)
        
        if self.last_state_data:
            self.update_state(self.last_state_data)

    def handle_terminate(self, pid):
        if not self.conn_data: return
        success, msg = terminate_postgres_backend(self.conn_data, pid)
        if not success:
            QMessageBox.warning(self, "Termination Failed", f"Could not terminate backend {pid}:\n\n{msg}")

    def handle_cancel(self, pid):
        if not self.conn_data: return
        success, msg = cancel_postgres_backend(self.conn_data, pid)
        if not success:
            QMessageBox.warning(self, "Cancellation Failed", f"Could not cancel query for backend {pid}:\n\n{msg}")
