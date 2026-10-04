# widgets/sqlplus_tool/terminal_widget.py
"""
Embedded Oracle SQL*Plus terminal widget.

Wraps the bundled sqlplus.exe (resources/oracle/instantclient/) using
pywinpty, building an Easy Connect string from the Oracle conn_data.
"""

from __future__ import annotations

import os
import threading
import time

import qtawesome as qta
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.components import SecondaryButton
from widgets.psql_tool.constants import (
    _PTY_DRAIN_SLEEP_S,
    _PTY_DRAIN_TIMEOUT_S,
    _STYLE,
)
from widgets.psql_tool.editor import _TerminalEdit
from widgets.sqlplus_tool.discovery import admin_dir, find_sqlplus, instantclient_dir

try:
    from winpty import PTY
except ImportError:
    PTY = None

_RESIZE_DEBOUNCE_MS = 350

# Keep the hidden console's buffer wider than any plausible formatted row.
# Windows consoles wrap output at the buffer width regardless of LINESIZE
# (same reason the external launcher runs `mode con cols=1000`). The Qt pane
# scrolls horizontally (NoWrap), so a wide buffer is invisible to the user.
_MIN_CONSOLE_COLS = 1000


class SQLPlusToolWidget(QWidget):
    """
    Embedded native Oracle SQL*Plus terminal tab widget.

    Backend: pywinpty wrapping sqlplus.exe from resources/oracle/instantclient/.
    Connection uses Oracle Easy Connect format: user/pass@//host:port/service_name
    Password is passed in the connection string and cleared from memory after spawn.
    """

    _output_received = Signal(str)
    terminal_closed = Signal()

    def __init__(self, conn: dict) -> None:
        super().__init__()
        self._conn: dict = conn or {}
        self._sqlplus_exe_path: str = ""

        self._history: list[str] = []
        self._history_index: int = 0

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

    def _conn_label_text(self) -> str:
        c = self._conn
        user = c.get("user") or c.get("username") or "oracle"
        host = c.get("host") or "localhost"
        port = c.get("port") or 1521
        service = c.get("service_name") or c.get("database") or "ORCL"
        return f"SQL*Plus  {user}@{host}:{port}/{service}"

    def _build_easy_connect(self) -> str:
        """Build Oracle Easy Connect string: user/pass@//host:port/service_name"""
        c = self._conn
        user = c.get("user") or c.get("username") or ""
        password = c.get("password") or ""
        host = c.get("host") or "localhost"
        port = c.get("port") or 1521
        service = c.get("service_name") or c.get("database") or "ORCL"
        return f"{user}/{password}@//{host}:{port}/{service}"

    # ---------------------------------------------------------------- Session --

    def _start_session(self, reset_ui: bool = True) -> None:
        self._first_prompt_pos = 0
        if reset_ui:
            self._term.reset_input_start()
        self._hide_error()
        self._show_spinner()

        sqlplus_path = find_sqlplus()
        if not sqlplus_path:
            self._show_error(
                "Could not locate sqlplus.exe. "
                "Place Oracle Instant Client files in resources/oracle/instantclient/."
            )
            self._term.append_output(
                "\nERROR: sqlplus.exe not found.\n"
                "Copy Oracle Instant Client (Basic + SQL*Plus ZIPs) into:\n"
                "  resources/oracle/instantclient/\n"
            )
            return
        self._sqlplus_exe_path = sqlplus_path

        if PTY is None:
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

        # Inject instantclient dir into PATH so OCI DLLs are found by sqlplus.exe
        ic_dir = instantclient_dir()
        env_path = os.environ.get("PATH", "")
        if ic_dir and ic_dir not in env_path:
            os.environ["PATH"] = ic_dir + os.pathsep + env_path

        # Always override TNS_ADMIN to point at the bundled sqlnet.ora so that
        # the Oracle 23c client picks up our auth-protocol settings (ORA-28041
        # fix). A system-level TNS_ADMIN from an existing Oracle home must not
        # take precedence over our bundled configuration. admin_dir()
        # resolves the frozen (installed/dist) and dev layouts.
        _bundled_admin = admin_dir()
        if ic_dir:
            os.environ["TNS_ADMIN"] = os.path.join(ic_dir, "network", "admin")
        elif _bundled_admin:
            os.environ["TNS_ADMIN"] = _bundled_admin

        easy_connect = self._build_easy_connect()

        try:
            self._pty = PTY(max(term_cols, _MIN_CONSOLE_COLS), 40)
            # Pass /NOLOG first, then connect via stdin to avoid password in process list
            cmd_line = f'"{sqlplus_path}" /NOLOG'
            self._pty.spawn(cmd_line)
            self._running = True
            self._spawn_time = time.time()
            self._reader_thread = threading.Thread(target=self._pty_reader, daemon=True)
            self._reader_thread.start()
            # Send CONNECT command via PTY stdin — password never appears in cmd args.
            # NOTE: sqlplus on Windows only submits a line on CR; a bare LF
            # is ignored, so every write must end with "\r\n" (same pattern
            # as USQLToolWidget). Pasted multi-line text is normalized too.
            time.sleep(0.3)
            self._pty.write(f"CONNECT {easy_connect}\r\n")
            # Same formatting as the external SQL*Plus launcher: without this
            # SQL*Plus defaults to LINESIZE 80 and wraps wide result sets
            # across multiple staggered line groups.
            for _fmt_cmd in (
                "SET LINESIZE 32000",
                "SET PAGESIZE 100",
                "SET TAB OFF",
                "SET TRIMSPOOL ON",
                "SET TRIMOUT ON",
            ):
                self._pty.write(f"{_fmt_cmd}\r\n")
        except Exception as e:
            self._show_error(f"Failed to start SQL*Plus: {e}")
            self._term.append_output(f"\nERROR: Failed to start SQL*Plus: {e}\n")

    def _pty_reader(self) -> None:
        exit_reason = "clean"
        while self._running and self._pty is not None:
            try:
                data = self._pty.read(blocking=True)
                if not data:
                    break
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
                text = "".join(buffer).replace("\r\n", "\n")
                self._output_received.emit(text)
            except Exception as exc:
                exit_reason = "clean" if type(exc).__name__ == "WinptyError" else str(exc)
                break
        self._running = False

    # ---------------------------------------------------------- Qt slots --

    def _on_output_received(self, text: str) -> None:
        self._hide_spinner()
        self._term.append_output(text)

    def _on_command_entered(self, cmd: str) -> None:
        if self._pty and self._running:
            self._pty.write(cmd.rstrip("\n").replace("\n", "\r\n") + "\r\n")
        if cmd.strip():
            self._history.append(cmd)
            self._history_index = len(self._history)

    def _on_history_up(self) -> None:
        if self._history and self._history_index > 0:
            self._history_index -= 1
            self._term.set_input(self._history[self._history_index])

    def _on_history_down(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._term.set_input(self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self._term.set_input("")

    def _on_interrupt(self) -> None:
        if self._pty and self._running:
            try:
                self._pty.write("\x03")
            except Exception:
                pass

    def _copy_output(self) -> None:
        QApplication.clipboard().setText(self._term.toPlainText())

    def _clear(self) -> None:
        self._term.clear()
        self._term.reset_input_start()

    def _reconnect(self) -> None:
        self.close_process()
        self._start_session(reset_ui=True)

    def _show_error(self, msg: str) -> None:
        self._err_lbl.setText(msg)
        self._err_frame.setVisible(True)

    def _hide_error(self) -> None:
        self._err_frame.setVisible(False)

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
            self._pty.set_size(max(cols, _MIN_CONSOLE_COLS), 40)
        except Exception:
            pass

    # ---------------------------------------------------------- lifecycle --

    def close_process(self) -> None:
        self._running = False
        if self._pty:
            try:
                self._pty.write("EXIT\r\n")
                time.sleep(0.1)
                self._pty.close()
            except Exception:
                pass
            self._pty = None

    def closeEvent(self, event) -> None:
        self._resize_timer.stop()
        self.close_process()
        super().closeEvent(event)


def open_sqlplus_tool(conn: dict, manager=None) -> SQLPlusToolWidget:
    """Create a SQLPlusToolWidget and open it in the main tab widget."""
    tab_widget = None

    if manager is not None:
        main_win = getattr(manager, "main_window", None) or (
            manager if hasattr(manager, "tab_widget") else None
        )
        if main_win:
            tab_widget = getattr(main_win, "tab_widget", None)

    widget = SQLPlusToolWidget(conn)

    if tab_widget is not None:
        try:
            icon = qta.icon("mdi.database-cog", color="#fab387")
        except Exception:
            icon = qta.icon("fa5s.terminal", color="#fab387")

        service = (conn or {}).get("service_name") or (conn or {}).get("database") or "oracle"
        index = tab_widget.addTab(widget, icon, f"SQL*Plus – {service}")
        tab_widget.setCurrentIndex(index)
    else:
        widget.resize(960, 640)
        widget.show()

    return widget
