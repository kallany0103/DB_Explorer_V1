"""PostgreSQL DDL, INSERT, and UPDATE script generators.

Provides developer-friendly script generation for PostgreSQL tables, views,
and materialized views with sequence, identity, primary key, and index detection.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from db.db_connections import PooledPostgresConnection

logger = logging.getLogger(__name__)

PG_RESERVED_KEYWORDS = frozenset({
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc",
    "asymmetric", "both", "case", "cast", "check", "collate", "column",
    "constraint", "create", "current_catalog", "current_date",
    "current_role", "current_time", "current_timestamp", "current_user",
    "default", "deferrable", "desc", "distinct", "do", "else", "end",
    "except", "false", "fetch", "for", "foreign", "from", "grant",
    "group", "having", "in", "initially", "intersect", "into", "lateral",
    "leading", "limit", "localtime", "localtimestamp", "not", "null",
    "offset", "on", "only", "or", "order", "placing", "primary",
    "references", "returning", "select", "session_user", "some",
    "symmetric", "table", "then", "to", "trailing", "true", "union",
    "unique", "user", "using", "variadic", "when", "where", "window",
    "with",
})


def _pg_quote(ident: str) -> str:
    """Format a PostgreSQL identifier, quoting only when necessary."""
    if not ident:
        return '""'
    if re.match(r"^[a-z_][a-z0-9_$]*$", ident) and ident.lower() not in PG_RESERVED_KEYWORDS:
        return ident
    return f'"{ident}"'


def _format_pg_insert_value(col: dict[str, Any]) -> str:
    """Return appropriate placeholder or default expression for a PostgreSQL column value."""
    ident = col.get("identity_type", "")
    default = col.get("default", "").lower()
    ftype = col.get("data_type", "").lower()
    cname = col.get("name", "")

    if ident in ("a", "d") or "nextval(" in default:
        return "DEFAULT"
    if "bool" in ftype:
        return "TRUE"
    if any(t in ftype for t in ("int", "numeric", "decimal", "real", "double", "precision", "serial")):
        return "1"
    if "date" in ftype and "time" not in ftype:
        return "CURRENT_DATE"
    if "timestamp" in ftype:
        return "CURRENT_TIMESTAMP"
    if "time" in ftype:
        return "CURRENT_TIME"
    if "json" in ftype:
        return "'{}'"
    if "uuid" in ftype:
        return "'00000000-0000-0000-0000-000000000000'::uuid"
    if any(t in ftype for t in ("char", "text")):
        return f"'{cname.title()}'"
    if "bytea" in ftype:
        return r"'\x00'::bytea"
    if "[]" in ftype or "array" in ftype:
        return "'{}'"
    return "NULL"


def _fetch_pg_table_columns(
    cursor: Any, schema_name: str, table_name: str
) -> tuple[int, str, list[dict[str, Any]]]:
    """Fetch oid, relkind, and column metadata for a PostgreSQL table or view."""
    cursor.execute(
        """
        SELECT c.oid, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = %s;
        """,
        (schema_name, table_name),
    )
    res = cursor.fetchone()
    if not res:
        raise ValueError(f"Object '{schema_name}.{table_name}' not found.")
    oid, relkind = res

    cursor.execute(
        """
        SELECT 
            a.attname AS column_name,
            pg_catalog.format_type(a.atttypid, a.atttypmod) AS formatted_type,
            a.attnotnull AS not_null,
            pg_get_expr(d.adbin, d.adrelid) AS column_default,
            a.attidentity AS identity_type,
            a.attgenerated AS generated_type
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON (a.attrelid, a.attnum) = (d.adrelid, d.adnum)
        WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum;
        """,
        (oid,),
    )
    cols: list[dict[str, Any]] = []
    for cname, ftype, not_null, ddef, ident_type, gen_type in cursor.fetchall():
        cols.append({
            "name": cname,
            "data_type": ftype,
            "not_null": bool(not_null),
            "default": str(ddef).strip() if ddef else "",
            "identity_type": str(ident_type or "").strip(),
            "generated_type": str(gen_type or "").strip(),
        })
    return oid, relkind, cols


def _fetch_pg_primary_key(cursor: Any, oid: int) -> tuple[str | None, list[str]]:
    """Fetch primary key constraint name and column names for a table."""
    cursor.execute(
        """
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = %s AND contype = 'p';
        """,
        (oid,),
    )
    row = cursor.fetchone()
    if not row:
        return None, []
    conname, condef = row
    m = re.search(r"\((.+?)\)", condef)
    pk_cols: list[str] = []
    if m:
        pk_cols = [c.strip().strip('"') for c in m.group(1).split(",")]
    return conname, pk_cols


def _fetch_pg_constraints_and_indexes(
    cursor: Any, schema_name: str, table_name: str, oid: int
) -> tuple[list[str], list[str]]:
    """Fetch table constraints (unique, check, foreign key) and non-PK secondary indexes."""
    cursor.execute(
        """
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = %s AND contype IN ('u', 'f', 'c')
        ORDER BY contype, conname;
        """,
        (oid,),
    )
    cst_lines = []
    for conname, condef in cursor.fetchall():
        cst_lines.append(f"    CONSTRAINT {_pg_quote(conname)} {condef}")

    cursor.execute(
        """
        SELECT indexdef
        FROM pg_indexes
        WHERE schemaname = %s AND tablename = %s
          AND indexname NOT IN (SELECT conname FROM pg_constraint WHERE conrelid = %s)
        ORDER BY indexname;
        """,
        (schema_name, table_name, oid),
    )
    indexes = [r[0].strip() + (";" if not r[0].strip().endswith(";") else "") for r in cursor.fetchall()]
    return cst_lines, indexes


def generate_postgres_table_ddl(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
    obj_type: str = "TABLE",
) -> str:
    """Generate clean, developer-friendly DDL for a PostgreSQL table, view, or materialized view."""
    schema = schema_name or "public"
    app_name = f"Universal SQL Client (DDL) - {conn_data.get('database', 'postgres')}"

    with PooledPostgresConnection(conn_data, application_name=app_name) as conn:
        if not conn:
            raise ConnectionError("Failed to establish PostgreSQL connection.")
        cursor = conn.cursor()

        oid, relkind, columns = _fetch_pg_table_columns(cursor, schema, table_name)
        full_tbl = f"{_pg_quote(schema)}.{_pg_quote(table_name)}"

        # Views and Materialized Views
        if relkind in ("v", "m"):
            cursor.execute("SELECT pg_get_viewdef(%s);", (oid,))
            view_def_row = cursor.fetchone()
            view_def = view_def_row[0].strip() if view_def_row else ""
            label = "MATERIALIZED VIEW" if relkind == "m" else "VIEW"
            sql = f"-- {label.title()}: {schema}.{table_name}\n\nCREATE {label} {full_tbl} AS\n{view_def}"
            if not sql.endswith(";"):
                sql += ";"
            return sql

        # Regular or Partitioned Tables
        col_defs = []
        for col in columns:
            cname = col["name"]
            ftype = col["data_type"]
            ident = col["identity_type"]
            default = col["default"]
            not_null = col["not_null"]

            line = f"    {_pg_quote(cname)} {ftype}"
            if ident == "a":
                line += " GENERATED ALWAYS AS IDENTITY"
            elif ident == "d":
                line += " GENERATED BY DEFAULT AS IDENTITY"
            elif default:
                line += f" DEFAULT {default}"

            if not_null and ident not in ("a", "d"):
                line += " NOT NULL"
            col_defs.append(line)

        pk_name, pk_cols = _fetch_pg_primary_key(cursor, oid)
        if pk_cols:
            pk_col_str = ", ".join(_pg_quote(c) for c in pk_cols)
            pk_label = _pg_quote(pk_name) if pk_name else f"{table_name}_pkey"
            col_defs.append(f"    CONSTRAINT {pk_label} PRIMARY KEY ({pk_col_str})")

        other_csts, indexes = _fetch_pg_constraints_and_indexes(cursor, schema, table_name, oid)
        col_defs.extend(other_csts)

        body = ",\n".join(col_defs)
        ddl = f"-- Table: {schema}.{table_name}\n\nCREATE TABLE {full_tbl} (\n{body}\n);"

        if indexes:
            ddl += "\n\n" + "\n".join(indexes)

        return ddl


def generate_postgres_insert_script(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
) -> str:
    """Generate an INSERT script for a PostgreSQL table with column names and sequence detection."""
    schema = schema_name or "public"
    app_name = f"Universal SQL Client (Insert Script) - {conn_data.get('database', 'postgres')}"

    with PooledPostgresConnection(conn_data, application_name=app_name) as conn:
        if not conn:
            raise ConnectionError("Failed to establish PostgreSQL connection.")
        cursor = conn.cursor()

        _, _, columns = _fetch_pg_table_columns(cursor, schema, table_name)
        if not columns:
            raise ValueError(f"Table '{schema}.{table_name}' has no accessible columns.")

        full_tbl = f"{_pg_quote(schema)}.{_pg_quote(table_name)}"
        col_names = [f"    {_pg_quote(c['name'])}" for c in columns]
        val_exprs = [f"    {_format_pg_insert_value(c)}" for c in columns]

        header_lines = [f"-- Insert Script for {full_tbl}"]
        for c in columns:
            if c.get("identity_type") in ("a", "d"):
                header_lines.append(
                    f"-- Identity column detected on {c['name']}: auto-generated (uses DEFAULT)"
                )
            elif "nextval(" in c.get("default", "").lower():
                header_lines.append(
                    f"-- Sequence default detected on {c['name']}: {c['default']} (uses DEFAULT)"
                )

        header = "\n".join(header_lines)
        cols_block = ",\n".join(col_names)
        vals_block = ",\n".join(val_exprs)

        return f"{header}\n\nINSERT INTO {full_tbl} (\n{cols_block}\n)\nVALUES (\n{vals_block}\n);"


def generate_postgres_update_script(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
) -> str:
    """Generate an UPDATE script for a PostgreSQL table with non-PK columns in SET and PK in WHERE."""
    schema = schema_name or "public"
    app_name = f"Universal SQL Client (Update Script) - {conn_data.get('database', 'postgres')}"

    with PooledPostgresConnection(conn_data, application_name=app_name) as conn:
        if not conn:
            raise ConnectionError("Failed to establish PostgreSQL connection.")
        cursor = conn.cursor()

        oid, _, columns = _fetch_pg_table_columns(cursor, schema, table_name)
        if not columns:
            raise ValueError(f"Table '{schema}.{table_name}' has no accessible columns.")

        _, pk_cols = _fetch_pg_primary_key(cursor, oid)

        full_tbl = f"{_pg_quote(schema)}.{_pg_quote(table_name)}"
        set_lines = []
        for c in columns:
            cname = c["name"]
            if cname in pk_cols:
                continue
            if c.get("identity_type") == "a" or c.get("generated_type") == "s":
                continue
            val = _format_pg_insert_value(c)
            if val == "DEFAULT":
                ftype = c.get("data_type", "").lower()
                val = "1" if any(t in ftype for t in ("int", "num", "serial")) else f"'{cname.title()}'"
            set_lines.append(f"    {_pg_quote(cname)} = {val}")

        if pk_cols:
            where_cond = " AND ".join(f"{_pg_quote(pk)} = 1" for pk in pk_cols)
            where_line = f"WHERE {where_cond};"
            header = f"-- Update Script for {full_tbl}\n-- Primary Key: {', '.join(pk_cols)}"
        else:
            where_line = "WHERE /* <specify condition> */ 1 = 1;"
            header = f"-- Update Script for {full_tbl}\n-- Note: No primary key detected; specify WHERE condition"

        if not set_lines:
            set_lines = ["    -- No editable non-PK columns found"]

        set_block = ",\n".join(set_lines)
        return f"{header}\n\nUPDATE {full_tbl}\nSET\n{set_block}\n{where_line}"

