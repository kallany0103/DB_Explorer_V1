import sqlite3 as sqlite
import psycopg2
from psycopg2 import OperationalError
import oracledb
import sys
import os
from db.connection_pool import get_or_create_pool
# DEBUG-START
import time
# DEBUG-END
import cdata.servicenow as sn_driver
import cdata.csv as csv_driver

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# Database file path updated
DB_FILE = resource_path("databases/hierarchy.db")

_failed_hosts = {}
FAILED_HOST_COOLDOWN = 15 # seconds

# --- Database Connection Functions ---
def create_sqlite_connection(path):
    """Establishes a connection to a SQLite database."""
    try:
        # isolation_level=None enables autocommit mode, 
        # allowing manual BEGIN/COMMIT/ROLLBACK in SQL scripts
        conn = sqlite.connect(path, isolation_level=None)
        return conn
    except sqlite.Error as e:
        print(f"SQLite connection error: {e}")
        return None


def create_postgres_connection(host, port=None, database=None, user=None, password=None, application_name=None, bypass_cooldown=False):
    """Establishes a connection to a PostgreSQL database with SSL support for cloud hosts."""
    try:
        app_name = application_name

        host_key = None
        if isinstance(host, dict):
            host_key = host.get("host") or host.get("dsn")
        else:
            host_key = host

        if not bypass_cooldown and host_key and host_key in _failed_hosts:
            if time.time() - _failed_hosts[host_key] < FAILED_HOST_COOLDOWN:
                return None
            else:
                del _failed_hosts[host_key]


        if isinstance(host, dict):
            conn_data = host
            dsn = conn_data.get("dsn")
            
            # Use application_name from conn_data if provided and not overridden by arg
            if not app_name:
                app_name = conn_data.get("application_name") or conn_data.get("name")

            if dsn:
                try:
                    # Safely merge application_name into DSN using psycopg2's own parser
                    from psycopg2.extensions import make_dsn
                    from psycopg2 import connect as pg_connect
                    
                    # Ensure we have a default name
                    final_app_name = app_name or "Universal SQL Client"
                    
                    # Detect if this is a cloud host to force SSL
                    is_cloud = any(cloud_domain in str(dsn).lower() or cloud_domain in str(host_key).lower() 
                                  for cloud_domain in ["aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"])

                    # Convert DSN to dict, override app name, and convert back to DSN
                    try:
                        # This handles both URL and keyword-style DSNs
                        import urllib.parse
                        if "://" in dsn:
                            # URL style: add to query params
                            u = urllib.parse.urlparse(dsn)
                            q = urllib.parse.parse_qs(u.query)
                            q['application_name'] = [final_app_name]
                            if is_cloud:
                                q['sslmode'] = ['require']
                            u = u._replace(query=urllib.parse.urlencode(q, doseq=True))
                            dsn = urllib.parse.urlunparse(u)
                        else:
                            # Keyword style: append with quotes if needed
                            if "application_name" not in dsn:
                                dsn += f" application_name='{final_app_name}'"
                            if is_cloud and "sslmode" not in dsn:
                                dsn += " sslmode='require'"
                    except:
                        pass # Fallback to original DSN if parsing fails
                        
                    # Use underscores for better compatibility with poolers/command line
                    safe_app_name = final_app_name.replace(" ", "_")
                    return psycopg2.connect(dsn, connect_timeout=5, application_name=safe_app_name)

                except Exception as e:
                    err_str = str(e)
                    if "timeout expired" in err_str or "Name or service not known" in err_str:
                        if host_key: _failed_hosts[host_key] = time.time()
                        return None
                    else:
                        print(f"DSN connection failed, falling back to keywords: {e}")

            host = conn_data.get("host")
            port = conn_data.get("port")
            database = conn_data.get("database")
            user = conn_data.get("user")
            password = conn_data.get("password")

        if not app_name:
            db_name = database
            if not db_name and isinstance(host, dict):
                db_name = host.get("database")
            
            if db_name:
                app_name = f"Universal SQL Client - {db_name}"
            else:
                app_name = "Universal SQL Client"

        if not host:
            return None

        # Basic connection parameters
        # Ensure application name is safe for command line (no spaces)
        safe_app_name = (app_name or "Universal_SQL_Client").replace(" ", "_")
        
        params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "connect_timeout": 5,
            "application_name": safe_app_name
        }
        
        # Determine if we should use SSL immediately (Aiven, Heroku, ElephantSQL, AWS)
        is_cloud = any(cloud_domain in str(host).lower() for cloud_domain in [
            "aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"
        ])
        
        if is_cloud:
            params["sslmode"] = "require"

        try:
            conn = psycopg2.connect(**params)
            return conn
        except OperationalError as e:
            if not is_cloud:
                # Retry with SSL for other hosts if first attempt fails
                try:
                    params["sslmode"] = "require"
                    conn = psycopg2.connect(**params)
                    return conn
                except OperationalError:
                    pass # Fall through to print original error
            
            # Print error only if it's not a common network issue or if it's a new error
            err_str = str(e).strip()
            if "timeout expired" in err_str:
                if host_key: _failed_hosts[host_key] = time.time()
                # print(f"PostgreSQL connection timeout: {host}")
            elif "Name or service not known" in err_str:
                if host_key: _failed_hosts[host_key] = time.time()
                # print(f"PostgreSQL host unreachable: {host}")
            else:
                print(f"PostgreSQL connection error: {err_str}")
            return None
            
    except Exception as e:
        print(f"Unexpected PostgreSQL connection error: {e}")
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

        # DEBUG-START
        t0 = time.time()
        # DEBUG-END
        conn = sn_driver.connect(conn_str)
        # DEBUG-START
        t1 = time.time()
        print(f"[SN-DEBUG] sn_driver.connect() took {t1-t0:.2f}s")
        # DEBUG-END
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
        
        # Configure CData CSV driver to scan more rows and use 64-bit integers
        # to avoid Int32 overflow errors with large values like 5600000000
        # RowScanDepth=0 scans every row so values like 5_600_000_000
        # are detected as Int64 instead of overflowing the default Int32.
        conn_str = f"URI={path};TypeDetectionScheme=RowScan;RowScanDepth=100;"
        conn = csv_driver.connect(conn_str)
        return conn
    except Exception as e:
        print(f"CSV connection error: {e}")
        return None


# =========================================================
# CONNECTION POOLING FOR PostgreSQL
# =========================================================

def get_pooled_postgres_connection(host, port=None, database=None, user=None, password=None, application_name=None, use_pool=True):
    """
    Get a PostgreSQL connection from the pool.
    
    If use_pool=False, falls back to creating a non-pooled connection (legacy behavior).
    
    Args:
        host: Host or connection data dict
        port: Port number
        database: Database name
        user: Username
        password: Password
        application_name: Application name for the connection
        use_pool: Whether to use connection pooling (default: True)
    
    Returns:
        Database connection or None
    """
    
    
    # Normalize parameters from dict if host is a connection data dict
    if isinstance(host, dict):
        conn_data = host
        pool_key = (conn_data.get("host"), int(conn_data.get("port", 5432)), 
                   conn_data.get("database"), conn_data.get("user"))
        
        if not use_pool:
            return create_postgres_connection(conn_data, application_name=application_name)
        
        pool = get_or_create_pool(conn_data)
        return pool.get_connection()
    else:
        # Legacy parameter style
        if not use_pool:
            return create_postgres_connection(host, port, database, user, password, application_name)
        
        conn_params = {
            'host': host,
            'port': port or 5432,
            'database': database,
            'user': user,
            'password': password,
            'application_name': application_name or "Universal SQL Client"
        }
        
        pool = get_or_create_pool(conn_params)
        return pool.get_connection()


def return_pooled_postgres_connection(host, port=None, database=None, user=None, password=None, conn=None):
    """
    Return a connection to the pool.
    
    Args:
        host: Host or connection data dict (used to identify the pool)
        port: Port number
        database: Database name
        user: Username
        password: Password
        conn: The connection to return to the pool
    """
    
    if conn is None:
        return
    
    try:
        if isinstance(host, dict):
            conn_data = host
            pool = get_or_create_pool(conn_data)
        else:
            conn_params = {
                'host': host,
                'port': port or 5432,
                'database': database,
                'user': user,
                'password': password,
            }
            pool = get_or_create_pool(conn_params)
        
        pool.return_connection(conn)
    except Exception as e:
        print(f"Error returning connection to pool: {e}")
        try:
            conn.close()
        except Exception:
            pass


class PooledPostgresConnection:
    """
    Context manager for pooled PostgreSQL connections.
    
    Usage:
        with PooledPostgresConnection(conn_data) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
            results = cursor.fetchall()
    """
    
    def __init__(self, conn_data, application_name=None):
        self.conn_data = conn_data
        self.application_name = application_name
        self.conn = None
    
    def __enter__(self):
        self.conn = get_pooled_postgres_connection(
            self.conn_data, 
            application_name=self.application_name,
            use_pool=True
        )
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            return_pooled_postgres_connection(self.conn_data, conn=self.conn)
        return False


def close_all_postgres_pools():
    """Close all PostgreSQL connection pools. Call on application shutdown."""
    from db.connection_pool import close_all_pools
    close_all_pools()
