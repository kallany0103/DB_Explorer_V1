def validate_explain_connection(conn_data, analyze=False):
    if not conn_data:
        return "No active database connection found."
    code = (conn_data.get("code") or "").upper()
    if not code:
        if "host" in conn_data:
            code = "POSTGRES"
        elif "db_path" in conn_data:
            code = "SQLITE"
    if code in ("POSTGRES", "ORACLE", "ORACLE_DB"):
        return None
    if analyze:
        return f"Explain Analyze is supported for PostgreSQL and Oracle connections (current: {code or 'unknown'})."
    return f"Explain is supported for PostgreSQL and Oracle connections (current: {code or 'unknown'})."


def build_explain_sql(selected_query, analyze=False, conn_data=None):
    code = ((conn_data or {}).get("code") or "").upper() if isinstance(conn_data, dict) else ""
    is_oracle = code in ("ORACLE", "ORACLE_DB")

    query_clean = (selected_query or "").strip().rstrip(";")
    query_upper = query_clean.upper()

    if is_oracle:
        if query_upper.startswith("EXPLAIN PLAN") or query_upper.startswith("EXPLAIN ANALYZE"):
            return query_clean, None
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH") or query_upper.startswith("INSERT") or query_upper.startswith("UPDATE") or query_upper.startswith("DELETE")):
            return None, "Please select a valid SQL query to explain."
        if analyze:
            return f"EXPLAIN ANALYZE {query_clean}", None
        return f"EXPLAIN PLAN FOR {query_clean}", None

    # PostgreSQL (default)
    if query_upper.startswith("EXPLAIN"):
        return selected_query, None

    if analyze:
        if query_upper.startswith("SELECT") or query_upper.startswith("WITH"):
            return f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {query_clean}", None
        return None, "Please select a SELECT query to explain."

    if query_upper.startswith("SELECT") or query_upper.startswith("WITH") or query_upper.startswith("INSERT") or query_upper.startswith("UPDATE") or query_upper.startswith("DELETE"):
        return f"EXPLAIN (FORMAT JSON, COSTS, VERBOSE) {query_clean}", None
    return None, "Please select a valid query to explain."
