"""widgets/worksheet/batch_optimize_dialog.py

Interactive dialog for batch workload SQL optimization, script-wide anti-pattern auditing,
prioritized tuning ranking, and automated multi-statement rewrites.
"""

from typing import Callable, Optional

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from db.optimizer.batch import (
    BatchItemResult,
    BatchOptimizationSummary,
    analyze_batch_workload,
)
from ui.components import PrimaryButton, SecondaryButton
from ui.optimize_style import OPTIMIZE_DIALOG_STYLE
from widgets.worksheet.optimize_dialog import OptimizeSqlDialog
from workers.optimizer_worker import BatchOptimizerWorker


class BatchOptimizerDialog(QDialog):
    """Workload & Batch SQL Optimizer dialog for multi-statement scripts."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        script_text: str = "",
        dialect: str = "postgres",
        conn_data: Optional[dict] = None,
        on_apply_script: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("batchOptimizerDialog")
        self.setWindowTitle("Workload & Batch SQL Optimizer")
        self.resize(1100, 720)
        self.setMinimumSize(920, 560)

        self.script_text = script_text
        self.dialect = dialect
        self.conn_data = conn_data
        self.on_apply_script = on_apply_script

        self.summary: BatchOptimizationSummary = analyze_batch_workload(
            script_text, dialect=dialect, conn_data=None
        )
        self.selected_item: Optional[BatchItemResult] = None

        self.setStyleSheet(OPTIMIZE_DIALOG_STYLE)
        self._init_ui()
        self._populate_table()
        self._select_initial_row()
        self._start_live_batch_evaluation()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Frame
        header = self._create_header()
        main_layout.addWidget(header)

        # 2. KPI Metrics Strip
        kpi_strip = self._create_kpi_strip()
        main_layout.addWidget(kpi_strip)

        # 3. Splitter Body
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.setHandleWidth(4)

        # Top: Workload Statements Leaderboard Table
        top_pane = self._create_leaderboard_pane()
        splitter.addWidget(top_pane)

        # Bottom: Statement SQL Comparison Viewer
        bottom_pane = self._create_diff_pane()
        splitter.addWidget(bottom_pane)

        splitter.setSizes([380, 240])
        main_layout.addWidget(splitter, 1)

        # 4. Footer Bar
        footer = self._create_footer()
        main_layout.addWidget(footer)

    def _create_header(self) -> QFrame:
        header_frame = QFrame(self)
        header_frame.setObjectName("optimizerHeaderFrame")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(16, 8, 16, 8)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title_label = QLabel("Workload & Batch SQL Optimizer", header_frame)
        title_label.setObjectName("optimizerTitle")
        subtitle_label = QLabel(
            "Multi-statement script analysis, bottleneck triage ranking, and batch query rewrites",
            header_frame,
        )
        subtitle_label.setObjectName("optimizerSubtitle")
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        h_layout.addLayout(title_block, 1)

        engine_name = self.dialect.upper() if self.dialect else "SQL"
        engine_badge = QLabel(f"ENGINE: {engine_name}", header_frame)
        engine_badge.setStyleSheet(
            "font-size: 8pt; font-weight: 700; color: #475569; background: #F1F5F9; "
            "border: 1px solid #CBD5E1; border-radius: 4px; padding: 4px 8px;"
        )
        h_layout.addWidget(engine_badge)
        return header_frame

    def _create_kpi_strip(self) -> QFrame:
        strip = QFrame(self)
        strip.setObjectName("kpiStripFrame")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(24)

        # Card 1: Total Statements
        self.kpi_total_lbl = QLabel(f"{self.summary.total_statements} Queries", strip)
        self.kpi_total_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "TOTAL STATEMENTS", self.kpi_total_lbl))

        # Card 2: Statements Needing Tuning
        self.kpi_tuning_lbl = QLabel(f"{self.summary.statements_needing_tuning} Queries", strip)
        self.kpi_tuning_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "NEEDS TUNING", self.kpi_tuning_lbl))

        # Card 3: Workload Savings
        self.kpi_savings_lbl = QLabel(f"-{self.summary.total_savings_pct}%", strip)
        self.kpi_savings_lbl.setProperty("class", "kpi-val-highlight")
        layout.addLayout(self._make_kpi_box(strip, "WORKLOAD SAVINGS", self.kpi_savings_lbl))

        # Card 4: Estimated Plan Cost
        self.kpi_cost_lbl = QLabel(
            f"{self.summary.total_cost_optimized:.1f} vs {self.summary.total_cost_baseline:.1f}",
            strip,
        )
        self.kpi_cost_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "ESTIMATED TOTAL COST", self.kpi_cost_lbl))

        layout.addStretch()
        self._update_kpi_strip()
        return strip

    def _make_kpi_box(self, parent: QWidget, title: str, value_lbl: QLabel) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        title_lbl = QLabel(title, parent)
        title_lbl.setProperty("class", "kpi-title")
        box.addWidget(title_lbl)
        box.addWidget(value_lbl)
        return box

    def _update_kpi_strip(self) -> None:
        self.kpi_total_lbl.setText(f"{self.summary.total_statements} Statements")

        tuning_count = self.summary.statements_needing_tuning
        if tuning_count > 0:
            self.kpi_tuning_lbl.setText(f"{tuning_count} Statements")
            self.kpi_tuning_lbl.setStyleSheet("color: #B45309; font-weight: 700;")
        else:
            self.kpi_tuning_lbl.setText("All Optimal")
            self.kpi_tuning_lbl.setStyleSheet("color: #166534; font-weight: 700;")

        if self.summary.total_savings_pct > 0:
            self.kpi_savings_lbl.setText(f"-{self.summary.total_savings_pct}% Cost")
            self.kpi_savings_lbl.setStyleSheet("color: #166534; font-weight: 700;")
        else:
            self.kpi_savings_lbl.setText("Baseline")
            self.kpi_savings_lbl.setStyleSheet("color: #475569; font-weight: 700;")

        self.kpi_cost_lbl.setText(
            f"{self.summary.total_cost_optimized:.1f} vs {self.summary.total_cost_baseline:.1f}"
        )

    def _create_leaderboard_pane(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 4)
        layout.setSpacing(6)

        hdr_row = QHBoxLayout()
        title_lbl = QLabel("Workload Statements Priority Ranking", container)
        title_lbl.setStyleSheet("font-weight: 600; color: #1E293B; font-size: 9pt;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        self.tune_btn = SecondaryButton("Tune Selected Query...", container)
        self.tune_btn.setIcon(qta.icon("fa5s.search", color="#475569"))
        self.tune_btn.clicked.connect(self._open_single_tune_dialog)
        hdr_row.addWidget(self.tune_btn)

        copy_script_btn = SecondaryButton("Copy Optimized Script", container)
        copy_script_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_script_btn.clicked.connect(self._copy_optimized_script)
        hdr_row.addWidget(copy_script_btn)

        layout.addLayout(hdr_row)

        self.batch_table = QTableWidget(container)
        self.batch_table.setObjectName("variantTable")
        self.batch_table.setColumnCount(7)
        self.batch_table.setHorizontalHeaderLabels([
            "#", "Line", "Status", "Savings", "Plan Cost", "Primary Bottleneck", "SQL Preview"
        ])
        self.batch_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.batch_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.verticalHeader().setDefaultSectionSize(26)
        self.batch_table.setShowGrid(False)

        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.batch_table.itemSelectionChanged.connect(self._on_row_selected)
        self.batch_table.itemDoubleClicked.connect(lambda item: self._open_single_tune_dialog())
        layout.addWidget(self.batch_table)
        return container

    def _create_diff_pane(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 4, 12, 10)
        layout.setSpacing(4)

        splitter = QSplitter(Qt.Orientation.Horizontal, container)
        splitter.setHandleWidth(4)

        # Left: Original Statement
        orig_widget = QWidget(splitter)
        o_layout = QVBoxLayout(orig_widget)
        o_layout.setContentsMargins(0, 0, 0, 0)
        o_layout.setSpacing(2)
        self.orig_hdr_lbl = QLabel("Original Statement", orig_widget)
        self.orig_hdr_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 8pt;")
        self.orig_editor = QTextEdit(orig_widget)
        self.orig_editor.setObjectName("originalSqlEditor")
        self.orig_editor.setReadOnly(True)
        o_layout.addWidget(self.orig_hdr_lbl)
        o_layout.addWidget(self.orig_editor)

        # Right: Optimized Statement
        opt_widget = QWidget(splitter)
        p_layout = QVBoxLayout(opt_widget)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(2)
        self.opt_hdr_lbl = QLabel("Optimized / Rewritten Statement", opt_widget)
        self.opt_hdr_lbl.setStyleSheet("font-weight: 600; color: #166534; font-size: 8pt;")
        self.opt_editor = QTextEdit(opt_widget)
        self.opt_editor.setObjectName("optimizedSqlEditor")
        self.opt_editor.setReadOnly(True)
        p_layout.addWidget(self.opt_hdr_lbl)
        p_layout.addWidget(self.opt_editor)

        splitter.setSizes([450, 450])
        layout.addWidget(splitter)
        return container

    def _create_footer(self) -> QFrame:
        footer = QFrame(self)
        footer.setStyleSheet("background-color: #F8FAFC; border-top: 1px solid #CBD5E1;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 8, 16, 8)

        close_btn = SecondaryButton("Close", footer)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        layout.addStretch()

        if self.on_apply_script:
            apply_all_btn = PrimaryButton("Apply All Rewrites to Worksheet", footer)
            apply_all_btn.setIcon(qta.icon("fa5s.check", color="#FFFFFF"))
            apply_all_btn.clicked.connect(self._apply_all_rewrites)
            layout.addWidget(apply_all_btn)

        return footer

    def _populate_table(self) -> None:
        self.batch_table.setRowCount(len(self.summary.items))
        for row, it in enumerate(self.summary.items):
            item_idx = QTableWidgetItem(str(it.statement_index))
            item_idx.setData(Qt.ItemDataRole.UserRole, it.statement_index)

            item_line = QTableWidgetItem(f"L{it.start_line}")

            item_status = QTableWidgetItem(it.status)
            if it.status == "Needs Tuning":
                item_status.setForeground(Qt.GlobalColor.darkRed)
            else:
                item_status.setForeground(Qt.GlobalColor.darkGreen)

            savings_str = f"-{it.cost_reduction_pct}%" if it.cost_reduction_pct > 0 else "-"
            item_savings = QTableWidgetItem(savings_str)

            cost_str = f"{it.optimized_cost:.1f} vs {it.baseline_cost:.1f}"
            item_cost = QTableWidgetItem(cost_str)

            item_bottleneck = QTableWidgetItem(it.top_finding)

            preview_text = " ".join(it.sql.split())
            if len(preview_text) > 80:
                preview_text = preview_text[:77] + "..."
            item_preview = QTableWidgetItem(preview_text)

            for col, item in enumerate([
                item_idx, item_line, item_status, item_savings, item_cost, item_bottleneck, item_preview
            ]):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.batch_table.setItem(row, col, item)

    def _select_initial_row(self) -> None:
        if self.summary.items:
            self.batch_table.selectRow(0)

    def _on_row_selected(self) -> None:
        selected_items = self.batch_table.selectedItems()
        if not selected_items:
            return

        row = self.batch_table.currentRow()
        if 0 <= row < len(self.summary.items):
            self.selected_item = self.summary.items[row]
            self.orig_editor.setPlainText(self.selected_item.sql)
            self.opt_editor.setPlainText(self.selected_item.best_rewrite_sql)
            self.orig_hdr_lbl.setText(f"Original Statement #{self.selected_item.statement_index} (Line {self.selected_item.start_line})")
            status_text = f"Optimized Statement ({self.selected_item.top_finding})"
            self.opt_hdr_lbl.setText(status_text)

    def _open_single_tune_dialog(self) -> None:
        if not self.selected_item:
            return

        def handle_single_apply(rewritten_sql: str) -> None:
            # Update this item's rewrite
            self.selected_item.best_rewrite_sql = rewritten_sql
            self.opt_editor.setPlainText(rewritten_sql)

        dialog = OptimizeSqlDialog(
            parent=self,
            sql=self.selected_item.sql,
            dialect=self.dialect,
            conn_data=self.conn_data,
            on_apply=handle_single_apply,
        )
        dialog.exec()

    def _copy_optimized_script(self) -> None:
        QApplication.clipboard().setText(self.summary.full_optimized_script)

    def _apply_all_rewrites(self) -> None:
        if self.on_apply_script:
            self.on_apply_script(self.summary.full_optimized_script)
        self.accept()

    def _start_live_batch_evaluation(self) -> None:
        if not self.conn_data or not self.conn_data.get("host"):
            return

        worker = BatchOptimizerWorker(self.script_text, self.dialect, self.conn_data)
        worker.signals.finished.connect(self._on_live_batch_finished)
        QThreadPool.globalInstance().start(worker)

    def _on_live_batch_finished(self, summary: BatchOptimizationSummary) -> None:
        self.summary = summary
        self._populate_table()
        self._update_kpi_strip()
        self._select_initial_row()

