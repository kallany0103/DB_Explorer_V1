"""db/optimizer/variants.py

Multi-variant SQL query generator for performance benchmarking.
Generates competing query execution alternatives (Baseline, EXISTS, JOINs, Sargable ranges)
following clean database query optimization principles.
"""

from dataclasses import dataclass
from typing import List, Optional

import sqlglot
from sqlglot import exp
from sqlglot.optimizer import optimize

from db.optimizer.engine import _map_dialect


@dataclass
class QueryVariant:
    """Represents a candidate SQL query rewrite and its performance profile."""

    id: int
    label: str
    strategy: str
    sql: str
    cost: Optional[float] = None
    estimated_rows: Optional[int] = None
    plan_summary: str = ""
    cost_change_pct: Optional[float] = None
    is_best: bool = False
    source: str = "rewrite"
    actual_time_ms: Optional[float] = None
    buffer_hits: Optional[int] = None
    disk_reads: Optional[int] = None
    benchmark_status: str = "untested"
    time_speedup: Optional[float] = None
    plan_root: Optional[object] = None


def generate_query_variants(
    sql: str,
    dialect: str = "postgres",
    depth: str = "standard",
) -> List[QueryVariant]:
    """Generates competing alternative query rewrites for the provided SQL.

    Args:
        sql: Original SQL statement.
        dialect: Target database dialect ('postgres', 'oracle', etc.).
        depth: Tuning search intensity ('standard' or 'deep').
    """
    cleaned_sql = (sql or "").strip()
    if not cleaned_sql:
        return []

    # Detect procedural blocks (PL/SQL, PL/pgSQL) or DDL
    clean_upper = cleaned_sql.upper()
    procedural_prefixes = (
        "BEGIN", "DECLARE", "CREATE OR REPLACE", "CREATE PROCEDURE",
        "CREATE FUNCTION", "CREATE PACKAGE", "CREATE TRIGGER",
    )
    is_procedural = clean_upper.startswith(procedural_prefixes)
    if not is_procedural:
        for line in cleaned_sql.splitlines():
            s = line.strip().upper()
            if s and not s.startswith("--") and not s.startswith("/*"):
                if s.startswith(procedural_prefixes):
                    is_procedural = True
                break

    if is_procedural:
        strat = (
            "PL/SQL Block Execution"
            if "oracle" in (dialect or "").lower()
            else "Procedural Block Execution"
        )
        return [
            QueryVariant(
                id=0,
                label="Baseline (Original)",
                strategy=strat,
                sql=cleaned_sql,
                plan_summary="Procedural Execution",
                source="baseline",
            )
        ]

    glot_dialect = _map_dialect(dialect)
    try:
        ast = sqlglot.parse_one(cleaned_sql, read=glot_dialect)
    except Exception:
        try:
            ast = sqlglot.parse_one(cleaned_sql)
        except Exception:
            ast = None

    variants: List[QueryVariant] = []

    # 1. Baseline Variant
    try:
        baseline_sql = ast.sql(dialect=glot_dialect, pretty=True) if ast else cleaned_sql
    except Exception:
        baseline_sql = cleaned_sql

    variants.append(
        QueryVariant(
            id=0,
            label="Baseline (Original)",
            strategy="Original query execution plan",
            sql=baseline_sql,
            source="baseline",
        )
    )

    if ast is None:
        return variants

    seen_sqls = {baseline_sql.strip().lower()}

    # 2. Variant: IN subquery -> EXISTS correlated subquery
    exists_ast = _rewrite_in_to_exists(ast)
    if exists_ast:
        try:
            exists_sql = exists_ast.sql(dialect=glot_dialect, pretty=True)
            if exists_sql.strip().lower() not in seen_sqls:
                seen_sqls.add(exists_sql.strip().lower())
                variants.append(
                    QueryVariant(
                        id=len(variants),
                        label=f"Variant {len(variants)}: Correlated EXISTS",
                        strategy="Rewrite IN subquery into correlated EXISTS to avoid full list materialization",
                        sql=exists_sql,
                    )
                )
        except Exception:
            pass

    # 3. Variant: IN subquery -> ANSI INNER JOIN
    join_ast = _rewrite_in_to_join(ast)
    if join_ast:
        try:
            join_sql = join_ast.sql(dialect=glot_dialect, pretty=True)
            if join_sql.strip().lower() not in seen_sqls:
                seen_sqls.add(join_sql.strip().lower())
                variants.append(
                    QueryVariant(
                        id=len(variants),
                        label=f"Variant {len(variants)}: ANSI INNER JOIN",
                        strategy="Convert subquery into explicit INNER JOIN to leverage hash/merge join algorithms",
                        sql=join_sql,
                    )
                )
        except Exception:
            pass

    # 4. Variant: Comma Join -> ANSI Explicit JOIN
    comma_ast = _rewrite_comma_join(ast, glot_dialect)
    if comma_ast:
        try:
            comma_sql = comma_ast.sql(dialect=glot_dialect, pretty=True)
            if comma_sql.strip().lower() not in seen_sqls:
                seen_sqls.add(comma_sql.strip().lower())
                variants.append(
                    QueryVariant(
                        id=len(variants),
                        label=f"Variant {len(variants)}: ANSI JOIN Syntax",
                        strategy="Modernize implicit comma joins to explicit ANSI JOIN ON predicates",
                        sql=comma_sql,
                    )
                )
        except Exception:
            pass

    # 5. Variant: Non-sargable date/function unwrapping
    date_ast = _rewrite_sargable_dates(ast)
    if date_ast:
        try:
            date_sql = date_ast.sql(dialect=glot_dialect, pretty=True)
            if date_sql.strip().lower() not in seen_sqls:
                seen_sqls.add(date_sql.strip().lower())
                variants.append(
                    QueryVariant(
                        id=len(variants),
                        label=f"Variant {len(variants)}: Sargable Date Range",
                        strategy="Replace YEAR() function call with half-open date range index scan",
                        sql=date_sql,
                    )
                )
        except Exception:
            pass

    # 6. Variant: Redundant DISTINCT removal with GROUP BY
    distinct_ast = _rewrite_redundant_distinct(ast)
    if distinct_ast:
        try:
            dist_sql = distinct_ast.sql(dialect=glot_dialect, pretty=True)
            if dist_sql.strip().lower() not in seen_sqls:
                seen_sqls.add(dist_sql.strip().lower())
                variants.append(
                    QueryVariant(
                        id=len(variants),
                        label=f"Variant {len(variants)}: Remove Redundant DISTINCT",
                        strategy="Eliminate secondary sort pass redundant to GROUP BY",
                        sql=dist_sql,
                    )
                )
        except Exception:
            pass

    # Deep Tuning Variants
    if depth == "deep":
        cte_sql = _rewrite_to_cte(ast, glot_dialect)
        if cte_sql and cte_sql.strip().lower() not in seen_sqls:
            seen_sqls.add(cte_sql.strip().lower())
            variants.append(
                QueryVariant(
                    id=len(variants),
                    label=f"Variant {len(variants)}: CTE Modularization",
                    strategy="Extract subquery into Common Table Expression for optimizer memoization",
                    sql=cte_sql,
                )
            )

        hinted_sql = _inject_optimizer_hints(baseline_sql, glot_dialect)
        if hinted_sql and hinted_sql.strip().lower() not in seen_sqls:
            seen_sqls.add(hinted_sql.strip().lower())
            variants.append(
                QueryVariant(
                    id=len(variants),
                    label=f"Variant {len(variants)}: Optimizer Hint Injection",
                    strategy="Inject planner hint (/*+ FIRST_ROWS(100) */) to bias planner towards index seeks",
                    sql=hinted_sql,
                )
            )

    return variants


def _rewrite_to_cte(ast: exp.Expression, dialect: str) -> Optional[str]:
    """Rewrites subquery into explicit WITH CTE block."""
    sub_query = None
    for in_expr in ast.find_all(exp.In):
        sub = in_expr.args.get("query")
        if sub:
            sub_query = sub.this if isinstance(sub, exp.Subquery) else sub
            break
    if not sub_query:
        return None
    try:
        import re
        cte_name = "filtered_keys"
        cte_sql = sub_query.sql(dialect=dialect)
        main_sql = ast.sql(dialect=dialect)
        main_replaced = re.sub(
            r"IN\s*\(\s*SELECT\s+.*?\)",
            f"IN (SELECT * FROM {cte_name})",
            main_sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f"WITH {cte_name} AS (\n  {cte_sql}\n)\n{main_replaced}"
    except Exception:
        return None


def _inject_optimizer_hints(sql: str, dialect: str) -> Optional[str]:
    """Injects vendor-specific execution hints."""
    import re
    clean = sql.strip()
    if clean.upper().startswith("SELECT"):
        hint = "/*+ FIRST_ROWS(100) */" if "oracle" in dialect else "/*+ IndexScan */"
        return re.sub(r"^(SELECT)", rf"\1 {hint}", clean, count=1, flags=re.IGNORECASE)
    return None


def _rewrite_in_to_exists(ast: exp.Expression) -> Optional[exp.Expression]:
    """Rewrites IN (SELECT ...) subqueries into correlated EXISTS (SELECT 1 ...)."""
    clone = ast.copy()
    from_node = clone.find(exp.From)
    outer_name = ""
    if from_node and from_node.this:
        tbl = from_node.this
        outer_name = getattr(tbl, "alias", None) or getattr(tbl, "name", "")

    transformed = False
    for in_expr in clone.find_all(exp.In):
        sub = in_expr.args.get("query")
        if not sub:
            for arg in in_expr.args.get("expressions", []):
                if isinstance(arg, (exp.Select, exp.Subquery)):
                    sub = arg
                    break
        if not sub:
            continue

        sub_select = sub.this if isinstance(sub, exp.Subquery) else sub
        if isinstance(sub_select, exp.Select) and sub_select.expressions:
            sub_col = sub_select.expressions[0]
            sub_from = sub_select.find(exp.From)
            inner_name = ""
            if sub_from and sub_from.this:
                stbl = sub_from.this
                inner_name = getattr(stbl, "alias", None) or getattr(stbl, "name", "")

            cloned_sub = sub_select.copy()
            cloned_sub.set("expressions", [sqlglot.parse_one("1")])

            outer_col = in_expr.this.sql()
            if outer_name and "." not in outer_col:
                outer_col = f"{outer_name}.{outer_col}"

            inner_col = sub_col.sql()
            if inner_name and "." not in inner_col:
                inner_col = f"{inner_name}.{inner_col}"

            corr_cond = sqlglot.parse_one(f"{inner_col} = {outer_col}")
            existing_where = cloned_sub.args.get("where")
            if existing_where:
                new_where = exp.Where(this=exp.and_(existing_where.this, corr_cond))
                cloned_sub.set("where", new_where)
            else:
                cloned_sub.set("where", exp.Where(this=corr_cond))

            exists_expr = sqlglot.parse_one(f"EXISTS ({cloned_sub.sql()})")
            in_expr.replace(exists_expr)
            transformed = True

    return clone if transformed else None


def _rewrite_in_to_join(ast: exp.Expression) -> Optional[exp.Expression]:
    """Rewrites IN (SELECT ...) subqueries into explicit INNER JOINs."""
    clone = ast.copy()
    from_node = clone.find(exp.From)
    if not from_node or not from_node.this:
        return None
    outer_tbl = from_node.this
    outer_name = getattr(outer_tbl, "alias", None) or getattr(outer_tbl, "name", "")

    where_node = clone.args.get("where")
    if not where_node:
        return None

    transformed = False
    for in_expr in clone.find_all(exp.In):
        sub = in_expr.args.get("query")
        if not sub:
            for arg in in_expr.args.get("expressions", []):
                if isinstance(arg, (exp.Select, exp.Subquery)):
                    sub = arg
                    break
        if not sub:
            continue

        sub_select = sub.this if isinstance(sub, exp.Subquery) else sub
        if isinstance(sub_select, exp.Select) and sub_select.expressions:
            sub_col = sub_select.expressions[0]
            sub_from = sub_select.find(exp.From)
            if not sub_from or not sub_from.this:
                continue
            inner_tbl = sub_from.this
            inner_name = getattr(inner_tbl, "alias", None) or getattr(inner_tbl, "name", "")

            outer_col = in_expr.this.sql()
            if outer_name and "." not in outer_col:
                outer_col = f"{outer_name}.{outer_col}"
            inner_col = sub_col.sql()
            if inner_name and "." not in inner_col:
                inner_col = f"{inner_name}.{inner_col}"

            on_condition = f"{outer_col} = {inner_col}"
            join_tbl_sql = inner_tbl.sql()
            parsed_join = sqlglot.parse_one(
                f"SELECT 1 FROM dummy INNER JOIN {join_tbl_sql} ON {on_condition}"
            )
            new_join = parsed_join.find(exp.Join)
            if not new_join:
                continue

            # Qualify unqualified outer columns in SELECT to prevent ORA-00918 column ambiguity
            if outer_name:
                for col in clone.find_all(exp.Column):
                    if col.find_ancestor(exp.Select) == clone and not col.table:
                        col.set("table", exp.to_identifier(outer_name))

            joins = clone.args.get("joins") or []
            joins.append(new_join)
            clone.set("joins", joins)

            sub_where = sub_select.args.get("where")
            if sub_where:
                cloned_sub_where = sub_where.copy()
                if inner_name:
                    for col in cloned_sub_where.find_all(exp.Column):
                        if not col.table:
                            col.set("table", exp.to_identifier(inner_name))
            else:
                cloned_sub_where = None

            in_parent = in_expr.parent
            if in_parent == where_node:
                if cloned_sub_where:
                    clone.set("where", cloned_sub_where)
                else:
                    clone.set("where", None)
            else:
                repl = cloned_sub_where.this if cloned_sub_where else exp.true()
                in_expr.replace(repl)

            transformed = True
            break

    return clone if transformed else None


def _rewrite_comma_join(ast: exp.Expression, dialect: str) -> Optional[exp.Expression]:
    """Converts comma joins with join predicates in WHERE to ANSI explicit JOIN."""
    joins = ast.args.get("joins") or []
    has_comma_join = any(not j.args.get("on") for j in joins)
    if not has_comma_join:
        return None

    try:
        opt = optimize(ast.copy(), dialect=dialect)
        return opt
    except Exception:
        return None


def _rewrite_sargable_dates(ast: exp.Expression) -> Optional[exp.Expression]:
    """Rewrites YEAR(col) = YYYY into range col >= 'YYYY-01-01' AND col < 'YYYY+1-01-01'."""
    clone = ast.copy()
    transformed = False

    for eq in clone.find_all(exp.EQ):
        left, right = eq.this, eq.expression
        year_col = None
        year_val = None
        if isinstance(left, exp.Year) and isinstance(right, exp.Literal) and right.is_number:
            year_col = left.this.sql()
            year_val = int(right.this)
        elif isinstance(right, exp.Year) and isinstance(left, exp.Literal) and left.is_number:
            year_col = right.this.sql()
            year_val = int(left.this)

        if year_col and year_val:
            try:
                replacement = sqlglot.parse_one(
                    f"{year_col} >= '{year_val}-01-01' AND {year_col} < '{year_val + 1}-01-01'"
                )
                eq.replace(replacement)
                transformed = True
            except Exception:
                pass

    return clone if transformed else None


def _rewrite_redundant_distinct(ast: exp.Expression) -> Optional[exp.Expression]:
    """Removes DISTINCT when GROUP BY is already present."""
    if isinstance(ast, exp.Select):
        if ast.args.get("distinct") and ast.args.get("group"):
            clone = ast.copy()
            clone.set("distinct", None)
            return clone
    return None

