"""widgets/worksheet/plan_diff_view.py

Visual Execution Plan Diff & Tree comparison widget.
Renders side-by-side hierarchical execution plan trees comparing baseline vs candidate queries.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from db.optimizer.plan_models import PlanNode


class PlanDiffWidget(QWidget):
    """Side-by-side visual execution plan comparison tree."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Comparison summary bar
        self.summary_bar = QFrame(self)
        self.summary_bar.setObjectName("planSummaryBar")
        self.summary_bar.setStyleSheet(
            "background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 4px; padding: 4px 8px;"
        )
        s_layout = QHBoxLayout(self.summary_bar)
        s_layout.setContentsMargins(6, 2, 6, 2)

        self.summary_lbl = QLabel("Select a candidate to view execution plan transition", self.summary_bar)
        self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8pt; color: #334155;")
        s_layout.addWidget(self.summary_lbl)
        layout.addWidget(self.summary_bar)

        # Splitter with 2 Trees: Baseline vs Candidate
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(4)

        # Left: Baseline Tree
        left_box = QWidget(splitter)
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self.base_hdr_lbl = QLabel("Baseline Execution Plan", left_box)
        self.base_hdr_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 8.5pt;")
        self.base_tree = self._create_plan_tree(left_box)
        left_layout.addWidget(self.base_hdr_lbl)
        left_layout.addWidget(self.base_tree)

        # Right: Candidate Tree
        right_box = QWidget(splitter)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        self.cand_hdr_lbl = QLabel("Candidate Execution Plan", right_box)
        self.cand_hdr_lbl.setStyleSheet("font-weight: 600; color: #166534; font-size: 8.5pt;")
        self.cand_tree = self._create_plan_tree(right_box)
        right_layout.addWidget(self.cand_hdr_lbl)
        right_layout.addWidget(self.cand_tree)

        splitter.setSizes([320, 320])
        layout.addWidget(splitter, 1)

    def _create_plan_tree(self, parent: QWidget) -> QTreeWidget:
        tree = QTreeWidget(parent)
        tree.setColumnCount(3)
        tree.setHeaderLabels(["Operation", "Cost", "Condition / Detail"])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(True)
        tree.setAnimated(True)
        tree.setStyleSheet(
            "QTreeWidget { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 3px; font-size: 8pt; } "
            "QTreeWidget::item { padding: 3px 4px; border-bottom: 1px solid #F1F5F9; } "
            "QHeaderView::section { background-color: #F1F5F9; color: #475569; font-weight: 600; font-size: 7.5pt; padding: 4px; border: none; border-bottom: 1px solid #CBD5E1; }"
        )

        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return tree

    def set_plans(
        self,
        base_node: Optional[PlanNode],
        cand_node: Optional[PlanNode],
        base_label: str = "Baseline",
        cand_label: str = "Candidate",
    ) -> None:
        """Populates both execution plan trees and updates the comparative summary."""
        self.base_tree.clear()
        self.cand_tree.clear()

        if base_node:
            self.base_hdr_lbl.setText(f"{base_label} (Cost: {base_node.cost:.1f})")
            self._populate_node(self.base_tree.invisibleRootItem(), base_node, is_candidate=False)
            self.base_tree.expandAll()
        else:
            self.base_hdr_lbl.setText(f"{base_label} (No plan data)")

        if cand_node:
            cost_str = f"Cost: {cand_node.cost:.1f}"
            reduction_str = ""
            if base_node and base_node.cost > 0 and cand_node.cost < base_node.cost:
                pct = round(((base_node.cost - cand_node.cost) / base_node.cost) * 100.0, 1)
                reduction_str = f" (-{pct}%)"
            self.cand_hdr_lbl.setText(f"{cand_label} ({cost_str}{reduction_str})")
            self._populate_node(self.cand_tree.invisibleRootItem(), cand_node, is_candidate=True)
            self.cand_tree.expandAll()
        else:
            self.cand_hdr_lbl.setText(f"{cand_label} (No plan data)")

        # Summary text
        if base_node and cand_node:
            if (
                "procedural" in base_node.node_type.lower()
                or "pl/sql" in base_node.node_type.lower()
                or base_node.condition == "Procedural block execution"
            ):
                self.summary_lbl.setText("Procedural Execution: Block executed directly by database server runtime")
                self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8pt; color: #475569;")
            else:
                diff_pct = (
                    round(((cand_node.cost - base_node.cost) / base_node.cost) * 100.0, 1)
                    if base_node.cost > 0
                    else 0.0
                )
                color_hex = "#166534" if diff_pct < 0 else "#475569"
                self.summary_lbl.setText(
                    f"Transition: {base_node.node_type} → {cand_node.node_type} | Total Cost: {base_node.cost:.1f} → {cand_node.cost:.1f} ({diff_pct}%)"
                )
                self.summary_lbl.setStyleSheet(f"font-weight: 600; font-size: 8pt; color: {color_hex};")
        else:
            self.summary_lbl.setText("No comparative execution plan data available.")

    def _populate_node(self, parent_item, node: PlanNode, is_candidate: bool) -> None:
        target_str = f" on {node.relation}" if node.relation else ""
        item_text = f"{node.node_type}{target_str}"
        cost_text = f"{node.cost:.1f}" if node.cost else "-"
        detail_text = node.condition or (f"Rows: {node.rows}" if node.rows else "")

        item = QTreeWidgetItem(parent_item, [item_text, cost_text, detail_text])

        # Node icon and badge color
        lower_type = node.node_type.lower()
        if "procedural" in lower_type or "pl/sql" in lower_type:
            item.setIcon(0, qta.icon("fa5s.cogs", color="#2563EB"))
        elif "index" in lower_type:
            item.setIcon(0, qta.icon("fa5s.bolt", color="#16A34A"))
            if is_candidate:
                item.setBackground(0, QColor("#F0FDF4"))
                item.setBackground(1, QColor("#F0FDF4"))
        elif "scan" in lower_type or node.is_bottleneck:
            item.setIcon(0, qta.icon("fa5s.exclamation-triangle", color="#D97706"))
            if not is_candidate:
                item.setBackground(0, QColor("#FEF2F2"))
                item.setBackground(1, QColor("#FEF2F2"))
        elif "join" in lower_type:
            item.setIcon(0, qta.icon("fa5s.link", color="#2563EB"))
        else:
            item.setIcon(0, qta.icon("fa5s.layer-group", color="#64748B"))

        for child in node.children:
            self._populate_node(item, child, is_candidate=is_candidate)

