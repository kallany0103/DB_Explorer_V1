# widgets/usql_tool/terminal_widget.py
"""
Proper embedded USQL tool widget, wrapping native psql.exe using pywinpty.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time

import qtawesome as qta
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFontMetrics, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QLabel,
    QFrame,
    QMessageBox
)

# from widgets.usql_tool.constants import _BANNER
from widgets.usql_tool.constants import _HISTORY_FILE
from widgets.usql_tool.constants import _APP_DATA_DIR
from widgets.usql_tool.constants import _PTY_DRAIN_TIMEOUT_S
from widgets.usql_tool.constants import _PTY_DRAIN_SLEEP_S
from widgets.usql_tool.constants import _STYLE
from ui.components import SecondaryButton
from widgets.usql_tool.editor import _TerminalEdit
from widgets.usql_tool.discovery import find_psql
from widgets.worksheet.autocomplete import CompletionEngine

try:
    from winpty import PTY
except ImportError:
    PTY = None


_RESIZE_DEBOUNCE_MS = 350


class USQLToolWidget(QWidget):
    """
    Embedded native USQL tool tab widget.

    Backend: pywinpty wrapping psql.exe.

    Features & Design:
    - Runs `psql.exe` inside a native Windows pseudo-terminal (PTY) using `pywinpty`.
    - I/O is handled via a background reader thread (`_pty_reader`) that drains output
      chunks and emits them to the Qt main thread via the `_output_received` signal.
    - Window resizing is debounced using a QTimer (`_RESIZE_DEBOUNCE_MS`) to prevent
      thrashing the PTY with rapid layout changes during window drag.
    - Captures `\c` / `\connect` commands to automatically track and update the active
      database in the UI tab and connection label.
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
        # _session_history_key is fixed at session-start so \c switches never
        # cause history entries to be saved under a different key.
        self._session_history_key: str = ""
        self._pending_db_switch_from: str = ""
        self._pg_bin_path = pg_bin_path
        self._psql_exe_path: str = ""  # resolved once _start_session runs
        self._completion_engine: CompletionEngine | None = None

        self._pty = None
        self._reader_thread = None
        self._running = False
        self._spawn_time: float = 0.0
        # Position in the document just after psql's connection preamble
        # (version info, WARNING, SSL line, "Type help").  Set on first prompt;
        # Copy Output skips everything before this so boilerplate is not included.
        self._first_prompt_pos: int = 0
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

        self._spinner_overlay = self._make_spinner_overlay()
        self._spinner_overlay.setParent(self._term.viewport())
        self._spinner_overlay.hide()



    # ------------------------------------------------------------------
    # Spinner overlay
    # ------------------------------------------------------------------

    _SPINNER_FRAMES: list[str] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _make_spinner_overlay(self) -> QLabel:
        """Build the connecting overlay label styled to match the app palette."""
        lbl = QLabel("⠋  Connecting…")
        lbl.setObjectName("spinner_overlay")
        # Use palette() tokens so the pill always matches the active Qt theme.
        # Avoid QGraphicsOpacityEffect — it composites on a black backing buffer
        # and cannot see through to the widget behind it, causing a black box.
        lbl.setStyleSheet(
            "QLabel#spinner_overlay {"
            "  color: palette(window-text);"
            "  background: palette(button);"
            "  border: 1px solid palette(window);"
            "  border-radius: 6px;"
            "  padding: 6px 16px;"
            "  font-family: 'Cascadia Code', 'Consolas', monospace;"
            "  font-size: 10pt;"
            "}"
        )
        # Spin timer (frame advance)
        self._spinner_frame_idx: int = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(80)
        self._spinner_timer.timeout.connect(self._advance_spinner_frame)
        return lbl

    def _show_spinner(self) -> None:
        """Show and animate the connecting spinner overlay."""
        vp = self._term.viewport()
        self._spinner_frame_idx = 0
        lbl = self._spinner_overlay
        lbl.setText(f"{self._SPINNER_FRAMES[0]}  Connecting…")
        lbl.adjustSize()
        # Centre in viewport
        lbl.move(
            (vp.width() - lbl.width()) // 2,
            (vp.height() - lbl.height()) // 2,
        )
        lbl.show()
        lbl.raise_()
        self._spinner_timer.start()

    def _hide_spinner(self) -> None:
        """Stop and hide the connecting spinner overlay."""
        self._spinner_timer.stop()
        self._spinner_overlay.hide()

    def _advance_spinner_frame(self) -> None:
        """Rotate to the next Braille spinner frame."""
        self._spinner_frame_idx = (self._spinner_frame_idx + 1) % len(self._SPINNER_FRAMES)
        frame = self._SPINNER_FRAMES[self._spinner_frame_idx]
        self._spinner_overlay.setText(f"{frame}  Connecting…")
        self._spinner_overlay.adjustSize()
        # Keep centred if the viewport was resized
        vp = self._term.viewport()
        lbl = self._spinner_overlay
        lbl.move(
            (vp.width() - lbl.width()) // 2,
            (vp.height() - lbl.height()) // 2,
        )

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
            ("fa5s.copy", "Copy Output", self._copy_output),
            ("fa5s.trash-alt", "Clear", self._clear),
            ("fa5s.redo-alt", "Reconnect", self._reconnect),
        ):
            btn = SecondaryButton(qta.icon(icon_key, color="#a6adc8"), label)
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
        self._first_prompt_pos = 0  # reset so the new preamble is skipped on copy
        if reset_ui:
            # self._term.setPlainText(_BANNER)
            self._term.reset_input_start()

        self._hide_error()
        self._show_spinner()

        psql_path = self._pg_bin_path or find_psql()
        if not psql_path:
            self._show_error("Could not locate psql executable.")
            self._term.append_output("\nERROR: Could not locate psql executable.\n")
            return
        self._psql_exe_path = psql_path

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
            args.append(f'"{self._current_db}"')

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

            self._completion_engine = CompletionEngine()
            _conn_with_db = {
                **self._conn,
                "database": self._current_db,
                "code": "POSTGRES",
                # Drop the old connection ID so the cache does not return
                # schema data from the previous database/host.
                "id": None,
            }
            self._completion_engine.refresh(_conn_with_db)
            self._term.set_engine(self._completion_engine, _conn_with_db)
        except Exception as e:
            self._show_error(f"Failed to start psql process: {e}")
            self._term.append_output(f"\nERROR: Failed to start psql process: {e}\n")
        finally:
            # Never leave the plaintext password in the process environment.
            os.environ.pop("PGPASSWORD", None)

    def _pty_reader(self) -> None:
        exit_reason: str = "clean"
        while self._running and self._pty is not None:
            try:
                data = self._pty.read(blocking=True)
                if not data:
                    break

                # Drain any immediately available bytes into one chunk
                buffer = [data]
                idle_start = time.time()
                while time.time() - idle_start < _PTY_DRAIN_TIMEOUT_S:
                    try:
                        more = self._pty.read(blocking=False)
                        if more:
                            buffer.append(more)
                            idle_start = time.time()
                        else:
                            time.sleep(_PTY_DRAIN_SLEEP_S)
                    except Exception:
                        break

                text = "".join(buffer).replace('\r\n', '\n')
                self._output_received.emit(text)
            except Exception as exc:
                if type(exc).__name__ == "WinptyError":
                    exit_reason = "clean"
                else:
                    exit_reason = str(exc) or type(exc).__name__
                break
        self._running = False
        if exit_reason == "clean":
            # Show the psql.exe directory as a Windows-style shell prompt,
            # exactly as the real cmd.exe / pgAdmin console would.
            psql_dir = ""
            if getattr(self, "_psql_exe_path", ""):
                psql_dir = str(Path(self._psql_exe_path).parent)
            shell_prompt = f"\n{psql_dir}>" if psql_dir else "\n[Process exited]\n"
            if getattr(self, "_first_prompt_pos", 0) == 0 and not psql_dir:
                shell_prompt += "[Hint: psql exited before showing a prompt. The connection may have failed, or the executable might be missing dependencies.]\n"
            self._output_received.emit(shell_prompt)
        else:
            self._output_received.emit(f"\n[Process exited unexpectedly: {exit_reason}]\n")


    def _on_output_received(self, text: str) -> None:
        if not text:
            return

        self._term.append_output(text)

        # Scrollbar visibility can change mid-session as output accumulates;
        # re-sync cols so psql's expanded=auto stays correct.
        self._resize_timer.start()

        # Detect the first psql prompt — everything before it is connection
        # preamble (version, WARNING, SSL line, "Type help") and should be
        # excluded from Copy Output.
        if self._first_prompt_pos == 0:
            text_lower = text.lower()
            if "=#" in text or "=>" in text:
                self._first_prompt_pos = self._term._input_start
                self._hide_spinner()
            elif "password" in text_lower and ":" in text_lower:
                self._hide_spinner()
            elif "[process exited" in text_lower or (">" in text and self._first_prompt_pos == 0):
                self._hide_spinner()

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

        if stripped and self._first_prompt_pos > 0:
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
            # After \q the user sees a shell-style prompt.
            # Typing `psql` relaunches the session, just like the real console.
            import shlex
            try:
                cmd_parts = shlex.split(stripped)
            except ValueError:
                cmd_parts = stripped.split()

            base_cmd = cmd_parts[0].lower() if cmd_parts else ""
            if base_cmd in ("usql", "psql"):
                if len(cmd_parts) > 1:
                    args = cmd_parts[1:]
                    c = self._conn.copy()
                    i = 0
                    while i < len(args):
                        arg = args[i]
                        if arg in ("-h", "--host") and i + 1 < len(args):
                            c["host"] = args[i+1]
                            for k in ("uri", "connection_string", "service_uri", "dsn", "password"):
                                c.pop(k, None)
                            i += 2
                        elif arg in ("-p", "--port") and i + 1 < len(args):
                            c["port"] = args[i+1]
                            i += 2
                        elif arg in ("-U", "--username") and i + 1 < len(args):
                            c["user"] = args[i+1]
                            for k in ("uri", "connection_string", "service_uri", "dsn", "password"):
                                c.pop(k, None)
                            i += 2
                        elif arg in ("-d", "--dbname") and i + 1 < len(args):
                            self._current_db = args[i+1]
                            i += 2
                        elif arg.startswith("postgres://") or arg.startswith("postgresql://"):
                            c["uri"] = arg
                            c.pop("password", None)
                            self._current_db = arg.split("/")[-1].split("?")[0]
                            i += 1
                        elif not arg.startswith("-"):
                            self._current_db = arg
                            i += 1
                        else:
                            i += 1
                    self._conn = c
                    self._update_tab_title(f"USQL Tool – {self._current_db}")
                    self._update_conn_label()

                self._reconnect()
            else:
                psql_dir = ""
                if self._psql_exe_path:
                    psql_dir = str(Path(self._psql_exe_path).parent)
                hint = f"\n'{stripped}' is not recognized. Type 'psql' to reconnect (e.g. 'psql -h <host> -U <user> <dbname>').\n{psql_dir}>"
                self._term.append_output(hint)
            return

        # \q — send to psql so it exits naturally; the PTY reader will then
        # display the psql.exe directory as a Windows shell prompt.

        # Replace internal \n with \r\n so winpty processes them as separate lines.
        try:
            self._pty.write(cmd.rstrip("\n").replace("\n", "\r\n") + "\r\n")
        except Exception as exc:
            self._term.append_output(f"\n[Error writing to process: {exc}]\n")

        # Track \c / \connect for db-name state
        # Use lowercased command to detect the meta-command prefix case-insensitively,
        # but take the db name from the lowercased parts so psql receives it verbatim.
        lower = stripped.lower()
        if lower.startswith("\\c ") or lower.startswith("\\connect "):
            lower_parts = lower.split()
            if len(lower_parts) >= 2:
                self._pending_db_switch_from = self._current_db
                self._current_db = lower_parts[1]
                self._update_tab_title(f"USQL Tool – {self._current_db}")
                self._update_conn_label()
                if self._completion_engine is not None:
                    updated_conn = {**self._conn, "database": self._current_db}
                    self._completion_engine.refresh(updated_conn)

    def _on_interrupt(self) -> None:
        """Cancel the current query via Ctrl+C (0x03)."""
        if self._running and self._pty is not None:
            try:
                self._pty.write("\x03")
            except Exception:
                pass


    def _history_key(self) -> str:
        """Return the stable history key for this session (fixed at load time)."""
        if self._session_history_key:
            return self._session_history_key
        c = self._conn
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        return f"{user}@{host}:{port}/{self._current_db}"

    def _load_history(self) -> None:
        # Pin the history key now so \c switches later in the session
        # don't redirect history entries to a different key on save.
        c = self._conn
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        self._session_history_key = f"{user}@{host}:{port}/{self._current_db}"
        try:
            if _HISTORY_FILE.exists():
                data: dict = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
                self._history = data.get(self._session_history_key, [])
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




    def _copy_output(self) -> None:
        """Copy terminal output to the clipboard.

        If the user has a selection, copies that selection only.
        Otherwise copies from the first psql prompt onward (skipping the
        banner and connection preamble) up to but not including the
        in-progress input line.
        """
        cursor = self._term.textCursor()
        if cursor.hasSelection():
            QApplication.clipboard().setText(cursor.selectedText().replace("\u2029", "\n"))
        else:
            # Start after the psql connection preamble (banner + version + warnings).
            # Fall back to 0 if the first prompt has not been seen yet.
            start = self._first_prompt_pos
            end = self._term._input_start
            if start >= end:
                return  # nothing meaningful to copy yet
            doc_cursor = QTextCursor(self._term.document())
            doc_cursor.setPosition(start)
            doc_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            output_text = doc_cursor.selectedText().replace("\u2029", "\n").rstrip()
            QApplication.clipboard().setText(output_text)

    def _clear(self) -> None:
        """Wipe all terminal output, preserving any in-progress typed input."""
        pending = self._term.current_input()
        self._term.clear()
        self._term.reset_input_start()
        self._first_prompt_pos = 0
        if pending:
            self._term.set_input_text(pending)
        # Ask the live psql process to re-print its prompt so the DB name is visible.
        if self._running and self._pty is not None:
            try:
                self._pty.write("\r\n")
            except Exception:
                pass

    def _reconnect(self) -> None:
        self.close_process()
        self._hide_error()
        self._load_history()
        self._term.append_output("\n")
        self._start_session(reset_ui=False)


    def _show_error(self, message: str) -> None:
        self._err_lbl.setText(f"{message}")
        self._err_frame.setVisible(True)

    def _hide_error(self) -> None:
        self._err_frame.setVisible(False)


    def _update_tab_title(self, title: str) -> None:
        widget = self.parent()
        while widget is not None:
            if hasattr(widget, "indexOf") and hasattr(widget, "setTabText"):
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
