import sqlite3 as sqlite
import datetime
from .db_connections import DB_FILE

def add_connection_group(name, parent_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO usf_connection_groups (name, connection_type_id) VALUES (?, ?)", (name, parent_id))
        conn.commit()


def add_connection(data, connection_group_id):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        if "db_path" in data:  # SQLite
            c.execute("INSERT INTO usf_connections (name, short_name, connection_group_id, db_path) VALUES (?, ?,?,?)",
                      (data["name"], data["short_name"], connection_group_id, data["db_path"]))
        else:  # Postgres/Oracle
            c.execute("INSERT INTO usf_connections (name, short_name, connection_group_id, host, \"database\", \"user\", password, port) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (data["name"], data["short_name"], connection_group_id, data["host"], data["database"], data["user"], data["password"], data["port"]))
        conn.commit()


def update_connection(data):
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        if "db_path" in data:  # SQLite
            c.execute("UPDATE usf_connections SET name = ?, short_name = ?, db_path = ? WHERE id = ?",
                      (data["name"], data["short_name"], data["db_path"], data["id"]))
        else:  # Postgres/Oracle
            c.execute("UPDATE usf_connections SET name = ?, short_name = ?, host = ?, database = ?, user = ?, password = ?, port = ? WHERE id = ?",
                      (data["name"], data["short_name"], data["host"], data["database"], data["user"], data["password"], data["port"], data["id"]))
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