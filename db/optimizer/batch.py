"""db/optimizer/batch.py

Batch Workload SQL Optimizer.
Analyzes multiple SQL statements across a worksheet or .sql script file,
evaluates performance bottlenecks, and generates prioritized workload tuning reports.
"""

from dataclasses import dataclass, field
import logging
from typing import List, Optional, Tuple

import sqlparse

from db.optimizer.cost_evaluator import evaluate_variant_costs
from db.optimizer.engine import OptimizationResult, analyze_query
from db.optimizer.variants import QueryVariant, generate_query_variants

logger = logging.getLogger(__name__)


@dataclass
class BatchItemResult:
    """Tuning assessment for a single statement in a batch workload."""

    statement_index: int
    sql: str
    start_line: int
    findings_count: int
    high_severity_count: int
    top_finding: str
    baseline_cost: float
    optimized_cost: float
    cost_reduction_pct: float
    has_rewrite: bool
    best_rewrite_sql: str
    status: str  # "Needs Tuning" or "Optimal"
    analysis_result: OptimizationResult
    variants: List[QueryVariant] = field(default_factory=list)


@dataclass
class BatchOptimizationSummary:
    """Workload-wide summary of batch optimization assessment."""

    total_statements: int
    statements_needing_tuning: int
    total_cost_baseline: float
    total_cost_optimized: float
    total_savings_pct: float
    items: List[BatchItemResult]
    full_optimized_script: str


def split_script_statements(script_text: str) -> List[Tuple[int, str]]:
    """Splits a multi-statement SQL script into individual statements with line numbers."""
    if not script_text or not script_text.strip():
        return []

    statements: List[Tuple[int, str]] = []
    raw_stmts = sqlparse.split(script_text)
    current_char = 0

    for s in raw_stmts:
        clean = s.strip()
        if not clean:
            continue
        pos = script_text.find(s, current_char)
        if pos != -1:
            line_no = script_text[:pos].count("\n") + 1
            current_char = pos + len(s)
        else:
            line_no = 1
        statements.append((line_no, clean))

    return statements


def analyze_batch_workload(
    script_text: str,
    dialect: str = "postgres",
    conn_data: Optional[dict] = None,
) -> BatchOptimizationSummary:
    """Analyzes all statements in a workload script and generates a prioritized report."""
    raw_statements = split_script_statements(script_text)
    if not raw_statements:
        return BatchOptimizationSummary(
            total_statements=0,
            statements_needing_tuning=0,
            total_cost_baseline=0.0,
            total_cost_optimized=0.0,
            total_savings_pct=0.0,
            items=[],
            full_optimized_script=script_text or "",
        )

    items: List[BatchItemResult] = []
    total_base_cost = 0.0
    total_opt_cost = 0.0
    replacements: List[Tuple[str, str]] = []

    for idx, (line_no, stmt_sql) in enumerate(raw_statements, start=1):
        clean_stmt = stmt_sql.strip()

        # Run AST analysis & anti-pattern detection
        analysis = analyze_query(clean_stmt, dialect=dialect)

        # Generate competing candidate rewrites
        variants = generate_query_variants(clean_stmt, dialect=dialect)
        evaluate_variant_costs(variants, conn_data=conn_data)

        # Identify baseline and best variant
        baseline_v = next((v for v in variants if v.id == 0), None)
        best_v = next((v for v in variants if v.is_best), baseline_v)

        base_cost = baseline_v.cost if baseline_v and baseline_v.cost is not None else 1000.0
        opt_cost = best_v.cost if best_v and best_v.cost is not None else base_cost

        cost_reduction = (
            round(((base_cost - opt_cost) / base_cost) * 100.0, 1)
            if base_cost > 0 and opt_cost < base_cost
            else 0.0
        )

        has_rewrite = best_v is not None and best_v.id != 0
        best_sql = best_v.sql if has_rewrite and best_v else clean_stmt

        high_count = sum(1 for f in analysis.findings if f.severity == "HIGH")
        findings_count = len(analysis.findings)

        top_finding = (
            analysis.findings[0].title
            if analysis.findings
            else ("Optimal Structure" if not has_rewrite else "Rewrite Available")
        )

        status = "Needs Tuning" if (findings_count > 0 or has_rewrite) else "Optimal"

        total_base_cost += base_cost
        total_opt_cost += opt_cost

        if has_rewrite:
            replacements.append((stmt_sql, best_sql))

        items.append(
            BatchItemResult(
                statement_index=idx,
                sql=clean_stmt,
                start_line=line_no,
                findings_count=findings_count,
                high_severity_count=high_count,
                top_finding=top_finding,
                baseline_cost=base_cost,
                optimized_cost=opt_cost,
                cost_reduction_pct=cost_reduction,
                has_rewrite=has_rewrite,
                best_rewrite_sql=best_sql,
                status=status,
                analysis_result=analysis,
                variants=variants,
            )
        )

    # Sort statements: Statements with highest cost reduction & issues first (Toad Priority Ranking)
    sorted_items = sorted(
        items,
        key=lambda x: (
            0 if x.status == "Needs Tuning" else 1,
            -x.cost_reduction_pct,
            -x.high_severity_count,
            -x.findings_count,
            x.statement_index,
        ),
    )

    statements_needing_tuning = sum(1 for it in items if it.status == "Needs Tuning")
    total_savings_pct = (
        round(((total_base_cost - total_opt_cost) / total_base_cost) * 100.0, 1)
        if total_base_cost > 0 and total_opt_cost < total_base_cost
        else 0.0
    )

    # Construct full optimized script replacing rewritten statements
    optimized_script = script_text
    for orig, repl in replacements:
        # Append semicolon if original had one
        if orig.rstrip().endswith(";") and not repl.rstrip().endswith(";"):
            repl = repl + ";"
        optimized_script = optimized_script.replace(orig, repl, 1)

    return BatchOptimizationSummary(
        total_statements=len(items),
        statements_needing_tuning=statements_needing_tuning,
        total_cost_baseline=round(total_base_cost, 1),
        total_cost_optimized=round(total_opt_cost, 1),
        total_savings_pct=total_savings_pct,
        items=sorted_items,
        full_optimized_script=optimized_script,
    )

