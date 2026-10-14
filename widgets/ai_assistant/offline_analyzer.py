# widgets/ai_assistant/offline_analyzer.py
"""
Intelligent rule-based offline SQL explainer.
Uses sqlglot (or fallback regex/heuristics) to analyze query components,
tables, projections, filters, joins, and potential performance bottlenecks.
Does not require any internet connection or API key.
"""

import re
from typing import Dict, Any, List

def analyze_sql_locally(sql: str, db_type: str = "GENERIC") -> str:
    """
    Parses and explains a SQL query locally without requiring an API key.
    Returns rich markdown-formatted explanation.
    """
    sql = sql.strip()
    if not sql:
        return "*(No SQL code provided to analyze)*"

    cleaned_sql = re.sub(r"--.*?\n|/\*.*?\*/", "", sql, flags=re.DOTALL).strip()
    first_word = cleaned_sql.split()[0].upper() if cleaned_sql.split() else "SQL"

    # Identify primary statement type
    statement_type = "Query"
    if first_word in ("SELECT", "WITH"):
        statement_type = "Data Retrieval (SELECT)"
    elif first_word == "INSERT":
        statement_type = "Data Insertion (INSERT)"
    elif first_word == "UPDATE":
        statement_type = "Data Modification (UPDATE)"
    elif first_word == "DELETE":
        statement_type = "Data Deletion (DELETE)"
    elif first_word in ("CREATE", "ALTER", "DROP", "TRUNCATE"):
        statement_type = f"Schema Definition ({first_word})"
    elif first_word in ("GRANT", "REVOKE"):
        statement_type = f"Permissions & Security ({first_word})"

    summary = f"This statement performs a **{statement_type}** operation against target database objects."

    # Try using sqlglot for structured AST parsing
    tables = []
    columns = []
    joins = []
    where_conditions = []
    has_wildcard = bool(re.search(r"SELECT\s+\*", cleaned_sql, re.IGNORECASE))
    has_limit = bool(re.search(r"\b(LIMIT|FETCH FIRST|TOP|ROWNUM)\b", cleaned_sql, re.IGNORECASE))
    has_order_by = bool(re.search(r"\bORDER\s+BY\b", cleaned_sql, re.IGNORECASE))
    has_group_by = bool(re.search(r"\bGROUP\s+BY\b", cleaned_sql, re.IGNORECASE))

    try:
        import sqlglot
        from sqlglot import exp

        read_dialect = "postgres"
        if "ORACLE" in db_type.upper():
            read_dialect = "oracle"
        elif "SQLITE" in db_type.upper():
            read_dialect = "sqlite"

        parsed_expressions = sqlglot.parse(cleaned_sql, read=read_dialect)
        for expression in parsed_expressions:
            if not expression:
                continue

            # Tables
            for tbl in expression.find_all(exp.Table):
                tbl_name = tbl.sql()
                if tbl_name and tbl_name not in tables:
                    tables.append(tbl_name)

            # Columns in Select
            if isinstance(expression, exp.Select):
                for select_expr in expression.selects:
                    col_repr = select_expr.sql()
                    if col_repr and col_repr not in columns:
                        columns.append(col_repr)

            # Joins
            for j in expression.find_all(exp.Join):
                join_side = j.args.get("side", "") or ""
                join_kind = j.args.get("kind", "") or ""
                join_type = f"{join_side} {join_kind}".strip().upper() or "JOIN"
                this_table = j.this.sql() if j.this else "relation"
                joins.append(f"{join_type} on `{this_table}`")

            # Where conditions
            where_node = expression.find(exp.Where)
            if where_node:
                where_conditions.append(where_node.this.sql())

    except Exception:
        # Fallback regex extraction if sqlglot parse fails
        from_matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\.\"]+)", cleaned_sql, re.IGNORECASE)
        for m in from_matches:
            if m not in tables:
                tables.append(m)

    # Build Components Description
    components_lines = []
    if first_word in ("SELECT", "WITH"):
        if has_wildcard:
            components_lines.append("- **`SELECT *`**: Requests **all columns** from the target table(s).")
        elif columns:
            top_cols = columns[:5]
            col_list_str = ", ".join(f"`{c}`" for c in top_cols)
            if len(columns) > 5:
                col_list_str += f" *(and {len(columns) - 5} more)*"
            components_lines.append(f"- **Columns Selected**: {col_list_str}")

    if tables:
        for t in tables:
            components_lines.append(f"- **`{t}`**: References table/entity in the current schema or catalog.")
    else:
        components_lines.append("- **Target Objects**: Database object reference.")

    if where_conditions:
        components_lines.append(f"- **Filters (WHERE)**: Evaluates condition `{where_conditions[0]}` to filter matching records.")

    if has_group_by:
        components_lines.append("- **Grouping (GROUP BY)**: Aggregates matching rows across grouped dimension attributes.")

    if has_order_by:
        components_lines.append("- **Sorting (ORDER BY)**: Specifies sort order before returning the dataset.")

    # Relationships
    relationships_lines = []
    if joins:
        for j in joins:
            relationships_lines.append(f"- {j}")
    elif len(tables) > 1:
        relationships_lines.append(f"- References multiple tables: {', '.join(f'`{t}`' for t in tables)}.")
    else:
        tbl_display = f"`{tables[0]}`" if tables else "a single table"
        relationships_lines.append(f"The statement operates strictly on {tbl_display} without joining other entities.")

    # Performance Considerations
    perf_lines = []
    if has_wildcard:
        perf_lines.append("- **`SELECT *` overhead**: Retrieving all columns can decrease performance and increase memory/network transfer, particularly if tables contain LOBs, long text, or many columns. Specify explicit column lists in production.")
    if not has_limit and first_word == "SELECT":
        perf_lines.append("- **Unbounded result set**: The query does not specify a `LIMIT` clause. For large tables, this may fetch millions of rows and stall client memory. Consider adding a `LIMIT` or pagination.")
    if where_conditions:
        perf_lines.append("- **Indexing**: Ensure filtered columns in the `WHERE` clause have appropriate indexes (B-tree / composite) to prevent full-table sequential scans.")
    if not perf_lines:
        perf_lines.append("- **Optimal pattern**: Statement is straightforward. Ensure target tables have updated database statistics (`ANALYZE`) for the query planner.")

    # Format into markdown Toad-style sections
    parts = []
    if summary:
        parts.append(summary)
        parts.append("")

    parts.append("### Components:")
    parts.append("\n".join(components_lines) if components_lines else "Standard statement components.")
    parts.append("")

    parts.append("### Relationships:")
    parts.append("\n".join(relationships_lines))
    parts.append("")

    parts.append("### Performance Considerations:")
    parts.append("\n".join(perf_lines))

    return "\n".join(parts)
