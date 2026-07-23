from db.db_connections import (
    create_sqlite_connection, 
    create_postgres_connection,
    create_csv_connection,
    create_servicenow_connection,
    create_oracle_connection_from_dict
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
    Retrieves metadata for CSV files in the specified path.
    CData CSV driver treats a folder as a database and each file as a table.
    """
    schema_data = {}
    conn = create_csv_connection(conn_info)
    if not conn:
        return schema_data

    try:
        cursor = conn.cursor()
        # Get tables (CSV files)
        cursor.execute("SELECT TableName FROM sys_tables")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            # Get columns
            cursor.execute(f"SELECT ColumnName, DataTypeName FROM sys_tablecolumns WHERE TableName='{table}'")
            columns = []
            for col_name, data_type in cursor.fetchall():
                columns.append({
                    "name": col_name,
                    "type": data_type,
                    "pk": False # CSV doesn't have PKs by default
                })
            
            schema_data[table] = {
                "columns": columns,
                "foreign_keys": [] # CSV doesn't have FKs
            }
    except Exception as e:
        print(f"Error retrieving CSV schema: {e}")
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
    Retrieves metadata for ServiceNow tables.
    """
    schema_data = {}
    conn = create_servicenow_connection(conn_info)
    if not conn:
        return schema_data

    try:
        cursor = conn.cursor()
        if table_name:
            tables = [table_name]
        else:
            # Limiting to a few common tables to avoid timeout
            cursor.execute("SELECT TableName FROM sys_tables LIMIT 50")
            tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            columns = []
            foreign_keys = []

            # Attempt 1: fetch columns + ReferencedTable in one query
            # CData exposes a ReferencedTable column in sys_tablecolumns for reference fields.
            col_query_succeeded = False
            try:
                cursor.execute(
                    f"SELECT ColumnName, DataTypeName, IsKey, ReferencedTable "
                    f"FROM sys_tablecolumns WHERE TableName='{table}'"
                )
                for row in cursor.fetchall():
                    col_name, data_type, is_key = row[0], row[1], row[2]
                    ref_table = row[3] if len(row) > 3 else None
                    columns.append({
                        "name": col_name,
                        "type": data_type,
                        "pk": str(is_key).lower() == "true"
                    })
                    if ref_table:
                        foreign_keys.append({"from": col_name, "table": ref_table, "to": "sys_id"})
                col_query_succeeded = True
            except Exception:
                pass

            # Fallback column query (no ReferencedTable) if Attempt 1 failed
            if not col_query_succeeded:
                try:
                    cursor.execute(
                        f"SELECT ColumnName, DataTypeName, IsKey "
                        f"FROM sys_tablecolumns WHERE TableName='{table}'"
                    )
                    for col_name, data_type, is_key in cursor.fetchall():
                        columns.append({
                            "name": col_name,
                            "type": data_type,
                            "pk": str(is_key).lower() == "true"
                        })
                except Exception:
                    pass

            # Attempt 2: ServiceNow sys_dictionary (reference field metadata)
            if not foreign_keys:
                try:
                    cursor.execute(
                        f"SELECT element, reference FROM sys_dictionary "
                        f"WHERE name='{table}' AND reference IS NOT NULL AND reference <> ''"
                    )
                    foreign_keys = [
                        {"from": r[0], "table": r[1], "to": "sys_id"}
                        for r in cursor.fetchall()
                        if r[0] and r[1]
                    ]
                except Exception:
                    pass

            # Attempt 3: sys_foreignkeys (original fallback)
            if not foreign_keys:
                try:
                    cursor.execute(
                        f"SELECT FKCOLUMN_NAME, PKTABLE_NAME FROM sys_foreignkeys "
                        f"WHERE FKTABLE_NAME='{table}'"
                    )
                    foreign_keys = [
                        {"from": r[0], "table": r[1], "to": "sys_id"}
                        for r in cursor.fetchall()
                        if r[1]
                    ]
                except Exception:
                    pass

            schema_data[table] = {
                "table": table,
                "columns": columns,
                "foreign_keys": foreign_keys
            }
    except Exception as e:
        print(f"Error retrieving ServiceNow schema: {e}")
    finally:
        conn.close()
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

def get_oracle_schema(conn_data):
    """
    Retrieves metadata for all tables in an Oracle database for the connected user.
    Returns a dict: { table_name: { columns: [...], foreign_keys: [...] } }
    """
    schema = {}
    conn = create_oracle_connection_from_dict(conn_data)
    if not conn:
        return schema

    try:
        cursor = conn.cursor()

        # 1. Get all tables for the current user
        cursor.execute("SELECT table_name FROM user_tables")
        tables = [row[0] for row in cursor.fetchall()]

        # 2. Get all columns for these tables
        cursor.execute(
            "SELECT table_name, column_name, data_type, nullable"
            " FROM user_tab_columns"
            " ORDER BY table_name, column_id"
        )
        all_columns = cursor.fetchall()

        # Group columns by table
        table_columns = {}
        for t_name, c_name, d_type, nullable in all_columns:
            if t_name not in table_columns:
                table_columns[t_name] = []
            table_columns[t_name].append({
                "name": c_name,
                "type": d_type,
                "nullable": nullable == "Y",
                "pk": False  # Will update below
            })

        # 3. Get Primary Keys
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
        table_fks = {}
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
