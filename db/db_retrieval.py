import sqlite3 as sqlite
from db.db_connections import DB_FILE, create_postgres_connection

def get_all_connections_from_db():
    """Returns a list of dicts with full hierarchical connection info from usf_connections table."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                i.id, c.name, c.code, sc.name, i.name, i.short_name, i.host, i.port, 
                i."database", i.db_path, i.user, i.password, instance_url
            FROM usf_connections i
            LEFT JOIN usf_connection_groups sc ON i.connection_group_id = sc.id
            LEFT JOIN usf_connection_types c ON sc.connection_type_id = c.id
            ORDER BY i.usage_count DESC, c.name, sc.name, i.name
        """)
        rows = c.fetchall()

    connections = []
    for row in rows:
        (connection_id, connection_type_name, code, connection_group_name, connection_name, short_name, host,
         port, dbname, db_path, user, password, instance_url) = row
        full_name = f"{connection_type_name} -> {connection_group_name} -> {connection_name} ({short_name})"
        connections.append({
            "id": connection_id,
            "display_name": full_name,
            "code": code,
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
            connection_type_data = {'id': connection_type_id, 'code': code, 'name': connection_type_name, 'usf_connection_groups': []}
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
                                 "user": user, "password": pwd, "port": port, "dsn": dsn, "db_path": db_path, "instance_url": instance_url, "db_type": code.lower()}
                    connection_group_data['usf_connections'].append(conn_data)
                connection_type_data['usf_connection_groups'].append(connection_group_data)
            data.append(connection_type_data)
    return data


def get_postgres_state_details(conn_data, active_only=False, application_name=None):
    """Fetches detailed server state with dynamic application name."""
    conn = None
    try:
        db_name = conn_data.get('database', 'unknown_db')
        app_name = application_name or f"Universal SQL Client - {db_name}"

        conn = create_postgres_connection(conn_data, application_name=app_name)
        if conn:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                # 1. Sessions (Activity)
                session_query = """
                    SELECT 
                        pid, 
                        datname AS "Database",
                        usename AS "User", 
                        CASE 
                            WHEN application_name IS NULL OR application_name = '' THEN 'External / Unknown'
                            ELSE application_name 
                        END AS "Application", 
                        COALESCE(client_addr::text, 'local') || ':' || client_port AS "Client", 
                        backend_start AS "Backend start", 
                        xact_start AS "Transaction start", 
                        state AS "State", 
                        wait_event_type || ': ' || wait_event AS "Wait event",
                        pg_blocking_pids(pid) AS "Blocking PIDs",
                        backend_type AS "Backend type",
                        query_start AS "Query start",
                        state_change AS "State change",
                        CASE 
                            WHEN state != 'idle' OR state_change > now() - interval '10 second' THEN query 
                            ELSE '' 
                        END AS "SQL"
                    FROM pg_stat_activity
                    WHERE pid != pg_backend_pid() 
                      AND datname = current_database()
                      AND backend_type = 'client backend'
                      AND COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%(Dashboard)%'
                      AND COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%(State)%'
                """
                if active_only:
                    session_query = session_query.replace("WHERE", "WHERE (state IS NOT NULL AND (state != 'idle' OR state_change > now() - interval '10 second')) AND")
                
                session_query += " ORDER BY backend_start DESC"
                
                cur.execute(session_query)
                sessions = cur.fetchall()
                session_cols = [desc[0] for desc in cur.description]

                # 2. Locks
                cur.execute("""
                    SELECT 
                        pid, 
                        locktype AS "Lock type", 
                        COALESCE((SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.oid = relation), relation::text) AS "Target relation", 
                        page AS "Page", 
                        tuple AS "Tuple", 
                        virtualxid AS "vXID", 
                        transactionid AS "XID (target)", 
                        COALESCE((SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.oid = classid), classid::text) AS "Class", 
                        objid AS "Object ID", 
                        virtualtransaction AS "vXID (owner)",
                        mode AS "Mode", 
                        granted AS "Granted?"
                    FROM pg_locks
                    ORDER BY pid
                """)
                locks = cur.fetchall()
                lock_cols = [desc[0] for desc in cur.description]
                
                return {
                    "sessions": {"columns": session_cols, "data": sessions},
                    "locks": {"columns": lock_cols, "data": locks}
                }
    except Exception as e:
        err_msg = str(e).lower()
        if "server closed the connection" not in err_msg and "connection to server" not in err_msg:
            print(f"Error fetching PG state details: {e}")
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
    return {"sessions": {"columns": [], "data": []}, "locks": {"columns": [], "data": []}}

def get_sqlite_state_details(conn_data, local_sessions=None):
    """
    Retrieves state for SQLite.
    'sessions' are simulated using open worksheets in the app (passed as local_sessions).
    'locks' are fetched using PRAGMA lock_status.
    """
    db_path = conn_data.get("db_path")
    if not db_path:
        return {"sessions": {"columns": [], "data": []}, "locks": {"columns": [], "data": []}}
        
    session_cols = ["PID", "Source", "State", "Database", "SQL"]
    session_data = []
    
    if local_sessions:
        for s in local_sessions:
            # Expected format: [pid, source, state, db_path, start_time, last_query]
            session_data.append(s)
            
    lock_cols = ["Database", "Lock Status"]
    lock_data = []
    
    try:
        conn = sqlite.connect(db_path, timeout=1.0)
        try:
            cur = conn.cursor()
            # PRAGMA lock_status is a non-standard but often available pragma in some sqlite builds.
            # If it fails, we fall back to a generic 'Connected' status.
            try:
                cur.execute("PRAGMA lock_status")
                lock_data = cur.fetchall()
            except:
                # Fallback: check if we can get at least the journal mode or sync status
                cur.execute("PRAGMA journal_mode")
                j_mode = cur.fetchone()[0]
                lock_data = [("main", f"Mode: {j_mode.upper()}")]
                
        finally:
            conn.close()
    except:
        pass
        
    return {
        "sessions": {"columns": session_cols, "data": session_data},
        "locks": {"columns": lock_cols, "data": lock_data}
    }

def get_postgres_session_stats(conn_data, current_db_only=False, conn=None):
    """Retrieves session counts, transactions, tuples, and block I/O metrics."""
    res = {}
    should_close = False
    try:
        db_name = conn_data.get("database", "postgres")
        app_name = f"Universal SQL Client - {db_name}"
        
        # Get application-tracked transactions and tuples to filter out system noise
        from workers.signals import tracker
        app_stats = tracker.get_stats()
        
        if conn is None:



            conn = create_postgres_connection(conn_data, application_name=app_name)
            should_close = True
            if conn:
                conn.set_session(readonly=True, autocommit=True)
            
        if conn:
            with conn.cursor() as cur:
                # 1. Session stats (Isolated try-block)
                try:
                    query_sessions = f"""
                        SELECT 
                            count(*) FILTER (WHERE state IS NOT NULL AND (state != 'idle' OR state_change > now() - interval '10 second'))::int as total_active,
                            count(*) FILTER (WHERE COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%')::int as other_total,
                            count(*) FILTER (WHERE application_name ILIKE '%Universal%SQL%Client%(Worksheet)%' AND (state IS NOT NULL AND (state != 'idle' OR state_change > now() - interval '10 second')))::int as our_active,
                            count(*) FILTER (WHERE COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%' AND (state IS NOT NULL AND (state != 'idle' OR state_change > now() - interval '10 second')))::int as other_active_running
                        FROM pg_stat_activity
                        WHERE backend_type = 'client backend'
                          AND COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%(Dashboard)%'
                          AND COALESCE(application_name, '') NOT ILIKE '%Universal%SQL%Client%(State)%'
                        {"AND datname = current_database()" if current_db_only else ""}
                    """
                    cur.execute(query_sessions)
                    row_sessions = cur.fetchone()
                    res.update({
                        "total_active": row_sessions[0] or 0,
                        "other_total": row_sessions[1] or 0,
                        "our_active": row_sessions[2] or 0,
                        "other_active_running": row_sessions[3] or 0
                    })
                except Exception:
                    res.update({"total_active": 0, "other_total": 0, "our_active": 0, "other_active_running": 0})

                # 2. Database stats (Isolated try-block)
                try:
                    query_stats = f"""
                        SELECT 
                            sum(xact_commit)::bigint, sum(xact_rollback)::bigint,
                            sum(tup_inserted)::bigint, sum(tup_updated)::bigint, sum(tup_deleted)::bigint,
                            sum(tup_returned)::bigint, sum(tup_fetched)::bigint,
                            sum(blks_read)::bigint, sum(blks_hit)::bigint
                        FROM pg_stat_database
                        {"WHERE datname = current_database()" if current_db_only else ""}
                    """
                    cur.execute(query_stats)
                    row_stats = cur.fetchone()
                    res.update({
                        "xact_commit": row_stats[0] or 0,
                        "xact_rollback": row_stats[1] or 0,
                        "app_commit": app_stats["commits"],
                        "app_rollback": app_stats["rollbacks"],
                        "app_tup_ins": app_stats["tup_ins"],
                        "app_tup_upd": app_stats["tup_upd"],
                        "app_tup_del": app_stats["tup_del"],
                        "app_tup_fet": app_stats["tup_fet"],
                        "app_tup_ret": app_stats["tup_ret"],
                        "app_exec_time": app_stats["exec_time"],
                        "tup_ins": row_stats[2] or 0,

                        "tup_upd": row_stats[3] or 0,
                        "tup_del": row_stats[4] or 0,
                        "tup_ret": row_stats[5] or 0,
                        "tup_fet": row_stats[6] or 0,
                        "blks_read": row_stats[7] or 0,
                        "blks_hit": row_stats[8] or 0
                    })


                except Exception:
                    res.update({k: 0 for k in ["xact_commit", "xact_rollback", "tup_ins", "tup_upd", "tup_del", "tup_ret", "tup_fet", "blks_read", "blks_hit"]})

                # 3. Tuple stats (Isolated try-block)
                if current_db_only:
                    try:
                        cur.execute("SELECT sum(n_tup_ins)::bigint, sum(n_tup_upd)::bigint, sum(n_tup_del)::bigint FROM pg_stat_user_tables")
                        row_tuples = cur.fetchone()
                        if row_tuples:
                            res["tup_ins"] = row_tuples[0] or res.get("tup_ins", 0)
                            res["tup_upd"] = row_tuples[1] or res.get("tup_upd", 0)
                            res["tup_del"] = row_tuples[2] or res.get("tup_del", 0)
                    except Exception:
                        pass
                
                return res


                
    except Exception as e:
        err_msg = str(e).lower()
        if "server closed the connection" not in err_msg and "connection to server" not in err_msg:
            print(f"Error fetching PG stats: {e}")
    finally:
        if should_close and conn:
            try:
                conn.close()
            except:
                pass
    return None

def get_sqlite_session_stats(conn_data):
    """Fetches basic SQLite stats. Since SQLite is file-based, stats are limited compared to PG."""
    try:
        db_path = conn_data.get('db_path')
        if not db_path:
            return None
        
        # Use a fresh connection with a short timeout
        conn = sqlite.connect(db_path, timeout=1.0)
        try:
            cur = conn.cursor()
            # PRAGMA data_version increments when the database is modified by any connection
            cur.execute("PRAGMA data_version")
            version = cur.fetchone()[0]
            
            cur.execute("PRAGMA page_count")
            pages = cur.fetchone()[0]
            
            cur.execute("PRAGMA freelist_count")
            freelist = cur.fetchone()[0]
            
            cur.execute("PRAGMA schema_version")
            schema_ver = cur.fetchone()[0]
            
            # Exact row count summation for accurate "Tuples In"
            # Exclude internal application tables starting with 'usf_'
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'usf_%'")
            tables = [r[0] for r in cur.fetchall()]
            total_rows = 0
            for table_name in tables:
                try:
                    cur.execute(f'SELECT count(*) FROM "{table_name}"')
                    total_rows += cur.fetchone()[0]
                except:
                    continue
            
            used_pages = pages - freelist
            
            return {
                "sessions_total": 1, 
                "sessions_active": 1,
                "sessions_idle": 0,
                "xact_commit": version + schema_ver,
                "xact_rollback": 0,
                "tup_ins": total_rows, # Exact row count
                "tup_upd": version,
                "tup_del": 0,
                "tup_fet": total_rows + pages,
                "tup_ret": pages,
                "blks_read": pages,
                "blks_hit": used_pages
            }
        finally:
            conn.close()
    except Exception as e:
        return None

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