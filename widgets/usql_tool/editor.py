# widgets/usql_tool/editor.py
"""
QPlainTextEdit subclass behaving like a real terminal pane.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QTextCharFormat,
    QTextCursor,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QMenu, QPlainTextEdit


class _TerminalEdit(QPlainTextEdit):
    """
    QPlainTextEdit that behaves like a real terminal input/output pane.

    Design principles
    -----------------
    - Text before _input_start is read-only (previous output + psql prompts).
    - Text from _input_start onward is freely editable (user's current input).
    - PTY output is appended via append_output(); the user's in-progress
      input is temporarily removed, output is inserted, then input is
      restored.  This avoids the cursor jumps that happen if you just append
      to the end while the user is mid-typing.
    - ANSI SGR color codes are translated to QTextCharFormat foreground colors.
      All other escape sequences (cursor movement, window title, etc.) are
      silently stripped so they never appear as garbage characters.

    Keyboard shortcuts
    ------------------
    Ctrl+Shift+C  copy selection
    Ctrl+Shift+V  paste into input zone
    Ctrl+C        send SIGINT (interrupt running query)
    Ctrl+L        clear screen
    Ctrl+R        reverse history search
    Ctrl+0        reset font to default size
    Ctrl+Scroll   zoom font size (8–24 pt)
    Up / Down     history navigation
    Home          jump to start of editable input zone
    """

    command_entered: Signal = Signal(str)
    history_up: Signal = Signal()
    history_down: Signal = Signal()
    interrupt: Signal = Signal()
    reverse_search_requested: Signal = Signal()

    _DEFAULT_FONT_SIZE: int = 10
    _MIN_FONT_SIZE: int = 8
    _MAX_FONT_SIZE: int = 24

    # ANSI SGR color map (standard 8 + bright 8)
    _ANSI_COLORS: dict[str, str] = {
        '30': "#494d64",  # black  (dimmed to avoid invisible-on-dark)
        '31': "#ed8796",  # red
        '32': "#a6da95",  # green
        '33': "#eed49f",  # yellow
        '34': "#8aadf4",  # blue
        '35': "#f5bde6",  # magenta
        '36': "#8bd5ca",  # cyan
        '37': "#cad3f5",  # white
        '90': "#5b6078",  # bright black (grey)
        '91': "#ed8796",  # bright red
        '92': "#a6da95",  # bright green
        '93': "#eed49f",  # bright yellow
        '94': "#8aadf4",  # bright blue
        '95': "#f5bde6",  # bright magenta
        '96': "#8bd5ca",  # bright cyan
        '97': "#cad3f5",  # bright white
    }

    # Matches any ANSI/VT escape sequence
    _ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    # Matches specifically SGR sequences (color / style)
    _SGR_RE = re.compile(r'\x1B\[([0-9;]*)m')

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("usql_term")
        self._input_start: int = 0
        self.setMaximumBlockCount(10_000)
        self.setUndoRedoEnabled(False)
        self.setAcceptDrops(True)
        self._default_font: QFont = self.font()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    # ------------------------------------------------------------------
    # Public helpers called by USQLToolWidget
    # ------------------------------------------------------------------

    def append_output(self, text: str) -> None:
        """
        Append psql output and advance the protected zone.

        The user's in-progress input (if any) is temporarily removed,
        the new output inserted with ANSI coloring, then the input is
        restored.  This keeps the cursor logically at the end of the
        input region after every output chunk.
        """
        cursor = self.textCursor()

        # Save current user input
        cursor.setPosition(self._input_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        user_input = cursor.selectedText().replace("\u2029", "\n")

        # Remove it temporarily
        cursor.removeSelectedText()

        # Insert new output with ANSI coloring applied
        self._insert_ansi_text(cursor, text)

        # Advance the protected boundary
        self._input_start = cursor.position()

        # Restore user's in-progress input
        if user_input:
            fmt = cursor.charFormat()
            fmt.setFontWeight(QFont.Weight.Normal)
            cursor.setCharFormat(fmt)
            cursor.insertText(user_input)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _insert_ansi_text(self, cursor: QTextCursor, text: str) -> None:
        """
        Insert *text* into *cursor*, translating ANSI SGR sequences into
        QTextCharFormat foreground colors.  All other escape sequences are
        stripped (not rendered as garbage).
        """
        parts = text.split('\r')
        for i, part in enumerate(parts):
            if i > 0:
                # Simulate terminal carriage return: clear the current line up to cursor
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

            fmt = cursor.charFormat()
            last_end = 0

            for match in self._ANSI_RE.finditer(part):
                start, end = match.span()

                # Insert plain text segment before this escape sequence
                if start > last_end:
                    cursor.setCharFormat(fmt)
                    cursor.insertText(part[last_end:start])

                # Only SGR ('m') sequences affect rendering; everything else is dropped
                code_str = match.group(0)
                if code_str.endswith('m'):
                    sgr = self._SGR_RE.match(code_str)
                    if sgr:
                        for code in sgr.group(1).split(';'):
                            if code in ('0', ''):
                                # Reset all attributes
                                fmt = QTextCharFormat()
                                fmt.setFont(self.font())
                            elif code == '1':
                                fmt.setFontWeight(QFont.Weight.Bold)
                            elif code in self._ANSI_COLORS:
                                fmt.setForeground(QColor(self._ANSI_COLORS[code]))

                last_end = end

            # Insert remaining text after the last escape sequence
            if last_end < len(part):
                cursor.setCharFormat(fmt)
                cursor.insertText(part[last_end:])

    def set_input_text(self, text: str) -> None:
        """Replace the current user input with *text* (for history navigation).

        Handles multi-line commands correctly: each ``\\n`` in *text* is rendered
        as a real line break rather than a literal character.
        """
        # Clamp _input_start in case Qt has trimmed blocks and the offset is stale.
        doc_len = self.document().characterCount() - 1  # exclude trailing \0
        safe_start = min(self._input_start, max(0, doc_len))
        cursor = QTextCursor(self.document())
        cursor.setPosition(safe_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        # insertText() does NOT convert \n to block breaks; split manually.
        lines = text.split("\n")
        cursor.insertText(lines[0])
        for line in lines[1:]:
            cursor.insertBlock()
            cursor.insertText(line)
        self.setTextCursor(cursor)

    def current_input(self) -> str:
        """Return the text after _input_start (what the user has typed so far)."""
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._input_start)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        return cursor.selectedText().replace("\u2029", "\n")

    def reset_input_start(self) -> None:
        """Advance _input_start to the document end."""
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

    # ------------------------------------------------------------------
    # Key handling — the heart of the terminal feel
    # ------------------------------------------------------------------

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

        # Ctrl+Shift+V → paste into input zone
        if key == Qt.Key.Key_V and mods == (ctrl | shift):
            self._paste_at_input()
            return

        # Ctrl+C → interrupt / SIGINT to psql
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

        # Enter / Return → submit command to psql
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cmd = self.current_input()
            # Remove the typed text — the PTY will echo it back authoritatively.
            cursor.setPosition(self._input_start)
            cursor.movePosition(
                QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            self.setTextCursor(cursor)
            self.command_entered.emit(cmd)
            return

        # Up / Down → history navigation
        if key == Qt.Key.Key_Up:
            self.history_up.emit()
            return
        if key == Qt.Key.Key_Down:
            self.history_down.emit()
            return

        # Home → jump to start of editable zone (not document start)
        if key == Qt.Key.Key_Home:
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            return

        # Backspace → guard the protected zone boundary
        if key == Qt.Key.Key_Backspace:
            if pos <= self._input_start:
                return
            super().keyPressEvent(event)
            return

        # Delete → guard the protected zone boundary
        if key == Qt.Key.Key_Delete:
            if pos < self._input_start:
                return
            super().keyPressEvent(event)
            return

        # Left → clamp at _input_start
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

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        cursor = self.textCursor()
        # If user clicked in the protected zone without a selection, send
        # cursor back to the input zone so they can keep typing.
        if cursor.position() < self._input_start and not cursor.hasSelection():
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ctrl+Scroll → adjust font size (clamped to 8–24 pt)."""
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
        """Right-click context menu: Copy / Paste / Select All / Clear."""
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

    # ------------------------------------------------------------------
    # Drag-and-drop — schema object names from the DB explorer tree
    # ------------------------------------------------------------------

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
