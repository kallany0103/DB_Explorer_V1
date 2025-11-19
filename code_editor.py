# # code_editor

# from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
# from PyQt6.QtGui import QColor, QTextFormat, QFont, QPainter, QPolygon, QBrush
# from PyQt6.QtCore import QRect, QSize, Qt, QPoint

# class LineNumberArea(QWidget):
#     def __init__(self, editor):
#         super().__init__(editor)
#         self.code_editor = editor

#     def sizeHint(self):
#         return QSize(self.code_editor.lineNumberAreaWidth(), 0)

#     def paintEvent(self, event):
#         self.code_editor.lineNumberAreaPaintEvent(event)

#     def mousePressEvent(self, event):
#         self.code_editor.handleLineNumberAreaClick(event)


# class CodeEditor(QPlainTextEdit):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.lineNumberArea = LineNumberArea(self)
#         self.folding_markers = {}

#         # Use monospace font for SQL editing
#         font = QFont("Courier New", 11)
#         self.setFont(font)

#         self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
#         self.updateRequest.connect(self.updateLineNumberArea)
#         self.textChanged.connect(self.updateFoldingMarkers)
#         #self.textChanged.connect(self.on_text_changed)

#         self.cursorPositionChanged.connect(self.highlightCurrentLine)

#         self.updateLineNumberAreaWidth(0)
#         self.highlightCurrentLine()

#     def lineNumberAreaWidth(self):
#         # Find how many digits the highest line number will have
#         digits = len(str(max(1, self.blockCount())))
#         # 2. Calculate the space needed:
#         # horizontalAdvance('9')` gives the pixel width of the widest digit ('9')
#         # multiply by digits to cover all digits of the largest line number
#         # add 3 pixels as padding
#         space = 20 + self.fontMetrics().horizontalAdvance('9') * digits
#         print(space)
#         return space

#     def updateLineNumberAreaWidth(self, _):
#         self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

#     def updateLineNumberArea(self, rect, dy):
#         if dy:
#             self.lineNumberArea.scroll(0, dy)
#         else:
#             self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

#         if rect.contains(self.viewport().rect()):
#             self.updateLineNumberAreaWidth(0)

#     def resizeEvent(self, event):
#         super().resizeEvent(event)
#         cr = self.contentsRect()
#         self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))


#     def lineNumberAreaPaintEvent(self, event):
#         painter = QPainter(self.lineNumberArea)
#         painter.fillRect(event.rect(), QColor(240, 240, 240))  # background

#         block = self.firstVisibleBlock()
#         blockNumber = block.blockNumber()
#         top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
#         bottom = top + int(self.blockBoundingRect(block).height())
#         height = self.fontMetrics().height()

#         while block.isValid() and top <= event.rect().bottom():
#             if block.isVisible() and bottom >= event.rect().top():
#                 # Draw line number
#                 number = str(blockNumber + 1)
#                 painter.setPen(Qt.GlobalColor.black)
#                 painter.drawText(0, top, self.lineNumberArea.width() - 20,
#                                  height, Qt.AlignmentFlag.AlignRight, number)

#                 # Draw folding marker if exists
#                 if blockNumber in self.folding_markers:
#                     marker_rect = QRect(self.lineNumberArea.width() - 15,  # X position (right side of line number area)
#                                         int(top) + (height - 10) // 2,     # Y position (vertically centered)
#                                         10, 10)                            # Width & height of marker (10x10 square)    
#                     painter.setPen(Qt.GlobalColor.black)
#                     painter.setBrush(QBrush(Qt.GlobalColor.black))

#                     if self.folding_markers[blockNumber]['open']:
#                         # Down triangle ▼
#                         points = [
#                             QPoint(marker_rect.left(), marker_rect.top()),
#                             QPoint(marker_rect.right(), marker_rect.top()),
#                             QPoint(marker_rect.center().x(), marker_rect.bottom())
#                         ]
#                     else:
#                         # Right triangle ►
#                         points = [
#                             QPoint(marker_rect.left(), marker_rect.top()),
#                             QPoint(marker_rect.left(), marker_rect.bottom()),
#                             QPoint(marker_rect.right(), marker_rect.center().y())
#                         ]
#                     painter.drawPolygon(QPolygon(points))

#             block = block.next()
#             top = bottom
#             bottom = top + int(self.blockBoundingRect(block).height())
#             blockNumber += 1


#     def updateFoldingMarkers(self):
#         new_markers = {}
#         processed_lines = set()

#         block = self.document().begin()
#         while block.isValid():
#             block_num = block.blockNumber()
#             if block_num in processed_lines:
#                 block = block.next()
#                 continue

            
#             # Find start and end of statement
#             statement_start = None     # Keeps track of where a statement starts
#             temp_block = block         # Start scanning from the current block (line)
#             statement_text = ""        # Accumulates the text of the statement
#             end_block_num = -1         # Marks where the statement ends


#             while temp_block.isValid():
#                 text = temp_block.text().strip()
#                 if text and statement_start is None:
#                     statement_start = temp_block.blockNumber()

#                 if text:  # ignore only empty lines in statement
#                     statement_text += text

#                 if ';' in statement_text:
#                     end_block_num = temp_block.blockNumber()
#                     break
#                 temp_block = temp_block.next()

#             if statement_start is not None and end_block_num > statement_start:
#                 # Found a multi-line statement
#                 is_open = self.folding_markers.get(
#                     statement_start, {'open': True})['open']
#                 new_markers[statement_start] = {
#                     'end': end_block_num, 'open': is_open}
#                 for i in range(statement_start, end_block_num + 1):
#                     processed_lines.add(i)



#             # Move to the next block after the processed statement
#             if end_block_num != -1:
#                 block = self.document().findBlockByNumber(end_block_num).next()
#             else:
#                 block = block.next()

#         self.folding_markers = new_markers
#         self.lineNumberArea.update()



#     def toggleFold(self, block_number: int) -> None:
#         # """
#         #  Fold/unfold the region that starts at `block_number`.
#         # Expects self.folding_markers[block_number] = {"open": bool, "end": int}
#         # """
       
#         if not hasattr(self, "folding_markers") or block_number not in self.folding_markers:
#             return

#         marker = self.folding_markers[block_number]
#         is_open = marker.get("open", True)
#         end_block_num = marker.get("end", block_number)

#         # toggle state update
#         marker["open"] = not is_open

#         doc = self.document()
#         start_block = doc.findBlockByNumber(block_number)

#         # terget end-block find (invalid than end)
#         end_block = doc.findBlockByNumber(end_block_num)
#         if not end_block.isValid():
#             # fallback
#             end_block_num = doc.blockCount() - 1
#             end_block = doc.findBlockByNumber(end_block_num)

#         # 
#         block = start_block.next()
#         while block.isValid() and block.blockNumber() <= end_block_num:
#             block.setVisible(not is_open)  
#             block = block.next()

       
#         start_pos = start_block.position()
#         end_pos = end_block.position() + end_block.length()
#         doc.markContentsDirty(start_pos, max(0, end_pos - start_pos))

#         # ---- UI refresh ----
#         # Text area and line number area update
#         self.viewport().update()
#         if hasattr(self, "lineNumberArea") and self.lineNumberArea is not None:
#             self.lineNumberArea.update()

#     # def on_text_changed(self):
#     #     # A simple debounce mechanism could be added here if performance is an issue
#     #     self.updateFoldingMarkers()


#     def mousePressEvent(self, event):
#         margin = self.viewportMargins().left()
#         click_x = event.pos().x()

#         # Click in line number/folding area
#         if click_x < margin:
#             block = self.firstVisibleBlock()
#             top = self.blockBoundingGeometry(
#                 block).translated(self.contentOffset()).top()

#             while block.isValid():
#                 bottom = top + self.blockBoundingRect(block).height()
#                 if top <= event.pos().y() < bottom:
#                     if block.blockNumber() in self.folding_markers:
#                         self.toggleFold(block.blockNumber())
#                         return
#                     break
#                 block = block.next()
#                 top = bottom

#         super().mousePressEvent(event)


#     def handleLineNumberAreaClick(self, event):
#         # Qt6: .position()
#         y = event.position().y() if hasattr(event, "position") else event.pos().y()

#         block = self.firstVisibleBlock()
#         top = self.blockBoundingGeometry(
#             block).translated(self.contentOffset()).top()

#         while block.isValid():
#             bottom = top + self.blockBoundingRect(block).height()
#             if top <= y < bottom:
#                 bn = block.blockNumber()
#                 if bn in self.folding_markers:
#                     self.toggleFold(bn)
#                 break
#             block = block.next()
#             top = bottom


#     def highlightCurrentLine(self):
#         extraSelections = []

#         if not self.isReadOnly():
#             # selection = self.ExtraSelection()
#             selection = QTextEdit.ExtraSelection()

#             # You can change the highlight color here
#             lineColor = QColor("#e8f4ff")  # A light blue color
#             selection.format.setBackground(lineColor)

#             # This makes the highlight span the entire width of the editor
#             selection.format.setProperty(
#                 QTextFormat.Property.FullWidthSelection, True)

#             selection.cursor = self.textCursor()
#             selection.cursor.clearSelection()
#             extraSelections.append(selection)

#         self.setExtraSelections(extraSelections)
# code_editor.py

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
# QTextCursor ইম্পোর্ট করুন
from PyQt6.QtGui import QColor, QTextFormat, QFont, QPainter, QPolygon, QBrush, QTextCursor
from PyQt6.QtCore import QRect, QSize, Qt, QPoint

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
        self.statement_map = {} # প্রতিটি লাইন কোন স্টেটমেন্টের অংশ তা ম্যাপ করবে

        # Use monospace font for SQL editing
        font = QFont("Courier New", 11)
        self.setFont(font)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.textChanged.connect(self.updateFoldingMarkers)
        #self.textChanged.connect(self.on_text_changed)

        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        # Find how many digits the highest line number will have
        digits = len(str(max(1, self.blockCount())))
        # 2. Calculate the space needed:
        # horizontalAdvance('9')` gives the pixel width of the widest digit ('9')
        # multiply by digits to cover all digits of the largest line number
        # add 3 pixels as padding
        space = 20 + self.fontMetrics().horizontalAdvance('9') * digits
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

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(240, 240, 240))  # background

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                # Draw line number
                number = str(blockNumber + 1)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(0, top, self.lineNumberArea.width() - 20,
                                 height, Qt.AlignmentFlag.AlignRight, number)

                # Draw folding marker if exists
                if blockNumber in self.folding_markers:
                    marker_rect = QRect(self.lineNumberArea.width() - 15,  # X position (right side of line number area)
                                        int(top) + (height - 10) // 2,     # Y position (vertically centered)
                                        10, 10)                            # Width & height of marker (10x10 square)    
                    painter.setPen(Qt.GlobalColor.black)
                    painter.setBrush(QBrush(Qt.GlobalColor.black))

                    if self.folding_markers[blockNumber]['open']:
                        # Down triangle ▼
                        points = [
                            QPoint(marker_rect.left(), marker_rect.top()),
                            QPoint(marker_rect.right(), marker_rect.top()),
                            QPoint(marker_rect.center().x(), marker_rect.bottom())
                        ]
                    else:
                        # Right triangle ►
                        points = [
                            QPoint(marker_rect.left(), marker_rect.top()),
                            QPoint(marker_rect.left(), marker_rect.bottom()),
                            QPoint(marker_rect.right(), marker_rect.center().y())
                        ]
                    painter.drawPolygon(QPolygon(points))

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1


    def updateFoldingMarkers(self):
        new_markers = {}
        new_statement_map = {} # <<< নতুন
        processed_lines = set()

        block = self.document().begin()
        while block.isValid():
            block_num = block.blockNumber()
            if block_num in processed_lines:
                block = block.next()
                continue

            
            # Find start and end of statement
            statement_start = None     # Keeps track of where a statement starts
            temp_block = block         # Start scanning from the current block (line)
            statement_text = ""        # Accumulates the text of the statement
            end_block_num = -1         # Marks where the statement ends


            while temp_block.isValid():
                text = temp_block.text().strip()
                if text and statement_start is None:
                    statement_start = temp_block.blockNumber()

                if text:  # ignore only empty lines in statement
                    statement_text += text

                if ';' in statement_text:
                    end_block_num = temp_block.blockNumber()
                    break
                temp_block = temp_block.next()

            if statement_start is not None and end_block_num != -1:
                # Found a statement (single or multi-line)
                boundaries = (statement_start, end_block_num)

                # 1. সব লাইনের জন্য ম্যাপ আপডেট করুন
                for i in range(statement_start, end_block_num + 1):
                    new_statement_map[i] = boundaries
                    processed_lines.add(i)

                # 2. মাল্টি-লাইন হলে ফোল্ডিং মার্কার যোগ করুন
                if end_block_num > statement_start:
                    is_open = self.folding_markers.get(
                        statement_start, {'open': True})['open']
                    new_markers[statement_start] = {
                        'end': end_block_num, 'open': is_open}

                # Move to the next block after the processed statement
                if end_block_num != -1:
                    block = self.document().findBlockByNumber(end_block_num).next()
                else:
                    block = block.next()
            
            else:
                # --- কোনো স্টেটমেন্ট পাওয়া যায়নি (যেমন: খালি লাইন, কমেন্ট) ---
                if block_num not in processed_lines:
                    new_statement_map[block_num] = (block_num, block_num)
                block = block.next()


        self.folding_markers = new_markers
        self.statement_map = new_statement_map # <<< নতুন
        self.lineNumberArea.update()



    def toggleFold(self, block_number: int) -> None:
        # """
        #  Fold/unfold the region that starts at `block_number`.
        # Expects self.folding_markers[block_number] = {"open": bool, "end": int}
        # """
       
        if not hasattr(self, "folding_markers") or block_number not in self.folding_markers:
            return

        marker = self.folding_markers[block_number]
        is_open = marker.get("open", True)
        end_block_num = marker.get("end", block_number)

        # toggle state update
        marker["open"] = not is_open

        doc = self.document()
        start_block = doc.findBlockByNumber(block_number)

        # terget end-block find (invalid than end)
        end_block = doc.findBlockByNumber(end_block_num)
        if not end_block.isValid():
            # fallback
            end_block_num = doc.blockCount() - 1
            end_block = doc.findBlockByNumber(end_block_num)

        # 
        block = start_block.next()
        while block.isValid() and block.blockNumber() <= end_block_num:
            block.setVisible(not is_open)  
            block = block.next()

       
        start_pos = start_block.position()
        end_pos = end_block.position() + end_block.length()
        doc.markContentsDirty(start_pos, max(0, end_pos - start_pos))

        # ---- UI refresh ----
        # Text area and line number area update
        self.viewport().update()
        if hasattr(self, "lineNumberArea") and self.lineNumberArea is not None:
            self.lineNumberArea.update()

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
                    # লজিকটি handleLineNumberAreaClick এ সরানো হয়েছে
                    # তাই এখানে শুধু break হবে
                    break
                block = block.next()
                top = bottom

        super().mousePressEvent(event)


    def handleLineNumberAreaClick(self, event):
        # event.pos() ব্যবহার করা হলো, কারণ এটি QWidget (LineNumberArea) থেকে আসছে
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
                
                # ফোল্ডিং মার্কারের এক্স-পজিশন (lineNumberAreaPaintEvent অনুযায়ী)
                marker_x_start = self.lineNumberArea.width() - 15 
                
                # --- নতুন সম্মিলিত লজিক ---
                
                # ১. চেক করুন: ফোল্ডিং মার্কারের উপর ক্লিক পড়েছে?
                if x >= marker_x_start and bn in self.folding_markers:
                    self.toggleFold(bn)
                
                # ২. অন্যথায়: লাইন নম্বরের উপর ক্লিক পড়েছে (সিলেকশন লজিক)
                elif hasattr(self, 'statement_map') and bn in self.statement_map:
                    start_bn, end_bn = self.statement_map[bn]
                    
                    # সংশ্লিষ্ট টেক্সট ব্লকগুলো খুঁজুন
                    start_block = self.document().findBlockByNumber(start_bn)
                    end_block = self.document().findBlockByNumber(end_bn)

                    if start_block.isValid() and end_block.isValid():
                        # একটি নতুন কার্সর তৈরি করুন
                        cursor = QTextCursor(start_block)
                        
                        # কার্সরটিকে শেষ ব্লকের শেষ পর্যন্ত মুভ করুন (সিলেকশন সহ)
                        # (length - 1) ব্যবহার করা হয়েছে যাতে পরবর্তী লাইনের নিউলাইন সিলেক্ট না হয়
                        cursor.setPosition(end_block.position() + end_block.length() - 1, QTextCursor.MoveMode.KeepAnchor)
                        
                        # এডিটরের প্রধান কার্সর হিসেবে সেট করুন
                        self.setTextCursor(cursor)

                break # ক্লিক করা ব্লকটি পাওয়া গেছে, লুপ ব্রেক করুন
            
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