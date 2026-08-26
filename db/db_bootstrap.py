import os
import shutil
import sys
import sqlite3 as sqlite
from db.db_connections import DB_FILE

DEFAULT_CONNECTION_TYPES = (
    ("ORACLE_FA", "Oracle Fusion Applications"),
    ("ORACLE_DB", "Oracle Databases"),
    ("POSTGRES", "PostgreSQL Databases"),
    ("SQLITE", "SQLite Databases"),
    ("SERVICENOW", "ServiceNow"),
    ("UDS", "Unified Data Sources"),
    ("CSV", "CSV DataStore"),
)

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS usf_connection_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usf_connection_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        connection_type_id INTEGER NOT NULL,
        FOREIGN KEY (connection_type_id) REFERENCES usf_connection_types(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usf_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        short_name TEXT,
        connection_group_id INTEGER,
        host TEXT,
        database TEXT,
        user TEXT,
        password TEXT,
        port INTEGER,
        dsn TEXT,
        db_path TEXT,
        instance_url TEXT,
        usage_count INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (connection_group_id) REFERENCES usf_connection_groups(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usf_data_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id INTEGER NOT NULL,
        source_name TEXT,
        display_name TEXT,
        source_type TEXT NOT NULL,
        host TEXT,
        port INTEGER,
        database_name TEXT,
        username TEXT,
        password TEXT,
        schema_name TEXT,
        service_url TEXT,
        file_path TEXT,
        config_json TEXT,
        server_name TEXT,
        fdw_name TEXT DEFAULT 'postgres_fdw',
        status TEXT DEFAULT 'ACTIVE',
        FOREIGN KEY (connection_id) REFERENCES usf_connections(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usf_query_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        connection_id INTEGER,
        query_text TEXT,
        status TEXT,
        rows_affected INTEGER,
        execution_time_sec REAL,
        timestamp TEXT,
        FOREIGN KEY (connection_id) REFERENCES usf_connections(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usf_processes (
        pid TEXT PRIMARY KEY,
        process_name TEXT,
        type TEXT,
        status TEXT,
        server TEXT,
        object TEXT,
        time_taken REAL,
        start_time TEXT,
        end_time TEXT,
        details TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_usf_connection_groups_type ON usf_connection_groups(connection_type_id)",
    "CREATE INDEX IF NOT EXISTS idx_usf_connections_group ON usf_connections(connection_group_id)",
    "CREATE INDEX IF NOT EXISTS idx_usf_data_sources_connection ON usf_data_sources(connection_id)",
    "CREATE INDEX IF NOT EXISTS idx_usf_query_history_connection ON usf_query_history(connection_id)",
    "CREATE INDEX IF NOT EXISTS idx_usf_processes_server ON usf_processes(server)",
    "CREATE INDEX IF NOT EXISTS idx_usf_processes_status ON usf_processes(status)",
)

def get_bundled_path(relative_path):
    """Helper to find files bundled by PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def ensure_hierarchy_db():
    """Bootstraps the database schema and default tables if they do not exist."""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Always overwrite local DB with the bundled, pre-populated database on startup
    # if not os.path.exists(DB_FILE):
    bundled_db = get_bundled_path("databases/hierarchy.db")
    if os.path.exists(bundled_db) and bundled_db != DB_FILE:
        try:
            shutil.copy2(bundled_db, DB_FILE)
            print(f"Copied pre-populated database from {bundled_db} to {DB_FILE}")
        except Exception as e:
            print(f"Failed to copy bundled database: {e}")

    with sqlite.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)

        conn.executemany(
            "INSERT OR IGNORE INTO usf_connection_types (code, name) VALUES (?, ?)",
            DEFAULT_CONNECTION_TYPES,
        )

        # Ensure missing columns in usf_data_sources are added
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(usf_data_sources)")
            existing_cols = {row[1] for row in cur.fetchall()}
            if "server_name" not in existing_cols:
                conn.execute("ALTER TABLE usf_data_sources ADD COLUMN server_name TEXT")
            if "fdw_name" not in existing_cols:
                conn.execute("ALTER TABLE usf_data_sources ADD COLUMN fdw_name TEXT DEFAULT 'postgres_fdw'")
        except Exception as e:
            print(f"Migration check error: {e}")

        # Ensure missing columns in usf_processes are added
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(usf_processes)")
            proc_cols = {row[1] for row in cur.fetchall()}
            if "process_name" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN process_name TEXT")
            if "server" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN server TEXT")
            if "object" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN object TEXT")
            if "time_taken" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN time_taken REAL")
            if "start_time" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN start_time TEXT")
            if "end_time" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN end_time TEXT")
            if "details" not in proc_cols:
                conn.execute("ALTER TABLE usf_processes ADD COLUMN details TEXT")
        except Exception as e:
            print(f"Migration check error for usf_processes: {e}")

        conn.commit()
