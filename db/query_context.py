import re


IDENTIFIER_PATTERN = r'"[^"]+"|\[[^\]]+\]|`[^`]+`|[A-Za-z_][\w$]*'


# ---------------------------------------------------------------------------
# Read-only object detection constants
# ---------------------------------------------------------------------------

# PostgreSQL: relkind values that are writable base tables
_PG_WRITABLE_RELKINDS = frozenset({"r", "p"})  # ordinary table, partitioned table

# PostgreSQL: system schemas whose objects are always read-only
_PG_SYSTEM_SCHEMAS = frozenset({"pg_catalog", "information_schema", "pg_toast"})

# Oracle: owners whose objects are always treated as system / read-only
_ORACLE_SYSTEM_OWNERS = frozenset({
    "SYS", "SYSTEM", "DBSNMP", "OUTLN", "MDSYS", "ORDSYS", "EXFSYS",
    "WMSYS", "CTXSYS", "XDB", "ANONYMOUS", "WKSYS", "SYSMAN", "MDDATA",
    "DMSYS", "TSMSYS", "OJVMSYS", "GSMADMIN_INTERNAL", "APPQOSSYS",
    "DBSFWUSER", "GGSYS", "DVF", "DVSYS", "LBACSYS", "REMOTE_SCHEDULER_AGENT",
})

# Oracle: table-name prefixes that indicate system objects (upper-cased before check)
_ORACLE_SYSTEM_NAME_PREFIXES = (
    "V$", "GV$", "ALL_", "DBA_", "USER_", "CDB_", "NLS_",
)
CLAUSE_BOUNDARY_KEYWORDS = (
    "where",
    "group by",
    "having",
    "window",
    "order by",
    "limit",
    "offset",
    "fetch",
    "for",
    "union",
    "intersect",
    "except",
)
SINGLE_FROM_PATTERN = re.compile(
    rf"""
    ^\s*
    (?:
        (?P<schema>{IDENTIFIER_PATTERN})
        \s*\.\s*
    )?
    (?P<table>{IDENTIFIER_PATTERN})
    (?:\s+(?:AS\s+)?(?P<alias>{IDENTIFIER_PATTERN}))?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
FROM_TABLE_PATTERN = SINGLE_FROM_PATTERN
COMMENT_PATTERN = re.compile(r"--.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
CLAUSE_BOUNDARY_PATTERN = re.compile(
    r"\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bOFFSET\b|\bFETCH\b|\bFOR\b|\bWINDOW\b",
    re.IGNORECASE,
)
COMPLEX_FROM_PATTERN = re.compile(r"\bJOIN\b|\bUNION\b|\bINTERSECT\b|\bEXCEPT\b", re.IGNORECASE)


def strip_sql_comments(query):
    return COMMENT_PATTERN.sub("", query or "")


def strip_identifier_quotes(identifier):
    if not identifier:
        return ""
    if (
        (identifier.startswith('"') and identifier.endswith('"'))
        or (identifier.startswith("[") and identifier.endswith("]"))
        or (identifier.startswith("`") and identifier.endswith("`"))
    ):
        return identifier[1:-1]
    return identifier


def quote_identifier(identifier):
    escaped = str(identifier or "").replace('"', '""')
    return f'"{escaped}"'


def build_qualified_table_name(schema_name, table_name):
    if schema_name:
        return f"{quote_identifier(schema_name)}.{quote_identifier(table_name)}"
    return quote_identifier(table_name)


def _find_top_level_keyword(sql, keyword):
    keyword_lower = keyword.lower()
    in_single_quote = False
    in_double_quote = False
    in_brackets = False
    in_backticks = False
    depth = 0

    for idx, char in enumerate(sql):
        if in_single_quote:
            if char == "'" and (idx == 0 or sql[idx - 1] != "\\"):
                in_single_quote = False
            continue
        if in_double_quote:
            if char == '"':
                in_double_quote = False
            continue
        if in_brackets:
            if char == "]":
                in_brackets = False
            continue
        if in_backticks:
            if char == "`":
                in_backticks = False
            continue

        if char == "'":
            in_single_quote = True
            continue
        if char == '"':
            in_double_quote = True
            continue
        if char == "[":
            in_brackets = True
            continue
        if char == "`":
            in_backticks = True
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            continue

        if depth != 0:
            continue

        if sql[idx:idx + len(keyword_lower)].lower() != keyword_lower:
            continue

        before_char = sql[idx - 1] if idx > 0 else " "
        after_index = idx + len(keyword_lower)
        after_char = sql[after_index] if after_index < len(sql) else " "
        if (before_char.isalnum() or before_char == "_") or (after_char.isalnum() or after_char == "_"):
            continue
        return idx

    return -1


def resolve_writable_table_context(query):
    sql = strip_sql_comments(query).strip().rstrip(";")
    if not sql:
        return None
    if re.match(r"^\s*WITH\b", sql, re.IGNORECASE):
        return None
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return None
    if re.match(r"^\s*SELECT\s+DISTINCT\b", sql, re.IGNORECASE):
        return None
    if _find_top_level_keyword(sql, "group by") >= 0 or _find_top_level_keyword(sql, "having") >= 0:
        return None
    if (
        _find_top_level_keyword(sql, "union") >= 0
        or _find_top_level_keyword(sql, "intersect") >= 0
        or _find_top_level_keyword(sql, "except") >= 0
    ):
        return None

    from_index = _find_top_level_keyword(sql, "from")
    if from_index < 0:
        return None

    from_sql = sql[from_index + 4:]

    # Find earliest top-level boundary that ends the FROM clause
    boundary_offset = -1
    for boundary in CLAUSE_BOUNDARY_KEYWORDS:
        idx = _find_top_level_keyword(from_sql, boundary)
        if idx >= 0 and (boundary_offset < 0 or idx < boundary_offset):
            boundary_offset = idx

    if boundary_offset >= 0:
        from_clause = from_sql[:boundary_offset].strip()
    else:
        from_clause = from_sql.strip()

    if not from_clause:
        return None
    if COMPLEX_FROM_PATTERN.search(from_clause):
        return None
    if "," in from_clause:
        return None
    if "(" in from_clause or ")" in from_clause:
        return None

    match = SINGLE_FROM_PATTERN.match(from_clause)
    if not match:
        return None

    schema_name = strip_identifier_quotes(match.group("schema") or "") or None
    table_name = strip_identifier_quotes(match.group("table") or "")
    if not table_name:
        return None

    return {
        "schema_name": schema_name,
        "real_table_name": table_name,
        "table_name": f"{schema_name}.{table_name}" if schema_name else table_name,
        "qualified_table_name": build_qualified_table_name(schema_name, table_name),
    }


def resolve_object_writability(schema, table, code, conn):
    # Check the database to determine if a resolved table name is writable.
    # Called from the worker thread while the connection is still open.
    # Returns: {"is_writable": bool, "reason": str, "reason_code": str}
    # reason_code: "view" | "mview" | "foreign_table" | "sequence" |
    #              "system_catalog" | "system_object" | "csv" | "servicenow" | "unknown"
    code_upper = (code or "").upper()
    if code_upper == "CSV":
        return {"is_writable": False, "reason": "CSV data source is a static file snapshot", "reason_code": "csv"}
    if code_upper == "SERVICENOW":
        return {"is_writable": False, "reason": "ServiceNow results cannot be modified through the result grid", "reason_code": "servicenow"}
    if code_upper in ("POSTGRES", "POSTGRESQL"):
        return _check_postgres_writability(schema, table, conn)
    if code_upper in ("ORACLE", "ORACLE_DB", "ORACLE_FA"):
        return _check_oracle_writability(schema, table, conn)
    # SQLite: single-table selects are always writable
    return {"is_writable": True, "reason": "", "reason_code": ""}


def _check_postgres_writability(schema, table, conn):
    # Query pg_class to verify the object type for PostgreSQL.
    _RELKIND_LABELS = {
        "v": ("view", "Views cannot be modified directly"),
        "m": ("mview", "Materialized views cannot be modified directly"),
        "f": ("foreign_table", "Foreign tables cannot be modified directly"),
        "S": ("sequence", "Sequences cannot be modified as table rows"),
        "c": ("system_object", "Composite types cannot be modified directly"),
        "t": ("system_object", "TOAST tables cannot be modified directly"),
        "I": ("system_object", "Partitioned indexes cannot be modified directly"),
    }

    # Fast system-schema check without a DB query
    if schema and schema.lower() in _PG_SYSTEM_SCHEMAS:
        return {
            "is_writable": False,
            "reason": f'System catalog schema "{schema}" is protected',
            "reason_code": "system_catalog",
        }

    try:
        cursor = conn.cursor()
        try:
            if schema:
                cursor.execute(
                    "SELECT c.relkind, n.nspname"
                    " FROM pg_class c"
                    " JOIN pg_namespace n ON n.oid = c.relnamespace"
                    " WHERE c.relname = %s AND n.nspname = %s"
                    " LIMIT 1",
                    (table, schema),
                )
            else:
                cursor.execute(
                    "SELECT c.relkind, n.nspname"
                    " FROM pg_class c"
                    " JOIN pg_namespace n ON n.oid = c.relnamespace"
                    " WHERE c.relname = %s"
                    " ORDER BY (n.nspname = current_schema()) DESC"
                    " LIMIT 1",
                    (table,),
                )
            row = cursor.fetchone()
        finally:
            cursor.close()
    except Exception:
        # On any lookup failure fall back to allowing edits (safe failure mode)
        return {"is_writable": True, "reason": "", "reason_code": ""}

    if row is None:
        return {"is_writable": False, "reason": "Object not found in pg_class", "reason_code": "unknown"}

    relkind, nspname = row

    # Re-check the resolved schema for system namespaces
    if nspname and nspname.lower() in _PG_SYSTEM_SCHEMAS:
        return {
            "is_writable": False,
            "reason": f'System catalog schema "{nspname}" is protected',
            "reason_code": "system_catalog",
        }

    if relkind in _PG_WRITABLE_RELKINDS:
        return {"is_writable": True, "reason": "", "reason_code": ""}

    reason_code, reason = _RELKIND_LABELS.get(relkind, ("unknown", "Object type is not directly editable"))
    return {"is_writable": False, "reason": reason, "reason_code": reason_code}


def _check_oracle_writability(schema, table, conn):
    # Query Oracle data dictionary to determine object writability.
    owner = (schema or "").upper()
    table_upper = table.upper()

    # Fast checks without a DB query
    if owner in _ORACLE_SYSTEM_OWNERS:
        return {
            "is_writable": False,
            "reason": f'System schema "{owner}" is protected',
            "reason_code": "system_object",
        }

    for prefix in _ORACLE_SYSTEM_NAME_PREFIXES:
        if table_upper.startswith(prefix):
            return {
                "is_writable": False,
                "reason": f'System object "{table}" is protected',
                "reason_code": "system_object",
            }

    try:
        cursor = conn.cursor()
        try:
            if owner:
                cursor.execute(
                    "SELECT 'TABLE' FROM ALL_TABLES WHERE OWNER = :o AND TABLE_NAME = :t"
                    " UNION ALL"
                    " SELECT 'VIEW' FROM ALL_VIEWS WHERE OWNER = :o AND VIEW_NAME = :t"
                    " UNION ALL"
                    " SELECT 'MVIEW' FROM ALL_MVIEWS WHERE OWNER = :o AND MVIEW_NAME = :t",
                    {"o": owner, "t": table_upper},
                )
            else:
                cursor.execute(
                    "SELECT 'TABLE' FROM USER_TABLES WHERE TABLE_NAME = :t"
                    " UNION ALL"
                    " SELECT 'VIEW' FROM USER_VIEWS WHERE VIEW_NAME = :t"
                    " UNION ALL"
                    " SELECT 'MVIEW' FROM USER_MVIEWS WHERE MVIEW_NAME = :t",
                    {"t": table_upper},
                )
            row = cursor.fetchone()
        finally:
            cursor.close()
    except Exception:
        return {"is_writable": True, "reason": "", "reason_code": ""}

    if row is None:
        return {
            "is_writable": False,
            "reason": "Object not found in Oracle data dictionary",
            "reason_code": "unknown",
        }

    obj_type = row[0]
    if obj_type == "TABLE":
        return {"is_writable": True, "reason": "", "reason_code": ""}
    if obj_type == "VIEW":
        return {"is_writable": False, "reason": "Views cannot be modified directly", "reason_code": "view"}
    if obj_type == "MVIEW":
        return {"is_writable": False, "reason": "Materialized views cannot be modified directly", "reason_code": "mview"}
    return {"is_writable": False, "reason": "Object type cannot be modified directly", "reason_code": "unknown"}
