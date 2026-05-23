# workers/inspector_stats.py
"""Resolve PostgreSQL statistics queries for inspector workbench and dialogs."""

from dialogs.properties import pg_queries

_GROUP_STATS = {
    "Tables": pg_queries.GET_TABLES_GROUP_STATS,
    "Views": pg_queries.GET_VIEWS_GROUP_STATS,
    "Materialized Views": pg_queries.GET_MATVIEWS_GROUP_STATS,
    "Sequences": pg_queries.GET_SEQUENCES_GROUP_STATS,
    "Functions": pg_queries.GET_FUNCTIONS_GROUP_STATS,
    "Trigger Functions": pg_queries.GET_TRIGGER_FUNCTIONS_GROUP_STATS,
    "Foreign Tables": pg_queries.GET_FOREIGN_TABLES_GROUP_STATS,
}


def resolve_statistics_queries(item_data, obj_name):
    """Return a list of {query, params} dicts for the given tree object."""
    obj_type = item_data.get("type")
    table_type = (item_data.get("table_type") or "").upper()
    schema_name = item_data.get("schema_name", "public")
    group_name = item_data.get("group_name")
    queries = []

    if obj_type == "schemas_root":
        queries.append((pg_queries.GET_ALL_SCHEMAS_STATS, ()))

    elif obj_type == "schema_group" and group_name:
        query = _GROUP_STATS.get(group_name)
        if query:
            queries.append((query, (schema_name,)))

    elif obj_type == "schema":
        schema = item_data.get("schema_name") or obj_name
        queries.append((pg_queries.GET_SCHEMA_STATS, (schema, schema, schema)))

    elif obj_type == "connection":
        conn = item_data.get("conn_data") or item_data
        db_name = item_data.get("database") or conn.get("database")
        if db_name:
            queries.append((pg_queries.GET_DATABASE_STATS, (db_name,)))

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
        cursor.execute(item["query"], item["params"])
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        final_results.append({"columns": cols, "rows": rows})
    return {"stats": final_results}
