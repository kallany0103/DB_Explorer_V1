from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
)
from PySide6.QtCore import Qt
from ui.components import PrimaryButton, SecondaryButton


class RenameTabDialog(QDialog):
    """A standard dialog for renaming a worksheet tab."""

    def __init__(self, current_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Worksheet")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setFixedWidth(320)

        self._build_ui(current_name)
        self._apply_styles()

    def _build_ui(self, current_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── Body ─────────────────────────────────────────────────────
        field_label = QLabel("New name:")
        field_label.setObjectName("renameFieldLabel")
        layout.addWidget(field_label)

        self._input = QLineEdit(current_name)
        self._input.setObjectName("renameInput")
        self._input.setFixedHeight(30)
        self._input.selectAll()
        self._input.returnPressed.connect(self._on_accept)
        layout.addWidget(self._input)

        # ── Buttons ──────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self._cancel_btn = SecondaryButton("Cancel")
        self._cancel_btn.setMinimumWidth(80)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._ok_btn = PrimaryButton("Rename")
        self._ok_btn.setMinimumWidth(80)
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self._ok_btn)

        layout.addLayout(btn_layout)

    def _apply_styles(self) -> None:
        # Subtle styling for the label and input, Buttons are styled by ui.components
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#renameFieldLabel {
                font-size: 9pt;
                color: #374151;
            }
            QLineEdit#renameInput {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10pt;
                color: #111827;
                background-color: #ffffff;
                selection-background-color: #bfdbfe;
            }
            QLineEdit#renameInput:focus {
                border-color: #0078d4;
            }
        """)

    def new_name(self) -> str:
        """Return the trimmed text entered by the user."""
        return self._input.text().strip()

    def _on_accept(self) -> None:
        if self._input.text().strip():
            self.accept()
