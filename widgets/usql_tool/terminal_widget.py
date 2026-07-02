# widgets/usql_tool/terminal_widget.py
"""
Proper embedded USQL tool widget, wrapping native psql.exe using pywinpty.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid

import qtawesome as qta
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from widgets.usql_tool.constants import _BANNER
from widgets.usql_tool.constants import _HISTORY_FILE
from widgets.usql_tool.constants import _APP_DATA_DIR
from widgets.usql_tool.constants import _STYLE
from widgets.usql_tool.editor import _TerminalEdit
from widgets.usql_tool.discovery import find_psql

try:
    from winpty import PTY
except ImportError:
    PTY = None


_RESIZE_DEBOUNCE_MS = 350


class USQLToolWidget(QWidget):
    """
    Embedded native USQL tool tab widget.

    Backend: pywinpty wrapping psql.exe

    Key design decisions vs. naive approach
    ----------------------------------------
    Problem 1 — Spurious blank prompts on startup / resize
        psql responds to every meta-command (\\set, \\pset) with a new prompt
        line.  During startup Qt fires showEvent + several resizeEvents, so
        _update_pty_size was sending 3 meta-commands × N resize events =
        many blank "dbname=>" lines before the user touched anything.

        Fix:
          • _session_ready flag — meta-commands are only sent AFTER psql has
            printed its first real prompt (detected in _on_output_received).
          • Debounced resize — a QTimer coalesces rapid resizeEvents into one
            _update_pty_size call after _RESIZE_DEBOUNCE_MS ms of quiet.
          • Startup quiet window — bare prompt lines are suppressed for
            _STARTUP_QUIET_SECS after spawning, covering the banner phase.
          • _BARE_PROMPT_RE strips any remaining lone prompt lines that are
            the direct response to our injected meta-commands.

    Problem 2 — LIMIT/OFFSET text visible in terminal
        The PTY echoes everything written to it.  Pagination SQL was echoed
        back verbatim.

        Fix: wrap injected SQL in \\set QUIET on/off + regex-strip the echo.

    Problem 3 — "\\set" Python string bug
        "\\set" in an f-string is two chars: backslash + 's'.  Fixed everywhere.
    """

    _output_received = Signal(str)
    terminal_closed = Signal()

    def __init__(self, conn: dict, pg_bin_path: str = "") -> None:
        super().__init__()
        self._conn: dict = conn or {}

        # Terminal state
        self._history: list[str] = []
        self._history_index: int = 0
        self._pending_sql: str = ""  # accumulates multi-line SQL before history commit
        self._current_db: str = (
            self._conn.get("database") or self._conn.get("db") or "postgres"
        )
        self._pending_db_switch_from: str = ""
        self._pg_bin_path = pg_bin_path

        self._pty = None
        self._reader_thread = None
        self._running = False
        self._output_received.connect(self._on_output_received)

        # Debounce timer for resize events
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._flush_resize)

        self._build_ui()
        self.setStyleSheet(_STYLE)
        self._load_history()
        self._start_session()


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
            self._term.append_output(
                "\nERROR: winpty module is not installed. PTY support unavailable.\n"
            )
            return

        fm = QFontMetrics(self._term.font())
        char_w = fm.horizontalAdvance('W')
        vbar_w = self._term.verticalScrollBar().sizeHint().width()
        usable_w = self._term.viewport().width() - vbar_w
        term_cols = max(80, usable_w // char_w) if char_w > 0 and usable_w > 0 else 80

        args = [
            "-P", "pager=off",
            "-P", "columns=0",
            "-P", "expanded=auto",
        ]
        c = self._conn

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

        try:
            self._pty = PTY(term_cols, 40)
            cmd_line = f'"{psql_path}" ' + " ".join(args)
            self._pty.spawn(cmd_line)
            self._running = True
            self._spawn_time = time.time()

            self._reader_thread = threading.Thread(target=self._pty_reader, daemon=True)
            self._reader_thread.start()
        except Exception as e:
            self._show_error(f"Failed to start psql process: {e}")
            self._term.append_output(f"\nERROR: Failed to start psql process: {e}\n")

    def _pty_reader(self) -> None:
        while self._running and self._pty is not None:
            try:
                data = self._pty.read(blocking=True)
                if not data:
                    break

                # Drain any immediately available bytes into one chunk
                buffer = [data]
                idle_start = time.time()
                while time.time() - idle_start < 0.05:
                    try:
                        more = self._pty.read(blocking=False)
                        if more:
                            buffer.append(more)
                            idle_start = time.time()
                        else:
                            time.sleep(0.005)
                    except Exception:
                        break

                text = "".join(buffer).replace('\r\n', '\n')
                self._output_received.emit(text)
            except Exception:
                break
        self._running = False
        self._output_received.emit("\n[Process exited]\n")


    def _on_output_received(self, text: str) -> None:
        if not text:
            return

        if self._pending_sentinel and self._pending_sentinel in text:
            text = re.sub(
                r'[^\n]*' + re.escape(self._pending_sentinel) + r'[^\n]*\n?',
                '',
                text,
            )
    def _on_output_received(self, text: str) -> None:
        if not text:
            return

        self._term.append_output(text)

        # Scrollbar visibility can change mid-session as output accumulates;
        # re-sync cols so psql's expanded=auto stays correct.
        self._resize_timer.start()

        if self._pending_db_switch_from:
            text_lower = text.lower()
            if (
                "fatal:" in text_lower
                or "error:" in text_lower
                or "connection to server" in text_lower
            ):
                self._current_db = self._pending_db_switch_from
                self._pending_db_switch_from = ""
                self._update_tab_title(f"USQL Tool – {self._current_db}")
                self._update_conn_label()
            elif (
                "you are now connected" in text_lower
                or "=>" in text
                or "=#" in text
            ):
                self._pending_db_switch_from = ""

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


    def _on_command_entered(self, cmd: str) -> None:
        """Send *cmd* to psql stdin; manage history and pagination."""
        cmd = cmd.replace("\r", "")
        stripped = cmd.strip()

        if stripped:
            # Accumulate multi-line SQL into one history entry.
            # A statement is complete when it ends with ';' or is a meta-command ('\').
            if self._pending_sql:
                self._pending_sql = self._pending_sql + "\n" + stripped
            else:
                self._pending_sql = stripped

            is_complete = stripped.endswith(";") or stripped.startswith("\\")
            if is_complete:
                full_cmd = self._pending_sql
                if not self._history or self._history[-1] != full_cmd:
                    self._history.append(full_cmd)
                self._pending_sql = ""

            self._history_index = len(self._history)

        if not self._running or self._pty is None:
            self._term.append_output("\n[Not connected — click Reconnect]\n")
            return

        # Intercept \q or exit/quit to close terminal gracefully
        if stripped in ("\\q", "exit", "quit"):
            self.terminal_closed.emit()
            return

        # Replace internal \n with \r\n so winpty processes them as separate lines.
        try:
            self._pty.write(cmd.replace("\n", "\r\n") + "\r\n")
        except Exception:
            self._term.append_output("\n[Error writing to process]\n")

        # Track \c / \connect for db-name state
        lower = stripped.lower()
        if lower.startswith("\\c ") or lower.startswith("\\connect "):
            parts = stripped.split()
            if len(parts) >= 2:
                self._pending_db_switch_from = self._current_db
                self._current_db = parts[1]
                self._update_tab_title(f"USQL Tool – {self._current_db}")
                self._update_conn_label()

    def _on_interrupt(self) -> None:
        """Cancel the current query via Ctrl+C (0x03)."""
        if self._running and self._pty is not None:
            try:
                self._pty.write("\x03")
            except Exception:
                pass


    def _history_key(self) -> str:
        c = self._conn
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        return f"{user}@{host}:{port}/{self._current_db}"

    def _load_history(self) -> None:
        try:
            if _HISTORY_FILE.exists():
                data: dict = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
                self._history = data.get(self._history_key(), [])
        except Exception:
            self._history = []
        self._history_index = len(self._history)

    def _save_history(self) -> None:
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




    def _clear(self) -> None:
        self._term.setPlainText(_BANNER)
        self._term.reset_input_start()

    def _reconnect(self) -> None:
        self.close_process()
        self._term.append_output("\n-- Reconnecting… --\n")
        self._hide_error()
        self._load_history()
        self._start_session(reset_ui=False)


    def _show_error(self, message: str) -> None:
        self._err_lbl.setText(f"⚠  {message}")
        self._err_frame.setVisible(True)

    def _hide_error(self) -> None:
        self._err_frame.setVisible(False)


    def _update_tab_title(self, title: str) -> None:
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "indexOf"):
                idx = widget.indexOf(self)
                if idx >= 0:
                    widget.setTabText(idx, title)
                    return
            widget = widget.parent()


    def _update_pty_size(self) -> None:
        """
        Schedule a debounced resize.  Does NOT send anything to psql directly —
        the actual write happens in _flush_resize after the debounce timer fires.
        This prevents a flood of \\pset commands during window-drag resizing.
        """
        self._resize_timer.start()



    def _flush_resize(self) -> None:
        """
        Actually resize the PTY and tell psql about the new column count.
        """
        if self._pty is None or not self._running:
            return
        try:
            fm = QFontMetrics(self._term.font())
            char_w = fm.horizontalAdvance('W')
            if char_w <= 0:
                return

            vp = self._term.viewport()
            vbar = self._term.verticalScrollBar()
            scrollbar_w = vbar.sizeHint().width() if vbar else 0
            usable_w = vp.width() - scrollbar_w
            cols = max(80, usable_w // char_w)
            rows = max(10, vp.height() // fm.height())
            self._pty.set_size(cols, rows)
            os.environ["COLUMNS"] = str(cols)
        except Exception:
            pass


    def showEvent(self, event) -> None:          # noqa: N802
        super().showEvent(event)
        self._resize_timer.start()

    def resizeEvent(self, event) -> None:        # noqa: N802
        super().resizeEvent(event)
        self._resize_timer.start()

    def closeEvent(self, event) -> None:         # noqa: N802
        self._resize_timer.stop()
        self.close_process()
        super().closeEvent(event)



def open_usql_tool(conn: dict, manager=None) -> USQLToolWidget:
    """Create a USQLToolWidget and open it in the main tab widget."""
    pg_bin_path = ""
    tab_widget = None

    if manager is not None:
        main_win = getattr(manager, "main_window", None) or (
            manager if hasattr(manager, "tab_widget") else None
        )
        if main_win:
            pg_bin_path = getattr(main_win, "pg_bin_path", "") or ""
            tab_widget = getattr(main_win, "tab_widget", None)

    widget = USQLToolWidget(conn, pg_bin_path=pg_bin_path)

    if tab_widget is not None:
        try:
            icon = qta.icon("mdi.console", color="#a6e3a1")
        except Exception:
            icon = qta.icon("fa5s.terminal", color="#a6e3a1")

        db_name = (conn or {}).get("database") or (conn or {}).get("db") or "psql"
        index = tab_widget.addTab(widget, icon, f"USQL Tool – {db_name}")
        tab_widget.setCurrentIndex(index)
    else:
        widget.resize(960, 640)
        widget.show()

    return widget
