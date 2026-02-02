import sqlite3
import psycopg2
from .db_connections import create_sqlite_connection, create_postgres_connection

def get_sqlite_schema(db_path):
    """
    Retrieves metadata for all tables in a SQLite database.
    Returns a dict: { table_name: { columns: [...], foreign_keys: [...] } }
    """
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
            cursor.execute(f"PRAGMA table_info('{table}');")
            columns = []
            for col in cursor.fetchall():
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "pk": bool(col[5])
                })
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list('{table}');")
            foreign_keys = []
            for fk in cursor.fetchall():
                foreign_keys.append({
                    "id": fk[0],
                    "table": fk[2], # target table
                    "from": fk[3],  # source column
                    "to": fk[4]     # target column
                })
            
            schema[table] = {
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
        host=conn_data["host"],
        database=conn_data["database"],
        user=conn_data["user"],
        password=conn_data["password"],
        port=int(conn_data["port"])
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
            
    except Exception as e:
        print(f"Error retrieving Postgres schema: {e}")
    finally:
        conn.close()
        
    return schema_data
