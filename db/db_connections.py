import sqlite3 as sqlite
import psycopg2
from psycopg2 import OperationalError
import oracledb
import sys
import os
import cdata.servicenow as sn_driver
import cdata.csv as csv_driver

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
        return conn
    except sqlite.Error as e:
        print(f"SQLite connection error: {e}")
        return None


def create_postgres_connection(host, port=None, database=None, user=None, password=None):
    """Establishes a connection to a PostgreSQL database with SSL support for cloud hosts."""
    try:
        if isinstance(host, dict):
            conn_data = host
            dsn = conn_data.get("dsn")
            if dsn:
                try:
                    return psycopg2.connect(dsn, connect_timeout=5)
                except Exception as e:
                    print(f"DSN connection failed, falling back to keywords: {e}")

            host = conn_data.get("host")
            port = conn_data.get("port")
            database = conn_data.get("database")
            user = conn_data.get("user")
            password = conn_data.get("password")

        # Basic connection parameters
        params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "connect_timeout": 5
        }
        
        # If the host looks like an Aive/ElephantSQL/AWS host, or if first attempt fails, try with SSL
        try:
            conn = psycopg2.connect(**params)
            return conn
        except OperationalError:
            # Retry with SSL for cloud providers
            params["sslmode"] = "require"
            conn = psycopg2.connect(**params)
            return conn
            
    except OperationalError as e:
        print(f"PostgreSQL connection error: {e}")
        return None


def create_oracle_connection(host, port, service_name, user, password):
    """Establishes a connection to an Oracle database."""
    try:
        dsn = f"{host}:{port}/{service_name}"
        conn = oracledb.connect(user=user, password=password, dsn=dsn)
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
            f"URL={conn_data['instance_url']};"
            f"AuthScheme=Basic;"
        )

        conn = sn_driver.connect(conn_str)
        return conn

    except Exception as e:
        print(f"ServiceNow connection error: {e}")
        return None

def create_csv_connection(conn_data):
    """Establishes a connection to a CSV file using CData CSV driver."""
    try:
        if not conn_data.get("db_path"):
            raise ValueError("Missing db_path in conn_data")
            
        # If it's a directory, CData CSV driver treats it as a database of CSV files
        # If it's a file, it treats it as a single table
        path = conn_data['db_path']
        
        conn_str = f"URI={path};"
        conn = csv_driver.connect(conn_str)
        return conn
    except Exception as e:
        print(f"CSV connection error: {e}")
        return None
