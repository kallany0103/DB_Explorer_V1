# dialogs/release_notes_dialog.py
"""Release Notes dialog – renders RELEASE_NOTES.md as rich in-app documentation."""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTextBrowser, QWidget, QFrame
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.components import SecondaryButton


class ReleaseNotesDialog(QDialog):
    """Displays the application release notes document directly inside the app."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Release Notes & Documentation")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setMinimumSize(720, 600)
        self.resize(800, 680)

        self._build_ui()
        self._load_content()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header_bar = QWidget()
        header_bar.setObjectName("headerBar")
        hb = QHBoxLayout(header_bar)
        hb.setContentsMargins(24, 16, 24, 16)

        try:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                qta.icon("mdi.book-open-page-variant-outline", color="#ffffff").pixmap(24, 24)
            )
            hb.addWidget(icon_lbl)
        except Exception:
            pass

        title = QLabel("Universal SQL Client — Release Notes")
        title.setObjectName("dialogTitle")
        hb.addWidget(title)
        hb.addStretch()

        badge = QLabel("Document Viewer")
        badge.setObjectName("badgeLabel")
        hb.addWidget(badge)

        root.addWidget(header_bar)

        # Content area with QTextBrowser (supports native Markdown rendering)
        container = QWidget()
        container.setObjectName("contentContainer")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(20, 20, 20, 20)

        self.text_browser = QTextBrowser()
        self.text_browser.setObjectName("notesBrowser")
        self.text_browser.setOpenExternalLinks(True)
        cl.addWidget(self.text_browser)

        root.addWidget(container, 1)

        # Footer
        footer = QWidget()
        footer.setObjectName("dialogFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 12)

        self.path_label = QLabel("RELEASE_NOTES.md")
        self.path_label.setObjectName("pathLabel")
        fl.addWidget(self.path_label)

        fl.addStretch()

        close_btn = SecondaryButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        fl.addWidget(close_btn)

        root.addWidget(footer)

    def _load_content(self) -> None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        notes_path = os.path.join(project_root, "RELEASE_NOTES.md")
        
        if os.path.isfile(notes_path):
            try:
                with open(notes_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_browser.setMarkdown(content)
                self.path_label.setText(f"Source: {notes_path}")
            except Exception as e:
                self.text_browser.setPlainText(f"Error loading release notes:\n{e}")
        else:
            self.text_browser.setPlainText(f"Release notes file not found:\n{notes_path}")

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background-color: #f8fafc;
            }
            QWidget#headerBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1e3a8a, stop:1 #0284c7);
                border-bottom: 1px solid #1e40af;
            }
            QLabel#dialogTitle {
                font-size: 14pt;
                font-weight: 700;
                color: #ffffff;
                margin-left: 8px;
            }
            QLabel#badgeLabel {
                font-size: 8pt;
                font-weight: 600;
                color: #bfdbfe;
                background-color: rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 4px 8px;
            }
            QWidget#contentContainer {
                background-color: #f8fafc;
            }
            QTextBrowser#notesBrowser {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 10pt;
                color: #1e293b;
                line-height: 1.6;
            }
            QWidget#dialogFooter {
                background-color: #f1f5f9;
                border-top: 1px solid #e2e8f0;
            }
            QLabel#pathLabel {
                font-size: 8.5pt;
                color: #64748b;
            }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)
