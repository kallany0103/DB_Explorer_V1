from db.type_utils import normalize_type
from db.query_context import resolve_writable_table_context


PG_COMMON_OID_MAP = {
    16: "BOOL",
    20: "BIGINT",
    21: "SMALLINT",
    23: "INT",
    25: "TEXT",
    114: "JSON",
    700: "FLOAT4",
    701: "FLOAT8",
    1042: "CHAR",
    1043: "VARCHAR",
    1082: "DATE",
    1083: "TIME",
    1114: "TIMESTAMP",
    1184: "TIMESTAMPTZ",
    1266: "TIMETZ",
    1700: "DECIMAL",
    2950: "UUID",
    3802: "JSONB",
}

PG_OID_TYPE_CACHE = {}


def _description_value(desc, attr_name, index, default=None):
    if hasattr(desc, attr_name):
        value = getattr(desc, attr_name)
        return default if value is None else value
    if len(desc) > index:
        value = desc[index]
        return default if value is None else value
    return default


def _default_column_spec(name, data_type=""):
    return {
        "name": str(name),
        "data_type": str(data_type or ""),
        "pk": False,
        "fk": False,
        "nullable": None,
        "read_only": False,
    }


def _normalize_postgres_type(type_name):
    return normalize_type(type_name) if type_name else ""


def _postgres_cache_key(conn_data):
    return (
        conn_data.get("host"),
        int(conn_data.get("port") or 5432),
        conn_data.get("database"),
    )


def _load_postgres_oid_cache(conn, conn_data):
    cache_key = _postgres_cache_key(conn_data)
    cached = PG_OID_TYPE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    oid_cache = dict(PG_COMMON_OID_MAP)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT oid, format_type(oid, NULL) FROM pg_type")
        for oid, type_name in cursor.fetchall():
            oid_cache[int(oid)] = _normalize_postgres_type(type_name)
    finally:
        cursor.close()

    PG_OID_TYPE_CACHE[cache_key] = oid_cache
    return oid_cache


def _postgres_fallback_type(desc, oid_cache):
    type_oid = int(_description_value(desc, "type_code", 1, 0) or 0)
    base_type = oid_cache.get(type_oid) or PG_COMMON_OID_MAP.get(type_oid, "")
    base_type = _normalize_postgres_type(base_type)
    precision = _description_value(desc, "precision", 4)
    scale = _description_value(desc, "scale", 5)

    if base_type in {"NUMERIC", "DECIMAL"} and precision is not None:
        if scale is not None:
            return f"{base_type}({precision},{scale})"
        return f"{base_type}({precision})"

    return base_type


def _resolve_postgres_column_specs(conn, conn_data, description):
    oid_cache = _load_postgres_oid_cache(conn, conn_data)
    specs = []
    requested_columns = []

    for result_index, desc in enumerate(description):
        column_name = _description_value(desc, "name", 0, "")
        spec = _default_column_spec(column_name, _postgres_fallback_type(desc, oid_cache))
        null_ok = _description_value(desc, "null_ok", 6)
        if null_ok is not None:
            spec["nullable"] = bool(null_ok)
        specs.append(spec)

        table_oid = int(_description_value(desc, "table_oid", 7, 0) or 0)
        column_index = int(_description_value(desc, "table_column", 8, 0) or 0)
        if table_oid and column_index:
            requested_columns.append((result_index, table_oid, column_index))
        else:
            spec["read_only"] = True

    if not requested_columns:
        return specs

    metadata_cursor = conn.cursor()
    try:
        values_clause = ", ".join(
            metadata_cursor.mogrify("(%s, %s, %s)", values).decode("utf-8")
            for values in requested_columns
        )
        server_version = getattr(conn, "server_version", 0) or 0
        gen_col_clause = (
            "COALESCE(a.attgenerated, '') <> '' AS is_generated"
            if server_version == 0 or server_version >= 120000
            else "FALSE AS is_generated"
        )
        try:
            metadata_cursor.execute(
                f"""
                WITH requested_cols(result_index, table_oid, column_index) AS (
                    VALUES {values_clause}
                )
                SELECT
                    rc.result_index,
                    UPPER(format_type(a.atttypid, a.atttypmod)) AS data_type,
                    a.attnotnull,
                    EXISTS (
                        SELECT 1
                        FROM pg_constraint c
                        WHERE c.conrelid = rc.table_oid::oid
                          AND c.contype = 'p'
                          AND a.attnum = ANY(c.conkey)
                    ) AS is_pk,
                    EXISTS (
                        SELECT 1
                        FROM pg_constraint c
                        WHERE c.conrelid = rc.table_oid::oid
                          AND c.contype = 'f'
                          AND a.attnum = ANY(c.conkey)
                    ) AS is_fk,
                    {gen_col_clause}
                FROM requested_cols rc
                JOIN pg_attribute a
                  ON a.attrelid = rc.table_oid::oid
                 AND a.attnum = rc.column_index::int2
                WHERE NOT a.attisdropped
                """
            )
        except Exception:
            return specs

        for result_index, data_type, attnotnull, is_pk, is_fk, is_generated in metadata_cursor.fetchall():
            if 0 <= result_index < len(specs):
                specs[result_index].update({
                    "data_type": _normalize_postgres_type(data_type),
                    "pk": bool(is_pk),
                    "fk": bool(is_fk),
                    "nullable": not bool(attnotnull),
                    "read_only": bool(is_generated),
                })
    finally:
        metadata_cursor.close()

    return specs


def _resolve_sqlite_table_info(cursor, table_name):
    escaped_table_name = str(table_name or "").replace('"', '""')
    try:
        cursor.execute(f'PRAGMA table_xinfo("{escaped_table_name}")')
    except Exception:
        cursor.execute(f'PRAGMA table_info("{escaped_table_name}")')
    return cursor.fetchall()


def _resolve_sqlite_column_specs(conn, query, description):
    specs = [_default_column_spec(desc[0]) for desc in description]
    table_context = resolve_writable_table_context(query)
    if not table_context:
        return specs
    table_name = table_context["real_table_name"]

    cursor = conn.cursor()
    try:
        table_rows = _resolve_sqlite_table_info(cursor, table_name)
        table_columns = {str(row[1]).lower(): row for row in table_rows if len(row) >= 6}
        escaped_table_name = table_name.replace('"', '""')
        cursor.execute(f'PRAGMA foreign_key_list("{escaped_table_name}")')
        fk_columns = {str(row[3]).lower() for row in cursor.fetchall() if len(row) > 3}

        for index, spec in enumerate(specs):
            row = table_columns.get(spec["name"].lower())
            if not row:
                spec["read_only"] = True
                continue

            is_generated = len(row) >= 7 and row[6] in (2, 3)
            specs[index].update({
                "data_type": normalize_type(row[2]),
                "pk": bool(row[5]),
                "fk": spec["name"].lower() in fk_columns,
                "nullable": not bool(row[3]),
                "read_only": bool(is_generated),
            })
    finally:
        cursor.close()

    return specs


def _resolve_oracle_column_specs(conn, query, description):
    from db.query_describe import _format_oracle_type
    from db.query_context import resolve_writable_table_context

    specs = []
    for desc in description:
        col_name = _description_value(desc, "name", 0, "")
        data_type = _format_oracle_type(desc)
        null_ok = _description_value(desc, "null_ok", 6)
        spec = _default_column_spec(col_name, data_type)
        if null_ok is not None:
            spec["nullable"] = bool(null_ok)
        spec["read_only"] = False
        specs.append(spec)

    table_context = resolve_writable_table_context(query)
    if not table_context:
        for spec in specs:
            spec["read_only"] = True
        return specs

    table_name = table_context.get("real_table_name")
    schema_name = table_context.get("schema_name")
    if not table_name:
        return specs

    table_upper = str(table_name).upper()
    owner_upper = str(schema_name).upper() if schema_name else None

    if conn is not None:
        try:
            cursor = conn.cursor()
            try:
                # 1. Primary Keys
                if owner_upper:
                    cursor.execute(
                        """
                        SELECT cols.COLUMN_NAME
                        FROM ALL_CONSTRAINTS cons
                        JOIN ALL_CONS_COLUMNS cols
                          ON cons.OWNER = cols.OWNER
                         AND cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                        WHERE cons.CONSTRAINT_TYPE = 'P'
                          AND cons.OWNER = :owner
                          AND (cons.TABLE_NAME = :tbl OR cons.TABLE_NAME = :tbl_raw)
                        """,
                        {"owner": owner_upper, "tbl": table_upper, "tbl_raw": table_name},
                    )
                else:
                    cursor.execute(
                        """
                        SELECT cols.COLUMN_NAME
                        FROM USER_CONSTRAINTS cons
                        JOIN USER_CONS_COLUMNS cols
                          ON cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                        WHERE cons.CONSTRAINT_TYPE = 'P'
                          AND (cons.TABLE_NAME = :tbl OR cons.TABLE_NAME = :tbl_raw)
                        """,
                        {"tbl": table_upper, "tbl_raw": table_name},
                    )
                pk_cols = {str(row[0]).upper() for row in cursor.fetchall() if row and row[0]}

                # 2. Foreign Keys
                if owner_upper:
                    cursor.execute(
                        """
                        SELECT cols.COLUMN_NAME
                        FROM ALL_CONSTRAINTS cons
                        JOIN ALL_CONS_COLUMNS cols
                          ON cons.OWNER = cols.OWNER
                         AND cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                        WHERE cons.CONSTRAINT_TYPE = 'R'
                          AND cons.OWNER = :owner
                          AND (cons.TABLE_NAME = :tbl OR cons.TABLE_NAME = :tbl_raw)
                        """,
                        {"owner": owner_upper, "tbl": table_upper, "tbl_raw": table_name},
                    )
                else:
                    cursor.execute(
                        """
                        SELECT cols.COLUMN_NAME
                        FROM USER_CONSTRAINTS cons
                        JOIN USER_CONS_COLUMNS cols
                          ON cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                        WHERE cons.CONSTRAINT_TYPE = 'R'
                          AND (cons.TABLE_NAME = :tbl OR cons.TABLE_NAME = :tbl_raw)
                        """,
                        {"tbl": table_upper, "tbl_raw": table_name},
                    )
                fk_cols = {str(row[0]).upper() for row in cursor.fetchall() if row and row[0]}

                # 3. Table Columns (check existence, virtual, hidden)
                table_cols = set()
                virtual_cols = set()
                try:
                    if owner_upper:
                        cursor.execute(
                            """
                            SELECT COLUMN_NAME, VIRTUAL_COLUMN, HIDDEN_COLUMN
                            FROM ALL_TAB_COLS
                            WHERE OWNER = :owner
                              AND (TABLE_NAME = :tbl OR TABLE_NAME = :tbl_raw)
                            """,
                            {"owner": owner_upper, "tbl": table_upper, "tbl_raw": table_name},
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT COLUMN_NAME, VIRTUAL_COLUMN, HIDDEN_COLUMN
                            FROM USER_TAB_COLS
                            WHERE TABLE_NAME = :tbl OR TABLE_NAME = :tbl_raw
                            """,
                            {"tbl": table_upper, "tbl_raw": table_name},
                        )
                    for r in cursor.fetchall():
                        if r and r[0]:
                            col_u = str(r[0]).upper()
                            table_cols.add(col_u)
                            is_virt = len(r) > 1 and str(r[1]).upper() == "YES"
                            is_hid = len(r) > 2 and str(r[2]).upper() == "YES"
                            if is_virt or is_hid:
                                virtual_cols.add(col_u)
                except Exception:
                    pass

                for spec in specs:
                    cname = spec["name"].upper()
                    if table_cols and cname not in table_cols:
                        spec["read_only"] = True
                    elif cname in virtual_cols:
                        spec["read_only"] = True
                    if cname in pk_cols:
                        spec["pk"] = True
                    if cname in fk_cols:
                        spec["fk"] = True
            finally:
                cursor.close()
        except Exception:
            pass

    return specs


def resolve_column_specs(code, conn, conn_data, query, description):
    columns = [_description_value(desc, "name", 0, "") for desc in description]
    code_upper = (code or "").upper()

    if code_upper in ("POSTGRES", "POSTGRESQL"):
        specs = _resolve_postgres_column_specs(conn, conn_data, description)
    elif code_upper == "SQLITE":
        specs = _resolve_sqlite_column_specs(conn, query, description)
    elif code_upper in ("ORACLE", "ORACLE_DB", "ORACLE_FA"):
        specs = _resolve_oracle_column_specs(conn, query, description)
    else:
        specs = [_default_column_spec(name) for name in columns]
        for spec in specs:
            spec["read_only"] = True

    return columns, specs

