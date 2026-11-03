"""widgets/results_view/messages.py

Modern card-based Messages panel for query status, results output,
compiler warnings, and error messages with individual copy actions.
"""

from __future__ import annotations

import datetime
import html
import re
from typing import Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from ui.menu_style import apply_menu_style
from ui.messages_style import (
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUCCESS,
    COLOR_TIMESTAMP,
    COPY_BUTTON_STYLE,
    MESSAGES_SCROLL_STYLE,
    TEXT_COLOR_DEFAULT,
    TEXT_COLOR_ERROR,
    TEXT_COLOR_SUCCESS,
)


class MessageCard(QWidget):
    """An individual message card displaying output/error with copy action and timestamp."""

    def __init__(
        self,
        msg_type: str = "success",
        title: str = "Success",
        text: str = "",
        is_html: bool = False,
        timestamp: str | None = None,
        on_anchor_clicked: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.msg_type = msg_type
        self.title = title
        self.text = text
        self.is_html = is_html
        self.on_anchor_clicked = on_anchor_clicked

        if not timestamp:
            now = datetime.datetime.now()
            self.timestamp = now.strftime("%I:%M:%S %p").lstrip("0")
        else:
            self.timestamp = timestamp

        # Determine theme colors based on message type
        if self.msg_type == "success":
            self.accent_color = QColor(COLOR_SUCCESS)
            self.title_color = COLOR_SUCCESS
            self.text_color = TEXT_COLOR_SUCCESS
        elif self.msg_type == "error":
            self.accent_color = QColor(COLOR_ERROR)
            self.title_color = COLOR_ERROR
            self.text_color = TEXT_COLOR_ERROR
        else:
            self.accent_color = QColor(COLOR_INFO)
            self.title_color = COLOR_INFO
            self.text_color = TEXT_COLOR_DEFAULT

        self._setup_ui()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _setup_ui(self) -> None:
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(26, 6, 16, 8)
        card_layout.setSpacing(4)

        # Header row: Title on left, Stretch, Copy button, Timestamp
        header_widget = QWidget()
        header_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel(self.title)
        title_font = QFont("Segoe UI", 10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(
            f"color: {self.title_color}; background: transparent; border: none;"
        )
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.copy_btn = QToolButton()
        self.copy_btn.setIcon(qta.icon("fa5.copy", color=COLOR_TIMESTAMP))
        self.copy_btn.setIconSize(QSize(13, 13))
        self.copy_btn.setStyleSheet(COPY_BUTTON_STYLE)
        self.copy_btn.setToolTip("Copy message")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        header_layout.addWidget(self.copy_btn)

        ts_label = QLabel(self.timestamp)
        ts_label.setFont(QFont("Segoe UI", 8))
        ts_label.setStyleSheet(
            f"color: {COLOR_TIMESTAMP}; background: transparent; border: none;"
        )
        header_layout.addWidget(ts_label)

        card_layout.addWidget(header_widget)

        # Body message
        if self.is_html:
            browser = QTextBrowser()
            browser.setReadOnly(True)
            browser.setOpenExternalLinks(False)
            browser.setOpenLinks(False)
            browser.setFrameShape(QTextBrowser.Shape.NoFrame)
            browser.setStyleSheet("background: transparent; border: none; padding: 0px;")
            browser.document().setDocumentMargin(0)
            browser.setHtml(self.text)
            if self.on_anchor_clicked:
                browser.anchorClicked.connect(self.on_anchor_clicked)
            card_layout.addWidget(browser)
        else:
            body_label = QLabel(self.text)
            body_label.setFont(QFont("Segoe UI", 9))
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            body_label.setStyleSheet(
                f"color: {self.text_color}; background: transparent; border: none; padding: 0px;"
            )
            card_layout.addWidget(body_label)

    def copy_to_clipboard(self) -> None:
        """Copies this message's text to the clipboard with visual confirmation."""
        if self.is_html:
            clean_text = re.sub(r"<[^>]+>", " ", self.text)
            clean_text = html.unescape(clean_text).strip()
            QGuiApplication.clipboard().setText(clean_text)
        else:
            QGuiApplication.clipboard().setText(self.text)

        self.copy_btn.setIcon(qta.icon("fa5s.check", color="#10b981"))
        self.copy_btn.setToolTip("Copied!")
        QTimer.singleShot(1500, self._reset_copy_icon)

    def _reset_copy_icon(self) -> None:
        self.copy_btn.setIcon(qta.icon("fa5.copy", color=COLOR_TIMESTAMP))
        self.copy_btn.setToolTip("Copy message")

    def paintEvent(self, event) -> None:
        """Paints the antialiased curved accent bracket on the left side."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.accent_color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        x = 13
        y = 6
        h = max(10, self.height() - 12)
        r = 6
        path = QPainterPath()
        path.moveTo(x + r, y)
        path.quadTo(x, y, x, y + r)
        path.lineTo(x, y + h - r)
        path.quadTo(x, y + h, x + r, y + h)
        painter.drawPath(path)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        apply_menu_style(menu)
        copy_action = QAction("Copy Message", menu)
        copy_action.triggered.connect(self.copy_to_clipboard)
        menu.addAction(copy_action)

        parent_view = self.parentWidget()
        while parent_view and not isinstance(parent_view, MessageView):
            parent_view = parent_view.parentWidget()

        if parent_view:
            copy_all_action = QAction("Copy All", menu)
            copy_all_action.triggered.connect(
                lambda: QGuiApplication.clipboard().setText(parent_view.toPlainText())
            )
            clear_action = QAction("Clear", menu)
            clear_action.triggered.connect(parent_view.clear)
            menu.addAction(copy_all_action)
            menu.addAction(clear_action)

        menu.exec(event.globalPos())


def parse_message_payload(raw_text: str) -> tuple[str, str, str, str | None]:
    """Inspects raw text to determine message type, title, cleaned text, and timestamp."""
    text = raw_text.strip()
    extracted_ts = None

    # Check for [YYYY-MM-DD HH:MM:SS] or [HH:MM:SS] prefix
    m_ts = re.match(r"^\[(\d{4}-\d{2}-\d{2} )?(\d{1,2}:\d{2}:\d{2})\]\s*", text)
    if m_ts:
        time_part = m_ts.group(2)
        try:
            dt = datetime.datetime.strptime(time_part, "%H:%M:%S")
            extracted_ts = dt.strftime("%I:%M:%S %p").lstrip("0")
        except Exception:
            extracted_ts = time_part
        text = text[m_ts.end():].strip()

    # Check if starts with ERROR:\n\n or Error:
    if re.match(r"^ERROR:\s*", text, re.IGNORECASE):
        text = re.sub(r"^ERROR:\s*", "", text, flags=re.IGNORECASE).strip()
        return ("error", "Error", text, extracted_ts)

    lower = text.lower()
    if any(k in lower for k in ("error", "exception", "ora-", "failed")):
        return ("error", "Error", text, extracted_ts)

    if "notice:" in lower or "warning:" in lower:
        return ("info", "Notice", text, extracted_ts)

    if any(
        k in lower
        for k in (
            "query executed successfully",
            "query returned",
            "rows returned",
            "rows affected",
            "completed successfully",
            "table created",
            "droped",
            "created",
            "updated",
            "inserted",
            "deleted",
            "truncated",
            "explain analyze",
        )
    ):
        return ("success", "Success", text, extracted_ts)

    return ("info", "Info", text, extracted_ts)


class MessageView(QTextEdit):
    """
    Subclasses QTextEdit for seamless drop-in compatibility across the app
    while rendering messages as individual copyable cards inside a QScrollArea.
    """

    MAX_CARDS = 200

    def __init__(self, parent: QWidget | None = None, tab_content: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("message_view")
        self.setReadOnly(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tab_content = tab_content
        self._cards: list[MessageCard] = []

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setStyleSheet(MESSAGES_SCROLL_STYLE)

        self.cards_container = QWidget()
        self.cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cards_container.setStyleSheet("background-color: #ffffff;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(10, 10, 10, 10)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        self.scroll_area.raise_()

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.scroll_area.setGeometry(self.rect())
        self.scroll_area.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.scroll_area.setGeometry(self.rect())
        self.scroll_area.raise_()

    def verticalScrollBar(self):
        return self.scroll_area.verticalScrollBar()

    def clear(self) -> None:
        """Clears all message cards."""
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        super().clear()

    def toPlainText(self) -> str:
        """Returns the concatenated plain text of all messages."""
        return "\n\n".join(card.text for card in self._cards)

    def append_card(self, card: MessageCard) -> None:
        """Inserts a MessageCard at the top so the latest message is always displayed first."""
        self.cards_layout.insertWidget(0, card)
        self._cards.insert(0, card)

        if len(self._cards) > self.MAX_CARDS:
            oldest = self._cards.pop()
            self.cards_layout.removeWidget(oldest)
            oldest.deleteLater()

        QTimer.singleShot(10, self.scroll_to_top)

    def scroll_to_top(self) -> None:
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.minimum())

    def scroll_to_bottom(self) -> None:
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def add_message(
        self,
        msg_type: str = "success",
        title: str = "Success",
        text: str = "",
        is_html: bool = False,
        timestamp: str | None = None,
    ) -> None:
        """Adds a message card to the view."""
        card = MessageCard(
            msg_type=msg_type,
            title=title,
            text=text,
            is_html=is_html,
            timestamp=timestamp,
            on_anchor_clicked=self._on_anchor_clicked,
            parent=self.cards_container,
        )
        self.append_card(card)

    def setPlainText(self, text: str) -> None:
        """Compatibility method: parses plain text and adds as message card."""
        if not text or not str(text).strip():
            return
        msg_type, title, clean_text, ts = parse_message_payload(str(text))
        self.add_message(msg_type=msg_type, title=title, text=clean_text, is_html=False, timestamp=ts)
        super().setPlainText(self.toPlainText())

    def append(self, text: str) -> None:
        """Compatibility method: appends a message card."""
        self.setPlainText(text)

    def setText(self, text: str) -> None:
        """Compatibility method: appends a message card."""
        self.setPlainText(text)

    def setHtml(self, html_text: str) -> None:
        """Compatibility method: renders HTML (e.g. Oracle compiler errors) as an Error card."""
        if not html_text or not str(html_text).strip():
            return
        self.add_message(
            msg_type="error",
            title="Oracle Compilation Errors",
            text=str(html_text),
            is_html=True,
        )

    def _on_anchor_clicked(self, url) -> None:
        """Handles compiler error anchor jumps (jump:line:col) to worksheet editor."""
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("jump:"):
            parts = url_str.split(":")
            if len(parts) >= 3:
                try:
                    line_no = int(parts[1])
                    col_no = int(parts[2])
                    from widgets.worksheet.utils import get_query_editor

                    editor = get_query_editor(self.tab_content)
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

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        apply_menu_style(menu)
        copy_all_action = QAction("Copy All", menu)
        copy_all_action.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(self.toPlainText())
        )
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(self.clear)
        menu.addAction(copy_all_action)
        menu.addAction(clear_action)
        menu.exec(self.mapToGlobal(pos))


def create_message_view(manager, tab_content) -> QWidget:
    """Builds and returns the container housing the MessageView widget."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    message_view = MessageView(parent=container, tab_content=tab_content)
    layout.addWidget(message_view)
    return container
