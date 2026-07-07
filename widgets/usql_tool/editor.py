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
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPlainTextEdit

from widgets.usql_tool.constants import _TERM_MAX_BLOCKS


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
        self.setMaximumBlockCount(_TERM_MAX_BLOCKS)
        self.setUndoRedoEnabled(False)
        self.setAcceptDrops(True)
        self._default_font: QFont = self.font()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Ghost-text autocomplete state
        self._engine = None
        self._conn_data: dict | None = None
        self._ghost_text: str = ""
        self._ghost_prefix: str = ""
        self._ghost_full_match: str = ""
        self._ghost_accepting: bool = False

        self._ghost_label = QLabel(self.viewport())
        self._ghost_label.setStyleSheet(
            "QLabel { color: #5b6078; background: transparent; border: none; "
            "margin: 0; padding: 0; }"
        )
        self._ghost_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._ghost_label.hide()

        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.updateRequest.connect(self._on_update_request)

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
    # Autocomplete — engine attachment + ghost-text helpers
    # ------------------------------------------------------------------

    def set_engine(self, engine, conn_data: dict | None = None) -> None:
        """Attach a CompletionEngine for inline ghost-text autocomplete."""
        self._engine = engine
        self._conn_data = conn_data

    def _current_word_prefix(self) -> str:
        """Return the identifier fragment immediately left of the cursor, scoped to the input zone."""
        cursor = self.textCursor()
        pos = cursor.position()
        # Only scan within [_input_start, pos] — never read protected terminal output.
        input_text = self.document().toPlainText()[self._input_start:pos]
        end = len(input_text)
        while end > 0 and (input_text[end - 1].isalnum() or input_text[end - 1] == '_'):
            end -= 1
        return input_text[end:]

    def _word_before_cursor(self) -> str:
        """Return the full identifier immediately before the cursor (for dot-mode detection)."""
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.document().toPlainText()[self._input_start:pos]
        match = re.search(r'(\w+)\s*$', text)
        return match.group(1) if match else ""

    def _compute_ghost(self) -> None:
        """Find the best completion for the current prefix and show it as ghost text."""
        if not self._engine:
            return
        prefix = self._current_word_prefix()
        if not prefix:
            self._clear_ghost()
            return
        best = self._engine.best_match(prefix)
        if best:
            self._ghost_prefix = prefix
            self._ghost_full_match = best
            self._ghost_text = best[len(prefix):]
            self._update_ghost_label()
        else:
            self._clear_ghost()

    def _accept_ghost(self) -> None:
        """Insert the ghost suggestion into the document and reset state."""
        if not self._ghost_text:
            return
        self._ghost_accepting = True
        full_word = self._ghost_full_match or (self._ghost_prefix + self._ghost_text)
        prefix_len = len(self._ghost_prefix)
        cursor = self.textCursor()
        if self._engine and self._engine.is_keyword(full_word):
            # Replace what the user typed with the full uppercased keyword.
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor,
                prefix_len,
            )
            cursor.insertText(full_word.upper())
        else:
            cursor.insertText(self._ghost_text)
        self.setTextCursor(cursor)
        self._ghost_accepting = False
        self._ghost_text = ""
        self._ghost_prefix = ""
        self._ghost_full_match = ""
        self._ghost_label.hide()
        if self._engine:
            self._engine.reset_active_list()

    def _clear_ghost(self) -> None:
        """Hide the ghost label and discard any pending suggestion."""
        self._ghost_text = ""
        self._ghost_prefix = ""
        self._ghost_full_match = ""
        self._ghost_label.hide()

    def _update_ghost_label(self) -> None:
        """Refresh ghost label text, font, and position."""
        if not self._ghost_text:
            self._ghost_label.hide()
            return
        self._ghost_label.setFont(self.font())
        self._ghost_label.setText(self._ghost_text)
        self._ghost_label.adjustSize()
        self._update_ghost_label_pos()
        self._ghost_label.show()
        self._ghost_label.raise_()

    def _update_ghost_label_pos(self) -> None:
        """Move the ghost label to sit immediately after the cursor."""
        if self._ghost_text:
            cr = self.cursorRect()
            self._ghost_label.move(cr.right(), cr.top())

    def _on_cursor_moved(self) -> None:
        """Clear ghost text whenever the cursor moves (unless we caused it)."""
        if not self._ghost_accepting:
            self._clear_ghost()

    def _on_update_request(self, _rect, dy: int) -> None:
        """Reposition the ghost label when the viewport scrolls."""
        if dy and self._ghost_text:
            self._update_ghost_label_pos()

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

        # Ghost-text: Tab / Right → accept suggestion; Escape → dismiss
        if self._engine and self._ghost_text:
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Right):
                self._accept_ghost()
                return
            if key == Qt.Key.Key_Escape:
                self._clear_ghost()
                return

        # Ctrl+Space → force-show ghost for the current word prefix
        if key == Qt.Key.Key_Space and mods == ctrl:
            if self._engine:
                prefix = self._current_word_prefix()
                best = self._engine.best_match(prefix) if prefix else ""
                if best:
                    self._ghost_prefix = prefix
                    self._ghost_full_match = best
                    self._ghost_text = best[len(prefix):]
                    self._update_ghost_label()
            return

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

        # Dot → activate schema.table or table.column completion mode
        if self._engine and event.text() == '.':
            word = self._word_before_cursor()
            self._clear_ghost()
            super().keyPressEvent(event)
            if word:
                if self._engine.is_schema(word):
                    items = self._engine.fetch_for_schema_dot(self._conn_data, word)
                else:
                    items = self._engine.get_columns_for_table(self._conn_data, word)
                if items:
                    self._ghost_prefix = ""
                    self._ghost_full_match = ""
                    self._ghost_text = items[0]
                    self._update_ghost_label()
            return

        super().keyPressEvent(event)

        # After regular character input, compute a new ghost suggestion.
        if self._engine:
            text = event.text()
            if text and text in ' \t\n\r;,()=!<>+-*/%|&\'\'"':
                self._engine.reset_active_list()
            elif text or key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self._compute_ghost()

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
