"""widgets/worksheet/optimize_dialog.py

Interactive dialog for multi-variant SQL optimization, execution plan cost benchmarking,
empirical runtime benchmarking, and risk-free virtual index simulation.
"""

from typing import Callable, List, Optional

from PySide6.QtCore import QRect, QSize, QThreadPool, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QSplitter,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from db.optimizer.cost_evaluator import evaluate_variant_costs
from db.optimizer.engine import OptimizationResult, analyze_query
from db.optimizer.variants import QueryVariant, generate_query_variants
from db.optimizer.virtual_index import VirtualIndexResult
from ui.components import PrimaryButton, SecondaryButton
from ui.optimize_style import OPTIMIZE_DIALOG_STYLE
from widgets.worksheet.plan_diff_view import PlanDiffWidget
from workers.optimizer_worker import BenchmarkWorker, OptimizerCostWorker, VirtualIndexWorker


class CandidateStrategyDelegate(QStyledItemDelegate):
    """Renders candidate name on line 1 (semi-bold) and strategy on line 2 (muted subtext)."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()

        # Row selection background
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if is_selected:
            painter.fillRect(option.rect, QColor("#EFF6FF"))
        else:
            painter.fillRect(option.rect, QColor("#FFFFFF"))

        # Subtle bottom divider line
        painter.setPen(QColor("#F1F5F9"))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        title = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        subtitle = str(index.data(Qt.ItemDataRole.UserRole + 1) or "")
        is_best = bool(index.data(Qt.ItemDataRole.UserRole + 2) or False)

        content_rect = option.rect.adjusted(8, 2, -8, -2)
        half_h = content_rect.height() // 2

        # Line 1: Title (Candidate Name)
        font_title = QFont(option.font)
        font_title.setPointSize(8)
        font_title.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font_title)
        title_color = QColor("#166534") if is_best else QColor("#0F172A")
        painter.setPen(title_color)

        rect_title = QRect(content_rect.left(), content_rect.top(), content_rect.width(), half_h)
        elided_title = painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, rect_title.width())
        painter.drawText(rect_title, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        # Line 2: Subtitle (Optimization Strategy Description)
        font_sub = QFont(option.font)
        font_sub.setPointSize(7)
        painter.setFont(font_sub)
        painter.setPen(QColor("#64748B"))

        rect_sub = QRect(content_rect.left(), content_rect.top() + half_h, content_rect.width(), half_h)
        elided_sub = painter.fontMetrics().elidedText(subtitle, Qt.TextElideMode.ElideRight, rect_sub.width())
        painter.drawText(rect_sub, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_sub)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(240, 40)


class OptimizeSqlDialog(QDialog):
    """SQL Optimizer dialog with multi-variant leaderboard, benchmarking, and virtual index simulation."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        sql: str = "",
        dialect: str = "postgres",
        conn_data: Optional[dict] = None,
        on_apply: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("optimizeSqlDialog")
        self.setWindowTitle("SQL Optimizer")
        self.resize(1080, 700)
        self.setMinimumSize(900, 540)

        self.original_sql = sql
        self.dialect = dialect
        self.conn_data = conn_data
        self.on_apply = on_apply

        self.result: OptimizationResult = analyze_query(sql, dialect=dialect)
        self.variants: List[QueryVariant] = generate_query_variants(sql, dialect=dialect)
        self.selected_variant: Optional[QueryVariant] = None

        # Calculate initial heuristic costs
        evaluate_variant_costs(self.variants, conn_data=None)

        self.setStyleSheet(OPTIMIZE_DIALOG_STYLE)
        self._init_ui()
        self._populate_variants_table()
        self._select_initial_variant()
        self._start_live_cost_evaluation()

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

        # 3. Main Splitter Body
        body_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        body_splitter.setHandleWidth(4)

        # Left: Leaderboard & SQL Diff Viewer
        left_pane = self._create_left_pane()
        left_pane.setMinimumWidth(500)
        body_splitter.addWidget(left_pane)

        # Right: Findings & Index Recommendations
        right_pane = self._create_findings_pane()
        right_pane.setMinimumWidth(320)
        body_splitter.addWidget(right_pane)

        body_splitter.setSizes([640, 440])
        body_splitter.setStretchFactor(0, 3)
        body_splitter.setStretchFactor(1, 2)
        main_layout.addWidget(body_splitter, 1)

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
        title_label = QLabel("SQL Optimizer", header_frame)
        title_label.setObjectName("optimizerTitle")
        subtitle_label = QLabel(
            "Multi-variant execution plan benchmark, deterministic rewrites, and virtual index simulator",
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

        self.depth_combo = QComboBox(header_frame)
        self.depth_combo.addItems(["Standard Tuning", "Exhaustive Tuning"])
        self.depth_combo.setToolTip("Adjust search depth and optimization hint exploration")
        self.depth_combo.setStyleSheet(
            "QComboBox { font-size: 8pt; font-weight: 600; color: #334155; background: #FFFFFF; "
            "border: 1px solid #CBD5E1; border-radius: 4px; padding: 3px 8px; } "
            "QComboBox::drop-down { border: none; }"
        )
        self.depth_combo.currentIndexChanged.connect(self._on_tuning_depth_changed)
        h_layout.addWidget(self.depth_combo)
        return header_frame

    def _create_kpi_strip(self) -> QFrame:
        strip = QFrame(self)
        strip.setObjectName("kpiStripFrame")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(24)

        # Card 1: Best Improvement
        self.kpi_best_lbl = QLabel("0.0%", strip)
        self.kpi_best_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "BEST IMPROVEMENT", self.kpi_best_lbl))

        # Card 2: Cost Comparison
        self.kpi_cost_lbl = QLabel("-", strip)
        self.kpi_cost_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "PLAN COST", self.kpi_cost_lbl))

        # Card 3: Primary Bottleneck
        self.kpi_bottleneck_lbl = QLabel("-", strip)
        self.kpi_bottleneck_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "PRIMARY BOTTLENECK", self.kpi_bottleneck_lbl))

        # Card 4: Alternatives
        self.kpi_alts_lbl = QLabel(f"{len(self.variants)} Candidates", strip)
        self.kpi_alts_lbl.setProperty("class", "kpi-val")
        layout.addLayout(self._make_kpi_box(strip, "ALTERNATIVES", self.kpi_alts_lbl))

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
        best_v = next((v for v in self.variants if v.is_best), None)
        baseline_v = next((v for v in self.variants if v.id == 0), None)
        is_proc = any(
            v.plan_summary in ("PL/SQL Block", "Procedural Block", "Procedural Execution")
            for v in self.variants
        )

        if is_proc or (baseline_v and baseline_v.cost is None):
            self.kpi_best_lbl.setText("N/A")
            self.kpi_best_lbl.setStyleSheet("color: #475569; font-weight: 700;")
            self.kpi_cost_lbl.setText("N/A (Procedural)")
            self.kpi_cost_lbl.setStyleSheet("color: #475569; font-weight: 700;")
            self.kpi_bottleneck_lbl.setText("None (Procedural Block)")
            self.kpi_bottleneck_lbl.setStyleSheet("color: #166534; font-weight: 600;")
            self.kpi_alts_lbl.setText("1 Block")
            return

        if best_v and best_v.id != 0 and best_v.cost_change_pct is not None and best_v.cost_change_pct < 0:
            self.kpi_best_lbl.setText(f"{best_v.cost_change_pct}%")
            self.kpi_best_lbl.setStyleSheet("color: #166534; font-weight: 700;")
        else:
            self.kpi_best_lbl.setText("Baseline")
            self.kpi_best_lbl.setStyleSheet("color: #475569; font-weight: 700;")

        if (
            best_v
            and baseline_v
            and best_v.cost is not None
            and baseline_v.cost is not None
            and best_v.id != 0
            and abs(best_v.cost - baseline_v.cost) >= 0.05
        ):
            self.kpi_cost_lbl.setText(f"{best_v.cost:.1f} vs {baseline_v.cost:.1f}")
            self.kpi_cost_lbl.setToolTip(
                f"Optimized Plan Cost: {best_v.cost:.1f} | Original Baseline Cost: {baseline_v.cost:.1f}"
            )
        elif baseline_v and baseline_v.cost is not None:
            self.kpi_cost_lbl.setText(f"{baseline_v.cost:.1f}")
            self.kpi_cost_lbl.setToolTip(
                f"Baseline Plan Cost: {baseline_v.cost:.1f} (Rewrites produced identical plan cost)"
            )
        else:
            self.kpi_cost_lbl.setText("-")
            self.kpi_cost_lbl.setToolTip("")

        if self.result.findings:
            high_findings = [f for f in self.result.findings if f.severity == "HIGH"]
            primary = high_findings[0] if high_findings else self.result.findings[0]
            self.kpi_bottleneck_lbl.setText(primary.title)
            self.kpi_bottleneck_lbl.setStyleSheet("color: #991B1B; font-weight: 600;")
        else:
            self.kpi_bottleneck_lbl.setText("Optimal Structure")
            self.kpi_bottleneck_lbl.setStyleSheet("color: #166534; font-weight: 600;")

        count = len(self.variants)
        plural = "Candidate" if count == 1 else "Candidates"
        self.kpi_alts_lbl.setText(f"{count} {plural}")

    def _create_left_pane(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 6, 10)
        layout.setSpacing(8)

        # Leaderboard Header Bar with Benchmark Action
        tbl_hdr_bar = QHBoxLayout()
        tbl_hdr = QLabel("Candidate Rewrites Leaderboard", container)
        tbl_hdr.setStyleSheet("font-weight: 600; color: #1E293B; font-size: 9pt;")
        tbl_hdr_bar.addWidget(tbl_hdr)
        tbl_hdr_bar.addStretch()

        self.benchmark_btn = SecondaryButton("Run Benchmark", container)
        self.benchmark_btn.setIcon(qta.icon("fa5s.stopwatch", color="#475569"))
        self.benchmark_btn.setToolTip("Empirically execute candidates with safety timeouts to measure actual runtime")
        self.benchmark_btn.clicked.connect(self._run_benchmark)
        tbl_hdr_bar.addWidget(self.benchmark_btn)
        layout.addLayout(tbl_hdr_bar)

        self.variant_table = QTableWidget(container)
        self.variant_table.setObjectName("variantTable")
        self.variant_table.setColumnCount(5)
        self.variant_table.setHorizontalHeaderLabels([
            "Candidate & Optimization Strategy", "Cost", "Improvement", "Runtime", "Plan Operator"
        ])
        self.variant_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.variant_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.variant_table.verticalHeader().setVisible(False)
        self.variant_table.verticalHeader().setDefaultSectionSize(40)
        self.variant_table.setShowGrid(False)
        self.variant_table.setMinimumHeight(62)
        self.variant_table.setItemDelegateForColumn(0, CandidateStrategyDelegate(self.variant_table))

        header = self.variant_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)

        self.variant_table.setColumnWidth(1, 55)
        self.variant_table.setColumnWidth(2, 85)
        self.variant_table.setColumnWidth(3, 110)
        self.variant_table.setColumnWidth(4, 125)

        self.variant_table.itemSelectionChanged.connect(self._on_variant_selected)
        layout.addWidget(self.variant_table)

        # SQL Viewer Tab Widget
        self.sql_tabs = QTabWidget(container)
        self.sql_tabs.setObjectName("diffTabWidget")
        self.sql_tabs.tabBar().setExpanding(False)
        self.sql_tabs.tabBar().setUsesScrollButtons(False)

        # Tab 1: Selected Candidate
        selected_widget = QWidget()
        sel_layout = QVBoxLayout(selected_widget)
        sel_layout.setContentsMargins(8, 8, 8, 8)
        sel_layout.setSpacing(4)

        sel_top_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        self.selected_tab_title = QLabel("Selected Candidate Query", selected_widget)
        self.selected_tab_title.setStyleSheet("font-weight: 600; color: #166534; font-size: 8.5pt;")
        self.selected_tab_strategy = QLabel("", selected_widget)
        self.selected_tab_strategy.setStyleSheet("color: #64748B; font-size: 7.5pt; font-weight: 400;")
        self.selected_tab_strategy.setWordWrap(True)

        title_box.addWidget(self.selected_tab_title)
        title_box.addWidget(self.selected_tab_strategy)
        sel_top_bar.addLayout(title_box, 1)

        copy_sel_btn = SecondaryButton("Copy", selected_widget)
        copy_sel_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_sel_btn.clicked.connect(self._copy_selected_sql)
        sel_top_bar.addWidget(copy_sel_btn)
        sel_layout.addLayout(sel_top_bar)

        self.selected_editor = QTextEdit(selected_widget)
        self.selected_editor.setObjectName("selectedVariantEditor")
        sel_layout.addWidget(self.selected_editor)
        self.sql_tabs.addTab(selected_widget, "Selected Candidate")

        # Tab 2: Original Baseline
        orig_widget = QWidget()
        orig_layout = QVBoxLayout(orig_widget)
        orig_layout.setContentsMargins(8, 8, 8, 8)
        orig_layout.setSpacing(4)

        orig_top_bar = QHBoxLayout()
        orig_hdr = QLabel("Original Baseline Query", orig_widget)
        orig_hdr.setStyleSheet("font-weight: 600; color: #475569; font-size: 8.5pt;")
        orig_top_bar.addWidget(orig_hdr)
        orig_top_bar.addStretch()

        copy_orig_btn = SecondaryButton("Copy", orig_widget)
        copy_orig_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_orig_btn.clicked.connect(self._copy_original_sql)
        orig_top_bar.addWidget(copy_orig_btn)
        orig_layout.addLayout(orig_top_bar)

        self.orig_editor = QTextEdit(orig_widget)
        self.orig_editor.setObjectName("originalSqlEditor")
        self.orig_editor.setReadOnly(True)
        self.orig_editor.setPlainText(self.original_sql)
        orig_layout.addWidget(self.orig_editor)
        self.sql_tabs.addTab(orig_widget, "Original Baseline")

        # Tab 3: Execution Plan Diff Tree
        self.plan_diff_widget = PlanDiffWidget(self.sql_tabs)
        self.sql_tabs.addTab(self.plan_diff_widget, "Execution Plan Diff")

        if len(self.variants) <= 1:
            self.sql_tabs.setTabText(0, "Query")
            self.sql_tabs.setTabVisible(1, False)

        layout.addWidget(self.sql_tabs, 1)
        return container

    def _create_findings_pane(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 10, 12, 10)
        layout.setSpacing(8)

        hdr_label = QLabel("Performance Diagnostics", container)
        hdr_label.setStyleSheet("font-weight: 600; color: #1E293B; font-size: 9pt;")
        layout.addWidget(hdr_label)

        scroll_area = QScrollArea(container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent;")

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(6)

        is_proc = any(
            v.plan_summary in ("PL/SQL Block", "Procedural Block", "Procedural Execution")
            for v in self.variants
        )

        if not self.result.findings:
            clean_card = QFrame(scroll_widget)
            clean_card.setObjectName("findingCard")
            c_layout = QVBoxLayout(clean_card)
            if is_proc:
                dialect_name = "Oracle PL/SQL" if "oracle" in (self.dialect or "").lower() else "Procedural"
                hdr = QLabel(f"{dialect_name} Block Execution", clean_card)
                hdr.setStyleSheet("color: #1E293B; font-weight: 600; font-size: 8.5pt;")
                msg = QLabel(
                    "Procedural code blocks run procedurally within the database runtime. "
                    "Set-based SQL rewrites and cost estimations do not apply to procedural control-flow statements.",
                    clean_card,
                )
                msg.setWordWrap(True)
                msg.setStyleSheet("color: #475569; font-weight: 400; font-size: 8pt; line-height: 1.3;")
                c_layout.addWidget(hdr)
                c_layout.addWidget(msg)
            else:
                msg = QLabel("No anti-patterns detected. The query structure looks good.", clean_card)
                msg.setStyleSheet("color: #166534; font-weight: 500; font-size: 8.5pt;")
                c_layout.addWidget(msg)
            scroll_layout.addWidget(clean_card)
        else:
            for finding in self.result.findings:
                card = self._create_finding_card(scroll_widget, finding)
                scroll_layout.addWidget(card)

        if self.result.index_recommendations:
            idx_card = self._create_index_card(scroll_widget, self.result.index_recommendations)
            scroll_layout.addWidget(idx_card)

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        return container

    def _create_finding_card(self, parent: QWidget, finding) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("findingCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        label_map = {"HIGH": "WARNING", "MEDIUM": "SUGGESTION", "INFO": "NOTE"}
        tag_text = label_map.get(finding.severity, "NOTE")

        badge = QLabel(tag_text, card)
        badge.setProperty("class", "severity-badge")
        badge.setProperty("severity", finding.severity)

        title = QLabel(finding.title, card)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #0F172A;")

        top_row.addWidget(badge)
        top_row.addWidget(title, 1)
        card_layout.addLayout(top_row)

        desc = QLabel(finding.description, card)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 8pt; line-height: 1.3;")
        card_layout.addWidget(desc)

        if finding.suggestion:
            sug = QLabel(f"Tip: {finding.suggestion}", card)
            sug.setWordWrap(True)
            sug.setStyleSheet("color: #0369A1; font-size: 8pt;")
            card_layout.addWidget(sug)

        return card

    def _create_index_card(self, parent: QWidget, indexes: List[str]) -> QFrame:
        card = QFrame(parent)
        card.setObjectName("findingCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        hdr_row = QHBoxLayout()
        icon_lbl = QLabel(card)
        icon_lbl.setPixmap(qta.icon("fa5s.key", color="#475569").pixmap(12, 12))
        title = QLabel("Recommended Indexes", card)
        title.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #1E293B;")
        hdr_row.addWidget(icon_lbl)
        hdr_row.addWidget(title)
        hdr_row.addStretch()
        card_layout.addLayout(hdr_row)

        ddl_text = "\n".join(indexes)
        code_box = QTextEdit(card)
        code_box.setObjectName("indexCodeBox")
        code_box.setReadOnly(True)
        code_box.setMaximumHeight(80)
        code_box.setPlainText(ddl_text)
        card_layout.addWidget(code_box)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        self.sim_btn = SecondaryButton("Simulate Index", card)
        self.sim_btn.setIcon(qta.icon("fa5s.bolt", color="#475569"))
        self.sim_btn.setToolTip("Test index adoption virtually without allocating physical disk space")
        self.sim_btn.clicked.connect(lambda: self._simulate_virtual_index(indexes[0]))
        btn_row.addWidget(self.sim_btn)

        copy_idx_btn = SecondaryButton("Copy DDL", card)
        copy_idx_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_idx_btn.clicked.connect(lambda: QApplication.clipboard().setText(ddl_text))
        btn_row.addWidget(copy_idx_btn)
        card_layout.addLayout(btn_row)

        # Virtual Index Simulation Result Frame (Hidden until run)
        self.sim_result_frame = QFrame(card)
        self.sim_result_frame.setObjectName("simResultBox")
        self.sim_result_frame.hide()

        sim_layout = QVBoxLayout(self.sim_result_frame)
        sim_layout.setContentsMargins(8, 6, 8, 6)
        sim_layout.setSpacing(2)

        self.sim_status_lbl = QLabel(self.sim_result_frame)
        self.sim_status_lbl.setProperty("class", "sim-status")
        sim_layout.addWidget(self.sim_status_lbl)

        self.sim_metric_lbl = QLabel(self.sim_result_frame)
        self.sim_metric_lbl.setProperty("class", "sim-metric")
        sim_layout.addWidget(self.sim_metric_lbl)

        self.sim_detail_lbl = QLabel(self.sim_result_frame)
        self.sim_detail_lbl.setProperty("class", "sim-detail")
        self.sim_detail_lbl.setWordWrap(True)
        sim_layout.addWidget(self.sim_detail_lbl)

        card_layout.addWidget(self.sim_result_frame)
        return card

    def _create_footer(self) -> QFrame:
        footer = QFrame(self)
        footer.setStyleSheet("background-color: #F8FAFC; border-top: 1px solid #CBD5E1;")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 8, 16, 8)

        close_btn = SecondaryButton("Close", footer)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        layout.addStretch()

        self.apply_btn = PrimaryButton("Apply to Worksheet", footer)
        self.apply_btn.setIcon(qta.icon("fa5s.check", color="#FFFFFF"))
        self.apply_btn.clicked.connect(self._apply_sql)
        layout.addWidget(self.apply_btn)
        return footer

    def _populate_variants_table(self) -> None:
        self.variant_table.setRowCount(len(self.variants))
        is_proc = any(
            v.plan_summary in ("PL/SQL Block", "Procedural Block", "Procedural Execution")
            for v in self.variants
        )

        row_h = 40
        hdr_h = 28
        total_h = hdr_h + (len(self.variants) * row_h) + 6
        clamped_h = max(74, min(220, total_h))
        self.variant_table.setFixedHeight(clamped_h)

        for row, v in enumerate(self.variants):
            label_text = f"⭐ {v.label}" if v.is_best and v.id != 0 else v.label
            item_candidate = QTableWidgetItem(label_text)
            item_candidate.setData(Qt.ItemDataRole.UserRole, v.id)
            item_candidate.setData(Qt.ItemDataRole.UserRole + 1, v.strategy)
            item_candidate.setData(Qt.ItemDataRole.UserRole + 2, v.is_best and v.id != 0)
            item_candidate.setToolTip(f"{label_text}\n\nStrategy: {v.strategy}")

            if v.cost is not None:
                cost_str = f"{v.cost:.1f}"
            else:
                cost_str = "N/A" if is_proc else "-"
            item_cost = QTableWidgetItem(cost_str)

            if is_proc:
                imp_str = "N/A"
            elif v.id == 0:
                imp_str = "Baseline"
            elif v.cost_change_pct is not None:
                imp_str = f"{v.cost_change_pct}%"
            else:
                imp_str = "-"
            item_imp = QTableWidgetItem(imp_str)

            # Runtime & Speedup column
            if v.benchmark_status == "running":
                time_str = "Benchmarking..."
            elif v.actual_time_ms is not None:
                if v.id == 0:
                    time_str = f"{v.actual_time_ms:.1f} ms"
                elif v.time_speedup and v.time_speedup > 1.0:
                    time_str = f"{v.actual_time_ms:.1f} ms ({v.time_speedup}x)"
                else:
                    time_str = f"{v.actual_time_ms:.1f} ms"
            else:
                time_str = "N/A" if is_proc else "-"
            item_time = QTableWidgetItem(time_str)

            item_plan = QTableWidgetItem(v.plan_summary or "-")

            for col, item in enumerate([
                item_candidate, item_cost, item_imp, item_time, item_plan
            ]):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.variant_table.setItem(row, col, item)

    def _select_initial_variant(self) -> None:
        best_idx = 0
        for i, v in enumerate(self.variants):
            if v.is_best and v.id != 0:
                best_idx = i
                break
        self.variant_table.selectRow(best_idx)
        self._update_apply_button_state()

    def _update_apply_button_state(self) -> None:
        if not hasattr(self, "apply_btn"):
            return
        if len(self.variants) <= 1:
            self.apply_btn.setEnabled(False)
            self.apply_btn.setText("No Rewrite Needed")
            self.apply_btn.setToolTip(
                "The query is already optimal or procedural. No alternative rewrites were generated."
            )
        elif self.selected_variant and self.selected_variant.id != 0:
            self.apply_btn.setEnabled(True)
            self.apply_btn.setText("Apply Rewrite to Worksheet")
            self.apply_btn.setToolTip("Replace query in worksheet with the selected optimized candidate")
        else:
            self.apply_btn.setEnabled(False)
            self.apply_btn.setText("Apply Rewrite to Worksheet")
            self.apply_btn.setToolTip(
                "Baseline is already active in the worksheet. Select an alternative rewrite candidate above to apply."
            )

    def _on_variant_selected(self) -> None:
        selected_items = self.variant_table.selectedItems()
        if not selected_items:
            return

        row = self.variant_table.currentRow()
        if 0 <= row < len(self.variants):
            self.selected_variant = self.variants[row]
            self.selected_editor.setPlainText(self.selected_variant.sql)

            is_proc = any(
                v.plan_summary in ("PL/SQL Block", "Procedural Block", "Procedural Execution")
                for v in self.variants
            )

            if len(self.variants) <= 1:
                title = "PL/SQL Block" if "oracle" in (self.dialect or "").lower() and is_proc else "Query"
                self.selected_tab_title.setText(f"{title} Definition")
                if hasattr(self, "selected_tab_strategy"):
                    self.selected_tab_strategy.setText(self.selected_variant.strategy or "")
                self.sql_tabs.setTabText(0, "Query")
                self.sql_tabs.setTabVisible(1, False)
            else:
                self.selected_tab_title.setText(f"{self.selected_variant.label} Query")
                if hasattr(self, "selected_tab_strategy"):
                    self.selected_tab_strategy.setText(f"Strategy: {self.selected_variant.strategy}")
                self.sql_tabs.setTabText(0, "Selected Candidate")
                self.sql_tabs.setTabVisible(1, True)

            # Update Plan Diff Tree
            baseline_v = next((v for v in self.variants if v.id == 0), None)
            base_plan = getattr(baseline_v, "plan_root", None) if baseline_v else None
            cand_plan = getattr(self.selected_variant, "plan_root", None)
            if hasattr(self, "plan_diff_widget"):
                self.plan_diff_widget.set_plans(
                    base_plan,
                    cand_plan,
                    "Baseline Plan",
                    f"{self.selected_variant.label} Plan",
                )

            self._update_apply_button_state()
            base_plan = getattr(baseline_v, "plan_root", None) if baseline_v else None
            cand_plan = getattr(self.selected_variant, "plan_root", None)
            if hasattr(self, "plan_diff_widget"):
                self.plan_diff_widget.set_plans(
                    base_plan,
                    cand_plan,
                    "Baseline Plan",
                    f"{self.selected_variant.label} Plan",
                )

    def _on_tuning_depth_changed(self, index: int) -> None:
        depth = "deep" if index == 1 else "standard"
        self.variants = generate_query_variants(self.original_sql, dialect=self.dialect, depth=depth)
        evaluate_variant_costs(self.variants, conn_data=None)
        self._populate_variants_table()
        self._update_kpi_strip()
        self._select_initial_variant()
        self._start_live_cost_evaluation()

    def _start_live_cost_evaluation(self) -> None:
        if not self.conn_data or not self.conn_data.get("host"):
            return

        worker = OptimizerCostWorker(self.variants, self.conn_data)
        worker.signals.finished.connect(self._on_costs_evaluated)
        QThreadPool.globalInstance().start(worker)

    def _on_costs_evaluated(self, evaluated_variants: List[QueryVariant]) -> None:
        self.variants = evaluated_variants
        self._populate_variants_table()
        self._update_kpi_strip()
        self._select_initial_variant()

    def _run_benchmark(self) -> None:
        self.benchmark_btn.setEnabled(False)
        self.benchmark_btn.setText("Benchmarking...")

        for v in self.variants:
            v.benchmark_status = "running"
        self._populate_variants_table()

        worker = BenchmarkWorker(self.variants, self.conn_data, timeout_sec=3.0)
        worker.signals.finished.connect(self._on_benchmark_finished)
        worker.signals.error.connect(self._on_benchmark_error)
        QThreadPool.globalInstance().start(worker)

    def _on_benchmark_finished(self, benchmarked_variants: List[QueryVariant]) -> None:
        self.variants = benchmarked_variants
        self._populate_variants_table()
        self._update_kpi_strip()
        self.benchmark_btn.setText("Re-run Benchmark")
        self.benchmark_btn.setEnabled(True)

    def _on_benchmark_error(self, err: str) -> None:
        self.benchmark_btn.setText("Benchmark Failed")
        self.benchmark_btn.setEnabled(True)

    def _simulate_virtual_index(self, ddl: str) -> None:
        if not hasattr(self, "sim_btn"):
            return
        self.sim_btn.setEnabled(False)
        self.sim_btn.setText("Simulating...")

        worker = VirtualIndexWorker(ddl, self.original_sql, self.conn_data)
        worker.signals.finished.connect(self._on_virtual_index_finished)
        worker.signals.error.connect(self._on_virtual_index_error)
        QThreadPool.globalInstance().start(worker)

    def _on_virtual_index_finished(self, res: VirtualIndexResult) -> None:
        self.sim_btn.setEnabled(True)
        self.sim_btn.setText("Re-simulate")

        self.sim_result_frame.setProperty("picked", "true" if res.is_picked else "false")
        self.sim_status_lbl.setProperty("picked", "true" if res.is_picked else "false")

        if res.is_picked:
            self.sim_status_lbl.setText("✓ OPTIMIZER SELECTED INDEX")
            self.sim_status_lbl.setStyleSheet("color: #166534; font-weight: 700;")
            self.sim_result_frame.setStyleSheet(
                "background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 8px 10px; margin-top: 6px;"
            )
        else:
            self.sim_status_lbl.setText("OPTIMIZER PREFERRED EXISTING SCAN")
            self.sim_status_lbl.setStyleSheet("color: #475569; font-weight: 700;")
            self.sim_result_frame.setStyleSheet(
                "background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 4px; padding: 8px 10px; margin-top: 6px;"
            )

        self.sim_metric_lbl.setText(
            f"Plan: {res.baseline_plan_node} → {res.simulated_plan_node} | Cost: {res.baseline_cost:.1f} → {res.simulated_cost:.1f} (-{res.cost_reduction_pct}%)"
        )
        self.sim_detail_lbl.setText(f"{res.engine_method} • {res.details}")

        self.sim_result_frame.show()

    def _on_virtual_index_error(self, err: str) -> None:
        self.sim_btn.setEnabled(True)
        self.sim_btn.setText("Simulate Index")

    @property
    def opt_editor(self) -> QTextEdit:
        """Backward-compatibility property for query editor."""
        return self.selected_editor

    def _copy_original_sql(self) -> None:
        QApplication.clipboard().setText(self.original_sql)

    def _copy_selected_sql(self) -> None:
        text = self.selected_editor.toPlainText()
        QApplication.clipboard().setText(text)

    def _apply_sql(self) -> None:
        if self.on_apply:
            target_sql = (
                self.selected_editor.toPlainText()
                if self.selected_variant
                else self.original_sql
            )
            self.on_apply(target_sql)
        self.accept()
