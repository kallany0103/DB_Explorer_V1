"""Dialog for viewing and editing sqlnet.ora for a selected Oracle Instant Client.

Opens the file from `<client_dir>/network/admin/sqlnet.ora`.
If the file does not yet exist the editor starts empty and creates it (along
with the `network/admin` directory) on save.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.components import PrimaryButton, SecondaryButton

_DEFAULT_SQLNET_CONTENT = """\
# sqlnet.ora - Oracle Net Configuration
# Reference: https://docs.oracle.com/en/database/oracle/oracle-database/19/netrf/parameters-for-the-sqlnet.ora-file.html

SQLNET.AUTHENTICATION_SERVICES = (NTS)
NAMES.DIRECTORY_PATH = (TNSNAMES, EZCONNECT)
"""


class SqlnetEditorDialog(QDialog):
    """Viewer/editor for the Oracle sqlnet.ora configuration file."""

    def __init__(self, sqlnet_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sqlnet_path = sqlnet_path

        self.setWindowTitle("SQLNET Editor")
        self.setMinimumSize(620, 480)
        self.resize(660, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setObjectName("sqlnetEditorDialog")

        self._build_ui()
        self._load_file()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        # Title
        title_lbl = QLabel("SQLNET Editor")
        title_lbl.setObjectName("dialogTitle")
        root.addWidget(title_lbl)

        # Path info
        path_lbl = QLabel(str(self._sqlnet_path))
        path_lbl.setObjectName("dialogSubtitle")
        path_lbl.setWordWrap(True)
        root.addWidget(path_lbl)

        # Editor
        self._editor = QPlainTextEdit()
        self._editor.setObjectName("sqlnetEditorPane")
        self._editor.setPlaceholderText(
            "# sqlnet.ora is empty or does not exist yet.\n"
            "# Edit here and click Save to create it."
        )
        self._editor.setStyleSheet(
            "QPlainTextEdit {"
            "  font-family: Consolas, 'Courier New', monospace;"
            "  font-size: 9.5pt;"
            "  background: #1e1e2e;"
            "  color: #cdd6f4;"
            "  border: 1px solid #313244;"
            "  border-radius: 6px;"
            "  padding: 6px;"
            "}"
        )
        root.addWidget(self._editor, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = PrimaryButton("Save")
        self._save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load_file(self) -> None:
        """Load existing sqlnet.ora content into the editor, or show defaults."""
        if self._sqlnet_path.is_file():
            try:
                content = self._sqlnet_path.read_text(encoding="utf-8", errors="replace")
                self._editor.setPlainText(content)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Load Error",
                    f"Could not read {self._sqlnet_path}:\n{exc}",
                )
        else:
            # Offer the user a sensible starter template
            self._editor.setPlainText(_DEFAULT_SQLNET_CONTENT)

    def _on_save(self) -> None:
        """Write editor content to disk, creating directories as needed."""
        content = self._editor.toPlainText()
        try:
            self._sqlnet_path.parent.mkdir(parents=True, exist_ok=True)
            self._sqlnet_path.write_text(content, encoding="utf-8")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save {self._sqlnet_path}:\n{exc}",
            )
