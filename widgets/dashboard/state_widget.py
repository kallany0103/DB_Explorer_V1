from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, 
                                QTableWidget, QTableWidgetItem, QHeaderView, 
                                QFrame, QSplitter, QLineEdit, QCheckBox, 
                                QAbstractItemView, QMessageBox, QHBoxLayout,
                                QPlainTextEdit, QApplication)
from PySide6.QtCore import Qt, Signal, QObject, QRunnable, Slot, QSize, QTimer
from ui.icons import get_icon
import db
from db.db_modifications import terminate_postgres_backend, cancel_postgres_backend
from ui.components import SecondaryButton, IconButton




class StateWorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(object)



class StateWorker(QRunnable):
    def __init__(self, conn_data, active_only=False, local_sessions=None):
        super().__init__()
        self.conn_data = conn_data
        self.active_only = active_only
        self.local_sessions = local_sessions
        self.signals = StateWorkerSignals()

    @Slot()
    def run(self):
        try:
            db_type = str(self.conn_data.get("db_type", "")).lower()
            if "sqlite" in db_type:
                state = db.get_sqlite_state_details(self.conn_data, self.local_sessions)
            else:
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
    def __init__(self, data_dict, on_close=None, parent=None):
        super().__init__(parent)
        self.data_dict = data_dict
        self.on_close = on_close
        self.setObjectName("DetailsPanel")
        self.setStyleSheet("""
            QFrame#DetailsPanel {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-left: 3px solid #0284c7;
                border-radius: 6px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(8)

        # ── Header ──
        header_lay = QHBoxLayout()
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)
        
        # PID badge
        pid = data_dict.get("pid")
        pid_lbl = QLabel(f"PID {pid}" if pid is not None else "Session Details")
        pid_lbl.setStyleSheet("""
            background-color: #e2e8f0;
            color: #0f172a;
            font-weight: 700;
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        header_lay.addWidget(pid_lbl)

        # State pill (active/idle)
        state_val = str(data_dict.get("State", "")).strip().lower()
        if state_val:
            is_active = state_val == "active"
            bg = "#dcfce7" if is_active else "#f1f5f9"
            fg = "#15803d" if is_active else "#64748b"
            dot = "● " if is_active else "○ "
            state_pill = QLabel(f"{dot}{state_val.capitalize()}")
            state_pill.setStyleSheet(f"""
                background-color: {bg};
                color: {fg};
                font-weight: 600;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
            """)
            header_lay.addWidget(state_pill)

        # Subtitle: user @ db
        db_usr_parts = []
        if data_dict.get("User"):
            db_usr_parts.append(str(data_dict.get("User")))
        if data_dict.get("Database"):
            db_usr_parts.append(f"@{data_dict.get('Database')}")
        if data_dict.get("Application") and str(data_dict.get("Application")) != "External / Unknown":
            db_usr_parts.append(f"({data_dict.get('Application')})")
        
        if db_usr_parts:
            info_lbl = QLabel(" ".join(db_usr_parts))
            info_lbl.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 500;")
            header_lay.addWidget(info_lbl)

        header_lay.addStretch()

        if self.on_close:
            close_btn = IconButton(get_icon('msc.chevron-up', color="#64748b"), tooltip="Collapse Details")
            close_btn.setFixedSize(22, 22)
            close_btn.setIconSize(QSize(12, 12))
            close_btn.clicked.connect(self.on_close)
            header_lay.addWidget(close_btn)

        layout.addLayout(header_lay)

        # ── Metadata Tiles Grid ──
        tiles_lay = QHBoxLayout()
        tiles_lay.setContentsMargins(0, 0, 0, 0)
        tiles_lay.setSpacing(8)

        def make_tile(title_text, val_text):
            tile = QFrame()
            tile.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 5px;
                }
            """)
            t_lay = QVBoxLayout(tile)
            t_lay.setContentsMargins(8, 5, 8, 5)
            t_lay.setSpacing(2)

            lbl = QLabel(title_text)
            lbl.setStyleSheet("font-size: 9px; font-weight: 700; color: #64748b; border: none; background: transparent; text-transform: uppercase;")
            
            clean_val = str(val_text).strip() if val_text is not None and str(val_text).strip() else "—"
            if len(clean_val) > 19 and ("+" in clean_val or "T" in clean_val):
                clean_val = clean_val[:19].replace("T", " ")
                
            val = QLabel(clean_val)
            val.setStyleSheet("font-size: 11px; font-weight: 600; color: #0f172a; border: none; background: transparent; font-family: 'Consolas', 'Monaco', monospace;")
            
            t_lay.addWidget(lbl)
            t_lay.addWidget(val)
            return tile

        tiles_lay.addWidget(make_tile("Backend Type", data_dict.get("Backend type")), 1)
        tiles_lay.addWidget(make_tile("Query Started", data_dict.get("Query start")), 1)
        tiles_lay.addWidget(make_tile("State Changed", data_dict.get("State change")), 1)
        tiles_lay.addWidget(make_tile("Wait Event", data_dict.get("Wait event")), 1)

        layout.addLayout(tiles_lay)

        # ── SQL Query Section ──
        sql_raw = str(data_dict.get("SQL", "") or "").strip()
        has_real_sql = bool(sql_raw and sql_raw != ";")

        sql_header_lay = QHBoxLayout()
        sql_header_lay.setContentsMargins(0, 2, 0, 0)
        sql_header_lay.setSpacing(6)

        sql_title = QLabel("SQL Statement")
        sql_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase;")
        sql_header_lay.addWidget(sql_title)
        sql_header_lay.addStretch()

        if has_real_sql:
            copy_btn = SecondaryButton(get_icon('msc.copy', color="#475569"), " Copy")
            copy_btn.setFixedHeight(22)
            copy_btn.setIconSize(QSize(12, 12))
            copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #475569;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    border-color: #94a3b8;
                }
            """)
            def do_copy():
                QApplication.clipboard().setText(sql_raw)
                copy_btn.setText(" Copied!")
                QTimer.singleShot(1500, lambda: copy_btn.setText(" Copy"))
            copy_btn.clicked.connect(do_copy)
            sql_header_lay.addWidget(copy_btn)

        layout.addLayout(sql_header_lay)

        self.sql_view = QPlainTextEdit()
        self.sql_view.setReadOnly(True)
        if has_real_sql:
            self.sql_view.setPlainText(sql_raw)
            self.sql_view.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 6px 8px;
                    color: #0f172a;
                    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
                    font-size: 11px;
                }
            """)
        else:
            self.sql_view.setPlaceholderText("No active SQL statement for this session.")
            self.sql_view.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #f8fafc;
                    border: 1px dashed #cbd5e1;
                    border-radius: 4px;
                    padding: 6px 8px;
                    color: #94a3b8;
                    font-style: italic;
                    font-size: 11px;
                }
            """)
        
        layout.addWidget(self.sql_view)

    def preferred_height(self) -> int:
        sql_raw = str(self.data_dict.get("SQL", "") or "").strip()
        if not sql_raw or sql_raw == ";":
            return 200
        lines = sql_raw.count("\n") + 1
        return min(320, max(220, 190 + lines * 16))

class TableFrame(QFrame):
    def __init__(self, title, has_checkbox=False, has_refresh=False, parent=None):
        super().__init__(parent)
        self.setObjectName("TableFrame")
        self.setStyleSheet("#TableFrame { background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; }")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 0, 1, 1)
        self.layout.setSpacing(0)

        self.header = QFrame()
        self.header.setFixedHeight(44)
        self.header.setStyleSheet("QFrame { background-color: #f9fafb; border: none; border-bottom: 1px solid #e5e7eb; border-top-left-radius: 5px; border-top-right-radius: 5px; }")
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(12, 0, 12, 0)
        h_lay.setSpacing(8)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")
        h_lay.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        h_lay.addStretch()

        if has_checkbox:
            self.checkbox = QCheckBox("Active sessions only")
            self.checkbox.setStyleSheet("font-size: 13px; color: #4b5563;")
            self.checkbox.setFixedHeight(28)
            h_lay.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
            h_lay.addSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(180)
        self.search_input.setFixedHeight(28)
        self.search_input.setStyleSheet("QLineEdit { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #1f2937; }")
        h_lay.addWidget(self.search_input, 0, Qt.AlignmentFlag.AlignVCenter)

        self.refresh_btn = None
        if has_refresh:
            self.refresh_btn = SecondaryButton(get_icon('msc.sync', color='#0ea5e9'), " Refresh")
            self.refresh_btn.setFixedHeight(28)
            self.refresh_btn.setIconSize(QSize(14, 14))
            h_lay.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.layout.addWidget(self.header)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setMinimumSectionSize(65)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.table.horizontalHeader().setFixedHeight(32)
        
        self.table.setStyleSheet("""
            QTableWidget { 
                background-color: #ffffff; 
                color: #0f172a; 
                gridline-color: #f1f5f9; 
                border: none; 
                border-bottom-left-radius: 5px; 
                border-bottom-right-radius: 5px; 
                font-size: 12px; 
            }
            QTableWidget::item {
                padding: 2px 6px;
            }
            QHeaderView::section { 
                background-color: #f8fafc; 
                color: #334155; 
                padding: 4px 8px; 
                border: none; 
                border-right: 1px solid #e2e8f0; 
                border-bottom: 1px solid #cbd5e1; 
                font-weight: 600; 
                font-size: 11px; 
                text-transform: uppercase; 
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 25px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: #f8fafc;
                height: 8px;
                margin: 0px 4px 2px 4px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                min-width: 25px;
                border-radius: 3px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        self.layout.addWidget(self.table)

class StateWidget(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn_data = None
        self.expanded_pids = set()
        self.last_state_data = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(10)
        self.splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        
        self.sessions_frame = TableFrame("Sessions", has_checkbox=True, has_refresh=True)
        self.sessions_table = self.sessions_frame.table
        self.refresh_btn = self.sessions_frame.refresh_btn
        if self.refresh_btn:
            self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        self.active_checkbox = self.sessions_frame.checkbox
        self.active_checkbox.setChecked(False)
        self.active_checkbox.toggled.connect(lambda _: self.refresh_requested.emit())
        self.sessions_frame.search_input.textChanged.connect(self._on_search)
        self.splitter.addWidget(self.sessions_frame)

        self.locks_frame = TableFrame("Locks")
        self.locks_table = self.locks_frame.table
        self.locks_frame.search_input.textChanged.connect(self._on_search)
        self.splitter.addWidget(self.locks_frame)

        layout.addWidget(self.splitter)
        self.splitter.setSizes([400, 250])

    def _on_search(self):
        # Trigger refresh to apply filters properly across expanded rows
        if self.last_state_data:
            self.update_state(self.last_state_data)

    def clear_state(self):
        """Clears all table rows to ensure no stale data is shown."""
        self.sessions_table.setRowCount(0)
        self.locks_table.setRowCount(0)
        self.last_state_data = None

    def set_db_type(self, db_type):
        is_sqlite = "sqlite" in str(db_type).lower()
        if is_sqlite:
            self.locks_frame.hide()
        else:
            self.locks_frame.show()

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
            if not row_data:
                continue
            pid = None
            if is_sessions and row_data[0] is not None:
                try:
                    pid = int(row_data[0])
                except (ValueError, TypeError):
                    pass
            
            # Check filter
            if search_text:
                match = False
                for val in row_data:
                    if val is not None and search_text in str(val).lower():
                        match = True
                        break
                if not match:
                    continue

            row_idx = table.rowCount()
            table.insertRow(row_idx)
            table.setRowHeight(row_idx, 34 if is_sessions else 30)
            
            row_map = {columns[i]: row_data[i] for i in range(len(columns))}
            
            if is_sessions and pid is not None:
                # Actions
                self._add_action_btn(table, row_idx, 0, 'msc.close', "#ef4444", "Terminate", pid, self.handle_terminate)
                self._add_action_btn(table, row_idx, 1, 'msc.debug-stop', "#1f2937", "Cancel", pid, self.handle_cancel)
                
                is_expanded = pid in expanded_pids_int
                icon = 'msc.chevron-down' if is_expanded else 'msc.chevron-right'
                self._add_action_btn(table, row_idx, 2, icon, "#64748b", "Details", pid, self.toggle_details)
                
                # Data
                for i, col_idx in enumerate(display_cols):
                    val = row_data[col_idx]
                    table.setItem(row_idx, i + offset, QTableWidgetItem(str(val) if val is not None else ""))
                
                if is_expanded:
                    det_idx = table.rowCount()
                    table.insertRow(det_idx)
                    panel = DetailsPanel(row_map, on_close=lambda p=pid: self.toggle_details(p))
                    table.setCellWidget(det_idx, 0, panel)
                    table.setSpan(det_idx, 0, 1, table.columnCount())
                    table.setRowHeight(det_idx, panel.preferred_height())
            else:
                for i, col_idx in enumerate(display_cols):
                    val = row_data[col_idx]
                    table.setItem(row_idx, i + offset, QTableWidgetItem(str(val) if val is not None else ""))

        # Widths
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        if is_sessions:
            header.resizeSection(0, 92)
            header.resizeSection(1, 75)
            header.resizeSection(2, 75)
            for i in range(3, table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        else:
            for i in range(table.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        table.verticalScrollBar().setValue(v_scroll)
        table.horizontalScrollBar().setValue(h_scroll)

    def _add_action_btn(self, table, row, col, icon_name, color, tooltip, pid, callback):
        btn = IconButton(get_icon(icon_name, color=color), tooltip=tooltip)
        btn.setFixedSize(20, 20)
        btn.setIconSize(QSize(12, 12))
        btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #d1d5db;
                border-radius: 3px;
                background-color: #f9fafb;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border-color: #9ca3af;
            }
            QPushButton:pressed {
                background-color: #e5e7eb;
            }
            QToolTip {
                background-color: #ffffff;
                color: #1f2937;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)
        # Use pid=pid to ensure the value is captured correctly
        btn.clicked.connect(lambda checked=False, p=pid: callback(p))
        
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn)
        table.setCellWidget(row, col, w)

    def toggle_details(self, pid):
        if pid in self.expanded_pids:
            self.expanded_pids.remove(pid)
        else:
            self.expanded_pids.add(pid)
        
        if self.last_state_data:
            self.update_state(self.last_state_data)

    def handle_terminate(self, pid):
        if not self.conn_data:
            return
        success, msg = terminate_postgres_backend(self.conn_data, pid)
        if not success:
            QMessageBox.warning(self, "Termination Failed", f"Could not terminate backend {pid}:\n\n{msg}")

    def handle_cancel(self, pid):
        if not self.conn_data:
            return
        success, msg = cancel_postgres_backend(self.conn_data, pid)
        if not success:
            QMessageBox.warning(self, "Cancellation Failed", f"Could not cancel query for backend {pid}:\n\n{msg}")
