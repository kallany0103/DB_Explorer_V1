# widgets/db_terminal/editor.py
"""
QPlainTextEdit subclass behaving like a real terminal pane.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor, QWheelEvent
from PySide6.QtWidgets import QApplication, QMenu, QPlainTextEdit


class _TerminalEdit(QPlainTextEdit):
    """
    QPlainTextEdit that behaves like a real terminal input/output pane.

    - Text before _input_start is read-only (previous output + psql prompts).
    - Text from _input_start onward is freely editable (user's current input).
    - Supports: Ctrl+Shift+C/V, Ctrl+L, Ctrl+0, Ctrl+Scroll, Home guard,
      right-click context menu, drag-and-drop schema object names.
    """

    command_entered: Signal = Signal(str)
    history_up: Signal = Signal()
    history_down: Signal = Signal()
    interrupt: Signal = Signal()

    _DEFAULT_FONT_SIZE: int = 10
    _MIN_FONT_SIZE: int = 8
    _MAX_FONT_SIZE: int = 24

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("psql_term")
        self._input_start: int = 0
        self.setUndoRedoEnabled(False)
        self.setAcceptDrops(True)
        self._default_font: QFont = self.font()

    # ------------------------------------------------------------------
    # Public helpers called by the parent widget
    # ------------------------------------------------------------------

    def append_output(self, text: str) -> None:
        """Append psql output and advance the protected zone."""
        cursor = self.textCursor()
        
        # Save current user input
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        user_input = cursor.selectedText().replace("\u2029", "\n")
        
        # Remove user input temporarily
        cursor.removeSelectedText()
        
        # Insert new output
        cursor.insertText(text)
        self._input_start = cursor.position()
        
        # Restore user input
        if user_input:
            cursor.insertText(user_input)
            
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def set_input_text(self, text: str) -> None:
        """Replace the current user input with *text* (history navigation)."""
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._input_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def current_input(self) -> str:
        """Return the text after _input_start (what the user has typed so far)."""
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._input_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End,
            QTextCursor.MoveMode.KeepAnchor,
        )
        return cursor.selectedText().replace("\u2029", "\n")

    def reset_input_start(self) -> None:
        """Advance _input_start to end (after we've appended a newline)."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._input_start = cursor.position()

    def _paste_at_input(self) -> None:
        """Paste clipboard text into the editable input zone."""
        clipboard_text = QApplication.clipboard().text()
        cursor = self.textCursor()
        if cursor.position() < self._input_start:
            cursor.setPosition(self.document().characterCount() - 1)
            self.setTextCursor(cursor)
        self.insertPlainText(clipboard_text)

    # Key handling — the heart of the terminal feel

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        cursor = self.textCursor()
        pos = cursor.position()

        ctrl = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier

        # Ctrl+Shift+C → copy selection
        if key == Qt.Key.Key_C and mods == (ctrl | shift):
            self.copy()
            return

        # Ctrl+Shift+V → paste at input zone
        if key == Qt.Key.Key_V and mods == (ctrl | shift):
            self._paste_at_input()
            return

        # Ctrl+C → interrupt psql query
        if key == Qt.Key.Key_C and (mods & ctrl):
            self.interrupt.emit()
            return

        # Ctrl+L → clear screen
        if key == Qt.Key.Key_L and mods == ctrl:
            parent = self.parent()
            if parent and hasattr(parent, "_clear"):
                parent._clear()
            return

        # Ctrl+0 → reset font to default size
        if key == Qt.Key.Key_0 and mods == ctrl:
            self.setFont(self._default_font)
            return

        # Enter / Return → submit command
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cmd = self.current_input()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText("\n")
            self._input_start = cursor.position()
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            self.command_entered.emit(cmd)
            return

        # Up / Down → history navigation
        if key == Qt.Key.Key_Up:
            self.history_up.emit()
            return
        if key == Qt.Key.Key_Down:
            self.history_down.emit()
            return

        # Home → jump to start of editable zone
        if key == Qt.Key.Key_Home:
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            return

        # Backspace → guard the protected zone
        if key == Qt.Key.Key_Backspace:
            if pos <= self._input_start:
                return
            super().keyPressEvent(event)
            return

        # Delete → guard the protected zone
        if key == Qt.Key.Key_Delete:
            if pos < self._input_start:
                return
            super().keyPressEvent(event)
            return

        # Left → clamp to _input_start
        if key == Qt.Key.Key_Left:
            if pos <= self._input_start:
                return
            super().keyPressEvent(event)
            return

        # Any printable character typed in the protected zone → redirect to end
        if event.text() and not (mods & ctrl):
            if pos < self._input_start:
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.setTextCursor(cursor)

        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ctrl+Scroll → adjust font size, clamped to 8-24 pt."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            font = self.font()
            new_size = max(
                self._MIN_FONT_SIZE,
                min(self._MAX_FONT_SIZE, font.pointSize() + (1 if delta > 0 else -1)),
            )
            font.setPointSize(new_size)
            self.setFont(font)
            event.accept()
        else:
            super().wheelEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """Right-click menu: Copy / Paste / Select All / Clear."""
        menu = QMenu(self)
        menu.addAction("Copy", self.copy)
        menu.addAction("Paste", self._paste_at_input)
        menu.addSeparator()
        menu.addAction("Select All", self.selectAll)
        menu.addSeparator()
        parent = self.parent()
        if parent and hasattr(parent, "_clear"):
            menu.addAction("Clear", parent._clear)
        menu.exec(event.globalPos())

    # Drag-and-drop — schema object names from the explorer tree


    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasText() or event.mimeData().hasFormat(
            "application/x-db-explorer-schema-object"
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasFormat("application/x-db-explorer-schema-object"):
            obj_name = mime.data(
                "application/x-db-explorer-schema-object"
            ).data().decode()
        elif mime.hasText():
            obj_name = mime.text()
        else:
            return
        cursor = self.textCursor()
        if cursor.position() < self._input_start:
            cursor.setPosition(self.document().characterCount() - 1)
            self.setTextCursor(cursor)
        self.insertPlainText(obj_name)
        event.acceptProposedAction()
