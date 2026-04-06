import re


IDENTIFIER_PATTERN = r'"[^"]+"|\[[^\]]+\]|`[^`]+`|[A-Za-z_][\w$]*'
FROM_TABLE_PATTERN = re.compile(
    rf"""
    (?:
        (?P<schema>{IDENTIFIER_PATTERN})
        \s*\.\s*
    )?
    (?P<table>{IDENTIFIER_PATTERN})
    (?:\s+(?:AS\s+)?(?P<alias>[A-Za-z_][\w$]*))?
    """,
    re.IGNORECASE | re.VERBOSE,
)
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

    from_index = _find_top_level_keyword(sql, "from")
    if from_index < 0:
        return None

    from_sql = sql[from_index + 4:].lstrip()
    match = FROM_TABLE_PATTERN.match(from_sql)
    if not match:
        return None

    remainder = from_sql[match.end():]
    boundary_offset = -1
    for boundary in ("where", "group by", "order by", "having", "limit", "offset", "fetch", "for", "window"):
        match_index = _find_top_level_keyword(remainder, boundary)
        if match_index >= 0 and (boundary_offset < 0 or match_index < boundary_offset):
            boundary_offset = match_index
    boundary_match = CLAUSE_BOUNDARY_PATTERN.search(remainder) if boundary_offset < 0 else None
    if boundary_offset >= 0:
        from_tail = remainder[:boundary_offset]
    else:
        from_tail = remainder[:boundary_match.start()] if boundary_match else remainder

    if COMPLEX_FROM_PATTERN.search(from_tail):
        return None
    if "," in from_tail:
        return None
    if "(" in from_tail or ")" in from_tail:
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
