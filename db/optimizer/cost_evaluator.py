"""db/optimizer/cost_evaluator.py

Evaluates query plan costs and performance metrics for candidate SQL variants.
Supports live execution plan extraction via PostgreSQL EXPLAIN and Oracle PLAN_TABLE,
with robust offline fallback for standalone static analysis.
"""

import json
import logging
from typing import List, Optional
import uuid

from db.db_connections import get_pooled_oracle_connection, get_pooled_postgres_connection
from db.optimizer.plan_models import (
    create_synthetic_plan,
    parse_oracle_plan_rows,
    parse_postgres_plan,
)
from db.optimizer.variants import QueryVariant

logger = logging.getLogger(__name__)


def evaluate_variant_costs(
    variants: List[QueryVariant],
    conn_data: Optional[dict] = None,
) -> List[QueryVariant]:
    """Evaluates query execution plan cost for each variant.

    If conn_data is provided and reachable, executes database EXPLAIN commands.
    Otherwise, computes static relative estimations.
    """
    if not variants:
        return []

    db_type = (
        (conn_data.get("db_type") or conn_data.get("code") or "").lower()
        if conn_data
        else ""
    )

    # Handle procedural code without running synthetic table scans
    if any(v.plan_summary == "Procedural Execution" for v in variants):
        for v in variants:
            v.cost = None
            v.estimated_rows = None
            is_oracle = "oracle" in db_type or "pl/sql" in v.strategy.lower()
            v.plan_summary = "PL/SQL Block" if is_oracle else "Procedural Block"
            v.cost_change_pct = None
            v.is_best = False
            v.plan_root = create_synthetic_plan(0, "Procedural", 0.0, v.plan_summary)
        return variants

    evaluated = False
    if conn_data and ("postgres" in db_type or "pgsql" in db_type):
        evaluated = _evaluate_postgres_costs(variants, conn_data)
    elif conn_data and "oracle" in db_type:
        evaluated = _evaluate_oracle_costs(variants, conn_data)

    if not evaluated:
        _apply_heuristic_cost_estimates(variants)

    _calculate_cost_deltas_and_best(variants)
    return variants


def _evaluate_postgres_costs(variants: List[QueryVariant], conn_data: dict) -> bool:
    """Runs EXPLAIN (FORMAT JSON, COSTS) for each variant on PostgreSQL."""
    conn = None
    try:
        conn = get_pooled_postgres_connection(conn_data)
        if not conn:
            return False

        with conn.cursor() as cur:
            # Enforce 5s statement timeout for explain
            try:
                cur.execute("SET statement_timeout = 5000;")
            except Exception:
                pass

            for v in variants:
                try:
                    clean_sql = v.sql.rstrip(";").strip()
                    cur.execute(f"EXPLAIN (FORMAT JSON, COSTS) {clean_sql}")
                    row = cur.fetchone()
                    if row and row[0]:
                        raw_plan = row[0]
                        if isinstance(raw_plan, str):
                            raw_plan = json.loads(raw_plan)

                        plan_root = {}
                        if isinstance(raw_plan, list) and raw_plan:
                            plan_root = raw_plan[0].get("Plan", {})
                        elif isinstance(raw_plan, dict):
                            plan_root = raw_plan.get("Plan", raw_plan)

                        v.cost = float(plan_root.get("Total Cost", 0.0))
                        v.estimated_rows = int(plan_root.get("Plan Rows", 0))

                        node_type = plan_root.get("Node Type", "Scan")
                        rel_name = plan_root.get("Relation Name", "")
                        v.plan_summary = (
                            f"{node_type} on {rel_name}" if rel_name else node_type
                        )
                        v.plan_root = parse_postgres_plan(raw_plan)
                except Exception as ex:
                    logger.debug("Failed to explain variant %s: %s", v.label, ex)
                    if hasattr(conn, "rollback"):
                        conn.rollback()

        return True
    except Exception as e:
        logger.debug("PostgreSQL explain evaluation encountered an issue: %s", e)
        return False


def _evaluate_oracle_costs(variants: List[QueryVariant], conn_data: dict) -> bool:
    """Runs EXPLAIN PLAN FOR on Oracle and reads PLAN_TABLE costs."""
    conn = None
    try:
        conn = get_pooled_oracle_connection(conn_data=conn_data)
        if not conn:
            return False

        cursor = conn.cursor()
        for v in variants:
            stmt_id = f"usql_{uuid.uuid4().hex[:10]}"
            try:
                clean_sql = v.sql.rstrip(";").strip()
                cursor.execute(
                    f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {clean_sql}"
                )
                cursor.execute(
                    """
                    SELECT cost, cardinality, operation, options, object_name
                    FROM plan_table
                    WHERE statement_id = :1 AND id = 0
                    """,
                    [stmt_id],
                )
                row = cursor.fetchone()
                if row:
                    v.cost = float(row[0]) if row[0] is not None else None
                    v.estimated_rows = int(row[1]) if row[1] is not None else None
                    op = f"{row[2] or ''} {row[3] or ''}".strip()
                    obj = row[4] or ""
                    v.plan_summary = f"{op} on {obj}" if obj else op

                # Fetch full plan hierarchy for diff viewer
                try:
                    cursor.execute(
                        """
                        SELECT id, parent_id, operation, options, object_name, cost, cardinality,
                               access_predicates, filter_predicates
                        FROM plan_table
                        WHERE statement_id = :1
                        ORDER BY id
                        """,
                        [stmt_id],
                    )
                    all_rows = cursor.fetchall()
                    if all_rows:
                        v.plan_root = parse_oracle_plan_rows(all_rows)
                        if (not op or op == "SELECT STATEMENT") and len(all_rows) > 1:
                            child = next((r for r in all_rows if r[1] == 0), all_rows[1])
                            c_op = f"{child[2] or ''} {child[3] or ''}".strip()
                            c_obj = child[4] or ""
                            v.plan_summary = f"{c_op} on {c_obj}" if c_obj else c_op
                except Exception:
                    pass

                # Clean up statement from plan table
                cursor.execute(
                    "DELETE FROM plan_table WHERE statement_id = :1", [stmt_id]
                )
                conn.commit()
            except Exception as ex:
                logger.debug("Oracle explain error for variant %s: %s", v.label, ex)
                if hasattr(conn, "rollback"):
                    conn.rollback()

        cursor.close()
        return True
    except Exception as e:
        logger.debug("Oracle cost evaluation encountered an issue: %s", e)
        return False


def _apply_heuristic_cost_estimates(variants: List[QueryVariant]) -> None:
    """Generates structural baseline and relative estimates when offline."""
    base_cost = 1000.0
    for v in variants:
        if v.id == 0:
            v.cost = base_cost
            v.plan_summary = "Seq Scan / Unindexed"
        else:
            lower_label = v.label.lower()
            if "exists" in lower_label:
                v.cost = round(base_cost * 0.35, 1)
                v.plan_summary = "SubPlan / Semi-Join"
            elif "join" in lower_label:
                v.cost = round(base_cost * 0.25, 1)
                v.plan_summary = "Hash / Index Join"
            elif "sargable" in lower_label:
                v.cost = round(base_cost * 0.15, 1)
                v.plan_summary = "Index Range Scan"
            elif "distinct" in lower_label:
                v.cost = round(base_cost * 0.80, 1)
                v.plan_summary = "Stream Aggregate"
            else:
                v.cost = round(base_cost * 0.50, 1)
                v.plan_summary = "Optimized Scan"
        v.plan_root = create_synthetic_plan(v.id, v.label, v.cost, v.plan_summary)


def _calculate_cost_deltas_and_best(variants: List[QueryVariant]) -> None:
    """Computes cost change percentage vs baseline and flags the best variant."""
    if not variants:
        return

    baseline_cost = variants[0].cost

    # Calculate percentage change
    for v in variants:
        if v.cost is not None and baseline_cost is not None and baseline_cost > 0:
            pct = round(((v.cost - baseline_cost) / baseline_cost) * 100.0, 1)
            v.cost_change_pct = pct

    # Mark the best variant
    valid_costs = [v for v in variants if v.cost is not None]
    if valid_costs:
        best_v = min(valid_costs, key=lambda x: x.cost or float("inf"))
        for v in variants:
            v.is_best = v.id == best_v.id

