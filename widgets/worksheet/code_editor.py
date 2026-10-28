# code_editor.py
import re
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QWidget,
    QTextEdit,
)
# QTextCursor 
from PySide6.QtGui import (
    QColor,
    QTextFormat,
    QFont,
    QFontMetrics,
    QPainter,
    QPolygon,
    QTextCursor,
    QTextDocument,
    QSyntaxHighlighter,
    QTextCharFormat,
    QPen,
    QWheelEvent,
)
from PySide6.QtCore import QRect, QSize, Qt, QPoint, QEvent



class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0b63c7"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        keywords = [
            "SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "HAVING", "LIMIT",
            "OFFSET", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "ON",
            "AS", "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "BETWEEN",
            "UNION", "ALL", "DISTINCT", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
            "DELETE", "CREATE", "TABLE", "VIEW", "DROP", "ALTER", "ADD", "PRIMARY",
            "KEY", "FOREIGN", "REFERENCES", "INDEX", "CASE", "WHEN", "THEN", "ELSE",
            "END", "WITH", "EXISTS",
        ]
        self.rules.extend((rf"\b{kw}\b", keyword_format) for kw in keywords)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#b05500"))
        self.rules.append((r"'[^']*'", string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#7d3ac1"))
        self.rules.append((r"\b\d+(?:\.\d+)?\b", number_format))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#2f7d4a"))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

        for match in re.finditer(r"--.*$", text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_format)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.code_editor.lineNumberAreaPaintEvent(event)

    def mousePressEvent(self, event):
        self.code_editor.handleLineNumberAreaClick(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.folding_markers = {}
        self.fold_regions = {}
        self.folded_blocks = set()
        self.statement_map = {}
        self._engine = None
        self._conn_data = None
        self._ghost_text = ""
        self._ghost_prefix = ""
        self._ghost_full_match = ""
        self._ghost_accepting = False
        self.folding_gutter_width = 18
        self.auto_uppercase = True
        self.autocomplete_enabled = True
        self.highlight_line_enabled = True
        self.keyword_casing = "UPPERCASE"
        self.identifier_casing = "Preserve (As-is)"
        self.auto_close_chars = True
        self.auto_indent = True

        self._sync_document_font_from_widget()

        self.highlighter = SqlHighlighter(self.document())

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.textChanged.connect(self.updateFoldingMarkers)
        #self.textChanged.connect(self.on_text_changed)

        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self._on_cursor_moved)
        self.updateRequest.connect(self._on_update_request)

        # Ghost text is painted directly in paintEvent (same baseline as the
        # document layout) so it can never drift above/below the typed text.

        self.updateLineNumberAreaWidth(0)
        self.updateFoldingMarkers()
        self.highlightCurrentLine()

    def _sync_document_font_from_widget(self):
        widget_font = self.font()
        if self.document().defaultFont() != widget_font:
            self.document().setDefaultFont(widget_font)


    def lineNumberAreaWidth(self):
        # Find how many digits the highest line number will have
        digits = max(3, len(str(max(1, self.blockCount()))))
        metrics = QFontMetrics(self.document().defaultFont())
        space = 8 + metrics.horizontalAdvance('9') * digits + self.folding_gutter_width
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.updateLineNumberAreaWidth(0)
        self.lineNumberArea.update()
        self.viewport().update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.updateLineNumberAreaWidth(0)
        self.lineNumberArea.update()
        self.viewport().update()


    def showEvent(self, event):
        super().showEvent(event)
        self._sync_document_font_from_widget()
        self.updateLineNumberAreaWidth(0)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))
        self.lineNumberArea.update()
        self.viewport().update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._sync_document_font_from_widget()
            self.updateLineNumberAreaWidth(0)
            if self.lineNumberArea is not None:
                self.lineNumberArea.update()
            self.viewport().update()


    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(event.rect(), QColor(240, 240, 240))  # background

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        metrics = QFontMetrics(self.document().defaultFont())
        height = metrics.height()
        fold_start_x = self.lineNumberArea.width() - self.folding_gutter_width

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # Draw line number
                number = str(blockNumber + 1)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(0, top, fold_start_x - 5,
                                 height, Qt.AlignmentFlag.AlignRight, number)

                # Draw folding marker if exists
                if blockNumber in self.folding_markers:
                    self.drawChevron(painter, fold_start_x, top, blockNumber in self.folded_blocks)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def updateFoldingMarkers(self):
        new_regions = {}
        new_statement_map = {}
        text = self.toPlainText()

        # 1) Statement-based folding and statement map
        block = self.document().begin()
        stmt_start_block = -1

        while block.isValid():
            b_idx = block.blockNumber()
            line_text = block.text().strip()
            is_comment = line_text.startswith('--') or line_text.startswith('/*')

            if stmt_start_block == -1 and line_text and not is_comment:
                stmt_start_block = b_idx

            if ';' in line_text and not is_comment and stmt_start_block != -1:
                boundaries = (stmt_start_block, b_idx)
                for i in range(stmt_start_block, b_idx + 1):
                    new_statement_map[i] = boundaries

                if b_idx > stmt_start_block:
                    new_regions[stmt_start_block] = list(range(stmt_start_block + 1, b_idx + 1))
                stmt_start_block = -1

            block = block.next()

        # fill single-line defaults for statement selection
        total_blocks = self.document().blockCount()
        for i in range(total_blocks):
            if i not in new_statement_map:
                new_statement_map[i] = (i, i)

        # 2) Parenthesis-based folding
        block = self.document().begin()
        while block.isValid():
            b_idx = block.blockNumber()
            line_text = block.text()

            if '(' in line_text and not line_text.strip().startswith('--') and b_idx not in new_regions:
                stack = 0
                found_end = -1
                start_pos = block.position() + line_text.find('(')

                remaining_text = text[start_pos:]
                for i, char in enumerate(remaining_text):
                    if char == '(':
                        stack += 1
                    elif char == ')':
                        stack -= 1
                        if stack == 0:
                            found_end = start_pos + i
                            break

                if found_end != -1:
                    end_block = self.document().findBlock(found_end)
                    if end_block.isValid() and end_block.blockNumber() > b_idx:
                        new_regions[b_idx] = list(range(b_idx + 1, end_block.blockNumber() + 1))

            block = block.next()

        # 3) Consecutive comment lines folding
        block = self.document().begin()
        comment_start = -1

        while block.isValid():
            b_idx = block.blockNumber()
            line = block.text().strip()

            if line.startswith('--'):
                if comment_start == -1:
                    comment_start = b_idx
            else:
                if comment_start != -1:
                    if b_idx - 1 > comment_start:
                        new_regions[comment_start] = list(range(comment_start + 1, b_idx))
                    comment_start = -1

            block = block.next()

        if comment_start != -1 and self.document().blockCount() - 1 > comment_start:
            new_regions[comment_start] = list(range(comment_start + 1, self.document().blockCount()))

        self.fold_regions = new_regions
        self.statement_map = new_statement_map

        # Keep folded state only for still-valid region starts
        self.folded_blocks = {idx for idx in self.folded_blocks if idx in self.fold_regions}

        self.folding_markers = {
            start: {
                'end': children[-1] if children else start,
                'open': start not in self.folded_blocks,
                'children': children,
            }
            for start, children in self.fold_regions.items()
        }

        self.applyFolding()



    def toggleFold(self, block_number: int) -> None:
        if not hasattr(self, "fold_regions") or block_number not in self.fold_regions:
            return

        if block_number in self.folded_blocks:
            self.folded_blocks.remove(block_number)
        else:
            self.folded_blocks.add(block_number)

            # If cursor is inside region being folded, move it to the start block.
            cursor = self.textCursor()
            current_block = cursor.block().blockNumber()
            if current_block in self.fold_regions[block_number]:
                target_block = self.document().findBlockByNumber(block_number)
                new_cursor = self.textCursor()
                new_cursor.setPosition(target_block.position() + target_block.length() - 1)
                self.setTextCursor(new_cursor)

        self.folding_markers[block_number]['open'] = block_number not in self.folded_blocks
        self.applyFolding()

    def applyFolding(self):
        hidden_blocks = set()
        for parent_idx, children in self.fold_regions.items():
            if parent_idx in self.folded_blocks:
                hidden_blocks.update(children)

        block = self.document().begin()
        while block.isValid():
            block_idx = block.blockNumber()
            block.setVisible(block_idx not in hidden_blocks)
            block = block.next()

        self.viewport().update()
        if self.lineNumberArea is not None:
            self.lineNumberArea.update()

    def drawChevron(self, painter, x, y, is_collapsed):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor("#5f6368"))
        pen.setWidthF(1.2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        size = 6
        cx = x + (self.folding_gutter_width // 2) - (size // 2)
        metrics = QFontMetrics(self.document().defaultFont())
        cy = y + (metrics.height() // 2) - (size // 2)

        if is_collapsed:
            poly = QPolygon([
                QPoint(int(cx + 1), int(cy)),
                QPoint(int(cx + size - 1), int(cy + size // 2)),
                QPoint(int(cx + 1), int(cy + size)),
            ])
        else:
            poly = QPolygon([
                QPoint(int(cx), int(cy + 2)),
                QPoint(int(cx + size // 2), int(cy + size - 1)),
                QPoint(int(cx + size), int(cy + 2)),
            ])

        painter.drawPolyline(poly)
        painter.restore()


    def mousePressEvent(self, event):
        margin = self.viewportMargins().left()
        click_x = event.pos().x()

        # Click in line number/folding area
        if click_x < margin:
            block = self.firstVisibleBlock()
            top = self.blockBoundingGeometry(
                block).translated(self.contentOffset()).top()

            while block.isValid():
                bottom = top + self.blockBoundingRect(block).height()
                if top <= event.pos().y() < bottom:
                    break
                block = block.next()
                top = bottom

        super().mousePressEvent(event)


    def handleLineNumberAreaClick(self, event):
        
        pos = event.pos() 
        y = pos.y()
        x = pos.x()

        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(
            block).translated(self.contentOffset()).top()

        while block.isValid():
            bottom = top + self.blockBoundingRect(block).height()
            if top <= y < bottom:
                bn = block.blockNumber()
                
                
                marker_x_start = self.lineNumberArea.width() - self.folding_gutter_width
                
    
            
                if x >= marker_x_start and bn in self.folding_markers:
                    self.toggleFold(bn)
                
            
                elif hasattr(self, 'statement_map') and bn in self.statement_map:
                    start_bn, end_bn = self.statement_map[bn]
                    
                    
                    start_block = self.document().findBlockByNumber(start_bn)
                    end_block = self.document().findBlockByNumber(end_bn)

                    if start_block.isValid() and end_block.isValid():
                    
                        cursor = QTextCursor(start_block)
                        
                        
                        cursor.setPosition(end_block.position() + end_block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
                        
                        
                        self.setTextCursor(cursor)

                break 
            
            block = block.next()
            top = bottom


    def highlightCurrentLine(self):
        extraSelections = []

        if not self.isReadOnly():
            # selection = self.ExtraSelection()
            selection = QTextEdit.ExtraSelection()

            # You can change the highlight color here
            lineColor = QColor("#e8f4ff")  # A light blue color
            selection.format.setBackground(lineColor)

            # This makes the highlight span the entire width of the editor
            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True)

            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)


    # New Edit Methods 

    def indent_selection(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            start_block = cursor.blockNumber()
            
            cursor.setPosition(end)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            end_block = cursor.blockNumber()
            
            cursor.beginEditBlock()
            for i in range(start_block, end_block + 1):
                block = self.document().findBlockByNumber(i)
                file_cursor = QTextCursor(block)
                file_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                file_cursor.insertText("    ") 
            cursor.endEditBlock()
        else:
            self.insertPlainText("    ") 

    def unindent_selection(self):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        start_block = cursor.blockNumber()
        
        cursor.setPosition(end)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        end_block = cursor.blockNumber()
        
        cursor.beginEditBlock()
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            file_cursor = QTextCursor(block)
            file_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            text = block.text()
            if text.startswith("    "):
                file_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
                file_cursor.removeSelectedText()
            elif text.startswith("\t"):
                file_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                file_cursor.removeSelectedText()
        cursor.endEditBlock()

    def toggle_comment(self):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        start_block = cursor.blockNumber()
        
        cursor.setPosition(end)
        # If selection ends at start of block (and spans multiple blocks), don't include that last block
        if cursor.atBlockStart() and end > start:
             cursor.movePosition(QTextCursor.MoveOperation.PreviousBlock)
        
        end_block = cursor.blockNumber()

        cursor.beginEditBlock()
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            file_cursor = QTextCursor(block)
            file_cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            text = block.text()
            if text.strip().startswith("--"):
                pos = text.find("--")
                if pos != -1:
                    file_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, pos)
                    file_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 2)
                    if file_cursor.block().text()[pos+2:].startswith(" "):
                         file_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                    file_cursor.removeSelectedText()
            else:
                # Comment
                file_cursor.insertText("-- ")
        cursor.endEditBlock()

    def initial_caps(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText()
        cursor.insertText(text.title())

    def swap_lines(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        line1 = cursor.block().text()
        if cursor.movePosition(QTextCursor.MoveOperation.Up):
            line2 = cursor.block().text()
            # Select the current line (line2)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(line1)
            # Move to the line below (where line1 was)
            cursor.movePosition(QTextCursor.MoveOperation.Down)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.insertText(line2)
        cursor.endEditBlock()

    def toggle_case(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        
        text = cursor.selectedText()
        if text.isupper():
            new_text = text.lower()
        else:
            new_text = text.upper()
            
        cursor.insertText(new_text)

    def find(self, text, case_sensitive=False, whole_word=False, forward=True):
        if not text:
            return False
            
        options = QTextDocument.FindFlag(0)
        if case_sensitive:
            options |= QTextDocument.FindFlag.FindCaseSensitively
        if whole_word:
            options |= QTextDocument.FindFlag.FindWholeWords
        if not forward:
            options |= QTextDocument.FindFlag.FindBackward
            
        found = super().find(text, options) # This calls QPlainTextEdit.find

        if not found:
            # Wrap around
            cursor = self.textCursor()
            if forward:
                cursor.movePosition(QTextCursor.MoveOperation.Start)
            else:
                cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            found = super().find(text, options)

        return found

    def replace_curr(self, target, replacement, case_sensitive=False, whole_word=False):
        cursor = self.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == target:
             cursor.insertText(replacement)
             self.find(target, case_sensitive, whole_word, True) # Find next
             return True
        return self.find(target, case_sensitive, whole_word, True)

    def replace_all(self, target, replacement, case_sensitive=False, whole_word=False):
        cursor = self.textCursor()
        cursor.beginEditBlock()

        # Start from beginning
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)

        count = 0
        while self.find(target, case_sensitive, whole_word, True):
            cursor = self.textCursor()
            cursor.insertText(replacement)
            count += 1

        cursor.endEditBlock()
        return count

    # --- AUTOCOMPLETE SUPPORT (ghost-text / inline suggestion) ---

    def set_engine(self, engine):
        """Attach a CompletionEngine to this editor."""
        self._engine = engine

    def _current_word_prefix(self):
        """Return the identifier fragment immediately left of the cursor."""
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()
        start = pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == '_'):
            start -= 1
        return text[start:pos]

    def _word_before_cursor(self):
        """Return the full identifier immediately before the cursor position."""
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()[:pos]
        match = re.search(r'(\w+)\s*$', text)
        return match.group(1) if match else ""

    def _compute_ghost(self):
        """Find the best match for the current prefix and show it as ghost text."""
        engine = self._engine
        if not engine:
            return
        prefix = self._current_word_prefix()
        if not prefix:
            self._clear_ghost()
            return
        match = engine.best_match(prefix)
        if match:
            self._ghost_prefix = prefix
            self._ghost_full_match = match   # store full match word for reliable uppercasing
            self._ghost_text = match[len(prefix):]
            self._update_ghost_label()
        else:
            self._clear_ghost()

    def _format_keyword_case(self, word: str) -> str:
        """Format a SQL keyword according to keyword_casing preference."""
        casing = getattr(self, "keyword_casing", "UPPERCASE")
        if casing == "UPPERCASE":
            return word.upper()
        elif casing == "lowercase":
            return word.lower()
        return word

    def _format_identifier_case(self, word: str) -> str:
        """Format an identifier (table, column, schema) according to identifier_casing preference."""
        casing = getattr(self, "identifier_casing", "Preserve (As-is)")
        if casing == "UPPERCASE":
            return word.upper()
        elif casing == "lowercase":
            return word.lower()
        return word

    def _accept_ghost(self):
        """Insert the ghost suggestion and clear the ghost overlay."""
        if not self._ghost_text:
            return
        self._ghost_accepting = True

        full_word = getattr(self, "_ghost_full_match", None) or (self._ghost_prefix + self._ghost_text)
        prefix_len = len(self._ghost_prefix)

        cursor = self.textCursor()

        if self._engine and self._engine.is_keyword(full_word):
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor,
                prefix_len,
            )
            cursor.insertText(self._format_keyword_case(full_word))
        elif prefix_len > 0:
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor,
                prefix_len,
            )
            cursor.insertText(self._format_identifier_case(full_word))
        else:
            cursor.insertText(self._format_identifier_case(self._ghost_text))

        self.setTextCursor(cursor)
        self._ghost_accepting = False
        self._ghost_text = ""
        self._ghost_prefix = ""
        self._ghost_full_match = ""
        self.viewport().update()
        if self._engine:
            self._engine.reset_active_list()

    def _clear_ghost(self):
        """Discard any pending suggestion and repaint to remove it."""
        self._ghost_text = ""
        self._ghost_prefix = ""
        self._ghost_full_match = ""
        self.viewport().update()

    def _try_uppercase_word_before_cursor(self):
        """If the word immediately left of the cursor is a SQL keyword or identifier, format according to preferences."""
        engine = self._engine
        if not engine:
            return
        
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()[:pos]
        match = re.search(r'(\w+)\s*$', text)
        if not match:
            return
            
        word = match.group(1)
        start_pos = match.start(1)
        end_pos = match.end(1)

        if engine.is_keyword(word):
            formatted = self._format_keyword_case(word)
        elif getattr(self, "identifier_casing", "Preserve (As-is)") != "Preserve (As-is)":
            formatted = self._format_identifier_case(word)
        else:
            return

        if word == formatted:
            return  # already formatted properly
            
        cursor.setPosition(start_pos)
        cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(formatted)
        cursor.setPosition(pos)
        self.setTextCursor(cursor)

    def _update_ghost_label(self):
        """Request a repaint so paintEvent draws the ghost at the baseline."""
        if self._ghost_text:
            self.viewport().update()
        else:
            self.viewport().update()

    def _update_ghost_label_pos(self):
        """Kept for compatibility; painting tracks the cursor automatically."""
        if self._ghost_text:
            self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._ghost_text:
            return
        cr = self.cursorRect()
        if not self.viewport().rect().intersects(cr):
            return
        # Anchor the ghost to the cursor rect itself (same top/ascent as the
        # typed text) so it can never drift above/below the current line.
        painter = QPainter(self.viewport())
        painter.setFont(self.document().defaultFont())
        painter.setPen(QColor("#AAAAAA"))
        metrics = QFontMetrics(self.document().defaultFont())
        x = cr.left() + self.cursorWidth()
        y = cr.top() + metrics.ascent()
        painter.drawText(x, y, self._ghost_text)
        painter.end()

    def _on_cursor_moved(self):
        """Clear ghost text whenever the cursor moves (unless we caused it)."""
        if not self._ghost_accepting:
            self._clear_ghost()

    def _on_update_request(self, _rect, dy):
        """Viewport scroll repaints automatically; nothing to reposition."""
        if dy and self._ghost_text:
            self.viewport().update()

    def keyPressEvent(self, event):
        engine = self._engine

        # 1. Tab or Right Arrow — accept ghost suggestion
        if engine and self._ghost_text:
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Right):
                self._accept_ghost()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._clear_ghost()
                return

        # 1b. Tab with no ghost — format word before cursor if keyword/identifier
        if engine and not self._ghost_text and event.key() == Qt.Key.Key_Tab:
            self._try_uppercase_word_before_cursor()
            return

        # 2. Ctrl+Space — force-show ghost for current prefix
        if (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_Space):
            if engine and getattr(self, "autocomplete_enabled", True):
                prefix = self._current_word_prefix()
                match = engine.best_match(prefix) if prefix else ""
                if match:
                    self._ghost_prefix = prefix
                    self._ghost_full_match = match
                    self._ghost_text = match[len(prefix):]
                    self._update_ghost_label()
            return

        # 3. Enter / Return — Auto-indent on Enter
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and getattr(self, "auto_indent", True):
            if self._ghost_text:
                self._clear_ghost()
            if engine:
                self._try_uppercase_word_before_cursor()

            cursor = self.textCursor()
            current_line = cursor.block().text()
            cursor_pos_in_block = cursor.positionInBlock()
            line_before_cursor = current_line[:cursor_pos_in_block]

            # Measure existing leading whitespace
            indent_match = re.match(r'^(\s*)', current_line)
            indent = indent_match.group(1) if indent_match else ""

            # Check if entering a new block or opening parenthesis
            trimmed_before = line_before_cursor.strip().upper()
            open_parens = line_before_cursor.count('(') - line_before_cursor.count(')')
            open_brackets = line_before_cursor.count('[') - line_before_cursor.count(']')
            open_braces = line_before_cursor.count('{') - line_before_cursor.count('}')

            extra_indent = ""
            tab_spaces = "    "

            if (open_parens > 0 or open_brackets > 0 or open_braces > 0
                    or trimmed_before.endswith(('BEGIN', 'CASE', 'THEN', 'ELSE', 'LOOP', 'DO', 'AS', '('))):
                extra_indent = tab_spaces

            cursor.beginEditBlock()
            cursor.insertText("\n" + indent + extra_indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
            if engine:
                engine.reset_active_list()
            return

        # 4. Auto-Close Characters ('', "", (), [], {})
        text = event.text()
        close_pairs = {
            '(': ')',
            '[': ']',
            '{': '}',
            "'": "'",
            '"': '"',
        }
        # If user typed a closing character and next character is that closing char, step over it
        if getattr(self, "auto_close_chars", True) and text in (')', ']', '}', "'", '"'):
            cursor = self.textCursor()
            if not cursor.hasSelection():
                pos = cursor.position()
                full_text = self.toPlainText()
                next_char = full_text[pos:pos + 1]
                if next_char == text:
                    cursor.movePosition(QTextCursor.MoveOperation.Right)
                    self.setTextCursor(cursor)
                    if self._ghost_text:
                        self._clear_ghost()
                    return

        if getattr(self, "auto_close_chars", True) and text in close_pairs:
            cursor = self.textCursor()
            closing_char = close_pairs[text]

            # If user has selected text, wrap selection with the pair
            if cursor.hasSelection():
                selected = cursor.selectedText()
                cursor.beginEditBlock()
                cursor.insertText(text + selected + closing_char)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                if self._ghost_text:
                    self._clear_ghost()
                return

            # For quotes, avoid auto-pairing if immediately preceded by alphanumeric (e.g. don't)
            pos = cursor.position()
            full_text = self.toPlainText()
            prev_char = full_text[pos - 1:pos] if pos > 0 else ""
            if text in ("'", '"') and prev_char.isalnum():
                super().keyPressEvent(event)
                return

            cursor.beginEditBlock()
            cursor.insertText(text + closing_char)
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            if self._ghost_text:
                self._clear_ghost()
            return

        # 4b. Backspace over auto-closed pair
        if getattr(self, "auto_close_chars", True) and event.key() == Qt.Key.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                pos = cursor.position()
                full_text = self.toPlainText()
                if 0 < pos < len(full_text):
                    prev_char = full_text[pos - 1]
                    next_char = full_text[pos]
                    if (prev_char, next_char) in (('(', ')'), ('[', ']'), ('{', '}'), ("'", "'"), ('"', '"')):
                        cursor.beginEditBlock()
                        cursor.deletePreviousChar()
                        cursor.deleteChar()
                        cursor.endEditBlock()
                        self.setTextCursor(cursor)
                        if self._ghost_text:
                            self._clear_ghost()
                        return

        # 5. Dot — capture word BEFORE super() inserts the dot, then branch:
        if engine and text == '.':
            word = self._word_before_cursor()
            self._clear_ghost()
            super().keyPressEvent(event)
            if word:
                if engine.is_schema(word):
                    formatted_schema = self._format_identifier_case(word)
                    if word != formatted_schema:
                        cur = self.textCursor()
                        cur.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, 1)
                        cur.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(word))
                        cur.insertText(formatted_schema)
                        cur.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 1)
                        self.setTextCursor(cur)
                    items = engine.fetch_for_schema_dot(self._conn_data, word)
                else:
                    items = engine.get_columns_for_table(self._conn_data, word)
                if items and getattr(self, "autocomplete_enabled", True):
                    self._ghost_prefix = ""
                    self._ghost_full_match = ""
                    self._ghost_text = items[0]
                    self._update_ghost_label()
            return

        # 6. Default editor handling; clear any stale ghost first
        if self._ghost_text:
            self._clear_ghost()

        super().keyPressEvent(event)

        if not engine:
            return

        # 7. Reset to base word list on word-breaking characters; also format keywords/identifiers
        if text and text in ' \t\n\r;,()=!<>+-*/%|&\'"':
            self._try_uppercase_word_before_cursor()
            engine.reset_active_list()
            return

        # 8. Skip modifier-only keys except Backspace / Delete
        is_delete = event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
        if not text and not is_delete:
            return

        # 9. Compute and display ghost suggestion
        if getattr(self, "autocomplete_enabled", True):
            self._compute_ghost()

    def wheelEvent(self, event: QWheelEvent):
        """Ctrl+Scroll dynamically zooms font size (clamped 8-32 pt)."""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            current_font = self.font()
            current_size = current_font.pointSize()
            if current_size <= 0:
                current_size = 10
            new_size = max(8, min(32, current_size + (1 if delta > 0 else -1)))
            if new_size != current_size:
                current_font.setPointSize(new_size)
                self.setFont(current_font)
                self._sync_document_font_from_widget()
                self.updateLineNumberAreaWidth(0)
                if self.lineNumberArea:
                    self.lineNumberArea.update()
                self.viewport().update()
            event.accept()
        else:
            super().wheelEvent(event)

    def apply_preferences(self, prefs: dict):
        """Applies editor font, tab stop, word wrap, and line number preferences."""
        if not prefs:
            return

        family = prefs.get("editor_font_family")
        size = prefs.get("editor_font_size")

        current_font = self.font()
        changed_font = False
        if family and current_font.family() != family:
            current_font.setFamily(family)
            changed_font = True
        if size and current_font.pointSize() != int(size):
            current_font.setPointSize(int(size))
            changed_font = True

        if changed_font:
            self.setFont(current_font)
            self._sync_document_font_from_widget()

        tab_size = prefs.get("editor_tab_size")
        if tab_size:
            fm = QFontMetrics(self.font())
            self.setTabStopDistance(fm.horizontalAdvance(' ') * int(tab_size))

        if "editor_word_wrap" in prefs:
            if prefs["editor_word_wrap"]:
                self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            else:
                self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        if "editor_line_numbers" in prefs:
            show_ln = bool(prefs["editor_line_numbers"])
            if hasattr(self, "lineNumberArea") and self.lineNumberArea:
                self.lineNumberArea.setVisible(show_ln)
                if show_ln:
                    self.updateLineNumberAreaWidth(0)
                else:
                    self.setViewportMargins(0, 0, 0, 0)

        if "editor_auto_uppercase" in prefs:
            self.auto_uppercase = bool(prefs["editor_auto_uppercase"])

        if "editor_autocomplete" in prefs:
            self.autocomplete_enabled = bool(prefs["editor_autocomplete"])

        if "editor_highlight_line" in prefs:
            self.highlight_line_enabled = bool(prefs["editor_highlight_line"])
            if hasattr(self, "highlightCurrentLine"):
                self.highlightCurrentLine()

        if "editor_keyword_casing" in prefs:
            self.keyword_casing = prefs["editor_keyword_casing"]

        if "editor_identifier_casing" in prefs:
            self.identifier_casing = prefs["editor_identifier_casing"]

        if "editor_auto_close_chars" in prefs:
            self.auto_close_chars = bool(prefs["editor_auto_close_chars"])

        if "editor_auto_indent" in prefs:
            self.auto_indent = bool(prefs["editor_auto_indent"])