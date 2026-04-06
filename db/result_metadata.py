from db.db_retrieval import normalize_type
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

    if not requested_columns:
        return specs

    metadata_cursor = conn.cursor()
    try:
        values_clause = ", ".join(
            metadata_cursor.mogrify("(%s, %s, %s)", values).decode("utf-8")
            for values in requested_columns
        )
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
                ) AS is_fk
            FROM requested_cols rc
            JOIN pg_attribute a
              ON a.attrelid = rc.table_oid::oid
             AND a.attnum = rc.column_index::int2
            WHERE NOT a.attisdropped
            """
        )

        for result_index, data_type, attnotnull, is_pk, is_fk in metadata_cursor.fetchall():
            if 0 <= result_index < len(specs):
                specs[result_index].update({
                    "data_type": _normalize_postgres_type(data_type),
                    "pk": bool(is_pk),
                    "fk": bool(is_fk),
                    "nullable": not bool(attnotnull),
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
                continue

            specs[index].update({
                "data_type": normalize_type(row[2]),
                "pk": bool(row[5]),
                "fk": spec["name"].lower() in fk_columns,
                "nullable": not bool(row[3]),
            })
    finally:
        cursor.close()

    return specs


def resolve_column_specs(code, conn, conn_data, query, description):
    columns = [_description_value(desc, "name", 0, "") for desc in description]

    if code == "POSTGRES":
        specs = _resolve_postgres_column_specs(conn, conn_data, description)
    elif code == "SQLITE":
        specs = _resolve_sqlite_column_specs(conn, query, description)
    else:
        specs = [_default_column_spec(name) for name in columns]

    return columns, specs
