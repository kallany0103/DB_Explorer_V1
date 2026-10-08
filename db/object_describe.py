"""
db/object_describe.py
Provides metadata inspection and describe functionality for database tables, views,
and schemas across Oracle, PostgreSQL, SQLite, and other supported engines.
Modeled after the "Describe (F4)" feature in Toad for Oracle.
"""

import re
import db
from db.result_metadata import _description_value


def parse_object_identifier(raw: str) -> tuple[str | None, str]:
    """
    Parses a raw object identifier string into (schema_name, object_name).
    Handles unquoted, double-quoted, bracketed, and backticked identifiers,
    as well as partially-selected or unbalanced quoted tokens (e.g. Emam"."credential).
    E.g.:
      'employees' -> (None, 'employees')
      'hr.employees' -> ('hr', 'employees')
      '"Emam"."credential"' -> ('Emam', 'credential')
      'Emam"."credential' -> ('Emam', 'credential')
      '[dbo].[Orders]' -> ('dbo', 'Orders')
    """
    raw = raw.strip().rstrip(";")
    desc_match = re.match(r"^(?:DESCRIBE|DESC)\s+(.+)$", raw, re.IGNORECASE)
    if desc_match:
        raw = desc_match.group(1).strip().rstrip(";")

    # Split by dot outside quotes
    tokens = []
    current = []
    in_quote = None
    for char in raw:
        if in_quote:
            current.append(char)
            if (in_quote == '"' and char == '"') or \
               (in_quote == '`' and char == '`') or \
               (in_quote == '[' and char == ']'):
                in_quote = None
        else:
            if char in ('"', '`', '['):
                in_quote = char
                current.append(char)
            elif char == '.':
                tokens.append("".join(current).strip())
                current = []
            else:
                current.append(char)
    if current:
        tokens.append("".join(current).strip())

    # Fallback if quotes were unbalanced or tokens length <= 1 and raw contains dot
    if in_quote is not None or (len(tokens) <= 1 and "." in raw):
        tokens = [p.strip() for p in raw.split(".") if p.strip()]

    cleaned = []
    for t in tokens:
        clean_t = t.strip(' "`[]\'')
        if clean_t:
            cleaned.append(clean_t)

    if not cleaned:
        return None, ""
    if len(cleaned) == 1:
        return None, cleaned[0]
    elif len(cleaned) == 2:
        return cleaned[0], cleaned[1]
    else:
        return cleaned[-2], cleaned[-1]


def _detect_db_code(conn_data: dict) -> str:
    code = (conn_data.get("code") or conn_data.get("type") or "").upper()
    if not code:
        if conn_data.get("service_name") or "oracle" in str(conn_data.get("driver", "")).lower():
            code = "ORACLE"
        elif conn_data.get("host"):
            code = "POSTGRES"
        elif conn_data.get("db_path"):
            code = "SQLITE"
    return code


def generate_object_scripts(meta: dict) -> dict[str, str]:
    """
    Generates a full suite of Toad for Oracle-style scripts for the described object:
    - 'Full DDL': Complete production DDL (Table, PK, FK, Checks, Indexes, Triggers, Comments, Grants)
    - 'Drop & Recreate': Drop statement followed by Full DDL
    - 'SELECT Query': Formatted SELECT statement listing all columns
    - 'INSERT Statement': Parameterized INSERT template
    - 'UPDATE Statement': Parameterized UPDATE template keyed by Primary Key
    - 'DELETE Statement': Parameterized DELETE template keyed by Primary Key
    - 'MERGE / Upsert Statement': Engine-specific MERGE or ON CONFLICT template
    - 'TRUNCATE Statement': TRUNCATE TABLE statement
    - 'Record Count & Stats': Query for total rows and key distinct counts
    - 'All Scripts Combined': Master script containing all DDL and DML scripts with banners
    """
    target_type = meta.get("target_type", "table")
    obj_type = meta.get("object_type", "Table")
    obj_name = meta.get("name", "")
    schema_name = meta.get("schema", "")
    db_code = (meta.get("db_code") or "").upper()
    full_quoted = f'"{schema_name}"."{obj_name}"' if schema_name else f'"{obj_name}"'

    columns = meta.get("columns", [])
    constraints = meta.get("constraints", [])
    indexes = meta.get("indexes", [])
    triggers = meta.get("triggers", [])
    tbl_comment = meta.get("details", {}).get("Comment", "")

    scripts = {}

    if target_type == "schema":
        schema_ddl = meta.get("ddl", f'CREATE SCHEMA "{obj_name}";')
        if db_code in ("ORACLE", "ORACLE_DB"):
            drop_ddl = f'DROP USER "{obj_name}" CASCADE;'
            stats_query = (
                f"SELECT OBJECT_TYPE, COUNT(*) AS OBJECT_COUNT\n"
                f"FROM ALL_OBJECTS\n"
                f"WHERE OWNER = '{obj_name}'\n"
                f"GROUP BY OBJECT_TYPE\n"
                f"ORDER BY 1;"
            )
        elif db_code == "SQLITE":
            drop_ddl = f"-- SQLite database file: {obj_name}"
            stats_query = (
                f"SELECT type AS object_type, COUNT(*) AS object_count\n"
                f"FROM sqlite_master\n"
                f"WHERE name NOT LIKE 'sqlite_%'\n"
                f"GROUP BY type\n"
                f"ORDER BY 1;"
            )
        else:
            drop_ddl = f'DROP SCHEMA IF EXISTS "{obj_name}" CASCADE;'
            stats_query = (
                f"SELECT table_type, COUNT(*) AS object_count\n"
                f"FROM information_schema.tables\n"
                f"WHERE table_schema = '{obj_name}'\n"
                f"GROUP BY table_type\n"
                f"ORDER BY 1;"
            )

        scripts["Full DDL"] = schema_ddl
        scripts["Drop & Recreate"] = f"{drop_ddl}\n\n{schema_ddl}"
        scripts["Schema Objects Query"] = stats_query
        scripts["All Scripts Combined"] = (
            f"-- =========================================================================\n"
            f"-- 1. FULL SCHEMA DDL\n"
            f"-- =========================================================================\n"
            f"{schema_ddl}\n\n"
            f"-- =========================================================================\n"
            f"-- 2. DROP SCHEMA STATEMENT\n"
            f"-- =========================================================================\n"
            f"{drop_ddl}\n\n"
            f"-- =========================================================================\n"
            f"-- 3. SCHEMA OBJECTS & STATISTICS QUERY\n"
            f"-- =========================================================================\n"
            f"{stats_query}\n"
        )
        return scripts

    if target_type == "view":
        view_ddl = meta.get("ddl", f'CREATE VIEW {full_quoted} AS SELECT 1;')
        if db_code in ("ORACLE", "ORACLE_DB"):
            drop_ddl = f'DROP VIEW {full_quoted};'
        else:
            drop_ddl = f'DROP VIEW IF EXISTS {full_quoted} CASCADE;'

        col_names = [f'    "{c["name"]}"' for c in columns]
        select_sql = f'SELECT\n' + ",\n".join(col_names) + f'\nFROM {full_quoted};' if col_names else f'SELECT * FROM {full_quoted};'
        count_sql = f'SELECT COUNT(*) AS total_rows FROM {full_quoted};'

        scripts["Full DDL"] = view_ddl
        scripts["Drop & Recreate"] = f"{drop_ddl}\n\n{view_ddl}"
        scripts["SELECT Query"] = select_sql
        scripts["Record Count Query"] = count_sql
        scripts["All Scripts Combined"] = (
            f"-- =========================================================================\n"
            f"-- 1. VIEW DDL\n"
            f"-- =========================================================================\n"
            f"{view_ddl}\n\n"
            f"-- =========================================================================\n"
            f"-- 2. SELECT QUERY\n"
            f"-- =========================================================================\n"
            f"{select_sql}\n\n"
            f"-- =========================================================================\n"
            f"-- 3. RECORD COUNT QUERY\n"
            f"-- =========================================================================\n"
            f"{count_sql}\n"
        )
        return scripts

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE SCRIPTS (Toad for Oracle Style Suite)
    # ─────────────────────────────────────────────────────────────────────────
    # 1. Full DDL
    ddl_sections = [
        f"-- -----------------------------------------------------------------------------",
        f"-- Object:    {full_quoted}",
        f"-- Type:      {obj_type}",
        f"-- Database:  {db_code or 'RELATIONAL'}",
        f"-- Generated: Toad for Oracle-style Object Describe",
        f"-- -----------------------------------------------------------------------------",
        f"",
    ]

    if db_code in ("ORACLE", "ORACLE_DB"):
        drop_table_syntax = f"DROP TABLE {full_quoted} CASCADE CONSTRAINTS PURGE;"
    elif db_code == "SQLITE":
        drop_table_syntax = f"DROP TABLE IF EXISTS {full_quoted};"
    else:
        drop_table_syntax = f"DROP TABLE IF EXISTS {full_quoted} CASCADE;"

    ddl_sections.append(f"-- Drop statement:")
    ddl_sections.append(f"-- {drop_table_syntax}")
    ddl_sections.append("")
    ddl_sections.append(f"CREATE TABLE {full_quoted} (")

    col_lines = []
    max_name_len = max([len(c["name"]) for c in columns]) if columns else 10
    padding = max(max_name_len + 4, 16)

    for c in columns:
        col_name_str = f'"{c["name"]}"'.ljust(padding)
        type_str = c.get("data_type", "TEXT")
        def_str = f" DEFAULT {c['default']}" if c.get("default") else ""
        null_str = "" if c.get("nullable", True) else " NOT NULL"
        col_lines.append(f"    {col_name_str} {type_str}{def_str}{null_str}")

    # Primary key constraint inside CREATE TABLE
    pk_cst = next((cst for cst in constraints if cst.get("type") == "Primary Key"), None)
    pk_cols = [c["name"] for c in columns if c.get("is_pk")]
    if not pk_cols and pk_cst:
        import re
        m = re.search(r'\((.+?)\)', pk_cst.get("definition", ""))
        if m:
            pk_cols = [x.strip().strip('"\'`') for x in m.group(1).split(",") if x.strip()]

    if pk_cst:
        pk_name = pk_cst.get("name", f"PK_{obj_name}")
        pk_def = pk_cst.get("definition", "")
        if not pk_def.upper().startswith("PRIMARY"):
            pk_def = f"PRIMARY KEY ({pk_def})"
        col_lines.append(f'    CONSTRAINT "{pk_name}" {pk_def}')
    elif pk_cols:
        pk_cols_str = ", ".join([f'"{p}"' for p in pk_cols])
        col_lines.append(f'    CONSTRAINT "PK_{obj_name}" PRIMARY KEY ({pk_cols_str})')

    ddl_sections.append(",\n".join(col_lines))
    ddl_sections.append(");")

    # Table & Column Comments
    comment_lines = []
    if tbl_comment:
        comment_lines.append(f"COMMENT ON TABLE {full_quoted} IS '{tbl_comment}';")
    for c in columns:
        if c.get("comment"):
            comment_lines.append(f'COMMENT ON COLUMN {full_quoted}."{c["name"]}" IS \'{c["comment"]}\';')
    if comment_lines:
        ddl_sections.append("\n-- Comments:")
        ddl_sections.extend(comment_lines)

    # Unique, Check & Foreign Key Constraints
    other_csts = [cst for cst in constraints if cst.get("type") != "Primary Key"]
    if other_csts:
        ddl_sections.append("\n-- Constraints:")
        for cst in other_csts:
            cst_name = cst.get("name", "CST")
            cst_def = cst.get("definition", "")
            ddl_sections.append(f'ALTER TABLE {full_quoted}\n    ADD CONSTRAINT "{cst_name}" {cst_def};')

    # Indexes
    idx_lines = []
    for idx in indexes:
        idx_def = idx.get("definition", "")
        if idx_def and idx_def.strip():
            stmt = idx_def.strip()
            if not stmt.endswith(";"):
                stmt += ";"
            idx_lines.append(stmt)
        elif idx.get("name"):
            uniq_str = "UNIQUE " if idx.get("unique") else ""
            idx_lines.append(f'CREATE {uniq_str}INDEX "{idx.get("name")}" ON {full_quoted};')
    if idx_lines:
        ddl_sections.append("\n-- Indexes:")
        ddl_sections.extend(idx_lines)

    # Triggers
    trg_lines = []
    for trg in triggers:
        t_def = trg.get("definition", "")
        if t_def:
            stmt = t_def.strip()
            if not stmt.endswith(";"):
                stmt += ";"
            trg_lines.append(stmt)
    if trg_lines:
        ddl_sections.append("\n-- Triggers:")
        ddl_sections.extend(trg_lines)

    # Grants
    ddl_sections.append("\n-- Grants:")
    ddl_sections.append(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {full_quoted} TO PUBLIC;")

    full_ddl = "\n".join(ddl_sections)

    # 2. Drop & Recreate
    recreate_ddl = f"{drop_table_syntax}\n\n{full_ddl}"

    # 3. SELECT Query
    if columns:
        sel_cols = [f'    "{c["name"]}"' for c in columns]
        select_sql = f"SELECT\n" + ",\n".join(sel_cols) + f"\nFROM {full_quoted};"
    else:
        select_sql = f"SELECT * FROM {full_quoted};"

    # 4. INSERT Statement
    if columns:
        ins_cols = [f'    "{c["name"]}"' for c in columns]
        ins_vals = [f'    :{c["name"]}' for c in columns]
        insert_sql = (
            f"INSERT INTO {full_quoted} (\n"
            + ",\n".join(ins_cols)
            + f"\n) VALUES (\n"
            + ",\n".join(ins_vals)
            + f"\n);"
        )
    else:
        insert_sql = f"INSERT INTO {full_quoted} DEFAULT VALUES;"

    # 5. UPDATE Statement
    non_pk_cols = [c["name"] for c in columns if c["name"] not in pk_cols]
    if not non_pk_cols:
        non_pk_cols = [c["name"] for c in columns]

    upd_sets = [f'    "{c}" = :{c}' for c in non_pk_cols]
    where_clauses = [f'    "{c}" = :{c}' for c in pk_cols] if pk_cols else ["    /* <specify condition> */ 1 = 1"]
    update_sql = (
        f"UPDATE {full_quoted}\nSET\n"
        + ",\n".join(upd_sets)
        + f"\nWHERE\n"
        + " AND\n".join(where_clauses)
        + ";"
    )

    # 6. DELETE Statement
    del_wheres = [f'    "{c}" = :{c}' for c in pk_cols] if pk_cols else ["    /* <specify condition> */ 1 = 1"]
    delete_sql = (
        f"DELETE FROM {full_quoted}\nWHERE\n"
        + " AND\n".join(del_wheres)
        + ";"
    )

    # 7. MERGE / Upsert Statement (Toad for Oracle Style)
    if db_code in ("ORACLE", "ORACLE_DB"):
        if pk_cols:
            source_cols = [f'        :{c["name"]} AS "{c["name"]}"' for c in columns]
            join_conds = [f'target."{c}" = source."{c}"' for c in pk_cols]
            m_upd_sets = [f'        target."{c}" = source."{c}"' for c in non_pk_cols]
            m_ins_cols = [f'        "{c["name"]}"' for c in columns]
            m_ins_vals = [f'        source."{c["name"]}"' for c in columns]
            merge_sql = (
                f"MERGE INTO {full_quoted} target\n"
                f"USING (\n"
                f"    SELECT\n"
                + ",\n".join(source_cols)
                + f"\n    FROM DUAL\n"
                f") source\n"
                f"ON (" + " AND ".join(join_conds) + ")\n"
                f"WHEN MATCHED THEN\n"
                f"    UPDATE SET\n"
                + ",\n".join(m_upd_sets)
                + f"\nWHEN NOT MATCHED THEN\n"
                f"    INSERT (\n"
                + ",\n".join(m_ins_cols)
                + f"\n    ) VALUES (\n"
                + ",\n".join(m_ins_vals)
                + f"\n    );"
            )
        else:
            merge_sql = f"-- MERGE requires a Primary Key or Unique constraint on {full_quoted};\n"
    elif db_code in ("POSTGRES", "POSTGRESQL"):
        if pk_cols and columns:
            p_ins_cols = [f'    "{c["name"]}"' for c in columns]
            p_ins_vals = [f'    :{c["name"]}' for c in columns]
            p_pk_conflict = ", ".join([f'"{p}"' for p in pk_cols])
            p_upd_sets = [f'    "{c}" = EXCLUDED."{c}"' for c in non_pk_cols]
            merge_sql = (
                f"INSERT INTO {full_quoted} (\n"
                + ",\n".join(p_ins_cols)
                + f"\n) VALUES (\n"
                + ",\n".join(p_ins_vals)
                + f"\n)\n"
                f"ON CONFLICT ({p_pk_conflict})\n"
                f"DO UPDATE SET\n"
                + ",\n".join(p_upd_sets)
                + f";"
            )
        else:
            merge_sql = f"-- Upsert requires a Primary Key on {full_quoted};\n"
    else:  # SQLite / Generic
        if columns:
            sq_ins_cols = [f'    "{c["name"]}"' for c in columns]
            sq_ins_vals = [f'    :{c["name"]}' for c in columns]
            merge_sql = (
                f"INSERT OR REPLACE INTO {full_quoted} (\n"
                + ",\n".join(sq_ins_cols)
                + f"\n) VALUES (\n"
                + ",\n".join(sq_ins_vals)
                + f"\n);"
            )
        else:
            merge_sql = f"INSERT OR REPLACE INTO {full_quoted} DEFAULT VALUES;"

    # 8. TRUNCATE Statement
    truncate_sql = f"TRUNCATE TABLE {full_quoted};"

    # 9. Record Count & Stats Query
    if pk_cols:
        count_stats_sql = (
            f"SELECT\n"
            f"    COUNT(*) AS total_rows,\n"
            f"    COUNT(DISTINCT \"{pk_cols[0]}\") AS distinct_primary_keys\n"
            f"FROM {full_quoted};"
        )
    else:
        count_stats_sql = f"SELECT COUNT(*) AS total_rows FROM {full_quoted};"

    # 10. All Combined
    combined_sql = (
        f"-- =========================================================================\n"
        f"-- 1. FULL DDL SCRIPT\n"
        f"-- =========================================================================\n"
        f"{full_ddl}\n\n"
        f"-- =========================================================================\n"
        f"-- 2. DROP & RECREATE SCRIPT\n"
        f"-- =========================================================================\n"
        f"{recreate_ddl}\n\n"
        f"-- =========================================================================\n"
        f"-- 3. SELECT STATEMENT\n"
        f"-- =========================================================================\n"
        f"{select_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 4. INSERT STATEMENT\n"
        f"-- =========================================================================\n"
        f"{insert_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 5. UPDATE STATEMENT\n"
        f"-- =========================================================================\n"
        f"{update_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 6. DELETE STATEMENT\n"
        f"-- =========================================================================\n"
        f"{delete_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 7. MERGE / UPSERT STATEMENT\n"
        f"-- =========================================================================\n"
        f"{merge_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 8. TRUNCATE STATEMENT\n"
        f"-- =========================================================================\n"
        f"{truncate_sql}\n\n"
        f"-- =========================================================================\n"
        f"-- 9. RECORD COUNT & STATS QUERY\n"
        f"-- =========================================================================\n"
        f"{count_stats_sql}\n"
    )

    scripts["Full DDL"] = full_ddl
    scripts["Drop & Recreate"] = recreate_ddl
    scripts["SELECT Query"] = select_sql
    scripts["INSERT Statement"] = insert_sql
    scripts["UPDATE Statement"] = update_sql
    scripts["DELETE Statement"] = delete_sql
    scripts["MERGE / Upsert Statement"] = merge_sql
    scripts["TRUNCATE Statement"] = truncate_sql
    scripts["Record Count & Stats"] = count_stats_sql
    scripts["All Scripts Combined"] = combined_sql

    return scripts


# ─────────────────────────────────────────────────────────────────────────────
# POSTGRESQL DESCRIBE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
def _describe_postgres(conn_data: dict, schema_hint: str | None, object_name: str) -> dict:
    conn = db.create_postgres_connection(
        conn_data,
        application_name="Universal SQL Client (Object Describe)",
        bypass_cooldown=True
    )
    if not conn:
        raise ConnectionError("Failed to connect to PostgreSQL database.")

    cursor = conn.cursor()
    try:
        # Check if the target is a schema (only if schema_hint is None)
        if not schema_hint:
            cursor.execute("SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s", (object_name,))
            schema_row = cursor.fetchone()
            if schema_row:
                # Target is a schema!
                return _describe_postgres_schema(cursor, object_name, schema_row[1])

        # Otherwise target is treated as a table or view
        effective_schema = schema_hint or "public"

        # Check table / view existence in pg_class (exact match or case-insensitive match)
        cursor.execute("""
            SELECT c.oid, c.relkind, pg_get_userbyid(c.relowner), n.nspname,
                   c.reltuples::bigint, pg_size_pretty(pg_total_relation_size(c.oid)),
                   obj_description(c.oid, 'pg_class'), c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE (n.nspname = %s OR lower(n.nspname) = lower(%s))
              AND (c.relname = %s OR lower(c.relname) = lower(%s))
            ORDER BY (n.nspname = %s AND c.relname = %s) DESC,
                     (lower(n.nspname) = lower(%s) AND lower(c.relname) = lower(%s)) DESC
            LIMIT 1;
        """, (effective_schema, effective_schema, object_name, object_name,
              effective_schema, object_name, effective_schema, object_name))
        tbl_row = cursor.fetchone()

        if not tbl_row:
            # Try finding table in any non-system schema (case-insensitive)
            cursor.execute("""
                SELECT c.oid, c.relkind, pg_get_userbyid(c.relowner), n.nspname,
                       c.reltuples::bigint, pg_size_pretty(pg_total_relation_size(c.oid)),
                       obj_description(c.oid, 'pg_class'), c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE (c.relname = %s OR lower(c.relname) = lower(%s))
                  AND n.nspname NOT LIKE 'pg_%%' AND n.nspname != 'information_schema'
                ORDER BY (c.relname = %s) DESC, (n.nspname = 'public') DESC
                LIMIT 1;
            """, (object_name, object_name, object_name))
            tbl_row = cursor.fetchone()

        if not tbl_row:
            # Check if either candidate is a schema
            for candidate in (object_name, schema_hint):
                if candidate:
                    cursor.execute("""
                        SELECT nspname, pg_get_userbyid(nspowner)
                        FROM pg_namespace
                        WHERE nspname = %s OR lower(nspname) = lower(%s)
                        ORDER BY (nspname = %s) DESC
                        LIMIT 1;
                    """, (candidate, candidate, candidate))
                    schema_row = cursor.fetchone()
                    if schema_row:
                        return _describe_postgres_schema(cursor, schema_row[0], schema_row[1])

            target_display = f'"{schema_hint}"."{object_name}"' if schema_hint else f'"{object_name}"'
            raise ValueError(f"Table or Schema '{target_display}' not found in database.")

        oid, relkind, owner, schema_name, row_est, total_size, comment, actual_relname = tbl_row
        relkind_map = {
            'r': 'Table',
            'p': 'Partitioned table',
            'v': 'View',
            'm': 'Materialized view',
            'f': 'Foreign table',
            'S': 'Sequence'
        }
        obj_type = relkind_map.get(relkind, 'Table')

        # 1. Fetch Columns
        cursor.execute("""
            SELECT 
                a.attnum,
                a.attname,
                pg_catalog.format_type(a.atttypid, a.atttypmod) as data_type,
                NOT a.attnotnull as nullable,
                pg_get_expr(d.adbin, d.adrelid) as default_val,
                EXISTS (
                    SELECT 1 FROM pg_constraint pk
                    WHERE pk.contype = 'p' AND pk.conrelid = a.attrelid AND a.attnum = ANY(pk.conkey)
                ) as is_pk,
                EXISTS (
                    SELECT 1 FROM pg_constraint fk
                    WHERE fk.contype = 'f' AND fk.conrelid = a.attrelid AND a.attnum = ANY(fk.conkey)
                ) as is_fk,
                col_description(a.attrelid, a.attnum) as comment
            FROM pg_attribute a
            LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
            WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum;
        """, (oid,))
        columns = []
        for r in cursor.fetchall():
            columns.append({
                "position": r[0],
                "name": r[1],
                "data_type": r[2],
                "nullable": bool(r[3]),
                "default": r[4] or "",
                "is_pk": bool(r[5]),
                "is_fk": bool(r[6]),
                "comment": r[7] or "",
            })

        # 2. Fetch Indexes
        cursor.execute("""
            SELECT
                i.relname AS index_name,
                pg_get_indexdef(ix.indexrelid, 0, true) AS index_def,
                ix.indisunique AS is_unique,
                am.amname AS index_type
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_am am ON am.oid = i.relam
            WHERE ix.indrelid = %s
            ORDER BY i.relname;
        """, (oid,))
        indexes = []
        for r in cursor.fetchall():
            indexes.append({
                "name": r[0],
                "definition": r[1] or "",
                "unique": bool(r[2]),
                "type": r[3] or "btree"
            })

        # 3. Fetch Constraints
        cursor.execute("""
            SELECT 
                conname,
                CASE contype
                    WHEN 'p' THEN 'Primary Key'
                    WHEN 'f' THEN 'Foreign Key'
                    WHEN 'u' THEN 'Unique'
                    WHEN 'c' THEN 'Check'
                    ELSE contype::text
                END,
                pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = %s
            ORDER BY conname;
        """, (oid,))
        constraints = []
        for r in cursor.fetchall():
            constraints.append({
                "name": r[0],
                "type": r[1],
                "definition": r[2] or ""
            })

        # 3b. Fetch Triggers
        triggers = []
        try:
            cursor.execute("""
                SELECT tgname, pg_get_triggerdef(oid, true)
                FROM pg_trigger
                WHERE tgrelid = %s AND NOT tgisinternal
                ORDER BY tgname;
            """, (oid,))
            for r in cursor.fetchall():
                triggers.append({
                    "name": r[0],
                    "definition": r[1] or ""
                })
        except Exception:
            triggers = []

        # 4. Fetch Sample Data (up to 50 rows)
        sample_headers = [c["name"] for c in columns]
        sample_rows = []
        try:
            full_quoted_name = f'"{schema_name}"."{actual_relname}"'
            cursor.execute(f"SELECT * FROM {full_quoted_name} LIMIT 50")
            sample_rows = cursor.fetchall()
        except Exception:
            sample_rows = []

        # 5. Build DDL Script
        ddl_lines = [f"CREATE {obj_type.upper()} \"{schema_name}\".\"{actual_relname}\" ("]
        col_defs = []
        for c in columns:
            null_str = "" if c["nullable"] else " NOT NULL"
            def_str = f" DEFAULT {c['default']}" if c["default"] else ""
            col_defs.append(f"    \"{c['name']}\" {c['data_type']}{def_str}{null_str}")
        for cst in constraints:
            if cst["type"] == "Primary Key":
                col_defs.append(f"    CONSTRAINT \"{cst['name']}\" {cst['definition']}")
        ddl_lines.append(",\n".join(col_defs))
        ddl_lines.append(");")
        ddl_script = "\n".join(ddl_lines)

        # 6. Fetch Parent Schema Details (so both table & schema are described together)
        schema_info = None
        try:
            schema_info = _describe_postgres_schema(cursor, schema_name, owner)
        except Exception:
            schema_info = None

        return {
            "target_type": "table" if "Table" in obj_type else "view",
            "name": actual_relname,
            "schema": schema_name,
            "title": f'"{schema_name}"."{actual_relname}"',
            "object_type": obj_type,
            "details": {
                "Schema": schema_name,
                "Owner": owner or "postgres",
                "Object Type": obj_type,
                "Estimated Rows": row_est if row_est is not None else "N/A",
                "Total Size": total_size or "N/A",
                "Columns Count": len(columns),
                "Comment": comment or ""
            },
            "columns": columns,
            "indexes": indexes,
            "constraints": constraints,
            "triggers": triggers,
            "sample_data": {
                "headers": sample_headers,
                "rows": sample_rows
            },
            "ddl": ddl_script,
            "schema_info": schema_info
        }
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass


def _describe_postgres_schema(cursor, schema_name: str, owner: str) -> dict:
    # 1. Fetch tables in schema
    cursor.execute("""
        SELECT 
            c.relname,
            CASE c.relkind
                WHEN 'r' THEN 'Table'
                WHEN 'p' THEN 'Partitioned table'
                WHEN 'm' THEN 'Materialized view'
                WHEN 'f' THEN 'Foreign table'
                ELSE 'Table'
            END,
            COALESCE(c.reltuples::bigint, 0),
            pg_size_pretty(pg_total_relation_size(c.oid)),
            (SELECT count(*) FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped),
            obj_description(c.oid, 'pg_class')
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'm', 'f')
        ORDER BY c.relname;
    """, (schema_name,))
    tables = []
    for r in cursor.fetchall():
        tables.append({
            "name": r[0],
            "type": r[1],
            "estimated_rows": r[2],
            "size": r[3] or "0 bytes",
            "columns_count": r[4],
            "comment": r[5] or ""
        })

    # 2. Fetch views in schema
    cursor.execute("""
        SELECT 
            c.relname,
            pg_get_userbyid(c.relowner),
            obj_description(c.oid, 'pg_class')
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = 'v'
        ORDER BY c.relname;
    """, (schema_name,))
    views = []
    for r in cursor.fetchall():
        views.append({
            "name": r[0],
            "owner": r[1],
            "comment": r[2] or ""
        })

    # 3. Fetch functions in schema
    cursor.execute("""
        SELECT 
            p.proname || '(' || pg_get_function_arguments(p.oid) || ')',
            pg_get_userbyid(p.proowner),
            l.lanname,
            obj_description(p.oid, 'pg_proc')
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_language l ON l.oid = p.prolang
        WHERE n.nspname = %s
        ORDER BY 1;
    """, (schema_name,))
    functions = []
    for r in cursor.fetchall():
        functions.append({
            "name": r[0],
            "owner": r[1],
            "language": r[2],
            "comment": r[3] or ""
        })

    ddl_script = f"CREATE SCHEMA \"{schema_name}\" AUTHORIZATION \"{owner}\";\n\n" \
                 f"-- Contains {len(tables)} tables, {len(views)} views, {len(functions)} functions"

    return {
        "target_type": "schema",
        "name": schema_name,
        "schema": schema_name,
        "title": f'Schema: "{schema_name}"',
        "object_type": "Schema",
        "details": {
            "Schema Name": schema_name,
            "Owner": owner,
            "Total Tables": len(tables),
            "Total Views": len(views),
            "Total Functions": len(functions),
        },
        "tables": tables,
        "views": views,
        "functions": functions,
        "ddl": ddl_script
    }


# ─────────────────────────────────────────────────────────────────────────────
# SQLITE DESCRIBE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
def _describe_sqlite(conn_data: dict, schema_hint: str | None, object_name: str) -> dict:
    db_path = conn_data.get("db_path")
    if not db_path:
        raise ValueError("SQLite database path is missing.")

    conn = db.create_sqlite_connection(db_path)
    if not conn:
        raise ConnectionError("Failed to connect to SQLite database.")

    cursor = conn.cursor()
    try:
        # Check if object exists in sqlite_master
        cursor.execute("SELECT type, name, sql FROM sqlite_master WHERE lower(name) = lower(?)", (object_name,))
        row = cursor.fetchone()

        # If not found as table, check if object_name is 'main' or sqlite schema/db
        if not row:
            if object_name.lower() in ("main", "database", "sqlite"):
                return _describe_sqlite_schema(cursor, object_name, db_path)
            raise ValueError(f"Table or View '{object_name}' not found in SQLite database.")

        obj_type_raw, tbl_name, raw_sql = row
        obj_type = "View" if obj_type_raw.lower() == "view" else "Table"

        # 1. Fetch Columns
        cursor.execute(f'PRAGMA table_info("{tbl_name}")')
        columns = []
        for r in cursor.fetchall():
            columns.append({
                "position": r[0] + 1,
                "name": r[1],
                "data_type": r[2] or "TEXT",
                "nullable": not bool(r[3]),
                "default": r[4] or "",
                "is_pk": bool(r[5]),
                "is_fk": False,
                "comment": ""
            })

        # 2. Fetch Foreign Keys
        cursor.execute(f'PRAGMA foreign_key_list("{tbl_name}")')
        fk_columns = set()
        constraints = []
        for r in cursor.fetchall():
            from_col = r[3]
            to_tbl = r[2]
            to_col = r[4]
            fk_columns.add(from_col)
            constraints.append({
                "name": f"FK_{tbl_name}_{from_col}",
                "type": "Foreign Key",
                "definition": f"FOREIGN KEY ({from_col}) REFERENCES {to_tbl}({to_col})"
            })

        for c in columns:
            if c["name"] in fk_columns:
                c["is_fk"] = True

        # 3. Fetch Indexes
        cursor.execute(f'PRAGMA index_list("{tbl_name}")')
        indexes = []
        for r in cursor.fetchall():
            idx_name = r[1]
            is_unique = bool(r[2])
            indexes.append({
                "name": idx_name,
                "definition": f"UNIQUE={is_unique}",
                "unique": is_unique,
                "type": "index"
            })

        # 3b. Fetch Triggers
        triggers = []
        try:
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?", (tbl_name,))
            for r in cursor.fetchall():
                triggers.append({
                    "name": r[0],
                    "definition": r[1] or ""
                })
        except Exception:
            triggers = []

        # 4. Fetch Sample Data
        sample_headers = [c["name"] for c in columns]
        sample_rows = []
        try:
            cursor.execute(f'SELECT * FROM "{tbl_name}" LIMIT 50')
            sample_rows = cursor.fetchall()
        except Exception:
            sample_rows = []

        schema_info = None
        try:
            schema_info = _describe_sqlite_schema(cursor, schema_hint or "main", db_path)
        except Exception:
            schema_info = None

        return {
            "target_type": "table" if obj_type == "Table" else "view",
            "name": tbl_name,
            "schema": schema_hint or "main",
            "title": f'"{tbl_name}"',
            "object_type": obj_type,
            "details": {
                "Database File": db_path,
                "Schema": schema_hint or "main",
                "Object Type": obj_type,
                "Columns Count": len(columns),
                "Indexes Count": len(indexes)
            },
            "columns": columns,
            "indexes": indexes,
            "constraints": constraints,
            "triggers": triggers,
            "sample_data": {
                "headers": sample_headers,
                "rows": sample_rows
            },
            "ddl": raw_sql or f"CREATE {obj_type.upper()} {tbl_name};",
            "schema_info": schema_info
        }
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass


def _describe_sqlite_schema(cursor, schema_name: str, db_path: str) -> dict:
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = []
    views = []
    for r in cursor.fetchall():
        name, otype = r
        if otype == "view":
            views.append({"name": name, "owner": "main", "comment": ""})
        else:
            tables.append({
                "name": name,
                "type": "Table",
                "estimated_rows": "N/A",
                "size": "N/A",
                "columns_count": 0,
                "comment": ""
            })

    return {
        "target_type": "schema",
        "name": schema_name,
        "schema": schema_name,
        "title": f"SQLite Database: {schema_name}",
        "object_type": "Schema",
        "details": {
            "Database File": db_path,
            "Tables": len(tables),
            "Views": len(views)
        },
        "tables": tables,
        "views": views,
        "functions": [],
        "ddl": f"-- SQLite Database: {db_path}\n-- Contains {len(tables)} tables, {len(views)} views"
    }


# ─────────────────────────────────────────────────────────────────────────────
# ORACLE DESCRIBE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
def _describe_oracle(conn_data: dict, schema_hint: str | None, object_name: str) -> dict:
    conn = db.get_pooled_oracle_connection(conn_data=conn_data)
    if not conn:
        raise ConnectionError("Failed to connect to Oracle database.")

    cursor = conn.cursor()
    try:
        eff_owner = (schema_hint or conn_data.get("user") or "").upper()
        eff_obj = object_name.upper()

        # Check if object is a schema / user in Oracle
        if not schema_hint:
            cursor.execute("SELECT USERNAME FROM ALL_USERS WHERE USERNAME = :usr", usr=eff_obj)
            usr_row = cursor.fetchone()
            if usr_row:
                return _describe_oracle_schema(cursor, eff_obj)

        # Check table in ALL_TABLES / ALL_VIEWS
        cursor.execute("""
            SELECT OWNER, TABLE_NAME, 'TABLE' AS OBJ_TYPE, NUM_ROWS
            FROM ALL_TABLES
            WHERE (OWNER = :own OR :own IS NULL) AND TABLE_NAME = :obj
            UNION ALL
            SELECT OWNER, VIEW_NAME, 'VIEW' AS OBJ_TYPE, NULL
            FROM ALL_VIEWS
            WHERE (OWNER = :own OR :own IS NULL) AND VIEW_NAME = :obj
        """, own=eff_owner or None, obj=eff_obj)
        tbl_row = cursor.fetchone()

        if not tbl_row:
            # Check table across all accessible schemas
            cursor.execute("""
                SELECT OWNER, TABLE_NAME, 'TABLE' AS OBJ_TYPE, NUM_ROWS
                FROM ALL_TABLES
                WHERE UPPER(TABLE_NAME) = :obj
                UNION ALL
                SELECT OWNER, VIEW_NAME, 'VIEW' AS OBJ_TYPE, NULL
                FROM ALL_VIEWS
                WHERE UPPER(VIEW_NAME) = :obj
            """, obj=eff_obj)
            tbl_row = cursor.fetchone()

        if not tbl_row:
            # Check if user meant schema
            for cand in (eff_obj, eff_owner):
                if cand:
                    cursor.execute("SELECT USERNAME FROM ALL_USERS WHERE UPPER(USERNAME) = :usr", usr=cand)
                    usr_row = cursor.fetchone()
                    if usr_row:
                        return _describe_oracle_schema(cursor, usr_row[0])
            target_display = f"{schema_hint}.{object_name}" if schema_hint else object_name
            raise ValueError(f"Table or Schema '{target_display}' not found in Oracle database.")

        owner, tbl_name, obj_type, num_rows = tbl_row

        # 1. Fetch Columns
        cursor.execute("""
            SELECT 
                COLUMN_ID,
                COLUMN_NAME,
                DATA_TYPE,
                DATA_LENGTH,
                DATA_PRECISION,
                DATA_SCALE,
                NULLABLE,
                DATA_DEFAULT
            FROM ALL_TAB_COLS
            WHERE OWNER = :own AND TABLE_NAME = :obj AND HIDDEN_COLUMN = 'NO'
            ORDER BY COLUMN_ID
        """, own=owner, obj=tbl_name)

        columns = []
        for r in cursor.fetchall():
            col_id, col_name, dtype, dlen, dprec, dscale, nullable, ddef = r
            if dtype == "NUMBER":
                if dprec and dscale:
                    dtype_str = f"NUMBER({dprec},{dscale})"
                elif dprec:
                    dtype_str = f"NUMBER({dprec})"
                else:
                    dtype_str = "NUMBER"
            elif dtype in ("VARCHAR2", "CHAR", "RAW"):
                dtype_str = f"{dtype}({dlen})"
            else:
                dtype_str = dtype

            columns.append({
                "position": col_id,
                "name": col_name,
                "data_type": dtype_str,
                "nullable": (nullable == "Y"),
                "default": str(ddef).strip() if ddef else "",
                "is_pk": False,
                "is_fk": False,
                "comment": ""
            })

        # 2. Fetch PK / FK Constraints
        cursor.execute("""
            SELECT 
                c.CONSTRAINT_NAME,
                c.CONSTRAINT_TYPE,
                cc.COLUMN_NAME,
                c.R_CONSTRAINT_NAME
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
            WHERE c.OWNER = :own AND c.TABLE_NAME = :obj
        """, own=owner, obj=tbl_name)
        constraints = []
        for r in cursor.fetchall():
            cname, ctype, colname, r_cname = r
            type_label = "Other"
            if ctype == "P":
                type_label = "Primary Key"
                for c in columns:
                    if c["name"] == colname:
                        c["is_pk"] = True
            elif ctype == "R":
                type_label = "Foreign Key"
                for c in columns:
                    if c["name"] == colname:
                        c["is_fk"] = True
            elif ctype == "U":
                type_label = "Unique"
            elif ctype == "C":
                type_label = "Check"

            constraints.append({
                "name": cname,
                "type": type_label,
                "definition": f"COLUMN: {colname}" + (f" -> REF: {r_cname}" if r_cname else "")
            })

        # 3. Fetch Indexes
        cursor.execute("""
            SELECT INDEX_NAME, UNIQUENESS, INDEX_TYPE
            FROM ALL_INDEXES
            WHERE OWNER = :own AND TABLE_NAME = :obj
            ORDER BY INDEX_NAME
        """, own=owner, obj=tbl_name)
        indexes = []
        for r in cursor.fetchall():
            indexes.append({
                "name": r[0],
                "definition": f"{r[1]} {r[2]}",
                "unique": (r[1] == "UNIQUE"),
                "type": r[2] or "NORMAL"
            })

        # 3b. Fetch Comments & Triggers
        tbl_comment = ""
        try:
            cursor.execute("SELECT COMMENTS FROM ALL_TAB_COMMENTS WHERE OWNER = :own AND TABLE_NAME = :obj", own=owner, obj=tbl_name)
            comm_row = cursor.fetchone()
            if comm_row and comm_row[0]:
                tbl_comment = comm_row[0]
        except Exception:
            tbl_comment = ""

        try:
            cursor.execute("SELECT COLUMN_NAME, COMMENTS FROM ALL_COL_COMMENTS WHERE OWNER = :own AND TABLE_NAME = :obj", own=owner, obj=tbl_name)
            for c_name, c_comm in cursor.fetchall():
                if c_comm:
                    for c in columns:
                        if c["name"] == c_name:
                            c["comment"] = c_comm
                            break
        except Exception:
            pass

        triggers = []
        try:
            cursor.execute("""
                SELECT TRIGGER_NAME, TRIGGER_TYPE, TRIGGERING_EVENT, STATUS
                FROM ALL_TRIGGERS
                WHERE TABLE_OWNER = :own AND TABLE_NAME = :obj
                ORDER BY TRIGGER_NAME
            """, own=owner, obj=tbl_name)
            for r in cursor.fetchall():
                triggers.append({
                    "name": r[0],
                    "definition": f"-- Trigger: {r[0]} ({r[1]} {r[2]} - Status: {r[3]})"
                })
        except Exception:
            triggers = []

        # 4. Fetch Sample Data
        sample_headers = [c["name"] for c in columns]
        sample_rows = []
        try:
            cursor.execute(f'SELECT * FROM "{owner}"."{tbl_name}" FETCH FIRST 50 ROWS ONLY')
            sample_rows = cursor.fetchall()
        except Exception:
            sample_rows = []

        # 5. DDL
        ddl_script = f"-- Oracle Table: {owner}.{tbl_name}\n" \
                     f"CREATE {obj_type} \"{owner}\".\"{tbl_name}\" (\n"
        col_strs = []
        for c in columns:
            null_part = "" if c["nullable"] else " NOT NULL"
            col_strs.append(f"    \"{c['name']}\" {c['data_type']}{null_part}")
        ddl_script += ",\n".join(col_strs) + "\n);"

        return {
            "target_type": "table" if obj_type == "TABLE" else "view",
            "name": tbl_name,
            "schema": owner,
            "title": f'"{owner}"."{tbl_name}"',
            "object_type": obj_type.title(),
            "details": {
                "Owner": owner,
                "Object Type": obj_type.title(),
                "Estimated Rows": num_rows if num_rows is not None else "N/A",
                "Columns Count": len(columns),
                "Indexes Count": len(indexes),
                "Comment": tbl_comment
            },
            "columns": columns,
            "indexes": indexes,
            "constraints": constraints,
            "triggers": triggers,
            "sample_data": {
                "headers": sample_headers,
                "rows": sample_rows
            },
            "ddl": ddl_script,
            "schema_info": _describe_oracle_schema(cursor, owner) if owner else None
        }
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass


def _describe_oracle_schema(cursor, schema_name: str) -> dict:
    cursor.execute("""
        SELECT TABLE_NAME, 'Table' as OBJ_TYPE, NUM_ROWS
        FROM ALL_TABLES WHERE OWNER = :own
        UNION ALL
        SELECT VIEW_NAME, 'View' as OBJ_TYPE, NULL
        FROM ALL_VIEWS WHERE OWNER = :own
        ORDER BY 1
    """, own=schema_name)
    tables = []
    views = []
    for r in cursor.fetchall():
        name, otype, num_rows = r
        if otype == "View":
            views.append({"name": name, "owner": schema_name, "comment": ""})
        else:
            tables.append({
                "name": name,
                "type": "Table",
                "estimated_rows": num_rows if num_rows is not None else "N/A",
                "size": "N/A",
                "columns_count": 0,
                "comment": ""
            })

    return {
        "target_type": "schema",
        "name": schema_name,
        "schema": schema_name,
        "title": f"Oracle Schema: {schema_name}",
        "object_type": "Schema",
        "details": {
            "Schema / User": schema_name,
            "Tables Count": len(tables),
            "Views Count": len(views)
        },
        "tables": tables,
        "views": views,
        "functions": [],
        "ddl": f"-- Oracle Schema: {schema_name}\n-- Contains {len(tables)} tables, {len(views)} views"
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────
def describe_database_object(conn_data: dict, raw_target: str) -> dict:
    """
    Main entry point for 'Describe' (Table and Schema).
    Dispatches to PostgreSQL, SQLite, Oracle, or fallback.
    """
    if not isinstance(conn_data, dict) or not conn_data:
        raise ValueError("Invalid connection information.")

    if not raw_target or not raw_target.strip():
        raise ValueError("Please provide a table or schema name to describe.")

    schema_hint, object_name = parse_object_identifier(raw_target)
    if not object_name:
        raise ValueError("Please provide a valid table or schema name to describe.")

    code = _detect_db_code(conn_data)

    if code in ("ORACLE", "ORACLE_DB"):
        meta = _describe_oracle(conn_data, schema_hint, object_name)
    elif code in ("POSTGRES", "POSTGRESQL"):
        meta = _describe_postgres(conn_data, schema_hint, object_name)
    elif code == "SQLITE":
        meta = _describe_sqlite(conn_data, schema_hint, object_name)
    else:
        # Fallback using postgres-compatible queries or zero-row describe
        try:
            meta = _describe_postgres(conn_data, schema_hint, object_name)
        except Exception:
            raise ValueError(f"Describe object is not supported for database engine: {code}")

    if meta:
        meta["db_code"] = code
        meta["scripts"] = generate_object_scripts(meta)
        if "Full DDL" in meta["scripts"]:
            meta["ddl"] = meta["scripts"]["Full DDL"]

        if meta.get("schema_info"):
            meta["schema_info"]["db_code"] = code
            meta["schema_info"]["scripts"] = generate_object_scripts(meta["schema_info"])
            if "Full DDL" in meta["schema_info"]["scripts"]:
                meta["schema_info"]["ddl"] = meta["schema_info"]["scripts"]["Full DDL"]

    return meta
