# widgets/psql_tool/terminal_widget.py
"""
Embedded PostgreSQL psql terminal widget.

Wraps native psql.exe using pywinpty — mirrors the UDS USQLToolWidget
but targets a direct POSTGRES connection instead of a UDS session.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time

from ui.icons import get_icon
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.components import CompactButton, ToastNotification
from widgets.psql_tool.constants import (
    _APP_DATA_DIR,
    _PTY_DRAIN_SLEEP_S,
    _PTY_DRAIN_TIMEOUT_S,
    _STYLE,
)
from widgets.psql_tool.editor import _TerminalEdit
from widgets.psql_tool.discovery import find_psql

try:
    from winpty import PTY
except ImportError:
    PTY = None

_RESIZE_DEBOUNCE_MS = 350
_PSQL_HISTORY_FILE = _APP_DATA_DIR / "psql_tool_history.json"


class PSQLToolWidget(QWidget):
    """
    Embedded native PostgreSQL psql terminal tab widget.

    Backend: pywinpty wrapping psql.exe.
    Targets direct POSTGRES connections (host/port/user/database).
    """

    _output_received = Signal(str)
    terminal_closed = Signal()

    def __init__(
        self,
        conn: dict,
        pg_bin_path: str = "",
        use_wsl: bool = False,
        wsl_distro: str | None = None,
        manager=None,
    ) -> None:
        super().__init__()
        self._conn: dict = conn or {}
        self._pg_bin_path = pg_bin_path
        self._use_wsl = use_wsl
        self._wsl_distro = wsl_distro
        self._manager = manager
        self._psql_exe_path: str = ""

        self._history: list[str] = self._load_history()
        self._history_index: int = len(self._history)
        self._current_db: str = (
            self._conn.get("database") or self._conn.get("db") or "postgres"
        )

        self._pty = None
        self._reader_thread = None
        self._running = False
        self._spawn_time: float = 0.0
        self._first_prompt_pos: int = 0
        self._output_received.connect(self._on_output_received)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._flush_resize)

        self._build_ui()
        self.setStyleSheet(_STYLE)
        self._start_session()

    # ------------------------------------------------------------------ UI --

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

    _SPINNER_FRAMES: list[str] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _make_spinner_overlay(self) -> QLabel:
        lbl = QLabel("⠋  Connecting…")
        lbl.setObjectName("spinner_overlay")
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
        self._spinner_frame_idx: int = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(80)
        self._spinner_timer.timeout.connect(self._advance_spinner_frame)
        return lbl

    def _show_spinner(self) -> None:
        vp = self._term.viewport()
        self._spinner_frame_idx = 0
        lbl = self._spinner_overlay
        lbl.setText(f"{self._SPINNER_FRAMES[0]}  Connecting…")
        lbl.adjustSize()
        lbl.move(
            (vp.width() - lbl.width()) // 2,
            (vp.height() - lbl.height()) // 2,
        )
        lbl.show()
        lbl.raise_()
        self._spinner_timer.start()

    def _hide_spinner(self) -> None:
        self._spinner_timer.stop()
        self._spinner_overlay.hide()

    def _advance_spinner_frame(self) -> None:
        self._spinner_frame_idx = (self._spinner_frame_idx + 1) % len(self._SPINNER_FRAMES)
        frame = self._SPINNER_FRAMES[self._spinner_frame_idx]
        self._spinner_overlay.setText(f"{frame}  Connecting…")
        self._spinner_overlay.adjustSize()
        vp = self._term.viewport()
        lbl = self._spinner_overlay
        lbl.move(
            (vp.width() - lbl.width()) // 2,
            (vp.height() - lbl.height()) // 2,
        )

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("term_header")
        header.setFixedHeight(38)
        header.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e2e8f0;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # 1. Connection & DB identity
        self._conn_lbl = QLabel()
        self._conn_lbl.setObjectName("term_conn_lbl")
        self._conn_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._update_conn_label()
        layout.addWidget(self._conn_lbl)

        # 2. CLI origin pill badge (clean desktop style, no emojis)
        self._path_badge = QLabel()
        self._path_badge.setObjectName("term_path_badge")
        self._path_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path_badge.setStyleSheet("""
            QLabel#term_path_badge {
                color: #475569;
                font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
                font-size: 8.5pt;
                font-weight: 500;
                padding: 3px 10px;
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
            QLabel#term_path_badge:hover {
                color: #0f172a;
                background-color: #f1f5f9;
                border-color: #cbd5e1;
            }
        """)
        self._path_badge.hide()
        layout.addWidget(self._path_badge)

        layout.addStretch()

        # 3. Action buttons
        for icon_key, label, slot in (
            ("msc.copy", "Copy Output", self._copy_output),
            ("msc.trash", "Clear", self._clear),
            ("msc.sync", "Reconnect", self._reconnect),
        ):
            btn = CompactButton(get_icon(icon_key, color="#4b5563"), label)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        return header

    def _update_conn_label(self) -> None:
        c = self._conn
        name = (c.get("name") or c.get("connection_name") or "").strip()
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        db = (
            c.get("database")
            or c.get("dbname")
            or c.get("db_name")
            or c.get("db")
            or getattr(self, "_current_db", "")
            or "postgres"
        )

        target_str = f"{user}@{host}:{port}/{db}"
        is_raw_host = (
            not name
            or name == host
            or ("." in name and (name.endswith((".com", ".net", ".org", ".io", ".cloud")) or any(ch.isdigit() for ch in name)))
        )

        if is_raw_host:
            self._conn_lbl.setText(
                f'<span style="font-family: \'Cascadia Code\', \'Consolas\', monospace; font-size: 9pt; font-weight: 600; color: #0f172a;">{target_str}</span>'
            )
        else:
            self._conn_lbl.setText(
                f'<span style="font-weight: 600; color: #0f172a; font-size: 9.5pt;">{name}</span> '
                f'<span style="font-family: \'Cascadia Code\', \'Consolas\', monospace; font-size: 8.5pt; color: #64748b;">({target_str})</span>'
            )

        self._conn_lbl.setToolTip(f"User: {user}\nHost: {host}:{port}\nDatabase: {db}")

    def _make_error_banner(self) -> QFrame:
        self._err_frame = QFrame()
        self._err_frame.setObjectName("term_err_frame")
        self._err_frame.setVisible(False)
        layout = QHBoxLayout(self._err_frame)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)
        self._err_lbl = QLabel()
        self._err_lbl.setObjectName("term_err_lbl")
        self._err_lbl.setWordWrap(True)
        layout.addWidget(self._err_lbl, 1)

        self._err_settings_btn = QPushButton("Configure in Settings")
        self._err_settings_btn.setObjectName("term_err_settings_btn")
        self._err_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._err_settings_btn.setStyleSheet("""
            QPushButton#term_err_settings_btn {
                background-color: #ef4444;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 9pt;
            }
            QPushButton#term_err_settings_btn:hover {
                background-color: #dc2626;
            }
        """)
        self._err_settings_btn.clicked.connect(self._open_settings)
        self._err_settings_btn.hide()
        layout.addWidget(self._err_settings_btn)
        return self._err_frame

    def _open_settings(self) -> None:
        main_win = getattr(self._manager, "main_window", None) or self._manager
        if main_win and hasattr(main_win, "open_preferences"):
            main_win.open_preferences()
            pref_dlg = getattr(main_win, "_preferences_dialog", None)
            if pref_dlg and hasattr(pref_dlg, "category_list"):
                pref_dlg.category_list.setCurrentRow(4)

    def _conn_label_text(self) -> str:
        c = self._conn
        host = c.get("host") or "localhost"
        port = c.get("port") or 5432
        user = c.get("user") or "postgres"
        return f"psql  {user}@{host}:{port}/{self._current_db}"

    # ---------------------------------------------------------------- Session --

    def _start_session(self, reset_ui: bool = True) -> None:
        self._first_prompt_pos = 0
        if reset_ui:
            self._term.clear()
            self._term.reset_input_start()
        self._hide_error()
        self._show_spinner()

        if self._use_wsl:
            wsl_bin = shutil.which("wsl") or "wsl.exe"
            distro_label = f"WSL: {self._wsl_distro}" if self._wsl_distro else "WSL"
            self._psql_exe_path = f"wsl psql ({self._wsl_distro})" if self._wsl_distro else "wsl psql"
            if hasattr(self, "_path_badge"):
                self._path_badge.setText(f"psql ({distro_label})")
                self._path_badge.setToolTip(
                    f"PostgreSQL Client: {distro_label}\n"
                    f"Running inside Windows Subsystem for Linux ({self._wsl_distro or 'Default'})\n\n"
                    "Click to configure in Settings → Database Tools."
                )
                self._path_badge.mousePressEvent = lambda _e: self._open_settings()
                self._path_badge.show()

            self._term.append_output(f"-- Using client: WSL psql (Linux Subsystem - {self._wsl_distro or 'Default'})\n")

            from widgets.psql_tool.wsl_discovery import check_wsl_postgres
            wsl_info = check_wsl_postgres(self._wsl_distro)
            if not wsl_info.get("available") and not wsl_info.get("timed_out"):
                self._hide_spinner()
                distro_name = self._wsl_distro or "WSL"
                install_cmd = wsl_info.get("install_cmd") or "sudo apt install postgresql-client"
                err_msg = (
                    f"psql is not installed inside WSL ({distro_name}).\n"
                    f"Install it with: {install_cmd}"
                )
                self._show_error(err_msg, show_settings=True)
                self._term.append_output(
                    f"\nERROR: psql not found in WSL ({distro_name}).\n"
                    "To install it, run this command inside your WSL terminal:\n"
                    f"  {install_cmd}\n\n"
                    "Or select a different WSL distribution in Settings → Database Tools.\n"
                )
                return

            if PTY is None:
                self._hide_spinner()
                self._show_error("winpty module is not installed.")
                self._term.append_output(
                    "\nERROR: winpty module is not installed. PTY support unavailable.\n"
                )
                return

            fm = QFontMetrics(self._term.font())
            char_w = fm.horizontalAdvance("W")
            vbar_w = self._term.verticalScrollBar().sizeHint().width()
            usable_w = self._term.viewport().width() - vbar_w
            term_cols = max(80, usable_w // char_w) if char_w > 0 and usable_w > 0 else 80

            c = self._conn
            args = ["-P", "pager=off", "-P", "columns=0", "-P", "expanded=auto"]
            if c.get("host"):
                args.extend(["-h", str(c["host"])])
            if c.get("port"):
                args.extend(["-p", str(c["port"])])
            if c.get("user"):
                args.extend(["-U", c["user"]])
            args.append(f'"{self._current_db}"')

            password = c.get("password") or ""
            escaped_pw = password.replace("'", "'\\''")
            distro_arg = f"-d {self._wsl_distro} " if self._wsl_distro else ""
            cmd_line = f'{wsl_bin} {distro_arg}-e sh -c "PGPASSWORD=\'{escaped_pw}\' psql ' + " ".join(args) + '"'

            try:
                self._pty = PTY(term_cols, 40)
                self._pty.spawn(cmd_line)
                self._running = True
                self._spawn_time = time.time()
                self._reader_thread = threading.Thread(target=self._pty_reader, daemon=True)
                self._reader_thread.start()
            except Exception as e:
                self._hide_spinner()
                self._show_error(f"Failed to start WSL psql: {e}")
                self._term.append_output(f"\nERROR: Failed to start WSL psql: {e}\n")
            return

        psql_path = find_psql(self._pg_bin_path)
        if not psql_path:
            self._hide_spinner()
            err_msg = (
                "Could not locate PostgreSQL client (psql.exe). "
                "Please install PostgreSQL or configure the binary path in Settings → Database Tools."
            )
            self._show_error(err_msg, show_settings=True)
            self._term.append_output(
                "\nERROR: psql.exe not found.\n"
                "To use the embedded PSQL terminal, please install PostgreSQL or\n"
                "set the PostgreSQL Binary Path in Settings → Database Tools.\n"
            )
            return
        self._psql_exe_path = psql_path
        if hasattr(self, "_path_badge"):
            is_custom = bool(self._pg_bin_path)
            p_lower = psql_path.lower()
            if is_custom:
                origin = "Custom"
            elif "pgadmin" in p_lower:
                origin = "pgAdmin 4"
            elif "program files" in p_lower:
                origin = "Standard"
            else:
                origin = "System PATH"

            self._path_badge.setText(f"psql ({origin})")
            self._path_badge.setToolTip(
                f"PostgreSQL Client Executable:\n{psql_path}\n"
                f"Detected via: {origin}\n\n"
                f"Click to configure in Settings → Database Tools."
            )
            self._path_badge.mousePressEvent = lambda _e: self._open_settings()
            self._path_badge.show()

        self._term.append_output(f"-- Using client: {psql_path}\n")

        if PTY is None:
            self._hide_spinner()
            self._show_error("winpty module is not installed.")
            self._term.append_output(
                "\nERROR: winpty module is not installed. PTY support unavailable.\n"
            )
            return

        fm = QFontMetrics(self._term.font())
        char_w = fm.horizontalAdvance("W")
        vbar_w = self._term.verticalScrollBar().sizeHint().width()
        usable_w = self._term.viewport().width() - vbar_w
        term_cols = max(80, usable_w // char_w) if char_w > 0 and usable_w > 0 else 80

        c = self._conn
        args = ["-P", "pager=off", "-P", "columns=0", "-P", "expanded=auto"]

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
        except Exception as e:
            self._hide_spinner()
            self._show_error(f"Failed to start psql: {e}")
            self._term.append_output(f"\nERROR: Failed to start psql: {e}\n")
        finally:
            os.environ.pop("PGPASSWORD", None)

    def _pty_reader(self) -> None:
        pty = self._pty
        while self._running and self._pty is not None and self._pty is pty:
            try:
                data = pty.read(blocking=True)
                if not data:
                    break
                buffer = [data]
                idle_start = time.time()
                while time.time() - idle_start < _PTY_DRAIN_TIMEOUT_S:
                    try:
                        more = pty.read(blocking=False)
                        if more:
                            buffer.append(more)
                            idle_start = time.time()
                        else:
                            time.sleep(_PTY_DRAIN_SLEEP_S)
                    except Exception:
                        break
                text = "".join(buffer).replace("\r\n", "\n")
                self._output_received.emit(text)
            except Exception:
                break
        if self._running:
            self._running = False
            self._output_received.emit("\n[Process exited]\n")

    # ---------------------------------------------------------- Qt slots --

    def _on_output_received(self, text: str) -> None:
        self._hide_spinner()
        self._term.append_output(text)
        if self._first_prompt_pos == 0 and ("=#" in text or "=>" in text):
            self._first_prompt_pos = self._term._input_start

    def _on_command_entered(self, cmd: str) -> None:
        if self._pty and self._running:
            self._pty.write(cmd.rstrip("\n").replace("\n", "\r\n") + "\r\n")
        if cmd.strip():
            self._history.append(cmd)
            self._history_index = len(self._history)
            self._save_history()

    def _load_history(self) -> list[str]:
        try:
            if _PSQL_HISTORY_FILE.exists():
                with open(_PSQL_HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [str(x) for x in data][-1000:]
        except Exception:
            pass
        return []

    def _save_history(self) -> None:
        try:
            _PSQL_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(_PSQL_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history[-1000:], f, indent=2)
        except Exception:
            pass

    def _on_history_up(self) -> None:
        if self._history and self._history_index > 0:
            self._history_index -= 1
            self._term.set_input_text(self._history[self._history_index])

    def _on_history_down(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._term.set_input_text(self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self._term.set_input_text("")

    def _on_interrupt(self) -> None:
        if self._pty and self._running:
            try:
                self._pty.write("\x03")
            except Exception:
                pass

    def _copy_output(self) -> None:
        cursor = self._term.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace("\u2029", "\n")
        else:
            text = self._term.toPlainText().rstrip()
        if text:
            QApplication.clipboard().setText(text)
            ToastNotification.show_toast(self, "Output copied to clipboard", kind="success")
        else:
            ToastNotification.show_toast(self, "No output to copy", kind="info")
        self._term.setFocus()

    def _clear(self) -> None:
        pending = self._term.current_input()
        self._term.clear()
        self._term.reset_input_start()
        self._first_prompt_pos = 0
        if pending:
            self._term.set_input_text(pending)
        if self._running and self._pty is not None:
            try:
                self._pty.write("\r\n")
            except Exception:
                pass
        self._term.setFocus()

    def _reconnect(self) -> None:
        self.close_process()
        self._start_session(reset_ui=True)
        self._term.setFocus()

    def _show_error(self, msg: str, show_settings: bool = False) -> None:
        self._err_lbl.setText(msg)
        if hasattr(self, "_err_settings_btn"):
            self._err_settings_btn.setVisible(show_settings)
        self._err_frame.setVisible(True)

    def _hide_error(self) -> None:
        self._err_frame.setVisible(False)
        if hasattr(self, "_err_settings_btn"):
            self._err_settings_btn.setVisible(False)

    # ---------------------------------------------------------- resize --

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_timer.start()

    def _flush_resize(self) -> None:
        if not (self._pty and self._running):
            return
        fm = QFontMetrics(self._term.font())
        char_w = fm.horizontalAdvance("W")
        vbar_w = self._term.verticalScrollBar().sizeHint().width()
        usable_w = self._term.viewport().width() - vbar_w
        cols = max(80, usable_w // char_w) if char_w > 0 and usable_w > 0 else 80
        try:
            self._pty.set_size(cols, 40)
        except Exception:
            pass

    # ---------------------------------------------------------- lifecycle --

    def close_process(self) -> None:
        self._running = False
        pty = self._pty
        self._pty = None
        if pty is not None:
            try:
                pty.write("\\q\r\n")
            except Exception:
                pass
            try:
                pty.cancel_io()
            except Exception:
                pass
            try:
                del pty
            except Exception:
                pass
        if self._reader_thread and self._reader_thread.is_alive():
            if threading.current_thread() != self._reader_thread:
                self._reader_thread.join(timeout=0.3)
            self._reader_thread = None

    def closeEvent(self, event) -> None:
        self._resize_timer.stop()
        self.close_process()
        super().closeEvent(event)


def open_psql_tool(conn: dict, manager=None) -> PSQLToolWidget:
    """Create a PSQLToolWidget and open it in the main tab widget."""
    pg_bin_path = ""
    use_wsl = False
    wsl_distro = None
    tab_widget = None

    if manager is not None:
        main_win = getattr(manager, "main_window", None) or (
            manager if hasattr(manager, "tab_widget") else None
        )
        if main_win:
            pg_bin_path = getattr(main_win, "pg_bin_path", "") or ""
            use_wsl = bool(getattr(main_win, "use_wsl", False))
            wsl_distro = getattr(main_win, "wsl_distro", None)
            tab_widget = getattr(main_win, "tab_widget", None)

    widget = PSQLToolWidget(
        conn,
        pg_bin_path=pg_bin_path,
        use_wsl=use_wsl,
        wsl_distro=wsl_distro,
        manager=manager,
    )

    if tab_widget is not None:
        icon = get_icon("msc.terminal", color="#89b4fa")

        db_name = (conn or {}).get("database") or (conn or {}).get("db") or "postgres"
        index = tab_widget.addTab(widget, icon, f"PSQL – {db_name}")
        tab_widget.setCurrentIndex(index)
    else:
        widget.resize(960, 640)
        widget.show()

    return widget
