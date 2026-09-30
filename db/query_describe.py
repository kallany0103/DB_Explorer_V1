"""
db/query_describe.py
Provides query describe (parse) functionality for SELECT queries across database engines
(Oracle, PostgreSQL, SQLite, etc.) without fetching data rows.
"""

import re
import db
from db.result_metadata import (
    _description_value,
    _resolve_postgres_column_specs,
    _resolve_sqlite_column_specs,
)


def _strip_sql_comments(query: str) -> str:
    """Removes single-line and multi-line comments from SQL."""
    # Remove block comments /* ... */
    q = re.sub(r"/\*.*?\*/", "", query, flags=re.DOTALL)
    # Remove line comments -- ...
    lines = []
    for line in q.splitlines():
        clean_line = re.sub(r"--.*$", "", line)
        if clean_line.strip():
            lines.append(clean_line)
    return "\n".join(lines).strip()


def validate_and_clean_select_query(query: str) -> str:
    """
    Validates that the query is a SELECT query and strips comments and trailing semicolons.
    Raises ValueError if not a valid SELECT query.
    """
    if not query or not query.strip():
        raise ValueError("Please provide a SQL query to describe.")

    clean = _strip_sql_comments(query).strip().rstrip(";")
    if not clean:
        raise ValueError("Query contains only comments or empty text.")

    upper = clean.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError("Query Describe only supports SELECT statements.")

    return clean


def _format_oracle_type(desc) -> str:
    """Formats an Oracle column description item into a standard type string."""
    type_obj = _description_value(desc, "type", 1) or _description_value(desc, "type_code", 1)
    type_name = ""
    if hasattr(type_obj, "name"):
        type_name = type_obj.name
    elif isinstance(type_obj, str):
        type_name = type_obj
    elif type_obj is not None:
        type_name = str(type_obj)

    if type_name.startswith("DB_TYPE_"):
        type_name = type_name[8:]

    if type_name == "VARCHAR":
        type_name = "VARCHAR2"
    elif type_name == "NVARCHAR":
        type_name = "NVARCHAR2"

    internal_size = _description_value(desc, "internal_size", 3)
    precision = _description_value(desc, "precision", 4)
    scale = _description_value(desc, "scale", 5)

    if type_name in ("NUMBER",):
        if precision is not None and precision > 0:
            if scale is not None and scale > 0:
                return f"NUMBER ({precision}, {scale})"
            elif scale == 0:
                return f"NUMBER ({precision})"
            return f"NUMBER ({precision})"
        return "NUMBER"
    elif type_name in ("VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR", "RAW"):
        if internal_size:
            return f"{type_name} ({internal_size})"
        return type_name
    elif type_name == "TIMESTAMP_TZ":
        return "TIMESTAMP WITH TIME ZONE"
    elif type_name == "TIMESTAMP_LTZ":
        return "TIMESTAMP WITH LOCAL TIME ZONE"
    elif type_name == "DATE":
        return "DATE"
    elif type_name == "FLOAT":
        if precision is not None and precision > 0:
            return f"FLOAT ({precision})"
        return "FLOAT"

    return type_name or "VARCHAR2"


def _resolve_oracle_describe(cursor_description):
    columns = []
    for idx, desc in enumerate(cursor_description or []):
        col_name = _description_value(desc, "name", 0, f"COL_{idx+1}")
        data_type = _format_oracle_type(desc)
        null_ok = _description_value(desc, "null_ok", 6, True)
        is_nullable = bool(null_ok)
        null_text = "" if is_nullable else "NOT NULL"

        columns.append({
            "position": idx + 1,
            "name": str(col_name),
            "data_type": data_type,
            "nullable": is_nullable,
            "null_text": null_text,
            "internal_size": _description_value(desc, "internal_size", 3),
            "precision": _description_value(desc, "precision", 4),
            "scale": _description_value(desc, "scale", 5),
        })
    return columns


def describe_select_query(conn_data: dict, raw_query: str) -> list[dict]:


    """
    Executes a zero-row describe / parse of the given SELECT query.
    Returns a list of dicts with column specifications:
    [
        {
            "position": 1,
            "name": "EMPLOYEE_ID",
            "data_type": "NUMBER",
            "nullable": False,
            "null_text": "NOT NULL"
        },
        ...
    ]
    """
    clean_query = validate_and_clean_select_query(raw_query)

    if not isinstance(conn_data, dict) or not conn_data:
        raise ValueError("Invalid connection information.")

    code = (conn_data.get("code") or conn_data.get("type") or "").upper()
    if not code:
        if conn_data.get("service_name") or "oracle" in str(conn_data.get("driver", "")).lower():
            code = "ORACLE"
        elif conn_data.get("host"):
            code = "POSTGRES"
        elif conn_data.get("db_path"):
            code = "SQLITE"

    # --- ORACLE ---
    if code in ("ORACLE", "ORACLE_DB"):
        conn = db.get_pooled_oracle_connection(conn_data=conn_data)
        if not conn:
            raise ConnectionError("Failed to connect to Oracle database.")
        cursor = conn.cursor()
        try:
            wrapper_sql = f"SELECT * FROM ({clean_query}) \"_DESC_Q_\" WHERE 1 = 0"
            try:
                cursor.execute(wrapper_sql)
            except Exception:
                # Fallback to direct execution without wrapper
                cursor.execute(clean_query)

            if not cursor.description:
                raise ValueError("The query did not produce any result columns to describe.")

            return _resolve_oracle_describe(cursor.description)
        finally:
            cursor.close()
            try:
                conn.close()
            except Exception:
                pass

    # --- POSTGRESQL ---
    elif code == "POSTGRES":
        app_name = "Universal SQL Client (Describe)"
        conn = db.create_postgres_connection(conn_data, application_name=app_name, bypass_cooldown=True)
        if not conn:
            raise ConnectionError("Failed to connect to PostgreSQL database.")
        cursor = conn.cursor()
        try:
            wrapper_sql = f"SELECT * FROM ({clean_query}) AS _desc_subq WHERE FALSE"
            try:
                cursor.execute(wrapper_sql)
            except Exception:
                cursor.execute(clean_query)

            if not cursor.description:
                raise ValueError("The query did not produce any result columns to describe.")

            specs = _resolve_postgres_column_specs(conn, conn_data, cursor.description)
            columns = []
            for idx, spec in enumerate(specs):
                is_nullable = spec.get("nullable", True)
                null_text = "" if is_nullable else "NOT NULL"
                data_type = spec.get("data_type") or "TEXT"
                columns.append({
                    "position": idx + 1,
                    "name": spec.get("name") or f"col_{idx+1}",
                    "data_type": data_type,
                    "nullable": is_nullable,
                    "null_text": null_text,
                    "pk": spec.get("pk", False),
                    "fk": spec.get("fk", False),
                })
            return columns
        finally:
            cursor.close()
            try:
                conn.close()
            except Exception:
                pass

    # --- SQLITE ---
    elif code == "SQLITE":
        db_path = conn_data.get("db_path")
        if not db_path:
            raise ValueError("SQLite database path is missing.")
        conn = db.create_sqlite_connection(db_path)
        if not conn:
            raise ConnectionError("Failed to connect to SQLite database.")
        cursor = conn.cursor()
        try:
            wrapper_sql = f"SELECT * FROM ({clean_query}) WHERE 0"
            try:
                cursor.execute(wrapper_sql)
            except Exception:
                cursor.execute(clean_query)

            if not cursor.description:
                raise ValueError("The query did not produce any result columns to describe.")

            specs = _resolve_sqlite_column_specs(conn, clean_query, cursor.description)
            columns = []
            for idx, spec in enumerate(specs):
                is_nullable = spec.get("nullable", True)
                null_text = "" if is_nullable else "NOT NULL"
                data_type = spec.get("data_type") or "TEXT"
                columns.append({
                    "position": idx + 1,
                    "name": spec.get("name") or f"col_{idx+1}",
                    "data_type": data_type,
                    "nullable": is_nullable,
                    "null_text": null_text,
                    "pk": spec.get("pk", False),
                    "fk": spec.get("fk", False),
                })
            return columns
        finally:
            cursor.close()
            try:
                conn.close()
            except Exception:
                pass

    # --- GENERIC DB-API (CSV, SERVICENOW, etc.) ---
    else:
        # Fallback using existing connection pool / factory if applicable
        raise ValueError(f"Query Describe is not supported for database engine: {code}")


def format_describe_text(columns: list[dict], style: str = "toad") -> str:
    """
    Formats the list of columns into a formatted text string according to the requested style.
    Styles:
    - 'toad': Aligned Toad-style list (Name, Type, NOT NULL)
    - 'ddl': DDL comma-separated list
    - 'names': Comma-separated list of column names
    - 'select_list': Indented column list suitable for SELECT statement
    - 'markdown': Markdown table format
    """
    if not columns:
        return ""

    if style == "toad":
        max_name_len = max(len(c["name"]) for c in columns)
        padding = max(max_name_len + 2, 16)
        lines = []
        for c in columns:
            name_part = c["name"].ljust(padding)
            type_part = c["data_type"]
            null_part = f" {c['null_text']}" if c.get("null_text") else ""
            lines.append(f"{name_part}{type_part}{null_part}")
        return "\n".join(lines)

    elif style == "ddl":
        max_name_len = max(len(c["name"]) for c in columns)
        padding = max(max_name_len + 2, 16)
        lines = []
        for idx, c in enumerate(columns):
            is_last = (idx == len(columns) - 1)
            name_part = c["name"].ljust(padding)
            type_part = c["data_type"]
            null_part = f" {c['null_text']}" if c.get("null_text") else ""
            comma = "" if is_last else ","
            lines.append(f"  {name_part}{type_part}{null_part}{comma}")
        return "(\n" + "\n".join(lines) + "\n)"

    elif style == "names":
        return ", ".join(c["name"] for c in columns)

    elif style == "select_list":
        lines = []
        for idx, c in enumerate(columns):
            comma = "" if idx == len(columns) - 1 else ","
            lines.append(f"  {c['name']}{comma}")
        return "\n".join(lines)

    elif style == "markdown":
        lines = [
            "| # | Column Name | Data Type | Nullable |",
            "|---|-------------|-----------|----------|",
        ]
        for c in columns:
            pos = c["position"]
            name = c["name"]
            dtype = c["data_type"]
            null_str = "NOT NULL" if not c.get("nullable", True) else "NULL"
            lines.append(f"| {pos} | {name} | {dtype} | {null_str} |")
        return "\n".join(lines)

    return ""
