"""widgets/worksheet/plan_diff_view.py

Visual Unified Execution Plan Diff & Inspection widget.
Renders a full-width unified hierarchical execution plan tree comparing
baseline vs candidate queries with inline transitions and zero horizontal scroll.
"""

from typing import List, Optional

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from db.optimizer.plan_models import PlanNode


class PlanDiffWidget(QWidget):
    """Full-width Unified Visual Execution Plan Diff and Explorer."""

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
            "background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 4px; padding: 6px 10px;"
        )
        s_layout = QHBoxLayout(self.summary_bar)
        s_layout.setContentsMargins(6, 4, 6, 4)

        self.summary_lbl = QLabel("Select a candidate to view execution plan transition", self.summary_bar)
        self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #334155;")
        s_layout.addWidget(self.summary_lbl)
        layout.addWidget(self.summary_bar)

        # Unified Plan Tree Widget
        self.plan_tree = QTreeWidget(self)
        self.plan_tree.setObjectName("unifiedPlanTree")
        self.plan_tree.setColumnCount(4)
        self.plan_tree.setHeaderLabels([
            "Execution Operation", "Cost", "Target Object", "Access Path / Predicate"
        ])
        self.plan_tree.setAlternatingRowColors(True)
        self.plan_tree.setRootIsDecorated(True)
        self.plan_tree.setAnimated(True)
        self.plan_tree.setStyleSheet(
            "QTreeWidget { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 3px; font-size: 8.5pt; } "
            "QTreeWidget::item { padding: 4px 6px; border-bottom: 1px solid #F1F5F9; } "
            "QHeaderView::section { background-color: #F1F5F9; color: #475569; font-weight: 600; font-size: 8pt; padding: 5px 6px; border: none; border-bottom: 1px solid #CBD5E1; border-right: 1px solid #E2E8F0; }"
        )

        header = self.plan_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.plan_tree.setColumnWidth(0, 240)
        self.plan_tree.setColumnWidth(1, 135)
        self.plan_tree.setColumnWidth(2, 85)

        layout.addWidget(self.plan_tree, 1)

    @property
    def base_tree(self) -> QTreeWidget:
        """Backward-compatibility accessor returning the unified plan tree."""
        return self.plan_tree

    @property
    def cand_tree(self) -> QTreeWidget:
        """Backward-compatibility accessor returning the unified plan tree."""
        return self.plan_tree

    def set_plans(
        self,
        base_node: Optional[PlanNode],
        cand_node: Optional[PlanNode],
        base_label: str = "Baseline",
        cand_label: str = "Candidate",
        is_baseline: bool = False,
    ) -> None:
        """Populates the unified execution plan tree and comparative transition summary."""
        self.plan_tree.clear()

        if not base_node and not cand_node:
            self.summary_lbl.setText("No comparative execution plan data available.")
            self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #64748B;")
            return

        active_base = base_node or cand_node
        is_proc = (
            "procedural" in active_base.node_type.lower()
            or "pl/sql" in active_base.node_type.lower()
            or active_base.condition == "Procedural block execution"
        )

        if is_proc:
            self.summary_lbl.setText("Procedural Execution: Block executed directly by database server runtime")
            self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #475569;")
            self._set_tree_headers(["Execution Operation", "Cost", "Target Object", "Execution Detail"])
            self.plan_tree.setColumnWidth(1, 75)
            self._populate_single_node(self.plan_tree.invisibleRootItem(), active_base)
            self.plan_tree.expandAll()
            return

        # Scenario 1: User selected Baseline (Explorer Mode)
        if is_baseline or cand_node is None or base_node == cand_node:
            self.summary_lbl.setText(
                f"Baseline Query Execution Plan | Total Cost: {active_base.cost:.1f} | Primary Operator: {active_base.node_type}"
            )
            self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #334155;")
            self._set_tree_headers(["Execution Operation", "Cost", "Target Object", "Access Path / Predicate"])
            self.plan_tree.setColumnWidth(1, 75)
            self._populate_single_node(self.plan_tree.invisibleRootItem(), active_base)
            self.plan_tree.expandAll()
            return

        # Scenario 2: Candidate selected - check if identical to baseline
        if self._is_identical_plan(base_node, cand_node):
            self.summary_lbl.setText(
                f"Equivalent Execution Plan | Total Cost: {base_node.cost:.1f} (Optimizer generated identical plan structure)"
            )
            self.summary_lbl.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #334155;")
            self._set_tree_headers(["Execution Operation", "Cost", "Target Object", "Access Path / Predicate"])
            self.plan_tree.setColumnWidth(1, 75)
            self._populate_single_node(self.plan_tree.invisibleRootItem(), base_node)
            self.plan_tree.expandAll()
            return

        # Scenario 3: Candidate selected with structural or cost diff
        diff_pct = (
            round(((cand_node.cost - base_node.cost) / base_node.cost) * 100.0, 1)
            if base_node.cost > 0
            else 0.0
        )
        if diff_pct < 0:
            pct_str = f"(-{abs(diff_pct):.1f}% Cost Reduction)"
            color_hex = "#166534"
        elif diff_pct > 0:
            pct_str = f"(+{diff_pct:.1f}% Cost Increase)"
            color_hex = "#92400E"
        else:
            pct_str = "(0.0% change)"
            color_hex = "#334155"

        self.summary_lbl.setText(
            f"Transition: {base_node.node_type} → {cand_node.node_type} | "
            f"Total Cost: {base_node.cost:.1f} → {cand_node.cost:.1f} {pct_str}"
        )
        self.summary_lbl.setStyleSheet(f"font-weight: 600; font-size: 8.5pt; color: {color_hex};")

        self._set_tree_headers([
            "Execution Operation", "Cost (Base → Cand)", "Target Object", "Access Path / Predicate"
        ])
        self.plan_tree.setColumnWidth(1, 140)
        self._populate_diff_tree(base_node, cand_node)
        self.plan_tree.expandAll()

    def _set_tree_headers(self, headers: List[str]) -> None:
        self.plan_tree.setHeaderLabels(headers)

    def _populate_single_node(self, parent_item, node: PlanNode) -> None:
        cost_text = f"{node.cost:.1f}" if node.cost else "-"
        detail_text = node.condition or (f"Rows: {node.rows}" if node.rows else "")
        icon = self._get_node_icon(node.node_type, is_bottleneck=node.is_bottleneck)

        item = QTreeWidgetItem(parent_item, [node.node_type, cost_text, node.relation, detail_text])
        item.setIcon(0, icon)

        if node.is_bottleneck or ("scan" in node.node_type.lower() and "index" not in node.node_type.lower()):
            item.setBackground(0, QColor("#FFFBEB"))
            item.setBackground(1, QColor("#FFFBEB"))
            item.setForeground(0, QColor("#92400E"))
            item.setForeground(1, QColor("#92400E"))
        elif "index" in node.node_type.lower() or node.is_optimized:
            item.setBackground(0, QColor("#F0FDF4"))
            item.setBackground(1, QColor("#F0FDF4"))
            item.setForeground(0, QColor("#166534"))
            item.setForeground(1, QColor("#166534"))

        for child in node.children:
            self._populate_single_node(item, child)

    def _populate_diff_tree(self, base_node: PlanNode, cand_node: PlanNode) -> None:
        root_item = self._create_diff_item(self.plan_tree.invisibleRootItem(), base_node, cand_node)
        root_item.setFont(0, QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self._diff_children(root_item, base_node.children, cand_node.children)

    def _diff_children(self, parent_item, b_nodes: List[PlanNode], c_nodes: List[PlanNode]) -> None:
        used_b = set()
        used_c = set()
        pairs = []

        # 1. Match by target relation
        for bi, b in enumerate(b_nodes):
            if b.relation:
                for ci, c in enumerate(c_nodes):
                    if ci not in used_c and c.relation and c.relation.lower() == b.relation.lower():
                        pairs.append((b, c))
                        used_b.add(bi)
                        used_c.add(ci)
                        break

        # 2. Match remaining unmatched children by index
        rem_b = [b for idx, b in enumerate(b_nodes) if idx not in used_b]
        rem_c = [c for idx, c in enumerate(c_nodes) if idx not in used_c]
        for i in range(max(len(rem_b), len(rem_c))):
            b = rem_b[i] if i < len(rem_b) else None
            c = rem_c[i] if i < len(rem_c) else None
            pairs.append((b, c))

        for b, c in pairs:
            item = self._create_diff_item(parent_item, b, c)
            b_children = b.children if b else []
            c_children = c.children if c else []
            if b_children or c_children:
                self._diff_children(item, b_children, c_children)

    def _create_diff_item(self, parent_item, b: Optional[PlanNode], c: Optional[PlanNode]) -> QTreeWidgetItem:
        if b and c:
            if b.node_type == c.node_type and b.relation == c.relation:
                op_text = b.node_type
                if abs(b.cost - c.cost) > 0.05:
                    pct = round(((b.cost - c.cost) / b.cost) * 100.0, 1) if b.cost else 0
                    cost_text = f"{b.cost:.1f} → {c.cost:.1f} (-{pct}%)"
                    status = "optimized" if c.cost < b.cost else "neutral"
                else:
                    cost_text = f"{b.cost:.1f}"
                    status = "bottleneck" if b.is_bottleneck else "neutral"
            else:
                op_text = f"{b.node_type} → {c.node_type}"
                if abs(b.cost - c.cost) > 0.05:
                    pct = round(((b.cost - c.cost) / b.cost) * 100.0, 1) if b.cost else 0
                    cost_text = f"{b.cost:.1f} → {c.cost:.1f} (-{pct}%)"
                else:
                    cost_text = f"{c.cost:.1f}"
                status = "optimized" if (c.cost < b.cost or "index" in c.node_type.lower()) else "neutral"

            rel_text = c.relation or b.relation
            cond_text = c.condition or b.condition
            icon = self._get_node_icon(
                c.node_type if status == "optimized" else b.node_type,
                is_bottleneck=(status == "bottleneck"),
            )

        elif b and not c:
            op_text = f"{b.node_type} (Eliminated)"
            cost_text = f"{b.cost:.1f} → 0.0 (-100%)"
            rel_text = b.relation
            cond_text = b.condition
            status = "optimized"
            icon = qta.icon("fa5s.check", color="#16A34A")

        else:
            active = c  # type: ignore[assignment]
            op_text = f"{active.node_type} (Adopted)"
            cost_text = f"+{active.cost:.1f}"
            rel_text = active.relation
            cond_text = active.condition
            status = "optimized" if "index" in active.node_type.lower() else "neutral"
            icon = self._get_node_icon(active.node_type, is_bottleneck=active.is_bottleneck)

        item = QTreeWidgetItem(parent_item, [op_text, cost_text, rel_text, cond_text])
        item.setIcon(0, icon)

        if status == "optimized":
            item.setBackground(0, QColor("#F0FDF4"))
            item.setBackground(1, QColor("#F0FDF4"))
            item.setForeground(0, QColor("#166534"))
            item.setForeground(1, QColor("#166534"))
        elif status == "bottleneck":
            item.setBackground(0, QColor("#FFFBEB"))
            item.setBackground(1, QColor("#FFFBEB"))
            item.setForeground(0, QColor("#92400E"))
            item.setForeground(1, QColor("#92400E"))

        return item

    def _get_node_icon(self, node_type: str, is_bottleneck: bool = False):
        lower = (node_type or "").lower()
        if "procedural" in lower or "pl/sql" in lower:
            return qta.icon("fa5s.cogs", color="#2563EB")
        if "index" in lower:
            return qta.icon("fa5s.bolt", color="#16A34A")
        if "scan" in lower or is_bottleneck:
            return qta.icon("fa5s.exclamation-triangle", color="#D97706")
        if "join" in lower:
            return qta.icon("fa5s.link", color="#2563EB")
        return qta.icon("fa5s.layer-group", color="#64748B")

    def _is_identical_plan(self, a: Optional[PlanNode], b: Optional[PlanNode]) -> bool:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        if a.node_type != b.node_type or a.relation != b.relation or abs(a.cost - b.cost) > 0.05:
            return False
        if len(a.children) != len(b.children):
            return False
        return all(self._is_identical_plan(ac, bc) for ac, bc in zip(a.children, b.children))
