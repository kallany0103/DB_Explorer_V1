from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

def create_message_view(manager, tab_content):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    message_view = QTextEdit()
    message_view.setObjectName("message_view")
    message_view.setReadOnly(True)
    
    # Enable text selection and copying
    message_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    
    # Use professional monospaced font
    from PySide6.QtGui import QFont
    mono_font = QFont("Consolas", 10)
    if not mono_font.exactMatch():
        mono_font = QFont("Courier New", 10)
    message_view.setFont(mono_font)
    
    # Simple, high-visibility styling
    message_view.setStyleSheet("QTextEdit { background-color: #ffffff; border: 1px solid #C9CFD8; padding: 4px; }")

    layout.addWidget(message_view)
    return container
