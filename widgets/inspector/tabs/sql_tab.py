from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

class SqlTab(QWidget):
    def __init__(self, data):
        super().__init__()
        self.init_ui(data)

    def init_ui(self, data):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(data["sql"])
        editor.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10pt; border: 1px solid #e5e7eb; background: #f9fafb; border-radius: 4px; padding: 8px;")
        editor.setMinimumHeight(200)
        layout.addWidget(editor)
