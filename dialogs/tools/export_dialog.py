# dialogs/tools/export_dialog.py

import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from ui.components import PrimaryButton, SecondaryButton
from ui.icons import get_icon


class ExportDialog(QDialog):
    """
    Unified dialog for exporting query results and table data.
    Provides destination, file format, and format-specific settings in a clean single view.
    """

    def __init__(self, parent=None, default_filename: str = "query_results.csv"):
        super().__init__(parent)
        self.setWindowTitle("Export Data")
        self.resize(540, 420)
        self.setMinimumSize(480, 360)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Scrollable / Padded Body ─────────────────────────────────
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(14)

        # ── Group 1: Output Destination & Format ─────────────────────
        dest_group = QGroupBox("Output Destination && Format")
        dest_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 9pt;
                color: #1E293B;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: #FFFFFF;
            }
        """)
        dest_form = QFormLayout(dest_group)
        dest_form.setContentsMargins(14, 12, 14, 12)
        dest_form.setHorizontalSpacing(14)
        dest_form.setVerticalSpacing(10)
        dest_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 1. File Name
        self.filename_edit = QLineEdit(default_filename)
        self.filename_edit.setFixedHeight(28)
        dest_form.addRow("File Name:", self.filename_edit)

        # 2. Location + Browse Button
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        self.location_edit = QLineEdit(desktop_path)
        self.location_edit.setFixedHeight(28)

        browse_btn = SecondaryButton(get_icon("msc.folder-opened", color="#374151"), "")
        browse_btn.setFixedHeight(28)
        browse_btn.setFixedWidth(34)
        browse_btn.setToolTip("Browse Destination Folder")
        browse_btn.clicked.connect(self.browse_folder)

        loc_layout = QHBoxLayout()
        loc_layout.setContentsMargins(0, 0, 0, 0)
        loc_layout.setSpacing(6)
        loc_layout.addWidget(self.location_edit)
        loc_layout.addWidget(browse_btn)
        dest_form.addRow("Location:", loc_layout)

        # 3. Format Selection
        self.format_combo = QComboBox()
        self.format_combo.setFixedHeight(28)
        self.format_combo.addItem("CSV (Comma Separated) (*.csv)", "csv")
        self.format_combo.addItem("Excel Workbook (*.xlsx)", "xlsx")
        self.format_combo.addItem("Text / Tab Delimited (*.txt)", "txt")
        self.format_combo.currentTextChanged.connect(self.on_format_change)
        dest_form.addRow("Format:", self.format_combo)

        # 4. Encoding
        self.encoding_combo = QComboBox()
        self.encoding_combo.setFixedHeight(28)
        self.encoding_combo.addItems(["UTF-8", "LATIN1", "windows-1252", "utf-8-sig"])
        self.encoding_combo.setEditable(True)
        dest_form.addRow("Encoding:", self.encoding_combo)

        body_layout.addWidget(dest_group)

        # ── Group 2: CSV Formatting Options ──────────────────────────
        self.csv_group = QGroupBox("CSV Formatting Options")
        self.csv_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 9pt;
                color: #1E293B;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                background-color: #FFFFFF;
            }
        """)
        csv_form = QFormLayout(self.csv_group)
        csv_form.setContentsMargins(14, 12, 14, 12)
        csv_form.setHorizontalSpacing(14)
        csv_form.setVerticalSpacing(10)
        csv_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Headers Checkbox
        self.header_check = QCheckBox("Include column headers in output")
        self.header_check.setChecked(True)
        csv_form.addRow("Headers:", self.header_check)

        # Delimiter & Quote Character
        opts_row = QHBoxLayout()
        opts_row.setContentsMargins(0, 0, 0, 0)
        opts_row.setSpacing(16)

        self.delimiter_combo = QComboBox()
        self.delimiter_combo.setFixedHeight(28)
        self.delimiter_combo.setFixedWidth(130)
        self.delimiter_combo.addItem("Comma ( , )", ",")
        self.delimiter_combo.addItem("Semicolon ( ; )", ";")
        self.delimiter_combo.addItem("Pipe ( | )", "|")
        self.delimiter_combo.addItem("Tab ( \\t )", "\\t")
        self.delimiter_combo.setEditable(True)
        opts_row.addWidget(self.delimiter_combo)

        opts_row.addWidget(QLabel("Quote char:"))
        self.quote_edit = QLineEdit('"')
        self.quote_edit.setFixedHeight(28)
        self.quote_edit.setFixedWidth(45)
        self.quote_edit.setMaxLength(1)
        self.quote_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        opts_row.addWidget(self.quote_edit)
        opts_row.addStretch()

        csv_form.addRow("Delimiter:", opts_row)
        body_layout.addWidget(self.csv_group)

        body_layout.addStretch()
        root_layout.addWidget(body, 1)

        # ── Grounded Footer Button Bar ───────────────────────────────
        footer = QFrame()
        footer.setObjectName("dialogFooter")
        footer.setStyleSheet("""
            QFrame#dialogFooter {
                background-color: #F8FAFC;
                border-top: 1px solid #E2E8F0;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_layout.setSpacing(8)
        footer_layout.addStretch()

        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.setMinimumWidth(85)
        cancel_btn.setFixedHeight(30)
        cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(cancel_btn)

        export_btn = PrimaryButton(get_icon("msc.export", color="#FFFFFF"), "Export")
        export_btn.setMinimumWidth(95)
        export_btn.setFixedHeight(30)
        export_btn.setDefault(True)
        export_btn.clicked.connect(self.accept)
        footer_layout.addWidget(export_btn)

        root_layout.addWidget(footer)

        self.on_format_change(self.format_combo.currentText())

    def on_format_change(self, _format_text: str = "") -> None:
        """Handle format selection changes: auto-update extension and toggle CSV options."""
        format_id = self.format_combo.currentData() or "csv"
        is_csv = format_id in ("csv", "txt")

        self.csv_group.setVisible(is_csv)
        self.encoding_combo.setEnabled(is_csv)

        current_filename = self.filename_edit.text()
        base_name, _ = os.path.splitext(current_filename)

        ext = f".{format_id}"
        self.filename_edit.setText(f"{base_name}{ext}")

    def browse_folder(self) -> None:
        """Open native directory picker to choose the export destination folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.location_edit.text()
        )
        if folder:
            self.location_edit.setText(folder)

    def get_options(self) -> dict:
        """Return the dictionary of export parameters required by export workers."""
        delimiter = self.delimiter_combo.currentData() or self.delimiter_combo.currentText()
        if delimiter in ("\\t", r"\t"):
            delimiter = "\t"

        full_path = os.path.join(self.location_edit.text(), self.filename_edit.text())
        format_id = self.format_combo.currentData() or "csv"

        return {
            "filename": full_path,
            "format": format_id,
            "encoding": self.encoding_combo.currentText(),
            "header": self.header_check.isChecked(),
            "delimiter": delimiter,
            "quote": self.quote_edit.text(),
        }
