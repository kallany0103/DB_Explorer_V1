import os
import json
import sqlite3
import psycopg2

from db.db_connections import (
    create_postgres_connection,
    create_sqlite_connection
)
from db.schema_retrieval import (
    get_postgres_schema,
    get_sqlite_schema,
    get_postgres_available_schemas
)


def _normalize_type(data_type: str) -> str:
    """Normalizes database data types into common comparable type categories."""
    if not data_type:
        return "UNKNOWN"
    dt = str(data_type).upper().strip()

    if any(k in dt for k in ("INT", "SERIAL", "NUMBER", "COUNTER")):
        return "INTEGER"
    if any(k in dt for k in ("CHAR", "TEXT", "CLOB", "STRING", "VARCHAR")):
        return "VARCHAR"
    if any(k in dt for k in ("FLOAT", "DOUBLE", "REAL", "NUMERIC", "DECIMAL")):
        return "DECIMAL"
    if any(k in dt for k in ("TIME", "DATE", "TIMESTAMP")):
        return "TIMESTAMP"
    if any(k in dt for k in ("BOOL", "BIT", "BOOLEAN")):
        return "BOOLEAN"
    if any(k in dt for k in ("BLOB", "BYTEA", "BINARY", "RAW")):
        return "BLOB"
    if "JSON" in dt:
        return "JSON"

    return dt


def introspect_schema_metadata(conn_data: dict, schema_name: str = None) -> dict:
    """
    Introspects table structures, columns, types, nullability, and primary keys
    for a given database connection and schema.
    Returns: dict of table_name -> { "columns": { col_name: { "type": str, "nullable": bool, "pk": bool, "raw_type": str } } }
    """
    db_type = (conn_data.get("db_type") or conn_data.get("source_type") or "postgres").lower()
    tables_meta = {}

    if "sqlite" in db_type:
        db_path = conn_data.get("db_path") or conn_data.get("file_path")
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as s_conn:
                    s_cur = s_conn.cursor()
                    s_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    table_names = [r[0] for r in s_cur.fetchall()]

                    for tbl in table_names:
                        s_cur.execute(f"PRAGMA table_info('{tbl}');")
                        cols = {}
                        for col in s_cur.fetchall():
                            # col: (cid, name, type, notnull, dflt_value, pk)
                            col_name = col[1]
                            raw_type = col[2] or "TEXT"
                            not_null = bool(col[3])
                            is_pk = bool(col[5])
                            cols[col_name] = {
                                "name": col_name,
                                "raw_type": raw_type,
                                "normalized_type": _normalize_type(raw_type),
                                "nullable": not not_null,
                                "pk": is_pk
                            }
                        tables_meta[tbl] = {"columns": cols}
            except Exception as e:
                print(f"Error introspecting SQLite schema: {e}")

    else:
        # PostgreSQL / Host FDW Connection
        target_schema = schema_name or conn_data.get("schema_name") or conn_data.get("schema") or "public"
        try:
            pg_conn = create_postgres_connection(
                conn_data,
                application_name="Universal SQL Client (Schema Diff Introspect)",
                bypass_cooldown=True
            )
            if pg_conn:
                cur = pg_conn.cursor()
                cur.execute("""
                    SELECT c.table_name, c.column_name, c.data_type, c.is_nullable,
                           c.udt_name, c.column_default,
                           COALESCE(tc.constraint_type = 'PRIMARY KEY', FALSE) AS is_pk
                    FROM information_schema.columns c
                    LEFT JOIN information_schema.key_column_usage kcu
                           ON c.table_schema = kcu.table_schema
                          AND c.table_name = kcu.table_name
                          AND c.column_name = kcu.column_name
                    LEFT JOIN information_schema.table_constraints tc
                           ON kcu.constraint_name = tc.constraint_name
                          AND kcu.table_schema = tc.table_schema
                          AND tc.constraint_type = 'PRIMARY KEY'
                    WHERE c.table_schema = %s
                    ORDER BY c.table_name, c.ordinal_position;
                """, (target_schema,))

                for row in cur.fetchall():
                    tbl_name, col_name, data_type, is_null, udt_name, dflt, is_pk = row
                    raw_type = udt_name or data_type or "VARCHAR"
                    nullable = (is_null == "YES")

                    if tbl_name not in tables_meta:
                        tables_meta[tbl_name] = {"columns": {}}

                    tables_meta[tbl_name]["columns"][col_name] = {
                        "name": col_name,
                        "raw_type": raw_type.upper(),
                        "normalized_type": _normalize_type(raw_type),
                        "nullable": nullable,
                        "pk": is_pk
                    }

                cur.close()
                pg_conn.close()
        except Exception as e:
            print(f"Error introspecting PostgreSQL schema '{target_schema}': {e}")

    return tables_meta


def compare_schemas(source_meta: dict, target_meta: dict) -> dict:
    """
    Compares Source metadata vs Target metadata.
    Returns structured diff metrics, table-by-table comparisons, and column diffs.
    """
    source_tables = set(source_meta.keys())
    target_tables = set(target_meta.keys())

    common_tables = source_tables.intersection(target_tables)
    missing_in_target = sorted(list(source_tables - target_tables))
    missing_in_source = sorted(list(target_tables - source_tables))

    table_diffs = []
    matched_count = 0
    mismatch_count = 0

    for tbl in sorted(list(source_tables.union(target_tables))):
        if tbl in missing_in_target:
            table_diffs.append({
                "table_name": tbl,
                "status": "MISSING IN TARGET",
                "source_columns": source_meta.get(tbl, {}).get("columns", {}),
                "target_columns": {},
                "column_diffs": []
            })
            mismatch_count += 1
        elif tbl in missing_in_source:
            table_diffs.append({
                "table_name": tbl,
                "status": "MISSING IN SOURCE",
                "source_columns": {},
                "target_columns": target_meta.get(tbl, {}).get("columns", {}),
                "column_diffs": []
            })
            mismatch_count += 1
        else:
            s_cols = source_meta[tbl]["columns"]
            t_cols = target_meta[tbl]["columns"]

            all_col_names = sorted(list(set(s_cols.keys()).union(set(t_cols.keys()))))
            col_diffs = []
            has_table_mismatch = False

            for c_name in all_col_names:
                if c_name not in t_cols:
                    col_diffs.append({
                        "column_name": c_name,
                        "status": "MISSING IN TARGET",
                        "source_type": s_cols[c_name]["raw_type"],
                        "target_type": "N/A",
                        "source_nullable": s_cols[c_name]["nullable"],
                        "target_nullable": None
                    })
                    has_table_mismatch = True
                elif c_name not in s_cols:
                    col_diffs.append({
                        "column_name": c_name,
                        "status": "MISSING IN SOURCE",
                        "source_type": "N/A",
                        "target_type": t_cols[c_name]["raw_type"],
                        "source_nullable": None,
                        "target_nullable": t_cols[c_name]["nullable"]
                    })
                    has_table_mismatch = True
                else:
                    s_info = s_cols[c_name]
                    t_info = t_cols[c_name]

                    type_match = (s_info["normalized_type"] == t_info["normalized_type"])
                    null_match = (s_info["nullable"] == t_info["nullable"])

                    if not type_match:
                        col_diffs.append({
                            "column_name": c_name,
                            "status": "TYPE MISMATCH",
                            "source_type": s_info["raw_type"],
                            "target_type": t_info["raw_type"],
                            "source_nullable": s_info["nullable"],
                            "target_nullable": t_info["nullable"]
                        })
                        has_table_mismatch = True
                    elif not null_match:
                        col_diffs.append({
                            "column_name": c_name,
                            "status": "NULLABILITY MISMATCH",
                            "source_type": s_info["raw_type"],
                            "target_type": t_info["raw_type"],
                            "source_nullable": s_info["nullable"],
                            "target_nullable": t_info["nullable"]
                        })
                        has_table_mismatch = True
                    else:
                        col_diffs.append({
                            "column_name": c_name,
                            "status": "MATCH",
                            "source_type": s_info["raw_type"],
                            "target_type": t_info["raw_type"],
                            "source_nullable": s_info["nullable"],
                            "target_nullable": t_info["nullable"]
                        })

            if has_table_mismatch:
                mismatch_count += 1
                tbl_status = "MISMATCH"
            else:
                matched_count += 1
                tbl_status = "MATCH"

            table_diffs.append({
                "table_name": tbl,
                "status": tbl_status,
                "source_columns": s_cols,
                "target_columns": t_cols,
                "column_diffs": col_diffs
            })

    return {
        "matched_count": matched_count,
        "mismatch_count": mismatch_count,
        "missing_target_count": len(missing_in_target),
        "missing_source_count": len(missing_in_source),
        "table_diffs": table_diffs
    }


def generate_ddl_migration_script(diff_result: dict, target_schema: str = "public") -> str:
    """
    Generates ready-to-run DDL migration SQL script for the target database.
    """
    sql_lines = [
        f"-- ========================================================",
        f"-- AUTOMATIC DDL MIGRATION SCRIPT",
        f"-- Target Schema: {target_schema}",
        f"-- Generated by DB Explorer V1 Schema Diff Tool",
        f"-- ========================================================\n"
    ]

    statements_count = 0

    for tbl_diff in diff_result.get("table_diffs", []):
        tbl = tbl_diff["table_name"]
        status = tbl_diff["status"]

        if status == "MISSING IN TARGET":
            s_cols = tbl_diff.get("source_columns", {})
            if s_cols:
                sql_lines.append(f"-- 1. Create missing table: {tbl}")
                col_defs = []
                pk_cols = []
                for c_name, c_info in s_cols.items():
                    c_type = c_info.get("raw_type", "VARCHAR(255)")
                    null_str = "" if c_info.get("nullable", True) else " NOT NULL"
                    col_defs.append(f"    \"{c_name}\" {c_type}{null_str}")
                    if c_info.get("pk"):
                        pk_cols.append(f"\"{c_name}\"")

                if pk_cols:
                    col_defs.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

                sql_lines.append(f"CREATE TABLE IF NOT EXISTS \"{target_schema}\".\"{tbl}\" (")
                sql_lines.append(",\n".join(col_defs))
                sql_lines.append(");\n")
                statements_count += 1

        elif status == "MISMATCH":
            col_diffs = tbl_diff.get("column_diffs", [])
            for c_diff in col_diffs:
                c_status = c_diff["status"]
                c_name = c_diff["column_name"]

                if c_status == "MISSING IN TARGET":
                    s_type = c_diff.get("source_type", "VARCHAR(255)")
                    null_str = "" if c_diff.get("source_nullable", True) else " NOT NULL"
                    sql_lines.append(f"-- Add missing column '{c_name}' to table '{tbl}'")
                    sql_lines.append(f"ALTER TABLE \"{target_schema}\".\"{tbl}\" ADD COLUMN \"{c_name}\" {s_type}{null_str};\n")
                    statements_count += 1
                elif c_status == "TYPE MISMATCH":
                    s_type = c_diff.get("source_type", "VARCHAR(255)")
                    sql_lines.append(f"-- Alter column '{c_name}' type in table '{tbl}'")
                    sql_lines.append(f"ALTER TABLE \"{target_schema}\".\"{tbl}\" ALTER COLUMN \"{c_name}\" TYPE {s_type};\n")
                    statements_count += 1

    if statements_count == 0:
        sql_lines.append("-- No DDL migration statements required. Schemas are in sync!")

    return "\n".join(sql_lines)
