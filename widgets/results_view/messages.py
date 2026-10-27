from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget, QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction, QGuiApplication, QTextCursor


def create_message_view(manager, tab_content):
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    message_view = QTextBrowser()
    message_view.setObjectName("message_view")
    message_view.setReadOnly(True)
    message_view.setOpenExternalLinks(False)
    message_view.setOpenLinks(False)
    message_view.setFrameShape(QTextBrowser.Shape.NoFrame)
    message_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    message_view.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
    )
    message_view.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    # Use professional monospaced font
    mono_font = QFont("Consolas", 10)
    if not mono_font.exactMatch():
        mono_font = QFont("Courier New", 10)
    message_view.setFont(mono_font)

    # Seamless borderless styling matching other tabs
    message_view.setStyleSheet("QTextBrowser { background-color: #ffffff; border: none; padding: 8px; }")

    # Handle compiler error anchor jumps (jump:line:col)
    def _on_anchor_clicked(url):
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("jump:"):
            parts = url_str.split(":")
            if len(parts) >= 3:
                try:
                    line_no = int(parts[1])
                    col_no = int(parts[2])
                    from widgets.worksheet.utils import get_query_editor
                    editor = get_query_editor(tab_content)
                    if editor:
                        doc = editor.document()
                        block = doc.findBlockByLineNumber(max(0, line_no - 1))
                        if block.isValid():
                            tc = QTextCursor(block)
                            tc.movePosition(
                                QTextCursor.MoveOperation.Right,
                                QTextCursor.MoveMode.MoveAnchor,
                                max(0, col_no - 1),
                            )
                            editor.setTextCursor(tc)
                            editor.centerCursor()
                            editor.setFocus()
                except Exception:
                    pass

    message_view.anchorClicked.connect(_on_anchor_clicked)

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
