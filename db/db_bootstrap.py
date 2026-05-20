import os
import sqlite3 as sqlite
from db.db_connections import DB_FILE

DEFAULT_CONNECTION_TYPES = (
    ("POSTGRES", "PostgreSQL Databases"),
    ("ORACLE", "Oracle Databases"),
    ("SQLITE", "SQLite Databases"),
    ("CSV", "CSV DataStore"),
    ("SERVICENOW", "ServiceNow"),
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
    "CREATE INDEX IF NOT EXISTS idx_usf_query_history_connection ON usf_query_history(connection_id)",
    "CREATE INDEX IF NOT EXISTS idx_usf_processes_server ON usf_processes(server)",
    "CREATE INDEX IF NOT EXISTS idx_usf_processes_status ON usf_processes(status)",
)

def ensure_hierarchy_db():
    """Bootstraps the database schema and default tables if they do not exist."""
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with sqlite.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.executemany(
            "INSERT OR IGNORE INTO usf_connection_types (code, name) VALUES (?, ?)",
            DEFAULT_CONNECTION_TYPES,
        )
        conn.commit()
