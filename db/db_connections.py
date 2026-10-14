# db_connections.py
import sqlite3 as sqlite
import psycopg2
from psycopg2 import OperationalError
import sys
import os
import time
import cdata.servicenow as sn_driver
import cdata.csv as csv_driver
import urllib.parse
import logging
from typing import Any
from db.connection_pool import (
    get_or_create_pool,
    get_or_create_oracle_pool,
    close_all_pools,
    invalidate_pool,
    invalidate_oracle_pool,
)

__all__ = [
    "create_sqlite_connection",
    "create_postgres_connection",
    "get_pooled_oracle_connection",
    "create_servicenow_connection",
    "create_csv_connection",
    "get_pooled_postgres_connection",
    "return_pooled_postgres_connection",
    "PooledPostgresConnection",
    "close_all_postgres_pools",
    "invalidate_pool",
    "invalidate_oracle_pool",
    "resource_path",
    "DB_FILE",
]

def resource_path(relative_path: str) -> str:
    """Get absolute path to a bundled read-only resource (assets, ui, etc.)."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def user_data_path(relative_path: str) -> str:
    """Get absolute path to a user-writable data file.

    When running as a PyInstaller bundle the file lives under
    %APPDATA%\\Universal SQL Client so that it is writable even
    when the app is installed in Program Files.
    In development mode it falls back to the local project directory.
    """
    if getattr(sys, 'frozen', False):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "Universal SQL Client")
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def get_downloads_dir() -> str:
    """Return the user's Downloads folder, falling back to the home directory."""
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    return downloads if os.path.isdir(downloads) else home


# hierarchy.db is a user-writable file — must NOT live inside the install dir
DB_FILE = user_data_path("databases/hierarchy.db")

_failed_hosts = {}
FAILED_HOST_COOLDOWN = 15 # seconds

# --- Database Connection Functions ---
def create_sqlite_connection(path):
    """Establishes a connection to a SQLite database."""
    try:
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

        if bypass_cooldown and host_key:
            _failed_hosts.pop(host_key, None)
        elif not bypass_cooldown and host_key and host_key in _failed_hosts:
            if time.time() - _failed_hosts[host_key] < FAILED_HOST_COOLDOWN:
                return None
            else:
                del _failed_hosts[host_key]


        if isinstance(host, dict):
            conn_data = host
            dsn = conn_data.get("dsn")
            
            if not app_name:
                app_name = conn_data.get("application_name") or conn_data.get("name")

            if dsn:
                try:
                    final_app_name = app_name or "Universal SQL Client"
                    
                    is_cloud = any(cloud_domain in str(dsn).lower() or cloud_domain in str(host_key).lower() 
                                  for cloud_domain in ["aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"])

                    # Convert DSN to dict, override app name, and convert back to DSN
                    try:
                        # This handles both URL and keyword-style DSNs
                        if "://" in dsn:
                            # URL style: add to query params
                            u = urllib.parse.urlparse(dsn)
                            q = urllib.parse.parse_qs(u.query)
                            q['application_name'] = [final_app_name]
                            if is_cloud:
                                q['sslmode'] = ['require']

                            # If a standalone password was saved separately (e.g. from Edit Connection),
                            # inject it into the DSN URL so the stored password always wins
                            standalone_pwd = conn_data.get("password")
                            if standalone_pwd is not None and str(standalone_pwd).strip():
                                netloc = u.netloc
                                # Replace or insert the password in user:pass@host
                                if '@' in netloc:
                                    userinfo, hostpart = netloc.rsplit('@', 1)
                                    username_part = userinfo.split(':')[0]
                                    netloc = f"{username_part}:{urllib.parse.quote(str(standalone_pwd), safe='')}@{hostpart}"
                                u = u._replace(netloc=netloc)

                            u = u._replace(query=urllib.parse.urlencode(q, doseq=True))
                            dsn = urllib.parse.urlunparse(u)
                        else:
                            # Keyword style: append with quotes if needed
                            if "application_name" not in dsn:
                                dsn += f" application_name='{final_app_name}'"
                            if is_cloud and "sslmode" not in dsn:
                                dsn += " sslmode='require'"
                            # Override password in keyword DSN if set separately
                            standalone_pwd = conn_data.get("password")
                            if standalone_pwd is not None and str(standalone_pwd).strip():
                                import re as _re
                                dsn = _re.sub(r"password='[^']*'", f"password='{standalone_pwd}'", dsn)
                                if "password=" not in dsn:
                                    dsn += f" password='{standalone_pwd}'"
                    except Exception:
                        pass # Fallback to original DSN if parsing fails
                        
                    # Use underscores for better compatibility with poolers/command line
                    safe_app_name = final_app_name.replace(" ", "_")
                    return psycopg2.connect(dsn, connect_timeout=5, application_name=safe_app_name)

                except Exception as e:
                    err_str = str(e)
                    if "timeout expired" in err_str or "Name or service not known" in err_str:
                        if host_key:
                            _failed_hosts[host_key] = time.time()
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
        
        # Determine if we should use SSL immediately (Aiven, Heroku, ElephantSQL, AWS, Supabase)
        is_cloud = any(cloud_domain in str(host).lower() for cloud_domain in [
            "aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com",
            "cloud.google.com", "supabase.com", "supabase.io",
        ])
        
        if is_cloud:
            params["sslmode"] = "require"

        try:
            conn = psycopg2.connect(**params)
            if host_key:
                _failed_hosts.pop(host_key, None)
            return conn
        except OperationalError as e:
            if not is_cloud:
                # Retry with SSL for other hosts if first attempt fails
                try:
                    params["sslmode"] = "require"
                    conn = psycopg2.connect(**params)
                    if host_key:
                        _failed_hosts.pop(host_key, None)
                    return conn
                except OperationalError:
                    pass # Fall through to print original error
            
            # Print error only if it's not a common network issue or if it's a new error
            err_str = str(e).strip()
            if "timeout expired" in err_str:
                if host_key:
                    _failed_hosts[host_key] = time.time()
                # print(f"PostgreSQL connection timeout: {host}")
            elif "Name or service not known" in err_str:
                if host_key:
                    _failed_hosts[host_key] = time.time()
                # print(f"PostgreSQL host unreachable: {host}")
            else:
                print(f"PostgreSQL connection error: {err_str}")
            return None
            
    except Exception as e:
        print(f"Unexpected PostgreSQL connection error: {e}")
        return None


_oracle_thick_mode_initialized = False

def _init_oracle_thick_mode(lib_dir: str | None = None) -> bool:
    global _oracle_thick_mode_initialized
    from db.oracle_utils import init_oracle_thick_mode
    success = init_oracle_thick_mode(lib_dir=lib_dir)
    if success:
        _oracle_thick_mode_initialized = True
    return success

def get_pooled_oracle_connection(host=None, port=None, service_name=None, user=None, password=None, conn_data=None, use_pool=True):
    """
    Get a pooled Oracle connection. Can accept either kwargs or a conn_data dictionary.
    Defaults to pure Python Thin mode (no client library required) unless Thick mode is requested.
    """
    if conn_data:
        driver_mode = str(conn_data.get("driver_mode", "")).lower()
        client_dir = conn_data.get("oracle_client_dir")
        if driver_mode == "thick" or client_dir:
            if not _init_oracle_thick_mode(client_dir):
                from db.oracle_utils import get_last_thick_mode_error
                err = get_last_thick_mode_error() or "Failed to load Oracle Instant Client"
                target = client_dir or "system default"
                raise ConnectionError(
                    f"Oracle Thick Mode (Instant Client) failed to initialize with client directory '{target}':\n\n{err}"
                )
    
    if conn_data is None:
        conn_data = {
            "host": host,
            "port": port,
            "service_name": service_name,
            "user": user,
            "password": password
        }
        
    try:
        import oracledb as _oracledb  # noqa: PLC0415  lazy — must not move to top-level
        if not use_pool:
            # Fallback to direct connection if pooling is disabled
            user = conn_data.get("user")
            password = conn_data.get("password")
            dsn = conn_data.get("dsn")
            if not dsn:
                host = conn_data.get("host")
                port = conn_data.get("port") or 1521
                service_name = conn_data.get("service_name") or conn_data.get("database")
                db_type = conn_data.get("oracle_db_type") or "service_name"
                from db.oracle_utils import build_oracle_dsn
                dsn = build_oracle_dsn(host, port, service_name, db_type=db_type)

            from db.oracle_utils import get_oracle_auth_mode
            mode = get_oracle_auth_mode(conn_data.get("role"))

            connect_kwargs: dict[str, Any] = {
                "user": user,
                "password": password,
                "dsn": dsn,
            }
            if mode != _oracledb.AUTH_MODE_DEFAULT:
                connect_kwargs["mode"] = mode
            if conn_data.get("config_dir"):
                connect_kwargs["config_dir"] = conn_data.get("config_dir")

            return _oracledb.connect(**connect_kwargs)

        pool = get_or_create_oracle_pool(conn_data)
        return pool.acquire()
    except Exception as e:
        import oracledb as _oracledb  # noqa: PLC0415
        if isinstance(e, _oracledb.DatabaseError):
            from db.oracle_utils import diagnose_oracle_error
            advice = diagnose_oracle_error(e)
            err_msg = f"Oracle connection error: {e}"
            if advice:
                err_msg += f"\n\nDiagnostic advice:\n{advice}"
            logging.error(err_msg)
            raise ConnectionError(err_msg) from e
        raise
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
        path = conn_data['db_path']
        conn_str = f"URI={path};TypeDetectionScheme=RowScan;RowScanDepth=100;"
        conn = csv_driver.connect(conn_str)
        return conn
    except Exception as e:
        print(f"CSV connection error: {e}")
        return None



# CONNECTION POOLING FOR PostgreSQL


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
        (conn_data.get("host"), int(conn_data.get("port", 5432)), 
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
    close_all_pools()
