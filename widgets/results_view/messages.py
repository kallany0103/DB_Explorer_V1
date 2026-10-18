from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction, QGuiApplication

def create_message_view(manager, tab_content):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    message_view = QTextEdit()
    message_view.setObjectName("message_view")
    message_view.setReadOnly(True)
    message_view.setFrameShape(QTextEdit.Shape.NoFrame)
    message_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    message_view.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    message_view.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    # Use professional monospaced font
    mono_font = QFont("Consolas", 10)
    if not mono_font.exactMatch():
        mono_font = QFont("Courier New", 10)
    message_view.setFont(mono_font)

    # Seamless borderless styling matching other tabs
    message_view.setStyleSheet("QTextEdit { background-color: #ffffff; border: none; padding: 8px; }")

    # Right-click context menu to allow copying without clicking/focusing
    def _show_context_menu(pos):
        menu = QMenu(message_view)
        copy_all_action = QAction("Copy All", menu)
        copy_all_action.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(message_view.toPlainText())
        )
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(message_view.clear)
        menu.addAction(copy_all_action)
        menu.addAction(clear_action)
        menu.exec(message_view.mapToGlobal(pos))

    message_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    message_view.customContextMenuRequested.connect(_show_context_menu)

    layout.addWidget(message_view)
    return container
