# widgets/db_terminal/terminal_widget.py
"""
Proper embedded psql terminal widget, wrapping native psql.exe using pywinpty.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Local imports
from widgets.db_terminal.constants import _BANNER
from widgets.db_terminal.constants import _HISTORY_FILE
from widgets.db_terminal.constants import _APP_DATA_DIR
from widgets.db_terminal.constants import _STYLE
from widgets.db_terminal.editor import _TerminalEdit
from widgets.db_terminal.discovery import find_psql

try:
    from winpty import PTY
except ImportError:
    PTY = None


class PSQLTerminalWidget(QWidget):
    """
    Embedded native PSQL terminal tab widget.

    Backend: pywinpty wrapping psql.exe
    """
    
    _output_received = Signal(str)

    def __init__(self, conn: dict, pg_bin_path: str = "") -> None:
        super().__init__()
        self._conn: dict = conn or {}
        
        # Terminal state
        self._history: list[str] = []
        self._history_index: int = 0
        self._current_db: str = (
            self._conn.get("database") or self._conn.get("db") or "postgres"
        )
        self._pg_bin_path = pg_bin_path

        self._pty = None
        self._reader_thread = None
        self._running = False
        self._output_received.connect(self._on_output_received)

        self._build_ui()
        self.setStyleSheet(_STYLE)
        self._load_history()
        self._start_session()

    # UI construction

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())
        root.addWidget(self._make_error_banner())

        self._term = _TerminalEdit()
        self._term.command_entered.connect(self._on_command_entered)
        self._term.history_up.connect(self._on_history_up)
        self._term.history_down.connect(self._on_history_down)
        self._term.interrupt.connect(self._on_interrupt)
        root.addWidget(self._term, 1)

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("term_header")
        header.setFixedHeight(36)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(6)

        self._conn_lbl = QLabel(self._conn_label_text())
        self._conn_lbl.setObjectName("term_conn_lbl")
        layout.addWidget(self._conn_lbl)
        layout.addStretch()

        for icon_key, label, slot in (
            ("fa5s.trash-alt", "Clear", self._clear),
            ("fa5s.redo-alt", "Reconnect", self._reconnect),
        ):
            btn = QPushButton(qta.icon(icon_key, color="#a6adc8"), label)
            btn.setObjectName("term_btn")
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        return header

    def _make_error_banner(self) -> QFrame:
        self._err_frame = QFrame()
        self._err_frame.setObjectName("term_err_frame")
        self._err_frame.setVisible(False)
        layout = QHBoxLayout(self._err_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        self._err_lbl = QLabel()
        self._err_lbl.setObjectName("term_err_lbl")
        self._err_lbl.setWordWrap(True)
        layout.addWidget(self._err_lbl)
        return self._err_frame

    def _resolve_uri(self) -> str:
        c = self._conn
        return (
            c.get("uri")
            or c.get("connection_string")
            or c.get("service_uri")
            or c.get("dsn")
            or ""
        )

    def _conn_label_text(self) -> str:
        c = self._conn
        uri = self._resolve_uri()
        if uri:
            label = f"URI: {uri[:60]}{'…' if len(uri) > 60 else ''}"
        else:
            host = c.get("host") or "localhost"
            port = c.get("port") or 5432
            db = self._current_db
            user = c.get("user") or "postgres"
            label = f"{user}@{host}:{port}/{db}"
        sslmode = c.get("sslmode", "")
        if sslmode and sslmode not in ("disable", "prefer", ""):
            label += " [SSL]"
        return label

    def _update_conn_label(self) -> None:
        self._conn_lbl.setText(self._conn_label_text())

    # Process lifecycle

    def _start_session(self, reset_ui: bool = True) -> None:
        """Fresh start: reset the terminal pane and spawn psql.exe."""
        if reset_ui:
            self._term.setPlainText(_BANNER)
            self._term.reset_input_start()

        self._hide_error()
        self._term.append_output("\n-- Connecting to database... --\n")
        
        psql_path = self._pg_bin_path or find_psql()
        if not psql_path:
            self._show_error("Could not locate psql executable.")
            self._term.append_output("\nERROR: Could not locate psql executable.\n")
            return

        if PTY is None:
            self._show_error("winpty module is not installed.")
            self._term.append_output("\nERROR: winpty module is not installed. PTY support unavailable.\n")
            return

        # Build arguments. Disable pager explicitly.
        args = ["-P", "pager=off"]
        c = self._conn
        
        # Connection URI takes precedence
        uri = self._resolve_uri()
        if uri:
            args.append(uri)
        else:
            if c.get("host"):
                args.extend(["-h", str(c["host"])])
            if c.get("port"):
                args.extend(["-p", str(c["port"])])
            if c.get("user"):
                args.extend(["-U", c["user"]])
            args.append(self._current_db)

        if c.get("password"):
            os.environ["PGPASSWORD"] = c["password"]
            
        # Do not set PAGER=cat on Windows, as cat doesn't exist
        if "PAGER" in os.environ:
            del os.environ["PAGER"]

        try:
            self._pty = PTY(200, 40)
            cmd_line = f'"{psql_path}" ' + " ".join(args)
            self._pty.spawn(cmd_line)
            self._running = True
            
            self._reader_thread = threading.Thread(target=self._pty_reader, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            self._show_error(f"Failed to start psql process: {e}")
            self._term.append_output(f"\nERROR: Failed to start psql process: {e}\n")
            return

    def _pty_reader(self) -> None:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        while self._running and self._pty is not None:
            try:
                data = self._pty.read(blocking=True)
                if not data:
                    break
                text = ansi_escape.sub('', data).replace('\r', '')
                self._output_received.emit(text)
            except Exception:
                break
        self._running = False
        self._output_received.emit("\n[Process exited]\n")

    def _on_output_received(self, text: str) -> None:
        self._term.append_output(text)

    def close_process(self) -> None:
        """Terminate cleanly. Must be called before closing the tab."""
        self._save_history()
        self._running = False
        if self._pty is not None:
            try:
                del self._pty
            except Exception:
                pass
            self._pty = None

    # I/O Handlers

    def _on_command_entered(self, cmd: str) -> None:
        """Send *cmd* to psql stdin; manage history."""
        stripped = cmd.strip()
        if stripped:
            if not self._history or self._history[-1] != stripped:
                self._history.append(stripped)
            self._history_index = len(self._history)
            
        if not self._running or self._pty is None:
            self._term.append_output("\n[Not connected — click Reconnect]\n")
            return

        # Write to psql PTY
        try:
            self._pty.write(cmd + "\r\n")
        except Exception:
            self._term.append_output("\n[Error writing to process]\n")
        
        # Check if the command was \c or \connect to update our current_db state conceptually
        if stripped.lower().startswith("\\c ") or stripped.lower().startswith("\\connect "):
            parts = stripped.split()
            if len(parts) >= 2:
                self._current_db = parts[1]
                self._update_tab_title(f"PSQL Tool – {self._current_db}")
                self._update_conn_label()

    def _on_interrupt(self) -> None:
        """Cancel the current query.
        With PTY, we can just send Ctrl+C (0x03).
        """
        if self._running and self._pty is not None:
            try:
                self._pty.write("\x03")
            except Exception:
                pass

    # History navigation + persistence

    def _history_key(self) -> str:
        """Unique key for this connection's history bucket."""
        c = self._conn
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        return f"{user}@{host}:{port}/{self._current_db}"

    def _load_history(self) -> None:
        """Load per-connection history from disk into _history."""
        try:
            if _HISTORY_FILE.exists():
                data: dict = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
                self._history = data.get(self._history_key(), [])
        except Exception:
            self._history = []
        self._history_index = len(self._history)

    def _save_history(self) -> None:
        """Persist the last 500 commands for this connection to disk."""
        try:
            _APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
            existing: dict = {}
            if _HISTORY_FILE.exists():
                existing = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            existing[self._history_key()] = self._history[-500:]
            _HISTORY_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_history_up(self) -> None:
        if not self._history:
            return
        self._history_index = max(0, self._history_index - 1)
        self._term.set_input_text(self._history[self._history_index])

    def _on_history_down(self) -> None:
        if not self._history:
            return
        self._history_index = min(len(self._history), self._history_index + 1)
        if self._history_index < len(self._history):
            self._term.set_input_text(self._history[self._history_index])
        else:
            self._term.set_input_text("")

    # Toolbar actions

    def _clear(self) -> None:
        self._term.setPlainText(_BANNER)
        self._term.reset_input_start()

    def _reconnect(self) -> None:
        self.close_process()
        self._term.append_output("\n-- Reconnecting… --\n")
        self._hide_error()
        self._load_history()
        self._start_session(reset_ui=False)

    # Error banner

    def _show_error(self, message: str) -> None:
        self._err_lbl.setText(f"⚠  {message}")
        self._err_frame.setVisible(True)

    def _hide_error(self) -> None:
        self._err_frame.setVisible(False)

    # Tab title

    def _update_tab_title(self, title: str) -> None:
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "indexOf"):
                idx = widget.indexOf(self)
                if idx >= 0:
                    widget.setTabText(idx, title)
                    return
            widget = widget.parent()

    # Widget lifecycle

    def closeEvent(self, event) -> None:  # noqa: N802
        self.close_process()
        super().closeEvent(event)


# Public factory

def open_psql_terminal(conn: dict, manager=None) -> PSQLTerminalWidget:
    """
    Create a PSQLTerminalWidget and open it in the main tab widget.
    """
    pg_bin_path = ""
    tab_widget = None

    if manager is not None:
        main_win = getattr(manager, "main_window", None) or (
            manager if hasattr(manager, "tab_widget") else None
        )
        if main_win:
            pg_bin_path = getattr(main_win, "pg_bin_path", "") or ""
            tab_widget = getattr(main_win, "tab_widget", None)

    widget = PSQLTerminalWidget(conn, pg_bin_path=pg_bin_path)

    if tab_widget is not None:
        try:
            icon = qta.icon("mdi.console", color="#a6e3a1")
        except Exception:
            icon = qta.icon("fa5s.terminal", color="#a6e3a1")

        db_name = (conn or {}).get("database") or (conn or {}).get("db") or "psql"
        index = tab_widget.addTab(widget, icon, f"PSQL Tool – {db_name}")
        tab_widget.setCurrentIndex(index)
    else:
        widget.resize(960, 640)
        widget.show()

    return widget
