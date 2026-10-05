"""
dialogs/tools/query_describe_dialog.py
Implements the "Describe (parse) select query" feature similar to Toad for Oracle.
Allows developers to parse and inspect the schema of any SELECT query without
fetching all data rows.
"""

import re
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QTextCharFormat,
    QSyntaxHighlighter,
    QTextCursor,
    QIcon,
)
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QPlainTextEdit,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QLineEdit,
    QComboBox,
    QToolButton,
    QFileDialog,
    QApplication,
    QFrame,
    QWidget,
    QAbstractItemView,
)
import qtawesome as qta

from ui.components import SecondaryButton, LoadingOverlay
from workers.workers import WorkerThread
from db.query_describe import describe_select_query, format_describe_text


class DescribeHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Query Describe text view."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Data types (blue / cyan)
        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#0369a1"))  # Sky 700 / nice IDE blue
        type_format.setFontWeight(QFont.Weight.Bold)

        types = [
            "NUMBER", "VARCHAR2", "VARCHAR", "NVARCHAR2", "NVARCHAR", "CHAR", "NCHAR",
            "DATE", "TIMESTAMP", "CLOB", "NCLOB", "BLOB", "BFILE", "RAW", "LONG",
            "INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE",
            "DECIMAL", "NUMERIC", "BOOLEAN", "BOOL", "ROWID", "UROWID", "XMLTYPE",
            "TEXT", "JSON", "JSONB", "UUID", "TIME", "TIMETZ", "TIMESTAMPTZ",
            "BINARY_FLOAT", "BINARY_DOUBLE", "BYTEA", "REAL",
            "WITH TIME ZONE", "WITH LOCAL TIME ZONE",
        ]
        for t in types:
            self.rules.append((rf"\b{t}\b", type_format))

        # Precision / Size parameters like (100) or (10, 2)
        param_format = QTextCharFormat()
        param_format.setForeground(QColor("#b45309"))  # Amber 700 / reddish-brown
        self.rules.append((r"\(\s*\d+(?:\s*,\s*\d+)?\s*\)", param_format))

        # NOT NULL constraint (bold red)
        not_null_format = QTextCharFormat()
        not_null_format.setForeground(QColor("#b91c1c"))  # Red 700
        not_null_format.setFontWeight(QFont.Weight.Bold)
        self.rules.append((r"\bNOT\s+NULL\b", not_null_format))

        # NULL keyword (grey)
        null_format = QTextCharFormat()
        null_format.setForeground(QColor("#64748b"))
        self.rules.append((r"\bNULL\b", null_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class DescribeLineNumberArea(QWidget):
    """Line number gutter matching Toad for Oracle."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class DescribeEditor(QPlainTextEdit):
    """Read-only editor displaying describe text with line numbers and syntax highlighting."""

    cursor_moved = Signal(int, int)  # line, col

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.line_number_area = DescribeLineNumberArea(self)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.document().setDefaultFont(font)

        self.highlighter = DescribeHighlighter(self.document())

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                selection-background-color: #bae6fd;
                selection-color: #0f172a;
            }
        """)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        metrics = QFontMetrics(self.font())
        return 12 + metrics.horizontalAdvance('9') * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f8fafc"))

        # Right border line on gutter
        painter.setPen(QColor("#e2e8f0"))
        painter.drawLine(
            self.line_number_area.width() - 1,
            event.rect().top(),
            self.line_number_area.width() - 1,
            event.rect().bottom(),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(self.font())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()

    def highlight_current_line(self):
        selection = QTextEdit.ExtraSelection()
        line_color = QColor("#f0f9ff")  # Soft sky tint
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def _on_cursor_position_changed(self):
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        self.cursor_moved.emit(line, col)


class QueryDescribeDialog(QDialog):
    """
    Toad-like Query Describe window that parses and shows column definitions
    for a given SELECT query.
    """

    def __init__(self, parent=None, conn_data=None, query: str = "", object_name: str = None):
        super().__init__(parent)
        self.conn_data = conn_data or {}
        self.query = query or ""
        self.object_name = object_name
        self.columns = []
        self._filtered_columns = []
        self._worker = None

        if self.object_name:
            self.setWindowTitle(f"Describe: {self.object_name}")
        else:
            self.setWindowTitle("Query Describe")
        self.resize(750, 520)
        self.setMinimumSize(520, 360)
        self.setSizeGripEnabled(True)

        self._init_ui()
        self._start_describe()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Top Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        # Save / Export button
        self.save_btn = QToolButton()
        self.save_btn.setIcon(qta.icon("fa5s.save", color="#475569"))
        self.save_btn.setToolTip("Save Describe Output to File...")
        self.save_btn.clicked.connect(self._save_to_file)
        toolbar.addWidget(self.save_btn)

        # Copy button
        self.copy_btn = QToolButton()
        self.copy_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        self.copy_btn.setToolTip("Copy to Clipboard (Ctrl+C)")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        toolbar.addWidget(self.copy_btn)

        # Select All button
        self.select_all_btn = QToolButton()
        self.select_all_btn.setIcon(qta.icon("mdi.select-all", color="#475569"))
        self.select_all_btn.setToolTip("Select All (Ctrl+A)")
        self.select_all_btn.clicked.connect(self._select_all)
        toolbar.addWidget(self.select_all_btn)

        # Separator
        toolbar.addWidget(self._create_v_separator())

        # View Switcher (Text View vs Grid View)
        self.text_view_btn = QToolButton()
        self.text_view_btn.setIcon(qta.icon("fa5s.align-left", color="#475569"))
        self.text_view_btn.setToolTip("Text View (Toad Style)")
        self.text_view_btn.setCheckable(True)
        self.text_view_btn.setChecked(True)
        self.text_view_btn.clicked.connect(lambda: self._set_view_mode(0))
        toolbar.addWidget(self.text_view_btn)

        self.grid_view_btn = QToolButton()
        self.grid_view_btn.setIcon(qta.icon("fa5s.table", color="#475569"))
        self.grid_view_btn.setToolTip("Grid View")
        self.grid_view_btn.setCheckable(True)
        self.grid_view_btn.setChecked(False)
        self.grid_view_btn.clicked.connect(lambda: self._set_view_mode(1))
        toolbar.addWidget(self.grid_view_btn)

        # Separator
        toolbar.addWidget(self._create_v_separator())

        # Format Style Dropdown
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Toad Format",
            "DDL Format",
            "Comma Separated Names",
            "Select List",
            "Markdown Table",
        ])
        self.format_combo.setToolTip("Choose output formatting style")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        toolbar.addWidget(self.format_combo)

        # Spacer
        toolbar.addStretch()

        # Search / Filter Box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter columns...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(180)
        self.search_box.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.search_box)

        layout.addLayout(toolbar)

        # ── Query Header Preview (Collapsible) ──
        query_preview = self.query.strip().replace("\n", " ")
        if len(query_preview) > 100:
            query_preview = query_preview[:97] + "..."

        if self.object_name:
            self.header_label = QLabel(
                f"<b>Table:</b> <code>{self.object_name}</code> &nbsp;&nbsp;<span style='color:#64748b;'>({query_preview})</span>"
            )
        else:
            self.header_label = QLabel(f"<b>Query:</b> <code>{query_preview}</code>")
        self.header_label.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 4px 8px;
                color: #334155;
                font-size: 8.5pt;
            }
        """)
        layout.addWidget(self.header_label)

        # ── Stacked View (Text vs Grid) ──
        self.stack = QStackedWidget()

        # 1. Text Viewer
        self.editor = DescribeEditor(self)
        self.editor.cursor_moved.connect(self._update_cursor_status)
        self.stack.addWidget(self.editor)

        # 2. Table Viewer
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Column Name", "Data Type", "Nullable"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                selection-background-color: #e0f2fe;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                border-right: 1px solid #e2e8f0;
                font-weight: 600;
            }
        """)
        self.stack.addWidget(self.table)

        # 3. Error Message Container (shown only if describe fails)
        self.status_view = QWidget()
        status_layout = QVBoxLayout(self.status_view)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #dc2626; font-size: 10.5pt; font-weight: 500;")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        self.stack.addWidget(self.status_view)

        layout.addWidget(self.stack, 1)

        # ── Bottom Status Bar ──
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 2, 4, 2)
        bottom_bar.setSpacing(10)

        # Position info
        self.cursor_pos_label = QLabel("1: 1")
        self.cursor_pos_label.setStyleSheet("color: #64748b; font-size: 9pt; min-width: 60px;")
        bottom_bar.addWidget(self.cursor_pos_label)

        # Columns count info
        self.count_label = QLabel("0 columns")
        self.count_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        bottom_bar.addWidget(self.count_label)

        bottom_bar.addStretch()

        # Close button
        self.close_btn = SecondaryButton("Close")
        self.close_btn.setFixedWidth(80)
        self.close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(self.close_btn)

        layout.addLayout(bottom_bar)

        # Common Loading Spinner Overlay
        self._loading_overlay = LoadingOverlay(self)

    def _create_v_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setStyleSheet("color: #cbd5e1; margin: 2px 4px;")
        return sep

    def _set_view_mode(self, mode: int):
        self.text_view_btn.setChecked(mode == 0)
        self.grid_view_btn.setChecked(mode == 1)
        self.stack.setCurrentIndex(mode)

    def _start_describe(self):
        self._loading_overlay.show_overlay()

        self._worker = WorkerThread(describe_select_query, self.conn_data, self.query)
        self._worker.finished_signal.connect(self._on_describe_finished)
        self._worker.start()

    def _on_describe_finished(self, result, error):
        self._loading_overlay.hide_overlay()
        if error:
            err_msg = str(error)
            self.status_label.setText(f"Error describing query:\n\n{err_msg}")
            self.stack.setCurrentIndex(2)
            return

        self.columns = result or []
        self._filtered_columns = list(self.columns)
        self._update_display()
        self._set_view_mode(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())
            self._loading_overlay.raise_()

    def closeEvent(self, event):
        if hasattr(self, "_loading_overlay"):
            self._loading_overlay.hide_overlay()
        super().closeEvent(event)

    def _on_filter_changed(self, text: str):
        filter_text = text.strip().lower()
        if not filter_text:
            self._filtered_columns = list(self.columns)
        else:
            self._filtered_columns = [
                c for c in self.columns
                if filter_text in c["name"].lower() or filter_text in c["data_type"].lower()
            ]
        self._update_display()

    def _on_format_changed(self):
        self._update_display()

    def _get_current_style_code(self) -> str:
        idx = self.format_combo.currentIndex()
        styles = ["toad", "ddl", "names", "select_list", "markdown"]
        return styles[idx] if 0 <= idx < len(styles) else "toad"

    def _update_display(self):
        # 1. Update text editor
        style_code = self._get_current_style_code()
        text = format_describe_text(self._filtered_columns, style=style_code)
        self.editor.setPlainText(text)

        # 2. Update table
        self.table.setRowCount(len(self._filtered_columns))
        for row, c in enumerate(self._filtered_columns):
            pos_item = QTableWidgetItem(str(c.get("position", row + 1)))
            pos_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, pos_item)

            name_item = QTableWidgetItem(c.get("name", ""))
            name_font = QFont()
            name_font.setBold(True)
            name_item.setFont(name_font)
            self.table.setItem(row, 1, name_item)

            type_item = QTableWidgetItem(c.get("data_type", ""))
            type_item.setForeground(QColor("#0369a1"))
            self.table.setItem(row, 2, type_item)

            is_nullable = c.get("nullable", True)
            null_text = "NOT NULL" if not is_nullable else "NULL"
            null_item = QTableWidgetItem(null_text)
            if not is_nullable:
                null_item.setForeground(QColor("#b91c1c"))
                f = QFont()
                f.setBold(True)
                null_item.setFont(f)
            else:
                null_item.setForeground(QColor("#64748b"))
            self.table.setItem(row, 3, null_item)

        # 3. Update count label
        total = len(self.columns)
        shown = len(self._filtered_columns)
        if shown == total:
            self.count_label.setText(f"{total} columns")
        else:
            self.count_label.setText(f"{shown} of {total} columns")

    def _update_cursor_status(self, line: int, col: int):
        self.cursor_pos_label.setText(f"{line}: {col}")

    def _copy_to_clipboard(self):
        if self.stack.currentIndex() == 1:
            # Copy table view as tab-separated text
            rows = []
            headers = ["#", "Column Name", "Data Type", "Nullable"]
            rows.append("\t".join(headers))
            for c in self._filtered_columns:
                null_str = "NOT NULL" if not c.get("nullable", True) else "NULL"
                rows.append(f"{c['position']}\t{c['name']}\t{c['data_type']}\t{null_str}")
            QApplication.clipboard().setText("\n".join(rows))
        else:
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                QApplication.clipboard().setText(cursor.selectedText())
            else:
                QApplication.clipboard().setText(self.editor.toPlainText())

    def _select_all(self):
        if self.stack.currentIndex() == 0:
            self.editor.selectAll()
        elif self.stack.currentIndex() == 1:
            self.table.selectAll()

    def _save_to_file(self):
        text = self.editor.toPlainText()
        if not text:
            return

        if self.object_name:
            safe_name = self.object_name.replace('"', '').replace('.', '_').replace('[', '').replace(']', '').replace('`', '')
            default_name = f"describe_{safe_name}.txt"
        else:
            default_name = "query_describe.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Query Describe",
            default_name,
            "Text Files (*.txt);;SQL Files (*.sql);;CSV Files (*.csv);;All Files (*.*)",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Save Error", f"Failed to save file: {e}")
