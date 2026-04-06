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
)
from PySide6.QtCore import QRect, QSize, Qt, QPoint, QEvent


# {mitayan}
# TODO: This is a basic SQL syntax highlighter. You might want to consider adding
# multi-line comment/string handling if needed.
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
        self.folding_gutter_width = 18

        self._sync_document_font_from_widget()

        self.highlighter = SqlHighlighter(self.document())

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.textChanged.connect(self.updateFoldingMarkers)
        #self.textChanged.connect(self.on_text_changed)

        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.updateFoldingMarkers()
        self.highlightCurrentLine()
# {mitayan}
    def _sync_document_font_from_widget(self):
        widget_font = self.font()
        if self.document().defaultFont() != widget_font:
            self.document().setDefaultFont(widget_font)

# {mitayan}
    def lineNumberAreaWidth(self):
        # Find how many digits the highest line number will have
        digits = max(3, len(str(max(1, self.blockCount()))))
        metrics = QFontMetrics(self.document().defaultFont())
        # 2. Calculate the space needed:
        # horizontalAdvance('9')` gives the pixel width of the widest digit ('9')
        # multiply by digits to cover all digits of the largest line number
        # add 3 pixels as padding
        space = 8 + metrics.horizontalAdvance('9') * digits + self.folding_gutter_width
        # print(space)
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

# {mitayan}
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

# {mitayan}
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

#{mitayan}
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

# {mitayan}


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
#{mitayan}
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
#{mitayan}

    # def on_text_changed(self):
    #     # A simple debounce mechanism could be added here if performance is an issue
    #     self.updateFoldingMarkers()


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
# {siam}

    # --- New Edit Methods ---

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
                # Uncomment: Find first instance of -- and remove it
                # We need to be careful to remove the specific '-- ' or '--' we added
                # Simple approach: remove first occurrence of '--' and optional following space
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
# {siam}