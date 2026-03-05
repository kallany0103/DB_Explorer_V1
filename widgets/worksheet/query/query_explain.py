def validate_explain_connection(conn_data, analyze=False):
    if conn_data and conn_data.get("host"):
        return None
    if analyze:
        return "Explain Analyze is only supported for PostgreSQL connections."
    return "Explain is only supported for PostgreSQL connections."


def build_explain_sql(selected_query, analyze=False):
    query_upper = (selected_query or "").upper().strip()
    if query_upper.startswith("EXPLAIN"):
        return selected_query, None

    if analyze:
        if query_upper.startswith("SELECT"):
            return f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {selected_query}", None
        return None, "Please select a SELECT query to explain."

    if query_upper.startswith("SELECT") or query_upper.startswith("INSERT") or query_upper.startswith("UPDATE") or query_upper.startswith("DELETE"):
        return f"EXPLAIN (FORMAT JSON, COSTS, VERBOSE) {selected_query}", None
    return None, "Please select a valid query to explain."
