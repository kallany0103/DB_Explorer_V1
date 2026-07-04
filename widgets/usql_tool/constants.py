# widgets/usql_tool/constants.py
"""
Constants and style definitions for the DB Explorer embedded USQL tool.
"""

from __future__ import annotations

import os
from pathlib import Path

# App-data paths (no admin rights needed — user-writable by default)
_APP_DATA_DIR: Path = Path(os.environ.get("APPDATA", "~")).expanduser() / "DBExplorer"
_HISTORY_FILE: Path = _APP_DATA_DIR / "psql_history.json"

# PTY I/O tuning
_PTY_DRAIN_TIMEOUT_S: float = 0.05   # seconds to keep draining after first chunk
_PTY_DRAIN_SLEEP_S: float = 0.005   # sleep between non-blocking drain polls

# Terminal display limits
_TERM_MAX_BLOCKS: int = 10_000       # maximum QPlainTextEdit block (line) count

_STYLE: str = """
/* ---- terminal pane ---- */
QPlainTextEdit#usql_term {
    border           : none;
    font-family      : "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size        : 10pt;
    padding          : 4px 8px;
}

/* ---- thin header bar ---- */
QWidget#term_header {
    border-bottom    : 1px solid palette(mid);
}
QLabel#term_conn_lbl {
    font-family : "Cascadia Code", "Consolas", monospace;
    font-size   : 9pt;
    font-weight : bold;
    background  : transparent;
}
QPushButton#term_btn {
    background    : transparent;
    border        : 1px solid transparent;
    border-radius : 4px;
    font-size     : 9pt;
    padding       : 3px 10px;
    min-width     : 64px;
}
QPushButton#term_btn:hover  { background: palette(alternate-base); border-color: palette(mid); }
QPushButton#term_btn:pressed { background: palette(mid); }

/* ---- error banner ---- */
QFrame#term_err_frame {
    border-bottom : 1px solid red;
}
QLabel#term_err_lbl {
    color      : red;
    font-weight: bold;
    font-size  : 9pt;
    background : transparent;
    padding    : 4px 10px;
}
"""

_BANNER: str = (
    "╔══════════════════════════════════════════════════════════════════╗\n"
    "║  USQL Tool  •  PostgreSQL Interactive Terminal                   ║\n"
    "╠══════════════════════════════════════════════════════════════════╣\n"
    "║  \\?        Show all commands and help                            ║\n"
    "║  \\l        List databases                                        ║\n"
    "║  \\dt       List tables in current schema                         ║\n"
    "║  \\c <db>   Switch database                                       ║\n"
    "║  \\q        Quit terminal                                         ║\n"
    "║  Ctrl+C    Interrupt query                                       ║\n"
    "║  Ctrl+L    Clear screen                                          ║\n"
    "╚══════════════════════════════════════════════════════════════════╝\n"
)
