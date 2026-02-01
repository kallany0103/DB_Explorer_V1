import sqlite3 as sqlite
import psycopg2
from psycopg2 import OperationalError
import oracledb
import sys
import os
import datetime
import cdata.servicenow as sn

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Database file path updated
DB_FILE = resource_path("databases/hierarchy.db")

# --- Database Connection Functions ---
def create_sqlite_connection(path):
    """Establishes a connection to a SQLite database."""
    try:
        conn = sqlite.connect(path)
        print("SQLite database connection established.")
        return conn
    except sqlite.Error as e:
        print(f"SQLite connection error: {e}")
        return None


def create_postgres_connection(host, port, database, user, password):
    """Establishes a connection to a PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        print("PostgreSQL database connection established.")
        return conn
    except OperationalError as e:
        print(f"PostgreSQL connection error: {e}")
        return None



def create_oracle_connection(host, port, service_name, user, password):
    """Establishes a connection to an Oracle database."""
    try:
        dsn = f"{host}:{port}/{service_name}"
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
        print("Oracle database connection established.")
        return conn
    except oracledb.DatabaseError as e:
        print(f"Oracle connection error: {e}")
        return None
    
def create_servicenow_connection(conn_data):
    try:
        if not conn_data.get("instance_url"):
            raise ValueError("Missing instance_url in conn_data")

        conn_str = (
            f"User={conn_data['user']};"
            f"Password={conn_data['password']};"
            f"Url={conn_data['instance_url']};"
            f"AuthScheme=Basic;"
            # f"ReadOnly=True"
        )

        conn = sn.connect(conn_str)
        print("ServiceNow connection established.")
        return conn

    except Exception as e:
        print(f"ServiceNow connection error: {e}")
        return None
