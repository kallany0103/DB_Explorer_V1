"""
dialogs/tools/describe_prompt_dialog.py
Modern prompt dialog for 'Describe (F4)' when no table or identifier is selected.
"""

from typing import Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import PrimaryButton, SecondaryButton
from ui.icons import get_icon


class DescribePromptDialog(QDialog):
    """
    Modern modal dialog prompting the user for a table, view, or schema name
    to describe (F4) when no object is currently selected in the editor.
    """

    def __init__(self, parent=None, initial_text: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Describe (F4)")
        self.setWindowIcon(get_icon("msc.table", color="#2563EB"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")

        self._build_ui(initial_text)

    def _build_ui(self, initial_text: str) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Body Content ─────────────────────────────────────────────
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 16)
        body_layout.setSpacing(14)

        # Header with icon badge and informative labels
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_badge = QLabel()
        icon_badge.setFixedSize(38, 38)
        icon_badge.setStyleSheet("""
            QLabel {
                background-color: #EFF6FF;
                border: 1px solid #DBEAFE;
                border-radius: 8px;
            }
        """)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico = get_icon("msc.table", color="#2563EB")
        icon_badge.setPixmap(ico.pixmap(20, 20))
        header_row.addWidget(icon_badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_lbl = QLabel("Enter Object or Schema Name")
        title_lbl.setStyleSheet("font-size: 10pt; font-weight: 600; color: #0F172A;")
        subtitle_lbl = QLabel("Inspect columns, types, constraints, indexes, and DDL script.")
        subtitle_lbl.setStyleSheet("font-size: 8.5pt; color: #64748B;")
        subtitle_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)
        text_col.addWidget(subtitle_lbl)
        header_row.addLayout(text_col, 1)

        body_layout.addLayout(header_row)

        # Object name input field
        self._input = QLineEdit(initial_text)
        self._input.setPlaceholderText("e.g., employees, hr.departments, public")
        self._input.setFixedHeight(32)
        self._input.setClearButtonEnabled(True)
        self._input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 9.5pt;
                color: #0F172A;
                background-color: #FFFFFF;
                selection-background-color: #BFDBFE;
            }
            QLineEdit:focus {
                border: 1px solid #0078D4;
            }
            QLineEdit::placeholder {
                color: #94A3B8;
            }
        """)
        self._input.returnPressed.connect(self._on_accept)
        self._input.textChanged.connect(self._on_text_changed)
        body_layout.addWidget(self._input)

        root_layout.addWidget(body)

        # ── Grounded Footer Bar ──────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border-top: 1px solid #E2E8F0;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        self._cancel_btn = SecondaryButton("Cancel")
        self._cancel_btn.setMinimumWidth(80)
        self._cancel_btn.setFixedHeight(30)
        self._cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self._cancel_btn)

        self._ok_btn = PrimaryButton("Describe")
        self._ok_btn.setIcon(get_icon("msc.inspect", color="#FFFFFF"))
        self._ok_btn.setMinimumWidth(95)
        self._ok_btn.setFixedHeight(30)
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_accept)
        footer_layout.addWidget(self._ok_btn)

        root_layout.addWidget(footer)

        # Initialize button state and focus
        self._on_text_changed(self._input.text())
        if initial_text:
            self._input.selectAll()
        self._input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        self._ok_btn.setEnabled(bool(text.strip()))

    def _on_accept(self) -> None:
        if self._input.text().strip():
            self.accept()

    def target_name(self) -> str:
        """Returns the trimmed target object name."""
        return self._input.text().strip()

    @classmethod
    def get_target(cls, parent=None, initial_text: str = "") -> Tuple[str, bool]:
        """
        Static helper mirroring QInputDialog.getText.
        Returns (target_name, ok_pressed).
        """
        dlg = cls(parent=parent, initial_text=initial_text)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        return (dlg.target_name(), accepted)
