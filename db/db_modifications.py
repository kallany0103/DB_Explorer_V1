import json
import re
import sqlite3 as sqlite
import datetime
from db.db_connections import DB_FILE, create_postgres_connection

def terminate_postgres_backend(conn_data, pid):
    """Terminates a PostgreSQL backend session by PID."""
    try:
        db_name = conn_data.get('database', 'unknown')
        conn = create_postgres_connection(conn_data, application_name=f"Universal SQL Client - Management ({db_name})")
        if conn:
            conn.set_session(autocommit=True)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
            conn.close()
            return True, None
    except Exception as e:
        return False, str(e)
    return False, "Unknown error"

def cancel_postgres_backend(conn_data, pid):
    """Cancels the current query of a PostgreSQL backend session by PID."""
    try:
        db_name = conn_data.get('database', 'unknown')
        conn = create_postgres_connection(conn_data, application_name=f"Universal SQL Client - Management ({db_name})")
        if conn:
            conn.set_session(autocommit=True)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_cancel_backend(%s)", (pid,))
            conn.close()
            return True, None
    except Exception as e:
        return False, str(e)
    return False, "Unknown error"

def add_connection_group(name, parent_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO usf_connection_groups (name, connection_type_id) VALUES (?, ?)", (name, parent_id))
        conn.commit()




def add_connection(data, connection_group_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()

        # SQLite / CSV
        if data.get("db_path"):
            c.execute(
                """
                INSERT INTO usf_connections
                (name, short_name, connection_group_id, db_path)
                VALUES (?, ?, ?, ?)
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    connection_group_id,
                    data.get("db_path"),
                )
            )

        #  ServiceNow 
        elif data.get("instance_url"):
            c.execute(
                """
                INSERT INTO usf_connections
                (name, short_name, connection_group_id, instance_url, "user", password)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    connection_group_id,
                    data.get("instance_url"),
                    data.get("user"),
                    None,
                )
            )
            connection_id = c.lastrowid
            c.execute("UPDATE usf_connections SET password = ? WHERE id = ?", (data.get("password"), connection_id))

        # Postgres / Oracle
        else:
            c.execute(
                """
                INSERT INTO usf_connections
                (name, short_name, connection_group_id, host, "database", "user", password, port, dsn)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    connection_group_id,
                    data.get("host"),
                    data.get("database"),
                    data.get("user"),
                    data.get("password"),
                    data.get("port"),
                    data.get("dsn"),
                )
            )

        conn.commit()



def update_connection(data):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT password FROM usf_connections WHERE id = ?", (data.get("id"),))
        existing_row = c.fetchone()
        existing_row[0] if existing_row else None

        #  SQLite / CSV 
        if data.get("db_path"):
            c.execute(
                """
                UPDATE usf_connections
                SET name = ?, short_name = ?, connection_group_id = ?, db_path = ?, password = NULL
                WHERE id = ?
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    data.get("connection_group_id"),
                    data.get("db_path"),
                    data.get("id")
                )
            )

        #ServiceNow 
        elif data.get("instance_url"):
            c.execute(
                """
                UPDATE usf_connections
                SET name = ?, short_name = ?, connection_group_id = ?, instance_url = ?, "user" = ?, password = ?
                WHERE id = ?
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    data.get("connection_group_id"),
                    data.get("instance_url"),
                    data.get("user"),
                    data.get("password"),
                    data.get("id")
                )
            )

        # Postgres / Oracle 
        else:
            c.execute(
                """
                UPDATE usf_connections
                SET name = ?, short_name = ?, connection_group_id = ?, host = ?, "database" = ?, "user" = ?, password = ?, port = ?, dsn = ?
                WHERE id = ?
                """,
                (
                    data.get("name"),
                    data.get("short_name"),
                    data.get("connection_group_id"),
                    data.get("host"),
                    data.get("database"),
                    data.get("user"),
                    data.get("password"),
                    data.get("port"),
                    data.get("dsn"),
                    data.get("id")
                )
            )

        conn.commit()


def delete_connection(connection_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM usf_connections WHERE id = ?", (connection_id,))
        c.execute(
            "DELETE FROM usf_query_history WHERE connection_id = ?", (connection_id,))
        conn.commit()


def save_query_history(conn_id, query, status, rows, duration):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO usf_query_history 
            (connection_id, query_text, status, rows_affected, execution_time_sec, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?)""",
                  (conn_id, query, status, rows, duration, datetime.datetime.now().isoformat()))
        conn.commit()

def get_query_history(conn_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, query_text, timestamp, status, rows_affected, execution_time_sec 
            FROM usf_query_history WHERE connection_id = ? ORDER BY timestamp DESC""",
                  (conn_id,))
        return c.fetchall()

def delete_history(history_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM usf_query_history WHERE id = ?", (history_id,))
        conn.commit()

def delete_all_history(conn_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM usf_query_history WHERE connection_id = ?", (conn_id,))
        conn.commit()
#{moitre}

def add_connection_type(name, code):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO usf_connection_types (name, code) VALUES (?, ?)", (name, code))
        conn.commit()

def update_connection_group(group_id, name):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE usf_connection_groups SET name = ? WHERE id = ?", (name, group_id))
        conn.commit()

def delete_connection_group(group_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Delete connections within the group first
        c.execute("SELECT id FROM usf_connections WHERE connection_group_id = ?", (group_id,))
        conn_ids = [row[0] for row in c.fetchall()]
        for conn_id in conn_ids:
            delete_connection(conn_id)
        
        c.execute("DELETE FROM usf_connection_groups WHERE id = ?", (group_id,))
        conn.commit()

def update_connection_type(type_id, name, code):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE usf_connection_types SET name = ?, code = ? WHERE id = ?", (name, code, type_id))
        conn.commit()

def delete_connection_type(type_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Delete groups within the type first
        c.execute("SELECT id FROM usf_connection_groups WHERE connection_type_id = ?", (type_id,))
        group_ids = [row[0] for row in c.fetchall()]
        for group_id in group_ids:
            delete_connection_group(group_id)
            
        c.execute("DELETE FROM usf_connection_types WHERE id = ?", (type_id,))
        conn.commit()
#{moitre}

def add_data_source(connection_id, source_type, data, server_name=None, fdw_name="postgres_fdw"):
    """Inserts a new data source into usf_data_sources table."""
    config_json = data.get("config_json")
    if not config_json and data.get("selected_tables") is not None:
        try:
            config_json = json.dumps({"selected_tables": data.get("selected_tables")})
        except Exception:
            config_json = None

    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO usf_data_sources
            (
                connection_id,
                source_name,
                display_name,
                source_type,
                host,
                port,
                database_name,
                username,
                password,
                schema_name,
                service_url,
                file_path,
                config_json,
                server_name,
                fdw_name,
                status
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            connection_id,
            data.get("short_name") or data.get("source_name") or data.get("name"),
            data.get("name") or data.get("display_name") or data.get("short_name"),
            source_type,
            data.get("host"),
            data.get("port"),
            data.get("database") or data.get("database_name"),
            data.get("user") or data.get("username"),
            data.get("password"),
            data.get("schema") or data.get("schema_name"),
            data.get("instance_url"),
            data.get("db_path"),
            config_json,
            server_name or data.get("server_name"),
            fdw_name or data.get("fdw_name", "postgres_fdw"),
            "ACTIVE"
        ))
        conn.commit()
        return c.lastrowid


def update_data_source(data_source_id, data, server_name=None):
    """Updates an existing data source in usf_data_sources."""
    config_json = data.get("config_json")
    if not config_json and data.get("selected_tables") is not None:
        try:
            config_json = json.dumps({"selected_tables": data.get("selected_tables")})
        except Exception:
            config_json = None

    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE usf_data_sources
            SET source_name = ?,
                display_name = ?,
                host = ?,
                port = ?,
                database_name = ?,
                username = ?,
                password = ?,
                schema_name = ?,
                service_url = ?,
                file_path = ?,
                config_json = ?,
                server_name = COALESCE(?, server_name)
            WHERE id = ?
        """, (
            data.get("short_name") or data.get("source_name") or data.get("name"),
            data.get("name") or data.get("display_name"),
            data.get("host"),
            data.get("port"),
            data.get("database") or data.get("database_name"),
            data.get("user") or data.get("username"),
            data.get("password"),
            data.get("schema") or data.get("schema_name"),
            data.get("instance_url"),
            data.get("db_path"),
            config_json,
            server_name or data.get("server_name"),
            data_source_id
        ))
        conn.commit()


def delete_data_source(data_source_id):
    """Deletes a data source record from usf_data_sources."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM usf_data_sources WHERE id = ?", (data_source_id,))
        conn.commit()


def _sanitize_identifier(name: str) -> str:
    """Sanitizes an input string to be a safe SQL identifier."""
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', str(name or "")).strip('_')
    return cleaned.lower() or "data_source"


def create_postgres_fdw_source(pg_conn_data: dict, ds_data: dict):
    """
    Provisions Foreign Data Wrapper (postgres_fdw), Foreign Server, User Mapping,
    and imports foreign schema/tables into the host PostgreSQL database.
    """
    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (FDW Provisioner)",
        bypass_cooldown=True
    )
    if not conn:
        raise Exception("Could not connect to host PostgreSQL database.")

    try:
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Ensure postgres_fdw extension exists
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgres_fdw;")

        # 2. Determine safe server name
        raw_name = ds_data.get("short_name") or ds_data.get("source_name") or ds_data.get("name") or "foreign_source"
        safe_name = _sanitize_identifier(raw_name)
        server_name = f"srv_{safe_name}"

        remote_host = ds_data.get("host") or "localhost"
        remote_port = str(ds_data.get("port") or 5432)
        remote_db = ds_data.get("database") or ds_data.get("database_name") or "postgres"
        remote_user = ds_data.get("user") or ds_data.get("username") or "postgres"
        remote_password = ds_data.get("password") or ""
        remote_schema = ds_data.get("schema") or ds_data.get("schema_name") or "public"

        # 3. Clean up existing server if present
        cur.execute("SELECT 1 FROM pg_foreign_server WHERE srvname = %s;", (server_name,))
        if cur.fetchone():
            cur.execute(f'DROP SERVER "{server_name}" CASCADE;')

        # 4. Create foreign server
        cur.execute(f"""
            CREATE SERVER "{server_name}"
            FOREIGN DATA WRAPPER postgres_fdw
            OPTIONS (host %s, port %s, dbname %s);
        """, (remote_host, remote_port, remote_db))

        # 5. Create user mapping for current user
        cur.execute(f"""
            CREATE USER MAPPING FOR CURRENT_USER
            SERVER "{server_name}"
            OPTIONS (user %s, password %s);
        """, (remote_user, remote_password))

        # 6. Import foreign schema into a dedicated schema
        local_schema = f"{safe_name}_schema"
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{local_schema}";')
        try:
            selected_tables = ds_data.get("selected_tables") or ds_data.get("tables")
            if selected_tables and isinstance(selected_tables, (list, tuple)) and len(selected_tables) > 0:
                tables_str = ", ".join(f'"{t}"' for t in selected_tables)
                cur.execute(f"""
                    IMPORT FOREIGN SCHEMA "{remote_schema}"
                    LIMIT TO ({tables_str})
                    FROM SERVER "{server_name}"
                    INTO "{local_schema}";
                """)
            else:
                cur.execute(f"""
                    IMPORT FOREIGN SCHEMA "{remote_schema}"
                    FROM SERVER "{server_name}"
                    INTO "{local_schema}";
                """)
        except Exception as import_err:
            # Fallback: if remote schema import fails, try public or log warning
            print(f"Notice: IMPORT FOREIGN SCHEMA warning: {import_err}")

        cur.close()
        return server_name, local_schema
    finally:
        conn.close()


def drop_postgres_fdw_source(pg_conn_data: dict, server_name: str, schema_name: str = None):
    """Drops foreign server and associated schema in the host PostgreSQL database."""
    if not server_name and not schema_name:
        return
    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (FDW Drop)",
        bypass_cooldown=True
    )
    if not conn:
        return

    try:
        conn.autocommit = True
        cur = conn.cursor()
        if server_name:
            cur.execute(f'DROP SERVER IF EXISTS "{server_name}" CASCADE;')
        if schema_name:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')
        cur.close()
    except Exception as e:
        print(f"Error dropping FDW objects: {e}")
    finally:
        conn.close()