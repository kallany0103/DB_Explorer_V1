import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.components import PrimaryButton, SecondaryButton
from widgets.results_view.summary_calculator import (
    CellSummary,
    format_summary_for_clipboard,
    get_summary_display_rows,
)


class CellSummaryDialog(QDialog):
    """
    Dialog displaying detailed statistical summary of selected cells,
    resembling TOAD's 'Summarize Selected Cells' / calculate dialog.
    """

    def __init__(self, summary: CellSummary, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.setWindowTitle("Summarize Selected Cells")
        self.resize(380, 420)
        self.setMinimumSize(320, 360)
        self.setWindowIcon(qta.icon("fa5s.calculator", color="#2563EB"))
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header info
        header_label = QLabel(f"<b>Statistical Summary</b> ({self.summary.total_count:,} cells selected)")
        header_label.setStyleSheet("color: #1E293B; font-size: 13px;")
        layout.addWidget(header_label)

        # Table showing metrics
        self.table = QTableWidget()
        self.table.setObjectName("cell_summary_table")
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        rows = get_summary_display_rows(self.summary)
        self.table.setRowCount(len(rows))
        for row_idx, (metric, val) in enumerate(rows):
            item_metric = QTableWidgetItem(metric)
            item_metric.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            
            item_val = QTableWidgetItem(val)
            item_val.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item_val.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.table.setItem(row_idx, 0, item_metric)
            self.table.setItem(row_idx, 1, item_val)
            self.table.setRowHeight(row_idx, 26)

        layout.addWidget(self.table)

        # Status label for copy feedback
        self.feedback_label = QLabel("")
        self.feedback_label.setStyleSheet("color: #16A34A; font-size: 11px;")
        layout.addWidget(self.feedback_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        copy_btn = SecondaryButton("Copy to Clipboard")
        copy_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        close_btn = PrimaryButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _copy_to_clipboard(self) -> None:
        text = format_summary_for_clipboard(self.summary)
        QApplication.clipboard().setText(text)
        self.feedback_label.setText("Summary copied to clipboard!")
