from db.db_connections import (
    create_sqlite_connection, 
    create_postgres_connection,
    create_csv_connection,
    create_servicenow_connection,
    get_pooled_oracle_connection
)

def get_sqlite_schema(db_path):
    """
    Retrieves metadata for all tables in a SQLite database.
    Returns a dict: { table_name: { columns: [...], foreign_keys: [...] } }
    """
    if isinstance(db_path, dict):
        db_path = db_path.get("db_path")

    if not db_path:
        return {}

    def _quote_sqlite_ident(name):
        return '"' + str(name).replace('"', '""') + '"'

    schema = {}
    conn = create_sqlite_connection(db_path)
    if not conn:
        return schema
    
    try:
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            # Get columns
            cursor.execute(f"PRAGMA table_info({_quote_sqlite_ident(table)});")
            columns = []
            for col in cursor.fetchall():
                col_type = (col[2] or "").strip() or "ANY"
                columns.append({
                    "name": col[1],
                    "type": col_type,
                    "nullable": not bool(col[3]),
                    "default": col[4],
                    "pk": bool(col[5])
                })
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({_quote_sqlite_ident(table)});")
            foreign_keys = []
            for fk in cursor.fetchall():
                foreign_keys.append({
                    "id": fk[0],
                    "table": fk[2], # target table
                    "from": fk[3],  # source column
                    "to": fk[4]     # target column
                })
            
            schema[table] = {
                "table": table,
                "columns": columns,
                "foreign_keys": foreign_keys
            }
            
    except Exception as e:
        print(f"Error retrieving SQLite schema: {e}")
    finally:
        conn.close()
        
    return schema

def get_postgres_schema(conn_data, schema_name=None):
    """
    Retrieves metadata for all tables in non-system schemas.
    If schema_name is provided, only fetches from that schema.
    Returns a dict: { "schema.table": { columns: [...], foreign_keys: [...], schema: "..." } }
    """
    schema_data = {}
    conn = create_postgres_connection(
        conn_data, 
        application_name=f"Universal SQL Client - Metadata Retrieval ({conn_data.get('database')})",
        bypass_cooldown=True
    )

    if not conn:
        return schema_data
        
    try:
        cursor = conn.cursor()
        
        # Define system schemas to exclude
        exclude_schemas = ('pg_catalog', 'information_schema', 'pg_toast')
        
        # Get all tables
        if schema_name:
            cursor.execute("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE';
            """, (schema_name,))
        else:
            cursor.execute("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema NOT IN %s AND table_type = 'BASE TABLE';
            """, (exclude_schemas,))
            
        tables_to_fetch = cursor.fetchall()
        
        for s_name, t_name in tables_to_fetch:
            full_table_name = f"{s_name}.{t_name}"
            
            # Get columns and PK info
            cursor.execute("""
                SELECT 
                    a.attname AS column_name,
                    format_type(a.atttypid, a.atttypmod) AS data_type,
                    CASE WHEN ct.contype = 'p' THEN true ELSE false END AS is_pk
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_constraint ct 
                  ON ct.conrelid = c.oid 
                 AND a.attnum = ANY(ct.conkey)
                 AND ct.contype = 'p'
                WHERE n.nspname = %s 
                  AND c.relname = %s 
                  AND a.attnum > 0 
                  AND NOT a.attisdropped
                ORDER BY a.attnum;
            """, (s_name, t_name))
            
            columns = []
            for col_name, data_type, is_pk in cursor.fetchall():
                columns.append({
                    "name": col_name,
                    "type": data_type,
                    "pk": is_pk
                })
                
            # Get foreign keys (including cross-schema if they exist)
            cursor.execute("""
                SELECT
                    tc.constraint_name, 
                    kcu.column_name, 
                    ccu.table_schema AS foreign_schema_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name=%s AND tc.table_schema=%s;
            """, (t_name, s_name))
            
            foreign_keys = []
            for constr_name, col_name, f_schema, f_table, f_col in cursor.fetchall():
                foreign_keys.append({
                    "name": constr_name,
                    "from": col_name,
                    "table": f"{f_schema}.{f_table}",
                    "to": f_col
                })
                
            schema_data[full_table_name] = {
                "schema": s_name,
                "table": t_name,
                "columns": columns,
                "foreign_keys": foreign_keys
            }
            
        conn.commit()
            
    except Exception as e:
        print(f"Error retrieving Postgres schema: {e}")
    finally:
        conn.close()
        
    return schema_data


def get_csv_schema(conn_info):
    """
    Retrieves metadata for CSV files in the specified path using DuckDB.
    """
    schema_data = {}
    conn = create_csv_connection(conn_info)
    if not conn:
        return schema_data

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name NOT LIKE '%.csv'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f'PRAGMA table_info("{table}")')
            columns = []
            for col in cursor.fetchall():
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "pk": bool(col[5]) if len(col) > 5 else False,
                })

            schema_data[table] = {
                "columns": columns,
                "foreign_keys": []
            }
    except Exception as e:
        print(f"Error retrieving DuckDB CSV schema: {e}")
    finally:
        conn.close()
    return schema_data


def _subprocess_fetch_servicenow_schema(conn_info, table_name):
    """Module-level picklable wrapper used by ProcessPoolExecutor.

    Must stay at module level so that concurrent.futures can pickle it
    when spawning a worker process on Windows.
    """
    return get_servicenow_schema(conn_info, table_name)


def get_servicenow_schema(conn_info, table_name=None):
    """
    Retrieves metadata for ServiceNow tables using REST metadata and local DuckDB cache.
    """
    from db.servicenow_metadata import fetch_servicenow_tables, fetch_servicenow_columns
    from db.servicenow_dlt import get_synced_tables
    from db.duckdb_manager import DuckDBManager

    schema_data = {}
    target_tables = [table_name] if table_name else []

    if not target_tables:
        raw_tables = fetch_servicenow_tables(conn_info)
        target_tables = [t[0] for t in raw_tables]

    conn_id = conn_info.get("id") or conn_info.get("connection_id") or "default"
    db_path = DuckDBManager.get_servicenow_duckdb_path(conn_id)
    synced_tables = set(get_synced_tables(db_path))

    for table in target_tables:
        cols_meta = fetch_servicenow_columns(conn_info, table)
        columns = []
        foreign_keys = []

        if cols_meta:
            for c in cols_meta:
                columns.append({
                    "name": c["name"],
                    "type": c.get("type", "STRING"),
                    "pk": c.get("pk", False),
                })
                ref = c.get("reference")
                if ref:
                    foreign_keys.append({"from": c["name"], "table": ref, "to": "sys_id"})
        else:
            columns = [
                {"name": "sys_id", "type": "STRING", "pk": True},
                {"name": "number", "type": "STRING", "pk": False},
                {"name": "short_description", "type": "STRING", "pk": False},
                {"name": "sys_created_on", "type": "TIMESTAMP", "pk": False},
            ]

        schema_data[table] = {
            "table": table,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "is_cached": table in synced_tables,
        }

    return schema_data


def get_postgres_available_schemas(conn_info: dict) -> list[str]:
    """Return sorted non-system schema names for a Postgres connection."""
    conn = None
    try:
        pg = {k: conn_info.get(k) for k in ['host', 'port', 'database', 'user', 'password']}
        conn = create_postgres_connection(**pg)
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
            "ORDER BY schema_name;"
        )
        return [row[0] for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        if conn:
            conn.close()

def get_oracle_schema(conn_data, schema_name: str | None = None):
    """Retrieves metadata for Oracle tables accessible to the connected user.

    Args:
        conn_data: Connection parameters dict.
        schema_name: When provided, restricts results to this owner (schema).
                     When ``None``, returns the current user's own objects
                     via ``USER_*`` views for backward compatibility.

    Returns:
        dict: ``{ table_name: { columns: [...], foreign_keys: [...] } }``
              Keys use the plain table name (not ``owner.table``).
    """
    schema: dict = {}
    conn = get_pooled_oracle_connection(conn_data=conn_data)
    if not conn:
        return schema

    owner = (schema_name or "").strip().upper() or None

    try:
        cursor = conn.cursor()

        # 1. Get tables for the target owner (or current user)
        if owner:
            cursor.execute(
                "SELECT object_name FROM all_objects "
                "WHERE owner = :owner AND object_type = 'TABLE' "
                "ORDER BY object_name",
                {"owner": owner},
            )
        else:
            cursor.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        tables = [row[0] for row in cursor.fetchall()]

        # 2. Get all columns for these tables
        if owner:
            cursor.execute(
                "SELECT table_name, column_name, data_type, nullable"
                " FROM all_tab_columns"
                " WHERE owner = :owner"
                " ORDER BY table_name, column_id",
                {"owner": owner},
            )
        else:
            cursor.execute(
                "SELECT table_name, column_name, data_type, nullable"
                " FROM user_tab_columns"
                " ORDER BY table_name, column_id"
            )
        all_columns = cursor.fetchall()

        # Group columns by table
        table_columns: dict = {}
        for t_name, c_name, d_type, nullable in all_columns:
            if t_name not in table_columns:
                table_columns[t_name] = []
            table_columns[t_name].append({
                "name": c_name,
                "type": d_type,
                "nullable": nullable == "Y",
                "pk": False  # Updated below
            })

        # 3. Get Primary Keys
        if owner:
            cursor.execute(
                "SELECT cols.table_name, cols.column_name"
                " FROM all_constraints cons"
                " JOIN all_cons_columns cols"
                "   ON cons.constraint_name = cols.constraint_name"
                "  AND cons.owner = cols.owner"
                " WHERE cons.constraint_type = 'P' AND cons.owner = :owner",
                {"owner": owner},
            )
        else:
            cursor.execute(
                "SELECT cols.table_name, cols.column_name"
                " FROM user_constraints cons"
                " JOIN user_cons_columns cols ON cons.constraint_name = cols.constraint_name"
                " WHERE cons.constraint_type = 'P'"
            )
        pk_columns = cursor.fetchall()
        pk_set = {(r[0], r[1]) for r in pk_columns}

        # Update PK status in table_columns
        for t_name, cols in table_columns.items():
            for col in cols:
                if (t_name, col["name"]) in pk_set:
                    col["pk"] = True

        # 4. Get Foreign Keys
        if owner:
            cursor.execute(
                "SELECT"
                "    a.table_name AS src_table,"
                "    a.column_name AS src_column,"
                "    c_pk.table_name AS dest_table,"
                "    b.column_name AS dest_column"
                " FROM all_cons_columns a"
                " JOIN all_constraints c ON a.constraint_name = c.constraint_name"
                "   AND a.owner = c.owner"
                " JOIN all_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name"
                " JOIN all_cons_columns b"
                "   ON c_pk.constraint_name = b.constraint_name AND a.position = b.position"
                " WHERE c.constraint_type = 'R' AND c.owner = :owner",
                {"owner": owner},
            )
        else:
            cursor.execute(
                "SELECT"
                "    a.table_name AS src_table,"
                "    a.column_name AS src_column,"
                "    c_pk.table_name AS dest_table,"
                "    b.column_name AS dest_column"
                " FROM user_cons_columns a"
                " JOIN user_constraints c ON a.constraint_name = c.constraint_name"
                " JOIN user_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name"
                " JOIN user_cons_columns b"
                "   ON c_pk.constraint_name = b.constraint_name AND a.position = b.position"
                " WHERE c.constraint_type = 'R'"
            )
        fk_records = cursor.fetchall()

        # Group FKs by table
        table_fks: dict = {}
        for src_t, src_c, dst_t, dst_c in fk_records:
            if src_t not in table_fks:
                table_fks[src_t] = []
            table_fks[src_t].append({
                "from": src_c,
                "table": dst_t,
                "to": dst_c
            })

        # 5. Build final schema dictionary
        for table in tables:
            schema[table] = {
                "table": table,
                "columns": table_columns.get(table, []),
                "foreign_keys": table_fks.get(table, [])
            }

    except Exception as e:
        print(f"Error retrieving Oracle schema: {e}")
    finally:
        conn.close()

    return schema


def get_oracle_available_schemas(conn_data: dict) -> list:
    """Retrieves list of available Oracle schemas (database users/owners)."""
    default_schema = (conn_data.get("user") or conn_data.get("username") or "SYSTEM").upper()
    conn = get_pooled_oracle_connection(conn_data=conn_data)
    if not conn:
        return [default_schema]
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM all_users ORDER BY username")
        schemas = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return schemas if schemas else [default_schema]
    except Exception as e:
        print(f"Error fetching Oracle schemas: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return [default_schema]

