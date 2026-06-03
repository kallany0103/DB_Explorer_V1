# widgets/connection_manager/context_menus/psql_console.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit,
    QLineEdit, QPushButton, QHBoxLayout
)
from PySide6.QtCore import QProcess


class PSQLConsole(QWidget):
    def __init__(self, conn):
        super().__init__()

        self.conn = conn
        self.process = QProcess(self)

        self.init_ui()
        self.start_psql()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter SQL...")

        btn = QPushButton("Send")

        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(btn)

        layout.addWidget(self.output)
        layout.addLayout(row)

        btn.clicked.connect(self.send)
        self.input.returnPressed.connect(self.send)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_output)

    # def start_psql(self):
    #     conn = self.conn or {}

    #     args = [
    #         "wsl",
    #         "psql",
    #         "-h", conn.get("host", ""),
    #         "-p", str(conn.get("port", 5432)),
    #         "-U", conn.get("user", ""),
    #         "-d", conn.get("database", "")
    #     ]

    #     self.process.start("wsl", args)
    
    from PySide6.QtCore import QProcessEnvironment

    def start_psql(self):
        conn = self.conn or {}

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PGPASSWORD", conn.get("password", ""))

        self.process.setProcessEnvironment(env)

        args = [
            "-h", conn.get("host", ""),
            "-p", str(conn.get("port", 5432)),
            "-U", conn.get("user", ""),
            "-d", conn.get("database", "")
        ]

        self.process.start("psql", args)

        if not self.process.waitForStarted():
         self.output.appendPlainText("Failed to start psql")

    def read_output(self):
        out = self.process.readAllStandardOutput().data().decode()
        err = self.process.readAllStandardError().data().decode()

        if out:
            self.output.appendPlainText(out)
        if err:
            self.output.appendPlainText(err)

    def send(self):
        text = self.input.text().strip()
        if not text:
            return

        self.output.appendPlainText("> " + text)
        self.process.write((text + "\n").encode())
        self.input.clear()
        

def open_psql_console(conn, manager=None):
    widget = PSQLConsole(conn)

    if manager and hasattr(manager, "tab_widget"):
        index = manager.tab_widget.addTab(widget, "PSQL Console")
        manager.tab_widget.setCurrentIndex(index)
    else:
        widget.resize(900, 600)
        widget.show()

    return widget