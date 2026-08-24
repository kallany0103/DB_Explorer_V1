import os
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
        local_schema = ds_data.get("schema_name")
        if not local_schema or local_schema.lower() in ("public", "siam", "suprava", "test", "test2", "test5", "pg_catalog", "information_schema"):
            local_schema = f"{safe_name}_schema"

        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{local_schema}";')
        cur.execute(f"""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (
                    SELECT c.relname, c.relkind
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = '{local_schema}'
                )
                LOOP
                    IF r.relkind = 'f' THEN
                        EXECUTE format('DROP FOREIGN TABLE IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'v' THEN
                        EXECUTE format('DROP VIEW IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'm' THEN
                        EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'r' THEN
                        EXECUTE format('DROP TABLE IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    END IF;
                END LOOP;
            END $$;
        """)

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


def sync_postgres_fdw_schema(pg_conn_data: dict, ds_data: dict):
    """
    Re-synchronizes foreign schema from remote data source into host PostgreSQL database.
    Drops existing foreign tables in the data source schema and re-executes IMPORT FOREIGN SCHEMA.
    """
    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (FDW Sync)",
        bypass_cooldown=True
    )
    if not conn:
        raise Exception("Could not connect to host PostgreSQL database.")

    try:
        conn.autocommit = True
        cur = conn.cursor()

        raw_name = ds_data.get("short_name") or ds_data.get("source_name") or ds_data.get("name") or "foreign_source"
        safe_name = _sanitize_identifier(raw_name)
        server_name = ds_data.get("server_name") or f"srv_{safe_name}"

        # Protect against collisions with native schemas or public
        local_schema = ds_data.get("schema_name")
        if not local_schema or local_schema.lower() in ("public", "siam", "suprava", "test", "test2", "test5", "pg_catalog", "information_schema"):
            local_schema = f"{safe_name}_schema"

        remote_schema = ds_data.get("schema") or "public"

        # Verify server exists
        cur.execute("SELECT 1 FROM pg_foreign_server WHERE srvname = %s;", (server_name,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            s_name, l_schema = create_postgres_fdw_source(pg_conn_data, ds_data)
            return s_name, l_schema, 0

        # Drop existing relations in local_schema for this data source
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{local_schema}";')
        cur.execute(f"""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (
                    SELECT c.relname, c.relkind
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = '{local_schema}'
                )
                LOOP
                    IF r.relkind = 'f' THEN
                        EXECUTE format('DROP FOREIGN TABLE IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'v' THEN
                        EXECUTE format('DROP VIEW IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'm' THEN
                        EXECUTE format('DROP MATERIALIZED VIEW IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    ELSIF r.relkind = 'r' THEN
                        EXECUTE format('DROP TABLE IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    END IF;
                END LOOP;
            END $$;
        """)

        # Parse selected_tables if any
        selected_tables = ds_data.get("selected_tables")
        if not selected_tables and ds_data.get("config_json"):
            try:
                cfg = json.loads(ds_data["config_json"]) if isinstance(ds_data["config_json"], str) else ds_data["config_json"]
                selected_tables = cfg.get("selected_tables")
            except Exception:
                pass

        # Re-import foreign schema
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

        # Query count of imported foreign tables
        cur.execute("""
            SELECT count(*)
            FROM pg_foreign_table ft
            JOIN pg_foreign_server s ON s.oid = ft.ftserver
            WHERE s.srvname = %s;
        """, (server_name,))
        count = cur.fetchone()[0]

        cur.close()
        return server_name, local_schema, count
    finally:
        conn.close()


def ensure_host_fdw_extensions(pg_conn_data: dict) -> dict:
    """
    Automatically installs/enables necessary FDW extensions on a host PostgreSQL database:
    - postgres_fdw
    - sqlite_fdw
    - oracle_fdw
    - file_fdw
    Returns a dict mapping extension name to boolean success.
    """
    if not pg_conn_data or not (pg_conn_data.get("host") or pg_conn_data.get("dsn")):
        return {}

    conn = None
    results = {}
    try:
        conn = create_postgres_connection(
            pg_conn_data,
            application_name="Universal SQL Client (FDW Extensions Auto-Installer)",
            bypass_cooldown=True
        )
        if not conn:
            return results

        conn.autocommit = True
        cur = conn.cursor()

        extensions = [
            ("postgres_fdw", "PostgreSQL Foreign Data Wrapper"),
            ("sqlite_fdw", "SQLite Foreign Data Wrapper"),
            ("oracle_fdw", "Oracle Foreign Data Wrapper"),
            ("file_fdw", "File/CSV Foreign Data Wrapper"),
        ]

        for ext_name, desc in extensions:
            try:
                cur.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext_name}";')
                results[ext_name] = True
                print(f"[FDW Auto-Installer] Extension '{ext_name}' ({desc}) enabled successfully.")
            except Exception as ext_err:
                results[ext_name] = False
                print(f"[FDW Auto-Installer] Extension '{ext_name}' ({desc}) notice: {ext_err}")

        cur.close()
    except Exception as e:
        print(f"[FDW Auto-Installer] Could not auto-install extensions on host: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def test_data_source_connection(ds_data: dict, host_conn_data: dict = None) -> tuple:
    """
    Tests connection to a data source (PostgreSQL, SQLite, Oracle, etc.).
    Returns (is_connected: bool, message: str, latency_ms: float).
    """
    import time
    import sqlite3
    source_type = (ds_data.get("source_type") or ds_data.get("db_type") or "POSTGRES").upper()
    start_time = time.time()

    if source_type == "SQLITE":
        db_path = ds_data.get("db_path") or ds_data.get("file_path")
        if not db_path or not os.path.exists(db_path):
            return False, f"Database file not found: '{db_path}'", 0.0
        try:
            with sqlite3.connect(db_path, timeout=3.0) as s_conn:
                s_cur = s_conn.cursor()
                s_cur.execute("SELECT 1;")
                s_cur.fetchone()
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            return True, "SQLite database file accessible and healthy.", elapsed_ms
        except Exception as e:
            return False, f"SQLite connection failed: {e}", 0.0

    elif source_type in ("CSV", "FILE", "FLAT_FILE"):
        file_path = ds_data.get("file_path") or ds_data.get("db_path")
        if not file_path or not os.path.exists(file_path):
            return False, f"CSV file or directory not found: '{file_path}'", 0.0
        elapsed_ms = round((time.time() - start_time) * 1000, 1)
        return True, "CSV file/directory accessible and healthy.", elapsed_ms

    elif source_type in ("POSTGRES", "POSTGRESQL"):
        target_conn = {
            'host': ds_data.get("host"),
            'port': ds_data.get("port") or 5432,
            'database': ds_data.get("database") or "postgres",
            'user': ds_data.get("user") or ds_data.get("username"),
            'password': ds_data.get("password"),
            'connect_timeout': 4
        }
        if not target_conn['host'] and host_conn_data:
            target_conn = host_conn_data

        try:
            conn = create_postgres_connection(
                target_conn,
                application_name="Universal SQL Client (DS Ping)",
                bypass_cooldown=True
            )
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                cur.fetchone()
                cur.close()
                conn.close()
                elapsed_ms = round((time.time() - start_time) * 1000, 1)
                return True, "PostgreSQL connection succeeded.", elapsed_ms
            return False, "Could not establish connection to PostgreSQL server.", 0.0
        except Exception as e:
            return False, f"PostgreSQL ping error: {e}", 0.0

    elif source_type in ("ORACLE", "ORACLE_DB"):
        try:
            import cx_Oracle
            dsn = ds_data.get("dsn") or ds_data.get("host")
            user = ds_data.get("user") or ds_data.get("username")
            pwd = ds_data.get("password")
            o_conn = cx_Oracle.connect(user, pwd, dsn)
            o_cur = o_conn.cursor()
            o_cur.execute("SELECT 1 FROM DUAL")
            o_cur.fetchone()
            o_cur.close()
            o_conn.close()
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            return True, "Oracle connection succeeded.", elapsed_ms
        except Exception as e:
            return False, f"Oracle ping error: {e}", 0.0

    elapsed_ms = round((time.time() - start_time) * 1000, 1)
    return True, "Data Source registered.", elapsed_ms


def create_sqlite_fdw_source(pg_conn_data: dict, ds_data: dict):
    """
    Provisions Foreign Data Wrapper (sqlite_fdw) if available on PostgreSQL host,
    or registers SQLite Data Source with client-side introspection.
    """
    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (SQLite FDW Provisioner)",
        bypass_cooldown=True
    )
    if not conn:
        raise Exception("Could not connect to host PostgreSQL database.")

    try:
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Try to ensure sqlite_fdw extension exists
        has_sqlite_fdw = False
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS sqlite_fdw;")
            has_sqlite_fdw = True
        except Exception as ext_err:
            print(f"Notice: sqlite_fdw extension not available on PostgreSQL host: {ext_err}")

        # 2. Determine safe server name
        raw_name = ds_data.get("short_name") or ds_data.get("source_name") or ds_data.get("name") or "sqlite_source"
        safe_name = _sanitize_identifier(raw_name)
        server_name = f"srv_{safe_name}"
        db_path = ds_data.get("db_path") or ds_data.get("file_path") or ""

        if not db_path:
            raise Exception("SQLite database file path is required.")

        local_schema = f"{safe_name}_schema"

        if has_sqlite_fdw:
            # 3. Clean up existing server if present
            cur.execute("SELECT 1 FROM pg_foreign_server WHERE srvname = %s;", (server_name,))
            if cur.fetchone():
                cur.execute(f'DROP SERVER "{server_name}" CASCADE;')

            # 4. Create foreign server
            cur.execute(f"""
                CREATE SERVER "{server_name}"
                FOREIGN DATA WRAPPER sqlite_fdw
                OPTIONS (database %s);
            """, (db_path,))

            # 5. User mapping (optional in sqlite_fdw)
            try:
                cur.execute(f'CREATE USER MAPPING FOR CURRENT_USER SERVER "{server_name}";')
            except Exception:
                pass

            # 6. Import foreign schema into a dedicated schema
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{local_schema}";')
            try:
                selected_tables = ds_data.get("selected_tables") or ds_data.get("tables")
                if selected_tables and isinstance(selected_tables, (list, tuple)) and len(selected_tables) > 0:
                    tables_str = ", ".join(f'"{t}"' for t in selected_tables)
                    cur.execute(f"""
                        IMPORT FOREIGN SCHEMA public
                        LIMIT TO ({tables_str})
                        FROM SERVER "{server_name}"
                        INTO "{local_schema}";
                    """)
                else:
                    cur.execute(f"""
                        IMPORT FOREIGN SCHEMA public
                        FROM SERVER "{server_name}"
                        INTO "{local_schema}";
                    """)
            except Exception as import_err:
                print(f"Notice: sqlite_fdw IMPORT FOREIGN SCHEMA warning: {import_err}")

        cur.close()
        return server_name, local_schema
    finally:
        conn.close()


def sync_sqlite_fdw_schema(pg_conn_data: dict, ds_data: dict):
    """
    Re-synchronizes SQLite foreign schema into host PostgreSQL database or local metadata.
    """
    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (SQLite FDW Sync)",
        bypass_cooldown=True
    )
    if not conn:
        raise Exception("Could not connect to host PostgreSQL database.")

    try:
        conn.autocommit = True
        cur = conn.cursor()

        raw_name = ds_data.get("short_name") or ds_data.get("source_name") or ds_data.get("name") or "sqlite_source"
        safe_name = _sanitize_identifier(raw_name)
        server_name = ds_data.get("server_name") or f"srv_{safe_name}"
        local_schema = ds_data.get("schema_name") or f"{safe_name}_schema"

        # Check if server exists on host
        cur.execute("SELECT 1 FROM pg_foreign_server WHERE srvname = %s;", (server_name,))
        if cur.fetchone():
            # Drop existing foreign tables in local_schema for this server
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{local_schema}";')
            cur.execute(f"""
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (
                        SELECT c.relname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        JOIN pg_foreign_table ft ON ft.ftrelid = c.oid
                        JOIN pg_foreign_server s ON s.oid = ft.ftserver
                        WHERE n.nspname = '{local_schema}' AND s.srvname = '{server_name}'
                    )
                    LOOP
                        EXECUTE format('DROP FOREIGN TABLE IF EXISTS "%I"."%I" CASCADE;', '{local_schema}', r.relname);
                    END LOOP;
                END $$;
            """)

            # Parse selected_tables if any
            selected_tables = ds_data.get("selected_tables")
            if not selected_tables and ds_data.get("config_json"):
                try:
                    cfg = json.loads(ds_data["config_json"]) if isinstance(ds_data["config_json"], str) else ds_data["config_json"]
                    selected_tables = cfg.get("selected_tables")
                except Exception:
                    pass

            # Re-import foreign schema
            if selected_tables and isinstance(selected_tables, (list, tuple)) and len(selected_tables) > 0:
                tables_str = ", ".join(f'"{t}"' for t in selected_tables)
                cur.execute(f"""
                    IMPORT FOREIGN SCHEMA public
                    LIMIT TO ({tables_str})
                    FROM SERVER "{server_name}"
                    INTO "{local_schema}";
                """)
            else:
                cur.execute(f"""
                    IMPORT FOREIGN SCHEMA public
                    FROM SERVER "{server_name}"
                    INTO "{local_schema}";
                """)

            # Query count of imported foreign tables
            cur.execute("""
                SELECT count(*)
                FROM pg_foreign_table ft
                JOIN pg_foreign_server s ON s.oid = ft.ftserver
                WHERE s.srvname = %s;
            """, (server_name,))
            count = cur.fetchone()[0]
        else:
            # Direct SQLite count
            count = 0
            db_path = ds_data.get("db_path") or ds_data.get("file_path")
            if db_path and os.path.exists(db_path):
                try:
                    import sqlite3 as s_reader
                    with s_reader.connect(db_path) as sc:
                        cc = sc.cursor()
                        cc.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
                        count = cc.fetchone()[0]
                except Exception:
                    pass

        cur.close()
        return server_name, local_schema, count
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


def inspect_csv_schema(file_path: str, delimiter: str = None, has_header: bool = True, sample_lines: int = 100) -> dict:
    """
    Inspects a CSV file to auto-detect delimiter, column names, data types, and sample data.
    Returns dict with keys: 'delimiter', 'has_header', 'columns', 'sample_rows'.
    """
    import csv
    if not file_path or not os.path.exists(file_path):
        return {"delimiter": ",", "has_header": True, "columns": [], "sample_rows": []}

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            sample_data = f.read(4096)
            f.seek(0)

            if not delimiter or delimiter == "AUTO":
                try:
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(sample_data, delimiters=",;\t|")
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ","

            reader = csv.reader(f, delimiter=delimiter)
            rows = []
            for i, row in enumerate(reader):
                if i >= sample_lines:
                    break
                if row:
                    rows.append(row)

            if not rows:
                return {"delimiter": delimiter, "has_header": has_header, "columns": [], "sample_rows": []}

            if has_header:
                header = [str(c).strip() for c in rows[0]]
                data_rows = rows[1:]
            else:
                header = [f"col_{j+1}" for j in range(len(rows[0]))]
                data_rows = rows

            columns = []
            num_cols = len(header)

            for col_idx in range(num_cols):
                col_name = header[col_idx] if header[col_idx] else f"column_{col_idx+1}"
                col_name = _sanitize_identifier(col_name)

                is_int = True
                is_numeric = True
                is_bool = True
                has_values = False

                for r in data_rows:
                    if col_idx < len(r):
                        val = r[col_idx].strip()
                        if val == "":
                            continue
                        has_values = True
                        if is_int:
                            try:
                                int(val)
                            except ValueError:
                                is_int = False
                        if is_numeric:
                            try:
                                float(val)
                            except ValueError:
                                is_numeric = False
                        if is_bool:
                            if val.lower() not in ("true", "false", "t", "f", "1", "0", "yes", "no"):
                                is_bool = False

                if has_values and is_int:
                    inferred_type = "INTEGER"
                elif has_values and is_numeric:
                    inferred_type = "NUMERIC"
                elif has_values and is_bool:
                    inferred_type = "BOOLEAN"
                else:
                    inferred_type = "TEXT"

                columns.append({
                    "name": col_name,
                    "type": inferred_type,
                    "original_name": header[col_idx]
                })

            return {
                "delimiter": delimiter,
                "has_header": has_header,
                "columns": columns,
                "sample_rows": data_rows[:10]
            }
    except Exception as e:
        print(f"Error inspecting CSV file {file_path}: {e}")
        return {"delimiter": delimiter or ",", "has_header": has_header, "columns": [], "sample_rows": []}


def create_file_fdw_source(pg_conn_data: dict, ds_data: dict):
    """
    Provisions Foreign Data Wrapper (file_fdw) on host PostgreSQL database
    or registers CSV Data Source for client-side virtual table queries.
    """
    raw_name = ds_data.get("short_name") or ds_data.get("source_name") or ds_data.get("name") or "csv_source"
    safe_name = _sanitize_identifier(raw_name)
    server_name = f"srv_{safe_name}"
    local_schema = f"{safe_name}_schema"

    csv_files = ds_data.get("csv_files") or []
    file_path = ds_data.get("file_path") or ds_data.get("db_path")
    if not csv_files and file_path:
        csv_files = [{
            "file_path": file_path,
            "table_name": _sanitize_identifier(os.path.splitext(os.path.basename(file_path))[0]),
            "delimiter": ds_data.get("delimiter", ","),
            "has_header": ds_data.get("has_header", True),
            "columns": ds_data.get("columns", [])
        }]

    conn = create_postgres_connection(
        pg_conn_data,
        application_name="Universal SQL Client (file_fdw Provisioner)",
        bypass_cooldown=True
    )
    if not conn:
        raise Exception("Could not connect to host PostgreSQL database.")

    count = 0
    try:
        conn.autocommit = True
        cur = conn.cursor()

        try:
            cur.execute('CREATE EXTENSION IF NOT EXISTS "file_fdw";')
        except Exception as ext_err:
            print(f"Notice: file_fdw extension notice on host: {ext_err}")

        cur.execute(f'DROP SERVER IF EXISTS "{server_name}" CASCADE;')
        cur.execute(f'DROP SCHEMA IF EXISTS "{local_schema}" CASCADE;')

        cur.execute(f'CREATE SERVER "{server_name}" FOREIGN DATA WRAPPER "file_fdw";')
        cur.execute(f'CREATE SCHEMA "{local_schema}";')

        for item in csv_files:
            c_path = item.get("file_path")
            if not c_path:
                continue
            tbl_name = _sanitize_identifier(item.get("table_name") or os.path.splitext(os.path.basename(c_path))[0])
            delim = item.get("delimiter") or ds_data.get("delimiter") or ","
            header = "true" if item.get("has_header", True) else "false"

            cols = item.get("columns")
            if not cols:
                inspected = inspect_csv_schema(c_path, delimiter=delim, has_header=(header == "true"))
                cols = inspected.get("columns", [])

            if not cols:
                cols = [{"name": "data", "type": "TEXT"}]

            col_defs = ", ".join(f'"{c["name"]}" {c["type"]}' for c in cols)
            escaped_path = c_path.replace("'", "''")
            escaped_delim = delim.replace("'", "''")

            try:
                cur.execute(f"""
                    CREATE FOREIGN TABLE "{local_schema}"."{tbl_name}" (
                        {col_defs}
                    ) SERVER "{server_name}"
                    OPTIONS (filename '{escaped_path}', format 'csv', header '{header}', delimiter '{escaped_delim}');
                """)
                count += 1
            except Exception as tbl_err:
                print(f"Notice: Could not create foreign table for {tbl_name}: {tbl_err}")

        cur.close()
        return server_name, local_schema, count
    finally:
        conn.close()