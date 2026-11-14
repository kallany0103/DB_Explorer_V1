"""
Cell Value Viewer and Editor Dialog for Universal SQL Client.
Provides formatted JSON, XML, and raw text inspection with line numbers,
search inside text, formatting tools, and safe edit-back to table models.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Optional
import xml.dom.minidom

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from ui.components import PrimaryButton, SecondaryButton


def try_parse_json(text: str) -> tuple[bool, Optional[object]]:
    """
    Attempt to parse text as JSON or Python dict/list representation.
    Handles strict JSON, single-quoted JSON, Python literals (True/False/None),
    and trailing commas. Returns (is_valid, parsed_obj).
    """
    text_stripped = str(text or "").strip()
    if not (
        (text_stripped.startswith("{") and text_stripped.endswith("}"))
        or (text_stripped.startswith("[") and text_stripped.endswith("]"))
    ):
        return False, None

    # 1. Standard strict JSON
    try:
        obj = json.loads(text_stripped)
        return True, obj
    except Exception:
        pass

    # 2. Python dictionary / literal representation (single quotes, True/False/None)
    try:
        val = ast.literal_eval(text_stripped)
        if isinstance(val, (dict, list)):
            return True, val
    except Exception:
        pass

    # 3. Relaxed JSON (e.g. single quotes with lowercase true/false/null)
    try:
        adapted = re.sub(r"\btrue\b", "True", text_stripped)
        adapted = re.sub(r"\bfalse\b", "False", adapted)
        adapted = re.sub(r"\bnull\b", "None", adapted)
        val = ast.literal_eval(adapted)
        if isinstance(val, (dict, list)):
            return True, val
    except Exception:
        pass

    # 4. Remove trailing commas from standard JSON: e.g. [1, 2,] or {"a": 1,}
    try:
        cleaned = re.sub(r",\s*([\]}])", r"\1", text_stripped)
        obj = json.loads(cleaned)
        return True, obj
    except Exception:
        pass

    return False, None


def format_json_string(text: str, indent: int = 2) -> Optional[str]:
    """Parse and format JSON text with indentation."""
    valid, obj = try_parse_json(text)
    if not valid:
        return None
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False)
    except Exception:
        return None


def minify_json_string(text: str) -> Optional[str]:
    """Parse and minify JSON text without extra whitespace."""
    valid, obj = try_parse_json(text)
    if not valid:
        return None
    try:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return None


def try_format_xml(text: str) -> Optional[str]:
    """Attempt to parse and format XML text."""
    text_stripped = str(text or "").strip()
    if text_stripped.startswith("<") and text_stripped.endswith(">"):
        try:
            dom = xml.dom.minidom.parseString(text_stripped)
            formatted = dom.toprettyxml(indent="  ")
            lines = [line for line in formatted.splitlines() if line.strip()]
            return "\n".join(lines)
        except Exception:
            return None
    return None


class JsonXmlHighlighter(QSyntaxHighlighter):
    """
    High-performance syntax highlighter for JSON and XML in CellValueViewerDialog.
    Features single-pass tokenization, block-state multi-line comments, and
    defensive block length capping for multi-megabyte payloads.
    """

    JSON_TOKEN_RE = re.compile(
        r"""(?P<STRING>"(?:\\.|[^"\\\n])*(?:"|$)|'(?:\\.|[^'\\\n])*(?:'|$))|"""
        r'(?P<NUMBER>(?<!\w)-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|'
        r'(?P<KEYWORD>\b(?:true|false|null|True|False|None)\b)'
    )

    XML_TAG_TOKEN = re.compile(
        r'(?P<TAG_OPEN></?[a-zA-Z0-9_\-:]+)|'
        r'(?P<TAG_CLOSE>/?>)|'
        r'(?P<ATTR_NAME>\b[a-zA-Z0-9_\-:]+(?=\s*=))|'
        r"""(?P<ATTR_VAL>=\s*(?:"[^"\\\n]*(?:"|$)|'[^'\\\n]*(?:'|$)))|"""
        r'(?P<PI><\?.*?\?>)|'
        r'(?P<CDATA><!\[CDATA\[.*?\]\]>)'
    )

    MAX_LINE_LENGTH = 10_000

    def __init__(self, parent: Optional[QTextDocument] = None) -> None:
        super().__init__(parent)
        self._mode = "text"

        # JSON token formats
        self.json_key_format = QTextCharFormat()
        self.json_key_format.setForeground(QColor("#6D28D9"))  # Purple-700
        self.json_key_format.setFontWeight(QFont.Weight.Medium)

        self.json_string_format = QTextCharFormat()
        self.json_string_format.setForeground(QColor("#15803D"))  # Green-700

        self.json_number_format = QTextCharFormat()
        self.json_number_format.setForeground(QColor("#C2410C"))  # Orange-700

        self.json_keyword_format = QTextCharFormat()
        self.json_keyword_format.setForeground(QColor("#1E40AF"))  # Navy-800
        self.json_keyword_format.setFontWeight(QFont.Weight.Bold)

        # XML token formats
        self.xml_tag_format = QTextCharFormat()
        self.xml_tag_format.setForeground(QColor("#1D4ED8"))  # Blue-700
        self.xml_tag_format.setFontWeight(QFont.Weight.Medium)

        self.xml_attr_format = QTextCharFormat()
        self.xml_attr_format.setForeground(QColor("#0E7490"))  # Cyan-700

        self.xml_attr_val_format = QTextCharFormat()
        self.xml_attr_val_format.setForeground(QColor("#15803D"))  # Green-700

        self.xml_comment_format = QTextCharFormat()
        self.xml_comment_format.setForeground(QColor("#64748B"))  # Slate-500
        self.xml_comment_format.setFontItalic(True)

    def set_mode(self, mode: Optional[str]) -> None:
        """Sets highlighting mode: 'json', 'xml', or 'text'."""
        m = (mode or "").lower()
        if "json" in m:
            new_mode = "json"
        elif "xml" in m:
            new_mode = "xml"
        else:
            new_mode = "text"

        if self._mode != new_mode:
            self._mode = new_mode
            self.rehighlight()

    @property
    def mode(self) -> str:
        return self._mode

    def highlightBlock(self, text: str) -> None:
        if self._mode == "text":
            self.setCurrentBlockState(0)
            return

        if not text:
            if self._mode == "xml" and self.previousBlockState() == 1:
                self.setCurrentBlockState(1)
            else:
                self.setCurrentBlockState(0)
            return

        if self._mode == "json":
            self._highlight_json(text)
        elif self._mode == "xml":
            self._highlight_xml(text)

    def _highlight_json(self, text: str) -> None:
        self.setCurrentBlockState(0)
        scan_text = text if len(text) <= self.MAX_LINE_LENGTH else text[: self.MAX_LINE_LENGTH]
        for m in self.JSON_TOKEN_RE.finditer(scan_text):
            kind = m.lastgroup
            start = m.start()
            length = m.end() - start
            if kind == "STRING":
                rest = scan_text[m.end() :]
                if rest.lstrip().startswith(":"):
                    self.setFormat(start, length, self.json_key_format)
                else:
                    self.setFormat(start, length, self.json_string_format)
            elif kind == "NUMBER":
                self.setFormat(start, length, self.json_number_format)
            elif kind == "KEYWORD":
                self.setFormat(start, length, self.json_keyword_format)

    def _highlight_xml(self, text: str) -> None:
        scan_text = text if len(text) <= self.MAX_LINE_LENGTH else text[: self.MAX_LINE_LENGTH]
        idx = 0
        state = self.previousBlockState()

        # Check if continuing from previous block comment
        if state == 1:
            end_idx = scan_text.find("-->")
            if end_idx == -1:
                self.setFormat(0, len(text), self.xml_comment_format)
                self.setCurrentBlockState(1)
                return
            else:
                comment_end = end_idx + 3
                self.setFormat(0, comment_end, self.xml_comment_format)
                idx = comment_end
                state = 0

        while idx < len(scan_text):
            comment_start = scan_text.find("<!--", idx)
            if comment_start != -1:
                # Highlight tokens before comment
                segment = scan_text[idx:comment_start]
                self._highlight_xml_tokens(segment, idx)

                # Process comment
                comment_end = scan_text.find("-->", comment_start + 4)
                if comment_end != -1:
                    end_pos = comment_end + 3
                    self.setFormat(comment_start, end_pos - comment_start, self.xml_comment_format)
                    idx = end_pos
                else:
                    self.setFormat(comment_start, len(text) - comment_start, self.xml_comment_format)
                    self.setCurrentBlockState(1)
                    return
            else:
                segment = scan_text[idx:]
                self._highlight_xml_tokens(segment, idx)
                break

        self.setCurrentBlockState(0)

    def _highlight_xml_tokens(self, segment: str, offset: int) -> None:
        for m in self.XML_TAG_TOKEN.finditer(segment):
            kind = m.lastgroup
            start = offset + m.start()
            length = m.end() - m.start()
            if kind in ("TAG_OPEN", "TAG_CLOSE"):
                self.setFormat(start, length, self.xml_tag_format)
            elif kind == "ATTR_NAME":
                self.setFormat(start, length, self.xml_attr_format)
            elif kind == "ATTR_VAL":
                val_str = m.group()
                eq_pos = val_str.find("=")
                if eq_pos != -1:
                    self.setFormat(start, eq_pos + 1, self.xml_attr_format)
                    quote_start = start + eq_pos + 1
                    while quote_start < (start + length) and segment[quote_start - offset].isspace():
                        quote_start += 1
                    if quote_start < (start + length):
                        self.setFormat(quote_start, (start + length) - quote_start, self.xml_attr_val_format)
                else:
                    self.setFormat(start, length, self.xml_attr_val_format)
            elif kind in ("PI", "CDATA"):
                self.setFormat(start, length, self.xml_comment_format)


class LineNumberArea(QWidget):
    """Paints line numbers alongside the code editor."""

    def __init__(self, editor: NumberedPlainTextEdit) -> None:
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.code_editor.line_number_area_paint_event(event)


class NumberedPlainTextEdit(QPlainTextEdit):
    """Monospace text editor with integrated line numbering and custom scroll synchronization."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)

    def line_number_area_width(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#F8FAFC"))

        painter.setPen(QColor("#E2E8F0"))
        painter.drawLine(event.rect().topRight(), event.rect().bottomRight())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setFont(self.font())
        painter.setPen(QColor("#94A3B8"))

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1


class CellValueViewerDialog(QDialog):
    """
    Inspector and multi-line editor for large cell values (JSON, XML, Text).
    Supports format switching, JSON pretty-print, minification, search inside text,
    line numbering, word wrap, and safe model application.
    """

    FORMAT_JSON = "JSON (Formatted)"
    FORMAT_RAW = "Plain Text (Raw)"
    FORMAT_XML = "XML"

    def __init__(
        self,
        raw_value: Optional[object],
        col_name: str = "Column",
        row_num: Optional[int] = None,
        is_read_only: bool = False,
        readonly_reason: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.raw_value = raw_value
        self.original_text = "" if raw_value is None else str(raw_value)
        self.col_name = col_name
        self.row_num = row_num
        self.is_read_only = is_read_only
        self.readonly_reason = readonly_reason
        self._baseline_text = self.original_text
        self.search_matches: list[QTextCursor] = []
        self.current_match_idx = -1

        self._detect_initial_format()
        self._init_window()
        self._init_ui()
        self._load_initial_content()
        self._setup_shortcuts()

    def _detect_initial_format(self) -> None:
        is_json, parsed_obj = try_parse_json(self.original_text)
        if is_json:
            self.current_format = self.FORMAT_JSON
            self._parsed_initial_json = parsed_obj
        elif self.original_text.strip().startswith("<") and self.original_text.strip().endswith(">"):
            self.current_format = self.FORMAT_XML
        else:
            self.current_format = self.FORMAT_RAW

    def _init_window(self) -> None:
        row_str = f" (Row {self.row_num})" if self.row_num is not None else ""
        self.setObjectName("cellViewerDialog")
        action_prefix = "View" if self.is_read_only else "Edit"
        self.setWindowTitle(f"{action_prefix}: {self.col_name}{row_str}")
        self.setWindowIcon(QIcon())
        self.resize(720, 560)
        self.setMinimumSize(480, 360)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Toolbar
        top_bar = QFrame(self)
        top_bar.setObjectName("cellViewerTopBar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 8, 12, 8)
        top_bar_layout.setSpacing(8)

        # Format selector
        format_label = QLabel("View As:", top_bar)
        format_label.setObjectName("cellViewerFormatLabel")
        top_bar_layout.addWidget(format_label)

        self.format_combo = QComboBox(top_bar)
        self.format_combo.setObjectName("cellViewerFormatCombo")
        self.format_combo.addItems([self.FORMAT_JSON, self.FORMAT_RAW, self.FORMAT_XML])
        self.format_combo.setCurrentText(self.current_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        top_bar_layout.addWidget(self.format_combo)

        # Separator
        top_bar_layout.addWidget(self._create_separator())

        # Prettify Button
        self.prettify_btn = QToolButton(top_bar)
        self.prettify_btn.setObjectName("cellViewerPrettifyBtn")
        self.prettify_btn.setIcon(qta.icon("fa5s.indent", color="#2563EB"))
        self.prettify_btn.setText("Format JSON")
        self.prettify_btn.setToolTip("Format / Indent JSON (Ctrl+Shift+F)")
        self.prettify_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.prettify_btn.clicked.connect(self.format_content)
        top_bar_layout.addWidget(self.prettify_btn)

        # Minify Button
        self.minify_btn = QToolButton(top_bar)
        self.minify_btn.setObjectName("cellViewerMinifyBtn")
        self.minify_btn.setIcon(qta.icon("fa5s.compress-alt", color="#475569"))
        self.minify_btn.setText("Minify")
        self.minify_btn.setToolTip("Remove whitespace and compact JSON")
        self.minify_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.minify_btn.clicked.connect(self.minify_content)
        top_bar_layout.addWidget(self.minify_btn)

        # Word wrap toggle
        self.wrap_btn = QToolButton(top_bar)
        self.wrap_btn.setObjectName("cellViewerWrapBtn")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(True)
        self.wrap_btn.setIcon(qta.icon("fa5s.align-left", color="#475569"))
        self.wrap_btn.setText("Wrap")
        self.wrap_btn.setToolTip("Toggle Word Wrap")
        self.wrap_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.wrap_btn.toggled.connect(self._toggle_word_wrap)
        top_bar_layout.addWidget(self.wrap_btn)

        # Search toggle button
        self.search_toggle_btn = QToolButton(top_bar)
        self.search_toggle_btn.setObjectName("cellViewerSearchToggleBtn")
        self.search_toggle_btn.setCheckable(True)
        self.search_toggle_btn.setIcon(qta.icon("fa5s.search", color="#475569"))
        self.search_toggle_btn.setText("Find")
        self.search_toggle_btn.setToolTip("Find in text (Ctrl+F)")
        self.search_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.search_toggle_btn.toggled.connect(self._toggle_search_bar)
        top_bar_layout.addWidget(self.search_toggle_btn)

        top_bar_layout.addStretch()

        # Read-only indicator badge
        if self.is_read_only:
            ro_badge = QFrame(top_bar)
            ro_badge.setObjectName("cellViewerRoBadge")
            ro_badge_layout = QHBoxLayout(ro_badge)
            ro_badge_layout.setContentsMargins(6, 2, 8, 2)
            ro_badge_layout.setSpacing(4)
            ro_icon = QLabel(ro_badge)
            ro_icon.setObjectName("cellViewerRoIcon")
            ro_icon.setPixmap(qta.icon("fa5s.lock", color="#D97706").pixmap(12, 12))
            ro_label = QLabel("Read-Only", ro_badge)
            ro_label.setObjectName("cellViewerRoLabel")
            ro_badge_layout.addWidget(ro_icon)
            ro_badge_layout.addWidget(ro_label)
            if self.readonly_reason:
                ro_badge.setToolTip(f"Read-Only: {self.readonly_reason}")
            top_bar_layout.addWidget(ro_badge)

        main_layout.addWidget(top_bar)

        # 2. Collapsible Search Bar
        self.search_bar = QFrame(self)
        self.search_bar.setObjectName("cellViewerSearchBar")
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(12, 6, 12, 6)
        search_layout.setSpacing(6)

        self.search_input = QLineEdit(self.search_bar)
        self.search_input.setObjectName("cellViewerSearchInput")
        self.search_input.setPlaceholderText("Find in text...")
        self.search_input.addAction(
            qta.icon("fa5s.search", color="#94A3B8"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        self.search_input.installEventFilter(self)
        search_layout.addWidget(self.search_input)

        self.search_count_label = QLabel("0 matches", self.search_bar)
        self.search_count_label.setObjectName("cellViewerSearchCountLabel")
        search_layout.addWidget(self.search_count_label)

        self.prev_match_btn = QToolButton(self.search_bar)
        self.prev_match_btn.setObjectName("cellViewerPrevMatchBtn")
        self.prev_match_btn.setIcon(qta.icon("fa5s.chevron-up", color="#475569"))
        self.prev_match_btn.setToolTip("Previous match (Shift+F3)")
        self.prev_match_btn.clicked.connect(self.find_prev)
        search_layout.addWidget(self.prev_match_btn)

        self.next_match_btn = QToolButton(self.search_bar)
        self.next_match_btn.setObjectName("cellViewerNextMatchBtn")
        self.next_match_btn.setIcon(qta.icon("fa5s.chevron-down", color="#475569"))
        self.next_match_btn.setToolTip("Next match (F3 or Enter)")
        self.next_match_btn.clicked.connect(self.find_next)
        search_layout.addWidget(self.next_match_btn)

        self.case_check = QCheckBox("Match Case", self.search_bar)
        self.case_check.setObjectName("cellViewerCaseCheck")
        self.case_check.toggled.connect(self._on_search_text_changed)
        search_layout.addWidget(self.case_check)

        close_search_btn = QToolButton(self.search_bar)
        close_search_btn.setObjectName("cellViewerCloseSearchBtn")
        close_search_btn.setIcon(qta.icon("fa5s.times", color="#64748B"))
        close_search_btn.setToolTip("Close find bar (Esc)")
        close_search_btn.clicked.connect(lambda: self.search_toggle_btn.setChecked(False))
        search_layout.addWidget(close_search_btn)

        self.search_bar.hide()
        main_layout.addWidget(self.search_bar)

        # 3. Text Editor with Line Numbers
        self.editor = NumberedPlainTextEdit(self)
        self.editor.setObjectName("cellViewerEditor")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        if self.is_read_only:
            self.editor.setReadOnly(True)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_cursor_info)

        # Attach Syntax Highlighter
        self.highlighter = JsonXmlHighlighter(self.editor.document())

        main_layout.addWidget(self.editor, stretch=1)

        # 4. Status Bar
        status_bar = QFrame(self)
        status_bar.setObjectName("cellViewerStatusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 4, 12, 4)

        self.stats_label = QLabel(status_bar)
        self.stats_label.setObjectName("cellViewerStatsLabel")
        status_layout.addWidget(self.stats_label)

        status_layout.addStretch()

        self.cursor_label = QLabel(status_bar)
        self.cursor_label.setObjectName("cellViewerCursorLabel")
        status_layout.addWidget(self.cursor_label)

        main_layout.addWidget(status_bar)

        # 5. Bottom Actions Footer
        footer_bar = QFrame(self)
        footer_bar.setObjectName("cellViewerFooterBar")
        footer_layout = QHBoxLayout(footer_bar)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(8)

        # Copy button
        self.copy_btn = SecondaryButton("Copy", footer_bar)
        self.copy_btn.setObjectName("cellViewerCopyBtn")
        self.copy_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        self.copy_btn.setToolTip("Copy full text to clipboard (Ctrl+C)")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        footer_layout.addWidget(self.copy_btn)

        # Export button (available in both editable and read-only modes)
        self.export_btn = SecondaryButton("Export...", footer_bar)
        self.export_btn.setObjectName("cellViewerExportBtn")
        self.export_btn.setIcon(qta.icon("fa5s.file-download", color="#475569"))
        self.export_btn.setToolTip("Export to file (Ctrl+E)")
        self.export_btn.clicked.connect(self.export_to_file)
        footer_layout.addWidget(self.export_btn)

        self.copy_feedback_label = QLabel("", footer_bar)
        self.copy_feedback_label.setObjectName("cellViewerCopyFeedbackLabel")
        footer_layout.addWidget(self.copy_feedback_label)

        footer_layout.addStretch()

        if self.is_read_only:
            self.close_btn = PrimaryButton("Close", footer_bar)
            self.close_btn.setObjectName("cellViewerCloseBtn")
            self.close_btn.clicked.connect(self.reject)
            footer_layout.addWidget(self.close_btn)
        else:
            self.cancel_btn = SecondaryButton("Cancel", footer_bar)
            self.cancel_btn.setObjectName("cellViewerCancelBtn")
            self.cancel_btn.clicked.connect(self.reject)
            footer_layout.addWidget(self.cancel_btn)

            self.apply_btn = PrimaryButton("Save", footer_bar)
            self.apply_btn.setObjectName("cellViewerSaveBtn")
            self.apply_btn.setIcon(qta.icon("fa5s.save", color="#FFFFFF"))
            self.apply_btn.setToolTip("Save changes to table cell (Ctrl+Enter, Ctrl+S)")
            self.apply_btn.clicked.connect(self.apply_changes)
            self.save_btn = self.apply_btn  # Alias for Save nomenclature
            footer_layout.addWidget(self.apply_btn)

        main_layout.addWidget(footer_bar)

    def _create_separator(self) -> QFrame:
        sep = QFrame(self)
        sep.setObjectName("cellViewerSeparator")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedWidth(1)
        sep.setFixedHeight(16)
        return sep

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: self.search_toggle_btn.setChecked(True))
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, activated=self.format_content)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_to_file)
        QShortcut(QKeySequence("F3"), self, activated=self.find_next)
        QShortcut(QKeySequence("Shift+F3"), self, activated=self.find_prev)
        if not self.is_read_only:
            QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_changes)
            QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.apply_changes)
            QShortcut(QKeySequence("Ctrl+S"), self, activated=self.apply_changes)

    def eventFilter(self, watched, event) -> bool:
        if (
            hasattr(self, "search_input")
            and watched is self.search_input
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            modifiers = event.modifiers()
            if key == Qt.Key.Key_Down:
                self.find_next()
                return True
            if key == Qt.Key.Key_Up:
                self.find_prev()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    self.find_prev()
                else:
                    self.find_next()
                return True
        return super().eventFilter(watched, event)

    def _load_initial_content(self) -> None:
        self.highlighter.set_mode(self.current_format)
        if self.current_format == self.FORMAT_JSON:
            if hasattr(self, "_parsed_initial_json"):
                try:
                    formatted = json.dumps(self._parsed_initial_json, indent=2, ensure_ascii=False)
                except Exception:
                    formatted = self.original_text
                del self._parsed_initial_json
            else:
                formatted = format_json_string(self.original_text)
            self.editor.setPlainText(formatted if formatted is not None else self.original_text)
        elif self.current_format == self.FORMAT_XML:
            formatted = try_format_xml(self.original_text)
            self.editor.setPlainText(formatted if formatted is not None else self.original_text)
        else:
            self.editor.setPlainText(self.original_text)

        self._baseline_text = self.editor.toPlainText()
        self._update_stats()
        self._update_cursor_info()

    def _on_format_changed(self, format_name: str) -> None:
        self.current_format = format_name
        current_text = self.editor.toPlainText()

        if format_name == self.FORMAT_JSON:
            formatted = format_json_string(current_text)
            if formatted is not None:
                self.editor.setPlainText(formatted)
            self.prettify_btn.setEnabled(True)
            self.minify_btn.setEnabled(True)
        elif format_name == self.FORMAT_XML:
            formatted = try_format_xml(current_text)
            if formatted is not None:
                self.editor.setPlainText(formatted)
            self.prettify_btn.setEnabled(False)
            self.minify_btn.setEnabled(False)
        else:
            self.prettify_btn.setEnabled(False)
            self.minify_btn.setEnabled(False)

        # Update highlighter mode
        self.highlighter.set_mode(format_name)

    def format_content(self) -> None:
        current_text = self.editor.toPlainText()
        formatted = format_json_string(current_text)
        if formatted is not None:
            self.editor.setPlainText(formatted)
            self.format_combo.setCurrentText(self.FORMAT_JSON)
        else:
            xml_formatted = try_format_xml(current_text)
            if xml_formatted is not None:
                self.editor.setPlainText(xml_formatted)
                self.format_combo.setCurrentText(self.FORMAT_XML)
            else:
                QMessageBox.information(
                    self,
                    "Format Content",
                    "The current content could not be parsed as valid JSON or XML.",
                )

    def minify_content(self) -> None:
        current_text = self.editor.toPlainText()
        minified = minify_json_string(current_text)
        if minified is not None:
            self.editor.setPlainText(minified)
        else:
            QMessageBox.information(
                self,
                "Minify JSON",
                "The current content is not valid JSON and cannot be minified.",
            )

    def _toggle_word_wrap(self, checked: bool) -> None:
        if checked:
            self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        else:
            self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def _toggle_search_bar(self, checked: bool) -> None:
        if checked:
            self.search_bar.show()
            self.search_input.setFocus()
            self.search_input.selectAll()
            self._on_search_text_changed()
        else:
            self.search_bar.hide()
            self._clear_search_highlights()
            self.editor.setFocus()

    def _on_text_changed(self) -> None:
        self._update_stats()
        if self.search_bar.isVisible():
            self._on_search_text_changed()

    def _update_stats(self) -> None:
        text = self.editor.toPlainText()
        char_count = len(text)
        line_count = self.editor.blockCount()
        size_bytes = len(text.encode("utf-8"))
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"

        self.stats_label.setText(
            f"Characters: {char_count:,}   |   Lines: {line_count:,}   |   Size: {size_str}"
        )

    def _update_cursor_info(self) -> None:
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.cursor_label.setText(f"Ln {line}, Col {col}")

    def _clear_search_highlights(self) -> None:
        self.editor.setExtraSelections([])
        self.search_matches = []
        self.current_match_idx = -1
        self.search_count_label.setText("0 matches")

    def _on_search_text_changed(self) -> None:
        pattern = self.search_input.text()
        if not pattern:
            self._clear_search_highlights()
            return

        doc = self.editor.document()
        flags = QTextDocument.FindFlag(0)
        if self.case_check.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        cursor = QTextCursor(doc)
        matches: list[QTextCursor] = []
        extra_selections: list[QTextEdit.ExtraSelection] = []

        match_format = QTextCharFormat()
        match_format.setBackground(QColor("#FEF08A"))
        match_format.setForeground(QColor("#0F172A"))

        while True:
            found_cursor = doc.find(pattern, cursor, flags)
            if found_cursor.isNull() or found_cursor.atEnd() and found_cursor.position() == cursor.position():
                break
            matches.append(found_cursor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = found_cursor
            sel.format = match_format
            extra_selections.append(sel)
            cursor = found_cursor

        self.search_matches = matches
        total = len(matches)
        if total > 0:
            self.current_match_idx = 0
            self._highlight_active_match(extra_selections)
            self.search_count_label.setText(f"1 of {total}")
        else:
            self.current_match_idx = -1
            self.editor.setExtraSelections([])
            self.search_count_label.setText("0 matches")

    def _highlight_active_match(self, base_selections: list[QTextEdit.ExtraSelection]) -> None:
        if self.current_match_idx < 0 or self.current_match_idx >= len(self.search_matches):
            self.editor.setExtraSelections(base_selections)
            return

        active_cursor = self.search_matches[self.current_match_idx]
        self.editor.setTextCursor(active_cursor)
        self.editor.centerCursor()
        self.editor.ensureCursorVisible()

        active_format = QTextCharFormat()
        active_format.setBackground(QColor("#F59E0B"))
        active_format.setForeground(QColor("#FFFFFF"))

        all_selections = list(base_selections)
        active_sel = QTextEdit.ExtraSelection()
        active_sel.cursor = active_cursor
        active_sel.format = active_format
        all_selections.append(active_sel)

        self.editor.setExtraSelections(all_selections)
        self.search_count_label.setText(f"{self.current_match_idx + 1} of {len(self.search_matches)}")

    def find_next(self) -> None:
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.search_matches)
        self._highlight_active_match(self._build_base_selections())

    def find_prev(self) -> None:
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.search_matches)
        self._highlight_active_match(self._build_base_selections())

    def _build_base_selections(self) -> list[QTextEdit.ExtraSelection]:
        match_format = QTextCharFormat()
        match_format.setBackground(QColor("#FEF08A"))
        match_format.setForeground(QColor("#0F172A"))
        res = []
        for c in self.search_matches:
            s = QTextEdit.ExtraSelection()
            s.cursor = c
            s.format = match_format
            res.append(s)
        return res

    def copy_to_clipboard(self) -> None:
        text = self.editor.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self.copy_feedback_label.setText("Copied to clipboard!")

            def _clear_feedback() -> None:
                if hasattr(self, "copy_feedback_label") and self.copy_feedback_label.text() == "Copied to clipboard!":
                    self.copy_feedback_label.setText("")

            QTimer.singleShot(2500, _clear_feedback)

    def export_to_file(self) -> None:
        """Export current editor content to an external file using QFileDialog."""
        if self.current_format == self.FORMAT_JSON:
            filter_str = "JSON Files (*.json);;All Files (*)"
            default_ext = ".json"
        elif self.current_format == self.FORMAT_XML:
            filter_str = "XML Files (*.xml);;All Files (*)"
            default_ext = ".xml"
        else:
            filter_str = "Text Files (*.txt);;All Files (*)"
            default_ext = ".txt"

        clean_col = "".join(c for c in str(self.col_name) if c.isalnum() or c in ("_", "-")).strip() or "cell_export"
        default_name = f"{clean_col}{default_ext}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cell Value",
            default_name,
            filter_str,
        )

        if not file_path:
            return

        try:
            target_path = Path(file_path)
            target_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except Exception as err:
            QMessageBox.critical(self, "Export Error", f"Failed to export file:\n{err}")
            return

        filename = target_path.name
        msg = f"Saved to {filename}"
        self.copy_feedback_label.setText(msg)

        def _clear_feedback() -> None:
            if hasattr(self, "copy_feedback_label") and self.copy_feedback_label.text() == msg:
                self.copy_feedback_label.setText("")

        QTimer.singleShot(3000, _clear_feedback)

    def save_changes(self) -> None:
        """Alias for apply_changes to support 'Save' nomenclature."""
        self.apply_changes()

    def apply_changes(self) -> None:
        if self.is_read_only:
            self.reject()
            return

        text = self.editor.toPlainText()
        # If currently configured in JSON mode, validate syntax before applying
        if self.current_format == self.FORMAT_JSON:
            valid, _ = try_parse_json(text)
            if not valid:
                res = QMessageBox.warning(
                    self,
                    "Invalid JSON",
                    "The current content is not valid JSON. Do you want to save it as raw text anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if res != QMessageBox.StandardButton.Yes:
                    return

        self._baseline_text = text
        if hasattr(self, "apply_btn") and self.apply_btn:
            self.apply_btn.setEnabled(False)
            self.apply_btn.setText("Saving...")
            self.apply_btn.setIcon(
                qta.icon(
                    "fa5s.circle-notch",
                    color="#FFFFFF",
                    color_disabled="#FFFFFF",
                    animation=qta.Spin(self.apply_btn, interval=16, step=15),
                )
            )
            QTimer.singleShot(400, self.accept)
        else:
            self.accept()

    def get_value(self) -> str:
        """Returns the edited text value from the viewer."""
        return self.editor.toPlainText()

    def is_modified(self) -> bool:
        """Returns True if the content in the editor differs from baseline content."""
        if self.is_read_only:
            return False
        return self.editor.toPlainText() != getattr(self, "_baseline_text", self.original_text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.is_modified():
            super().reject()
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes in this cell.\n\nDo you want to save your changes before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if reply == QMessageBox.StandardButton.Save:
            self.save_changes()
            if self.result() == QDialog.DialogCode.Accepted:
                event.accept()
            else:
                event.ignore()
        elif reply == QMessageBox.StandardButton.Discard:
            super().reject()
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        self.close()
