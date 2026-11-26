# workers/inspector_stats.py
"""Resolve database statistics queries (PostgreSQL, Oracle, SQLite) for inspector workbench and dialogs."""

import os
import dialogs.properties.pg_queries as pg_queries
import dialogs.properties.oracle_queries as oracle_queries

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


def is_sqlite(item_data):
    """Check if item_data represents a SQLite connection or object."""
    if not item_data:
        return False
    db_type = (item_data.get("db_type") or "").lower()
    if "sqlite" in db_type:
        return True
    node_type = str(item_data.get("type", "")).lower()
    if "sqlite" in node_type:
        return True
    conn_data = item_data.get("conn_data") or {}
    code = str(conn_data.get("code", "")).upper()
    if "SQLITE" in code:
        return True
    if conn_data.get("db_path") and not conn_data.get("host"):
        return True
    return False


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


def _format_file_size(size_bytes: int | None) -> str:
    """Format file size in bytes to a human-readable string."""
    if size_bytes is None:
        return "N/A"
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB ({size_bytes:,} bytes)"
    return f"{size_bytes / (1024 * 1024):.2f} MB ({size_bytes:,} bytes)"


def _fetch_sqlite_pragmas(cursor) -> dict:
    """Read standard PRAGMA metadata values from a SQLite database."""
    res = {
        "page_size": 4096,
        "page_count": 0,
        "freelist_count": 0,
        "encoding": "UTF-8",
        "journal_mode": "DELETE",
    }
    for pragma_name in ("page_size", "page_count", "freelist_count", "encoding", "journal_mode"):
        try:
            cursor.execute(f"PRAGMA {pragma_name}")
            row = cursor.fetchone()
            if row:
                res[pragma_name] = str(row[0]).upper() if pragma_name == "journal_mode" else row[0]
        except Exception:
            pass
    return res


def _fetch_sqlite_db_stats(cursor, db_path: str | None, pragmas: dict) -> dict:
    """Gather overall database statistics for SQLite connection node."""
    tbl_count, view_count, idx_count, auto_vac, user_ver = 0, 0, 0, "NONE", 0
    try:
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        r = cursor.fetchone()
        tbl_count = r[0] if r else 0
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='view'")
        r = cursor.fetchone()
        view_count = r[0] if r else 0
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        r = cursor.fetchone()
        idx_count = r[0] if r else 0
        cursor.execute("PRAGMA auto_vacuum")
        r = cursor.fetchone()
        if r:
            auto_vac = {0: "NONE", 1: "FULL", 2: "INCREMENTAL"}.get(r[0], str(r[0]))
        cursor.execute("PRAGMA user_version")
        r = cursor.fetchone()
        user_ver = r[0] if r else 0
    except Exception:
        pass

    file_size_str = "N/A"
    if db_path and os.path.exists(db_path):
        try:
            file_size_str = _format_file_size(os.path.getsize(db_path))
        except OSError:
            pass

    cols = [
        "Database file", "File size", "Total tables", "Total views",
        "Total indexes", "Page size", "Total pages", "Freelist pages",
        "Encoding", "Journal mode", "Auto vacuum", "User version"
    ]
    rows = [(
        os.path.basename(db_path) if db_path else "N/A",
        file_size_str, tbl_count, view_count, idx_count,
        pragmas["page_size"], pragmas["page_count"], pragmas["freelist_count"],
        pragmas["encoding"], pragmas["journal_mode"], auto_vac, user_ver
    )]
    return {"stats": [{"columns": cols, "rows": rows}]}


def _fetch_sqlite_table_stats(cursor, table_name: str, db_path: str | None, pragmas: dict) -> dict:
    """Gather table-level statistics for a SQLite table or view."""
    is_view = False
    try:
        cursor.execute("SELECT type FROM sqlite_master WHERE name = ?", (table_name,))
        r = cursor.fetchone()
        is_view = bool(r and r[0] == "view")
    except Exception:
        pass

    row_count = "N/A"
    if not is_view:
        try:
            cursor.execute(f'SELECT count(*) FROM "{table_name}"')
            r = cursor.fetchone()
            row_count = r[0] if r else 0
        except Exception:
            pass

    cols_count, pk_cols = 0, []
    try:
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        c_rows = cursor.fetchall()
        cols_count = len(c_rows)
        pk_cols = [str(r[1]) for r in c_rows if r[5]]
    except Exception:
        pass

    idx_count, fk_count = 0, 0
    try:
        cursor.execute(f"PRAGMA index_list('{table_name}')")
        idx_count = len(cursor.fetchall())
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        fk_count = len(set(r[0] for r in cursor.fetchall()))
    except Exception:
        pass

    file_size_str = "N/A"
    if db_path and os.path.exists(db_path):
        try:
            file_size_str = _format_file_size(os.path.getsize(db_path))
        except OSError:
            pass

    cols = [
        "Table name", "Row count", "Columns count", "Primary key columns",
        "Indexes count", "Foreign keys count", "File size", "Page size",
        "Total pages", "Freelist pages", "Encoding", "Journal mode"
    ]
    rows = [(
        table_name, row_count, cols_count,
        ", ".join(pk_cols) if pk_cols else "None",
        idx_count, fk_count, file_size_str,
        pragmas["page_size"], pragmas["page_count"], pragmas["freelist_count"],
        pragmas["encoding"], pragmas["journal_mode"]
    )]
    return {"stats": [{"columns": cols, "rows": rows}]}


def _fetch_sqlite_statistics_results(cursor, item_data: dict, obj_name: str) -> dict:
    """Return {stats: [{columns, rows}]} for a SQLite object or connection."""
    conn_data = item_data.get("conn_data") or item_data
    db_path = conn_data.get("db_path")
    pragmas = _fetch_sqlite_pragmas(cursor)
    obj_type = item_data.get("type") or ""

    if obj_type == "connection":
        return _fetch_sqlite_db_stats(cursor, db_path, pragmas)

    table_name = item_data.get("table_name") or obj_name
    return _fetch_sqlite_table_stats(cursor, table_name, db_path, pragmas)


def fetch_statistics_results(cursor, item_data, obj_name):
    """Execute resolved queries and return {stats: [{columns, rows}, ...]}."""
    if is_sqlite(item_data):
        return _fetch_sqlite_statistics_results(cursor, item_data, obj_name)

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
