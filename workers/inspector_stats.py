# workers/inspector_stats.py
"""Resolve database statistics queries (PostgreSQL and Oracle) for inspector workbench and dialogs."""

from dialogs.properties import pg_queries, oracle_queries

_PG_GROUP_STATS = {
    "Tables": pg_queries.GET_TABLES_GROUP_STATS,
    "Views": pg_queries.GET_VIEWS_GROUP_STATS,
    "Materialized Views": pg_queries.GET_MATVIEWS_GROUP_STATS,
    "Sequences": pg_queries.GET_SEQUENCES_GROUP_STATS,
    "Functions": pg_queries.GET_FUNCTIONS_GROUP_STATS,
    "Trigger Functions": pg_queries.GET_TRIGGER_FUNCTIONS_GROUP_STATS,
    "Foreign Tables": pg_queries.GET_FOREIGN_TABLES_GROUP_STATS,
    "Triggers": pg_queries.GET_TRIGGERS_GROUP_STATS,
}

_ORACLE_GROUP_STATS = {
    "Tables": oracle_queries.GET_TABLES_GROUP_STATS,
    "Views": oracle_queries.GET_VIEWS_GROUP_STATS,
    "Materialized Views": oracle_queries.GET_MATVIEWS_GROUP_STATS,
    "Sequences": oracle_queries.GET_SEQUENCES_GROUP_STATS,
    "Functions": oracle_queries.GET_FUNCTIONS_GROUP_STATS,
    "Procedures": oracle_queries.GET_PROCEDURES_GROUP_STATS,
    "Packages": oracle_queries.GET_PACKAGES_GROUP_STATS,
    "Triggers": oracle_queries.GET_TRIGGERS_GROUP_STATS,
    "Synonyms": oracle_queries.GET_SYNONYMS_GROUP_STATS,
    "Database Links": oracle_queries.GET_DBLINKS_GROUP_STATS,
    "Java": oracle_queries.GET_JAVA_GROUP_STATS,
}


def is_oracle(item_data):
    """Check if item_data represents an Oracle connection or object."""
    if not item_data:
        return False
    db_type = (item_data.get("db_type") or "").lower()
    if "oracle" in db_type:
        return True
    node_type = str(item_data.get("type", "")).lower()
    if "oracle" in node_type:
        return True
    conn_data = item_data.get("conn_data") or {}
    code = str(conn_data.get("code", "")).upper()
    if code in ("ORACLE_DB", "ORACLE_FA") or "ORACLE" in code:
        return True
    if (
        conn_data.get("service_name")
        or conn_data.get("oracle_db_type")
        or "oracle" in str(conn_data.get("db_type", "")).lower()
        or conn_data.get("driver_mode")
        or conn_data.get("oracle_client_dir")
    ):
        return True
    return False


def _resolve_oracle_statistics_queries(item_data, obj_name):
    """Return a list of {query, params} dicts for an Oracle tree object."""
    obj_type = item_data.get("type") or ""
    table_type = (item_data.get("table_type") or "").upper()
    conn_data = item_data.get("conn_data") or item_data
    schema_name = (item_data.get("schema_name") or conn_data.get("user") or "").upper()
    group_name = item_data.get("group_name")
    if not group_name and obj_type in ("oracle_schema_group", "schema_group"):
        group_name = obj_name
    eff_obj = obj_name.upper()
    queries = []

    if obj_type in ("oracle_schemas_root", "schemas_root"):
        queries.append((oracle_queries.GET_ALL_SCHEMAS_STATS, {}))

    elif group_name or obj_type in ("oracle_schema_group", "schema_group"):
        eff_group = group_name or obj_name
        query = _ORACLE_GROUP_STATS.get(eff_group)
        if not query:
            if eff_group.startswith("Materializ"):
                query = _ORACLE_GROUP_STATS.get("Materialized Views")
            elif eff_group.startswith("Database"):
                query = _ORACLE_GROUP_STATS.get("Database Links")
        if query:
            queries.append((query, {"own": schema_name}))

    elif obj_type in ("oracle_schema", "schema"):
        schema = (item_data.get("schema_name") or obj_name).upper()
        queries.append((oracle_queries.GET_SCHEMA_STATS, {"own": schema}))

    elif obj_type == "connection":
        queries.append((oracle_queries.GET_DATABASE_STATS, {}))

    elif obj_type == "trigger":
        trigger_name = (item_data.get("trigger_name") or obj_name).upper()
        queries.append((oracle_queries.GET_TRIGGER_DETAILS, {"own": schema_name, "obj": trigger_name}))

    elif obj_type == "table" or any(k in table_type for k in ("TABLE", "VIEW", "MATERIALIZED")):
        queries.append((oracle_queries.GET_TABLE_STATS, {"own": schema_name, "obj": eff_obj}))
        queries.append((oracle_queries.GET_COLUMN_STATS, {"own": schema_name, "obj": eff_obj}))
        queries.append((oracle_queries.GET_INDEX_STATS, {"own": schema_name, "obj": eff_obj}))

    elif any(k in table_type for k in ("FUNCTION", "PROCEDURE", "PACKAGE")) or obj_type in ("function", "procedure", "package"):
        func_name = obj_name.split("(")[0].upper()
        queries.append((oracle_queries.GET_PROCEDURE_OR_FUNCTION_DETAILS, {"own": schema_name, "obj": func_name}))

    elif "SEQUENCE" in table_type or obj_type == "sequence":
        queries.append((oracle_queries.GET_SEQUENCE_DETAILS, {"own": schema_name, "obj": eff_obj}))

    return [{"query": q, "params": p} for q, p in queries]


def resolve_statistics_queries(item_data, obj_name):
    """Return a list of {query, params} dicts for the given tree object."""
    if is_oracle(item_data):
        return _resolve_oracle_statistics_queries(item_data, obj_name)

    obj_type = item_data.get("type")
    table_type = (item_data.get("table_type") or "").upper()
    schema_name = item_data.get("schema_name", "public")
    group_name = item_data.get("group_name")
    queries = []

    if obj_type == "schemas_root":
        queries.append((pg_queries.GET_ALL_SCHEMAS_STATS, ()))

    elif obj_type == "schema_group" and group_name:
        query = _PG_GROUP_STATS.get(group_name)
        if query:
            queries.append((query, (schema_name,)))

    elif obj_type == "schema":
        schema = item_data.get("schema_name") or obj_name
        queries.append((pg_queries.GET_SCHEMA_STATS, (schema, schema)))

    elif obj_type == "connection":
        conn = item_data.get("conn_data") or item_data
        db_name = item_data.get("database") or conn.get("database")
        if db_name:
            queries.append((pg_queries.GET_DATABASE_STATS, (db_name,)))

    # Trigger-specific: must come before generic table_type checks 
    elif obj_type == "trigger":
        trigger_name = item_data.get("trigger_name") or obj_name
        queries.append((pg_queries.GET_TRIGGER_STATS, (schema_name, trigger_name)))

    elif obj_type == "triggers_group":
        table_name = item_data.get("table_name")
        queries.append((pg_queries.GET_TRIGGERS_GROUP_STATS, (schema_name, table_name)))

    # Generic type-based checks
    elif obj_type == "table" or any(
        k in table_type for k in ("TABLE", "VIEW", "MATERIALIZED")
    ):
        queries.append((pg_queries.GET_TABLE_SIZE_STATS, (schema_name, obj_name)))
        queries.append((pg_queries.GET_TABLE_STATS, (schema_name, obj_name)))

    elif "FUNCTION" in table_type or "TRIGGER" in table_type:
        func_name = obj_name.split("(")[0]
        queries.append((pg_queries.GET_FUNCTION_STATS, (schema_name, func_name)))

    elif "SEQUENCE" in table_type:
        queries.append((pg_queries.GET_SEQUENCE_STATS, (schema_name, obj_name)))

    return [{"query": q, "params": p} for q, p in queries]


def fetch_statistics_results(cursor, item_data, obj_name):
    """Execute resolved queries and return {stats: [{columns, rows}, ...]}."""
    final_results = []
    for item in resolve_statistics_queries(item_data, obj_name):
        try:
            cursor.execute(item["query"], item["params"])
            cols = [desc[0] for desc in cursor.description]
            raw_rows = cursor.fetchall()
            rows = []
            for r in raw_rows:
                clean_row = []
                for val in r:
                    if hasattr(val, "read"):
                        clean_row.append(val.read())
                    else:
                        clean_row.append(val)
                rows.append(tuple(clean_row))
            final_results.append({"columns": cols, "rows": rows})
        except Exception:
            # If a particular stats view is unavailable or lacks permission, continue gracefully
            pass
    return {"stats": final_results}
