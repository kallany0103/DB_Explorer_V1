import csv as _csv_mod
import os
import threading
import sqlite3 as sqlite

try:
    import psycopg2
except ImportError:
    psycopg2 = None


SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT",
    "OFFSET", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS",
    "ON", "AS", "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "ILIKE",
    "BETWEEN", "UNION", "ALL", "DISTINCT", "INSERT", "INTO", "VALUES",
    "UPDATE", "SET", "DELETE", "CREATE", "TABLE", "VIEW", "DROP", "ALTER",
    "ADD", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "INDEX", "UNIQUE",
    "CASE", "WHEN", "THEN", "ELSE", "END", "WITH", "EXISTS", "SCHEMA",
    "DATABASE", "TRUNCATE", "RETURNING", "DEFAULT", "CONSTRAINT", "IF",
    "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION", "GRANT", "REVOKE",
    "EXPLAIN", "ANALYZE", "VERBOSE", "MATERIALIZED", "REFRESH", "COLUMN",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "NULLIF", "CAST",
    "EXTRACT", "NOW", "CURRENT_DATE", "CURRENT_TIMESTAMP", "CURRENT_TIME",
    "BY", "ASC", "DESC", "NULLS", "FIRST", "LAST", "OVER", "PARTITION",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "NTILE",
    "INTERVAL", "DATE", "TIME", "TIMESTAMP", "BOOLEAN", "INTEGER", "TEXT",
    "VARCHAR", "CHAR", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "SERIAL",
    "BIGINT", "SMALLINT", "BIGSERIAL", "TRUE", "FALSE", "VOID",
    "RAISE", "NOTICE", "EXCEPTION", "LANGUAGE", "PLPGSQL", "RETURNS",
    "FUNCTION", "PROCEDURE", "TRIGGER", "BEFORE", "AFTER", "EACH", "ROW",
    "STATEMENT", "EXECUTE", "PERFORM", "DECLARE",
    "REPLACE", "IGNORE", "AUTO_INCREMENT", "COMMENT", "COLLATE",
]

_SQL_KEYWORDS_SET = frozenset(SQL_KEYWORDS)

# Module-level cache: {conn_id: (schemas, tables, schema_tables, table_columns)}
_db_word_cache = {}


def _fetch_db_words(conn_data):
    """
    Query the DB for schema names, table/view names, schema→tables map, and
    table→columns map.  Returns (schemas, tables, schema_tables, table_columns)
    — all empty on any error.  Runs entirely in a background thread.
    """
    if not conn_data:
        return [], [], {}, {}
    code = (conn_data.get("code") or conn_data.get("db_type") or "").upper()
    try:
        if code == "SQLITE":
            db_path = conn_data.get("db_path")
            if not db_path:
                return [], [], {}, {}
            conn = sqlite.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
            tables = [r[0] for r in cur.fetchall()]
            table_columns = {}
            for tbl in tables:
                try:
                    cur.execute(f'PRAGMA table_info("{tbl}")')
                    cols = [r[1] for r in cur.fetchall()]
                    if cols:
                        table_columns[tbl.lower()] = cols
                except Exception:
                    pass
            conn.close()
            return [], tables, {}, table_columns

        elif code == "POSTGRES":
            if psycopg2 is None:
                return [], [], {}, {}
            pg_conn = psycopg2.connect(
                host=conn_data.get("host"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password"),
                port=int(conn_data.get("port", 5432)),
                connect_timeout=3,
            )
            cur = pg_conn.cursor()
            cur.execute(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' "
                "ORDER BY nspname"
            )
            schemas = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                "ORDER BY table_schema, table_name"
            )
            tbl_rows = cur.fetchall()
            cur.execute(
                "SELECT table_name, column_name "
                "FROM information_schema.columns "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                "ORDER BY table_name, ordinal_position"
            )
            col_rows = cur.fetchall()
            pg_conn.close()
            tables = [r[1] for r in tbl_rows]
            schema_tables = {}
            for schema, tbl in tbl_rows:
                schema_tables.setdefault(schema.lower(), []).append(tbl)
            table_columns = {}
            for tbl, col in col_rows:
                table_columns.setdefault(tbl.lower(), []).append(col)
            return schemas, tables, schema_tables, table_columns

        elif code == "CSV":
            path = conn_data.get("db_path", "")
            if not path or not os.path.isdir(path):
                return [], [], {}, {}
            tables = []
            table_columns = {}
            try:
                for fname in sorted(os.listdir(path)):
                    if fname.lower().endswith(".csv"):
                        tbl = os.path.splitext(fname)[0]
                        tables.append(tbl)
                        try:
                            with open(os.path.join(path, fname), newline="", encoding="utf-8", errors="replace") as f:
                                headers = next(_csv_mod.reader(f), [])
                                cols = [h.strip() for h in headers if h.strip()]
                                if cols:
                                    table_columns[tbl.lower()] = cols
                        except Exception:
                            pass
            except Exception as e:
                print(f"CSV autocomplete fetch error: {e}")
            return [], tables, {}, table_columns

        elif code == "SERVICENOW":
            try:
                from db.db_connections import create_servicenow_connection
                conn = create_servicenow_connection(conn_data)
                if not conn:
                    return [], [], {}, {}
                cur = conn.cursor()
                cur.execute("SELECT TableName FROM sys_tables")
                tables = [row[0] for row in cur.fetchall()]
                conn.close()
                return [], tables, {}, {}
            except Exception as e:
                print(f"ServiceNow autocomplete fetch error: {e}")

    except Exception:
        pass
    return [], [], {}, {}



def fetch_columns(conn_data, table_name):
    """
    Fetch column names for a table from the active connection.
    Returns [] silently on any error.
    """
    if not conn_data or not table_name:
        return []
    code = (conn_data.get("code") or conn_data.get("db_type") or "").upper()
    try:
        if code == "SQLITE":
            db_path = conn_data.get("db_path")
            if not db_path:
                return []
            conn = sqlite.connect(db_path)
            cur = conn.cursor()
            cur.execute(f'PRAGMA table_info("{table_name}")')
            rows = cur.fetchall()
            conn.close()
            return [r[1] for r in rows]

        elif code == "POSTGRES":
            if psycopg2 is None:
                return []
            pg_conn = psycopg2.connect(
                host=conn_data.get("host"),
                database=conn_data.get("database"),
                user=conn_data.get("user"),
                password=conn_data.get("password"),
                port=int(conn_data.get("port", 5432)),
                connect_timeout=3,
            )
            cur = pg_conn.cursor()
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position",
                (table_name,),
            )
            rows = cur.fetchall()
            pg_conn.close()
            return [r[0] for r in rows]

        elif code == "CSV":
            path = conn_data.get("db_path", "")
            if not path:
                return []
            csv_file = os.path.join(path, table_name + ".csv")
            if not os.path.isfile(csv_file):
                try:
                    for fname in os.listdir(path):
                        if fname.lower() == table_name.lower() + ".csv":
                            csv_file = os.path.join(path, fname)
                            break
                    else:
                        return []
                except Exception:
                    return []
            try:
                with open(csv_file, newline="", encoding="utf-8", errors="replace") as f:
                    headers = next(_csv_mod.reader(f), [])
                    return [h.strip() for h in headers if h.strip()]
            except Exception:
                pass

        elif code == "SERVICENOW":
            try:
                from db.db_connections import create_servicenow_connection
                conn = create_servicenow_connection(conn_data)
                if not conn:
                    return []
                cur = conn.cursor()
                cur.execute(f"SELECT ColumnName FROM sys_tablecolumns WHERE TableName='{table_name}'")
                cols = [row[0] for row in cur.fetchall()]
                conn.close()
                return cols
            except Exception:
                pass

    except Exception:
        pass
    return []


class CompletionEngine:
    """
    Schema-aware SQL completion engine for CodeEditor.
    No Qt dependency — pure Python + background thread for DB queries.
    """

    def __init__(self):
        self._base_list = list(SQL_KEYWORDS)
        self._active_list = self._base_list
        self._schema_names = []        # kept separate for dot-context detection
        self._schema_tables = {}       # {schema_lower: [table_names]} — pre-fetched
        self._table_columns = {}       # {table_lower: [col_names]}    — pre-fetched
        self._conn_data = None

    def refresh(self, conn_data):
        """
        Rebuild word list (keywords + schema names + table names) for conn_data.
        The DB query runs in a background thread to avoid blocking the UI.
        """
        self._conn_data = conn_data
        if not conn_data:
            self._base_list = list(SQL_KEYWORDS)
            self._active_list = self._base_list
            self._schema_names = []
            return

        conn_id = conn_data.get("id")
        if conn_id and conn_id in _db_word_cache:
            schemas, tables, schema_tables, table_columns = _db_word_cache[conn_id]
            self._schema_names = schemas
            self._schema_tables = schema_tables
            self._table_columns = table_columns
            self._base_list = SQL_KEYWORDS + schemas + tables
            self._active_list = self._base_list
            return

        def _bg():
            schemas, tables, schema_tables, table_columns = _fetch_db_words(conn_data)
            if conn_id:
                _db_word_cache[conn_id] = (schemas, tables, schema_tables, table_columns)
            self._schema_names = schemas
            self._schema_tables = schema_tables
            self._table_columns = table_columns
            self._base_list = SQL_KEYWORDS + schemas + tables
            self._active_list = self._base_list

        threading.Thread(target=_bg, daemon=True).start()

    def best_match(self, prefix):
        """
        Return the first word in the active list that starts with prefix
        (case-insensitive) and is longer than the prefix. Returns '' if none.
        """
        if not prefix:
            return ""
        p = prefix.lower()
        for word in self._active_list:
            if word.lower().startswith(p) and len(word) > len(prefix):
                return word
        return ""

    def is_keyword(self, word):
        """Return True if word (any case) is a SQL keyword."""
        return bool(word) and word.upper() in _SQL_KEYWORDS_SET

    def is_schema(self, word):
        """Return True if word matches a known schema name (case-insensitive)."""
        if not word:
            return False
        wl = word.lower()
        return any(s.lower() == wl for s in self._schema_names)

    def fetch_for_schema_dot(self, conn_data, schema_name):
        """
        Return pre-fetched tables for schema_name and activate them as the
        current completion list. Pure dict lookup — no DB call, no freeze.
        """
        tables = self._schema_tables.get(schema_name.lower(), [])
        if tables:
            self._active_list = list(tables)
        return tables

    def get_columns_for_table(self, conn_data, table_name):
        """
        Return pre-fetched columns for table_name, or fetch dynamically if missing.
        """
        columns = self._table_columns.get(table_name.lower(), [])
        if not columns:
            columns = fetch_columns(conn_data, table_name)
            if columns:
                self._table_columns[table_name.lower()] = columns
        
        if columns:
            self._active_list = list(columns)
        return columns

    def activate_dot_mode(self, columns):
        """Activate an arbitrary column list (fallback for non-cached tables)."""
        if columns:
            self._active_list = list(columns)

    def reset_active_list(self):
        """Return to keyword + schema + table completion."""
        self._active_list = self._base_list
