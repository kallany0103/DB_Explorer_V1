from __future__ import annotations
import csv
import io
import json
import datetime
import re, datetime
from typing import List, Dict, Any
import re
from PySide6.QtWidgets import QComboBox, QMessageBox, QFileDialog
import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, QSortFilterProxyModel, QThread, Signal
from ui.components import IconButton
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from db import get_postgres_server_logs

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------
_COLUMNS = ["", "Error Severity", "Log Prefix/Timestamp", "Logs"]
_COL_EXPAND = 0
_COL_SEV = 1
_COL_PREFIX = 2
_COL_LOGS = 3

# Colours
_CLR_SUCCESS  = "#000000"   # black
_CLR_FAILURE  = "#000000"   # black
_CLR_BG_SUCC  = "#f0fdf4"
_CLR_BG_FAIL  = "#fff1f2"


class _ToggleButton(QPushButton):
    """Flat segmented toggle button (like pgAdmin format selectors)."""

    _ACTIVE_SS = """
        QPushButton {
            background: #e5e7eb;
            color: #111827;
            border: 1px solid #d1d5db;
            padding: 3px 12px;
            font-size: 11px;
            font-weight: 600;
        }
    """
    _INACTIVE_SS = """
        QPushButton {
            background: #ffffff;
            color: #374151;
            border: 1px solid #d1d5db;
            padding: 3px 12px;
            font-size: 11px;
        }
        QPushButton:hover {
            background: #f3f4f6;
        }
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFlat(True)
        self.setFixedHeight(26)
        self._apply()
        self.toggled.connect(self._apply)

    def _apply(self, *_):
        self.setStyleSheet(self._ACTIVE_SS if self.isChecked() else self._INACTIVE_SS)


class _SwitchButton(QPushButton):
    """A simple ON/OFF toggle that looks like a switch (for 'Tabular format?')."""

    _ON_SS = """
        QPushButton {
            background: #e5e7eb;
            color: #111827;
            border: 1px solid #d1d5db;
            border-radius: 11px;
            padding: 2px 14px;
            font-size: 11px;
            font-weight: 600;
            min-width: 46px;
        }
    """
    _OFF_SS = """
        QPushButton {
            background: #ffffff;
            color: #6b7280;
            border: 1px solid #d1d5db;
            border-radius: 11px;
            padding: 2px 14px;
            font-size: 11px;
            min-width: 46px;
        }
        QPushButton:hover { background: #f3f4f6; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setFixedHeight(24)
        self._apply()
        self.toggled.connect(self._apply)

    def _apply(self, *_):
        self.setText("ON" if self.isChecked() else "OFF")
        self.setStyleSheet(self._ON_SS if self.isChecked() else self._OFF_SS)

class ServerLogsWorker(QThread):
    finished = Signal(dict)
    
    def __init__(self, conn_data, parent=None):
        super().__init__(parent)
        self.conn_data = conn_data
        
    def run(self):
        result = get_postgres_server_logs(self.conn_data)
        
        if result.get("status") == "error":
            self.finished.emit(result)
            return

        raw_data = result.get("data", "")
        if not raw_data:
            self.finished.emit({"status": "success", "entries": []})
            return
            
        lines = raw_data.splitlines()
        pattern = re.compile(r"^([^\[]+ \[\d+\] [^:]+)\s*(LOG|ERROR|FATAL|WARNING|INFO|DEBUG|NOTICE):\s*(.*)$")
        
        entries = []
        current_entry = None
        conn_name = self.conn_data.get("name", "")
        db_name = self.conn_data.get("database", "")
        
        for line in lines:
            match = pattern.match(line)
            if match:
                if current_entry:
                    entries.append(current_entry)
                    
                prefix, severity, msg = match.groups()
                status = "Success" if severity == "LOG" else "Failure"
                if msg.startswith("statement: "):
                    msg = msg[11:]
                    
                current_entry = {
                    "timestamp": prefix,
                    "conn_name": "",
                    "database": "",
                    "status": status,
                    "duration": 0.0,
                    "rows": 0,
                    "query": msg
                }
            else:
                if current_entry:
                    current_entry["query"] += "\n" + line
                else:
                    current_entry = {
                        "timestamp": datetime.datetime.now(),
                        "conn_name": conn_name,
                        "database": db_name,
                        "status": "LOG",
                        "duration": 0.0,
                        "rows": 0,
                        "query": line
                    }
        
        if current_entry:
            entries.append(current_entry)
            
        result["entries"] = entries
        self.finished.emit(result)

class LogsWidget(QWidget):
   
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[Dict[str, Any]] = []
        self._current_conn_data: dict | None = None
        self._worker = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current_connection(self, conn_data: dict | None):
        """Called by DashboardWidget when the selected connection changes."""
        self._current_conn_data = conn_data
        self.clear_logs()
        
        if not conn_data:
            return
            
        db_type = str(conn_data.get("db_type", "")).lower()
        if "postgres" not in db_type:
            return
            
        host = str(conn_data.get("host", "")).lower()
        if host not in ("localhost", "127.0.0.1"):
            entry = {
                "timestamp": datetime.datetime.now(),
                "conn_name": conn_data.get("name", ""),
                "database": conn_data.get("database", ""),
                "status": "Failure",
                "duration": 0.0,
                "rows": 0,
                "query": "Permission denied."
            }
            self.append_log_entry(entry)
            return

        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
            
        self._worker = ServerLogsWorker(conn_data)
        self._worker.finished.connect(self._on_server_logs_fetched)
        self._worker.start()

    def _on_server_logs_fetched(self, result: dict):
        if result.get("status") == "error":
            # Add error entry
            entry = {
                "timestamp": datetime.datetime.now(),
                "conn_name": self._current_conn_data.get("name", ""),
                "database": self._current_conn_data.get("database", ""),
                "status": "Failure",
                "duration": 0.0,
                "rows": 0,
                "query": result.get("message", "Unknown error")
            }
            self.append_log_entry(entry)
            return

        entries = result.get("entries", [])
        if not entries:
            return
            
        self._source_model.layoutAboutToBeChanged.emit()
        
        for entry in entries:
            entry.setdefault("timestamp", datetime.datetime.now())
            self._entries.append(entry)
            self._add_model_row(entry, update_ui=False)
            
        self._source_model.layoutChanged.emit()
        self._update_count_label()
        
        if not self._tabular_switch.isChecked():
            self._update_raw_view()

    def append_log_entry(self, entry: dict):
        """Append one log entry (thread-safe — must be called on the main thread)."""
        entry.setdefault("timestamp", datetime.datetime.now())
        self._entries.append(entry)
        self._add_model_row(entry)

    def clear_logs(self):
        self._entries.clear()
        self._source_model.removeRows(0, self._source_model.rowCount())
        self._update_count_label()
        if not self._tabular_switch.isChecked():
            self._update_raw_view()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ────────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet("""
            QFrame {
                background: #f9fafb;
                border: none;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(12, 0, 12, 0)
        tb_lay.setSpacing(8)

        # Log Format label + segmented buttons
        fmt_lbl = QLabel("Log Format")
        fmt_lbl.setStyleSheet("font-size: 12px; color: #374151; font-weight: 500; background: transparent;")
        tb_lay.addWidget(fmt_lbl)
        tb_lay.addSpacing(4)

        self._btn_text = _ToggleButton(" Text")
        self._btn_json = _ToggleButton(" JSON")
        self._btn_csv  = _ToggleButton(" CSV")
        self._btn_text.setChecked(True)

        # Rounded group border styling
        for btn, pos in [(self._btn_text, "left"), (self._btn_json, "mid"), (self._btn_csv, "right")]:
            radii = {
                "left":  "border-radius: 0; border-top-left-radius: 4px; border-bottom-left-radius: 4px; border-right: none;",
                "mid":   "border-radius: 0; border-right: none;",
                "right": "border-radius: 0; border-top-right-radius: 4px; border-bottom-right-radius: 4px;",
            }[pos]
            btn.setStyleSheet(btn.styleSheet() + radii)
            tb_lay.addWidget(btn)

        self._btn_text.toggled.connect(self._on_format_changed)
        self._btn_json.toggled.connect(self._on_format_changed)
        self._btn_csv.toggled.connect(self._on_format_changed)

        # Keep them exclusive
        def _exclusive(checked, clicked_btn, others):
            if checked:
                for o in others:
                    o.setChecked(False)
        self._btn_text.toggled.connect(lambda c: _exclusive(c, self._btn_text, [self._btn_json, self._btn_csv]))
        self._btn_json.toggled.connect(lambda c: _exclusive(c, self._btn_json, [self._btn_text, self._btn_csv]))
        self._btn_csv.toggled.connect(lambda c:  _exclusive(c, self._btn_csv,  [self._btn_text, self._btn_json]))

        tb_lay.addStretch()

        # Filter box
        self._filter_box = QLineEdit()
        self._filter_box.setPlaceholderText("Filter logs...")
        self._filter_box.setFixedWidth(180)
        self._filter_box.setFixedHeight(26)
        self._filter_box.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12px;
                color: #1f2937;
            }
        """)
        self._filter_box.textChanged.connect(self._on_filter_changed)
        tb_lay.addWidget(self._filter_box)

        # Tabular format label + switch
        tab_lbl = QLabel("Tabular format?")
        tab_lbl.setStyleSheet("font-size: 12px; color: #374151; background: transparent; margin-left: 8px;")
        tb_lay.addWidget(tab_lbl)
        self._tabular_switch = _SwitchButton()
        self._tabular_switch.setChecked(False) 
        self._tabular_switch.toggled.connect(self._on_tabular_toggled)
        tb_lay.addWidget(self._tabular_switch)

    
        # Download button
        dl_btn = IconButton(qta.icon("mdi.download", color="#374151"), tooltip="Download logs")
        dl_btn.setFixedSize(28, 28)
        dl_btn.clicked.connect(self._download)
        tb_lay.addWidget(dl_btn)

        root.addWidget(toolbar)

        # ── Content (stacked: table vs raw text) ──────────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # Page 0: Table view
        self._table_page = QWidget()
        tp_lay = QVBoxLayout(self._table_page)
        tp_lay.setContentsMargins(0, 0, 0, 0)
        tp_lay.setSpacing(0)
        self._tree_view = QTreeView()
        self._tree_view.setAlternatingRowColors(False)
        self._tree_view.setRootIsDecorated(True)
        self._tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree_view.header().setStretchLastSection(True)
        self._tree_view.header().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self._tree_view.setSortingEnabled(True)
        self._tree_view.setStyleSheet("""
            QTreeView {
                background: #ffffff;
                color: #111827;
                border: none;
                font-size: 12px;
            }
            QTreeView::item {
                border-bottom: 1px solid #e5e7eb;
                border-right: 1px solid #e5e7eb;
                padding: 4px;
            }
            QHeaderView::section {
                background: #f8f9fa;
                color: #374151;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid #d1d5db;
                border-bottom: 2px solid #d1d5db;
                font-weight: 600;
                font-size: 11px;
            }
            QTreeView::item:selected {
                background: #dbeafe;
                color: #1e3a8a;
            }
        """)
        tp_lay.addWidget(self._tree_view)

        # Source model
        self._source_model = QStandardItemModel(0, len(_COLUMNS))
        self._source_model.setHorizontalHeaderLabels(_COLUMNS)

        # Proxy for filtering
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)

        self._tree_view.setModel(self._proxy_model)
        self._configure_table_columns()
        self._stack.addWidget(self._table_page)

        # Page 1: Raw text view
        self._raw_view = QPlainTextEdit()
        self._raw_view.setReadOnly(True)
        self._raw_view.setFont(QFont("Consolas", 11))
        self._raw_view.setStyleSheet("""
            QPlainTextEdit {
                background: #ffffff;
                color: #000000;
                border: none;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        self._stack.addWidget(self._raw_view)

        # Show tabular by default (stack page 0)
        self._stack.setCurrentIndex(0)

        # ── Status bar ────────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setFixedHeight(24)
        status_bar.setStyleSheet("QFrame { background: #f3f4f6; border-top: 1px solid #e5e7eb; }")
        sb_lay = QHBoxLayout(status_bar)
        sb_lay.setContentsMargins(12, 0, 12, 0)
        self._count_label = QLabel("0 entries")
        self._count_label.setStyleSheet("font-size: 11px; color: #6b7280; background: transparent;")
        sb_lay.addWidget(self._count_label)
        sb_lay.addStretch()
        self._scroll_lbl = QLabel("Auto-scroll: ON")
        self._scroll_lbl.setStyleSheet("font-size: 11px; color: #6b7280; background: transparent;")
        sb_lay.addWidget(self._scroll_lbl)
        root.addWidget(status_bar)

        # Auto-scroll: when new rows appear, scroll to bottom
        self._source_model.rowsInserted.connect(self._auto_scroll)

    def _configure_table_columns(self):
        hh = self._tree_view.header()
        hh.resizeSection(_COL_EXPAND, 30)
        hh.resizeSection(_COL_SEV,    100)
        hh.resizeSection(_COL_PREFIX, 280)
        hh.setSectionResizeMode(_COL_LOGS, QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    def _add_model_row(self, entry: dict, update_ui: bool = True):
        ts = entry.get("timestamp", datetime.datetime.now())
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " +06" if isinstance(ts, datetime.datetime) else str(ts)
        status  = entry.get("status", "")
        dur_f   = f"{entry.get('duration', 0):.3f}"
        rows    = str(entry.get("rows", ""))
        query   = str(entry.get("query", "")).strip()
        single_line_query = query.replace("\n", " ").strip()

        is_ok = status.lower() == "success"
        severity = "LOG" if is_ok else "ERROR"
        fg = QColor(_CLR_SUCCESS) if is_ok else QColor(_CLR_FAILURE)
        bg = QColor(_CLR_BG_SUCC) if is_ok else QColor(_CLR_BG_FAIL)

        def _item(text: str, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft) -> QStandardItem:
            it = QStandardItem(text)
            it.setForeground(fg)
            it.setBackground(bg)
            it.setEditable(False)
            it.setTextAlignment(align)
            return it

        conn_name = entry.get("conn_name", "")
        db_name = entry.get("database", "")
        # We might have synthesized the prefix from parsing server logs
        if isinstance(entry.get("timestamp"), str) and not conn_name and not db_name:
            prefix_str = entry.get("timestamp")
        else:
            prefix_str = f"{ts_str} {conn_name}@{db_name}"

        sev_item = _item(severity)

        row_items = [
            _item(""),
            sev_item,
            _item(prefix_str),
            _item(f"statement: {single_line_query}"),
        ]
        
        # Store raw entry on the first item for retrieval
        row_items[0].setData(entry, Qt.ItemDataRole.UserRole)
        
        # Child row for expanded logs
        child_text = f"statement: {query}\nduration: {dur_f}s\nrows: {rows}"
        child_row = [
            _item(""),
            _item(""),
            _item(""),
            _item(child_text, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        ]
        
        row_items[0].appendRow(child_row)

        self._source_model.appendRow(row_items)
        if update_ui:
            self._update_count_label()
            if not self._tabular_switch.isChecked():
                self._update_raw_view()

    def _rebuild_view(self):
        """Re-populate model after connection filter changes (future use)."""
        self._source_model.removeRows(0, self._source_model.rowCount())
        for entry in self._entries:
            self._add_model_row(entry)

    # ------------------------------------------------------------------
    # Slots / handlers
    # ------------------------------------------------------------------

    def _on_format_changed(self, *_):
        if not self._tabular_switch.isChecked():
            self._update_raw_view()
        else:
            self._stack.setCurrentIndex(0)

    def _on_tabular_toggled(self, checked: bool):
        if checked:
            self._stack.setCurrentIndex(0)
        else:
            self._update_raw_view()

    def _on_filter_changed(self, text: str):
        self._proxy_model.setFilterFixedString(text)
        self._update_count_label()

    def _auto_scroll(self):
        self._tree_view.scrollToBottom()
        sb = self._raw_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ------------------------------------------------------------------
    # Raw view rendering
    # ------------------------------------------------------------------

    def _get_visible_entries(self) -> List[dict]:
        """Return entries matching the current filter text."""
        f = self._filter_box.text().lower()
        if not f:
            return list(self._entries)
        out = []
        for e in self._entries:
            haystack = " ".join([
                str(e.get("timestamp", "")),
                e.get("conn_name", ""),
                e.get("database", ""),
                e.get("status", ""),
                str(e.get("duration", "")),
                str(e.get("rows", "")),
                e.get("query", ""),
            ]).lower()
            if f in haystack:
                out.append(e)
        return out

    def _update_raw_view(self):
        entries = self._get_visible_entries()
        self._stack.setCurrentIndex(1)
        if self._btn_json.isChecked():
            self._raw_view.setPlainText(self._format_json(entries))
        elif self._btn_csv.isChecked():
            self._raw_view.setPlainText(self._format_csv(entries))
        else:
            self._raw_view.setPlainText(self._format_text(entries))

    def _format_text(self, entries: List[dict]) -> str:
        lines = []
        for e in entries:
            ts = e.get("timestamp", "")
            ts_s = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime.datetime) else str(ts)
            dur = e.get("duration", 0)
            rows = e.get("rows", "")
            status = e.get("status", "")
            db = e.get("database", "")
            conn = e.get("conn_name", "")
            q = str(e.get("query", "")).replace("\n", " ").strip()
            lines.append(
                f"[{ts_s}] [{status.upper():7}] [{dur:7.3f}s] [{rows:>6} rows] [{conn}/{db}]  {q}"
            )
        return "\n".join(lines)

    def _format_json(self, entries: List[dict]) -> str:
        out = []
        for e in entries:
            ts = e.get("timestamp", "")
            ts_s = ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts)
            out.append({
                "timestamp":   ts_s,
                "connection":  e.get("conn_name", ""),
                "database":    e.get("database", ""),
                "status":      e.get("status", ""),
                "duration_s":  round(float(e.get("duration", 0)), 6),
                "rows":        int(e.get("rows", 0)),
                "query":       e.get("query", ""),
            })
        return json.dumps(out, indent=2)

    def _format_csv(self, entries: List[dict]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Timestamp", "Connection", "Database", "Status", "Duration (s)", "Rows", "Query"])
        for e in entries:
            ts = e.get("timestamp", "")
            ts_s = ts.isoformat() if isinstance(ts, datetime.datetime) else str(ts)
            writer.writerow([
                ts_s,
                e.get("conn_name", ""),
                e.get("database", ""),
                e.get("status", ""),
                f"{e.get('duration', 0):.6f}",
                e.get("rows", ""),
                e.get("query", ""),
            ])
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download(self):
        ext = "CSV Files (*.csv)"
        default = "logs.csv"

        path, _ = QFileDialog.getSaveFileName(self, "Save Logs", default, ext)
        if not path:
            return

        entries = self._get_visible_entries()
        content = self._format_csv(entries)

        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except Exception as exc:
         
            QMessageBox.warning(self, "Download Failed", str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_count_label(self):
        visible = self._proxy_model.rowCount()
        total   = self._source_model.rowCount()
        if visible == total:
            self._count_label.setText(f"{total} {'entry' if total == 1 else 'entries'}")
        else:
            self._count_label.setText(f"{visible} of {total} entries")
