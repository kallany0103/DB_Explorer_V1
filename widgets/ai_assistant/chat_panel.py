# widgets/ai_assistant/chat_panel.py
"""
Toad-style AI Chat Panel for DB Explorer.
Displays:
- Top Toolbar: New Chat (+), History icon, Disclaimer, and Close (x)
- Active Document / Target SQL indicator chip
- Rich Markdown / HTML view of AI Explanations and conversations
- Interactive follow-up input box with Send button (↑)
"""

import html
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPlainTextEdit, QLabel, QFrame, QApplication, QSplitter
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QEvent
from PySide6.QtGui import QFont, QColor, QTextCursor, QIcon, QKeySequence
import qtawesome as qta

from ui.components import SecondaryButton, PrimaryButton
from widgets.ai_assistant.ai_service import explain_query_ai


def markdown_to_html(md_text: str) -> str:
    """Converts a subset of markdown to styled HTML suitable for QTextBrowser."""
    escaped = html.escape(md_text)

    # Code blocks ```sql ... ```
    def replace_code_block(match):
        code = match.group(1).strip()
        return f'<div style="background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 8px; margin: 8px 0; font-family: Consolas, monospace; font-size: 9pt; color: #0f172a; white-space: pre-wrap;">{code}</div>'

    escaped = re.sub(r'```(?:sql|SQL)?(.*?)```', replace_code_block, escaped, flags=re.DOTALL)

    # Inline code `code`
    escaped = re.sub(r'`([^`]+)`', r'<code style="background-color: #f1f5f9; color: #0969da; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace; font-size: 9pt;">\1</code>', escaped)

    # Headers (Toad style: simple bold section titles)
    escaped = re.sub(r'^###\s*(.*?)$', r'<p style="margin: 10px 0 3px 0; color: #111827; font-weight: bold; font-size: 9.5pt;">\1</p>', escaped, flags=re.MULTILINE)
    escaped = re.sub(r'^##\s*(.*?)$', r'<p style="margin: 12px 0 4px 0; color: #111827; font-weight: bold; font-size: 10.5pt;">\1</p>', escaped, flags=re.MULTILINE)

    # Bold & Italic
    escaped = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped)
    escaped = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped)

    # Lists
    lines = escaped.split("\n")
    formatted_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            if not in_list:
                formatted_lines.append('<ul style="margin: 4px 0; padding-left: 20px;">')
                in_list = True
            content = stripped[2:]
            formatted_lines.append(f'<li style="margin-bottom: 4px; color: #334155;">{content}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if stripped:
                formatted_lines.append(f'<p style="margin: 4px 0; line-height: 1.45; color: #1e293b;">{line}</p>')
            else:
                formatted_lines.append('<div style="height: 4px;"></div>')

    if in_list:
        formatted_lines.append('</ul>')

    return "".join(formatted_lines)


class AIWorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)


class AIWorkerThread(QThread):
    def __init__(self, sql, ai_settings, chat_history, user_prompt, db_type):
        super().__init__()
        self.sql = sql
        self.ai_settings = ai_settings
        self.chat_history = chat_history
        self.user_prompt = user_prompt
        self.db_type = db_type
        self.signals = AIWorkerSignals()

    def run(self):
        try:
            result = explain_query_ai(
                sql=self.sql,
                ai_settings=self.ai_settings,
                chat_history=self.chat_history,
                user_prompt=self.user_prompt,
                db_type=self.db_type
            )
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


class ChatInputField(QPlainTextEdit):
    """Text edit that submits on Enter, and inserts a newline on Shift+Enter."""
    submit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Press Enter to send, or Shift+Enter to insert a new line.")
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background-color: transparent;
                font-size: 9.5pt;
                color: #1f2937;
                padding: 4px;
            }
        """)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.submit_requested.emit()
        else:
            super().keyPressEvent(event)


class AIChatPanel(QWidget):
    """Toad-style side panel for AI explanations and conversations."""
    close_requested = Signal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.current_sql = ""
        self.db_type = "GENERIC"
        self.chat_history = []
        self._worker_thread = None

        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("aiChatPanel")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Header Toolbar ──────────────────────────────────────────
        header = QWidget()
        header.setObjectName("aiChatHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 2, 8, 2)
        header_layout.setSpacing(4)

        title_label = QLabel("Toad Chat")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1f2937; border: none; background: transparent;")
        header_layout.addWidget(title_label)

        self.btn_new_chat = SecondaryButton(qta.icon("fa5s.plus", color="#555555"))
        self.btn_new_chat.setToolTip("New Chat")
        self.btn_new_chat.setFixedSize(24, 24)
        self.btn_new_chat.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.btn_new_chat)

        self.btn_history = SecondaryButton(qta.icon("fa5s.history", color="#555555"))
        self.btn_history.setToolTip("Clear & Reset History")
        self.btn_history.setFixedSize(24, 24)
        self.btn_history.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.btn_history)

        header_layout.addStretch()

        disclaimer = QLabel("AI generated. Check for accuracy. <a href='#' style='color: #0066CC; text-decoration: none;'>Terms of use.</a>")
        disclaimer.setStyleSheet("color: #6b7280; font-size: 8pt; border: none; background: transparent;")
        header_layout.addWidget(disclaimer)

        self.btn_close = SecondaryButton("✕")
        self.btn_close.setToolTip("Close Chat")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.btn_close)

        layout.addWidget(header)

        # ── 2. Active Document / SQL Context Chip ───────────────────────
        self.chip_frame = QFrame()
        self.chip_frame.setObjectName("aiChatChipFrame")
        self.chip_frame.setFixedHeight(28)
        chip_layout = QHBoxLayout(self.chip_frame)
        chip_layout.setContentsMargins(10, 2, 8, 2)
        chip_layout.setSpacing(6)

        doc_icon = QLabel()
        doc_icon.setPixmap(qta.icon("fa5s.times", color="#718096").pixmap(11, 11))
        chip_layout.addWidget(doc_icon)

        self.chip_label = QLabel("Active document")
        self.chip_label.setStyleSheet("color: #4A5568; font-weight: 600; font-size: 8.5pt; border: none; background: transparent;")
        chip_layout.addWidget(self.chip_label)
        chip_layout.addStretch()

        layout.addWidget(self.chip_frame)

        # ── 3. Messages View ────────────────────────────────────────────
        self.chat_view = QTextBrowser()
        self.chat_view.setObjectName("aiChatBrowser")
        self.chat_view.setOpenExternalLinks(True)
        self.chat_view.setStyleSheet("""
            QTextBrowser {
                border: none;
                background-color: #ffffff;
                padding: 14px;
                color: #1f2937;
                font-size: 9.5pt;
            }
        """)
        layout.addWidget(self.chat_view, stretch=1)

        # Initial Welcome
        self._append_system_message(
            "Click **Explain code using AI** in the worksheet toolbar or select query text to get an instant breakdown of query components, relationships, and performance considerations."
        )

        # ── 4. Bottom Input Box ─────────────────────────────────────────
        bottom_container = QWidget()
        bottom_container.setObjectName("aiChatBottomContainer")
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(10, 8, 10, 10)
        bottom_layout.setSpacing(6)

        # Input Frame
        input_border_frame = QFrame()
        input_border_frame.setObjectName("aiChatInputBorder")
        input_frame_layout = QHBoxLayout(input_border_frame)
        input_frame_layout.setContentsMargins(6, 4, 6, 4)
        input_frame_layout.setSpacing(6)

        self.input_edit = ChatInputField()
        self.input_edit.submit_requested.connect(self.handle_send_message)
        input_frame_layout.addWidget(self.input_edit, stretch=1)

        self.btn_send = PrimaryButton(qta.icon("fa5s.arrow-up", color="#ffffff"))
        self.btn_send.setFixedSize(28, 28)
        self.btn_send.setToolTip("Send (Enter)")
        self.btn_send.clicked.connect(self.handle_send_message)
        input_frame_layout.addWidget(self.btn_send, alignment=Qt.AlignmentFlag.AlignBottom)

        bottom_layout.addWidget(input_border_frame)
        layout.addWidget(bottom_container)

    def _append_system_message(self, md_text: str):
        html_content = markdown_to_html(md_text)
        self.chat_view.append(f"<div style='margin-bottom: 12px;'>{html_content}</div>")
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _append_user_message(self, text: str):
        escaped = html.escape(text).replace("\n", "<br>")
        user_html = (
            f"<div style='margin: 10px 0; text-align: right;'>"
            f"<span style='background-color: #e0f2fe; color: #0369a1; padding: 6px 12px; border-radius: 12px; font-weight: 500; display: inline-block; font-size: 9pt;'>"
            f"{escaped}"
            f"</span></div>"
        )
        self.chat_view.append(user_html)
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def explain_sql(self, sql: str, db_type: str = "GENERIC"):
        """Triggers explanation for the given SQL query."""
        self.current_sql = sql.strip()
        self.db_type = db_type
        
        preview = self.current_sql.splitlines()[0] if self.current_sql else ""
        if len(preview) > 40:
            preview = preview[:37] + "..."
        self.chip_label.setText(f"Active Query: {preview or 'Empty'}")

        self.clear_chat()
        self._append_user_message("Explain this code using AI")
        self._trigger_ai_query(user_prompt=None)

    def handle_send_message(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.input_edit.clear()
        self._append_user_message(text)
        self._trigger_ai_query(user_prompt=text)

    def _trigger_ai_query(self, user_prompt=None):
        ai_settings = {
            "ai_provider": getattr(self.main_window, "ai_provider", "OpenAI"),
            "ai_api_key": getattr(self.main_window, "ai_api_key", ""),
            "ai_base_url": getattr(self.main_window, "ai_base_url", ""),
            "ai_model": getattr(self.main_window, "ai_model", ""),
        }

        self.btn_send.setEnabled(False)
        self.input_edit.setEnabled(False)

        # Show typing indicator
        self.chat_view.append("<p id='typing' style='color: #64748b; font-style: italic;'>Analyzing code with AI...</p>")
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

        self._worker_thread = AIWorkerThread(
            sql=self.current_sql,
            ai_settings=ai_settings,
            chat_history=list(self.chat_history),
            user_prompt=user_prompt,
            db_type=self.db_type
        )
        self._worker_thread.signals.finished.connect(self._on_ai_finished)
        self._worker_thread.signals.error.connect(self._on_ai_error)
        self._worker_thread.start()

    def _on_ai_finished(self, response_text: str):
        self._remove_typing_indicator()
        self.btn_send.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.input_edit.setFocus()

        # Save to chat history
        self.chat_history.append({"role": "assistant", "content": response_text})

        # Render HTML
        html_resp = markdown_to_html(response_text)
        self.chat_view.append(f"<div style='margin-bottom: 14px;'>{html_resp}</div>")
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _on_ai_error(self, error_msg: str):
        self._remove_typing_indicator()
        self.btn_send.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.chat_view.append(
            f"<div style='color: #dc2626; background-color: #fef2f2; border: 1px solid #fecaca; padding: 8px; border-radius: 4px; margin: 8px 0;'>"
            f"<b>Error:</b> {html.escape(error_msg)}</div>"
        )
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _remove_typing_indicator(self):
        doc = self.chat_view.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Re-fetch without typing if needed or simple clear of last block
        # In QTextBrowser, appending replacement is simplest:
        html_all = self.chat_view.toHtml()
        cleaned_html = html_all.replace("<p id=\"typing\" style=\"color: #64748b; font-style: italic;\">Analyzing code with AI...</p>", "")
        self.chat_view.setHtml(cleaned_html)
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def clear_chat(self):
        self.chat_history.clear()
        self.chat_view.clear()
