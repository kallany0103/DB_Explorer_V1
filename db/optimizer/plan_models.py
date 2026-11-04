"""db/optimizer/plan_models.py

Execution plan tree representation and parsers for PostgreSQL and Oracle plans.
Converts heterogeneous engine plans into a unified hierarchical structure for diffing.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional


@dataclass
class PlanNode:
    """Represents a unified node in a query execution plan tree."""

    node_type: str
    relation: str = ""
    cost: float = 0.0
    rows: int = 0
    actual_time_ms: Optional[float] = None
    condition: str = ""
    is_bottleneck: bool = False
    is_optimized: bool = False
    children: List["PlanNode"] = field(default_factory=list)


def parse_postgres_plan(plan_data: Any) -> Optional[PlanNode]:
    """Parses PostgreSQL EXPLAIN JSON output into a PlanNode hierarchy."""
    if not plan_data:
        return None

    if isinstance(plan_data, str):
        try:
            plan_data = json.loads(plan_data)
        except Exception:
            return None

    root_dict = None
    if isinstance(plan_data, list) and plan_data:
        root_dict = plan_data[0].get("Plan", plan_data[0])
    elif isinstance(plan_data, dict):
        root_dict = plan_data.get("Plan", plan_data)

    if not root_dict or not isinstance(root_dict, dict):
        return None

    return _build_postgres_node(root_dict)


def _build_postgres_node(d: Dict[str, Any]) -> PlanNode:
    node_type = d.get("Node Type", "Scan")
    rel_name = d.get("Relation Name") or d.get("Index Name") or ""
    cost = float(d.get("Total Cost", 0.0))
    rows = int(d.get("Plan Rows", 0))

    exec_time = d.get("Actual Total Time")
    actual_time_ms = float(exec_time) if exec_time is not None else None

    # Extract conditions
    cond = (
        d.get("Index Cond")
        or d.get("Filter")
        or d.get("Hash Cond")
        or d.get("Join Filter")
        or ""
    )

    is_bottleneck = "seq scan" in node_type.lower()
    is_optimized = "index" in node_type.lower()

    node = PlanNode(
        node_type=node_type,
        relation=rel_name,
        cost=cost,
        rows=rows,
        actual_time_ms=actual_time_ms,
        condition=str(cond),
        is_bottleneck=is_bottleneck,
        is_optimized=is_optimized,
    )

    for child_dict in d.get("Plans", []):
        if isinstance(child_dict, dict):
            node.children.append(_build_postgres_node(child_dict))

    return node


def parse_oracle_plan_rows(rows: List[tuple]) -> Optional[PlanNode]:
    """Reconstructs Oracle hierarchical plan tree from PLAN_TABLE rows.

    Expected row tuple: (id, parent_id, operation, options, object_name, cost, cardinality)
    """
    if not rows:
        return None

    nodes_by_id: Dict[int, PlanNode] = {}
    parent_map: Dict[int, Optional[int]] = {}
    root_id = None

    for r in rows:
        node_id = int(r[0])
        parent_id = int(r[1]) if r[1] is not None and r[1] != "" else None
        op = f"{r[2] or ''} {r[3] or ''}".strip()
        obj = str(r[4] or "")
        cost = float(r[5]) if len(r) > 5 and r[5] is not None else 0.0
        rows_est = int(r[6]) if len(r) > 6 and r[6] is not None else 0

        access_pred = str(r[7]).strip() if len(r) > 7 and r[7] else ""
        filter_pred = str(r[8]).strip() if len(r) > 8 and r[8] else ""

        cond_parts = []
        if access_pred:
            cond_parts.append(f"Access: {access_pred}")
        if filter_pred:
            cond_parts.append(f"Filter: {filter_pred}")
        if rows_est:
            cond_parts.append(f"Est. Rows: {rows_est:,}")

        condition = " • ".join(cond_parts) if cond_parts else ""

        is_bottleneck = "full" in op.lower()
        is_optimized = "index" in op.lower()

        pnode = PlanNode(
            node_type=op or "Operation",
            relation=obj,
            cost=cost,
            rows=rows_est,
            condition=condition,
            is_bottleneck=is_bottleneck,
            is_optimized=is_optimized,
        )
        nodes_by_id[node_id] = pnode
        parent_map[node_id] = parent_id

        if parent_id is None and root_id is None:
            root_id = node_id

    # Assemble hierarchy
    for node_id, p_id in parent_map.items():
        if p_id is not None and p_id in nodes_by_id and node_id in nodes_by_id:
            nodes_by_id[p_id].children.append(nodes_by_id[node_id])

    return nodes_by_id.get(root_id or 0)


def create_synthetic_plan(variant_id: int, label: str, cost: float, plan_summary: str) -> PlanNode:
    """Constructs a deterministic plan hierarchy for offline/simulated analysis."""
    if "procedural" in label.lower() or "procedural" in plan_summary.lower() or "pl/sql" in plan_summary.lower():
        return PlanNode(
            node_type=plan_summary or "PL/SQL Execution",
            relation="",
            cost=0.0,
            rows=1,
            condition="Procedural block execution",
            is_bottleneck=False,
            is_optimized=False,
        )

    if variant_id == 0:
        # Baseline plan with sequential scan bottleneck
        root = PlanNode(
            node_type="Seq Scan",
            relation="orders",
            cost=cost or 1000.0,
            rows=10000,
            condition="Filter: YEAR(order_date) = 2024",
            is_bottleneck=True,
            is_optimized=False,
        )
        sub = PlanNode(
            node_type="SubPlan",
            relation="customers",
            cost=round((cost or 1000.0) * 0.4, 1),
            rows=150,
            condition="Filter: status = 'active'",
            is_bottleneck=True,
        )
        root.children.append(sub)
        return root

    # Rewritten plan
    lower = label.lower()
    if "sargable" in lower:
        root = PlanNode(
            node_type="Index Range Scan",
            relation="idx_orders_order_date",
            cost=cost or 150.0,
            rows=120,
            condition="Index Cond: (order_date >= '2024-01-01' AND order_date < '2025-01-01')",
            is_bottleneck=False,
            is_optimized=True,
        )
        sub = PlanNode(
            node_type="SubPlan (Hash Join)",
            relation="customers",
            cost=round((cost or 150.0) * 0.3, 1),
            rows=150,
            condition="Hash Cond: (orders.customer_id = customers.id)",
            is_optimized=True,
        )
        root.children.append(sub)
        return root
    elif "join" in lower:
        root = PlanNode(
            node_type="Hash Join",
            relation="orders ⨝ customers",
            cost=cost or 250.0,
            rows=150,
            condition="Hash Cond: (orders.customer_id = customers.id)",
            is_optimized=True,
        )
        root.children.append(
            PlanNode(
                node_type="Index Scan",
                relation="idx_customers_status",
                cost=50.0,
                rows=150,
                condition="Index Cond: (status = 'active')",
                is_optimized=True,
            )
        )
        root.children.append(
            PlanNode(
                node_type="Seq Scan",
                relation="orders",
                cost=180.0,
                rows=1200,
                condition="Filter: YEAR(order_date) = 2024",
            )
        )
        return root
    else:
        root = PlanNode(
            node_type="Index Scan",
            relation="orders",
            cost=cost or 350.0,
            rows=150,
            condition="Index Cond: ...",
            is_optimized=True,
        )
        return root

