"""db/optimizer/engine.py

SQL analysis and query optimization engine.
Parses query ASTs via sqlglot and generates concrete recommendations,
rewritten queries, and index suggestions.
"""

from dataclasses import dataclass
import re
from typing import List, Set, Tuple

import sqlglot
from sqlglot import exp

from db.optimizer.rules import (
    OptimizationFinding,
    RULE_COMMA_JOIN,
    RULE_COUNT_EXISTENCE,
    RULE_HAVING_WITHOUT_AGGREGATE,
    RULE_IN_SUBQUERY,
    RULE_LEADING_WILDCARD,
    RULE_NONSARGABLE_FUNCTION,
    RULE_NOT_IN_SUBQUERY,
    RULE_OR_ACROSS_COLUMNS,
    RULE_PAGINATION_WITHOUT_ORDER,
    RULE_REDUNDANT_DISTINCT,
    RULE_SELECT_STAR,
    RULE_UNCONSTRAINED_MUTATION,
)


@dataclass
class OptimizationResult:
    findings: List[OptimizationFinding]
    optimized_sql: str
    has_rewrite: bool
    index_recommendations: List[str]
    score: int
    original_sql: str
    dialect: str


def analyze_query(sql: str, dialect: str = "postgres") -> OptimizationResult:
    """Analyzes a query and returns actionable optimization findings."""
    cleaned_sql = (sql or "").strip()
    if not cleaned_sql:
        return OptimizationResult(
            findings=[],
            optimized_sql="",
            has_rewrite=False,
            index_recommendations=[],
            score=100,
            original_sql="",
            dialect=dialect,
        )

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
        return OptimizationResult(
            findings=[],
            optimized_sql=cleaned_sql,
            has_rewrite=False,
            index_recommendations=[],
            score=100,
            original_sql=cleaned_sql,
            dialect=dialect,
        )

    glot_dialect = _map_dialect(dialect)
    try:
        ast = sqlglot.parse_one(cleaned_sql, read=glot_dialect)
    except Exception:
        try:
            ast = sqlglot.parse_one(cleaned_sql)
        except Exception:
            ast = None

    findings = _detect_anti_patterns(ast, cleaned_sql)
    optimized_sql, has_rewrite = _generate_optimized_sql(ast, cleaned_sql, glot_dialect)
    index_recommendations = _generate_index_recommendations(ast)
    score = _compute_score(findings)

    return OptimizationResult(
        findings=findings,
        optimized_sql=optimized_sql,
        has_rewrite=has_rewrite,
        index_recommendations=index_recommendations,
        score=score,
        original_sql=cleaned_sql,
        dialect=dialect,
    )


def _map_dialect(dialect: str) -> str:
    d = (dialect or "").lower()
    if "oracle" in d:
        return "oracle"
    if "postgres" in d or "pgsql" in d:
        return "postgres"
    if "mysql" in d:
        return "mysql"
    if "sqlite" in d:
        return "sqlite"
    return "postgres"


def _detect_anti_patterns(ast, raw_sql: str) -> List[OptimizationFinding]:
    findings: List[OptimizationFinding] = []
    if ast is None:
        _detect_regex_fallback(raw_sql, findings)
        return findings

    # 1. Avoid SELECT *
    if isinstance(ast, exp.Select):
        has_star = any(isinstance(expr, exp.Star) for expr in ast.expressions)
        if has_star:
            findings.append(
                OptimizationFinding(
                    severity="MEDIUM",
                    category="PROJECTION",
                    rule_id=RULE_SELECT_STAR,
                    title="Avoid SELECT *",
                    description="Fetching all columns increases network payload, memory usage, and prevents index-only scans.",
                    suggestion="Specify explicit column names (e.g. SELECT id, name FROM ...).",
                )
            )

    # 2. Leading Wildcard in LIKE
    for like_node in ast.find_all(exp.Like):
        right = like_node.expression
        if isinstance(right, exp.Literal) and str(right.this).startswith("%"):
            findings.append(
                OptimizationFinding(
                    severity="HIGH",
                    category="INDEX",
                    rule_id=RULE_LEADING_WILDCARD,
                    title="Leading wildcard in LIKE ('%...')",
                    description=f"Predicate '{like_node.sql()}' cannot use standard B-Tree indexes, requiring a full table scan.",
                    suggestion="Use prefix search ('pattern%') or consider a trigram index (pg_trgm) or full-text search.",
                )
            )

    # 3. Non-Sargable Functions in WHERE (e.g., YEAR(dt), UPPER(col), TO_CHAR(col))
    sargable_funcs = {"YEAR", "MONTH", "DAY", "DATE", "UPPER", "LOWER", "TRIM", "TO_CHAR", "SUBSTR", "SUBSTRING"}
    for func in ast.find_all(exp.Func, exp.Anonymous):
        func_name = func.key.upper() if hasattr(func, "key") else (func.this.upper() if isinstance(func.this, str) else "")
        if func_name in sargable_funcs:
            parent = func.parent
            in_predicate = False
            while parent:
                if isinstance(parent, (exp.Where, exp.Join)):
                    in_predicate = True
                    break
                parent = parent.parent

            if in_predicate:
                findings.append(
                    OptimizationFinding(
                        severity="HIGH",
                        category="PREDICATE",
                        rule_id=RULE_NONSARGABLE_FUNCTION,
                        title=f"Function on filter column ({func_name})",
                        description=f"Evaluating '{func.sql()}' in WHERE prevents the optimizer from performing index seeks.",
                        suggestion=f"Compare against a literal range, or create an expression index on '{func.sql()}'.",
                    )
                )

    # 4 & 5. IN and NOT IN Subqueries
    for in_node in ast.find_all(exp.In):
        subqueries = [a for a in in_node.args.values() if isinstance(a, (exp.Select, exp.Subquery))]
        is_negated = bool(in_node.args.get("is_negated")) or isinstance(in_node.parent, exp.Not)
        if subqueries:
            if is_negated:
                findings.append(
                    OptimizationFinding(
                        severity="HIGH",
                        category="SAFETY",
                        rule_id=RULE_NOT_IN_SUBQUERY,
                        title="Subquery in NOT IN clause (NULL risk)",
                        description="If the subquery returns any NULL values, NOT IN returns 0 rows and disables hash anti-joins.",
                        suggestion="Use NOT EXISTS (SELECT 1 ...) or a LEFT JOIN ... WHERE ... IS NULL anti-join.",
                    )
                )
            else:
                findings.append(
                    OptimizationFinding(
                        severity="HIGH",
                        category="SUBQUERY",
                        rule_id=RULE_IN_SUBQUERY,
                        title="Subquery in IN clause",
                        description="Large or unindexed subqueries in IN() can degrade into slow nested loop scans.",
                        suggestion="Rewrite using EXISTS (SELECT 1 ...) or an explicit INNER JOIN.",
                    )
                )

    # 6. Comma Joins (FROM a, b WHERE ...)
    if isinstance(ast, exp.Select) and ast.args.get("from"):
        from_expr = ast.args["from"]
        joins = ast.args.get("joins") or []
        comma_tables = [c for c in from_expr.expressions if isinstance(c, exp.Table)]
        if len(comma_tables) > 0 and not joins:
            findings.append(
                OptimizationFinding(
                    severity="MEDIUM",
                    category="JOIN",
                    rule_id=RULE_COMMA_JOIN,
                    title="Comma-separated join syntax",
                    description="FROM a, b risks accidental Cartesian products if join conditions are missed or altered.",
                    suggestion="Use explicit ANSI JOIN syntax: INNER JOIN table_b ON ...",
                )
            )

    # 7. Redundant DISTINCT with GROUP BY
    if isinstance(ast, exp.Select):
        has_distinct = bool(ast.args.get("distinct"))
        has_group = bool(ast.args.get("group"))
        if has_distinct and has_group:
            findings.append(
                OptimizationFinding(
                    severity="MEDIUM",
                    category="STRUCTURE",
                    rule_id=RULE_REDUNDANT_DISTINCT,
                    title="Redundant DISTINCT",
                    description="GROUP BY already deduplicates rows; DISTINCT adds unnecessary sort overhead.",
                    suggestion="Remove DISTINCT to reduce sorting and memory overhead.",
                )
            )

    # 8. Existence Check with COUNT(*)
    for eq in ast.find_all(exp.GT, exp.GTE, exp.NEQ):
        if any(isinstance(a, exp.Count) for a in (eq.this, eq.expression)):
            findings.append(
                OptimizationFinding(
                    severity="MEDIUM",
                    category="PREDICATE",
                    rule_id=RULE_COUNT_EXISTENCE,
                    title="COUNT(*) used to check existence",
                    description="COUNT(*) scans and counts all matching rows instead of stopping at the first match.",
                    suggestion="Use EXISTS (SELECT 1 ...) or LIMIT 1 to terminate on the first matching record.",
                )
            )

    # 9. Mutating Query Without WHERE
    if isinstance(ast, (exp.Delete, exp.Update)):
        if not ast.args.get("where"):
            findings.append(
                OptimizationFinding(
                    severity="HIGH",
                    category="SAFETY",
                    rule_id=RULE_UNCONSTRAINED_MUTATION,
                    title="UPDATE / DELETE without WHERE",
                    description="This statement modifies every row in the target table without a condition.",
                    suggestion="Add a WHERE clause, or use TRUNCATE to intentionally clear the table.",
                )
            )

    # 10. OR Across Different Columns in WHERE
    if isinstance(ast, exp.Select) and ast.args.get("where"):
        for or_node in ast.args["where"].find_all(exp.Or):
            cols = {col.name.lower() for col in or_node.find_all(exp.Column) if col.name}
            if len(cols) > 1:
                findings.append(
                    OptimizationFinding(
                        severity="MEDIUM",
                        category="PREDICATE",
                        rule_id=RULE_OR_ACROSS_COLUMNS,
                        title="OR condition across different columns",
                        description=f"OR condition references separate columns ({', '.join(sorted(cols))}), which often prevents index usage.",
                        suggestion="Consider combining separate indexed queries with UNION ALL.",
                    )
                )
                break

    # 11. Pagination Without ORDER BY
    if isinstance(ast, exp.Select):
        has_limit = bool(ast.args.get("limit") or ast.args.get("offset"))
        has_order = bool(ast.args.get("order"))
        if has_limit and not has_order:
            findings.append(
                OptimizationFinding(
                    severity="INFO",
                    category="SAFETY",
                    rule_id=RULE_PAGINATION_WITHOUT_ORDER,
                    title="LIMIT without ORDER BY",
                    description="Without an ORDER BY clause, rows are returned in undefined order across pagination pages.",
                    suggestion="Add an ORDER BY clause to guarantee consistent pagination.",
                )
            )

    # 12. Non-Aggregate Condition in HAVING
    if isinstance(ast, exp.Select) and ast.args.get("having"):
        having = ast.args["having"]
        for comp in having.find_all(exp.EQ, exp.NEQ, exp.GT, exp.LT, exp.GTE, exp.LTE):
            has_agg = any(isinstance(n, exp.AggFunc) for n in comp.find_all(exp.AggFunc))
            if not has_agg:
                findings.append(
                    OptimizationFinding(
                        severity="MEDIUM",
                        category="PREDICATE",
                        rule_id=RULE_HAVING_WITHOUT_AGGREGATE,
                        title="Non-aggregate condition in HAVING",
                        description=f"Condition '{comp.sql()}' does not evaluate an aggregate function. Filtering in HAVING happens after grouping.",
                        suggestion=f"Move '{comp.sql()}' to the WHERE clause so rows are pruned before aggregation.",
                    )
                )
                break

    return findings


def _detect_regex_fallback(raw_sql: str, findings: List[OptimizationFinding]) -> None:
    """Regex fallback when AST parser cannot parse complex vendor-specific code."""
    sql_upper = raw_sql.upper()

    if re.search(r"\bSELECT\s+\*\s+FROM\b", sql_upper):
        findings.append(
            OptimizationFinding(
                severity="MEDIUM",
                category="PROJECTION",
                rule_id=RULE_SELECT_STAR,
                title="Avoid SELECT *",
                description="Fetching all columns increases network payload, memory usage, and prevents index-only scans.",
                suggestion="Specify explicit column names (e.g. SELECT id, name FROM ...).",
            )
        )

    if re.search(r"\bLIKE\s+['\"]%", raw_sql, re.IGNORECASE):
        findings.append(
            OptimizationFinding(
                severity="HIGH",
                category="INDEX",
                rule_id=RULE_LEADING_WILDCARD,
                title="Leading wildcard in LIKE ('%...')",
                description="Predicate starts with a leading wildcard ('%'), forcing a full table scan.",
                suggestion="Use prefix matching ('abc%') or trigram / full-text indexes.",
            )
        )

    if re.search(r"\b(DELETE\s+FROM|UPDATE)\s+[a-zA-Z0-9_.]+\s*(;|$)", sql_upper):
        findings.append(
            OptimizationFinding(
                severity="HIGH",
                category="SAFETY",
                rule_id=RULE_UNCONSTRAINED_MUTATION,
                title="UPDATE / DELETE without WHERE",
                description="Statement modifies every row in the target table without a condition.",
                suggestion="Add a WHERE clause, or use TRUNCATE to intentionally clear the table.",
            )
        )


def _generate_optimized_sql(ast, original_sql: str, dialect: str) -> Tuple[str, bool]:
    """Rewrites queries where deterministic transformations improve performance."""
    if ast is None:
        return original_sql, False

    clone = ast.copy()
    transformed = False

    # Transformation 1: Rewrite YEAR(date_col) = YYYY to range condition
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

    # Transformation 2: Remove redundant DISTINCT when GROUP BY is present
    if isinstance(clone, exp.Select):
        if clone.args.get("distinct") and clone.args.get("group"):
            clone.set("distinct", None)
            transformed = True

    if not transformed:
        return original_sql, False

    try:
        return clone.sql(dialect=dialect, pretty=True), True
    except Exception:
        return original_sql, False


def _generate_index_recommendations(ast) -> List[str]:
    """Generates CREATE INDEX DDL suggestions based on columns in WHERE and JOIN."""
    if ast is None:
        return []

    recommendations: List[str] = []
    seen: Set[Tuple[str, str]] = set()

    tables = {t.name.lower(): t.name for t in ast.find_all(exp.Table) if t.name}

    where = ast.args.get("where") if isinstance(ast, exp.Select) else None
    if where:
        for col in where.find_all(exp.Column):
            tbl = col.table or ""
            col_name = col.name
            target_tbl = tables.get(tbl.lower()) or list(tables.values())[0] if tables else tbl
            if target_tbl and col_name:
                key = (target_tbl.lower(), col_name.lower())
                if key not in seen:
                    seen.add(key)
                    idx_name = f"idx_{target_tbl}_{col_name}"
                    recommendations.append(
                        f"CREATE INDEX {idx_name} ON {target_tbl} ({col_name});"
                    )

    for join in ast.find_all(exp.Join):
        on_clause = join.args.get("on")
        if on_clause:
            for col in on_clause.find_all(exp.Column):
                tbl = col.table or ""
                col_name = col.name
                target_tbl = tables.get(tbl.lower()) or list(tables.values())[0] if tables else tbl
                if target_tbl and col_name:
                    key = (target_tbl.lower(), col_name.lower())
                    if key not in seen:
                        seen.add(key)
                        idx_name = f"idx_{target_tbl}_{col_name}"
                        recommendations.append(
                            f"CREATE INDEX {idx_name} ON {target_tbl} ({col_name});"
                        )

    return recommendations[:6]


def _compute_score(findings: List[OptimizationFinding]) -> int:
    """Calculates a health score from 0 to 100."""
    score = 100
    for f in findings:
        if f.severity == "HIGH":
            score -= 18
        elif f.severity == "MEDIUM":
            score -= 8
        elif f.severity == "INFO":
            score -= 4
    return max(20, min(100, score))
