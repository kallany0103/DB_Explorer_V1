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
import uuid
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPlainTextEdit, QLabel, QFrame, QApplication, QSplitter,
    QToolButton, QMenu
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QEvent, QSize
from PySide6.QtGui import QFont, QColor, QTextCursor, QIcon, QKeySequence, QAction
import qtawesome as qta

from ui.components import SecondaryButton, PrimaryButton
from widgets.ai_assistant.ai_service import explain_query_ai
from ui.menu_style import apply_menu_style


def markdown_to_html(md_text: str) -> str:
    """Converts a subset of markdown to styled HTML suitable for QTextBrowser."""
    escaped = html.escape(md_text)

    # Code blocks ```sql ... ```
    def replace_code_block(match):
        code = match.group(1).strip()
        return (
            f'<div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; '
            f'border-radius: 5px; padding: 8px 10px; margin: 8px 0; font-family: Consolas, monospace; '
            f'font-size: 9pt; color: #0F172A; white-space: pre-wrap; line-height: 1.4;">{code}</div>'
        )

    escaped = re.sub(r'```(?:sql|SQL)?(.*?)```', replace_code_block, escaped, flags=re.DOTALL)

    # Inline code `code`
    escaped = re.sub(
        r'`([^`]+)`',
        r'<code style="background-color: #F1F5F9; color: #0284C7; padding: 2px 5px; border-radius: 4px; font-family: Consolas, monospace; font-size: 8.5pt;">\1</code>',
        escaped
    )

    # Section Headers (Clean, Toad-style bold labels)
    escaped = re.sub(
        r'^###\s*(.*?)$',
        r'<p style="margin: 12px 0 4px 0; color: #1E293B; font-weight: 700; font-size: 9.5pt; letter-spacing: -0.2px;">\1</p>',
        escaped,
        flags=re.MULTILINE
    )
    escaped = re.sub(
        r'^##\s*(.*?)$',
        r'<p style="margin: 14px 0 6px 0; color: #0F172A; font-weight: 700; font-size: 10.5pt;">\1</p>',
        escaped,
        flags=re.MULTILINE
    )

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
                formatted_lines.append('<ul style="margin: 4px 0 8px 0; padding-left: 18px;">')
                in_list = True
            content = stripped[2:]
            formatted_lines.append(f'<li style="margin-bottom: 5px; color: #334155; line-height: 1.45;">{content}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if stripped:
                formatted_lines.append(f'<p style="margin: 4px 0; line-height: 1.5; color: #334155;">{line}</p>')
            else:
                formatted_lines.append('<div style="height: 3px;"></div>')

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
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background-color: transparent;
                font-size: 9pt;
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
    """Refined Toad-style side panel for AI explanations and conversations."""
    close_requested = Signal()

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.current_sql = ""
        self.db_type = "GENERIC"
        self.chat_history = []
        self._last_raw_response = ""
        self._worker_thread = None
        self.past_conversations = []  # List of saved conversation dicts
        self.active_conversation_id = None  # Tracks which conversation is currently open

        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("aiChatPanel")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 1. Top Header Bar ──────────────────────────────────────────
        header = QWidget()
        header.setObjectName("aiChatHeader")
        header.setFixedHeight(34)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 2, 6, 2)
        header_layout.setSpacing(4)

        # Sparkles/AI icon + Title
        ai_icon = QLabel()
        ai_icon.setPixmap(qta.icon("fa5s.magic", color="#2563EB").pixmap(13, 13))
        ai_icon.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(ai_icon)

        title_label = QLabel("USQL Chat")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #1F2937; border: none; background: transparent;")
        header_layout.addWidget(title_label)

        # Action: New Chat (+)
        self.btn_new_chat = QToolButton()
        self.btn_new_chat.setIcon(qta.icon("fa5s.plus", color="#4B5563"))
        self.btn_new_chat.setIconSize(QSize(12, 12))
        self.btn_new_chat.setFixedSize(22, 22)
        self.btn_new_chat.setToolTip("New Chat")
        self.btn_new_chat.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                background: transparent;
            }
            QToolButton:hover {
                background: #E5E7EB;
                border: 1px solid #D1D5DB;
            }
            QToolButton:pressed {
                background: #D1D5DB;
            }
        """)
        self.btn_new_chat.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.btn_new_chat)

        # Action: Past Conversation
        self.btn_history = QToolButton()
        self.btn_history.setIcon(qta.icon("fa5s.history", color="#4B5563"))
        self.btn_history.setIconSize(QSize(12, 12))
        self.btn_history.setFixedSize(22, 22)
        self.btn_history.setToolTip("Past Conversation")
        self.btn_history.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                background: transparent;
            }
            QToolButton:hover {
                background: #E5E7EB;
                border: 1px solid #D1D5DB;
            }
            QToolButton:pressed {
                background: #D1D5DB;
            }
        """)
        self.btn_history.clicked.connect(self.show_past_conversations)
        header_layout.addWidget(self.btn_history)

        # Action: Copy last explanation to clipboard
        self.btn_copy = QToolButton()
        self.btn_copy.setIcon(qta.icon("fa5s.copy", color="#4B5563"))
        self.btn_copy.setIconSize(QSize(12, 12))
        self.btn_copy.setFixedSize(22, 22)
        self.btn_copy.setToolTip("Copy Explanation")
        self.btn_copy.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                background: transparent;
            }
            QToolButton:hover {
                background: #E5E7EB;
                border: 1px solid #D1D5DB;
            }
            QToolButton:pressed {
                background: #D1D5DB;
            }
        """)
        self.btn_copy.clicked.connect(self._copy_explanation)
        header_layout.addWidget(self.btn_copy)

        header_layout.addStretch()

        disclaimer = QLabel("AI generated. Check for accuracy. <a href='#' style='color: #2563EB; text-decoration: none;'>Terms of use.</a>")
        disclaimer.setStyleSheet("color: #6B7280; font-size: 8pt; border: none; background: transparent;")
        header_layout.addWidget(disclaimer)

        # Action: Close (✕)
        self.btn_close = QToolButton()
        self.btn_close.setIcon(qta.icon("fa5s.times", color="#4B5563"))
        self.btn_close.setIconSize(QSize(11, 11))
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setToolTip("Close Panel")
        self.btn_close.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                background: transparent;
            }
            QToolButton:hover {
                background: #FEE2E2;
                border: 1px solid #FCA5A5;
            }
        """)
        self.btn_close.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.btn_close)

        layout.addWidget(header)

        # ── 2. Active Document Context Chip ─────────────────────────────
        self.chip_frame = QFrame()
        self.chip_frame.setObjectName("aiChatChipFrame")
        self.chip_frame.setFixedHeight(28)
        chip_layout = QHBoxLayout(self.chip_frame)
        chip_layout.setContentsMargins(10, 2, 8, 2)
        chip_layout.setSpacing(6)

        doc_icon = QLabel()
        doc_icon.setPixmap(qta.icon("fa5s.file-code", color="#0284C7").pixmap(12, 12))
        doc_icon.setStyleSheet("background: transparent; border: none;")
        chip_layout.addWidget(doc_icon)

        self.chip_label = QLabel("Active document")
        self.chip_label.setStyleSheet("color: #334155; font-weight: 600; font-size: 8.5pt; border: none; background: transparent;")
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
                background-color: #FFFFFF;
                padding: 14px 16px;
                color: #1F2937;
                font-size: 9pt;
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

        # Input Frame with modern border & focus state
        input_border_frame = QFrame()
        input_border_frame.setObjectName("aiChatInputBorder")
        input_frame_layout = QHBoxLayout(input_border_frame)
        input_frame_layout.setContentsMargins(6, 4, 6, 4)
        input_frame_layout.setSpacing(6)

        self.input_edit = ChatInputField()
        self.input_edit.submit_requested.connect(self.handle_send_message)
        input_frame_layout.addWidget(self.input_edit, stretch=1)

        # Send Button with clean arrow-up
        self.btn_send = PrimaryButton(qta.icon("fa5s.arrow-up", color="#FFFFFF"))
        self.btn_send.setIconSize(QSize(13, 13))
        self.btn_send.setFixedSize(28, 28)
        self.btn_send.setToolTip("Send (Enter)")
        self.btn_send.clicked.connect(self.handle_send_message)
        input_frame_layout.addWidget(self.btn_send, alignment=Qt.AlignmentFlag.AlignBottom)

        bottom_layout.addWidget(input_border_frame)
        layout.addWidget(bottom_container)

    def _copy_explanation(self):
        if self._last_raw_response:
            QApplication.clipboard().setText(self._last_raw_response)
        else:
            QApplication.clipboard().setText(self.chat_view.toPlainText())

    def _append_system_message(self, md_text: str):
        html_content = markdown_to_html(md_text)
        self.chat_view.append(f"<div style='margin-bottom: 12px;'>{html_content}</div>")
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _append_user_message(self, text: str):
        escaped = html.escape(text).replace("\n", "<br>")
        user_html = (
            f"<div style='margin: 8px 0; text-align: right;'>"
            f"<span style='background-color: #EFF6FF; border: 1px solid #BFDBFE; color: #1E40AF; "
            f"padding: 5px 12px; border-radius: 12px; font-weight: 500; display: inline-block; font-size: 8.5pt;'>"
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
        if len(preview) > 36:
            preview = preview[:33] + "..."
        self.chip_label.setText(f"Active document: {preview or 'Empty'}")

        self.clear_chat(show_greeting=False)
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
        self.chat_view.append("<p id='typing' style='color: #64748B; font-style: italic; font-size: 8.5pt;'>Analyzing code with AI...</p>")
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

        self._last_raw_response = response_text
        self.chat_history.append({"role": "assistant", "content": response_text})

        # Render HTML
        html_resp = markdown_to_html(response_text)
        self.chat_view.append(f"<div style='margin-bottom: 14px;'>{html_resp}</div>")
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

        # Automatically update/save this session in past conversations
        self._archive_current_conversation()

    def _on_ai_error(self, error_msg: str):
        self._remove_typing_indicator()
        self.btn_send.setEnabled(True)
        self.input_edit.setEnabled(True)
        self.chat_view.append(
            f"<div style='color: #DC2626; background-color: #FEF2F2; border: 1px solid #FECACA; padding: 8px 10px; border-radius: 4px; margin: 8px 0; font-size: 8.5pt;'>"
            f"<b>Error:</b> {html.escape(error_msg)}</div>"
        )
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _remove_typing_indicator(self):
        doc = self.chat_view.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        html_all = self.chat_view.toHtml()
        cleaned_html = html_all.replace("<p id=\"typing\" style=\"color: #64748B; font-style: italic; font-size: 8.5pt;\">Analyzing code with AI...</p>", "")
        self.chat_view.setHtml(cleaned_html)
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _archive_current_conversation(self):
        """Saves or updates the current conversation in past_conversations without creating duplicates."""
        if not self.chat_history:
            return

        preview = ""
        # Look for the target SQL or first real question for the title
        if self.current_sql:
            preview = self.current_sql.splitlines()[0].strip()
        if not preview:
            for msg in self.chat_history:
                if msg.get("role") == "user" and msg.get("content") != "Explain this code using AI":
                    preview = msg.get("content", "").strip()
                    break
        if not preview:
            preview = "SQL Explanation"
        if len(preview) > 35:
            preview = preview[:32] + "..."

        # If this is already an active tracked conversation in past_conversations, update it
        if self.active_conversation_id:
            for conv in self.past_conversations:
                if conv.get("id") == self.active_conversation_id:
                    conv["title"] = preview
                    conv["messages"] = list(self.chat_history)
                    conv["sql"] = self.current_sql
                    conv["db_type"] = self.db_type
                    conv["html"] = self.chat_view.toHtml()
                    conv["last_raw_response"] = self._last_raw_response
                    return

        # Otherwise create a new entry
        conv_id = str(uuid.uuid4())
        self.active_conversation_id = conv_id
        session_entry = {
            "id": conv_id,
            "title": preview,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "messages": list(self.chat_history),
            "sql": self.current_sql,
            "db_type": self.db_type,
            "html": self.chat_view.toHtml(),
            "last_raw_response": self._last_raw_response
        }
        self.past_conversations.insert(0, session_entry)
        if len(self.past_conversations) > 20:
            self.past_conversations.pop()

    def show_past_conversations(self):
        """Displays a menu of past conversations to view or switch back to."""
        menu = QMenu(self)
        apply_menu_style(menu)

        if not self.past_conversations:
            empty_action = menu.addAction("No past conversations yet")
            empty_action.setEnabled(False)
        else:
            for idx, conv in enumerate(self.past_conversations):
                title = conv.get("title", f"Chat #{idx + 1}")
                time_str = conv.get("timestamp", "")
                is_current = (conv.get("id") == self.active_conversation_id)
                prefix = "✓ " if is_current else ""
                label = f"{prefix}[{time_str}] {title}" if time_str else f"{prefix}{title}"
                action = menu.addAction(qta.icon("fa5s.comment-dots", color="#2563EB" if is_current else "#6B7280"), label)
                action.triggered.connect(lambda checked=False, c=conv: self._restore_conversation(c))

            menu.addSeparator()
            clear_all_action = menu.addAction(qta.icon("fa5s.trash-alt", color="#EF4444"), "Clear All History")
            clear_all_action.triggered.connect(self._clear_past_conversations)

        # Show menu aligned under btn_history
        menu.exec(self.btn_history.mapToGlobal(self.btn_history.rect().bottomLeft()))

    def _restore_conversation(self, conv: dict):
        """Restores a past conversation without creating duplicate history."""
        # If user clicks the currently active conversation, no action needed
        if conv.get("id") and conv.get("id") == self.active_conversation_id:
            return

        # Save any in-progress changes to the currently open chat before switching
        if self.chat_history:
            self._archive_current_conversation()

        self.active_conversation_id = conv.get("id")
        self.chat_history = list(conv.get("messages", []))
        self.current_sql = conv.get("sql", "")
        self.db_type = conv.get("db_type", "GENERIC")
        self._last_raw_response = conv.get("last_raw_response", "")

        preview = self.current_sql.splitlines()[0] if self.current_sql else ""
        if len(preview) > 36:
            preview = preview[:33] + "..."
        self.chip_label.setText(f"Active document: {preview or 'Empty'}")

        if conv.get("html"):
            self.chat_view.setHtml(conv.get("html"))
            self.chat_view.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self.chat_view.clear()
            for msg in self.chat_history:
                if msg.get("role") == "user":
                    self._append_user_message(msg.get("content", ""))
                else:
                    html_content = markdown_to_html(msg.get("content", ""))
                    self.chat_view.append(f"<div style='margin-bottom: 14px;'>{html_content}</div>")

    def _clear_past_conversations(self):
        """Clears stored past conversations."""
        self.past_conversations.clear()
        self.active_conversation_id = None

    def clear_chat(self, show_greeting: bool = True):
        """Starts a new clean chat, saving current if needed and resetting conversation ID."""
        self._archive_current_conversation()
        self.active_conversation_id = None
        self.chat_history.clear()
        self._last_raw_response = ""
        self.chat_view.clear()
        if show_greeting:
            self._append_system_message("Started a new chat session.")

