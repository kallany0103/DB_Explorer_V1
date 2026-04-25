import sqlite3 as sqlite
from db.db_connections import DB_FILE, create_postgres_connection

def get_all_connections_from_db():
    """Returns a list of dicts with full hierarchical connection info from usf_connections table."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                i.id, c.name, c.code, sc.name, i.name, i.short_name, i.host, i.port, 
                i."database", i.db_path, i.user, i.password,instance_url
            FROM usf_connections i
            LEFT JOIN usf_connection_groups sc ON i.connection_group_id = sc.id
            LEFT JOIN usf_connection_types c ON sc.connection_type_id = c.id
            ORDER BY i.usage_count DESC, c.name, sc.name, i.name
        """)
        rows = c.fetchall()

    connections = []
    for row in rows:
        (connection_id, connection_type_name, code, connection_group_name, connection_name, short_name, host,
         port, dbname, db_path, user, password,instance_url) = row
        full_name = f"{connection_type_name} -> {connection_group_name} -> {connection_name} ({short_name})"
        connections.append({
            "id": connection_id,
            "display_name": full_name,
            "code":code,
            "name": connection_name,
            "short_name": short_name,
            "host": host,
            "port": port,
            "database": dbname,
            "db_path": db_path,
            "user": user,
            "password": password,
            "instance_url": instance_url

        })
    return connections

def get_hierarchy_data():
    """Returns all usf_connection_types, usf_connection_groups, and usf_connections for the main tree view."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, code, name FROM usf_connection_types")
        usf_connection_types = c.fetchall()

        data = []
        for connection_type_id, code, connection_type_name in usf_connection_types:
            connection_type_data = {'id': connection_type_id,'code': code, 'name': connection_type_name, 'usf_connection_groups': []}
            c.execute(
                "SELECT id, name FROM usf_connection_groups WHERE connection_type_id=?", (connection_type_id,))
            connection_groups = c.fetchall()

            for connection_group_id, connection_group_name in connection_groups:
                connection_group_data = {'id': connection_group_id,
                               'name': connection_group_name, 'usf_connections': []}
                c.execute(
                    "SELECT id, name, short_name, host, \"database\", \"user\", password, port, dsn, db_path, instance_url FROM usf_connections WHERE connection_group_id=?", (connection_group_id,))
                usf_connections = c.fetchall()
                for connections in usf_connections:
                    connection_id, name, short_name, host, db, user, pwd, port, dsn, db_path, instance_url = connections
                    conn_data = {"id": connection_id, "name": name, "short_name": short_name, "host": host, "database": db,
                                 "user": user, "password": pwd, "port": port, "dsn": dsn,"db_path": db_path, "instance_url": instance_url, "db_type": code.lower()}
                    connection_group_data['usf_connections'].append(conn_data)
                connection_type_data['usf_connection_groups'].append(connection_group_data)
            data.append(connection_type_data)
    return data

#     except Exception as e:
#         print(f"Error fetching PG stats: {e}")
#     return {"sessions_total":0, "sessions_active":0, "sessions_idle":0, "transactions":0, "tup_ins":0, "tup_upd":0, "tup_del":0, "tup_fet":0, "tup_ret":0}


def get_postgres_state_details(conn_data):
    """Fetches detailed server state including sessions, locks, and prepared transactions."""
    try:
        conn = create_postgres_connection(conn_data)
        if conn:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                # 1. Sessions (Activity)
                cur.execute("""
                    SELECT 
                        pid, usename, datname, application_name, client_addr, 
                        backend_start, query_start, state, query 
                    FROM pg_stat_activity
                    ORDER BY backend_start DESC
                """)
                sessions = cur.fetchall()
                session_cols = [desc[0] for desc in cur.description]

                # 2. Locks
                cur.execute("""
                    SELECT 
                        pid, locktype, mode, granted, 
                        fastpath, waitstart 
                    FROM pg_locks
                    ORDER BY pid
                """)
                locks = cur.fetchall()
                lock_cols = [desc[0] for desc in cur.description]

                # 3. Prepared Transactions
                cur.execute("""
                    SELECT gid, database, owner, prepared 
                    FROM pg_prepared_xacts
                """)
                prepared = cur.fetchall()
                prepared_cols = [desc[0] for desc in cur.description]

                conn.close()
                
                return {
                    "sessions": {"columns": session_cols, "data": sessions},
                    "locks": {"columns": lock_cols, "data": locks},
                    "prepared": {"columns": prepared_cols, "data": prepared}
                }
    except Exception as e:
        print(f"Error fetching PG state details: {e}")
    return {"sessions": {"columns": [], "data": []}, "locks": {"columns": [], "data": []}, "prepared": {"columns": [], "data": []}}

def get_postgres_session_stats(conn_data, current_db_only=False):
    """Fetches high-accuracy PG session, transaction and tuple stats."""
    try:
        conn = create_postgres_connection(conn_data)
        if conn:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                # 1. Session stats
                query_sessions = """
                    SELECT 
                        count(*)::int,
                        count(*) FILTER (WHERE state != 'idle' AND state IS NOT NULL)::int,
                        count(*) FILTER (WHERE state = 'idle')::int
                    FROM pg_stat_activity
                """
                if current_db_only:
                    query_sessions += " WHERE datname = current_database()"
                
                cur.execute(query_sessions)
                row_sessions = cur.fetchone()
                
                # 2. Transaction/Tuple stats - Simplified to match pgAdmin logic
                query_stats = """
                    SELECT 
                        sum(xact_commit)::bigint,
                        sum(xact_rollback)::bigint,
                        sum(tup_inserted)::bigint,
                        sum(tup_updated)::bigint,
                        sum(tup_deleted)::bigint,
                        sum(tup_fetched)::bigint,
                        sum(tup_returned)::bigint,
                        sum(blks_read)::bigint,
                        sum(blks_hit)::bigint
                    FROM pg_stat_database
                """
                if current_db_only:
                    query_stats += " WHERE datname = (SELECT current_database())"
                    cur.execute(query_stats)
                else:
                    cur.execute(query_stats)
                
                row_stats = cur.fetchone()
                
                conn.close()
                
                res = {
                    "sessions_total": 0, "sessions_active": 0, "sessions_idle": 0,
                    "xact_commit": 0, "xact_rollback": 0,
                    "tup_ins": 0, "tup_upd": 0, "tup_del": 0, "tup_fet": 0, "tup_ret": 0,
                    "blks_read": 0, "blks_hit": 0
                }
                
                if row_sessions:
                    res["sessions_total"] = row_sessions[0] or 0
                    res["sessions_active"] = row_sessions[1] or 0
                    res["sessions_idle"] = row_sessions[2] or 0
                
                if row_stats:
                    res["xact_commit"] = row_stats[0] or 0
                    res["xact_rollback"] = row_stats[1] or 0
                    res["tup_ins"] = row_stats[2] or 0
                    res["tup_upd"] = row_stats[3] or 0
                    res["tup_del"] = row_stats[4] or 0
                    res["tup_fet"] = row_stats[5] or 0
                    res["tup_ret"] = row_stats[6] or 0
                    res["blks_read"] = row_stats[7] or 0
                    res["blks_hit"] = row_stats[8] or 0
                
                return res
    except Exception as e:
        print(f"Error fetching PG stats: {e}")
    return {"sessions_total":0, "sessions_active":0, "sessions_idle":0, "transactions":0, "tup_ins":0, "tup_upd":0, "tup_del":0, "tup_fet":0, "tup_ret":0}

def normalize_type(raw_type: str) -> str:
    """Standardizes database types for human-readable display."""
    if not raw_type:
        return ""
    t = raw_type.lower().strip()
    
    mapping = {
        'character varying': 'VARCHAR',
        'character': 'CHAR',
        'integer': 'INT',
        'bigint': 'BIGINT',
        'smallint': 'SMALLINT',
        'boolean': 'BOOL',
        'double precision': 'FLOAT8',
        'real': 'FLOAT4',
        'timestamp without time zone': 'TIMESTAMP',
        'timestamp with time zone': 'TIMESTAMPTZ',
        'time without time zone': 'TIME',
        'numeric': 'DECIMAL',
        'jsonb': 'JSONB',
        'json': 'JSON',
        'uuid': 'UUID',
        'text': 'TEXT',
    }
    
    for key in sorted(mapping.keys(), key=len, reverse=True):
        if t.startswith(key):
            return t.replace(key, mapping[key]).upper()
            
    return raw_type.upper()

def get_connection_types():
    """Returns all available connection types."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, code, name FROM usf_connection_types ORDER BY name")
        rows = c.fetchall()
        return [{"id": r[0], "code": r[1], "name": r[2]} for r in rows]

def get_groups_by_type(type_id):
    """Returns all connection groups for a specific connection type."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM usf_connection_groups WHERE connection_type_id = ? ORDER BY name", (type_id,))
        rows = c.fetchall()
        return [{"id": r[0], "name": r[1]} for r in rows]