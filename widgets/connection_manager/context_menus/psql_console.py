# widgets/connection_manager/context_menus/psql_console.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import QProcess, Qt, QProcessEnvironment
from PySide6.QtCore import QEvent
import subprocess


class PSQLConsole(QWidget):
    """
    Windows GUI + PostgreSQL inside WSL
    Runs:
        wsl.exe psql ...
    """

    def __init__(self, conn):
        super().__init__()

        self.conn = conn
        # self.history = []
        # self.history_index = -1

        # self.setWindowTitle("PSQL Console")
        self.start_psql()

    
    def start_psql(self):
        conn = self.conn or {}

        subprocess.Popen([
            "wt.exe",
            "wsl",
            "psql",
            "-h", conn.get("host",""),
            "-p", str(conn.get("port",5432)),
            "-U", conn.get("user",""),
            "-d", conn.get("database","")
        ])


# ==========================================================
# Open console in tab or window
# ==========================================================
def open_psql_console(conn, manager=None):
    widget = PSQLConsole(conn)
    return widget