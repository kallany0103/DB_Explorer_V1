"""ServiceNow ingestion into DuckDB using dlt (data load tool)."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
import duckdb
from db.duckdb_manager import DuckDBManager

logger = logging.getLogger(__name__)


def _quote_ident(name: str) -> str:
    """Safely double-quote a DuckDB SQL identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def _build_clean_view_sql(
    raw_cols: List[str],
    dict_cols: List[Dict[str, Any]],
    table_name: str,
) -> Tuple[str, str]:
    """Build DuckDB CREATE OR REPLACE VIEW SQL for display and raw schemas."""
    raw_set = set(raw_cols)
    base_names: List[str] = []
    seen = set()

    for col_name in [c.get("name") for c in dict_cols if c.get("name")]:
        if col_name in seen:
            continue
        if f"{col_name}__display_value" in raw_set or f"{col_name}__value" in raw_set or col_name in raw_set:
            seen.add(col_name)
            base_names.append(col_name)

    for col in raw_cols:
        if col.startswith("_dlt"):
            continue
        if col.endswith("__display_value"):
            base = col[: -len("__display_value")]
        elif col.endswith("__value"):
            base = col[: -len("__value")]
        elif "__v_" in col:
            base = col.split("__v_", 1)[0]
        else:
            base = col
        if base and base not in seen:
            seen.add(base)
            base_names.append(base)

    display_exprs: List[str] = []
    raw_exprs: List[str] = []
    for base in base_names:
        q_base = _quote_ident(base)
        disp_col = f"{base}__display_value"
        val_col = f"{base}__value"
        has_disp = disp_col in raw_set
        has_val = val_col in raw_set

        if has_disp and has_val:
            qd, qv = _quote_ident(disp_col), _quote_ident(val_col)
            display_exprs.append(
                f"COALESCE(NULLIF(CAST({qd} AS VARCHAR), ''), CAST({qv} AS VARCHAR)) AS {q_base}"
            )
            raw_exprs.append(f"COALESCE(CAST({qv} AS VARCHAR), CAST({qd} AS VARCHAR)) AS {q_base}")
        elif has_disp:
            display_exprs.append(f"CAST({_quote_ident(disp_col)} AS VARCHAR) AS {q_base}")
            raw_exprs.append(f"CAST({_quote_ident(disp_col)} AS VARCHAR) AS {q_base}")
        elif has_val:
            display_exprs.append(f"CAST({_quote_ident(val_col)} AS VARCHAR) AS {q_base}")
            raw_exprs.append(f"CAST({_quote_ident(val_col)} AS VARCHAR) AS {q_base}")
        else:
            display_exprs.append(f"{q_base} AS {q_base}")
            raw_exprs.append(f"{q_base} AS {q_base}")

    q_tbl = _quote_ident(table_name)
    disp_sql = f"CREATE OR REPLACE VIEW main.{q_tbl} AS SELECT {', '.join(display_exprs)} FROM _sn_raw.{q_tbl};"
    raw_sql = f"CREATE OR REPLACE VIEW _sn_raw_vals.{q_tbl} AS SELECT {', '.join(raw_exprs)} FROM _sn_raw.{q_tbl};"
    return disp_sql, raw_sql


def _drop_if_base_table(conn: duckdb.DuckDBPyConnection, schema_name: str, table_name: str) -> None:
    """Drop legacy base tables before replacing them with clean views."""
    row = conn.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [schema_name, table_name],
    ).fetchone()
    if row and str(row[0]).upper() == "BASE TABLE":
        conn.execute(f"DROP TABLE IF EXISTS {_quote_ident(schema_name)}.{_quote_ident(table_name)};")


def _create_servicenow_views(
    db_path: str,
    table_name: str,
    dict_cols: List[Dict[str, Any]],
) -> None:
    """Create clean display and raw views in DuckDB without dlt metadata columns."""
    conn = duckdb.connect(database=db_path, read_only=False)
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS main;")
        conn.execute("CREATE SCHEMA IF NOT EXISTS _sn_raw_vals;")
        raw_cols_rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = '_sn_raw' AND table_name = ? ORDER BY ordinal_position",
            [table_name],
        ).fetchall()
        if raw_cols_rows:
            raw_cols = [r[0] for r in raw_cols_rows]
            disp_sql, raw_sql = _build_clean_view_sql(raw_cols, dict_cols, table_name)
            _drop_if_base_table(conn, "main", table_name)
            _drop_if_base_table(conn, "_sn_raw_vals", table_name)
            conn.execute(disp_sql)
            conn.execute(raw_sql)
            return

        # 0 rows returned by ServiceNow: create empty tables so SELECT returns headers
        if dict_cols:
            col_defs = [f"{_quote_ident(c['name'])} {_map_to_duckdb_type(c.get('type', 'STRING'))}" for c in dict_cols]
        else:
            col_defs = ['"sys_id" VARCHAR PRIMARY KEY', '"sys_created_on" TIMESTAMP', '"sys_updated_on" TIMESTAMP']
        cols_clause = ", ".join(col_defs)
        for schema_name in ("main", "_sn_raw_vals"):
            q_sch, q_tbl = _quote_ident(schema_name), _quote_ident(table_name)
            conn.execute(f"DROP VIEW IF EXISTS {q_sch}.{q_tbl};")
            conn.execute(f"CREATE TABLE IF NOT EXISTS {q_sch}.{q_tbl} ({cols_clause});")
    finally:
        conn.close()


def _map_to_duckdb_type(servicenow_type: str) -> str:
    """Maps ServiceNow dictionary type to DuckDB column type."""
    t = (servicenow_type or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(x in t for x in ("DOUBLE", "FLOAT", "DECIMAL", "CURRENCY")):
        return "DOUBLE"
    if "BOOL" in t:
        return "BOOLEAN"
    if any(x in t for x in ("TIME", "DATE")):
        return "TIMESTAMP"
    return "VARCHAR"


def _build_dlt_source(
    instance_url: str,
    user: str,
    password: str,
    table_name: str,
    limit: int = 5000,
    display_value: str = "true",
    column_hints: Optional[Dict[str, Dict[str, str]]] = None,
    auth_type: str = "basic",
    client_id: str = "",
    client_secret: str = "",
):
    """Constructs a declarative dlt REST API source for ServiceNow."""
    from dlt.sources.rest_api import rest_api_source
    from dlt.sources.helpers.rest_client.auth import HttpBasicAuth, BearerTokenAuth
    from db.servicenow_metadata import (
        _normalize_instance_url,
        _fetch_oauth_token,
        build_table_api_url,
    )

    clean_url = _normalize_instance_url(instance_url)
    base_endpoint = build_table_api_url(clean_url)

    if "oauth" in (auth_type or "").lower():
        token = _fetch_oauth_token(clean_url, client_id, client_secret, user=user, password=password)
        auth_config = BearerTokenAuth(token)
    elif user or password:
        auth_config = HttpBasicAuth(user, password)
    else:
        auth_config = None

    resource_config: Dict[str, Any] = {
        "name": table_name,
        "write_disposition": "replace",
        "endpoint": {
            "path": table_name,
            "params": {
                "sysparm_limit": limit,
                "sysparm_display_value": display_value,
                "sysparm_exclude_reference_link": "true",
                "sysparm_no_count": "true",
            },
            "paginator": "header_link",
            "data_selector": "result",
        },
    }
    if column_hints:
        resource_config["columns"] = column_hints

    config = {
        "client": {
            "base_url": base_endpoint,
            "auth": auth_config,
            "paginator": "header_link",
        },
        "resources": [resource_config],
    }
    return rest_api_source(config)


def sync_servicenow_table(
    conn_data: Dict[str, Any],
    table_name: str,
    limit: int = 5000,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Syncs a ServiceNow table into the local DuckDB database using dlt.

    Args:
        conn_data: ServiceNow connection parameters.
        table_name: Target ServiceNow table (e.g. 'incident').
        limit: Maximum rows to fetch in this batch.
        progress_callback: Optional status reporter.

    Returns:
        str: Absolute path to the DuckDB database file.
    """
    import dlt
    logging.getLogger("dlt.normalize").setLevel(logging.ERROR)
    logging.getLogger("dlt.schema").setLevel(logging.ERROR)

    conn_id = conn_data.get("id") or conn_data.get("connection_id") or "default"
    db_path = DuckDBManager.get_servicenow_duckdb_path(conn_id)

    instance_url = conn_data.get("instance_url", "")
    user = conn_data.get("user", "")
    password = conn_data.get("password", "")

    if progress_callback:
        progress_callback(f"Syncing '{table_name}' from ServiceNow...")

    pipeline = dlt.pipeline(
        pipeline_name=f"sn_v2_{conn_id}",
        destination=dlt.destinations.duckdb(db_path),
        dataset_name="_sn_raw",
    )

    batch_limit = int(conn_data.get("page_size") or limit)

    from db.servicenow_metadata import fetch_servicenow_columns
    cols = fetch_servicenow_columns(conn_data, table_name)
    column_hints: Dict[str, Dict[str, str]] = {}
    if not cols:
        fallback_cols = [
            "sys_id", "number", "short_description", "description", "state",
            "priority", "urgency", "impact", "contact_type", "assigned_to",
            "assignment_group", "sys_created_on", "sys_updated_on", "opened_at",
            "closed_at", "active",
        ]
        for col_name in fallback_cols:
            column_hints[col_name] = {"data_type": "text"}
            column_hints[f"{col_name}__display_value"] = {"data_type": "text"}
            column_hints[f"{col_name}__value"] = {"data_type": "text"}
    for col in cols or []:
        col_name = col.get("name")
        if col_name:
            column_hints[col_name] = {"data_type": "text"}
            column_hints[f"{col_name}__display_value"] = {"data_type": "text"}
            column_hints[f"{col_name}__value"] = {"data_type": "text"}

    source = _build_dlt_source(
        instance_url=instance_url,
        user=user,
        password=password,
        table_name=table_name,
        limit=batch_limit,
        display_value="all",
        column_hints=column_hints or None,
        auth_type=conn_data.get("auth_type", "basic"),
        client_id=conn_data.get("client_id", ""),
        client_secret=conn_data.get("client_secret", ""),
    )

    load_info = pipeline.run(source)
    logger.info("dlt pipeline finished: %s", load_info)

    _create_servicenow_views(db_path, table_name, cols)

    if progress_callback:
        progress_callback(f"Synced '{table_name}' into DuckDB.")

    return db_path


def get_synced_tables(db_path: str, schema_name: str = "main") -> List[str]:
    """Returns list of user tables/views currently loaded in the local DuckDB schema."""
    if not db_path or not os.path.exists(db_path):
        return []
    try:
        conn = duckdb.connect(database=db_path, read_only=True)
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name NOT LIKE '_dlt%'",
            [schema_name],
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as exc:
        logger.debug("Error checking synced tables in %s: %s", db_path, exc)
        return []
